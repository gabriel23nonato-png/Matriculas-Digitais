"""
drive_service.py
────────────────
Integração com Google Drive via OAuth 2.0 (InstalledAppFlow).

Migrado de Service Account para OAuth porque a pasta raiz
MATRICULAS_ESCOLA vive no Drive PESSOAL da conta Gmail — Service
Account não tem cota/acesso próprio a Drives pessoais sem
compartilhamento explícito pasta a pasta, o que gerava
403 storageQuotaExceeded.

Fluxo:
1. autenticar() é chamada 1x no app.py, ANTES do Flask subir.
2. Primeira execução: abre o navegador, você loga com a conta Gmail
   dona da pasta, aceita os escopos → token.json é salvo na raiz.
3. Execuções seguintes: lê token.json e renova sozinho via
   refresh_token (sem precisar logar de novo).

Mantido da versão anterior (Service Account):
- supportsAllDrives / includeItemsFromAllDrives=True em todas as
  chamadas — inofensivo em Meu Drive pessoal, mas mantém compat.
  caso a pasta raiz um dia vire um Drive Compartilhado.
- resumable=True sempre, para uploads consistentes.
- Validação de conteúdo vazio antes do upload.
- Estrutura de pastas: /ANO/SALA/ALUNOS/NOME/SUBPASTA
"""

import os
import sys
import io
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)


