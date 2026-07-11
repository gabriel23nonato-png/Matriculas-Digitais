# Empacotando o Sistema de Matrículas em .exe

Guia completo: gerar o executável, e instalar/configurar em outro computador
(ex.: o computador da escola), incluindo banco de dados e Google Drive.

---

## Visão geral do processo

1. **No SEU computador** (onde você já desenvolve): gera o `.exe` com PyInstaller.
2. **Copia a pasta gerada** para o computador da escola (pendrive, rede, nuvem — como preferir).
3. **No computador da escola**: só cola os arquivos de configuração ao lado do `.exe` e roda. **Não precisa instalar Python lá** — é essa a vantagem do executável.

---

## Parte 1 — Correção necessária antes de gerar o .exe

Um executável gerado pelo PyInstaller, ao rodar, extrai os arquivos para uma
pasta temporária diferente a cada abertura. Se o caminho do banco de dados,
dos uploads e do `token.json` do Drive dependesse dessa pasta temporária
(como no código original, baseado em `__file__`), **tudo seria perdido a
cada vez que o programa fosse fechado e reaberto** — banco zerado, uploads
sumindo, login do Drive pedido de novo sempre.

Já apliquei a correção nos dois arquivos anexados a esta mensagem
(`app.py` e `drive_service.py`): agora banco, uploads, `.env`,
`client_secret.json` e `token.json` sempre são lidos/gravados na pasta
**onde o `.exe` está**, não na pasta temporária. Templates e arquivos
estáticos (que não precisam persistir) continuam vindo de dentro do
executável normalmente. Também desliguei o modo debug/reloader do Flask
quando rodando como `.exe` (o reloader tenta reabrir o processo sozinho e
quebra dentro de um executável), e adicionei abertura automática do
navegador ao iniciar.

**Use os `app.py` e `drive_service.py` anexados a partir de agora** — eles
substituem os que você já tinha.

---

## Parte 2 — Gerar o executável (no seu computador)

### 2.1 Estrutura de pastas esperada antes do build

```
projeto/
├── app.py                 ← já corrigido
├── drive_service.py       ← já corrigido
├── requirements.txt
├── build.spec
├── build.bat
├── templates/              (seus .html: nova_matricula.html, etc.)
├── static/                 (se você tiver css/js/imagens — opcional)
├── client_secret.json      (sua credencial OAuth)
└── .env                    (SECRET_KEY e DRIVE_ROOT_FOLDER_ID reais)
```

Coloque `requirements.txt`, `build.spec` e `build.bat` (anexados) na raiz do
projeto, junto do `app.py`.

### 2.2 Rodar o build

Com o projeto organizado assim, dê duplo clique em `build.bat` (ou rode pelo
terminal: `build.bat`). O script vai:

1. Criar um ambiente virtual `venv_build`
2. Instalar tudo do `requirements.txt`
3. Rodar o PyInstaller usando `build.spec`

Ao final, você terá:

```
dist/
└── SistemaMatriculas/
    ├── SistemaMatriculas.exe
    ├── templates/            ← já embutido
    ├── static/               ← já embutido (se existir)
    └── (arquivos internos do PyInstaller)
```

> Usei modo **onedir** (pasta), não **onefile** (um único .exe). Onedir abre
> mais rápido e é mais fácil de debugar se algo der errado — o preço é ter
> uma pasta em vez de um arquivo único, mas para instalar num computador da
> escola isso não faz diferença nenhuma.

### 2.3 Testar antes de levar para a escola

Dentro de `dist/SistemaMatriculas/`, copie:
- `.env` (preenchido com valores reais — use `.env.example` como modelo)
- `client_secret.json`

Dê duplo clique em `SistemaMatriculas.exe`. Ele deve:
- Abrir uma janela de console (por enquanto deixei `console=True` no spec de propósito, pra você ver erros se houver)
- Abrir o navegador automaticamente em `http://127.0.0.1:5000`
- Na primeira vez que qualquer ação tocar o Drive, abrir o navegador pedindo login OAuth (gera o `token.json` ali do lado)

