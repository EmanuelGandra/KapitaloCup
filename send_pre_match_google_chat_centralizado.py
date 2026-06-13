#!/usr/bin/env python3
"""
send_pre_match_google_chat.py

Envia automaticamente, 30 minutos antes de cada jogo da Kapitalo Cup, as MESMAS
mensagens/imagens usadas no app em:

1) Admin > Google Chat > Palpites por jogo
2) Admin > Google Chat > Distribuição placares

O script é seguro: por padrão ele só lê Supabase. Ele só grava na tabela
public.chat_reminders_sent para não reenviar o mesmo aviso várias vezes.

USO NORMAL, POR AGENDADOR:
    python send_pre_match_google_chat.py --send

TESTE SEM ENVIAR:
    python send_pre_match_google_chat.py --dry-run

TESTE COM JOGO FAKE, SEM MEXER NO SUPABASE:
    python send_pre_match_google_chat.py --dry-run --fake-game

TESTE REAL MANDANDO NO SPACE DE TESTE:
    python send_pre_match_google_chat.py --send --fake-game --space AAQAwXXcclU

FORÇAR UM JOGO REAL ESPECÍFICO, IGNORANDO HORÁRIO:
    python send_pre_match_google_chat.py --dry-run --match-id GA-01
    python send_pre_match_google_chat.py --send --match-id GA-01 --force --space AAQAwXXcclU

SIMULAR QUE AGORA É 30MIN ANTES DE UM JOGO REAL:
    python send_pre_match_google_chat.py --dry-run --now "2026-06-11 15:30:00"

DEPENDÊNCIAS:
    pip install pandas matplotlib supabase google-auth google-api-python-client tomli

SECRETS ACEITOS POR VARIÁVEL DE AMBIENTE OU .streamlit/secrets.toml:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_KEY ou SUPABASE_ANON_KEY
    GOOGLE_CHAT_SPACE_ID
    GOOGLE_CHAT_CLIENT_SECRET_JSON
    GOOGLE_CHAT_TOKEN_JSON
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except Exception:  # pragma: no cover
        tomllib = None  # type: ignore


# ============================================================
# CONFIGURAÇÃO
# ============================================================

APP_NAME = "Kapitalo Cup"
PRIMARY_COLOR = "#ba083a"
APP_TIMEZONE = "America/Sao_Paulo"
GOOGLE_CHAT_SCOPE = "https://www.googleapis.com/auth/chat.messages.create"
SUPABASE_PAGE_SIZE = 1000
DEFAULT_SPACE_ID = "spaces/AAQAwXXcclU"  # space de teste pedido

DEFAULT_TABLE_ORDER_COLUMNS = {
    "profiles": ["username", "id"],
    "matches": ["kickoff_at", "match_no", "match_id"],
    "predictions": ["match_id", "user_id"],
    "actual_results": ["match_id"],
    "bonus_predictions": ["user_id"],
    "chat_reminders_sent": ["sent_at", "id"],
}


@dataclass
class MatchInfo:
    match_id: str
    match_no: Any
    stage: str
    group_name: str
    kickoff_at: pd.Timestamp
    home_team: str
    away_team: str
    venue: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "match_no": self.match_no,
            "stage": self.stage,
            "group_name": self.group_name,
            "kickoff_at": self.kickoff_at,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "venue": self.venue,
        }


# ============================================================
# SECRETS / CLIENTES
# ============================================================


def _load_local_streamlit_secrets() -> dict[str, Any]:
    """Lê .streamlit/secrets.toml quando o script roda fora do Streamlit."""
    if tomllib is None:
        return {}

    candidates = [
        Path.cwd() / ".streamlit" / "secrets.toml",
        Path(__file__).resolve().parent / ".streamlit" / "secrets.toml",
        Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml",
    ]

    for path in candidates:
        if path.exists():
            with path.open("rb") as f:
                return tomllib.load(f)

    return {}


_LOCAL_SECRETS = _load_local_streamlit_secrets()


def get_secret(name: str, default: str | None = None) -> str | None:
    """Busca secret em env, depois em .streamlit/secrets.toml."""
    value = os.getenv(name)
    if value is not None and str(value).strip() != "":
        return value

    if name in _LOCAL_SECRETS:
        raw = _LOCAL_SECRETS[name]
        if isinstance(raw, (dict, list)):
            return json.dumps(raw)
        return str(raw)

    return default


def get_secret_json(name: str) -> dict[str, Any]:
    raw = get_secret(name)
    if not raw:
        return {}

    raw = str(raw).strip()
    try:
        return json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"Secret {name} não é um JSON válido: {exc}") from exc


def get_supabase_client():
    try:
        from supabase import create_client
    except Exception as exc:
        raise RuntimeError("Pacote supabase não instalado. Rode: pip install supabase") from exc

    url = get_secret("SUPABASE_URL")
    key = (
        get_secret("SUPABASE_SERVICE_ROLE_KEY")
        or get_secret("SUPABASE_KEY")
        or get_secret("SUPABASE_ANON_KEY")
    )

    if not url or not key:
        raise RuntimeError(
            "Faltam SUPABASE_URL e uma chave: SUPABASE_SERVICE_ROLE_KEY, SUPABASE_KEY ou SUPABASE_ANON_KEY."
        )

    return create_client(url, key)


def normalize_google_token_json(token_data: dict[str, Any], client_secret_data: dict[str, Any] | None = None) -> dict[str, Any]:
    token_data = dict(token_data or {})

    if "token" not in token_data and "access_token" in token_data:
        token_data["token"] = token_data.pop("access_token")

    for key in ["token", "refresh_token", "client_id", "client_secret", "token_uri"]:
        if isinstance(token_data.get(key), list):
            token_data[key] = token_data[key][0] if token_data[key] else ""

    client_block: dict[str, Any] = {}
    if client_secret_data:
        client_block = client_secret_data.get("installed") or client_secret_data.get("web") or {}

    token_data.setdefault("token_uri", client_block.get("token_uri", "https://oauth2.googleapis.com/token"))
    token_data.setdefault("client_id", client_block.get("client_id", ""))
    token_data.setdefault("client_secret", client_block.get("client_secret", ""))
    token_data.setdefault("scopes", [GOOGLE_CHAT_SCOPE])

    return token_data


def get_chat_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.exceptions import RefreshError
    except Exception as exc:
        raise RuntimeError(
            "Dependências do Google Chat não instaladas. Rode: pip install google-auth google-api-python-client"
        ) from exc

    client_secret_data = get_secret_json("GOOGLE_CHAT_CLIENT_SECRET_JSON")
    token_data = normalize_google_token_json(get_secret_json("GOOGLE_CHAT_TOKEN_JSON"), client_secret_data)

    if not token_data.get("token") and not token_data.get("refresh_token"):
        raise RuntimeError("GOOGLE_CHAT_TOKEN_JSON não tem token ou refresh_token válido.")

    creds = Credentials.from_authorized_user_info(token_data, [GOOGLE_CHAT_SCOPE])

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise RuntimeError(
                    "Token do Google Chat expirou e não conseguiu renovar. Gere um novo GOOGLE_CHAT_TOKEN_JSON."
                ) from exc
        else:
            raise RuntimeError("Credenciais do Google Chat inválidas.")

    return build("chat", "v1", credentials=creds)


def normalize_space_id(space: str | None) -> str:
    raw = (space or get_secret("GOOGLE_CHAT_SPACE_ID") or DEFAULT_SPACE_ID).strip()
    if not raw:
        return DEFAULT_SPACE_ID
    if raw.startswith("spaces/"):
        return raw
    return f"spaces/{raw}"


# ============================================================
# HELPERS DE DADOS / TEMPO
# ============================================================


def now_app_tz() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(ZoneInfo(APP_TIMEZONE))).floor("s")


def parse_app_datetime(value: Any) -> pd.Timestamp:
    """Converte datas do app para timezone oficial.

    Se a data vier sem timezone, é interpretada como horário de Brasília.
    Se vier com timezone explícito, é convertida para Brasília.
    """
    if value is None or pd.isna(value) or str(value).strip() == "":
        raise ValueError("Data vazia")

    dt = pd.to_datetime(value, errors="raise")
    ts = pd.Timestamp(dt)

    if ts.tzinfo is None:
        return ts.tz_localize(APP_TIMEZONE)
    return ts.tz_convert(APP_TIMEZONE)


def get_kickoff_source_timezone() -> str:
    """Timezone usado quando kickoff_at vem sem timezone do Supabase.

    Na base atual do bolão, kickoff_at costuma ser salvo como timestamp sem timezone,
    representando o horário de Brasília que aparece no app. Nesse caso, o valor
    correto é America/Sao_Paulo. Se no futuro a base passar a guardar outro fuso,
    defina KICKOFF_SOURCE_TIMEZONE nos secrets/env.
    """
    return get_secret("KICKOFF_SOURCE_TIMEZONE", APP_TIMEZONE) or APP_TIMEZONE


def parse_kickoff_datetime(value: Any) -> pd.Timestamp:
    """Converte kickoff_at para o timezone oficial do app.

    - Se kickoff_at vier com timezone/offset, converte para America/Sao_Paulo.
    - Se vier sem timezone, interpreta no timezone definido por
      KICKOFF_SOURCE_TIMEZONE. O default é America/Sao_Paulo.
    """
    if value is None or pd.isna(value) or str(value).strip() == "":
        raise ValueError("Data vazia")

    dt = pd.to_datetime(value, errors="raise")
    ts = pd.Timestamp(dt)

    if ts.tzinfo is None:
        return ts.tz_localize(get_kickoff_source_timezone()).tz_convert(APP_TIMEZONE)

    return ts.tz_convert(APP_TIMEZONE)


def parse_now_arg(value: str | None) -> pd.Timestamp:
    if not value:
        return now_app_tz()
    return parse_app_datetime(value).floor("s")


def format_kickoff(value: Any) -> str:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return "Horário a definir"
    try:
        dt = parse_kickoff_datetime(value)
    except Exception:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return "Horário a definir"
    return pd.Timestamp(dt).strftime("%d/%m/%Y %H:%M")


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def norm_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().lower()


def normalize_username(value: Any) -> str:
    return norm_text(value)


def is_group_stage(stage: str) -> bool:
    stage_norm = norm_text(stage)
    return (
        "grupo" in stage_norm
        or "group" in stage_norm
        or "primeira" in stage_norm
        or "fase de grupos" in stage_norm
    )


def is_knockout_stage(stage: str) -> bool:
    return not is_group_stage(stage)


def get_match_result_type(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def sort_matches_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if "kickoff_at" in out.columns:
        out["kickoff_sort"] = pd.to_datetime(out["kickoff_at"], errors="coerce")
    else:
        out["kickoff_sort"] = pd.NaT

    sort_cols = ["kickoff_sort"]
    ascending = [True]
    if "match_no" in out.columns:
        sort_cols.append("match_no")
        ascending.append(True)
    if "match_id" in out.columns:
        sort_cols.append("match_id")
        ascending.append(True)

    return out.sort_values(sort_cols, ascending=ascending, na_position="last").drop(columns=["kickoff_sort"], errors="ignore")


def supabase_select_all(client, table_name: str, order_columns: list[str] | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    start = 0

    while True:
        end = start + SUPABASE_PAGE_SIZE - 1
        query = client.table(table_name).select("*")
        for col in order_columns or DEFAULT_TABLE_ORDER_COLUMNS.get(table_name, []):
            query = query.order(col)
        response = query.range(start, end).execute()
        page_rows = response.data or []
        rows.extend(page_rows)

        if len(page_rows) < SUPABASE_PAGE_SIZE:
            break

        start += SUPABASE_PAGE_SIZE
        if start > 250_000:
            raise RuntimeError(f"Paginação interrompida em {table_name}: mais de 250.000 linhas.")

    return pd.DataFrame(rows)


def load_supabase_data(client) -> dict[str, pd.DataFrame]:
    return {
        "matches": supabase_select_all(client, "matches"),
        "profiles": supabase_select_all(client, "profiles"),
        "predictions": supabase_select_all(client, "predictions"),
    }


# ============================================================
# SELEÇÃO DOS JOGOS-ALVO
# ============================================================


def get_target_matches(
    matches: pd.DataFrame,
    now: pd.Timestamp,
    minutes_before: int,
    early_window_minutes: int,
    late_window_minutes: int,
    post_kickoff_grace_minutes: int,
    match_id: str | None = None,
) -> list[MatchInfo]:
    """Seleciona jogos-alvo de forma robusta para scheduler.

    Em vez de depender de uma janela simétrica pequena em torno de now + 30min,
    usamos uma janela por minutos até o jogo:

        minutes_before - late_window <= minutos_para_o_jogo <= minutes_before + early_window

    Com defaults 30, early=7, late=30 e grace=2, o robô envia quando o jogo
    está entre 37 minutos antes e 2 minutos depois do início. Como há registro
    em chat_reminders_sent, rodar a cada 5 minutos no GitHub Actions não duplica.
    """
    if matches.empty or "match_id" not in matches.columns:
        return []

    df = matches.copy()
    if "kickoff_at" not in df.columns:
        return []

    parsed_values: list[pd.Timestamp | pd.NaT] = []
    for value in df["kickoff_at"].tolist():
        try:
            parsed_values.append(parse_kickoff_datetime(value))
        except Exception:
            parsed_values.append(pd.NaT)

    df["kickoff_ts"] = parsed_values
    df = df.dropna(subset=["kickoff_ts"])
    if df.empty:
        return []

    if match_id:
        df = df[df["match_id"].astype(str) == str(match_id)].copy()
    else:
        # minutos_para_o_jogo positivo = jogo ainda vai começar.
        df["minutes_to_kickoff"] = df["kickoff_ts"].apply(lambda ts: (pd.Timestamp(ts) - now).total_seconds() / 60.0)
        lower_minutes = float(minutes_before - late_window_minutes)
        lower_minutes = min(lower_minutes, 0.0) if post_kickoff_grace_minutes > 0 else max(lower_minutes, 0.0)
        lower_minutes = min(lower_minutes, -float(post_kickoff_grace_minutes))
        upper_minutes = float(minutes_before + early_window_minutes)
        df = df[(df["minutes_to_kickoff"] >= lower_minutes) & (df["minutes_to_kickoff"] <= upper_minutes)].copy()

    if df.empty:
        return []

    df = df.sort_values(["kickoff_ts"] + [c for c in ["match_no", "match_id"] if c in df.columns])

    out: list[MatchInfo] = []
    for _, row in df.iterrows():
        out.append(
            MatchInfo(
                match_id=str(row.get("match_id", "")),
                match_no=row.get("match_no", ""),
                stage=str(row.get("stage", "") or ""),
                group_name=str(row.get("group_name", "") or ""),
                kickoff_at=pd.Timestamp(row.get("kickoff_ts")),
                home_team=str(row.get("home_team", "") or ""),
                away_team=str(row.get("away_team", "") or ""),
                venue=str(row.get("venue", "") or ""),
            )
        )
    return out


def print_next_matches(matches: pd.DataFrame, now: pd.Timestamp, limit: int = 12) -> None:
    """Mostra os próximos jogos e quantos minutos faltam, para depurar horário."""
    if matches.empty or "kickoff_at" not in matches.columns:
        print("Não há jogos para listar.")
        return

    rows = []
    for _, row in matches.iterrows():
        try:
            kickoff = parse_kickoff_datetime(row.get("kickoff_at"))
        except Exception:
            continue
        minutes_to = (kickoff - now).total_seconds() / 60.0
        if minutes_to >= -180:
            rows.append(
                {
                    "match_id": row.get("match_id", ""),
                    "jogo": f"{row.get('home_team', '')} x {row.get('away_team', '')}",
                    "kickoff_brt": kickoff.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "minutos_para_o_jogo": round(minutes_to, 1),
                }
            )

    if not rows:
        print("Não encontrei próximos jogos a partir do horário usado.")
        return

    view = pd.DataFrame(rows).sort_values("minutos_para_o_jogo").head(limit)
    print("\nPróximos jogos detectados pelo script:")
    print(view.to_string(index=False))


# ============================================================
# TABELA PALPITES POR JOGO
# ============================================================


def build_match_mode_row(match_predictions: pd.DataFrame, match: dict[str, Any]) -> dict[str, str] | None:
    """Calcula a Moda Kapitalo dos palpites do jogo."""
    if match_predictions is None or match_predictions.empty:
        return None

    required_cols = {"home_goals", "away_goals"}
    if not required_cols.issubset(set(match_predictions.columns)):
        return None

    valid = match_predictions.copy()
    valid["home_goals_num"] = pd.to_numeric(valid["home_goals"], errors="coerce")
    valid["away_goals_num"] = pd.to_numeric(valid["away_goals"], errors="coerce")
    valid = valid.dropna(subset=["home_goals_num", "away_goals_num"])

    if valid.empty:
        return None

    valid["home_goals_num"] = valid["home_goals_num"].astype(int)
    valid["away_goals_num"] = valid["away_goals_num"].astype(int)

    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    stage = match.get("stage", "")

    counts = (
        valid.groupby(["home_goals_num", "away_goals_num"], as_index=False)
        .size()
        .rename(columns={"size": "qtd"})
        .sort_values(["qtd", "home_goals_num", "away_goals_num"], ascending=[False, True, True])
        .reset_index(drop=True)
    )

    if counts.empty:
        return None

    max_qtd = int(counts.iloc[0]["qtd"])
    modes = counts[counts["qtd"] == max_qtd].copy()

    score_labels = [
        f"{home_team} {int(row.home_goals_num)} x {int(row.away_goals_num)} {away_team}"
        for row in modes.itertuples(index=False)
    ]
    palpite_label = score_labels[0] if len(score_labels) == 1 else " / ".join(score_labels)

    if is_group_stage(stage):
        advancing_label = "—"
    else:
        advancing_options = set()
        for row in modes.itertuples(index=False):
            home_goals = int(row.home_goals_num)
            away_goals = int(row.away_goals_num)
            if home_goals > away_goals:
                advancing_options.add(str(home_team))
            elif away_goals > home_goals:
                advancing_options.add(str(away_team))
            else:
                advancing_options.add("Empate")

        if len(advancing_options) == 1:
            only_option = next(iter(advancing_options))
            advancing_label = "Empate modal" if only_option == "Empate" else only_option
        else:
            advancing_label = "Múltiplos"

    return {
        "Participante": "Moda Kapitalo",
        "Palpite": palpite_label,
        "Classificado": advancing_label,
    }


def build_match_predictions_table(
    match_id: str,
    match: dict[str, Any],
    profiles: pd.DataFrame,
    predictions: pd.DataFrame,
    prediction_filter: str = "all",
    exclude_users: set[str] | None = None,
) -> pd.DataFrame:
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    stage = match.get("stage", "")
    rows: list[dict[str, str]] = []
    exclude_users = exclude_users or set()

    if profiles.empty:
        return pd.DataFrame(columns=["Participante", "Palpite", "Classificado"])

    if predictions.empty:
        predictions = pd.DataFrame(columns=["user_id", "match_id", "home_goals", "away_goals", "advancing_team"])

    match_predictions = (
        predictions[predictions["match_id"].astype(str) == str(match_id)].copy()
        if "match_id" in predictions.columns
        else pd.DataFrame()
    )

    users = profiles.copy()
    if "username" in users.columns:
        users["username_norm"] = users["username"].apply(normalize_username)
        users = users[~users["username_norm"].isin(exclude_users)].copy()
        users = users.sort_values("username")

    for _, user in users.iterrows():
        user_id = user.get("id")
        username = str(user.get("username", "") or "")
        user_pred = (
            match_predictions[match_predictions["user_id"] == user_id]
            if not match_predictions.empty and "user_id" in match_predictions.columns
            else pd.DataFrame()
        )

        if user_pred.empty:
            rows.append({"Participante": username, "Palpite": "Pendente", "Classificado": "—" if is_group_stage(stage) else "Pendente"})
            continue

        pred = user_pred.iloc[0]
        home_goals = safe_int(pred.get("home_goals"))
        away_goals = safe_int(pred.get("away_goals"))
        advancing_team = pred.get("advancing_team") or ""

        if is_knockout_stage(stage) and not advancing_team:
            if home_goals > away_goals:
                advancing_team = home_team
            elif away_goals > home_goals:
                advancing_team = away_team
            else:
                advancing_team = "Não informado"

        rows.append(
            {
                "Participante": username,
                "Palpite": f"{home_team} {home_goals} x {away_goals} {away_team}",
                "Classificado": "—" if is_group_stage(stage) else str(advancing_team),
            }
        )

    mode_row = build_match_mode_row(match_predictions, match)
    if mode_row is not None and prediction_filter not in {"pending", "pendentes", "only_pending", "somente_pendentes"}:
        rows.append(mode_row)

    out = pd.DataFrame(rows, columns=["Participante", "Palpite", "Classificado"])
    if out.empty:
        return out

    prediction_filter = str(prediction_filter or "all").strip().lower()
    if prediction_filter in {"complete", "completed", "only_complete", "somente_com_palpite"}:
        out = out[out["Palpite"] != "Pendente"].copy()
    elif prediction_filter in {"pending", "pendentes", "only_pending", "somente_pendentes"}:
        out = out[out["Palpite"] == "Pendente"].copy()

    return out.reset_index(drop=True)


def build_match_chat_text(match: dict[str, Any]) -> str:
    stage = match.get("stage", "")
    group_name = match.get("group_name", "")
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    kickoff_text = format_kickoff(match.get("kickoff_at"))
    group_part = f" • Grupo {group_name}" if group_name and str(group_name).lower() != "nan" else ""

    return (
        "🏆 Kapitalo Cup\n\n"
        f"Palpites para: {home_team} x {away_team}\n"
        f"Fase: {stage}{group_part}\n"
        f"Horário: {kickoff_text}\n\n"
        "Segue o consolidado dos palpites dos participantes."
    )


# ============================================================
# DISTRIBUIÇÃO DE PLACARES
# ============================================================


def build_match_score_distribution_table(match_id: str, match: dict[str, Any], predictions: pd.DataFrame) -> pd.DataFrame:
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")

    if predictions.empty or "match_id" not in predictions.columns:
        return pd.DataFrame(columns=["Placar", "Qtd", "%"])

    pred = predictions[predictions["match_id"].astype(str) == str(match_id)].copy()
    if pred.empty:
        return pd.DataFrame(columns=["Placar", "Qtd", "%"])

    pred["home_goals"] = pd.to_numeric(pred.get("home_goals"), errors="coerce")
    pred["away_goals"] = pd.to_numeric(pred.get("away_goals"), errors="coerce")
    pred = pred.dropna(subset=["home_goals", "away_goals"])
    if pred.empty:
        return pd.DataFrame(columns=["Placar", "Qtd", "%"])

    pred["home_goals"] = pred["home_goals"].astype(int)
    pred["away_goals"] = pred["away_goals"].astype(int)
    pred["Placar"] = pred.apply(
        lambda row: f"{home_team} {int(row['home_goals'])} x {int(row['away_goals'])} {away_team}",
        axis=1,
    )

    total = len(pred)
    out = (
        pred.groupby(["Placar", "home_goals", "away_goals"], as_index=False)
        .size()
        .rename(columns={"size": "Qtd"})
        .sort_values(["Qtd", "home_goals", "away_goals"], ascending=[False, True, True])
        .reset_index(drop=True)
    )
    out["%"] = (out["Qtd"] / total * 100).round(1).astype(str) + "%"
    return out[["Placar", "Qtd", "%"]]


def build_match_distribution_chat_text(match: dict[str, Any]) -> str:
    return (
        "🏆 Kapitalo Cup\n\n"
        f"Distribuição dos palpites: {match.get('home_team', '')} x {match.get('away_team', '')}\n"
        f"Fase: {match.get('stage', '')}\n"
        f"Horário: {format_kickoff(match.get('kickoff_at'))}\n\n"
        "O gráfico mostra quantas pessoas escolheram cada placar. "
        "Cada placar está escrito com os nomes dos times para evitar ambiguidade."
    )


# ============================================================
# PNGS COM O MESMO DESIGN DO APP
# ============================================================


def dataframe_to_png(
    df: pd.DataFrame,
    title: str = "",
    subtitle: str = "",
    footer: str = "",
    max_rows: int | None = None,
    max_fig_height: float = 34,
) -> str:
    """Gera PNG no mesmo estilo da tabela do app, centralizado e sem reticências quando max_rows=None.

    Ajuste importante: a versão anterior salvava com bbox_inches="tight" e o rodapé longo
    podia alargar o canvas para a direita, deixando a tabela visualmente deslocada para a
    esquerda no Google Chat. Aqui o canvas é fixo, o rodapé é quebrado em linhas e todo o
    conteúdo fica dentro do mesmo eixo centralizado.
    """
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError("matplotlib não instalado. Rode: pip install matplotlib") from exc

    table_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if table_df.empty:
        table_df = pd.DataFrame({"Mensagem": ["Sem dados para exibir."]})

    truncated = False
    if max_rows is not None and len(table_df) > int(max_rows):
        table_df = table_df.head(int(max_rows)).copy()
        truncated = True

    table_df = table_df.fillna("").astype(str)
    if truncated:
        table_df.loc[len(table_df)] = ["..." for _ in table_df.columns]

    n_rows, n_cols = table_df.shape
    title_text = str(title or "").strip()
    subtitle_text = str(subtitle or "").strip()
    footer_text = str(footer or "").strip()

    # Canvas proporcional à tabela, não ao rodapé. Isso evita a tabela "puxada" para um lado.
    fig_width = max(7.2, min(13.8, 1.85 * n_cols + 1.9))

    # Quebra o rodapé dentro da largura útil da figura para não expandir o bbox.
    footer_wrapped = ""
    if footer_text:
        # Aproximação: quanto mais larga a figura, mais caracteres cabem por linha.
        footer_width_chars = max(72, int(fig_width * 11.5))
        footer_wrapped = textwrap.fill(footer_text, width=footer_width_chars)

    footer_lines = footer_wrapped.count("\n") + 1 if footer_wrapped else 0
    title_block = (0.44 if title_text else 0.0) + (0.34 if subtitle_text else 0.0)
    footer_block = 0.28 * footer_lines if footer_wrapped else 0.0
    table_block = 0.285 * (n_rows + 1)
    fig_height = max(2.1, min(max_fig_height, table_block + title_block + footer_block + 0.55))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    y_cursor = 0.985
    if title_text:
        ax.text(
            0.5,
            y_cursor,
            title_text,
            ha="center",
            va="top",
            fontsize=12.2,
            fontweight="bold",
            transform=ax.transAxes,
        )
        y_cursor -= 0.035

    if subtitle_text:
        ax.text(
            0.5,
            y_cursor,
            subtitle_text,
            ha="center",
            va="top",
            fontsize=10.3,
            fontweight="bold",
            transform=ax.transAxes,
        )
        y_cursor -= 0.033

    footer_bottom = 0.018 if footer_wrapped else 0.0
    footer_area_height = 0.036 * footer_lines if footer_wrapped else 0.0
    table_bottom = footer_bottom + footer_area_height + (0.016 if footer_wrapped else 0.02)
    table_top = y_cursor - 0.018
    table_bbox_height = max(0.12, table_top - table_bottom)

    # Margens iguais nas laterais, para a tabela ficar centralizada mesmo no Chat.
    table_left = 0.035
    table_width = 0.93

    table = ax.table(
        cellText=table_df.values,
        colLabels=table_df.columns,
        cellLoc="center",
        colLoc="center",
        bbox=[table_left, table_bottom, table_width, table_bbox_height],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.6 if n_rows > 58 else 8.0 if n_rows > 42 else 8.6)

    participant_colors = {
        "lobo-guará": "#fff7d6",
        "lobo-guara": "#fff7d6",
        "mico-leão": "#fff7d6",
        "mico-leao": "#fff7d6",
        "claude fable 5": "#eef2ff",
        "moda kapitalo": "#f9e8ef",  # cor tema bem opaca
    }

    participant_col_idx = None
    for idx, col_name in enumerate(table_df.columns):
        if str(col_name).strip().casefold() in {"participante", "usuário", "usuario"}:
            participant_col_idx = idx
            break

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#d1d5db")
        cell.set_linewidth(0.55)
        cell.PAD = 0.035

        if row == 0:
            cell.set_facecolor(PRIMARY_COLOR)
            cell.set_text_props(color="white", weight="bold")
            continue

        row_color = "#f9fafb" if row % 2 == 0 else "#ffffff"
        if participant_col_idx is not None and row - 1 < len(table_df):
            participant = str(table_df.iloc[row - 1, participant_col_idx]).strip().casefold()
            if participant in participant_colors:
                row_color = participant_colors[participant]
        cell.set_facecolor(row_color)

    if footer_wrapped:
        ax.text(
            0.5,
            footer_bottom,
            footer_wrapped,
            ha="center",
            va="bottom",
            fontsize=8.2,
            color="#374151",
            transform=ax.transAxes,
            linespacing=1.15,
        )

    output = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    output.close()

    # Não usar bbox_inches="tight" aqui. O canvas fixo mantém título, tabela e rodapé alinhados.
    fig.savefig(output.name, dpi=190, facecolor="white", bbox_inches=None, pad_inches=0)
    plt.close(fig)
    return output.name

def distribution_chart_to_png(distribution_df: pd.DataFrame, match: dict[str, Any]) -> str:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError("matplotlib não instalado. Rode: pip install matplotlib") from exc

    chart_df = distribution_df.copy() if isinstance(distribution_df, pd.DataFrame) else pd.DataFrame()
    if chart_df.empty:
        chart_df = pd.DataFrame({"Placar": ["Sem palpites"], "Qtd": [0], "%": ["0%"]})

    chart_df = chart_df.sort_values("Qtd", ascending=True).tail(18)
    height = max(3.2, min(9.5, 0.42 * len(chart_df) + 1.5))
    fig, ax = plt.subplots(figsize=(11, height))

    ax.barh(chart_df["Placar"], chart_df["Qtd"], color=PRIMARY_COLOR, alpha=0.86)
    ax.set_xlabel("Quantidade de participantes")
    ax.set_ylabel("")
    title = f"Distribuição de palpites — {match.get('home_team', '')} x {match.get('away_team', '')}"
    subtitle = f"{match.get('stage', '')} • {format_kickoff(match.get('kickoff_at'))}"
    ax.set_title(f"{title}\n{subtitle}", fontweight="bold", pad=12)

    max_qtd = max([1] + [int(x) for x in chart_df["Qtd"].tolist()])
    for i, (_, row) in enumerate(chart_df.iterrows()):
        ax.text(int(row["Qtd"]) + max_qtd * 0.015, i, f"{row['Qtd']} ({row['%']})", va="center", fontsize=9)

    ax.set_xlim(0, max_qtd * 1.22)
    ax.grid(axis="x", alpha=0.22)
    fig.tight_layout(pad=0.7)

    output = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    output.close()
    fig.savefig(output.name, dpi=190, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    return output.name


# ============================================================
# GOOGLE CHAT
# ============================================================


def send_google_chat_image(textbody: str, image_path: str, space_id: str) -> dict[str, Any]:
    try:
        from googleapiclient.http import MediaFileUpload
    except Exception as exc:
        raise RuntimeError("Dependência google-api-python-client não instalada.") from exc

    service = get_chat_service()
    image_path_obj = Path(image_path)

    if not image_path_obj.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {image_path}")

    media = MediaFileUpload(str(image_path_obj), mimetype="image/png")
    attachment_uploaded = service.media().upload(
        parent=space_id,
        body={"filename": image_path_obj.name},
        media_body=media,
    ).execute()

    return service.spaces().messages().create(
        parent=space_id,
        body={"text": textbody, "attachment": [attachment_uploaded]},
    ).execute()


# ============================================================
# DEDUP / LOG DE ENVIO
# ============================================================


def ensure_reminder_table(client) -> None:
    try:
        client.table("chat_reminders_sent").select("id").limit(1).execute()
    except Exception as exc:
        raise RuntimeError(
            "A tabela public.chat_reminders_sent parece não existir. "
            "Rode o arquivo create_chat_reminders_sent_pre_match.sql no Supabase."
        ) from exc


def reminder_already_sent(client, match_id: str, reminder_type: str, minutes_before: int) -> bool:
    try:
        response = (
            client.table("chat_reminders_sent")
            .select("id")
            .eq("match_id", match_id)
            .eq("reminder_type", reminder_type)
            .eq("minutes_before", minutes_before)
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception:
        return False


def mark_reminder_sent(
    client,
    match: MatchInfo,
    reminder_type: str,
    minutes_before: int,
    payload: dict[str, Any],
) -> None:
    row = {
        "match_id": match.match_id,
        "reminder_type": reminder_type,
        "minutes_before": minutes_before,
        "sent_at": datetime.now(ZoneInfo(APP_TIMEZONE)).isoformat(timespec="seconds"),
        "payload": payload,
    }
    client.table("chat_reminders_sent").upsert(row, on_conflict="match_id,reminder_type,minutes_before").execute()


# ============================================================
# TESTE FAKE, SEM SUPABASE
# ============================================================


def build_fake_data(now: pd.Timestamp, minutes_before: int) -> tuple[dict[str, pd.DataFrame], list[MatchInfo]]:
    kickoff = now + timedelta(minutes=minutes_before)
    match = MatchInfo(
        match_id="TEST-FAKE-01",
        match_no=999,
        stage="Grupos",
        group_name="Teste",
        kickoff_at=kickoff,
        home_team="Mexico",
        away_team="South Africa",
        venue="Teste local",
    )

    profiles = pd.DataFrame(
        [
            {"id": "u1", "username": "alfredobinnie"},
            {"id": "u2", "username": "bfranco"},
            {"id": "u3", "username": "claude fable 5"},
            {"id": "u4", "username": "lobo-guará"},
            {"id": "u5", "username": "mico-leão"},
            {"id": "u6", "username": "admin"},
        ]
    )
    predictions = pd.DataFrame(
        [
            {"user_id": "u1", "match_id": match.match_id, "home_goals": 2, "away_goals": 0, "advancing_team": None},
            {"user_id": "u2", "match_id": match.match_id, "home_goals": 2, "away_goals": 0, "advancing_team": None},
            {"user_id": "u3", "match_id": match.match_id, "home_goals": 3, "away_goals": 1, "advancing_team": None},
            {"user_id": "u4", "match_id": match.match_id, "home_goals": 1, "away_goals": 2, "advancing_team": None},
            {"user_id": "u5", "match_id": match.match_id, "home_goals": 1, "away_goals": 1, "advancing_team": None},
        ]
    )
    matches = pd.DataFrame([match.to_dict()])
    return {"matches": matches, "profiles": profiles, "predictions": predictions}, [match]


# ============================================================
# EXECUÇÃO
# ============================================================


def parse_excluded_users(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {normalize_username(x) for x in raw.split(",") if normalize_username(x)}


def build_and_optionally_send_for_match(
    match: MatchInfo,
    data: dict[str, pd.DataFrame],
    args: argparse.Namespace,
    space_id: str,
    dry_run: bool,
) -> dict[str, Any]:
    match_dict = match.to_dict()
    profiles = data["profiles"]
    predictions = data["predictions"]
    exclude_users = parse_excluded_users(args.exclude_users)

    table_df = build_match_predictions_table(
        match_id=match.match_id,
        match=match_dict,
        profiles=profiles,
        predictions=predictions,
        prediction_filter=args.prediction_filter,
        exclude_users=exclude_users,
    )
    distribution_df = build_match_score_distribution_table(match.match_id, match_dict, predictions)

    title = f"Palpites — {match.home_team} x {match.away_team}"
    subtitle = f"{match.stage} • {format_kickoff(match.kickoff_at)}"
    footer = "Legenda: lobo-guará e mico-leão = palpites aleatórios; claude fable 5 = palpite da IA; Moda Kapitalo = placar mais frequente."

    table_image_path = dataframe_to_png(
        table_df,
        title=title,
        subtitle=subtitle,
        footer=footer,
        max_rows=None,          # importante: todos os palpites, sem reticências
        max_fig_height=32,
    )
    distribution_image_path = distribution_chart_to_png(distribution_df, match_dict)

    match_chat_text = build_match_chat_text(match_dict)
    distribution_chat_text = build_match_distribution_chat_text(match_dict)

    result = {
        "match_id": match.match_id,
        "label": f"{match.match_id} — {match.home_team} x {match.away_team} — {format_kickoff(match.kickoff_at)}",
        "table_rows": len(table_df),
        "distribution_rows": len(distribution_df),
        "table_image_path": table_image_path,
        "distribution_image_path": distribution_image_path,
        "sent_messages": [],
    }

    print("\n" + "=" * 90)
    print(result["label"])
    print(f"Linhas da tabela de palpites: {len(table_df)}")
    print(f"Linhas da distribuição: {len(distribution_df)}")
    print(f"Imagem tabela: {table_image_path}")
    print(f"Imagem distribuição: {distribution_image_path}")
    print("\nMensagem Palpites por jogo:")
    print(match_chat_text)
    print("\nMensagem Distribuição placares:")
    print(distribution_chat_text)

    if dry_run:
        print("DRY-RUN: nada foi enviado ao Google Chat.")
        return result

    if args.kind in {"both", "palpites"}:
        print(f"Enviando Palpites por jogo para {space_id}...")
        msg = send_google_chat_image(match_chat_text, table_image_path, space_id)
        result["sent_messages"].append({"kind": "palpites", "response": msg})

    if args.kind in {"both", "distribuicao"}:
        print(f"Enviando Distribuição placares para {space_id}...")
        msg = send_google_chat_image(distribution_chat_text, distribution_image_path, space_id)
        result["sent_messages"].append({"kind": "distribuicao", "response": msg})

    print("Envio concluído.")
    return result


def run(args: argparse.Namespace) -> int:
    dry_run = not args.send
    now = parse_now_arg(args.now)
    space_id = normalize_space_id(args.space)
    reminder_type = f"pre_match_{args.kind}"

    print(f"Agora usado no script: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Timezone oficial: {APP_TIMEZONE}")
    print(f"Modo: {'ENVIO REAL' if args.send else 'DRY-RUN'}")
    print(f"Space alvo: {space_id}")
    print(f"Tipo de envio: {args.kind}")
    if args.window_minutes is not None:
        effective_early = args.window_minutes
        effective_late = args.window_minutes
        effective_post_grace = 0
    else:
        effective_early = args.early_window_minutes
        effective_late = args.late_window_minutes
        effective_post_grace = args.post_kickoff_grace_minutes

    print(f"Minutos antes nominal: {args.minutes_before}")
    print(f"Janela robusta: de {args.minutes_before + effective_early} min antes até {max(args.minutes_before - effective_late, -effective_post_grace)} min antes do kickoff")
    print(f"Timezone oficial: {APP_TIMEZONE} | Timezone de kickoff naive: {get_kickoff_source_timezone()}")
    if args.exclude_users:
        print(f"Usuários excluídos: {args.exclude_users}")

    client = None

    if args.fake_game:
        data, target_matches = build_fake_data(now, args.minutes_before)
        print("Usando jogo fake em memória. O Supabase não será lido nem alterado.")
    else:
        client = get_supabase_client()
        if not dry_run:
            ensure_reminder_table(client)

        data = load_supabase_data(client)
        if args.list_next:
            print_next_matches(data["matches"], now=now, limit=args.list_next)

        target_matches = get_target_matches(
            matches=data["matches"],
            now=now,
            minutes_before=args.minutes_before,
            early_window_minutes=effective_early,
            late_window_minutes=effective_late,
            post_kickoff_grace_minutes=effective_post_grace,
            match_id=args.match_id,
        )

    print(f"Jogos candidatos: {len(target_matches)}")
    if not target_matches:
        print("Nenhum jogo encontrado para esta janela.")
        if not args.fake_game and client is not None and not args.list_next:
            print_next_matches(data["matches"], now=now, limit=8)
        return 0

    sent_count = 0
    results: list[dict[str, Any]] = []

    for match in target_matches:
        if not args.fake_game and client is not None and not args.force and not args.match_id:
            if reminder_already_sent(client, match.match_id, reminder_type, args.minutes_before):
                print(f"Pulando {match.match_id}: já enviado. Use --force para reenviar.")
                continue

        result = build_and_optionally_send_for_match(match, data, args, space_id, dry_run)
        results.append(result)

        if not dry_run:
            sent_count += 1
            if not args.fake_game and client is not None:
                mark_reminder_sent(
                    client=client,
                    match=match,
                    reminder_type=reminder_type,
                    minutes_before=args.minutes_before,
                    payload={
                        "kind": args.kind,
                        "space_id": space_id,
                        "table_rows": result["table_rows"],
                        "distribution_rows": result["distribution_rows"],
                    },
                )
                print("Registro salvo em public.chat_reminders_sent.")

    print("\n" + "=" * 90)
    print(f"Jogos processados: {len(results)}")
    print(f"Envios reais realizados: {sent_count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Envia automaticamente Palpites por jogo e Distribuição placares no Google Chat.")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--send", action="store_true", help="Envia de verdade para o Google Chat.")
    mode.add_argument("--dry-run", action="store_true", help="Simula execução sem enviar. É o padrão.")

    parser.add_argument("--minutes-before", type=int, default=30, help="Quantos minutos antes do kickoff enviar.")
    parser.add_argument("--window-minutes", type=int, default=None, help="Compatibilidade: usa janela simétrica antiga ±N em torno de now + minutes-before.")
    parser.add_argument("--early-window-minutes", type=int, default=7, help="Quantos minutos antes dos 30min nominais o job pode enviar. Default: 7.")
    parser.add_argument("--late-window-minutes", type=int, default=30, help="Quantos minutos depois dos 30min nominais o job ainda pode enviar antes do kickoff. Default: 30.")
    parser.add_argument("--post-kickoff-grace-minutes", type=int, default=2, help="Tolerância em minutos depois do kickoff para não perder por atraso do GitHub Actions. Default: 2.")
    parser.add_argument("--list-next", type=int, default=0, help="Lista os próximos N jogos detectados e os minutos até o kickoff.")
    parser.add_argument("--now", type=str, default=None, help="Override de horário atual para teste. Ex: '2026-06-11 15:30:00'.")
    parser.add_argument("--match-id", type=str, default=None, help="Força um jogo específico, ignorando a janela de horário.")
    parser.add_argument("--force", action="store_true", help="Reenvia mesmo se já existir registro em chat_reminders_sent.")
    parser.add_argument("--space", type=str, default=None, help="Space do Google Chat. Aceita AAQ... ou spaces/AAQ...")
    parser.add_argument("--fake-game", action="store_true", help="Cria um jogo fake em memória para testar sem mexer no Supabase.")
    parser.add_argument("--kind", choices=["both", "palpites", "distribuicao"], default="both", help="Qual mensagem enviar.")
    parser.add_argument("--prediction-filter", choices=["all", "complete", "pending"], default="all", help="Filtro da tabela de palpites.")
    parser.add_argument("--exclude-users", type=str, default=None, help="Usuários a excluir, separados por vírgula. Default: não exclui ninguém.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