def _app_dir() -> str:
    """
    Pasta onde client_secret.json e token.json devem morar.
    Rodando como .exe, isso é a pasta do .exe (não a pasta temporária
    do PyInstaller) — senão o login OAuth seria perdido a cada abertura
    do programa. Mantém consistência com app_dir() em app.py.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR            = _app_dir()
CLIENT_SECRET_FILE  = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_FILE          = os.path.join(BASE_DIR, "token.json")
SCOPES              = ["https://www.googleapis.com/auth/drive"]

_PLACEHOLDER = "COLE_O_ID_DA_PASTA_RAIZ_AQUI"


def _get_folder_id() -> str | None:
    """Lê o ID da pasta raiz do ambiente em tempo de execução."""
    return os.getenv("DRIVE_ROOT_FOLDER_ID")


CAMPO_PARA_SUBPASTA = {
    "doc_cep":                   "COMP_RESIDÊNCIA",
    "doc_cpf":                   "RG E CERT_NASCIMENTO",
    "doc_certidao":              "RG E CERT_NASCIMENTO",
    "doc_cpf_mae":               "RG DO RESPONSÁVEL",
    "doc_cpf_pai":               "RG DO RESPONSÁVEL",
    "doc_cartao_sus":            "CARTÃO SUS, CARTEIRA, COMP_VACINA E LAUDO",
    "doc_laudo":                 "CARTÃO SUS, CARTEIRA, COMP_VACINA E LAUDO",
    "doc_carteira_vacinacao":    "CARTÃO SUS, CARTEIRA, COMP_VACINA E LAUDO",
    "doc_comprovante_vacinacao": "CARTÃO SUS, CARTEIRA, COMP_VACINA E LAUDO",
}

CAMPO_NOME_DISPLAY = {
    "doc_cep":                   "Comprovante de residência",
    "doc_cpf":                   "RG do aluno",
    "doc_certidao":              "Certidão de nascimento",
    "doc_cpf_mae":               "RG da mãe",
    "doc_cpf_pai":               "RG do pai",
    "doc_cartao_sus":            "Cartão SUS",
    "doc_laudo":                 "Laudo médico",
    "doc_carteira_vacinacao":    "Carteira de vacinação",
    "doc_comprovante_vacinacao": "Comprovante de vacinação",
}

_drive_service   = None  # cache do client já autenticado
_auth_tentada    = False  # evita reabrir o navegador a cada request após falha
_auth_erro       = None   # guarda a última mensagem de erro para diagnóstico


# ── Autenticação ──────────────────────────────────────────────────────────────
def carregar_credenciais(interativo: bool = False):
    """
    Carrega/valida as credenciais do Drive.

    interativo=False (padrão — usado pelo app.py no boot e por qualquer
    chamada durante requests do Flask): NUNCA abre o navegador. Se não
    houver um token.json válido, levanta RuntimeError na hora — quem
    chamou decide o que fazer (o app.py loga o erro e segue sem Drive).
    Isso existe porque, antes, uma falha de autenticação fazia o Flask
    tentar autenticar de novo (abrindo uma aba nova) a cada clique do
    usuário, já que cada rota chama drive_disponivel() por baixo.

    interativo=True: pode abrir o navegador para o consentimento OAuth.
    Só deve ser chamado pelo autenticar_drive.py, rodado manualmente
    pelo usuário UMA vez fora do Flask.
    """
    global _drive_service

    if not os.path.exists(CLIENT_SECRET_FILE):
        raise FileNotFoundError(
            f"Credencial OAuth não encontrada: {CLIENT_SECRET_FILE}\n"
            "Baixe o client_secret.json no Google Cloud Console "
            "(APIs & Services → Credentials → OAuth client ID → Desktop app)."
        )

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as exc:
            logger.warning("Drive: token.json existe mas está corrompido/ilegível: %s", exc)
            creds = None

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        logger.info("Drive: token renovado via refresh_token.")

    if not creds or not creds.valid:
        if not interativo:
            raise RuntimeError(
                "Nenhum token.json válido encontrado. Rode 'python "
                "autenticar_drive.py' (ou o .exe equivalente) UMA vez, "
                "fora do servidor Flask, para fazer o login do Drive."
            )
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        logger.info("Drive: login OAuth concluído pelo navegador. token.json salvo em %s", TOKEN_FILE)

    _drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
    logger.info("Google Drive: autenticado via OAuth 2.0.")
    return _drive_service


def autenticar():
    """
    Mantido por compatibilidade com o app.py (chamado 1x no boot).
    NÃO é interativo — só carrega um token.json já existente.
    """
    return carregar_credenciais(interativo=False)


def autenticar_interativo():
    """Usado somente por autenticar_drive.py (setup manual, fora do Flask)."""
    return carregar_credenciais(interativo=True)


def get_drive_service():
    """
    Retorna o client já autenticado.
    Se ainda não autenticou nesta execução do processo, tenta 1x — se
    falhar, marca a falha e para de tentar (não reabre navegador a cada
    chamada seguinte). Reinicie o processo (ou rode autenticar_drive.py
    e reinicie) para tentar de novo.
    """
    global _drive_service, _auth_tentada, _auth_erro

    if _drive_service is not None:
        return _drive_service

    if _auth_tentada:
        raise RuntimeError(_auth_erro or "Drive não autenticado nesta sessão.")

    _auth_tentada = True
    try:
        return carregar_credenciais(interativo=False)
    except Exception as exc:
        _auth_erro = str(exc)
        raise


def drive_disponivel() -> bool:
    if not os.path.exists(CLIENT_SECRET_FILE):
        return False
    folder_id = _get_folder_id()
    if not folder_id or folder_id == _PLACEHOLDER:
        logger.warning("Drive: DRIVE_ROOT_FOLDER_ID não configurado no .env")
        return False
    try:
        get_drive_service()
        return True
    except Exception as exc:
        logger.warning("Drive indisponível: %s", exc)
        return False


# ── Pastas ────────────────────────────────────────────────────────────────────
def _buscar_ou_criar_pasta(service, nome: str, parent_id: str) -> str:
    """Busca pasta pelo nome dentro de parent_id. Cria se não existir."""
    nome_seguro = nome.replace("'", "\\'")
    query = (
        f"name='{nome_seguro}' and '{parent_id}' in parents "
        f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    res = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    arquivos = res.get("files", [])
    if arquivos:
        return arquivos[0]["id"]

    pasta = service.files().create(
        body={
            "name": nome,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        },
        fields="id",
        supportsAllDrives=True,
    ).execute()
    logger.info("Drive: pasta criada '%s' (id=%s)", nome, pasta["id"])
    return pasta["id"]


def obter_pasta_aluno(ano: str, sala: str, nome_aluno: str) -> str:
    service   = get_drive_service()
    folder_id = _get_folder_id()

    ano_str    = str(ano).strip()   or "SEM_ANO"
    sala_str   = str(sala).strip()  or "SEM_SALA"
    nome_upper = nome_aluno.strip().upper()

    pasta_ano    = _buscar_ou_criar_pasta(service, ano_str,    folder_id)
    pasta_sala   = _buscar_ou_criar_pasta(service, sala_str,   pasta_ano)
    pasta_alunos = _buscar_ou_criar_pasta(service, "ALUNOS",   pasta_sala)
    pasta_aluno  = _buscar_ou_criar_pasta(service, nome_upper, pasta_alunos)
    return pasta_aluno


def obter_subpasta(pasta_aluno_id: str, nome_subpasta: str) -> str:
    service = get_drive_service()
    return _buscar_ou_criar_pasta(service, nome_subpasta, pasta_aluno_id)


# ── Upload / Delete ──────────────────────────────────────────────────────────
def upload_documento(
    file_stream,
    filename: str,
    campo: str,
    ano: str,
    sala: str,
    nome_aluno: str,
) -> dict:
    service = get_drive_service()

    subpasta_nome  = CAMPO_PARA_SUBPASTA.get(campo, "OUTROS")
    pasta_aluno_id = obter_pasta_aluno(ano, sala, nome_aluno)
    subpasta_id    = obter_subpasta(pasta_aluno_id, subpasta_nome)

    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        "pdf":  "application/pdf",
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "png":  "image/png",
        "webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    conteudo = file_stream.read()
    if not conteudo:
        raise ValueError(f"Arquivo '{filename}' está vazio.")

    media = MediaIoBaseUpload(
        io.BytesIO(conteudo),
        mimetype=mime_type,
        resumable=True,
    )

    arquivo = service.files().create(
        body={"name": filename, "parents": [subpasta_id]},
        media_body=media,
        fields="id, webViewLink, name",
        supportsAllDrives=True,
    ).execute()

    logger.info(
        "Drive: '%s' → /%s/%s/ALUNOS/%s/%s (id=%s)",
        filename, ano, sala, nome_aluno.upper(), subpasta_nome, arquivo["id"],
    )
    return {
        "drive_id":  arquivo["id"],
        "drive_url": arquivo.get("webViewLink", ""),
        "subpasta":  subpasta_nome,
        "nome":      filename,
    }


def deletar_arquivo(drive_id: str) -> bool:
    try:
        get_drive_service().files().delete(
            fileId=drive_id, supportsAllDrives=True
        ).execute()
        logger.info("Drive: arquivo id=%s deletado.", drive_id)
        return True
    except HttpError as exc:
        if exc.resp.status == 404:
            logger.warning("Drive: arquivo id=%s não encontrado.", drive_id)
            return False
        raise


def deletar_pasta_aluno(ano: str, sala: str, nome_aluno: str) -> bool:
    try:
        service    = get_drive_service()
        folder_id  = _get_folder_id()
        nome_upper = nome_aluno.strip().upper()
        ano_str    = str(ano).strip()  or "SEM_ANO"
        sala_str   = str(sala).strip() or "SEM_SALA"

        def buscar(nome, parent):
            ns = nome.replace("'", "\\'")
            res = service.files().list(
                q=(f"name='{ns}' and '{parent}' in parents "
                   f"and mimeType='application/vnd.google-apps.folder' and trashed=false"),
                fields="files(id)",
                pageSize=1,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            f = res.get("files", [])
            return f[0]["id"] if f else None

        p_ano    = buscar(ano_str,    folder_id)
        if not p_ano:    return False
        p_sala   = buscar(sala_str,   p_ano)
        if not p_sala:   return False
        p_alunos = buscar("ALUNOS",   p_sala)
        if not p_alunos: return False
        p_aluno  = buscar(nome_upper, p_alunos)
        if not p_aluno:  return False

        service.files().delete(fileId=p_aluno, supportsAllDrives=True).execute()
        logger.info("Drive: pasta de '%s' deletada.", nome_upper)
        return True
    except HttpError as exc:
        logger.error("Drive: erro ao deletar pasta de '%s': %s", nome_aluno, exc)
        return False


def verificar_existencia(drive_ids: list[str]) -> dict[str, bool]:
    service   = get_drive_service()
    resultado = {}
    for i in range(0, len(drive_ids), 100):
        for drive_id in drive_ids[i : i + 100]:
            try:
                service.files().get(
                    fileId=drive_id,
                    fields="id, trashed",
                    supportsAllDrives=True,
                ).execute()
                resultado[drive_id] = True
            except HttpError as exc:
                resultado[drive_id] = False if exc.resp.status in (404, 403) else True
    return resultado
