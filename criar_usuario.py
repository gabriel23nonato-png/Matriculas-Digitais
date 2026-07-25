"""
criar_usuario.py
─────────────────
Rode este script MANUALMENTE para criar o primeiro usuário do sistema
(ou redefinir a senha de um usuário existente). Sem isso, a tabela
`usuario` fica vazia e ninguém consegue logar em /login.

Usa o mesmo DATABASE que o app.py (database/database/alunosv3_novo.db,
na pasta deste arquivo, ou ao lado do .exe empacotado) e o mesmo
esquema de hash de senha (werkzeug.security), então o usuário criado
aqui funciona direto no login do Flask.

Uso:
    python criar_usuario.py
"""

import getpass
import os
import sqlite3
import sys

from werkzeug.security import generate_password_hash


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATABASE = os.path.join(app_dir(), "database", "database", "alunosv3_novo.db")


def main():
    print("=" * 60)
    print("Criar / redefinir usuário — Sistema de Matrículas")
    print("=" * 60)

    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    if not os.path.exists(DATABASE):
        print(f"\nAviso: banco ainda não existe em {DATABASE} — será criado agora.")

    username = input("\nUsuário (login): ").strip()
    if not username:
        print("Usuário não pode ser vazio.")
        sys.exit(1)

    nome = input("Nome de exibição (opcional, Enter para usar o usuário): ").strip()
    nome = nome or username

    senha = getpass.getpass("Senha: ")
    if len(senha) < 5:
        print("A senha deve ter pelo menos 5 caracteres.")
        sys.exit(1)
    confirmacao = getpass.getpass("Confirme a senha: ")
    if senha != confirmacao:
        print("As senhas não coincidem.")
        sys.exit(1)

    senha_hash = generate_password_hash(senha)

    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        # Cria a tabela caso este script rode antes do app.py (que é quem
        # normalmente cria o schema via init_db() ao subir o Flask).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuario (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT UNIQUE NOT NULL,
                senha_hash  TEXT NOT NULL,
                nome        TEXT,
                criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP,
                ativo       INTEGER DEFAULT 1
            )
        """)
        conn.commit()

        existente = conn.execute(
            "SELECT id FROM usuario WHERE username=?", (username,)
        ).fetchone()

        if existente:
            resposta = (
                input(
                    f"\nUsuário '{username}' já existe. Redefinir a senha dele? [s/N]: "
                )
                .strip()
                .lower()
            )
            if resposta != "s":
                print("Cancelado.")
                sys.exit(0)
            conn.execute(
                "UPDATE usuario SET senha_hash=?, nome=?, ativo=1 WHERE username=?",
                (senha_hash, nome, username),
            )
            print(f"\nSenha de '{username}' redefinida com sucesso.")
        else:
            conn.execute(
                "INSERT INTO usuario (username, senha_hash, nome, ativo) VALUES (?,?,?,1)",
                (username, senha_hash, nome),
            )
            print(f"\nUsuário '{username}' criado com sucesso.")
        conn.commit()
    finally:
        conn.close()

    print("Agora é só fazer login em /login com esse usuário e senha.")


if __name__ == "__main__":
    main()
