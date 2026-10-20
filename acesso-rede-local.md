# Guia: Acessar o Sistema de Matrículas de Outro Notebook

> **Contexto:** O sistema roda em Flask com SQLite, numa máquina local (Windows ou Linux).  
> O objetivo é fazer **um segundo notebook na mesma rede Wi-Fi** acessar o sistema sem precisar instalar nada.

---

## Índice

1. [O que muda e o que não muda](#1-o-que-muda-e-o-que-não-muda)
2. [Passo 1 — Expor o Flask na rede local](#2-passo-1--expor-o-flask-na-rede-local)
3. [Passo 2 — Descobrir o IP do servidor](#3-passo-2--descobrir-o-ip-do-servidor)
4. [Passo 3 — Liberar o firewall](#4-passo-3--liberar-o-firewall)
5. [Passo 4 — Acessar do segundo notebook](#5-passo-4--acessar-do-segundo-notebook)
6. [Banco de dados SQLite — cuidados com acesso simultâneo](#6-banco-de-dados-sqlite--cuidados-com-acesso-simultâneo)
7. [Google OAuth e o problema do localhost](#7-google-oauth-e-o-problema-do-localhost)
8. [Opção alternativa: ngrok (acesso de qualquer lugar)](#8-opção-alternativa-ngrok-acesso-de-qualquer-lugar)
9. [Checklist final](#9-checklist-final)
10. [Erros comuns e soluções](#10-erros-comuns-e-soluções)

---

## 1. O que muda e o que não muda

| Item | Situação atual | Após as mudanças |
|---|---|---|
| Servidor Flask | `localhost:5000` (só a própria máquina acessa) | `0.0.0.0:5000` (qualquer máquina da rede acessa) |
| Banco SQLite | Acesso por um usuário só | Continua funcionando; pequeno risco se dois usuários salvarem ao mesmo tempo |
| Google OAuth | Configurado para `localhost` | Precisa adicionar o IP local como URI autorizado |
| Segundo notebook | Sem acesso | Abre o sistema pelo navegador, sem instalar nada |

---

## 2. Passo 1 — Expor o Flask na rede local

Por padrão, o Flask escuta apenas `127.0.0.1` (a própria máquina).  
Para aceitar conexões de fora, mude o `host` na última linha do `app.py`:

**Antes:**
```python
if __name__ == '__main__':
    app.run(debug=True)
```

**Depois:**
```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

> ⚠️ **Mude `debug=False`** ao abrir para a rede. O modo debug expõe um console Python interativo acessível por qualquer pessoa na rede.

---

## 3. Passo 2 — Descobrir o IP do servidor

No notebook que roda o Flask (o servidor), abra o terminal e execute:

**Windows:**
```
ipconfig
```
Procure por **"Endereço IPv4"** na seção do adaptador Wi-Fi. Exemplo: `192.168.1.105`

**Linux/macOS:**
```
ip a
```
ou
```
hostname -I
```
Procure pelo IP que começa com `192.168.x.x` ou `10.x.x.x`.

> 💡 **Dica:** Esse IP pode mudar toda vez que o roteador reinicia. Veja a seção [IP fixo na rede local](#ip-fixo-na-rede-local-opcional) se isso for um problema.

### IP fixo na rede local (opcional)

Para o IP não mudar, acesse as configurações do roteador (geralmente `192.168.1.1` no navegador) e reserve o IP para o endereço MAC do notebook servidor. O processo varia por modelo de roteador — procure por "DHCP reservation" ou "IP estático" nas configurações.

---

## 4. Passo 3 — Liberar o firewall

O Windows bloqueia conexões de entrada por padrão. É preciso abrir a porta 5000.

**Windows — via PowerShell (como Administrador):**
```powershell
New-NetFirewallRule -DisplayName "Flask Matriculas" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

**Windows — via interface gráfica:**
1. Abra **Firewall do Windows Defender**
2. Clique em **Regras de Entrada → Nova Regra**
3. Selecione **Porta → TCP → 5000**
4. Selecione **Permitir a conexão**
5. Marque as três redes (Domínio, Privada, Pública)
6. Dê o nome "Flask Matriculas"

**Linux (ufw):**
```bash
sudo ufw allow 5000/tcp
```

---

## 5. Passo 4 — Acessar do segundo notebook

No segundo notebook (o cliente), abra qualquer navegador e acesse:

```
http://192.168.1.105:5000
```

Substitua `192.168.1.105` pelo IP real que você descobriu no Passo 2.

Não é preciso instalar Python, Flask ou qualquer dependência no segundo notebook. Ele só precisa estar **na mesma rede Wi-Fi**.

---

## 6. Banco de dados SQLite — cuidados com acesso simultâneo

O SQLite foi feito para uso por um processo só. Com dois usuários acessando ao mesmo tempo, pode acontecer o erro `database is locked` se os dois tentarem **escrever** no mesmo momento.

### O que já funciona bem

- Dois usuários **lendo** ao mesmo tempo: sem problema.
- Um usuário lendo enquanto outro escreve: geralmente funciona.
- Dois usuários salvando matrículas **ao mesmo tempo**: risco de conflito.

### Solução simples (recomendada para uso com poucos usuários)

Adicione o modo WAL e um timeout no `get_db()` do `app.py`. Isso resolve a grande maioria dos conflitos:

```python
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")   # ← adicionar
        db.execute("PRAGMA busy_timeout = 5000")  # ← adicionar (5 segundos)
    return db
```

- **WAL (Write-Ahead Logging):** permite leituras enquanto uma escrita está em andamento.
- **busy_timeout:** em vez de travar com erro imediatamente, o SQLite aguarda até 5 segundos antes de desistir.

> ℹ️ Para uso com mais de 5 usuários simultâneos fazendo cadastros ao mesmo tempo, o ideal seria migrar para PostgreSQL. Para o uso atual (secretaria escolar com 1–3 pessoas), SQLite com WAL é suficiente.

---

## 7. Google OAuth e o problema do localhost

Se o sistema usa Google OAuth para login, o Google valida a URL de retorno (callback) contra uma lista de URIs autorizados cadastrada no Google Cloud Console. O problema é que o callback estava registrado como `http://localhost:5000/callback` — e agora o endereço mudou para `http://192.168.1.105:5000/callback`.

### Como corrigir

**1. Acesse o Google Cloud Console:**
```
https://console.cloud.google.com
```

**2. Vá em:** APIs e Serviços → Credenciais → clique na sua credencial OAuth 2.0

**3. Em "URIs de redirecionamento autorizados", adicione as novas URLs:**
```
http://192.168.1.105:5000/callback
http://192.168.1.105:5000/login/google/authorized
```
(adicione as duas formas se não souber qual o projeto usa; mantenha o `localhost` também)

**4. Salve e aguarde até 5 minutos** para propagar.

### Alternativa: usar ngrok para manter o OAuth funcionando

Se não quiser mexer no Google Cloud toda vez que o IP mudar, use o ngrok (explicado na seção seguinte). O ngrok gera um endereço fixo HTTPS que o Google aceita.

### Problema: "Este app não é verificado"

Se o projeto OAuth ainda está em modo de teste no Google, só os e-mails cadastrados como "usuários de teste" conseguem fazer login. Para resolver:

- Vá em **OAuth consent screen → Test users** e adicione o e-mail do segundo notebook.
- Ou publique o app (se for uso interno/escolar, não é necessário verificação formal).

---

## 8. Opção alternativa: ngrok (acesso de qualquer lugar)

O ngrok cria um túnel seguro que expõe seu `localhost` para a internet com um endereço HTTPS fixo. É útil se:

- Você quer acessar de **fora da rede** (de casa ou de outro local)
- Quer resolver o problema do OAuth sem mexer no IP toda vez
- Quer HTTPS sem configurar certificado

### Instalação

Acesse [https://ngrok.com](https://ngrok.com), crie uma conta gratuita e baixe o executável.

**Windows:** extraia o `ngrok.exe` e execute no terminal:
```
ngrok config add-authtoken SEU_TOKEN_AQUI
```

### Uso

Com o Flask rodando em `localhost:5000`, abra outro terminal e execute:
```
ngrok http 5000
```

O ngrok vai exibir algo como:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:5000
```

Qualquer pessoa com esse endereço consegue acessar o sistema — inclusive de fora da rede.

### OAuth com ngrok

Adicione o endereço ngrok como URI autorizado no Google Cloud Console:
```
https://abc123.ngrok-free.app/callback
```

> ⚠️ **Atenção:** no plano gratuito do ngrok, o endereço muda toda vez que você reinicia. Para endereço fixo, use o plano pago ou configure um domínio estático (a conta gratuita oferece 1 domínio estático).

---

## 9. Checklist final

Antes de usar, confirme cada item:

- [ ] `app.run(host='0.0.0.0', debug=False)` no `app.py`
- [ ] IP do servidor anotado (ex: `192.168.1.105`)
- [ ] Porta 5000 liberada no firewall do servidor
- [ ] Ambos os notebooks na mesma rede Wi-Fi
- [ ] `PRAGMA journal_mode = WAL` e `busy_timeout` configurados no `get_db()`
- [ ] URI de callback atualizado no Google Cloud Console (se usa OAuth)
- [ ] E-mail do segundo usuário cadastrado nos "Test users" do OAuth (se em modo teste)
- [ ] Testado: segundo notebook abre `http://IP_DO_SERVIDOR:5000` no navegador

---

## 10. Erros comuns e soluções

| Erro | Causa provável | Solução |
|---|---|---|
| Segundo notebook não consegue acessar | Firewall bloqueando | Criar regra de entrada para porta 5000 (Passo 3) |
| `database is locked` | Dois usuários salvando ao mesmo tempo | Adicionar WAL e busy_timeout (Seção 6) |
| `redirect_uri_mismatch` no OAuth | URI de callback não cadastrado no Google | Adicionar IP:5000 no Google Cloud Console (Seção 7) |
| `Access blocked: This app's request is invalid` | App OAuth em modo teste, e-mail não cadastrado | Adicionar e-mail em Test Users (Seção 7) |
| Página carrega mas login não funciona | `SECRET_KEY` do Flask não está fixa | Definir `app.secret_key = 'valor-fixo'` no app.py |
| IP muda e para de funcionar | DHCP do roteador redistribuiu o IP | Reservar o IP no roteador ou usar ngrok |
| `OSError: [Errno 98] Address already in use` | Outra instância do Flask já está rodando | Encerrar o processo anterior com `kill $(lsof -t -i:5000)` |

---

> **Resumo rápido:** Para uso simples na mesma rede Wi-Fi, as mudanças necessárias são apenas três: `host='0.0.0.0'` no Flask, uma regra no firewall, e adicionar o IP no Google OAuth. O banco SQLite aguenta bem com WAL ativado.
