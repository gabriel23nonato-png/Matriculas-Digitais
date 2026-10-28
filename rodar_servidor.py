#!/usr/bin/env python3
"""
rodar_servidor.py — substitui o "python app.py" do dia a dia.

Diferenças em relação ao Flask dev server:
  - Waitress é um servidor WSGI de produção: não crasha com erros em rotas
  - Aceita múltiplas conexões simultâneas (threads configurável)
  - Não reinicia sozinho em modo debug (mais seguro na rede local)
  - Continua rodando mesmo que uma rota lance uma exceção não tratada

Uso:
  python rodar_servidor.py

Instalar uma vez (se ainda não tiver):
  pip install waitress
"""

from waitress import serve
from app import app  # importa o objeto Flask do seu app.py

HOST = "0.0.0.0"  # aceita conexões de qualquer IP da rede local
PORT = 5000
THREADS = 4  # conexões simultâneas — 4 é mais que suficiente

print(f"✅  Servidor iniciado em http://{HOST}:{PORT}")
print(f"    Threads: {THREADS}")
print(f"    Pressione Ctrl+C para parar.\n")

serve(
    app,
    host=HOST,
    port=PORT,
    threads=THREADS,
    channel_timeout=300,  # fecha conexão ociosa após 300s
    cleanup_interval=10,
)
