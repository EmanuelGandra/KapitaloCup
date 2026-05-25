# Bolão Copa do Mundo 2026 — Streamlit + Supabase

Aplicação de bolão **sem apostas financeiras**, com cadastro de usuários, palpites por partida, palpites de classificados/campeão/artilheiro, ranking e painel admin para inserir resultados oficiais.

## Estrutura esperada

```text
.
├── app.py
├── data/
│   └── wc2026_group_stage_seed.csv
├── src/
│   ├── auth.py
│   ├── db.py
│   ├── scoring.py
│   └── seed.py
├── aux/
│   └── supabase_schema.sql
├── outputs/
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
└── requirements.txt
```

## Por que Supabase?

Para ranking atualizado entre várias pessoas, Supabase é mais adequado que Google Sheets porque oferece banco Postgres, constraints, upsert, consultas e separação clara entre usuários, jogos, palpites e resultados. Google Sheets funciona para protótipo, mas fica frágil para concorrência e validação.

## Setup

1. Crie um projeto Supabase.
2. Rode o SQL em `aux/supabase_schema.sql` no SQL Editor do Supabase.
3. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "sua_anon_key_ou_service_role_para_app_privado"
ADMIN_USER = "admin"
```

4. Instale dependências:

```bash
pip install -r requirements.txt
```

5. Suba os jogos seed:

```bash
python -m src.seed
```

6. Rode a aplicação:

```bash
streamlit run app.py
```

## Observações importantes

- O arquivo seed inclui os 72 jogos da fase de grupos como combinações entre as seleções dos grupos. Para datas/estádios oficiais, atualize o CSV com uma fonte oficial/API e rode novamente o seed.
- Jogos de mata-mata começam como placeholders. Quando os classificados forem conhecidos, o admin pode criar/atualizar partidas pelo painel admin.
- O scoring usa as regras em `src/scoring.py`, com pesos por fase.
- Para um app público real, prefira Supabase Auth com e-mail/magic link. Este starter usa usuário/senha com hash bcrypt para manter o fluxo simples por username.
