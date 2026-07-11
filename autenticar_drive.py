"""
autenticar_drive.py
────────────────────
Rode este script MANUALMENTE, uma vez, para autenticar no Google Drive.

Ele abre o navegador para o login/consentimento e salva o token.json ao
lado deste arquivo (ou ao lado do .exe, se você empacotar isto também).

Depois de rodar isso com sucesso, o app.py NUNCA mais abre o navegador
sozinho — ele só lê o token.json salvo aqui e renova via refresh_token
quando expira. Se o token.json for perdido/revogado, rode este script
de novo.

Uso:
    python autenticar_drive.py
"""
import sys

import drive_service as drive


def main():
    print("=" * 60)
    print("Autenticação Google Drive — Sistema de Matrículas")
    print("=" * 60)

    if not drive.os.path.exists(drive.CLIENT_SECRET_FILE):
        print(f"\nERRO: não encontrei {drive.CLIENT_SECRET_FILE}")
        print("Baixe o client_secret.json no Google Cloud Console e coloque")
        print("nessa pasta antes de rodar este script de novo.")
        sys.exit(1)

    print(f"\nUsando credencial: {drive.CLIENT_SECRET_FILE}")
    print("Abrindo o navegador para login/consentimento...\n")

    try:
        drive.autenticar_interativo()
    except Exception as exc:
        print(f"\nFALHA na autenticação: {exc}")
        print("\nChecklist rápido se isso continuar falhando:")
        print(" 1. O client_secret.json foi criado como tipo 'Desktop app'")
        print("    no Google Cloud Console (não 'Web application')?")
        print(" 2. Se o app OAuth está em modo 'Testing' no Cloud Console,")
        print("    a conta Gmail usada está na lista de 'Test users'?")
        print(" 3. A API do Google Drive está ativada no projeto do Cloud")
        print("    Console (APIs & Services → Library → Google Drive API)?")
        sys.exit(1)

    print(f"\ntoken.json salvo em: {drive.TOKEN_FILE}")
    print("Autenticação concluída! Agora rode 'python app.py' normalmente")
    print("(ou copie o token.json para a pasta do .exe empacotado).")


if __name__ == "__main__":
    main()
