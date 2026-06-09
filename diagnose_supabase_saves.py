"""
Diagnóstico de salvamento no Supabase para Kapitalo Cup.

Como usar:
1) Salve este arquivo na raiz do projeto, ao lado do app.py.
2) Rode:
   python diagnose_supabase_saves.py

O script tenta reproduzir os salvamentos principais do app:
- leitura de profiles/matches
- criação de usuário diagnóstico
- insert/upsert em bonus_predictions
- insert/upsert em predictions
- limpeza das linhas de teste

Ele NÃO apaga dados de usuários reais. Só cria e remove linhas com username começando por __diag_save_.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    import tomli as tomllib

try:
    from supabase import create_client
except Exception as exc:
    print("ERRO: pacote supabase não instalado/importável.")
    print("Instale com: pip install supabase")
    raise


ROOT = Path(__file__).resolve().parent
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"


def load_secrets() -> dict[str, Any]:
    data: dict[str, Any] = {}

    if SECRETS_PATH.exists():
        with SECRETS_PATH.open("rb") as f:
            data.update(tomllib.load(f))

    # env vence arquivo local, se existir
    for key in ["SUPABASE_URL", "SUPABASE_KEY"]:
        if os.getenv(key):
            data[key] = os.getenv(key)

    return data


def decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    except Exception:
        return {}


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_ok(msg: str) -> None:
    print(f"OK   | {msg}")


def print_warn(msg: str) -> None:
    print(f"WARN | {msg}")


def print_fail(msg: str) -> None:
    print(f"FAIL | {msg}")


def show_exception(exc: Exception) -> None:
    print_fail(f"{type(exc).__name__}: {exc}")
    # Supabase/PostgREST costuma ter args com dict útil
    if getattr(exc, "args", None):
        print("Detalhes args:", exc.args)
    print("Traceback curto:")
    traceback.print_exc(limit=3)


def require_columns(df_like: list[dict[str, Any]], table_name: str) -> None:
    if not df_like:
        print_warn(f"{table_name}: consulta retornou vazia.")
        return
    print_ok(f"{table_name}: colunas detectadas: {sorted(df_like[0].keys())}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="Não limpar linhas de diagnóstico ao final.")
    parser.add_argument("--username-prefix", default="__diag_save_", help="Prefixo do usuário diagnóstico.")
    args = parser.parse_args()

    print_header("1) Lendo configuração")
    secrets = load_secrets()

    url = str(secrets.get("SUPABASE_URL", "")).strip()
    key = str(secrets.get("SUPABASE_KEY", "")).strip()

    if not url or not key:
        print_fail("SUPABASE_URL ou SUPABASE_KEY não encontrados em .streamlit/secrets.toml nem em env vars.")
        return 2

    print_ok(f"SUPABASE_URL encontrado: {url[:35]}...")
    print_ok(f"SUPABASE_KEY encontrado: tamanho={len(key)}")

    payload = decode_jwt_payload(key)
    role = payload.get("role") or payload.get("app_metadata", {}).get("role")
    if role:
        print_ok(f"Role da chave JWT: {role}")
        if role == "anon":
            print_warn("Você está usando anon key. Inserts dependem de policies RLS para anon.")
        elif role == "service_role":
            print_ok("Você está usando service_role. Deve bypassar RLS se a chave estiver correta.")
    else:
        print_warn("Não consegui identificar a role da SUPABASE_KEY. A chave pode não ser JWT ou está em formato inesperado.")

    supabase = create_client(url, key)

    diag_username = f"{args.username_prefix}{int(time.time())}"
    diag_password_hash = hashlib.sha256(b"diagnostic_password_not_used").hexdigest()
    created_profile_id: str | None = None
    chosen_match_id: str | None = None

    print_header("2) Testando leituras básicas")
    try:
        profiles_res = supabase.table("profiles").select("id, username").limit(5).execute()
        print_ok(f"profiles SELECT funcionou. Linhas retornadas: {len(profiles_res.data or [])}")
        require_columns(profiles_res.data or [], "profiles")
    except Exception as exc:
        print_fail("profiles SELECT falhou. Se isso falha, o app não consegue nem logar/listar usuários.")
        show_exception(exc)
        return 3

    try:
        matches_res = (
            supabase.table("matches")
            .select("match_id, stage, home_team, away_team")
            .limit(1)
            .execute()
        )
        print_ok(f"matches SELECT funcionou. Linhas retornadas: {len(matches_res.data or [])}")
        require_columns(matches_res.data or [], "matches")
        if matches_res.data:
            chosen_match_id = str(matches_res.data[0]["match_id"])
            print_ok(f"Usarei match_id de teste: {chosen_match_id}")
        else:
            print_fail("Não há jogos em matches; não dá para testar predictions.")
            return 4
    except Exception as exc:
        print_fail("matches SELECT falhou.")
        show_exception(exc)
        return 4

    print_header("3) Testando criação de profile diagnóstico")
    try:
        profile_payload = {
            "username": diag_username,
            "password_hash": diag_password_hash,
        }
        res = supabase.table("profiles").insert(profile_payload).execute()
        if not res.data:
            print_warn("profiles INSERT não retornou dados. Vou tentar buscar pelo username.")
            lookup = supabase.table("profiles").select("id, username").eq("username", diag_username).execute()
            if not lookup.data:
                print_fail("profiles INSERT aparentemente não criou linha.")
                return 5
            created_profile_id = lookup.data[0]["id"]
        else:
            created_profile_id = res.data[0]["id"]
        print_ok(f"profiles INSERT funcionou. user_id={created_profile_id}")
    except Exception as exc:
        print_fail("profiles INSERT falhou. Provável RLS/policy/constraint.")
        show_exception(exc)
        return 5

    print_header("4) Testando bonus_predictions upsert")
    try:
        bonus_payload = {
            "user_id": created_profile_id,
            "champion": "Brazil",
            "top_scorer": "Kylian Mbappé",
        }
        res = supabase.table("bonus_predictions").upsert(bonus_payload, on_conflict="user_id").execute()
        print_ok(f"bonus_predictions UPSERT funcionou. Retorno linhas: {len(res.data or [])}")

        check = supabase.table("bonus_predictions").select("user_id, champion, top_scorer").eq("user_id", created_profile_id).execute()
        if check.data:
            print_ok(f"bonus_predictions SELECT pós-upsert: {check.data}")
        else:
            print_fail("bonus_predictions não apareceu depois do upsert.")
    except Exception as exc:
        print_fail("bonus_predictions UPSERT falhou.")
        show_exception(exc)

    print_header("5) Testando predictions upsert")
    try:
        pred_payload = {
            "user_id": created_profile_id,
            "match_id": chosen_match_id,
            "home_goals": 1,
            "away_goals": 0,
            "advancing_team": None,
        }
        res = supabase.table("predictions").upsert(pred_payload, on_conflict="user_id,match_id").execute()
        print_ok(f"predictions UPSERT funcionou. Retorno linhas: {len(res.data or [])}")

        check = (
            supabase.table("predictions")
            .select("user_id, match_id, home_goals, away_goals, advancing_team")
            .eq("user_id", created_profile_id)
            .eq("match_id", chosen_match_id)
            .execute()
        )
        if check.data:
            print_ok(f"predictions SELECT pós-upsert: {check.data}")
        else:
            print_fail("prediction não apareceu depois do upsert.")
    except Exception as exc:
        print_fail("predictions UPSERT falhou.")
        show_exception(exc)

    print_header("6) Testando limpeza das linhas diagnóstico")
    if args.keep:
        print_warn(f"--keep ativo. Não vou deletar o usuário diagnóstico {diag_username}.")
        print_warn("Apague manualmente depois se quiser.")
    else:
        try:
            if created_profile_id:
                supabase.table("predictions").delete().eq("user_id", created_profile_id).execute()
                supabase.table("bonus_predictions").delete().eq("user_id", created_profile_id).execute()
                # phase_predictions pode existir em versões antigas
                try:
                    supabase.table("phase_predictions").delete().eq("user_id", created_profile_id).execute()
                except Exception as exc:
                    print_warn(f"phase_predictions cleanup falhou/ignorado: {exc}")
                supabase.table("profiles").delete().eq("id", created_profile_id).execute()
                print_ok("Limpeza concluída.")
        except Exception as exc:
            print_fail("Falha na limpeza. Pode ter sobrado usuário diagnóstico.")
            print_warn(f"Username diagnóstico: {diag_username}")
            print_warn(f"User id diagnóstico: {created_profile_id}")
            show_exception(exc)
            return 6

    print_header("7) Resultado")
    print("Se profiles/bonus_predictions/predictions UPSERT funcionaram aqui, o problema está no app.py/validação/cache.")
    print("Se algum UPSERT falhou com RLS/policy/permission, o problema está em RLS/policies/chave Supabase.")
    print("Se falhou com constraint/column, o schema da tabela está diferente do esperado.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
