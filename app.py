"""
Sistema de Matrículas Escolares – app.py
Banco  : alunosv3_novo.db (schema normalizado em 5 tabelas)
Storage: Google Drive via OAuth 2.0 / InstalledAppFlow (drive_service.py)
Config : .env  →  DRIVE_ROOT_FOLDER_ID, SECRET_KEY
         client_secret.json e token.json na raiz do projeto
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from flask import (
    Flask, g, redirect, render_template,
    request, send_from_directory, url_for, flash, jsonify,
)
from werkzeug.utils import secure_filename


def app_dir() -> str:
    """
    Pasta onde os dados PERSISTENTES devem morar (banco, uploads, .env,
    client_secret.json, token.json).

    - Rodando como .py normal: pasta deste arquivo.
    - Rodando como .exe (PyInstaller): pasta onde o .exe está, NÃO a pasta
      temporária de extração (sys._MEIPASS). Se usássemos _MEIPASS aqui,
      o banco de dados e o login do Drive seriam recriados do zero a cada
      vez que o programa fosse aberto, porque essa pasta temp muda toda hora.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(rel: str) -> str:
    """
    Pasta onde os recursos EMBUTIDOS no executável estão (templates, static).
    Esses são só leitura e podem ficar na pasta temporária do PyInstaller.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# Carrega .env ANTES de qualquer import que leia variáveis de ambiente.
# Procurado ao lado do .exe (ou do app.py, fora do .exe).
load_dotenv(os.path.join(app_dir(), ".env"))

# ── Importa Drive com fallback seguro ─────────────────────────────────────────
try:
    import drive_service as drive
    _DRIVE_IMPORT_OK = True
except ImportError:
    _DRIVE_IMPORT_OK = False

# ── Configuração ──────────────────────────────────────────────────────────────
BASE_DIR      = app_dir()
DATABASE      = os.path.join(BASE_DIR, "database", "database", "alunosv3_novo.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}

SALAS_IV  = ["IVA", "IVB", "IVC", "IVD", "IVE"]
SALAS_V   = ["VA",  "VB",  "VC",  "VD",  "VE"]
SALAS     = ["Sem Sala"] + SALAS_IV + SALAS_V

UFS = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
    "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO",
]

CAMPOS_NUMERICOS = {"contribuicao"}
CAMPOS_DATA      = {"data_nascimento", "expedicao_rg_mae", "validade_vacina"}

CAMPOS_UPLOAD = [
    "doc_cpf", "doc_cartao_sus", "doc_certidao",
    "doc_cpf_mae", "doc_cpf_pai", "doc_cep",
    "doc_laudo", "doc_carteira_vacinacao", "doc_comprovante_vacinacao",
]

os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "matriculas_beta_2025")
app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB


# ── Banco de dados ────────────────────────────────────────────────────────────
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


@app.teardown_appcontext
def close_db(_exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def _add_col(db, tabela, coluna, tipo):
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({tabela})").fetchall()]
    if coluna not in cols:
        db.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        logger.info("Banco: coluna '%s.%s' adicionada.", tabela, coluna)


def init_db():
    """Cria/atualiza o schema — idempotente."""
    db = get_db()
    db.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS aluno (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        ra                   TEXT,
        rm                   TEXT,
        nome_completo        TEXT NOT NULL,
        data_nascimento      DATE,
        sexo                 TEXT,
        raca_cor             TEXT,
        nacionalidade        TEXT,
        municipio_nascimento TEXT,
        rg_aluno             TEXT,
        cpf_aluno            TEXT,
        cartao_sus           TEXT,
        certidao_nascimento  TEXT,
        rne                  TEXT,
        gemeo                TEXT,
        criado_em            DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_aluno_nome ON aluno(nome_completo);
    CREATE INDEX IF NOT EXISTS idx_aluno_cpf  ON aluno(cpf_aluno);

    CREATE TABLE IF NOT EXISTS responsavel (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id              INTEGER NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
        nome_mae              TEXT, cpf_mae TEXT, rg_mae TEXT,
        uf_rg_mae             TEXT, expedicao_rg_mae TEXT,
        estado_civil_mae      TEXT, profissao_mae TEXT, email_mae TEXT,
        nome_pai              TEXT, cpf_pai TEXT, rg_pai TEXT, profissao_pai TEXT,
        responsavel_matricula TEXT,
        telefone1 TEXT, telefone2 TEXT, telefone3 TEXT, telefone4 TEXT,
        bolsa_familia TEXT, nis TEXT,
        pessoa1 TEXT, pessoa2 TEXT, pessoa3 TEXT
    );

    CREATE TABLE IF NOT EXISTS endereco (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id   INTEGER NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
        logradouro TEXT, numero TEXT, bairro TEXT,
        cidade TEXT, estado TEXT, cep TEXT
    );

    CREATE TABLE IF NOT EXISTS saude (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id       INTEGER NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
        tipo_sanguineo TEXT, alergico TEXT, diabetico TEXT,
        lactose TEXT, aplv TEXT, plano TEXT,
        uniforme TEXT, calcado TEXT, observacoes TEXT
    );

    CREATE TABLE IF NOT EXISTS matricula (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id          INTEGER NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
        nivel             TEXT,
        sala              TEXT DEFAULT 'Sem Sala',
        integral          TEXT,
        ano               TEXT,
        escola_anterior   TEXT,
        permite_edfisica  TEXT,
        permite_fotos     TEXT,
        permite_passeios  TEXT,
        contribuicao      REAL,
        tipo_contribuicao TEXT,
        data_matricula    DATETIME DEFAULT CURRENT_TIMESTAMP,
        data_modificacao  TEXT,
        ativo             INTEGER DEFAULT 1
    );
    CREATE INDEX IF NOT EXISTS idx_matricula_nivel  ON matricula(nivel);
    CREATE INDEX IF NOT EXISTS idx_matricula_sala   ON matricula(sala);
    CREATE INDEX IF NOT EXISTS idx_matricula_aluno  ON matricula(aluno_id);

    CREATE TABLE IF NOT EXISTS documento (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id   INTEGER NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
        campo      TEXT,
        nome       TEXT,
        subpasta   TEXT,
        drive_id   TEXT,
        drive_url  TEXT,
        enviado_em DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # Migrações seguras — adiciona colunas ausentes em bancos existentes
    for col, tipo in [("data_modificacao","TEXT")]:
        _add_col(db, "matricula", col, tipo)
    _add_col(db, "saude", "validade_vacina", "DATE")
    for col, tipo in [("campo","TEXT"),("subpasta","TEXT"),("drive_id","TEXT"),("drive_url","TEXT")]:
        _add_col(db, "documento", col, tipo)
    db.commit()


# ── Normalização centralizada ─────────────────────────────────────────────────
def normalizar(campo: str, valor) -> object:
    """
    Regras por tipo de campo:
    • Datas       → string ISO ou None
    • Numéricos   → float ou None
    • CPFs        → valor ou None  (nunca "NÃO INFORMADO" — são identificadores)
    • Selects/radio → valor exato preservado (Sim/Não, INFANTIL IV, etc.)
    • Texto livre → UPPER ou "NÃO INFORMADO"
    """
    v = str(valor).strip() if valor is not None else ""

    if campo in CAMPOS_DATA:
        return v or None

    if campo in CAMPOS_NUMERICOS:
        if not v:
            return None
        try:
            return float(v.replace(",", "."))
        except (ValueError, TypeError):
            return None

    if campo in ("cpf_aluno", "cpf_mae", "cpf_pai"):
        return v if v else None

    # Campos cujo valor deve ser preservado exatamente como veio do formulário
    CAMPOS_PRESERVAR_CASE = {
        "permite_edfisica", "permite_fotos", "permite_passeios",
        "sexo", "integral", "gemeo", "bolsa_familia",
        "tipo_contribuicao", "nivel", "sala",
        "estado_civil_mae", "raca_cor", "uf_rg_mae",
        "uniforme", "calcado", "tipo_sanguineo", "lactose", "aplv", "diabetico",
    }
    if campo in CAMPOS_PRESERVAR_CASE:
        return v if v else "NÃO INFORMADO"

    # Texto livre → CAPS
    return v.upper() if v else "NÃO INFORMADO"


def form_para_dict(form, campos: list) -> dict:
    return {c: normalizar(c, form.get(c, "")) for c in campos}


def agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_aluno_completo(aluno_id):
    return get_db().execute(
        """
        SELECT
            a.id, a.ra, a.rm, a.nome_completo, a.data_nascimento,
            a.sexo, a.raca_cor, a.nacionalidade, a.municipio_nascimento,
            a.rg_aluno, a.cpf_aluno, a.cartao_sus, a.certidao_nascimento,
            a.rne, a.gemeo, a.criado_em,
            r.nome_mae, r.cpf_mae, r.rg_mae, r.uf_rg_mae, r.expedicao_rg_mae,
            r.estado_civil_mae, r.profissao_mae, r.email_mae,
            r.nome_pai, r.cpf_pai, r.rg_pai, r.profissao_pai,
            r.responsavel_matricula,
            r.telefone1, r.telefone2, r.telefone3, r.telefone4,
            r.bolsa_familia, r.nis, r.pessoa1, r.pessoa2, r.pessoa3,
            e.logradouro, e.numero, e.bairro, e.cidade, e.estado, e.cep,
            s.tipo_sanguineo, s.alergico, s.diabetico, s.lactose, s.aplv,
            s.plano, s.uniforme, s.calcado, s.observacoes, s.validade_vacina,
            m.id AS matricula_id, m.nivel, m.sala, m.integral, m.ano,
            m.escola_anterior, m.permite_edfisica, m.permite_fotos,
            m.permite_passeios, m.contribuicao, m.tipo_contribuicao,
            m.data_modificacao
        FROM aluno a
        LEFT JOIN responsavel r ON r.aluno_id = a.id
        LEFT JOIN endereco    e ON e.aluno_id = a.id
        LEFT JOIN saude       s ON s.aluno_id = a.id
        LEFT JOIN matricula   m ON m.aluno_id = a.id
        WHERE a.id = ?
        ORDER BY m.id DESC LIMIT 1
        """,
        (aluno_id,),
    ).fetchone()


# ── Drive ─────────────────────────────────────────────────────────────────────
def _drive_ativo() -> bool:
    return _DRIVE_IMPORT_OK and drive.drive_disponivel()


def processar_uploads(aluno_id: int, ano: str, sala: str, nome_aluno: str):
    """Processa todos os campos de upload do request atual."""
    db = get_db()
    ok = _drive_ativo()

    for campo in CAMPOS_UPLOAD:
        arquivo = request.files.get(campo)
        if not arquivo or not arquivo.filename:
            continue
        if not allowed_file(arquivo.filename):
            flash(f"'{arquivo.filename}' ignorado — extensão não permitida.", "warning")
            continue

        nome_original = arquivo.filename
        nome_seguro   = secure_filename(f"{aluno_id}_{campo}_{nome_original}")
        subpasta_nome = drive.CAMPO_PARA_SUBPASTA.get(campo, "OUTROS") if _DRIVE_IMPORT_OK else "OUTROS"
        drive_id  = None
        drive_url = None

        if ok:
            try:
                arquivo.stream.seek(0)
                res = drive.upload_documento(
                    file_stream=arquivo.stream,
                    filename=nome_original,
                    campo=campo,
                    ano=str(ano),
                    sala=str(sala),
                    nome_aluno=nome_aluno,
                )
                drive_id      = res["drive_id"]
                drive_url     = res["drive_url"]
                subpasta_nome = res["subpasta"]
                logger.info("Drive: upload OK — %s → %s", nome_original, subpasta_nome)
            except Exception as exc:
                logger.error("Drive: falha em '%s': %s", nome_original, exc)
                flash(f"'{nome_original}' salvo localmente (Drive indisponível: {exc}).", "warning")
                arquivo.stream.seek(0)
                arquivo.save(os.path.join(app.config["UPLOAD_FOLDER"], nome_seguro))
        else:
            arquivo.stream.seek(0)
            arquivo.save(os.path.join(app.config["UPLOAD_FOLDER"], nome_seguro))

        db.execute(
            "INSERT INTO documento (aluno_id, campo, nome, subpasta, drive_id, drive_url) VALUES (?,?,?,?,?,?)",
            (aluno_id, campo, nome_original, subpasta_nome, drive_id, drive_url),
        )
    db.commit()


def verificar_divergencias(aluno_id: int) -> dict:
    db   = get_db()
    docs = db.execute(
        "SELECT id, campo, nome, drive_id, drive_url, subpasta FROM documento WHERE aluno_id=?",
        (aluno_id,),
    ).fetchall()

    ausentes  = []
    sem_drive = []
    ids_check = [d["drive_id"] for d in docs if d["drive_id"]]
    existencia = {}

    if _drive_ativo() and ids_check:
        try:
            existencia = drive.verificar_existencia(ids_check)
        except Exception as exc:
            logger.warning("Drive: verificação de existência falhou: %s", exc)

    for doc in docs:
        if not doc["drive_id"]:
            sem_drive.append(dict(doc))
        elif existencia.get(doc["drive_id"]) is False:
            ausentes.append(dict(doc))

    return {"total": len(docs), "ausentes": ausentes, "sem_drive": sem_drive}


# ── Rotas ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/alunos")
def listar_alunos():
    db    = get_db()
    q     = request.args.get("q",     "").strip()
    nivel = request.args.get("nivel", "").strip()
    sala  = request.args.get("sala",  "").strip()
    ordem = request.args.get("ordem", "nome")

    sql = """
        SELECT a.id, a.nome_completo, r.nome_mae, m.nivel, m.sala, m.data_modificacao
        FROM aluno a
        LEFT JOIN responsavel r ON r.aluno_id = a.id
        LEFT JOIN matricula   m ON m.aluno_id = a.id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND (a.nome_completo LIKE ? OR r.nome_mae LIKE ? OR a.cpf_aluno LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if nivel:
        sql += " AND m.nivel LIKE ?"
        params.append(f"%{nivel}%")
    if sala:
        sql += " AND m.sala = ?"
        params.append(sala)
    sql += (" ORDER BY m.data_modificacao DESC"
            if ordem == "data_modificacao" else " ORDER BY a.nome_completo")

    alunos = db.execute(sql, params).fetchall()
    return render_template(
        "alunos.html",
        alunos=alunos, q=q, nivel=nivel, sala=sala,
        salas=SALAS, salas_iv=SALAS_IV, salas_v=SALAS_V, ordem=ordem,
    )


@app.route("/nova_matricula", methods=["GET", "POST"])
def nova_matricula():
    if request.method == "POST":
        f  = request.form
        db = get_db()

        a = form_para_dict(f, [
            "ra","rm","nome_completo","data_nascimento","sexo","raca_cor",
            "nacionalidade","municipio_nascimento","rg_aluno","cpf_aluno",
            "cartao_sus","certidao_nascimento","rne","gemeo",
        ])
        db.execute(
            """INSERT INTO aluno (ra,rm,nome_completo,data_nascimento,sexo,raca_cor,
               nacionalidade,municipio_nascimento,rg_aluno,cpf_aluno,
               cartao_sus,certidao_nascimento,rne,gemeo)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            list(a.values()),
        )
        aluno_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        r = form_para_dict(f, [
            "nome_mae","cpf_mae","rg_mae","uf_rg_mae","expedicao_rg_mae",
            "estado_civil_mae","profissao_mae","nome_pai","cpf_pai","rg_pai",
            "profissao_pai","responsavel_matricula",
            "telefone1","telefone2","telefone3","telefone4",
            "bolsa_familia","nis","pessoa1","pessoa2","pessoa3",
        ])
        db.execute(
            """INSERT INTO responsavel (aluno_id,nome_mae,cpf_mae,rg_mae,uf_rg_mae,
               expedicao_rg_mae,estado_civil_mae,profissao_mae,nome_pai,cpf_pai,rg_pai,
               profissao_pai,responsavel_matricula,telefone1,telefone2,telefone3,telefone4,
               bolsa_familia,nis,pessoa1,pessoa2,pessoa3)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [aluno_id] + list(r.values()),
        )

        e = form_para_dict(f, ["logradouro","numero","bairro","cidade_end","estado","cep"])
        db.execute(
            """INSERT INTO endereco (aluno_id,logradouro,numero,bairro,cidade,estado,cep)
               VALUES (?,?,?,?,?,?,?)""",
            [aluno_id, e["logradouro"], e["numero"], e["bairro"],
             e["cidade_end"], e["estado"], e["cep"]],
        )

        s = form_para_dict(f, [
            "tipo_sanguineo","alergico","diabetico","lactose","aplv",
            "plano","uniforme","calcado","observacoes","validade_vacina",
        ])
        db.execute(
            """INSERT INTO saude (aluno_id,tipo_sanguineo,alergico,diabetico,lactose,aplv,
               plano,uniforme,calcado,observacoes,validade_vacina) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [aluno_id] + list(s.values()),
        )

        m = form_para_dict(f, [
            "nivel","sala","integral","escola_anterior",
            "permite_edfisica","permite_fotos","permite_passeios",
            "contribuicao","tipo_contribuicao",
        ])
        ano_val = normalizar("ano_texto", f.get("ano_matricula", ""))
        db.execute(
            """INSERT INTO matricula (aluno_id,nivel,sala,integral,ano,escola_anterior,
               permite_edfisica,permite_fotos,permite_passeios,contribuicao,
               tipo_contribuicao,data_modificacao)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [aluno_id, m["nivel"], m["sala"], m["integral"], ano_val,
             m["escola_anterior"], m["permite_edfisica"], m["permite_fotos"],
             m["permite_passeios"], m["contribuicao"], m["tipo_contribuicao"],
             agora()],
        )
        db.commit()

        processar_uploads(
            aluno_id=aluno_id,
            ano=str(ano_val or "SEM_ANO"),
            sala=str(m["sala"]),
            nome_aluno=str(a["nome_completo"]),
        )

        flash(f"Matrícula de {a['nome_completo']} salva com sucesso!", "success")
        return redirect(url_for("listar_alunos"))

    return render_template(
        "nova_matricula.html",
        modo="novo", edicao_habilitada=True,
        aluno=None, documentos=[], divergencias=None,
        salas=SALAS, salas_iv=SALAS_IV, salas_v=SALAS_V, ufs=UFS,
        ano_atual=datetime.now().year,
        drive_ativo=_drive_ativo(),
    )


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_matricula(id):
    # Edição habilitada se vier ?editar=1 na URL, ou se for POST
    edicao_habilitada = request.args.get("editar") == "1" or request.method == "POST"
    aluno = _get_aluno_completo(id)

    if not aluno:
        flash("Aluno não encontrado.", "danger")
        return redirect(url_for("listar_alunos"))

    if request.method == "POST":
        f  = request.form
        db = get_db()

        a = form_para_dict(f, [
            "ra","rm","nome_completo","data_nascimento","sexo","raca_cor",
            "nacionalidade","municipio_nascimento","rg_aluno","cpf_aluno",
            "cartao_sus","certidao_nascimento","rne","gemeo",
        ])
        db.execute(
            """UPDATE aluno SET ra=?,rm=?,nome_completo=?,data_nascimento=?,sexo=?,
               raca_cor=?,nacionalidade=?,municipio_nascimento=?,rg_aluno=?,cpf_aluno=?,
               cartao_sus=?,certidao_nascimento=?,rne=?,gemeo=? WHERE id=?""",
            list(a.values()) + [id],
        )

        r = form_para_dict(f, [
            "nome_mae","cpf_mae","rg_mae","uf_rg_mae","expedicao_rg_mae",
            "estado_civil_mae","profissao_mae","nome_pai","cpf_pai","rg_pai",
            "profissao_pai","responsavel_matricula",
            "telefone1","telefone2","telefone3","telefone4",
            "bolsa_familia","nis","pessoa1","pessoa2","pessoa3",
        ])
        db.execute(
            """UPDATE responsavel SET nome_mae=?,cpf_mae=?,rg_mae=?,uf_rg_mae=?,
               expedicao_rg_mae=?,estado_civil_mae=?,profissao_mae=?,nome_pai=?,cpf_pai=?,
               rg_pai=?,profissao_pai=?,responsavel_matricula=?,telefone1=?,telefone2=?,
               telefone3=?,telefone4=?,bolsa_familia=?,nis=?,pessoa1=?,pessoa2=?,pessoa3=?
               WHERE aluno_id=?""",
            list(r.values()) + [id],
        )

        e = form_para_dict(f, ["logradouro","numero","bairro","cidade_end","estado","cep"])
        db.execute(
            """UPDATE endereco SET logradouro=?,numero=?,bairro=?,cidade=?,estado=?,cep=?
               WHERE aluno_id=?""",
            [e["logradouro"], e["numero"], e["bairro"],
             e["cidade_end"], e["estado"], e["cep"], id],
        )

        s = form_para_dict(f, [
            "tipo_sanguineo","alergico","diabetico","lactose","aplv",
            "plano","uniforme","calcado","observacoes","validade_vacina",
        ])
        db.execute(
            """UPDATE saude SET tipo_sanguineo=?,alergico=?,diabetico=?,lactose=?,aplv=?,
               plano=?,uniforme=?,calcado=?,observacoes=?,validade_vacina=? WHERE aluno_id=?""",
            list(s.values()) + [id],
        )

        m = form_para_dict(f, [
            "nivel","sala","integral","escola_anterior",
            "permite_edfisica","permite_fotos","permite_passeios",
            "contribuicao","tipo_contribuicao",
        ])
        ano_val = normalizar("ano_texto", f.get("ano_matricula", ""))
        db.execute(
            """UPDATE matricula SET nivel=?,sala=?,integral=?,ano=?,escola_anterior=?,
               permite_edfisica=?,permite_fotos=?,permite_passeios=?,contribuicao=?,
               tipo_contribuicao=?,data_modificacao=? WHERE aluno_id=?""",
            [m["nivel"], m["sala"], m["integral"], ano_val,
             m["escola_anterior"], m["permite_edfisica"], m["permite_fotos"],
             m["permite_passeios"], m["contribuicao"], m["tipo_contribuicao"],
             agora(), id],
        )
        db.commit()

        processar_uploads(
            aluno_id=id,
            ano=str(ano_val or aluno["ano"] or "SEM_ANO"),
            sala=str(m["sala"] or aluno["sala"]),
            nome_aluno=str(a["nome_completo"]),
        )

        flash(f"Matrícula de {a['nome_completo']} atualizada com sucesso!", "success")
        return redirect(url_for("listar_alunos"))

    # GET — carrega documentos e verifica divergências no Drive
    docs = get_db().execute(
        "SELECT * FROM documento WHERE aluno_id=? ORDER BY enviado_em DESC", (id,)
    ).fetchall()
    divergencias = verificar_divergencias(id) if edicao_habilitada else None

    return render_template(
        "nova_matricula.html",
        modo="editar", edicao_habilitada=edicao_habilitada,
        aluno=aluno, documentos=docs, divergencias=divergencias,
        salas=SALAS, salas_iv=SALAS_IV, salas_v=SALAS_V, ufs=UFS,
        ano_atual=datetime.now().year,
        drive_ativo=_drive_ativo(),
    )


@app.route("/excluir/<int:id>", methods=["POST"])
def excluir_matricula(id):
    db  = get_db()
    row = db.execute(
        """SELECT a.nome_completo, m.ano, m.sala
           FROM aluno a LEFT JOIN matricula m ON m.aluno_id = a.id
           WHERE a.id=? LIMIT 1""",
        (id,),
    ).fetchone()

    if not row:
        flash("Aluno não encontrado.", "danger")
        return redirect(url_for("listar_alunos"))

    nome = row["nome_completo"]
    ano  = row["ano"]  or "SEM_ANO"
    sala = row["sala"] or "SEM_SALA"

    if _drive_ativo():
        try:
            drive.deletar_pasta_aluno(ano=ano, sala=sala, nome_aluno=nome)
        except Exception as exc:
            logger.error("Drive: erro ao deletar pasta de '%s': %s", nome, exc)
            flash(f"Aviso: pasta do Drive não removida ({exc}).", "warning")

    db.execute("DELETE FROM aluno WHERE id=?", (id,))
    db.commit()
    flash(f"Matrícula de {nome} excluída.", "warning")
    return redirect(url_for("listar_alunos"))


@app.route("/excluir_documento/<int:doc_id>", methods=["POST"])
def excluir_documento(doc_id):
    db  = get_db()
    doc = db.execute("SELECT * FROM documento WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        flash("Documento não encontrado.", "danger")
        return redirect(url_for("listar_alunos"))

    if doc["drive_id"] and _drive_ativo():
        try:
            drive.deletar_arquivo(doc["drive_id"])
        except Exception as exc:
            logger.warning("Drive: erro ao deletar arquivo %s: %s", doc["drive_id"], exc)

    db.execute("DELETE FROM documento WHERE id=?", (doc_id,))
    db.commit()
    flash(f"Documento '{doc['nome']}' excluído.", "warning")
    return redirect(request.referrer or url_for("listar_alunos"))


@app.route("/resumo/<int:aluno_id>")
def resumo_matricula(aluno_id):
    aluno = _get_aluno_completo(aluno_id)
    if not aluno:
        return "Aluno não encontrado", 404
    return render_template("resumo_matricula.html", aluno=aluno)


@app.route("/uploads/<path:arquivo>")
def servir_upload(arquivo):
    return send_from_directory(app.config["UPLOAD_FOLDER"], arquivo)


@app.route("/status_drive")
def status_drive():
    return jsonify({"drive_ativo": _drive_ativo()})



@app.errorhandler(413)
def arquivo_muito_grande(e):
    flash(
        "Arquivos muito grandes. O limite é 100 MB por matrícula. "
        "Comprima as imagens antes de enviar.",
        "danger",
    )
    return redirect(request.referrer or url_for("index"))

# ── Inicialização ─────────────────────────────────────────────────────────────
# Carrega o token do Drive (OAuth) ANTES do Flask subir — cobre tanto
# 'python app.py' quanto 'flask run' / gunicorn. NÃO é interativo: se não
# houver token.json válido, só loga o aviso e o app segue sem Drive (os
# uploads caem para o disco local). Rode 'python autenticar_drive.py' uma
# vez para gerar o token.json.
if _DRIVE_IMPORT_OK:
    try:
        drive.autenticar()
        logger.info("Drive: token carregado — integração ativa.")
    except Exception as exc:
        logger.warning(
            "Drive: %s — app segue sem Drive (uploads vão para o disco local). "
            "Rode 'python autenticar_drive.py' para autenticar.", exc
        )

with app.app_context():
    init_db()

if __name__ == "__main__":
    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        # debug=True liga o reloader, que tenta reiniciar o processo
        # executando sys.executable de novo — isso quebra dentro de um
        # .exe do PyInstaller (abre um segundo processo, ou trava).
        import threading
        import webbrowser

        def _abrir_navegador():
            webbrowser.open("http://127.0.0.1:5000")

        threading.Timer(1.5, _abrir_navegador).start()
        app.run(debug=False, use_reloader=False, host="0.0.0.0", port=5000)
    else:
        app.run(debug=True, host="0.0.0.0", port=5000)
