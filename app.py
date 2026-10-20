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
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
    flash,
    jsonify,
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


load_dotenv(os.path.join(app_dir(), ".env"))

try:
    import drive_service as drive

    _DRIVE_IMPORT_OK = True
except ImportError:
    _DRIVE_IMPORT_OK = False

BASE_DIR = app_dir()
DATABASE = os.path.join(BASE_DIR, "database", "database", "alunosv3_novo.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "webp"}

SALAS_IV = ["IVA", "IVB", "IVC", "IVD", "IVE"]
SALAS_V = ["VA", "VB", "VC", "VD", "VE"]
SALAS = ["Sem Sala"] + SALAS_IV + SALAS_V

UFS = [
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
]

CAMPOS_NUMERICOS = {"contribuicao", "peso", "altura"}
CAMPOS_DATA = {"data_nascimento", "expedicao_rg_mae", "validade_vacina"}

CAMPOS_UPLOAD = [
    "doc_cpf",
    "doc_cartao_sus",
    "doc_certidao",
    "doc_cpf_mae",
    "doc_cpf_pai",
    "doc_cep",
    "doc_laudo",
    "doc_carteira_vacinacao",
    "doc_comprovante_vacinacao",
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

# SECRET_KEY é OBRIGATÓRIA — sem fallback hardcoded. Se o .env não estiver
# configurado, o app recusa subir em vez de rodar silenciosamente com uma
# chave pública e previsível (comprometeria sessão/cookies/CSRF).
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY não definida.\n"
        "Crie/edite o arquivo '.env' (na pasta do app.py, ou ao lado do .exe) "
        "e adicione uma linha como:\n"
        "    SECRET_KEY=" + os.urandom(24).hex() + "\n"
        "(gere seu próprio valor aleatório — o exemplo acima é só ilustrativo, "
        "não copie o mesmo valor entre instalações). Veja '.env.example'."
    )
app.secret_key = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

csrf = CSRFProtect(app)


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            "PRAGMA journal_mode = WAL"
        )  # ← WAL (Write-Ahead Logging): permite leituras enquanto uma escrita está em andamento.
        db.execute(
            "PRAGMA busy_timeout = 30000"
        )  # busy_timeout: em vez de travar com erro imediatamente, o SQLite aguarda até 30 segundos antes de desistir.
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

    CREATE TABLE IF NOT EXISTS usuario (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT UNIQUE NOT NULL,
        senha_hash  TEXT NOT NULL,
        nome        TEXT,
        criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP,
        ativo       INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS log_acao (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario     TEXT,
        acao        TEXT,
        alvo_tipo   TEXT,
        alvo_id     INTEGER,
        detalhe     TEXT,
        criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    for col, tipo in [("data_modificacao", "TEXT")]:
        _add_col(db, "matricula", col, tipo)
    _add_col(db, "saude", "validade_vacina", "DATE")
    _add_col(db, "saude", "peso", "REAL")
    _add_col(db, "saude", "altura", "REAL")
    for col, tipo in [
        ("campo", "TEXT"),
        ("subpasta", "TEXT"),
        ("drive_id", "TEXT"),
        ("drive_url", "TEXT"),
    ]:
        _add_col(db, "documento", col, tipo)
    db.commit()


# ── Autenticação (Fase 1 — Segurança de Base) ─────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "warning"


class Usuario(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.nome = row["nome"] or row["username"]


@login_manager.user_loader
def load_user(user_id):
    row = (
        get_db()
        .execute("SELECT * FROM usuario WHERE id=? AND ativo=1", (user_id,))
        .fetchone()
    )
    return Usuario(row) if row else None


def registrar_log(acao: str, alvo_tipo: str, alvo_id=None, detalhe: str = None):
    """Grava uma linha de auditoria: quem fez o quê e quando."""
    usuario = current_user.username if current_user.is_authenticated else "sistema"
    db = get_db()
    db.execute(
        "INSERT INTO log_acao (usuario, acao, alvo_tipo, alvo_id, detalhe) VALUES (?,?,?,?,?)",
        (usuario, acao, alvo_tipo, alvo_id, detalhe),
    )
    db.commit()


def normalizar(campo: str, valor) -> object:
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

    CAMPOS_PRESERVAR_CASE = {
        "permite_edfisica",
        "permite_fotos",
        "permite_passeios",
        "sexo",
        "integral",
        "gemeo",
        "bolsa_familia",
        "tipo_contribuicao",
        "nivel",
        "sala",
        "estado_civil_mae",
        "raca_cor",
        "uf_rg_mae",
        "uniforme",
        "calcado",
        "tipo_sanguineo",
        "lactose",
        "aplv",
        "diabetico",
    }
    if campo in CAMPOS_PRESERVAR_CASE:
        return v if v else "NÃO INFORMADO"

    return v.upper() if v else "NÃO INFORMADO"


def form_para_dict(form, campos: list) -> dict:
    return {c: normalizar(c, form.get(c, "")) for c in campos}


def agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_aluno_completo(aluno_id):
    return (
        get_db()
        .execute(
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
            s.peso, s.altura,
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
        )
        .fetchone()
    )


def _drive_ativo() -> bool:
    return _DRIVE_IMPORT_OK and drive.drive_disponivel()


def processar_uploads(aluno_id: int, ano: str, sala: str, nome_aluno: str):
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
        nome_seguro = secure_filename(f"{aluno_id}_{campo}_{nome_original}")
        subpasta_nome = (
            drive.CAMPO_PARA_SUBPASTA.get(campo, "OUTROS")
            if _DRIVE_IMPORT_OK
            else "OUTROS"
        )
        drive_id = None
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
                drive_id = res["drive_id"]
                drive_url = res["drive_url"]
                subpasta_nome = res["subpasta"]
                logger.info("Drive: upload OK — %s → %s", nome_original, subpasta_nome)
            except Exception as exc:
                logger.error("Drive: falha em '%s': %s", nome_original, exc)
                flash(
                    f"'{nome_original}' salvo localmente (Drive indisponível: {exc}).",
                    "warning",
                )
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
    db = get_db()
    docs = db.execute(
        "SELECT id, campo, nome, drive_id, drive_url, subpasta FROM documento WHERE aluno_id=?",
        (aluno_id,),
    ).fetchall()

    ausentes = []
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


# ── Módulo Documentação ──────────────────────────────────────────────────────
DOC_LABELS = (
    drive.CAMPO_NOME_DISPLAY if _DRIVE_IMPORT_OK else {c: c for c in CAMPOS_UPLOAD}
)

DIAS_ALERTA_VACINA = 30


def _limpo(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in ("None", "NÃO INFORMADO", "none") else s


def _idade(data_nascimento: str) -> str:
    if not data_nascimento:
        return "—"
    try:
        nasc = datetime.strptime(data_nascimento[:10], "%Y-%m-%d").date()
    except ValueError:
        return "—"
    hoje = datetime.now().date()
    anos = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
    return f"{anos} anos"


def _mapa_documentos_entregues() -> dict:
    linhas = (
        get_db()
        .execute("SELECT aluno_id, campo FROM documento WHERE campo IS NOT NULL")
        .fetchall()
    )
    mapa = {}
    for l in linhas:
        mapa.setdefault(l["aluno_id"], set()).add(l["campo"])
    return mapa


def _stats_dashboard() -> dict:
    db = get_db()
    total_alunos = db.execute("SELECT COUNT(*) FROM aluno").fetchone()[0]

    entregues = _mapa_documentos_entregues()
    ids_alunos = [r["id"] for r in db.execute("SELECT id FROM aluno").fetchall()]
    completos = sum(
        1 for aid in ids_alunos if len(entregues.get(aid, set())) >= len(CAMPOS_UPLOAD)
    )
    total_docs_pendentes = sum(
        len(CAMPOS_UPLOAD) - len(entregues.get(aid, set())) for aid in ids_alunos
    )

    por_documento = {}
    for row in db.execute(
        "SELECT campo, COUNT(DISTINCT aluno_id) AS n FROM documento "
        "WHERE campo IS NOT NULL GROUP BY campo"
    ):
        por_documento[row["campo"]] = row["n"]

    hoje_iso = datetime.now().strftime("%Y-%m-%d")
    limite_iso = (datetime.now() + timedelta(days=DIAS_ALERTA_VACINA)).strftime(
        "%Y-%m-%d"
    )
    vencidas = db.execute(
        "SELECT COUNT(*) FROM saude WHERE validade_vacina IS NOT NULL "
        "AND validade_vacina != '' AND validade_vacina < ?",
        (hoje_iso,),
    ).fetchone()[0]
    proximas = db.execute(
        "SELECT COUNT(*) FROM saude WHERE validade_vacina >= ? AND validade_vacina <= ?",
        (hoje_iso, limite_iso),
    ).fetchone()[0]

    laudos_entregues = por_documento.get("doc_laudo", 0)
    fotos_pendentes = db.execute(
        "SELECT COUNT(*) FROM matricula WHERE permite_fotos IS NULL "
        "OR permite_fotos = '' OR permite_fotos = 'NÃO INFORMADO'"
    ).fetchone()[0]

    return {
        "total_alunos": total_alunos,
        "completos": completos,
        "pendentes_alunos": total_alunos - completos,
        "total_docs_pendentes": total_docs_pendentes,
        "vac_vencidas": vencidas,
        "vac_proximas": proximas,
        "laudos_pendentes": total_alunos - laudos_entregues,
        "fotos_pendentes": fotos_pendentes,
        "por_documento": [
            {
                "campo": c,
                "label": DOC_LABELS.get(c, c),
                "entregues": por_documento.get(c, 0),
                "pendentes": total_alunos - por_documento.get(c, 0),
                "percentual": (
                    round((por_documento.get(c, 0) / total_alunos) * 100)
                    if total_alunos
                    else 0
                ),
            }
            for c in CAMPOS_UPLOAD
        ],
    }


def _filtro_base_alunos(q: str, sala: str, nivel: str, ano: str):
    sql = """
        SELECT a.id, a.nome_completo, a.data_nascimento, a.sexo, a.cpf_aluno,
               a.cartao_sus, m.sala, m.nivel, m.ano,
               r.responsavel_matricula, r.telefone1,
               r.pessoa1, r.pessoa2, r.pessoa3, r.telefone2, r.telefone3, r.telefone4,
               s.validade_vacina, s.peso, s.altura, s.uniforme, s.calcado,
               m.contribuicao, m.tipo_contribuicao
        FROM aluno a
        LEFT JOIN matricula   m ON m.aluno_id = a.id
        LEFT JOIN responsavel r ON r.aluno_id = a.id
        LEFT JOIN saude       s ON s.aluno_id = a.id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND a.nome_completo LIKE ?"
        params.append(f"%{q}%")
    if sala:
        sql += " AND m.sala = ?"
        params.append(sala)
    if nivel:
        sql += " AND m.nivel LIKE ?"
        params.append(f"%{nivel}%")
    if ano:
        sql += " AND m.ano = ?"
        params.append(ano)
    sql += " ORDER BY m.sala, a.nome_completo"
    return get_db().execute(sql, params).fetchall()


def _matriz_documentos(args) -> list:
    q = args.get("doc_q", "").strip()
    sala = args.get("doc_sala", "").strip()
    nivel = args.get("doc_nivel", "").strip()
    ano = args.get("doc_ano", "").strip()
    status = args.get("doc_status", "").strip()
    campo = args.get("doc_campo", "").strip()
    ordem = args.get("doc_ordem", "nome").strip()

    alunos = _filtro_base_alunos(q, sala, nivel, ano)
    entregues = _mapa_documentos_entregues()

    linhas = []
    for a in alunos:
        docs_aluno = entregues.get(a["id"], set())
        completo = len(docs_aluno) >= len(CAMPOS_UPLOAD)
        if status == "completa" and not completo:
            continue
        if status == "pendente" and completo:
            continue
        if campo and campo in docs_aluno:
            continue
        linhas.append(
            {
                "aluno": a,
                "docs": {c: (c in docs_aluno) for c in CAMPOS_UPLOAD},
                "completo": completo,
                "qtd_entregues": len(docs_aluno),
            }
        )

    if ordem == "sala":
        linhas.sort(
            key=lambda l: (l["aluno"]["sala"] or "", l["aluno"]["nome_completo"])
        )
    elif ordem in CAMPOS_UPLOAD:
        linhas.sort(key=lambda l: (l["docs"][ordem], l["aluno"]["nome_completo"]))
    elif ordem == "pendencias":
        linhas.sort(key=lambda l: (l["qtd_entregues"], l["aluno"]["nome_completo"]))
    else:
        linhas.sort(key=lambda l: l["aluno"]["nome_completo"])

    return linhas


def _relatorio_vacinacao(args) -> list:
    q = args.get("vac_q", "").strip()
    sala = args.get("vac_sala", "").strip()
    nivel = args.get("vac_nivel", "").strip()
    situ = args.get("vac_situacao", "").strip()

    hoje_iso = datetime.now().strftime("%Y-%m-%d")
    limite_iso = (datetime.now() + timedelta(days=DIAS_ALERTA_VACINA)).strftime(
        "%Y-%m-%d"
    )

    resultado = []
    for a in _filtro_base_alunos(q, sala, nivel, ""):
        v = a["validade_vacina"]
        if not v:
            situacao = "SEM DATA"
        elif v < hoje_iso:
            situacao = "VENCIDO"
        elif v <= limite_iso:
            situacao = "PRÓXIMO DO VENCIMENTO"
        else:
            situacao = "EM DIA"
        if situ and situ != situacao:
            continue
        resultado.append({"aluno": a, "situacao": situacao})
    return resultado


def _relatorio_autorizacoes(args) -> list:
    q, sala, nivel = (
        args.get(k, "").strip() for k in ("aut_q", "aut_sala", "aut_nivel")
    )
    return _filtro_base_alunos(q, sala, nivel, "")


def _relatorio_uniformes(args) -> list:
    q, sala, nivel = (
        args.get(k, "").strip() for k in ("uni_q", "uni_sala", "uni_nivel")
    )
    return _filtro_base_alunos(q, sala, nivel, "")


def _relatorio_financeiro(args) -> dict:
    q, sala, nivel = (
        args.get(k, "").strip() for k in ("fin_q", "fin_sala", "fin_nivel")
    )
    alunos = _filtro_base_alunos(q, sala, nivel, "")

    por_sala, por_nivel, total_geral = {}, {}, 0.0
    for a in alunos:
        v = a["contribuicao"] or 0
        total_geral += v
        s = a["sala"] or "Sem Sala"
        n = a["nivel"] or "NÃO INFORMADO"
        por_sala[s] = por_sala.get(s, 0) + v
        por_nivel[n] = por_nivel.get(n, 0) + v

    return {
        "alunos": alunos,
        "por_sala": por_sala,
        "por_nivel": por_nivel,
        "total_geral": total_geral,
    }


def _relatorio_pendencias(args) -> list:
    q, sala, nivel = (
        args.get(k, "").strip() for k in ("pend_q", "pend_sala", "pend_nivel")
    )
    entregues = _mapa_documentos_entregues()
    resultado = []
    for a in _filtro_base_alunos(q, sala, nivel, ""):
        docs_aluno = entregues.get(a["id"], set())
        pendentes = [DOC_LABELS.get(c, c) for c in CAMPOS_UPLOAD if c not in docs_aluno]
        if pendentes:
            resultado.append({"aluno": a, "pendentes": pendentes})
    return resultado


def _relatorio_sus(args) -> list:
    q, sala, nivel = (
        args.get(k, "").strip() for k in ("sus_q", "sus_sala", "sus_nivel")
    )
    return _filtro_base_alunos(q, sala, nivel, "")


def _export_csv(rows, colunas, nome: str):
    import csv, io

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([label for _, label in colunas])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _ in colunas])
    dados = ("\ufeff" + buf.getvalue()).encode("utf-8")
    resp = app.response_class(dados, mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f'attachment; filename="{nome}.csv"'
    return resp


def _export_xlsx(rows, colunas, nome: str):
    import io

    try:
        from openpyxl import Workbook
    except ImportError:
        flash(
            "Exportação em Excel indisponível: instale 'openpyxl' (pip install openpyxl).",
            "danger",
        )
        return redirect(request.referrer or url_for("documentacao"))

    wb = Workbook()
    ws = wb.active
    ws.append([label for _, label in colunas])
    for row in rows:
        ws.append([row.get(key, "") for key, _ in colunas])
    for col in ws.columns:
        largura = max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2
        ws.column_dimensions[col[0].column_letter].width = min(largura, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = app.response_class(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp.headers["Content-Disposition"] = f'attachment; filename="{nome}.xlsx"'
    return resp


def _linhas_export_documentos(args):
    linhas = _matriz_documentos(args)
    colunas = [("nome", "Aluno"), ("sala", "Sala"), ("nivel", "Nível")]
    colunas += [(c, DOC_LABELS.get(c, c)) for c in CAMPOS_UPLOAD]
    dados = []
    for l in linhas:
        d = {
            "nome": l["aluno"]["nome_completo"],
            "sala": l["aluno"]["sala"] or "",
            "nivel": l["aluno"]["nivel"] or "",
        }
        d.update({c: ("Entregue" if v else "Pendente") for c, v in l["docs"].items()})
        dados.append(d)
    return dados, colunas


def _linhas_export_vacinacao(args):
    linhas = _relatorio_vacinacao(args)
    colunas = [
        ("nome", "Aluno"),
        ("sala", "Sala"),
        ("nivel", "Nível"),
        ("validade", "Validade da Vacina"),
        ("situacao", "Situação"),
    ]
    return [
        {
            "nome": l["aluno"]["nome_completo"],
            "sala": l["aluno"]["sala"] or "",
            "nivel": l["aluno"]["nivel"] or "",
            "validade": l["aluno"]["validade_vacina"] or "",
            "situacao": l["situacao"],
        }
        for l in linhas
    ], colunas


def _linhas_export_autorizacoes(args):
    alunos = _relatorio_autorizacoes(args)
    colunas = [
        ("nome", "Aluno"),
        ("sala", "Sala"),
        ("pessoa1", "Autorizado 1"),
        ("pessoa2", "Autorizado 2"),
        ("pessoa3", "Autorizado 3"),
        ("telefone1", "Telefone 1"),
        ("telefone2", "Telefone 2"),
    ]
    return [
        {
            "nome": a["nome_completo"],
            "sala": a["sala"] or "",
            "pessoa1": _limpo(a["pessoa1"]),
            "pessoa2": _limpo(a["pessoa2"]),
            "pessoa3": _limpo(a["pessoa3"]),
            "telefone1": _limpo(a["telefone1"]),
            "telefone2": _limpo(a["telefone2"]),
        }
        for a in alunos
    ], colunas


def _linhas_export_uniformes(args):
    alunos = _relatorio_uniformes(args)
    colunas = [
        ("nome", "Aluno"),
        ("sala", "Sala"),
        ("idade", "Idade"),
        ("peso", "Peso (kg)"),
        ("altura", "Altura (cm)"),
        ("uniforme", "Uniforme"),
        ("calcado", "Calçado"),
        ("sexo", "Sexo"),
        ("sus", "Cartão SUS"),
    ]
    return [
        {
            "nome": a["nome_completo"],
            "sala": a["sala"] or "",
            "idade": _idade(a["data_nascimento"]),
            "peso": a["peso"] or "",
            "altura": a["altura"] or "",
            "uniforme": _limpo(a["uniforme"]),
            "calcado": _limpo(a["calcado"]),
            "sexo": a["sexo"] or "",
            "sus": a["cartao_sus"] or "",
        }
        for a in alunos
    ], colunas


def _linhas_export_financeiro(args):
    dados = _relatorio_financeiro(args)
    colunas = [
        ("nome", "Aluno"),
        ("sala", "Sala"),
        ("nivel", "Nível"),
        ("valor", "Valor"),
        ("tipo", "Tipo de Contribuição"),
    ]
    return [
        {
            "nome": a["nome_completo"],
            "sala": a["sala"] or "",
            "nivel": a["nivel"] or "",
            "valor": a["contribuicao"] or 0,
            "tipo": _limpo(a["tipo_contribuicao"]),
        }
        for a in dados["alunos"]
    ], colunas


def _linhas_export_pendencias(args):
    linhas = _relatorio_pendencias(args)
    colunas = [
        ("nome", "Aluno"),
        ("sala", "Sala"),
        ("nivel", "Nível"),
        ("responsavel", "Responsável"),
        ("telefone", "Telefone"),
        ("pendentes", "Documentos Pendentes"),
    ]
    return [
        {
            "nome": l["aluno"]["nome_completo"],
            "sala": l["aluno"]["sala"] or "",
            "nivel": l["aluno"]["nivel"] or "",
            "responsavel": _limpo(l["aluno"]["responsavel_matricula"]),
            "telefone": _limpo(l["aluno"]["telefone1"]),
            "pendentes": ", ".join(l["pendentes"]),
        }
        for l in linhas
    ], colunas


def _linhas_export_sus(args):
    alunos = _relatorio_sus(args)
    colunas = [
        ("nome", "Aluno"),
        ("sala", "Sala"),
        ("nascimento", "Data de Nascimento"),
        ("cpf", "CPF"),
        ("sus", "Cartão SUS"),
    ]
    return [
        {
            "nome": a["nome_completo"],
            "sala": a["sala"] or "",
            "nascimento": a["data_nascimento"] or "",
            "cpf": a["cpf_aluno"] or "",
            "sus": a["cartao_sus"] or "",
        }
        for a in alunos
    ], colunas


_DATASETS_EXPORT = {
    "documentos": _linhas_export_documentos,
    "vacinacao": _linhas_export_vacinacao,
    "autorizacoes": _linhas_export_autorizacoes,
    "uniformes": _linhas_export_uniformes,
    "financeiro": _linhas_export_financeiro,
    "pendencias": _linhas_export_pendencias,
    "sus": _linhas_export_sus,
}


# ── Rotas ─────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")
        row = (
            get_db()
            .execute("SELECT * FROM usuario WHERE username=? AND ativo=1", (username,))
            .fetchone()
        )

        if row and check_password_hash(row["senha_hash"], senha):
            login_user(Usuario(row))
            registrar_log("login", "usuario", row["id"], detalhe=username)
            proximo = request.args.get("next")
            return redirect(proximo or url_for("index"))

        flash("Usuário ou senha inválidos.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    registrar_log("logout", "usuario", current_user.id, detalhe=current_user.username)
    logout_user()
    flash("Sessão encerrada.", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/alunos")
@login_required
def listar_alunos():
    db = get_db()
    q = request.args.get("q", "").strip()
    nivel = request.args.get("nivel", "").strip()
    sala = request.args.get("sala", "").strip()
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
        sql += (
            " AND (a.nome_completo LIKE ? OR r.nome_mae LIKE ? OR a.cpf_aluno LIKE ?)"
        )
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if nivel:
        sql += " AND m.nivel LIKE ?"
        params.append(f"%{nivel}%")
    if sala:
        sql += " AND m.sala = ?"
        params.append(sala)
    sql += (
        " ORDER BY m.data_modificacao DESC"
        if ordem == "data_modificacao"
        else " ORDER BY a.nome_completo"
    )

    alunos = db.execute(sql, params).fetchall()
    return render_template(
        "alunos.html",
        alunos=alunos,
        q=q,
        nivel=nivel,
        sala=sala,
        salas=SALAS,
        salas_iv=SALAS_IV,
        salas_v=SALAS_V,
        ordem=ordem,
    )


@app.route("/nova_matricula", methods=["GET", "POST"])
@login_required
def nova_matricula():
    if request.method == "POST":
        f = request.form
        db = get_db()

        a = form_para_dict(
            f,
            [
                "ra",
                "rm",
                "nome_completo",
                "data_nascimento",
                "sexo",
                "raca_cor",
                "nacionalidade",
                "municipio_nascimento",
                "rg_aluno",
                "cpf_aluno",
                "cartao_sus",
                "certidao_nascimento",
                "rne",
                "gemeo",
            ],
        )
        db.execute(
            """INSERT INTO aluno (ra,rm,nome_completo,data_nascimento,sexo,raca_cor,
               nacionalidade,municipio_nascimento,rg_aluno,cpf_aluno,
               cartao_sus,certidao_nascimento,rne,gemeo)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            list(a.values()),
        )
        aluno_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        r = form_para_dict(
            f,
            [
                "nome_mae",
                "cpf_mae",
                "rg_mae",
                "uf_rg_mae",
                "expedicao_rg_mae",
                "estado_civil_mae",
                "profissao_mae",
                "nome_pai",
                "cpf_pai",
                "rg_pai",
                "profissao_pai",
                "responsavel_matricula",
                "telefone1",
                "telefone2",
                "telefone3",
                "telefone4",
                "bolsa_familia",
                "nis",
                "pessoa1",
                "pessoa2",
                "pessoa3",
            ],
        )
        db.execute(
            """INSERT INTO responsavel (aluno_id,nome_mae,cpf_mae,rg_mae,uf_rg_mae,
               expedicao_rg_mae,estado_civil_mae,profissao_mae,nome_pai,cpf_pai,rg_pai,
               profissao_pai,responsavel_matricula,telefone1,telefone2,telefone3,telefone4,
               bolsa_familia,nis,pessoa1,pessoa2,pessoa3)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [aluno_id] + list(r.values()),
        )

        e = form_para_dict(
            f, ["logradouro", "numero", "bairro", "cidade_end", "estado", "cep"]
        )
        db.execute(
            """INSERT INTO endereco (aluno_id,logradouro,numero,bairro,cidade,estado,cep)
               VALUES (?,?,?,?,?,?,?)""",
            [
                aluno_id,
                e["logradouro"],
                e["numero"],
                e["bairro"],
                e["cidade_end"],
                e["estado"],
                e["cep"],
            ],
        )

        s = form_para_dict(
            f,
            [
                "tipo_sanguineo",
                "alergico",
                "diabetico",
                "lactose",
                "aplv",
                "plano",
                "uniforme",
                "calcado",
                "observacoes",
                "validade_vacina",
                "peso",
                "altura",
            ],
        )
        db.execute(
            """INSERT INTO saude (aluno_id,tipo_sanguineo,alergico,diabetico,lactose,aplv,
               plano,uniforme,calcado,observacoes,validade_vacina,peso,altura)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [aluno_id] + list(s.values()),
        )

        m = form_para_dict(
            f,
            [
                "nivel",
                "sala",
                "integral",
                "escola_anterior",
                "permite_edfisica",
                "permite_fotos",
                "permite_passeios",
                "contribuicao",
                "tipo_contribuicao",
            ],
        )
        ano_val = normalizar("ano_texto", f.get("ano_matricula", ""))
        db.execute(
            """INSERT INTO matricula (aluno_id,nivel,sala,integral,ano,escola_anterior,
               permite_edfisica,permite_fotos,permite_passeios,contribuicao,
               tipo_contribuicao,data_modificacao)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                aluno_id,
                m["nivel"],
                m["sala"],
                m["integral"],
                ano_val,
                m["escola_anterior"],
                m["permite_edfisica"],
                m["permite_fotos"],
                m["permite_passeios"],
                m["contribuicao"],
                m["tipo_contribuicao"],
                agora(),
            ],
        )
        db.commit()

        processar_uploads(
            aluno_id=aluno_id,
            ano=str(ano_val or "SEM_ANO"),
            sala=str(m["sala"]),
            nome_aluno=str(a["nome_completo"]),
        )

        registrar_log("criar", "matricula", aluno_id, detalhe=a["nome_completo"])

        flash(f"Matrícula de {a['nome_completo']} salva com sucesso!", "success")
        return redirect(url_for("listar_alunos"))

    return render_template(
        "nova_matricula.html",
        modo="novo",
        edicao_habilitada=True,
        aluno=None,
        documentos=[],
        divergencias=None,
        salas=SALAS,
        salas_iv=SALAS_IV,
        salas_v=SALAS_V,
        ufs=UFS,
        ano_atual=datetime.now().year,
        drive_ativo=_drive_ativo(),
    )


@app.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_matricula(id):
    edicao_habilitada = request.args.get("editar") == "1" or request.method == "POST"
    aluno = _get_aluno_completo(id)

    if not aluno:
        flash("Aluno não encontrado.", "danger")
        return redirect(url_for("listar_alunos"))

    if request.method == "POST":
        f = request.form
        db = get_db()

        a = form_para_dict(
            f,
            [
                "ra",
                "rm",
                "nome_completo",
                "data_nascimento",
                "sexo",
                "raca_cor",
                "nacionalidade",
                "municipio_nascimento",
                "rg_aluno",
                "cpf_aluno",
                "cartao_sus",
                "certidao_nascimento",
                "rne",
                "gemeo",
            ],
        )
        db.execute(
            """UPDATE aluno SET ra=?,rm=?,nome_completo=?,data_nascimento=?,sexo=?,
               raca_cor=?,nacionalidade=?,municipio_nascimento=?,rg_aluno=?,cpf_aluno=?,
               cartao_sus=?,certidao_nascimento=?,rne=?,gemeo=? WHERE id=?""",
            list(a.values()) + [id],
        )

        r = form_para_dict(
            f,
            [
                "nome_mae",
                "cpf_mae",
                "rg_mae",
                "uf_rg_mae",
                "expedicao_rg_mae",
                "estado_civil_mae",
                "profissao_mae",
                "nome_pai",
                "cpf_pai",
                "rg_pai",
                "profissao_pai",
                "responsavel_matricula",
                "telefone1",
                "telefone2",
                "telefone3",
                "telefone4",
                "bolsa_familia",
                "nis",
                "pessoa1",
                "pessoa2",
                "pessoa3",
            ],
        )
        db.execute(
            """UPDATE responsavel SET nome_mae=?,cpf_mae=?,rg_mae=?,uf_rg_mae=?,
               expedicao_rg_mae=?,estado_civil_mae=?,profissao_mae=?,nome_pai=?,cpf_pai=?,
               rg_pai=?,profissao_pai=?,responsavel_matricula=?,telefone1=?,telefone2=?,
               telefone3=?,telefone4=?,bolsa_familia=?,nis=?,pessoa1=?,pessoa2=?,pessoa3=?
               WHERE aluno_id=?""",
            list(r.values()) + [id],
        )

        e = form_para_dict(
            f, ["logradouro", "numero", "bairro", "cidade_end", "estado", "cep"]
        )
        db.execute(
            """UPDATE endereco SET logradouro=?,numero=?,bairro=?,cidade=?,estado=?,cep=?
               WHERE aluno_id=?""",
            [
                e["logradouro"],
                e["numero"],
                e["bairro"],
                e["cidade_end"],
                e["estado"],
                e["cep"],
                id,
            ],
        )

        s = form_para_dict(
            f,
            [
                "tipo_sanguineo",
                "alergico",
                "diabetico",
                "lactose",
                "aplv",
                "plano",
                "uniforme",
                "calcado",
                "observacoes",
                "validade_vacina",
                "peso",
                "altura",
            ],
        )
        db.execute(
            """UPDATE saude SET tipo_sanguineo=?,alergico=?,diabetico=?,lactose=?,aplv=?,
               plano=?,uniforme=?,calcado=?,observacoes=?,validade_vacina=?,peso=?,altura=?
               WHERE aluno_id=?""",
            list(s.values()) + [id],
        )

        m = form_para_dict(
            f,
            [
                "nivel",
                "sala",
                "integral",
                "escola_anterior",
                "permite_edfisica",
                "permite_fotos",
                "permite_passeios",
                "contribuicao",
                "tipo_contribuicao",
            ],
        )
        ano_val = normalizar("ano_texto", f.get("ano_matricula", ""))
        db.execute(
            """UPDATE matricula SET nivel=?,sala=?,integral=?,ano=?,escola_anterior=?,
               permite_edfisica=?,permite_fotos=?,permite_passeios=?,contribuicao=?,
               tipo_contribuicao=?,data_modificacao=? WHERE aluno_id=?""",
            [
                m["nivel"],
                m["sala"],
                m["integral"],
                ano_val,
                m["escola_anterior"],
                m["permite_edfisica"],
                m["permite_fotos"],
                m["permite_passeios"],
                m["contribuicao"],
                m["tipo_contribuicao"],
                agora(),
                id,
            ],
        )
        db.commit()

        processar_uploads(
            aluno_id=id,
            ano=str(ano_val or aluno["ano"] or "SEM_ANO"),
            sala=str(m["sala"] or aluno["sala"]),
            nome_aluno=str(a["nome_completo"]),
        )

        registrar_log("editar", "matricula", id, detalhe=a["nome_completo"])

        flash(f"Matrícula de {a['nome_completo']} atualizada com sucesso!", "success")
        return redirect(url_for("listar_alunos"))

    docs = (
        get_db()
        .execute(
            "SELECT * FROM documento WHERE aluno_id=? ORDER BY enviado_em DESC", (id,)
        )
        .fetchall()
    )
    divergencias = verificar_divergencias(id) if edicao_habilitada else None

    return render_template(
        "nova_matricula.html",
        modo="editar",
        edicao_habilitada=edicao_habilitada,
        aluno=aluno,
        documentos=docs,
        divergencias=divergencias,
        salas=SALAS,
        salas_iv=SALAS_IV,
        salas_v=SALAS_V,
        ufs=UFS,
        ano_atual=datetime.now().year,
        drive_ativo=_drive_ativo(),
    )


@app.route("/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_matricula(id):
    db = get_db()
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
    ano = row["ano"] or "SEM_ANO"
    sala = row["sala"] or "SEM_SALA"

    if _drive_ativo():
        try:
            drive.deletar_pasta_aluno(ano=ano, sala=sala, nome_aluno=nome)
        except Exception as exc:
            logger.error("Drive: erro ao deletar pasta de '%s': %s", nome, exc)
            flash(f"Aviso: pasta do Drive não removida ({exc}).", "warning")

    db.execute("DELETE FROM aluno WHERE id=?", (id,))
    db.commit()

    registrar_log("excluir", "matricula", id, detalhe=nome)

    flash(f"Matrícula de {nome} excluída.", "warning")
    return redirect(url_for("listar_alunos"))


@app.route("/excluir_documento/<int:doc_id>", methods=["POST"])
@login_required
def excluir_documento(doc_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documento WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        flash("Documento não encontrado.", "danger")
        return redirect(url_for("listar_alunos"))

    if doc["drive_id"] and _drive_ativo():
        try:
            drive.deletar_arquivo(doc["drive_id"])
        except Exception as exc:
            logger.warning(
                "Drive: erro ao deletar arquivo %s: %s", doc["drive_id"], exc
            )

    db.execute("DELETE FROM documento WHERE id=?", (doc_id,))
    db.commit()

    registrar_log("excluir", "documento", doc_id, detalhe=doc["nome"])

    flash(f"Documento '{doc['nome']}' excluído.", "warning")
    return redirect(request.referrer or url_for("listar_alunos"))


@app.route("/resumo/<int:aluno_id>")
@login_required
def resumo_matricula(aluno_id):
    aluno = _get_aluno_completo(aluno_id)
    if not aluno:
        return "Aluno não encontrado", 404
    return render_template("resumo_matricula.html", aluno=aluno)


@app.route("/uploads/<path:arquivo>")
@login_required
def servir_upload(arquivo):
    return send_from_directory(app.config["UPLOAD_FOLDER"], arquivo)


@app.route("/status_drive")
@login_required
def status_drive():
    return jsonify({"drive_ativo": _drive_ativo()})


@app.route("/documentacao")
@login_required
def documentacao():
    aba = request.args.get("tab", "dashboard")

    contexto = dict(
        aba=aba,
        salas=SALAS,
        salas_iv=SALAS_IV,
        salas_v=SALAS_V,
        campos_upload=CAMPOS_UPLOAD,
        doc_labels=DOC_LABELS,
        args=request.args,
    )

    if aba == "dashboard":
        contexto["stats"] = _stats_dashboard()
    elif aba == "documentos":
        contexto["linhas"] = _matriz_documentos(request.args)
    elif aba == "vacinacao":
        contexto["linhas"] = _relatorio_vacinacao(request.args)
    elif aba == "autorizacoes":
        contexto["alunos"] = _relatorio_autorizacoes(request.args)
    elif aba == "uniformes":
        contexto["alunos"] = _relatorio_uniformes(request.args)
        contexto["idade_fn"] = _idade
    elif aba == "financeiro":
        contexto["dados"] = _relatorio_financeiro(request.args)
    elif aba == "relatorios":
        contexto["pendencias"] = _relatorio_pendencias(request.args)
        contexto["sus"] = _relatorio_sus(request.args)

    return render_template("documentacao.html", **contexto)


@app.route("/documentacao/exportar/<dataset>/<formato>")
@login_required
def exportar_documentacao(dataset, formato):
    gerador = _DATASETS_EXPORT.get(dataset)
    if not gerador:
        return "Conjunto de dados inválido.", 400
    if formato not in ("csv", "xlsx"):
        return "Formato inválido.", 400

    rows, colunas = gerador(request.args)
    nome = f"{dataset}_{datetime.now().strftime('%Y%m%d_%H%M')}"

    if formato == "csv":
        return _export_csv(rows, colunas, nome)
    return _export_xlsx(rows, colunas, nome)


@app.errorhandler(413)
def arquivo_muito_grande(e):
    flash(
        "Arquivos muito grandes. O limite é 100 MB por matrícula. "
        "Comprima as imagens antes de enviar.",
        "danger",
    )
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(CSRFError)
def erro_csrf(e):
    # POST sem token CSRF válido — rejeitado com 400 SEMPRE, mesmo quando
    # há referrer para onde redirecionar de volta (antes só o fallback
    # sem referrer retornava 400; o caminho com referrer respondia 302).
    logger.warning("CSRF rejeitado em %s: %s", request.path, e.description)
    flash("Sessão expirada ou formulário inválido. Tente novamente.", "warning")
    destino = request.referrer or url_for("login")
    resposta = redirect(destino)
    resposta.status_code = 400
    return resposta


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
            "Rode 'python autenticar_drive.py' para autenticar.",
            exc,
        )

with app.app_context():
    init_db()

if __name__ == "__main__":
    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        import threading
        import webbrowser

        def _abrir_navegador():
            webbrowser.open("http://127.0.0.1:5000")

        threading.Timer(1.5, _abrir_navegador).start()
        app.run(debug=False, use_reloader=False, host="0.0.0.0", port=5000)
    else:
        app.run(debug=False, host="0.0.0.0", port=5000)