Se tudo funcionar, teste criar uma matrícula com upload de documento antes de levar pra escola.

---

## Parte 3 — Instalar no computador da escola

### 3.1 O que copiar

Leve a pasta `dist/SistemaMatriculas/` inteira (pendrive, ZIP, etc.) e cole
em qualquer lugar do computador da escola, por exemplo
`C:\SistemaMatriculas\`.

### 3.2 Arquivos de configuração — duas opções para o Google Drive

**Opção A — reaproveitar o login que você já fez (recomendado)**
Depois de testar no seu computador (Parte 2.3), o `token.json` já foi criado
ali do lado do `.exe`. Copie esse `token.json` junto com o resto da pasta
para a escola. Assim o computador da escola **já abre autenticado**, sem
pedir login — é essa a configuração combinada anteriormente (tratar o
computador da escola como produção, evitando reautenticação).

**Opção B — autenticar direto no computador da escola**
Se preferir (ou se o Drive terá conta diferente), não leve o `token.json`.
Na primeira execução lá, o navegador vai abrir pedindo login Google — só
funciona se aquele computador tiver acesso à internet e a um navegador.

Em ambos os casos, o `client_secret.json` **precisa estar presente** —
ele identifica a aplicação (não a pessoa), então é o mesmo arquivo nos dois
casos.

### 3.3 Checklist final de arquivos na pasta do .exe (na escola)

```
C:\SistemaMatriculas\
├── SistemaMatriculas.exe
├── templates\               ← veio do build, não mexer
├── static\                  ← veio do build, não mexer
├── .env                     ← copiado, com SECRET_KEY e DRIVE_ROOT_FOLDER_ID
├── client_secret.json       ← copiado
└── token.json               ← copiado (Opção A) ou gerado na 1ª execução (Opção B)
```

O banco (`database\database\alunosv3_novo.db`) e a pasta `uploads\` **não
precisam existir previamente** — o próprio `app.py` cria (`os.makedirs`) na
primeira execução.

### 3.4 Rodando no dia a dia

Dê duplo clique em `SistemaMatriculas.exe`. Ele abre o navegador sozinho.
Para a secretária/diretora não precisar entender nada de terminal, sugiro:

- Criar um atalho do `.exe` na área de trabalho, renomeado para algo como
  "Sistema de Matrículas".
- (Opcional, depois de validar que está tudo estável) trocar `console=True`
  para `console=False` no `build.spec` e gerar o build de novo — isso some
  com a janela preta de terminal, deixando só o navegador visível.

### 3.5 Backup do banco de dados

Como o banco fica em
`C:\SistemaMatriculas\database\database\alunosv3_novo.db`, o backup da
escola é simplesmente copiar esse arquivo (e a pasta `uploads\`, para os
poucos documentos que não estão no Drive) periodicamente para um pendrive
ou nuvem. Não depende de instalar nada.

---

## Parte 4 — Perguntas frequentes

**Preciso instalar Python no computador da escola?**
Não. O PyInstaller empacota o interpretador Python junto no `.exe` — é
essa a finalidade dele.

**E se eu alterar o código depois?**
Você refaz o build (Parte 2) só no seu computador e leva a nova pasta
`dist/SistemaMatriculas/` pra escola, tomando cuidado de **copiar de volta**
o `.env`, `client_secret.json`, `token.json` e as pastas `database/` e
`uploads/` antigas para dentro da nova pasta antes de substituir — senão
perde os dados já cadastrados.

**O antivírus da escola pode bloquear o .exe?**
É comum: executáveis gerados por PyInstoller sem assinatura digital às
vezes disparam falso positivo em antivírus corporativos/Windows Defender
SmartScreen. Se acontecer, será preciso adicionar uma exceção manual no
antivírus daquele computador — isso foge do que dá pra resolver por código.

**Preciso reautenticar o Drive toda vez que atualizar o .exe?**
Não, desde que você preserve o `token.json` ao substituir os arquivos
(ver pergunta 2). Ele só expira/pede login de novo se for revogado
manualmente no Google, ou se o `client_secret.json` mudar (novo projeto
OAuth no Google Cloud).
