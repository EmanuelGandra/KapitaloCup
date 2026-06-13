# Guia — Automação pré-jogo no Google Chat

## 1. Arquivos que devem ficar no repositório

Na raiz do repositório:

```text
send_pre_match_google_chat_centralizado.py
requirements_google_chat_automation.txt
```

Dentro da pasta `.github/workflows/`:

```text
.github/workflows/pre_match_google_chat.yml
```

No Supabase SQL Editor, rode uma vez:

```text
create_chat_reminders_sent_pre_match.sql
```

Essa tabela impede reenvio duplicado para o mesmo jogo.

## 2. Secrets no GitHub

Crie estes repository secrets em:

```text
Repository > Settings > Secrets and variables > Actions > New repository secret
```

Secrets necessários:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
GOOGLE_CHAT_SPACE_ID
GOOGLE_CHAT_CLIENT_SECRET_JSON
GOOGLE_CHAT_TOKEN_JSON
```

Para testar no space de teste:

```text
GOOGLE_CHAT_SPACE_ID = spaces/AAQAwXXcclU
```

ou:

```text
GOOGLE_CHAT_SPACE_ID = AAQAwXXcclU
```

O script aceita os dois formatos.

## 3. Como subir no GitHub

Na pasta do projeto:

```bash
git pull
mkdir -p .github/workflows
cp /caminho/do/arquivo/send_pre_match_google_chat_centralizado.py .
cp /caminho/do/arquivo/requirements_google_chat_automation.txt .
cp /caminho/do/arquivo/pre_match_google_chat_centralizado.yml .github/workflows/pre_match_google_chat.yml

git add send_pre_match_google_chat_centralizado.py requirements_google_chat_automation.txt .github/workflows/pre_match_google_chat.yml
git commit -m "Automatiza mensagens pre-jogo no Google Chat"
git push
```

## 4. Como testar no GitHub Actions

Depois do push:

1. Entre no repositório no GitHub.
2. Clique em `Actions`.
3. Clique no workflow `Pre-match Google Chat reminders`.
4. Clique em `Run workflow`.
5. Para o primeiro teste, use:
   - `mode`: `dry-run`
   - `match_id`: vazio ou um jogo específico como `GD-01`
   - `kind`: `both`
6. Abra o log da execução e confira:
   - timezone usado;
   - próximos jogos detectados;
   - jogo candidato;
   - caminhos das imagens geradas;
   - se o script entraria ou não na janela de envio.

Quando estiver certo, rode novamente com:

```text
mode = send
```

Para forçar um jogo específico no teste:

```text
match_id = GD-01
mode = send
kind = both
```

O workflow adiciona `--force` automaticamente quando `match_id` é preenchido.

## 5. Como funciona automaticamente

O workflow roda a cada 5 minutos. O script procura jogos que estejam dentro da janela:

```text
37 minutos antes do jogo até 3 minutos depois do início
```

Como o script grava `match_id + reminder_type + minutes_before` em `chat_reminders_sent`, ele não reenvia a mesma mensagem em execuções seguintes.

## 6. Convenção de horário

Use uma regra única na tabela `matches`:

```text
kickoff_at = horário de Brasília mostrado no app
```

Por exemplo:

```text
Estados Unidos x Paraguai: 2026-06-12 22:00:00
Austrália x Turquia: 2026-06-14 01:00:00
```

O workflow usa:

```text
KICKOFF_SOURCE_TIMEZONE = America/Sao_Paulo
```

então datas sem timezone no Supabase são interpretadas como horário de Brasília.
