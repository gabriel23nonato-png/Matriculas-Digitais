# ─────────────────────────────────────────────────────────────────
# SUBSTITUIÇÃO COMPLETA do bloco get_db() + teardown no app.py
#
# Correções aplicadas:
#  1. BEGIN IMMEDIATE na transação → evita "database is locked" em escrita
#  2. Serialização via threading.Lock → nunca dois POSTs escrevem juntos
#  3. WAL + busy_timeout mantidos como segunda linha de defesa
# ─────────────────────────────────────────────────────────────────

import sqlite3
import threading
from flask import g

# Lock global — garante que apenas UM request faz escrita por vez.
# Leituras (GET) passam direto; só o bloco "with _write_lock:" serializa.
_write_lock = threading.Lock()


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(
            DATABASE, timeout=15, check_same_thread=False
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA busy_timeout = 8000")
        db.execute("PRAGMA synchronous = NORMAL")  # boa performance com WAL
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        if exception:
            db.rollback()  # garante rollback se a rota crashou no meio
        db.close()


# ─────────────────────────────────────────────────────────────────
# COMO USAR o _write_lock nas rotas de escrita
#
# Envolva TODO o bloco de INSERTs/UPDATEs/DELETEs com o lock:
#
#   @app.route('/nova_matricula', methods=['GET', 'POST'])
#   def nova_matricula():
#       if request.method == 'POST':
#           with _write_lock:               # ← ADICIONAR ISSO
#               db = get_db()
#               try:
#                   db.execute("BEGIN IMMEDIATE")
#                   db.execute("INSERT INTO aluno ...")
#                   aluno_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
#                   db.execute("INSERT INTO responsavel ...")
#                   db.execute("INSERT INTO endereco ...")
#                   db.execute("INSERT INTO saude ...")
#                   db.execute("INSERT INTO matricula ...")
#                   db.execute("COMMIT")
#               except Exception as e:
#                   db.execute("ROLLBACK")
#                   app.logger.error(f"Erro ao salvar matrícula: {e}")
#                   return render_template('nova_matricula.html',
#                                          erro="Erro ao salvar. Tente novamente.",
#                                          modo='novo', salas=SALAS, aluno=None, documentos=[])
#           return redirect(url_for('listar_alunos'))   # fora do with, após commit
#
# O mesmo padrão vale para editar_matricula e excluir_matricula.
# ─────────────────────────────────────────────────────────────────
