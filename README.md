# Sistema de Matrículas Escolares
**E.M. Profª Maria de Lourdes Gonçalves de Oliveira — Guarujá/SP**

Sistema web de gerenciamento de matrículas escolares desenvolvido em Python/Flask com armazenamento de documentos no Google Drive.

---

## Estrutura do Projeto

```
Projeto_Matricula_v2/
│
├── app.py                      # Aplicação Flask principal — rotas, banco, lógica
├── drive_service.py            # Módulo de integração com Google Drive (Service Account)
│
├── .env                        # ⚠️ NÃO versionar — variáveis de ambiente (ver .env.example)
├── .env.example                # Modelo do .env para novos desenvolvedores
├── .gitignore                  # Arquivos ignorados pelo Git
├── requirements.txt            # Dependências Python
│
├── service_account.json        # ⚠️ NÃO versionar — credenciais Google Cloud
│
├── GUIA_GOOGLE_DRIVE.md        # Passo a passo para configurar o Google Drive
│
├── database/
│   └── database/
│       └── alunosv3_novo.db    # Banco SQLite (não versionado)
│
├── uploads/                    # Arquivos salvos localmente como fallback (não versionado)
│
├── templates/
│   ├── base.html               # Layout base com navbar, flash messages, Bootstrap
│   ├── index.html              # Página inicial com os 3 botões de navegação
│   ├── nova_matricula.html     # Formulário de nova matrícula e edição (8 seções)
│   ├── alunos.html             # Listagem de alunos com filtros e ordenação
│   ├── resumo_matricula.html   # Ficha de impressão da matrícula
│   └── _documentos_painel.html # Painel de documentos (include no nova_matricula)
│
└── static/
    └── css/
        └── style.css           # Estilos customizados
```

---

## Banco de Dados — Schema

O banco é normalizado em 5 tabelas com chaves estrangeiras e CASCADE:

```
aluno           → dados pessoais do aluno
responsavel     → dados do pai, mãe e responsável pela matrícula
endereco        → endereço residencial
saude           → informações de saúde e necessidades especiais
matricula       → nível, sala, autorizações, financeiro, datas
documento       → registro de cada arquivo enviado (local ou Drive)
```

---

## Google Drive — Estrutura de Pastas

```
MATRICULAS_ESCOLA/               ← pasta raiz compartilhada com a Service Account
    2025/
        IVA/
            ALUNOS/
                JOAO DA SILVA/
                    FICHA_MATRICULA_JOAO DA SILVA.pdf
                    COMP_RESIDÊNCIA/
                        comprovante.jpg
                    RG E CERT_NASCIMENTO/
                        rg_aluno.jpg
                        certidao.jpg
                    RG DO RESPONSÁVEL/
                        rg_mae.jpg
                        rg_pai.jpg
                    CARTÃO SUS, CARTEIRA, COMP_VACINA E LAUDO/
                        cartao_sus.jpg
                        laudo.pdf
                        carteira_vacinacao.jpg
                        comprovante_vacina.jpg
```

---

## Instalação e Execução

### 1. Clonar o repositório
```bash
git clone https://github.com/gabriel23nonato-png/Projeto_Matricula_v2.git
cd Projeto_Matricula_v2
git checkout ClaudeRefatora1
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente
```bash
cp .env.example .env
# Editar .env com o DRIVE_ROOT_FOLDER_ID correto
```

### 4. Configurar Google Drive
Siga o **GUIA_GOOGLE_DRIVE.md** para:
- Criar a Service Account no Google Cloud Console
- Baixar o `service_account.json`
- Compartilhar a pasta raiz do Drive com a Service Account

### 5. Executar
```bash
python app.py
```
Acesse: **http://localhost:5000**

---

## Dependências (`requirements.txt`)

```
flask>=3.0
python-dotenv>=1.0
google-api-python-client>=2.111
google-auth>=2.26
google-auth-oauthlib>=1.2
werkzeug>=3.0
```

---

## Funcionalidades

- ✅ Cadastro completo de alunos (8 seções no formulário)
- ✅ Edição de matrícula com trava de edição acidental
- ✅ Exclusão com confirmação via modal
- ✅ Listagem com filtros (nome, nível, sala) e ordenação
- ✅ Ficha de impressão com @media print
- ✅ Upload de 9 documentos por matrícula para o Google Drive
- ✅ Organização automática no Drive: `/ANO/SALA/ALUNOS/NOME/SUBPASTA`
- ✅ Aviso de divergência quando arquivo some do Drive
- ✅ Fallback local quando Drive está offline
- ✅ CAPS LOCK automático + "NÃO INFORMADO" para campos vazios
- ✅ Data de modificação registrada em cada alteração

---

## Desenvolvedor

Gabriel Nonato F. Carmo
