# Guia: Google Drive com OAuth 2.0 — Gmail Pessoal

Este guia substitui a configuração anterior com Service Account,
que era incompatível com Gmail pessoal gratuito.

**Por que mudamos:**
Service Account não possui cota de armazenamento no Google Drive pessoal.
OAuth 2.0 autentica como o próprio usuário Gmail, usando a cota normal (15 GB).

---

## O que você vai precisar

- Acesso à conta `sistemamatriculas10@gmail.com`
- O projeto já existente no Google Cloud Console (o mesmo que você usou antes)
- Cerca de 10 minutos

---

## PARTE 1 — Google Cloud Console

### Passo 1 — Configurar a Tela de Consentimento OAuth

1. Acesse **https://console.cloud.google.com**
2. Faça login com `sistemamatriculas10@gmail.com`
3. Selecione o projeto `sistema-matriculas` (o que você já criou)
4. No menu esquerdo: **APIs e serviços → Tela de consentimento OAuth**
5. Tipo de usuário: **Externo** → clique em Criar
6. Preencha:
   - Nome do app: `Sistema de Matrículas`
   - E-mail de suporte: `sistemamatriculas10@gmail.com`
   - E-mail do desenvolvedor: `sistemamatriculas10@gmail.com`
7. Clique em **Salvar e continuar** (nas telas seguintes pode manter o padrão)
8. Na tela **Usuários de teste** → clique em **+ ADD USERS**
   - Adicione: `sistemamatriculas10@gmail.com`
   - Salve
9. Clique em **Salvar e continuar** até o fim

> ⚠️ O app ficará em modo "Teste" — isso é suficiente para uso interno.
> Você não precisa publicar o app.

---

### Passo 2 — Criar credencial OAuth (Desktop App)

1. No menu esquerdo: **APIs e serviços → Credenciais**
2. Clique em **+ CRIAR CREDENCIAIS → ID do cliente OAuth**
3. Tipo de aplicativo: **App para computador** (Desktop app)
4. Nome: `Matriculas Desktop`
5. Clique em **Criar**
6. No popup que aparecer, clique em **FAZER DOWNLOAD DO JSON**
7. O arquivo será baixado com nome tipo `client_secret_xxx.json`
8. **Renomeie para: `client_secret.json`**
9. **Coloque na raiz do projeto** (mesma pasta do `app.py`)

---

### Passo 3 — Verificar que a Google Drive API está ativada

1. **APIs e serviços → Biblioteca**
2. Pesquise: `Google Drive API`
3. Se aparecer o botão **ATIVAR**, clique. Se aparecer **GERENCIAR**, já está ativa.

---

## PARTE 2 — Configuração local do projeto

### .gitignore

Confirme que estas linhas estão no `.gitignore` (nunca versionar):

```
client_secret.json
token.json
service_account.json
.env
```

### .env

O `.env` permanece igual — só o `DRIVE_ROOT_FOLDER_ID`:

```
DRIVE_ROOT_FOLDER_ID=1abc2def3ghi
SECRET_KEY=matriculas_beta_2025
```

O `DRIVE_ROOT_FOLDER_ID` é o ID da pasta `MATRICULAS_ESCOLA` que já existe
no seu Drive — não precisa recriar nada.

---

## PARTE 3 — Primeira execução (login único)

1. Instale a biblioteca OAuth (se ainda não tiver):
   ```bash
   pip install google-auth-oauthlib
   ```

2. Rode o sistema normalmente:
   ```bash
   python app.py
   ```

3. No terminal aparecerá:
   ```
   Drive: iniciando autenticação — o navegador será aberto...
   ```

4. O navegador abrirá automaticamente com a tela de login do Google.
   - Faça login com `sistemamatriculas10@gmail.com`
   - Clique em **Continuar** (pode aparecer aviso "app não verificado" — clique em Avançado → Ir para Sistema de Matrículas)
   - Conceda permissão de acesso ao Google Drive
   - Aparecerá: "Autorização concedida! Pode fechar esta aba."

5. O sistema salvará `token.json` na raiz do projeto automaticamente.

6. A partir daí, o servidor Flask sobe normalmente:
   ```
   Drive: já autenticado via token.json.
   * Running on http://0.0.0.0:5000
   ```

**Nas próximas vezes, o navegador NÃO abrirá mais.** O sistema usa o
`token.json` automaticamente. Mesmo que o token expire, ele é renovado
sem interação do usuário.

---

## PARTE 4 — Transferindo para outro computador

Ao instalar em outro computador (ex: computador da escola):

1. Clone o repositório
2. Instale as dependências: `pip install -r requirements.txt`
3. Copie manualmente (pen drive ou e-mail):
   - `client_secret.json`
   - `token.json`  ← o token pode ser copiado, não precisa fazer login de novo
   - `.env`
   - `alunosv3_novo.db`
4. Rode `python app.py` — já estará autenticado

---

## Troubleshooting

**"client_secret.json não encontrado"**
→ Verifique se o arquivo está na raiz do projeto (mesma pasta do app.py)

**"Access blocked: sistema-matriculas has not completed the Google verification process"**
→ Clique em "Avançado" → "Ir para Sistema de Matrículas (não seguro)"
→ Isso é normal para apps em modo teste

**"Token has been expired or revoked"**
→ Delete o arquivo `token.json` e rode `python app.py` novamente para refazer o login

**"redirect_uri_mismatch"**
→ O tipo de credencial está errado. Confirme que criou como "App para computador" (Desktop app), não como "Aplicativo Web"

**O navegador não abriu automaticamente**
→ Verifique no terminal se apareceu uma URL. Copie e cole no navegador manualmente.
