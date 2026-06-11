from pathlib import Path
import base64
import io
import json
import re
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

from src.auth import create_user, login_user, logout
from src.db import fetch_df, get_client


# ============================================================
# CONFIGURAÇÃO
# ============================================================

APP_NAME = "Kapitalo Cup"
PRIMARY_COLOR = "#ba083a"
LOGO_PATH = Path("aux/Logo.png")
# Fallback global antigo, usado apenas se uma chave específica de fase não existir.
DEFAULT_PREDICTION_LOCK_AT = "2026-06-11 00:00:00"

# Prazos padrão por fase. Edite via .streamlit/secrets.toml.
# As datas abaixo são defaults operacionais; use as datas oficiais/definidas pelo bolão.
DEFAULT_STAGE_LOCKS = {
    "groups": "2026-06-11 00:00:00",
    "r32": "2026-06-28 00:00:00",
    "r16": "2026-07-04 00:00:00",
    "quarters": "2026-07-09 00:00:00",
    "semis": "2026-07-14 00:00:00",
    "third_place": "2026-07-18 00:00:00",
    "final": "2026-07-19 00:00:00",
    "extras": "2026-06-11 00:00:00",
}

STAGE_LOCK_SECRET_KEYS = {
    "groups": "PREDICTION_LOCK_GROUPS_AT",
    "r32": "PREDICTION_LOCK_R32_AT",
    "r16": "PREDICTION_LOCK_R16_AT",
    "quarters": "PREDICTION_LOCK_QUARTERS_AT",
    "semis": "PREDICTION_LOCK_SEMIS_AT",
    "third_place": "PREDICTION_LOCK_THIRD_PLACE_AT",
    "final": "PREDICTION_LOCK_FINAL_AT",
    "extras": "PREDICTION_LOCK_EXTRAS_AT",
}

# Timezone oficial do app. Datas sem timezone no secrets.toml são tratadas como horário de Brasília.
APP_TIMEZONE = "America/Sao_Paulo"


def now_app_tz() -> pd.Timestamp:
    """Agora no timezone oficial do bolão."""
    return pd.Timestamp(datetime.now(ZoneInfo(APP_TIMEZONE)))


def parse_app_datetime(value) -> pd.Timestamp:
    """Converte datas do app/secrets para America/Sao_Paulo.

    Se o valor vier sem timezone, ele é interpretado como horário de Brasília.
    Se vier com timezone explícito, é convertido para Brasília.
    """
    dt = pd.to_datetime(value)

    if pd.isna(dt):
        raise ValueError(f"Data inválida: {value}")

    if getattr(dt, "tzinfo", None) is None:
        return dt.tz_localize(APP_TIMEZONE)

    return dt.tz_convert(APP_TIMEZONE)


st.set_page_config(
    page_title=APP_NAME,
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    f"""
    <style>
    :root {{
        --primary: {PRIMARY_COLOR};
        --primary-dark: #92002d;
        --gold: #d8b45a;
        --green: #0f7a3b;
        --surface: #ffffff;
        --muted: #6b7280;
        --border: #e5e7eb;
        --bg: #f7f7f8;
    }}

    .stApp {{
        background: linear-gradient(180deg, #fafafa 0%, #f4f4f5 100%);
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #ba083a 0%, #9e0031 100%);
        border-right: 1px solid rgba(255,255,255,0.2);
    }}

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {{
        color: #ffffff !important;
    }}

    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {{
        color: #111827 !important;
        background-color: #ffffff !important;
        border-radius: 10px !important;
    }}

    [data-testid="stSidebar"] button,
    [data-testid="stSidebar"] button:disabled {{
        color: #111827 !important;
        background-color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.85) !important;
        border-radius: 10px !important;
        opacity: 1 !important;
        font-weight: 700 !important;
    }}

    [data-testid="stSidebar"] button p,
    [data-testid="stSidebar"] button span,
    [data-testid="stSidebar"] button div {{
        color: #111827 !important;
    }}

    [data-testid="stSidebar"] [data-baseweb="tab-list"] {{
        gap: 0.35rem;
    }}

    [data-testid="stSidebar"] [data-baseweb="tab"] {{
        background-color: rgba(255,255,255,0.92) !important;
        border: 1px solid rgba(255,255,255,0.85) !important;
        border-radius: 10px !important;
        padding: 8px 10px !important;
    }}

    [data-testid="stSidebar"] [data-baseweb="tab"] p,
    [data-testid="stSidebar"] [data-baseweb="tab"] span,
    [data-testid="stSidebar"] [data-baseweb="tab"] div {{
        color: #111827 !important;
        font-weight: 700 !important;
    }}

    [data-testid="stSidebar"] [role="radiogroup"] label,
    [data-testid="stSidebar"] [role="radiogroup"] label span,
    [data-testid="stSidebar"] [role="radiogroup"] label div,
    [data-testid="stSidebar"] [role="radiogroup"] p {{
        color: #ffffff !important;
        font-weight: 600 !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTextInputRootElement"] button svg {{
        color: #111827 !important;
        fill: #111827 !important;
    }}

    /* Main page elements */
    .hero-card {{
        background: linear-gradient(135deg, #c3043c 0%, #8d002d 70%);
        color: white;
        padding: 2rem;
        border-radius: 26px;
        box-shadow: 0 20px 45px rgba(195,4,60,0.24);
        margin-bottom: 1.25rem;
        border: 1px solid rgba(255,255,255,0.22);
    }}

    .hero-title {{
        font-size: 2.25rem;
        line-height: 1.1;
        font-weight: 900;
        margin-bottom: 0.35rem;
    }}

    .hero-subtitle {{
        font-size: 1rem;
        opacity: 0.92;
        margin-bottom: 0;
    }}

    .section-card {{
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 22px;
        padding: 1.25rem;
        box-shadow: 0 10px 28px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }}

    .match-card {{
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 1rem 1rem 0.85rem 1rem;
        box-shadow: 0 8px 22px rgba(0,0,0,0.045);
        margin-bottom: 0.85rem;
    }}

    .match-title {{
        font-weight: 900;
        font-size: 1.05rem;
        margin-bottom: 0.2rem;
        color: #111827;
    }}

    .match-meta {{
        font-size: 0.85rem;
        color: #6b7280;
        margin-bottom: 0.75rem;
    }}

    .pill {{
        display: inline-block;
        padding: 0.25rem 0.65rem;
        border-radius: 999px;
        background: #f3f4f6;
        color: #374151;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid #e5e7eb;
    }}

    .pill-red {{
        background: #fff1f2;
        color: #be123c;
        border: 1px solid #fecdd3;
    }}

    .pill-green {{
        background: #ecfdf5;
        color: #047857;
        border: 1px solid #bbf7d0;
    }}

    .metric-box {{
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 8px 22px rgba(0,0,0,0.045);
    }}

    .metric-label {{
        color: #6b7280;
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}

    .metric-value {{
        color: #111827;
        font-size: 1.9rem;
        font-weight: 900;
        margin-top: 0.2rem;
    }}

    .rules-card {{
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 8px 22px rgba(0,0,0,0.045);
        height: 100%;
    }}

    .rules-card h3 {{
        color: #111827;
        font-size: 1.05rem;
        margin-bottom: 0.5rem;
    }}

    .rules-card p {{
        color: #4b5563;
        margin-bottom: 0.35rem;
    }}

    .sidebar-user-card {{
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.24);
        border-radius: 16px;
        padding: 0.8rem;
        margin: 0.75rem 0 1rem 0;
    }}

    .sidebar-user-card p {{
        margin: 0;
    }}

    div[data-testid="stNumberInput"] {{
        max-width: 150px;
    }}

    div[data-testid="stNumberInput"] input {{
        text-align: center;
        font-weight: 900;
        min-height: 38px !important;
    }}

    div[data-testid="stButton"] button {{
        min-height: 38px !important;
    }}

    div[data-testid="stDataFrame"] {{
        border-radius: 18px;
        overflow: hidden;
    }}

    .block-container {{
        padding-top: 2rem;
        padding-bottom: 3rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CACHE / DADOS
# ============================================================

SUPABASE_PAGE_SIZE = 1000

# Ordem estável para paginação. Sem uma ordenação fixa, páginas sucessivas
# podem ficar inconsistentes se a tabela mudar enquanto o app lê os dados.
DEFAULT_TABLE_ORDER_COLUMNS = {
    "profiles": ["username", "id"],
    "matches": ["match_no", "match_id"],
    "predictions": ["user_id", "match_id"],
    "actual_results": ["match_id"],
    "bonus_predictions": ["user_id"],
    "bonus_actuals": ["id"],
    "phase_predictions": ["user_id", "phase", "team"],
    "phase_actuals": ["phase", "team"],
    "debug_streamlit_writes": ["created_at", "id"],
}


def _apply_supabase_order(query, table_name: str, order_by: str | None):
    """Aplica ordenação compatível com paginação via range().

    O PostgREST/Supabase pode limitar respostas a 1.000 linhas. Para buscar
    todas as páginas, precisamos usar range() em blocos e, idealmente, uma
    ordenação estável.
    """
    order_columns = []

    if order_by:
        order_columns.append(order_by)

    for col in DEFAULT_TABLE_ORDER_COLUMNS.get(table_name, []):
        if col not in order_columns:
            order_columns.append(col)

    for col in order_columns:
        query = query.order(col)

    return query


def fetch_df_paginated(table_name: str, order_by: str | None = None, page_size: int = SUPABASE_PAGE_SIZE) -> pd.DataFrame:
    """Busca uma tabela inteira do Supabase, contornando o limite de 1.000 linhas.

    O fetch_df antigo pode trazer só a primeira página. Isso fazia a tela
    parecer "apagar" palpites quando predictions passava de 1.000 registros.
    Esta função usa .range(start, end) até receber uma página menor que o limite.
    """
    client = get_client()
    rows: list[dict] = []
    start = 0

    while True:
        end = start + page_size - 1

        query = client.table(table_name).select("*")
        query = _apply_supabase_order(query, table_name, order_by)
        response = query.range(start, end).execute()

        page_rows = response.data or []
        rows.extend(page_rows)

        if len(page_rows) < page_size:
            break

        start += page_size

        # Guarda contra loop infinito caso a API retorne comportamento inesperado.
        if start > 250_000:
            raise RuntimeError(
                f"Paginação interrompida em {table_name}: mais de 250.000 linhas.")

    return pd.DataFrame(rows)


@st.cache_data(ttl=300, show_spinner=False)
def cached_table(table_name: str, order_by: str | None = None) -> pd.DataFrame:
    try:
        return fetch_df_paginated(table_name, order_by=order_by)
    except Exception:
        # Fallback para manter compatibilidade se alguma tabela não aceitar a
        # ordenação padrão. Ainda assim, o caminho principal acima é o paginado.
        try:
            return fetch_df(table_name, order_by=order_by)
        except Exception:
            return pd.DataFrame()


def load_table_uncached(table_name: str, order_by: str | None = None) -> pd.DataFrame:
    """Leitura direta e paginada, sem cache. Útil logo depois de salvar."""
    try:
        return fetch_df_paginated(table_name, order_by=order_by)
    except Exception:
        return pd.DataFrame()


def clear_data_cache():
    cached_table.clear()
    if "calculate_ranking_cached" in globals():
        calculate_ranking_cached.clear()


def load_table(table_name: str, order_by: str | None = None) -> pd.DataFrame:
    return cached_table(table_name, order_by)


# ============================================================
# HELPERS
# ============================================================

def get_admin_user() -> str:
    try:
        return st.secrets.get("ADMIN_USER", "admin").strip().lower()
    except Exception:
        return "admin"


def is_admin() -> bool:
    username = st.session_state.get("username", "")
    return username.strip().lower() == get_admin_user()


def safe_int(value, default=0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except Exception:
        return default


def norm_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().lower()


def get_match_result_type(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def infer_advancing_team(home_team: str, away_team: str, home_goals, away_goals, selected_advancing: str | None = None) -> str | None:
    """Define classificado para jogos de mata-mata.

    Se houver vencedor no tempo regulamentar do palpite/resultado, ele passa.
    Se houver empate, usa a seleção escolhida manualmente.
    """
    if home_goals is None or away_goals is None:
        return selected_advancing or None

    hg = safe_int(home_goals)
    ag = safe_int(away_goals)

    if hg > ag:
        return home_team
    if ag > hg:
        return away_team

    selected = (selected_advancing or "").strip()
    return selected or None


def build_prediction_payloads_from_state(visible_prediction_rows: list[dict], user_id: str) -> tuple[list[str], list[dict]]:
    """Monta payloads de palpites a partir dos widgets visíveis na tela.

    Usado pelos botões de salvar todos. Valida placares vazios e,
    em mata-mata empatado, exige o classificado.
    """
    invalid_rows = []
    payload_rows = []

    for item in visible_prediction_rows:
        match_id = item["match_id"]
        home_key = f"pred_home_{match_id}"
        away_key = f"pred_away_{match_id}"
        adv_key = f"pred_adv_{match_id}"

        home_value = st.session_state.get(home_key)
        away_value = st.session_state.get(away_key)

        if home_value is None or away_value is None:
            invalid_rows.append(item["label"])
            continue

        final_advancing = None

        if is_knockout_stage(item.get("stage", "")):
            selected_advancing = st.session_state.get(adv_key)
            final_advancing = infer_advancing_team(
                item.get("home_team", ""),
                item.get("away_team", ""),
                home_value,
                away_value,
                selected_advancing,
            )

            if not final_advancing:
                invalid_rows.append(
                    f"{item['label']} — selecione o classificado")
                continue

        payload_rows.append(
            {
                "user_id": user_id,
                "match_id": match_id,
                "home_goals": int(home_value),
                "away_goals": int(away_value),
                "advancing_team": final_advancing,
            }
        )

    return invalid_rows, payload_rows


def save_prediction_payloads_or_show_errors(
    supabase,
    payload_rows: list[dict],
    invalid_rows: list[str],
    success_message: str,
) -> bool:
    """Salva vários palpites ou mostra exatamente o que falta preencher.

    Importante: quando há erro de validação, a página continua renderizando.
    Isso evita a sensação de que os palpites já digitados foram apagados.
    """
    if invalid_rows:
        st.error("Não foi possível salvar todos os palpites. Revise estes jogos:")
        st.dataframe(
            pd.DataFrame({"Jogos para revisar": invalid_rows}),
            use_container_width=True,
            hide_index=True,
        )
        return False

    if not payload_rows:
        st.warning("Não há jogos para salvar nesta tela.")
        return False

    try:
        supabase.table("predictions").upsert(
            payload_rows,
            on_conflict="user_id,match_id",
        ).execute()

        clear_data_cache()
        st.success(success_message)
        st.rerun()
        return True

    except Exception as exc:
        st.error(f"Erro ao salvar todos os palpites: {exc}")
        return False


def stage_points_for_match(stage: str) -> dict:
    """Pontuação por jogo na nova dinâmica.

    A classificação por fase não é mais escolhida em uma tela separada.
    Em mata-mata, o classificado vem do próprio palpite do jogo.
    """
    stage = norm_text(stage)

    if "grupo" in stage or "group" in stage or "primeira" in stage:
        return {"result": 7, "exact": 7, "qualified": 0}

    if (
        "dezesseis" in stage
        or "16 avos" in stage
        or "16avos" in stage
        or "round of 32" in stage
        or "r32" in stage
        or "32" in stage
    ):
        return {"result": 10, "exact": 10, "qualified": 10}

    if (
        "oitavas" in stage
        or "8 avos" in stage
        or "8avos" in stage
        or "round of 16" in stage
        or "r16" in stage
    ):
        return {"result": 12, "exact": 12, "qualified": 12}

    if "quartas" in stage or "quarter" in stage:
        return {"result": 15, "exact": 15, "qualified": 15}

    if "semi" in stage:
        return {"result": 20, "exact": 20, "qualified": 20}

    if "3" in stage or "terceiro" in stage or "third" in stage:
        return {"result": 15, "exact": 15, "qualified": 15}

    if "final" in stage:
        return {"result": 25, "exact": 25, "qualified": 25}

    return {"result": 0, "exact": 0, "qualified": 0}


def points_for_phase_prediction(phase: str) -> int:
    """Mantida por compatibilidade, mas classificações por fase não pontuam mais.

    A pontuação de classificado agora vem de predictions.advancing_team
    contra actual_results.advancing_team em cada jogo de mata-mata.
    """
    return 0


def get_all_teams(matches: pd.DataFrame) -> list[str]:
    if matches.empty:
        return []

    home = matches["home_team"].dropna().tolist(
    ) if "home_team" in matches.columns else []
    away = matches["away_team"].dropna().tolist(
    ) if "away_team" in matches.columns else []

    return sorted(set(home).union(set(away)))


def get_groups(matches: pd.DataFrame) -> list[str]:
    if matches.empty or "group_name" not in matches.columns:
        return []

    groups = matches["group_name"].dropna().unique().tolist()
    return sorted(groups)


def render_logo_sidebar():
    if LOGO_PATH.exists():
        logo_bytes = LOGO_PATH.read_bytes()
        logo_base64 = base64.b64encode(logo_bytes).decode()

        st.sidebar.markdown(
            f"""
            <div style="width:100%; margin:-1.2rem 0 1rem 0; padding:0; text-align:center;">
                <img src="data:image/png;base64,{logo_base64}"
                     style="width:100%; max-width:100%; display:block; margin:0 auto; border-radius:0;" />
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(f"## 🏆 {APP_NAME}")


def hero(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-title">{title}</div>
            <p class="hero-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_box(label: str, value: str):
    st.markdown(
        f"""
        <div class="metric-box">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_pill(text: str, kind: str = ""):
    class_name = "pill"
    if kind:
        class_name += f" pill-{kind}"

    st.markdown(
        f"""<span class="{class_name}">{text}</span>""",
        unsafe_allow_html=True,
    )


def get_stage_lock_key(stage_or_phase: str) -> str:
    """
    Converte o nome da fase em uma chave de prazo.
    Serve para jogos e para a aba Classificados e extras.
    """
    value = norm_text(stage_or_phase)

    if value in {"extras", "bonus", "campeao", "campeão", "artilheiro"}:
        return "extras"

    if is_group_stage(value):
        return "groups"

    if (
        "dezesseis" in value
        or "16 avos" in value
        or "16avos" in value
        or "round of 32" in value
        or "r32" in value
        or "32" in value
    ):
        return "r32"

    if (
        "oitavas" in value
        or "8 avos" in value
        or "8avos" in value
        or "round of 16" in value
        or "r16" in value
    ):
        return "r16"

    if "quartas" in value or "quarter" in value:
        return "quarters"

    if "semi" in value:
        return "semis"

    if "3" in value or "terceiro" in value or "third" in value:
        return "third_place"

    if "final" in value:
        return "final"

    return "groups"


def get_lock_label_from_key(lock_key: str) -> str:
    labels = {
        "groups": "Fase de grupos",
        "r32": "16-avos",
        "r16": "Oitavas",
        "quarters": "Quartas",
        "semis": "Semifinais",
        "third_place": "3º e 4º lugar",
        "final": "Final",
        "extras": "Extras",
    }
    return labels.get(lock_key, lock_key)


def get_stage_lock_at(stage_or_phase: str) -> pd.Timestamp:
    """
    Busca prazo específico por fase no secrets.toml.
    Se não existir, usa PREDICTION_LOCK_AT como fallback.
    Se também não existir, usa DEFAULT_STAGE_LOCKS.

    Datas sem timezone são interpretadas como horário de Brasília
    (America/Sao_Paulo), para evitar o servidor travar o bolão em UTC.
    """
    lock_key = get_stage_lock_key(stage_or_phase)
    secret_key = STAGE_LOCK_SECRET_KEYS.get(lock_key)
    default_value = DEFAULT_STAGE_LOCKS.get(
        lock_key, DEFAULT_PREDICTION_LOCK_AT)

    raw_value = default_value

    try:
        if secret_key and secret_key in st.secrets:
            raw_value = st.secrets.get(secret_key, default_value)
        else:
            raw_value = st.secrets.get("PREDICTION_LOCK_AT", default_value)
    except Exception:
        raw_value = default_value

    try:
        return parse_app_datetime(raw_value)
    except Exception:
        return parse_app_datetime(default_value)


def is_stage_locked(stage_or_phase: str) -> bool:
    return now_app_tz() >= get_stage_lock_at(stage_or_phase)


def stage_lock_text(stage_or_phase: str) -> str:
    return get_stage_lock_at(stage_or_phase).strftime("%d/%m/%Y %H:%M")


def get_prediction_lock_at() -> pd.Timestamp:
    """
    Compatibilidade com versões anteriores.
    Usa o prazo da fase de grupos.
    """
    return get_stage_lock_at("groups")


def is_prediction_locked() -> bool:
    """
    Compatibilidade com versões anteriores.
    Usa o prazo da fase de grupos.
    """
    return is_stage_locked("groups")


def prediction_lock_text() -> str:
    """
    Compatibilidade com versões anteriores.
    Usa o prazo da fase de grupos.
    """
    return stage_lock_text("groups")


def next_open_lock_info() -> tuple[str, pd.Timestamp] | None:
    now = now_app_tz()
    future_rows = []

    for lock_key in DEFAULT_STAGE_LOCKS:
        lock_at = get_stage_lock_at(lock_key)
        if lock_at > now:
            future_rows.append((lock_key, lock_at))

    if not future_rows:
        return None

    return sorted(future_rows, key=lambda item: item[1])[0]


def build_lock_schedule_df() -> pd.DataFrame:
    now = now_app_tz()
    rows = []

    for lock_key in ["groups", "r32", "r16", "quarters", "semis", "third_place", "final", "extras"]:
        lock_at = get_stage_lock_at(lock_key)
        locked = now >= lock_at
        rows.append(
            {
                "Fase": get_lock_label_from_key(lock_key),
                "Chave no secrets.toml": STAGE_LOCK_SECRET_KEYS.get(lock_key, ""),
                "Prazo": lock_at.strftime("%d/%m/%Y %H:%M"),
                "Status": "Travado" if locked else "Aberto",
            }
        )

    return pd.DataFrame(rows)


def render_stage_lock_message(stage_or_phase: str, label: str | None = None):
    label = label or get_lock_label_from_key(
        get_stage_lock_key(stage_or_phase))
    lock_at = stage_lock_text(stage_or_phase)

    if is_stage_locked(stage_or_phase):
        st.warning(
            f"{label}: prazo encerrado em {lock_at}. Você ainda pode consultar e exportar previsões.")
    else:
        st.success(f"{label}: aberto para cadastro/alteração até {lock_at}.")


def sanitize_sheet_name(name: str) -> str:
    clean = re.sub(r"[\[\]\:\*\?\/\\]", "_", str(name))
    clean = clean.strip() or "usuario"
    return clean[:31]


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


def format_kickoff(value) -> str:
    """Formata kickoff_at como horário do Brasil/São Paulo.

    A coluna kickoff_at está sendo tratada como timestamp local do Brasil,
    sem conversão adicional de timezone.
    """
    if value is None or pd.isna(value) or str(value).strip() == "":
        return "Horário a definir"

    dt = pd.to_datetime(value, errors="coerce")

    if pd.isna(dt):
        return "Horário a definir"

    return dt.strftime("%d/%m/%Y %H:%M")


def sort_matches_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Ordena jogos por horário de realização e usa match_no como desempate."""
    if df is None or df.empty:
        return df

    out = df.copy()

    if "kickoff_at" in out.columns:
        out["kickoff_sort"] = pd.to_datetime(
            out["kickoff_at"], errors="coerce")
    else:
        out["kickoff_sort"] = pd.NaT

    sort_cols = ["kickoff_sort"]
    ascending = [True]

    if "match_no" in out.columns:
        sort_cols.append("match_no")
        ascending.append(True)

    out = out.sort_values(sort_cols, ascending=ascending, na_position="last")

    return out.drop(columns=["kickoff_sort"], errors="ignore")


def create_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        wrote_any = False

        for sheet_name, df in sheets.items():
            safe_name = sanitize_sheet_name(sheet_name)
            table = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
            table.to_excel(writer, index=False, sheet_name=safe_name)
            wrote_any = True

        if not wrote_any:
            pd.DataFrame({"Mensagem": ["Sem dados para exportar."]}).to_excel(
                writer,
                index=False,
                sheet_name="Sem dados",
            )

    output.seek(0)
    return output.getvalue()


def build_user_prediction_export(user_id: str) -> bytes:
    matches = sort_matches_for_display(
        load_table("matches", order_by="match_no"))
    predictions = load_table("predictions")
    bonus_predictions = load_table("bonus_predictions")

    if not predictions.empty and "user_id" in predictions.columns:
        user_predictions = predictions[predictions["user_id"] == user_id].copy(
        )
    else:
        user_predictions = pd.DataFrame()

    if not user_predictions.empty and not matches.empty:
        match_cols = [
            col
            for col in ["match_id", "match_no", "stage", "group_name", "home_team", "away_team", "kickoff_at", "venue"]
            if col in matches.columns
        ]

        jogos = user_predictions.merge(
            matches[match_cols],
            on="match_id",
            how="left",
        )
        jogos = sort_matches_for_display(jogos)

        if "kickoff_at" in jogos.columns:
            jogos["Horário"] = jogos["kickoff_at"].apply(format_kickoff)

        ordered_cols = [
            col
            for col in [
                "match_no",
                "stage",
                "group_name",
                "Horário",
                "home_team",
                "away_team",
                "home_goals",
                "away_goals",
                "advancing_team",
                "updated_at",
                "match_id",
                "kickoff_at",
                "venue",
            ]
            if col in jogos.columns
        ]
        jogos = jogos[ordered_cols]
    else:
        jogos = pd.DataFrame(
            columns=[
                "match_no",
                "stage",
                "group_name",
                "Horário",
                "home_team",
                "away_team",
                "home_goals",
                "away_goals",
                "advancing_team",
                "updated_at",
                "match_id",
            ]
        )

    if not bonus_predictions.empty and "user_id" in bonus_predictions.columns:
        extras = bonus_predictions[bonus_predictions["user_id"] == user_id].copy(
        )
    else:
        extras = pd.DataFrame(columns=["champion", "top_scorer"])

    pending_matches, pending_extras = build_missing_items_for_user(user_id)

    return create_excel_bytes(
        {
            "Palpites jogos": jogos,
            "Extras": extras,
            "Pendencias jogos": pending_matches,
            "Pendencias extras": pending_extras,
        }
    )


def build_all_users_predictions_export() -> bytes:
    profiles = load_table("profiles")
    matches = sort_matches_for_display(
        load_table("matches", order_by="match_no"))
    predictions = load_table("predictions")
    bonus_predictions = load_table("bonus_predictions")

    sheets = {}

    if profiles.empty:
        return create_excel_bytes({"Sem usuarios": pd.DataFrame({"Mensagem": ["Nenhum usuário cadastrado."]})})

    for _, user in profiles.sort_values("username").iterrows():
        user_id = user["id"]
        username = user["username"]

        rows = []

        if not predictions.empty and "user_id" in predictions.columns:
            user_pred = predictions[predictions["user_id"] == user_id].copy()

            if not user_pred.empty and not matches.empty:
                match_cols = [
                    col
                    for col in ["match_id", "match_no", "stage", "group_name", "home_team", "away_team", "kickoff_at"]
                    if col in matches.columns
                ]
                user_pred = user_pred.merge(
                    matches[match_cols], on="match_id", how="left")
                user_pred = sort_matches_for_display(user_pred)

                for _, row in user_pred.iterrows():
                    rows.append(
                        {
                            "Tipo": "Jogo",
                            "Fase": row.get("stage", ""),
                            "Grupo": row.get("group_name", ""),
                            "Horário": format_kickoff(row.get("kickoff_at")),
                            "Jogo": f"{row.get('home_team', '')} x {row.get('away_team', '')}",
                            "Gols casa": row.get("home_goals", ""),
                            "Gols fora": row.get("away_goals", ""),
                            "Classificado/Campeão": row.get("advancing_team", ""),
                            "Artilheiro": "",
                            "Atualizado em": row.get("updated_at", ""),
                            "match_id": row.get("match_id", ""),
                            "match_no": row.get("match_no", ""),
                        }
                    )

        if not bonus_predictions.empty and "user_id" in bonus_predictions.columns:
            user_bonus = bonus_predictions[bonus_predictions["user_id"] == user_id].copy(
            )

            for _, row in user_bonus.iterrows():
                rows.append(
                    {
                        "Tipo": "Extras",
                        "Fase": "Extras",
                        "Grupo": "",
                        "Horário": "",
                        "Jogo": "",
                        "Gols casa": "",
                        "Gols fora": "",
                        "Classificado/Campeão": row.get("champion", ""),
                        "Artilheiro": row.get("top_scorer", ""),
                        "Atualizado em": row.get("updated_at", ""),
                        "match_id": "",
                        "match_no": "",
                    }
                )

        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(
                {"Mensagem": ["Usuário ainda não cadastrou previsões."]})

        sheets[str(username)] = df

    return create_excel_bytes(sheets)


def build_missing_items_for_user(user_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    matches = sort_matches_for_display(
        load_table("matches", order_by="match_no"))
    predictions = load_table("predictions")
    bonus_predictions = load_table("bonus_predictions")

    if matches.empty:
        pending_matches = pd.DataFrame(
            columns=["Fase", "Grupo", "Horário", "Jogo", "match_id"])
    else:
        pred_ids = set()

        if not predictions.empty and "user_id" in predictions.columns and "match_id" in predictions.columns:
            pred_ids = set(
                predictions[predictions["user_id"] == user_id]["match_id"]
                .astype(str)
                .tolist()
            )

        missing = matches[~matches["match_id"].astype(
            str).isin(pred_ids)].copy()
        missing = sort_matches_for_display(missing)

        pending_matches = pd.DataFrame(
            {
                "Fase": missing["stage"] if "stage" in missing.columns else "",
                "Grupo": missing["group_name"] if "group_name" in missing.columns else "",
                "Horário": missing.apply(lambda row: format_kickoff(row.get("kickoff_at")), axis=1),
                "Jogo": missing.apply(
                    lambda row: f"{row.get('home_team', '')} x {row.get('away_team', '')}",
                    axis=1,
                ),
                "Prazo": missing.apply(lambda row: stage_lock_text(row.get("stage", "")), axis=1),
                "Status prazo": missing.apply(lambda row: "Travado" if is_stage_locked(row.get("stage", "")) else "Aberto", axis=1),
                "match_id": missing["match_id"] if "match_id" in missing.columns else "",
            }
        )

        if "match_no" in missing.columns:
            pending_matches.insert(0, "Nº", missing["match_no"].values)

    extras_rows = []

    if not bonus_predictions.empty and "user_id" in bonus_predictions.columns:
        user_bonus = bonus_predictions[bonus_predictions["user_id"] == user_id].copy(
        )
    else:
        user_bonus = pd.DataFrame()

    champion_ok = False
    scorer_ok = False

    if not user_bonus.empty:
        champion_ok = bool(
            str(user_bonus.iloc[0].get("champion") or "").strip())
        scorer_ok = bool(
            str(user_bonus.iloc[0].get("top_scorer") or "").strip())

    if not champion_ok:
        extras_rows.append({
            "Tipo": "Extra",
            "Item": "Campeão",
            "Status": "Pendente",
            "Prazo": stage_lock_text("extras"),
            "Status prazo": "Travado" if is_stage_locked("extras") else "Aberto",
        })

    if not scorer_ok:
        extras_rows.append({
            "Tipo": "Extra",
            "Item": "Artilheiro",
            "Status": "Pendente",
            "Prazo": stage_lock_text("extras"),
            "Status prazo": "Travado" if is_stage_locked("extras") else "Aberto",
        })

    pending_extras = pd.DataFrame(extras_rows)

    return pending_matches.reset_index(drop=True), pending_extras.reset_index(drop=True)


def simulate_group_table(group_matches: pd.DataFrame, user_predictions: pd.DataFrame) -> pd.DataFrame:
    """Simula a classificação do grupo sempre com todos os times.

    Mesmo quando ainda existem jogos sem palpite, a tabela aparece completa,
    com os times zerados até que os resultados sejam preenchidos.
    """
    if group_matches is None or group_matches.empty:
        return pd.DataFrame(columns=["Pos", "Seleção", "J", "V", "E", "D", "GP", "GC", "SG", "Pts"])

    teams = sorted(
        set(group_matches["home_team"].dropna().tolist()).union(
            set(group_matches["away_team"].dropna().tolist())
        )
    )

    table = {
        team: {
            "Seleção": team,
            "J": 0,
            "V": 0,
            "E": 0,
            "D": 0,
            "GP": 0,
            "GC": 0,
            "SG": 0,
            "Pts": 0,
        }
        for team in teams
    }

    if user_predictions is not None and not user_predictions.empty:
        needed_cols = {"match_id", "home_goals", "away_goals"}
        if needed_cols.issubset(set(user_predictions.columns)):
            merged = group_matches.merge(
                user_predictions[["match_id", "home_goals", "away_goals"]],
                on="match_id",
                how="left",
            )
            merged = merged.dropna(subset=["home_goals", "away_goals"])

            for _, row in merged.iterrows():
                home = row["home_team"]
                away = row["away_team"]
                hg = safe_int(row["home_goals"])
                ag = safe_int(row["away_goals"])

                table[home]["J"] += 1
                table[away]["J"] += 1
                table[home]["GP"] += hg
                table[home]["GC"] += ag
                table[away]["GP"] += ag
                table[away]["GC"] += hg

                if hg > ag:
                    table[home]["V"] += 1
                    table[away]["D"] += 1
                    table[home]["Pts"] += 3
                elif hg < ag:
                    table[away]["V"] += 1
                    table[home]["D"] += 1
                    table[away]["Pts"] += 3
                else:
                    table[home]["E"] += 1
                    table[away]["E"] += 1
                    table[home]["Pts"] += 1
                    table[away]["Pts"] += 1

    df = pd.DataFrame(table.values())
    if df.empty:
        return pd.DataFrame(columns=["Pos", "Seleção", "J", "V", "E", "D", "GP", "GC", "SG", "Pts"])

    df["SG"] = df["GP"] - df["GC"]
    df = df.sort_values(
        ["Pts", "SG", "GP", "Seleção"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    df.insert(0, "Pos", df.index + 1)

    return df


def compact_group_table(df: pd.DataFrame) -> pd.DataFrame:
    """Tabela simulada menor para exibir no modo agrupado."""
    wanted_cols = ["Pos", "Seleção", "J", "V", "E", "D", "SG", "Pts"]

    if df is None or df.empty:
        return pd.DataFrame(columns=wanted_cols)

    out = df.copy()
    out = out.drop(columns=["GP", "GC"], errors="ignore")

    for col in wanted_cols:
        if col not in out.columns:
            out[col] = 0 if col not in {"Seleção"} else ""

    return out[wanted_cols]


def parse_score_input(value) -> int | None:
    """Converte o texto do input de gols para int ou None se estiver vazio/inválido."""
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None

    if not text.isdigit():
        return None

    number = int(text)
    if number < 0 or number > 20:
        return None

    return number


def group_table_from_widget_keys(group_matches: pd.DataFrame, match_ids: list[str]) -> pd.DataFrame:
    """Simula o grupo lendo diretamente os valores atuais dos widgets.

    Como os inputs ficam fora de st.form, a tabela é recalculada a cada edição
    e fica completa com todos os times do grupo.
    """
    pred_rows = []

    for match_id in match_ids:
        home_value = parse_score_input(
            st.session_state.get(f"grouped_home_{match_id}"))
        away_value = parse_score_input(
            st.session_state.get(f"grouped_away_{match_id}"))

        if home_value is None or away_value is None:
            continue

        pred_rows.append(
            {
                "match_id": match_id,
                "home_goals": home_value,
                "away_goals": away_value,
            }
        )

    return compact_group_table(simulate_group_table(group_matches, pd.DataFrame(pred_rows)))


# ============================================================
# GOOGLE CHAT / COMUNICAÇÕES
# ============================================================
GOOGLE_CHAT_SCOPE = "https://www.googleapis.com/auth/chat.messages.create"


def get_secret_json(secret_name: str) -> dict:
    """Lê um JSON salvo no st.secrets.

    Aceita tanto string TOML com JSON quanto objeto/dict do Streamlit.
    """
    try:
        raw_value = st.secrets.get(secret_name)
    except Exception:
        raw_value = None

    if not raw_value:
        return {}

    if isinstance(raw_value, str):
        return json.loads(raw_value)

    try:
        return json.loads(json.dumps(raw_value))
    except Exception:
        return dict(raw_value)


def normalize_google_token_json(token_data: dict, client_secret_data: dict | None = None) -> dict:
    """Normaliza o JSON de token para o formato esperado pelo google-auth."""
    token_data = dict(token_data or {})

    # Alguns exports trazem access_token em vez de token; outros trazem listas.
    if "token" not in token_data and "access_token" in token_data:
        token_data["token"] = token_data.pop("access_token")

    for key in ["token", "refresh_token", "client_id", "client_secret", "token_uri"]:
        if isinstance(token_data.get(key), list):
            token_data[key] = token_data[key][0] if token_data[key] else ""

    client_block = {}
    if client_secret_data:
        client_block = client_secret_data.get(
            "installed") or client_secret_data.get("web") or {}

    token_data.setdefault("token_uri", client_block.get(
        "token_uri", "https://oauth2.googleapis.com/token"))
    token_data.setdefault("client_id", client_block.get("client_id", ""))
    token_data.setdefault(
        "client_secret", client_block.get("client_secret", ""))
    token_data.setdefault("scopes", [GOOGLE_CHAT_SCOPE])

    return token_data


def google_chat_config_ok() -> tuple[bool, str]:
    missing = []

    for key in ["GOOGLE_CHAT_SPACE_ID", "GOOGLE_CHAT_CLIENT_SECRET_JSON", "GOOGLE_CHAT_TOKEN_JSON"]:
        try:
            value = st.secrets.get(key)
        except Exception:
            value = None

        if not value:
            missing.append(key)

    if missing:
        return False, "Faltam secrets: " + ", ".join(missing)

    return True, "Configuração encontrada."


def get_chat_service():
    """Cria serviço do Google Chat usando secrets do Streamlit."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.exceptions import RefreshError
    except Exception as exc:
        raise RuntimeError(
            "Dependências do Google Chat não instaladas. Adicione google-auth, "
            "google-auth-oauthlib e google-api-python-client ao requirements.txt."
        ) from exc

    client_secret_data = get_secret_json("GOOGLE_CHAT_CLIENT_SECRET_JSON")
    token_data = normalize_google_token_json(
        get_secret_json("GOOGLE_CHAT_TOKEN_JSON"),
        client_secret_data,
    )

    if not token_data.get("token") and not token_data.get("refresh_token"):
        raise RuntimeError(
            "GOOGLE_CHAT_TOKEN_JSON não tem token ou refresh_token válido.")

    creds = Credentials.from_authorized_user_info(
        token_data, [GOOGLE_CHAT_SCOPE])

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise RuntimeError(
                    "Token do Google Chat expirou e não conseguiu renovar. "
                    "Gere um novo GOOGLE_CHAT_TOKEN_JSON e atualize o Streamlit Secrets."
                ) from exc
        else:
            raise RuntimeError(
                "Credenciais do Google Chat inválidas. Gere um token OAuth localmente "
                "e atualize GOOGLE_CHAT_TOKEN_JSON no Streamlit Secrets."
            )

    return build("chat", "v1", credentials=creds)


def get_google_chat_space_id() -> str:
    try:
        return st.secrets.get("GOOGLE_CHAT_SPACE_ID", "spaces/AAQAwXXcclU")
    except Exception:
        return "spaces/AAQAwXXcclU"


def send_google_chat_file(textbody: str, file_path: str, filename: str | None = None, mimetype: str = "image/png"):
    try:
        from googleapiclient.http import MediaFileUpload
    except Exception as exc:
        raise RuntimeError(
            "Dependência google-api-python-client não instalada. Adicione ao requirements.txt."
        ) from exc

    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    if filename is None:
        filename = file_path_obj.name

    service = get_chat_service()
    space_id = get_google_chat_space_id()

    media = MediaFileUpload(str(file_path_obj), mimetype=mimetype)

    attachment_uploaded = service.media().upload(
        parent=space_id,
        body={"filename": filename},
        media_body=media,
    ).execute()

    service.spaces().messages().create(
        parent=space_id,
        body={
            "text": textbody,
            "attachment": [attachment_uploaded],
        },
    ).execute()


def send_google_chat_image(textbody: str, image_path: str):
    ext = Path(image_path).suffix.lower()

    if ext in [".jpg", ".jpeg"]:
        mimetype = "image/jpeg"
    elif ext == ".png":
        mimetype = "image/png"
    elif ext == ".gif":
        mimetype = "image/gif"
    elif ext == ".webp":
        mimetype = "image/webp"
    else:
        raise ValueError(f"Extensão de imagem não suportada: {ext}")

    send_google_chat_file(
        textbody=textbody,
        file_path=image_path,
        filename=Path(image_path).name,
        mimetype=mimetype,
    )


def dataframe_to_png(
    df: pd.DataFrame,
    title: str = "",
    subtitle: str = "",
    footer: str = "",
    highlight_participants: dict[str, str] | None = None,
    max_rows: int | None = 42,
    max_fig_height: float = 18,
) -> str:
    """Gera uma imagem PNG compacta e legível de uma tabela.

    O enquadramento foi ajustado para evitar o espaço branco grande que aparecia
    nas imagens enviadas ao Google Chat. Também permite destacar linhas por
    participante e adicionar um rodapé/legenda.
    """
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError(
            "matplotlib não instalado. Adicione matplotlib ao requirements.txt.") from exc

    table_df = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()

    if table_df.empty:
        table_df = pd.DataFrame({"Mensagem": ["Sem dados para exibir."]})

    # Por padrão, limita tabelas muito grandes. Quando max_rows=None,
    # a imagem inclui todas as linhas, sem inserir a linha de reticências.
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
    has_title = bool(title_text or subtitle_text)
    has_footer = bool(footer_text)

    # Enquadramento mais justo: altura baseada no número real de linhas,
    # sem centralizar a tabela no meio da figura.
    fig_width = max(6.8, min(15.5, 1.95 * n_cols + 1.4))
    title_height = 0.48 if title_text else 0
    subtitle_height = 0.32 if subtitle_text else 0
    footer_height = 0.36 if has_footer else 0
    table_height = 0.31 * (n_rows + 1)
    fig_height = max(1.7, min(max_fig_height, table_height + title_height + subtitle_height + footer_height + 0.34))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")

    y_top = 0.99
    if title_text:
        ax.text(
            0.5,
            y_top,
            title_text,
            ha="center",
            va="top",
            fontsize=12,
            fontweight="bold",
            transform=ax.transAxes,
        )
        y_top -= 0.045

    if subtitle_text:
        ax.text(
            0.5,
            y_top,
            subtitle_text,
            ha="center",
            va="top",
            fontsize=10.5,
            fontweight="bold",
            transform=ax.transAxes,
        )
        y_top -= 0.04

    table_bottom = 0.055 if has_footer else 0.012
    table_top = y_top - (0.018 if has_title else 0.004)
    table_bbox_height = max(0.1, table_top - table_bottom)

    table = ax.table(
        cellText=table_df.values,
        colLabels=table_df.columns,
        cellLoc="center",
        colLoc="center",
        bbox=[0.0, table_bottom, 1.0, table_bbox_height],
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8.2 if n_rows > 34 else 8.8)

    # Destaques leves por participante.
    # Cores mantidas discretas para não parecer alerta/erro.
    default_random_color = "#fff7d6"
    default_ai_color = "#eef2ff"
    default_median_color = "#f9e8ef"  # vinho bem leve, derivado da cor base do site
    participant_colors = {
        "lobo-guará": default_random_color,
        "lobo-guara": default_random_color,
        "mico-leão": default_random_color,
        "mico-leao": default_random_color,
        "claude fable 5": default_ai_color,
        "mediana kapitalo": default_median_color,
    }
    if highlight_participants:
        participant_colors.update({str(k).casefold(): v for k, v in highlight_participants.items()})

    participant_col_idx = None
    for idx, col_name in enumerate(table_df.columns):
        if str(col_name).strip().casefold() in {"participante", "usuário", "usuario"}:
            participant_col_idx = idx
            break

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#d1d5db")
        cell.set_linewidth(0.55)

        if row == 0:
            cell.set_facecolor("#ba083a")
            cell.set_text_props(color="white", weight="bold")
            continue

        row_color = "#f9fafb" if row % 2 == 0 else "#ffffff"

        if participant_col_idx is not None and row - 1 < len(table_df):
            participant = str(table_df.iloc[row - 1, participant_col_idx]).strip().casefold()
            if participant in participant_colors:
                row_color = participant_colors[participant]

        cell.set_facecolor(row_color)

    if has_footer:
        ax.text(
            0.0,
            0.012,
            footer_text,
            ha="left",
            va="bottom",
            fontsize=8.6,
            color="#374151",
            transform=ax.transAxes,
        )

    output = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    output.close()

    fig.savefig(output.name, dpi=190, bbox_inches="tight", pad_inches=0.025)
    plt.close(fig)

    return output.name


def format_median_goal(value) -> str:
    """Formata a mediana dos gols para a linha Mediana Kapitalo."""
    try:
        number = float(value)
    except Exception:
        return ""

    if number.is_integer():
        return str(int(number))

    # Em caso de mediana quebrada, mostra uma casa decimal com vírgula.
    return f"{number:.1f}".replace(".", ",")


def build_match_median_row(match_predictions: pd.DataFrame, match: dict) -> dict | None:
    """Calcula a mediana dos palpites de placar para um jogo.

    A linha é calculada somente com participantes que têm placar preenchido.
    Não grava nada no banco; é apenas uma linha sintética para análise/distribuição.
    """
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

    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    stage = match.get("stage", "")

    median_home = valid["home_goals_num"].median()
    median_away = valid["away_goals_num"].median()
    home_label = format_median_goal(median_home)
    away_label = format_median_goal(median_away)

    if is_group_stage(stage):
        advancing_label = "—"
    else:
        if median_home > median_away:
            advancing_label = home_team
        elif median_away > median_home:
            advancing_label = away_team
        else:
            advancing_label = "Empate mediano"

    return {
        "Participante": "Mediana Kapitalo",
        "Palpite": f"{home_team} {home_label} x {away_label} {away_team}",
        "Classificado": advancing_label,
    }

def build_match_predictions_table(match_id: str, prediction_filter: str = "all") -> tuple[pd.DataFrame, dict]:
    profiles = load_table("profiles")
    matches = load_table("matches", order_by="match_no")
    matches = sort_matches_for_display(matches)
    predictions = load_table("predictions")

    match_rows = matches[matches["match_id"].astype(str) == str(
        match_id)] if not matches.empty and "match_id" in matches.columns else pd.DataFrame()

    if match_rows.empty:
        return pd.DataFrame(), {}

    match = match_rows.iloc[0].to_dict()
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    stage = match.get("stage", "")

    rows = []

    if profiles.empty:
        return pd.DataFrame(columns=["Participante", "Palpite", "Classificado"]), match

    if predictions.empty:
        predictions = pd.DataFrame(columns=[
                                   "user_id", "match_id", "home_goals", "away_goals", "advancing_team", "updated_at"])

    match_predictions = predictions[predictions.get("match_id", pd.Series(dtype=str)).astype(
        str) == str(match_id)].copy() if "match_id" in predictions.columns else pd.DataFrame()

    for _, user in profiles.sort_values("username").iterrows():
        user_id = user.get("id")
        username = user.get("username", "")
        user_pred = match_predictions[match_predictions["user_id"] ==
                                      user_id] if not match_predictions.empty and "user_id" in match_predictions.columns else pd.DataFrame()

        if user_pred.empty:
            rows.append(
                {
                    "Participante": username,
                    "Palpite": "Pendente",
                    "Classificado": "—" if is_group_stage(stage) else "Pendente",
                }
            )
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
                "Classificado": "—" if is_group_stage(stage) else advancing_team,
            }
        )

    median_row = build_match_median_row(match_predictions, match)
    if median_row is not None:
        rows.append(median_row)

    out = pd.DataFrame(rows)

    if not out.empty:
        prediction_filter = str(prediction_filter or "all").strip().lower()
        if prediction_filter in {"complete", "completed", "only_complete", "somente_com_palpite"}:
            out = out[out["Palpite"] != "Pendente"].copy()
        elif prediction_filter in {"pending", "pendentes", "only_pending", "somente_pendentes"}:
            out = out[out["Palpite"] == "Pendente"].copy()

    return out.reset_index(drop=True), match


def build_match_chat_text(match: dict) -> str:
    stage = match.get("stage", "")
    group_name = match.get("group_name", "")
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")
    kickoff_text = format_kickoff(match.get("kickoff_at"))

    group_part = f" • Grupo {group_name}" if group_name else ""

    return (
        "🏆 Kapitalo Cup\n\n"
        f"Palpites para: {home_team} x {away_team}\n"
        f"Fase: {stage}{group_part}\n"
        f"Horário: {kickoff_text}\n\n"
        "Segue o consolidado dos palpites dos participantes."
    )


def build_ranking_chat_text() -> str:
    return (
        "🏆 Kapitalo Cup\n\n"
        "Ranking atualizado.\n\n"
        "Segue a classificação geral da Kapitalo Cup."
    )


def build_pending_predictions_summary_table() -> pd.DataFrame:
    """Tabela apenas com usuários que ainda têm jogos pendentes.

    Usuários com todos os placares preenchidos não aparecem na lista enviada
    para o Google Chat. Isso deixa a mensagem focada só em quem precisa agir.
    """
    profiles = load_table("profiles")
    matches = load_table("matches", order_by="match_no")
    predictions = load_table("predictions")

    total_matches = len(matches) if not matches.empty else 0

    columns = ["Usuário", "Jogos preenchidos",
               "Jogos pendentes", "Total de jogos"]
    if profiles.empty:
        return pd.DataFrame(columns=columns)

    rows = []
    for _, user in profiles.sort_values("username").iterrows():
        user_id = user.get("id")
        username = user.get("username", "")

        if not predictions.empty and {"user_id", "match_id"}.issubset(predictions.columns):
            filled = predictions[predictions["user_id"] ==
                                 user_id]["match_id"].astype(str).nunique()
        else:
            filled = 0

        pending = max(total_matches - int(filled), 0)

        # Só entram usuários pendentes. Quem completou todos os placares sai da imagem/lista.
        if pending <= 0 and total_matches > 0:
            continue

        rows.append(
            {
                "Usuário": username,
                "Jogos preenchidos": int(filled),
                "Jogos pendentes": pending,
                "Total de jogos": total_matches,
            }
        )

    out = pd.DataFrame(rows, columns=columns)
    if out.empty:
        return out

    return out.sort_values(["Jogos pendentes", "Usuário"], ascending=[False, True]).reset_index(drop=True)


def build_pending_extras_summary_table() -> pd.DataFrame:
    """Tabela apenas com usuários que ainda não completaram Campeão/Artilheiro."""
    profiles = load_table("profiles")
    bonus_predictions = load_table("bonus_predictions")

    columns = ["Usuário", "Campeão", "Artilheiro", "Pendências"]
    if profiles.empty:
        return pd.DataFrame(columns=columns)

    rows = []
    for _, user in profiles.sort_values("username").iterrows():
        user_id = user.get("id")
        username = user.get("username", "")

        champion = ""
        top_scorer = ""

        if not bonus_predictions.empty and "user_id" in bonus_predictions.columns:
            row = bonus_predictions[bonus_predictions["user_id"] == user_id]
            if not row.empty:
                champion = row.iloc[0].get("champion") or ""
                top_scorer = row.iloc[0].get("top_scorer") or ""

        missing_items = []
        if not str(champion).strip():
            missing_items.append("Campeão")
        if not str(top_scorer).strip():
            missing_items.append("Artilheiro")

        # Só entram usuários com algum extra pendente.
        if not missing_items:
            continue

        rows.append(
            {
                "Usuário": username,
                "Campeão": champion if str(champion).strip() else "Pendente",
                "Artilheiro": top_scorer if str(top_scorer).strip() else "Pendente",
                "Pendências": ", ".join(missing_items),
            }
        )

    out = pd.DataFrame(rows, columns=columns)
    if out.empty:
        return out

    return out.sort_values(["Pendências", "Usuário"], ascending=[False, True]).reset_index(drop=True)


def build_bonus_predictions_all_users_table() -> pd.DataFrame:
    """Tabela com campeão e artilheiro escolhidos por todos os usuários.

    Mantida para compatibilidade/consulta futura. Para mensagens de pendência,
    use build_pending_extras_summary_table().
    """
    profiles = load_table("profiles")
    bonus_predictions = load_table("bonus_predictions")

    if profiles.empty:
        return pd.DataFrame(columns=["Usuário", "Campeão", "Artilheiro", "Status"])

    rows = []
    for _, user in profiles.sort_values("username").iterrows():
        user_id = user.get("id")
        username = user.get("username", "")
        champion = ""
        top_scorer = ""
        updated_at = ""

        if not bonus_predictions.empty and "user_id" in bonus_predictions.columns:
            row = bonus_predictions[bonus_predictions["user_id"] == user_id]
            if not row.empty:
                champion = row.iloc[0].get("champion") or ""
                top_scorer = row.iloc[0].get("top_scorer") or ""
                updated_at = row.iloc[0].get("updated_at") or ""

        rows.append(
            {
                "Usuário": username,
                "Campeão": champion if str(champion).strip() else "Pendente",
                "Artilheiro": top_scorer if str(top_scorer).strip() else "Pendente",
                "Atualizado em": format_kickoff(updated_at) if updated_at else "",
                "Status": "Completo" if str(champion).strip() and str(top_scorer).strip() else "Pendente",
            }
        )

    return pd.DataFrame(rows).reset_index(drop=True)


def build_pending_chat_text() -> str:
    return (
        "🏆 Kapitalo Cup\n\n"
        "Pendências de placares por participante.\n"
        "A tabela abaixo mostra somente quem ainda não completou todos os jogos."
    )


def build_pending_extras_chat_text() -> str:
    return (
        "🏆 Kapitalo Cup\n\n"
        "Pendências de extras por participante.\n"
        "A tabela abaixo mostra somente quem ainda precisa preencher campeão e/ou artilheiro."
    )


def build_bonus_predictions_chat_text() -> str:
    return (
        "🏆 Kapitalo Cup\n\n"
        "Campeões e artilheiros escolhidos pelos participantes.\n\n"
        "Segue o consolidado dos extras cadastrados."
    )



def render_chat_match_selector(matches: pd.DataFrame, key_prefix: str) -> tuple[str | None, dict]:
    """Componente reutilizável para escolher fase/grupo/jogo nas abas do Google Chat."""
    schedule_matches = sort_matches_for_display(matches)
    stages = schedule_matches["stage"].dropna().unique().tolist() if "stage" in schedule_matches.columns else []

    if not stages:
        st.info("Nenhuma fase encontrada.")
        return None, {}

    col_stage, col_group = st.columns(2)

    with col_stage:
        selected_stage = st.selectbox("Fase", stages, key=f"{key_prefix}_stage")

    filtered = schedule_matches[schedule_matches["stage"] == selected_stage].copy()

    with col_group:
        if "group_name" in filtered.columns and filtered["group_name"].notna().any():
            groups = ["Todos"] + sorted(filtered["group_name"].dropna().unique().tolist())
            selected_group = st.selectbox("Grupo", groups, key=f"{key_prefix}_group")
            if selected_group != "Todos":
                filtered = filtered[filtered["group_name"] == selected_group]
        else:
            st.selectbox("Grupo", ["Não aplicável"], disabled=True, key=f"{key_prefix}_group_disabled")

    filtered = sort_matches_for_display(filtered)

    match_options = []
    match_option_map = {}
    match_info_map = {}
    for _, row in filtered.iterrows():
        label = (
            f"{format_kickoff(row.get('kickoff_at'))} — "
            f"{row.get('home_team', '')} x {row.get('away_team', '')} "
            f"({row.get('match_id', '')})"
        )
        match_options.append(label)
        match_option_map[label] = row.get("match_id")
        match_info_map[label] = row.to_dict()

    if not match_options:
        st.info("Nenhum jogo encontrado para esse filtro.")
        return None, {}

    selected_match_label = st.selectbox("Jogo", match_options, key=f"{key_prefix}_selected")
    return match_option_map[selected_match_label], match_info_map[selected_match_label]


def build_match_score_distribution_table(match_id: str) -> tuple[pd.DataFrame, dict]:
    """Distribuição dos placares previstos para um jogo.

    A etiqueta do placar sempre mostra os nomes dos times, para deixar claro
    se o 2 x 1 é do mandante ou do visitante.
    """
    matches = load_table("matches", order_by="match_no")
    matches = sort_matches_for_display(matches)
    predictions = load_table("predictions")

    match_rows = matches[matches["match_id"].astype(str) == str(match_id)] if not matches.empty and "match_id" in matches.columns else pd.DataFrame()
    if match_rows.empty:
        return pd.DataFrame(columns=["Placar", "Qtd", "%"]), {}

    match = match_rows.iloc[0].to_dict()
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")

    if predictions.empty or "match_id" not in predictions.columns:
        return pd.DataFrame(columns=["Placar", "Qtd", "%"]), match

    pred = predictions[predictions["match_id"].astype(str) == str(match_id)].copy()
    if pred.empty:
        return pd.DataFrame(columns=["Placar", "Qtd", "%"]), match

    pred["home_goals"] = pd.to_numeric(pred.get("home_goals"), errors="coerce")
    pred["away_goals"] = pd.to_numeric(pred.get("away_goals"), errors="coerce")
    pred = pred.dropna(subset=["home_goals", "away_goals"])
    if pred.empty:
        return pd.DataFrame(columns=["Placar", "Qtd", "%"]), match

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
    return out[["Placar", "Qtd", "%"]], match


def distribution_chart_to_png(distribution_df: pd.DataFrame, match: dict) -> str:
    """Gera gráfico horizontal da distribuição dos placares previstos."""
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError("matplotlib não instalado. Adicione matplotlib ao requirements.txt.") from exc

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


def build_match_distribution_chat_text(match: dict) -> str:
    return (
        "🏆 Kapitalo Cup\n\n"
        f"Distribuição dos palpites: {match.get('home_team', '')} x {match.get('away_team', '')}\n"
        f"Fase: {match.get('stage', '')}\n"
        f"Horário: {format_kickoff(match.get('kickoff_at'))}\n\n"
        "O gráfico mostra quantas pessoas escolheram cada placar. "
        "Cada placar está escrito com os nomes dos times para evitar ambiguidade."
    )


def score_prediction_for_match(row: pd.Series, match: dict) -> tuple[int, str]:
    """Calcula a pontuação de uma pessoa em um jogo específico."""
    stage = match.get("stage", "")
    stage_points = stage_points_for_match(stage)

    pred_home = safe_int(row.get("home_goals_pred"))
    pred_away = safe_int(row.get("away_goals_pred"))
    actual_home = safe_int(row.get("home_goals_actual"))
    actual_away = safe_int(row.get("away_goals_actual"))

    pred_type = get_match_result_type(pred_home, pred_away)
    actual_type = get_match_result_type(actual_home, actual_away)

    points = 0
    details = []

    if pred_type == actual_type and stage_points["result"] > 0:
        points += stage_points["result"]
        details.append(f"resultado +{stage_points['result']}")

    if pred_home == actual_home and pred_away == actual_away and stage_points["exact"] > 0:
        points += stage_points["exact"]
        details.append(f"placar exato +{stage_points['exact']}")

    pred_advancing = norm_text(row.get("advancing_team_pred"))
    actual_advancing = norm_text(row.get("advancing_team_actual"))
    if (
        is_knockout_stage(stage)
        and pred_advancing
        and actual_advancing
        and pred_advancing == actual_advancing
        and stage_points["qualified"] > 0
    ):
        points += stage_points["qualified"]
        details.append(f"classificado +{stage_points['qualified']}")

    return points, "; ".join(details)


def build_match_points_table(match_id: str) -> tuple[pd.DataFrame, dict]:
    """Tabela com quem pontuou em um jogo e quantos pontos fez."""
    profiles = load_table("profiles")
    matches = sort_matches_for_display(load_table("matches", order_by="match_no"))
    predictions = load_table("predictions")
    actual_results = load_table("actual_results")

    match_rows = matches[matches["match_id"].astype(str) == str(match_id)] if not matches.empty and "match_id" in matches.columns else pd.DataFrame()
    if match_rows.empty:
        return pd.DataFrame(columns=["Participante", "Palpite", "Resultado", "Pontos", "Como pontuou"]), {}

    match = match_rows.iloc[0].to_dict()
    home_team = match.get("home_team", "")
    away_team = match.get("away_team", "")

    if actual_results.empty or "match_id" not in actual_results.columns:
        return pd.DataFrame(columns=["Participante", "Palpite", "Resultado", "Pontos", "Como pontuou"]), match

    actual = actual_results[actual_results["match_id"].astype(str) == str(match_id)].copy()
    if actual.empty:
        return pd.DataFrame(columns=["Participante", "Palpite", "Resultado", "Pontos", "Como pontuou"]), match

    if predictions.empty or profiles.empty:
        return pd.DataFrame(columns=["Participante", "Palpite", "Resultado", "Pontos", "Como pontuou"]), match

    pred = predictions[predictions["match_id"].astype(str) == str(match_id)].copy()
    if pred.empty:
        return pd.DataFrame(columns=["Participante", "Palpite", "Resultado", "Pontos", "Como pontuou"]), match

    merged = (
        pred.merge(actual, on="match_id", suffixes=("_pred", "_actual"), how="inner")
        .merge(profiles[["id", "username"]], left_on="user_id", right_on="id", how="left")
    )

    rows = []
    actual_row = actual.iloc[0]
    actual_score = f"{home_team} {safe_int(actual_row.get('home_goals'))} x {safe_int(actual_row.get('away_goals'))} {away_team}"

    for _, row in merged.iterrows():
        points, detail = score_prediction_for_match(row, match)
        if points <= 0:
            continue

        pred_score = f"{home_team} {safe_int(row.get('home_goals_pred'))} x {safe_int(row.get('away_goals_pred'))} {away_team}"
        rows.append(
            {
                "Participante": row.get("username", ""),
                "Palpite": pred_score,
                "Resultado": actual_score,
                "Pontos": int(points),
                "Como pontuou": detail,
            }
        )

    out = pd.DataFrame(rows, columns=["Participante", "Palpite", "Resultado", "Pontos", "Como pontuou"])
    if out.empty:
        return out, match
    return out.sort_values(["Pontos", "Participante"], ascending=[False, True]).reset_index(drop=True), match


def build_match_points_chat_text(match: dict) -> str:
    return (
        "🏆 Kapitalo Cup\n\n"
        f"Pontuação do jogo: {match.get('home_team', '')} x {match.get('away_team', '')}\n"
        f"Fase: {match.get('stage', '')}\n"
        f"Horário: {format_kickoff(match.get('kickoff_at'))}\n\n"
        "A tabela mostra somente os participantes que pontuaram neste jogo."
    )


def build_bonus_distribution_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Distribuição de campeões e artilheiros cadastrados."""
    bonus = load_table("bonus_predictions")

    def _dist(col: str) -> pd.DataFrame:
        if bonus.empty or col not in bonus.columns:
            return pd.DataFrame(columns=["Nome", "Qtd", "%"])
        series = bonus[col].fillna("").astype(str).str.strip()
        series = series[series != ""]
        if series.empty:
            return pd.DataFrame(columns=["Nome", "Qtd", "%"])
        total = len(series)
        out = series.value_counts().rename_axis("Nome").reset_index(name="Qtd")
        out["%"] = (out["Qtd"] / total * 100).round(1).astype(str) + "%"
        return out.sort_values(["Qtd", "Nome"], ascending=[False, True]).reset_index(drop=True)

    return _dist("champion"), _dist("top_scorer")


def bonus_distribution_chart_to_png(champion_df: pd.DataFrame, scorer_df: pd.DataFrame) -> str:
    """Gera imagem com duas distribuições: campeões e artilheiros."""
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError("matplotlib não instalado. Adicione matplotlib ao requirements.txt.") from exc

    champ = champion_df.copy() if isinstance(champion_df, pd.DataFrame) and not champion_df.empty else pd.DataFrame({"Nome": ["Sem dados"], "Qtd": [0], "%": ["0%"]})
    scorer = scorer_df.copy() if isinstance(scorer_df, pd.DataFrame) and not scorer_df.empty else pd.DataFrame({"Nome": ["Sem dados"], "Qtd": [0], "%": ["0%"]})

    champ = champ.sort_values("Qtd", ascending=True).tail(12)
    scorer = scorer.sort_values("Qtd", ascending=True).tail(12)

    fig_height = max(6.0, 0.34 * (len(champ) + len(scorer)) + 2.4)
    fig, axes = plt.subplots(2, 1, figsize=(11, fig_height))

    for ax, df, title in [(axes[0], champ, "Distribuição dos campeões"), (axes[1], scorer, "Distribuição dos artilheiros")]:
        ax.barh(df["Nome"], df["Qtd"], color=PRIMARY_COLOR, alpha=0.86)
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("Quantidade de participantes")
        ax.grid(axis="x", alpha=0.22)
        max_qtd = max([1] + [int(x) for x in df["Qtd"].tolist()])
        ax.set_xlim(0, max_qtd * 1.25)
        for i, (_, row) in enumerate(df.iterrows()):
            ax.text(int(row["Qtd"]) + max_qtd * 0.015, i, f"{row['Qtd']} ({row['%']})", va="center", fontsize=9)

    fig.suptitle("Kapitalo Cup — Distribuição dos extras", fontweight="bold", y=0.995)
    fig.tight_layout(pad=0.9)

    output = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    output.close()
    fig.savefig(output.name, dpi=190, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return output.name


def build_bonus_distribution_chat_text() -> str:
    return (
        "🏆 Kapitalo Cup\n\n"
        "Distribuição dos campeões e artilheiros escolhidos.\n\n"
        "O gráfico mostra a concentração dos palpites de extras cadastrados pelos participantes."
    )

def render_google_chat_admin_page(matches: pd.DataFrame):
    st.markdown("### Google Chat")
    st.caption(
        "Envie manualmente para o Space os palpites de um jogo, distribuições, pontuações e ranking. "
        "Os dados são lidos do Supabase no momento do envio."
    )

    config_ok, config_msg = google_chat_config_ok()
    if config_ok:
        st.success(f"Google Chat configurado. Space: {get_google_chat_space_id()}")
    else:
        st.warning(config_msg)
        st.info(
            "Configure GOOGLE_CHAT_SPACE_ID, GOOGLE_CHAT_CLIENT_SECRET_JSON e GOOGLE_CHAT_TOKEN_JSON "
            "no Streamlit Secrets antes de enviar mensagens."
        )

    if matches.empty:
        st.warning("Nenhum jogo encontrado.")
        return

    (
        tab_match_chat,
        tab_score_dist_chat,
        tab_match_points_chat,
        tab_ranking_chat,
        tab_bonus_dist_chat,
        tab_pending_chat,
        tab_bonus_chat,
    ) = st.tabs(
        [
            "Palpites por jogo",
            "Distribuição placares",
            "Pontuação por jogo",
            "Ranking atualizado",
            "Distribuição extras",
            "Pendências placares",
            "Pendências extras",
        ]
    )

    with tab_match_chat:
        st.markdown("#### Enviar palpites de um jogo")
        selected_match_id, match_info = render_chat_match_selector(matches, "chat_match")
        if not selected_match_id:
            return

        prediction_filter_label = st.radio(
            "Quem entra na tabela/imagem?",
            ["Todos", "Somente com palpite", "Somente pendentes"],
            horizontal=True,
            key="chat_match_prediction_filter",
            help=(
                "Todos inclui quem já mandou palpite e quem ainda está pendente. "
                "Somente com palpite tira os pendentes. Somente pendentes mostra só quem ainda não preencheu."
            ),
        )
        prediction_filter_map = {
            "Todos": "all",
            "Somente com palpite": "complete",
            "Somente pendentes": "pending",
        }
        prediction_filter = prediction_filter_map[prediction_filter_label]

        table_df, match_info = build_match_predictions_table(
            selected_match_id,
            prediction_filter=prediction_filter,
        )
        all_table_df, _ = build_match_predictions_table(selected_match_id, prediction_filter="all")

        st.markdown("##### Prévia da tabela")
        st.dataframe(table_df, use_container_width=True, hide_index=True, height=420)

        pending_count = int((all_table_df["Palpite"] == "Pendente").sum()) if "Palpite" in all_table_df.columns else 0
        complete_count = int((all_table_df["Palpite"] != "Pendente").sum()) if "Palpite" in all_table_df.columns else 0
        st.caption(f"Filtro da imagem: {prediction_filter_label}. Com palpite: {complete_count} | Pendentes: {pending_count}.")
        if pending_count:
            st.warning(f"Ainda existem {pending_count} participantes sem palpite para este jogo.")

        chat_text = build_match_chat_text(match_info)
        with st.expander("Prévia da mensagem"):
            st.text(chat_text)

        if st.button(
            "Enviar palpites deste jogo para Google Chat",
            key="send_match_predictions_chat",
            use_container_width=True,
            disabled=not config_ok or table_df.empty,
        ):
            try:
                title = f"Palpites — {match_info.get('home_team', '')} x {match_info.get('away_team', '')}"
                subtitle = f"{match_info.get('stage', '')} • {format_kickoff(match_info.get('kickoff_at'))}"
                footer = "Legenda: lobo-guará e mico-leão = palpites aleatórios; claude fable 5 = palpite da IA."
                image_path = dataframe_to_png(
                    table_df,
                    title=title,
                    subtitle=subtitle,
                    footer=footer,
                    max_rows=None,
                    max_fig_height=32,
                )
                send_google_chat_image(chat_text, image_path)
                st.success("Palpites enviados para o Google Chat.")
            except Exception as exc:
                st.error(f"Erro ao enviar para Google Chat: {exc}")

    with tab_score_dist_chat:
        st.markdown("#### Enviar distribuição dos placares previstos")
        selected_match_id, match_info = render_chat_match_selector(matches, "chat_score_distribution")
        if not selected_match_id:
            return

        dist_df, match_info = build_match_score_distribution_table(selected_match_id)
        st.markdown("##### Prévia da distribuição")
        if dist_df.empty:
            st.info("Ainda não há palpites preenchidos para este jogo.")
        else:
            st.dataframe(dist_df, use_container_width=True, hide_index=True, height=360)
            st.caption("O placar está sempre escrito como: Time mandante Gols x Gols Time visitante.")

        chat_text = build_match_distribution_chat_text(match_info)
        with st.expander("Prévia da mensagem"):
            st.text(chat_text)

        if st.button(
            "Enviar distribuição de placares para Google Chat",
            key="send_score_distribution_chat",
            use_container_width=True,
            disabled=not config_ok or dist_df.empty,
        ):
            try:
                image_path = distribution_chart_to_png(dist_df, match_info)
                send_google_chat_image(chat_text, image_path)
                st.success("Distribuição de placares enviada para o Google Chat.")
            except Exception as exc:
                st.error(f"Erro ao enviar distribuição: {exc}")

    with tab_match_points_chat:
        st.markdown("#### Enviar quem pontuou em um jogo")
        selected_match_id, match_info = render_chat_match_selector(matches, "chat_match_points")
        if not selected_match_id:
            return

        points_df, match_info = build_match_points_table(selected_match_id)
        st.markdown("##### Prévia da pontuação do jogo")
        if points_df.empty:
            st.info("Ainda não há resultado oficial cadastrado para este jogo ou ninguém pontuou.")
        else:
            st.dataframe(points_df, use_container_width=True, hide_index=True, height=420)

        chat_text = build_match_points_chat_text(match_info)
        with st.expander("Prévia da mensagem"):
            st.text(chat_text)

        if st.button(
            "Enviar pontuação deste jogo para Google Chat",
            key="send_match_points_chat",
            use_container_width=True,
            disabled=not config_ok or points_df.empty,
        ):
            try:
                title = f"Pontuação — {match_info.get('home_team', '')} x {match_info.get('away_team', '')}"
                subtitle = f"{match_info.get('stage', '')} • {format_kickoff(match_info.get('kickoff_at'))}"
                image_path = dataframe_to_png(points_df, title=title, subtitle=subtitle)
                send_google_chat_image(chat_text, image_path)
                st.success("Pontuação do jogo enviada para o Google Chat.")
            except Exception as exc:
                st.error(f"Erro ao enviar pontuação do jogo: {exc}")

    with tab_ranking_chat:
        st.markdown("#### Enviar ranking atualizado")

        data = load_ranking_inputs()
        ranking = calculate_ranking_cached(
            profiles=data["profiles"],
            matches=data["matches"],
            predictions=data["predictions"],
            actual_results=data["actual_results"],
            phase_predictions=data["phase_predictions"],
            phase_actuals=data["phase_actuals"],
            bonus_predictions=data["bonus_predictions"],
            bonus_actuals=data["bonus_actuals"],
        )

        ranking_view = ranking.drop(columns=["user_id"], errors="ignore")
        st.markdown("##### Prévia do ranking")
        st.dataframe(ranking_view, use_container_width=True, hide_index=True, height=420)

        chat_text = build_ranking_chat_text()
        with st.expander("Prévia da mensagem"):
            st.text(chat_text)

        if st.button(
            "Enviar ranking atualizado para Google Chat",
            key="send_ranking_chat",
            use_container_width=True,
            disabled=not config_ok or ranking_view.empty,
        ):
            try:
                image_path = dataframe_to_png(
                    ranking_view,
                    title="Ranking Kapitalo Cup",
                    subtitle=now_app_tz().strftime("Atualizado em %d/%m/%Y %H:%M"),
                )
                send_google_chat_image(chat_text, image_path)
                st.success("Ranking enviado para o Google Chat.")
            except Exception as exc:
                st.error(f"Erro ao enviar ranking para Google Chat: {exc}")

    with tab_bonus_dist_chat:
        st.markdown("#### Enviar distribuição de campeões e artilheiros")
        champion_df, scorer_df = build_bonus_distribution_tables()

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### Campeões")
            if champion_df.empty:
                st.info("Sem campeões preenchidos.")
            else:
                st.dataframe(champion_df, use_container_width=True, hide_index=True, height=360)
        with col2:
            st.markdown("##### Artilheiros")
            if scorer_df.empty:
                st.info("Sem artilheiros preenchidos.")
            else:
                st.dataframe(scorer_df, use_container_width=True, hide_index=True, height=360)

        chat_text = build_bonus_distribution_chat_text()
        with st.expander("Prévia da mensagem"):
            st.text(chat_text)

        if st.button(
            "Enviar distribuição de extras para Google Chat",
            key="send_bonus_distribution_chat",
            use_container_width=True,
            disabled=not config_ok or (champion_df.empty and scorer_df.empty),
        ):
            try:
                image_path = bonus_distribution_chart_to_png(champion_df, scorer_df)
                send_google_chat_image(chat_text, image_path)
                st.success("Distribuição de extras enviada para o Google Chat.")
            except Exception as exc:
                st.error(f"Erro ao enviar distribuição de extras: {exc}")

    with tab_pending_chat:
        st.markdown("#### Enviar pendências por participante")

        pending_view = build_pending_predictions_summary_table()
        st.markdown("##### Prévia das pendências")
        st.dataframe(pending_view, use_container_width=True, hide_index=True, height=420)

        chat_text = build_pending_chat_text()
        with st.expander("Prévia da mensagem"):
            st.text(chat_text)

        if st.button(
            "Enviar pendências para Google Chat",
            key="send_pending_chat",
            use_container_width=True,
            disabled=not config_ok or pending_view.empty,
        ):
            try:
                image_path = dataframe_to_png(pending_view)
                send_google_chat_image(chat_text, image_path)
                st.success("Pendências enviadas para o Google Chat.")
            except Exception as exc:
                st.error(f"Erro ao enviar pendências para Google Chat: {exc}")

    with tab_bonus_chat:
        st.markdown("#### Enviar pendências de extras")

        extras_pending_view = build_pending_extras_summary_table()
        st.markdown("##### Prévia dos extras pendentes")

        if extras_pending_view.empty:
            st.success("Todos os participantes já preencheram campeão e artilheiro.")
        else:
            st.dataframe(extras_pending_view, use_container_width=True, hide_index=True, height=420)

        chat_text = build_pending_extras_chat_text()
        with st.expander("Prévia da mensagem"):
            st.text(chat_text)

        if st.button(
            "Enviar pendências de extras para Google Chat",
            key="send_bonus_predictions_chat",
            use_container_width=True,
            disabled=not config_ok or extras_pending_view.empty,
        ):
            try:
                image_path = dataframe_to_png(extras_pending_view)
                send_google_chat_image(chat_text, image_path)
                st.success("Pendências de extras enviadas para o Google Chat.")
            except Exception as exc:
                st.error(f"Erro ao enviar pendências de extras para Google Chat: {exc}")

# ============================================================
# RANKING E DETALHE DE PONTOS
# ============================================================


def build_score_breakdown_for_user(
    user_id: str,
    matches: pd.DataFrame,
    predictions: pd.DataFrame,
    actual_results: pd.DataFrame,
    phase_predictions: pd.DataFrame,
    phase_actuals: pd.DataFrame,
    bonus_predictions: pd.DataFrame,
    bonus_actuals: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    if (
        not predictions.empty
        and not actual_results.empty
        and not matches.empty
        and "match_id" in predictions.columns
        and "match_id" in actual_results.columns
        and "match_id" in matches.columns
    ):
        user_preds = predictions[predictions["user_id"] == user_id].copy()

        if not user_preds.empty:
            match_cols = [
                col
                for col in ["match_id", "match_no", "stage", "group_name", "home_team", "away_team", "kickoff_at"]
                if col in matches.columns
            ]

            merged = (
                user_preds
                .merge(
                    actual_results,
                    on="match_id",
                    suffixes=("_pred", "_actual"),
                    how="inner",
                )
                .merge(
                    matches[match_cols],
                    on="match_id",
                    how="left",
                )
            )

            for _, row in merged.iterrows():
                stage = row.get("stage", "")
                stage_points = stage_points_for_match(stage)

                pred_home = safe_int(row.get("home_goals_pred"))
                pred_away = safe_int(row.get("away_goals_pred"))
                actual_home = safe_int(row.get("home_goals_actual"))
                actual_away = safe_int(row.get("away_goals_actual"))

                pred_type = get_match_result_type(pred_home, pred_away)
                actual_type = get_match_result_type(actual_home, actual_away)

                match_label = f"{row.get('home_team', '')} x {row.get('away_team', '')}"
                pred_score = f"{pred_home} x {pred_away}"
                actual_score = f"{actual_home} x {actual_away}"

                if pred_type == actual_type and stage_points["result"] > 0:
                    rows.append(
                        {
                            "Categoria": "Jogo",
                            "Fase": row.get("stage", ""),
                            "Item": match_label,
                            "Detalhe": f"Resultado correto | Palpite {pred_score} | Real {actual_score}",
                            "Pontos": stage_points["result"],
                        }
                    )

                if pred_home == actual_home and pred_away == actual_away and stage_points["exact"] > 0:
                    rows.append(
                        {
                            "Categoria": "Jogo",
                            "Fase": row.get("stage", ""),
                            "Item": match_label,
                            "Detalhe": f"Placar exato | Palpite {pred_score} | Real {actual_score}",
                            "Pontos": stage_points["exact"],
                        }
                    )

                pred_advancing = norm_text(row.get("advancing_team_pred"))
                actual_advancing = norm_text(row.get("advancing_team_actual"))

                if (
                    is_knockout_stage(stage)
                    and pred_advancing
                    and actual_advancing
                    and pred_advancing == actual_advancing
                    and stage_points["qualified"] > 0
                ):
                    rows.append(
                        {
                            "Categoria": "Classificado no jogo",
                            "Fase": row.get("stage", ""),
                            "Item": match_label,
                            "Detalhe": f"Classificado correto: {row.get('advancing_team_pred')}",
                            "Pontos": stage_points["qualified"],
                        }
                    )

    if not bonus_predictions.empty and not bonus_actuals.empty:
        user_bonus = bonus_predictions[bonus_predictions["user_id"] == user_id].copy(
        )

        if not user_bonus.empty:
            pred = user_bonus.iloc[0]
            actual = bonus_actuals.iloc[0]

            pred_champion = norm_text(pred.get("champion"))
            actual_champion = norm_text(actual.get("champion"))

            pred_top_scorer = norm_text(pred.get("top_scorer"))
            actual_top_scorer = norm_text(actual.get("top_scorer"))

            if pred_champion and actual_champion and pred_champion == actual_champion:
                rows.append(
                    {
                        "Categoria": "Extras",
                        "Fase": "Extras",
                        "Item": pred.get("champion", ""),
                        "Detalhe": "Campeão correto",
                        "Pontos": 100,
                    }
                )

            if pred_top_scorer and actual_top_scorer and pred_top_scorer == actual_top_scorer:
                rows.append(
                    {
                        "Categoria": "Extras",
                        "Fase": "Extras",
                        "Item": pred.get("top_scorer", ""),
                        "Detalhe": "Artilheiro correto",
                        "Pontos": 100,
                    }
                )

    if not rows:
        return pd.DataFrame(columns=["Categoria", "Fase", "Item", "Detalhe", "Pontos"])

    df = pd.DataFrame(rows)
    return df.sort_values(["Categoria", "Fase", "Item"]).reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def calculate_ranking_cached(
    profiles: pd.DataFrame,
    matches: pd.DataFrame,
    predictions: pd.DataFrame,
    actual_results: pd.DataFrame,
    phase_predictions: pd.DataFrame,
    phase_actuals: pd.DataFrame,
    bonus_predictions: pd.DataFrame,
    bonus_actuals: pd.DataFrame,
) -> pd.DataFrame:
    if profiles.empty:
        return pd.DataFrame(columns=["Posição", "Usuário", "Pontuação"])

    ranking_rows = []

    for _, user in profiles.iterrows():
        user_id = user.get("id")
        username = user.get("username", "")

        breakdown = build_score_breakdown_for_user(
            user_id=user_id,
            matches=matches,
            predictions=predictions,
            actual_results=actual_results,
            phase_predictions=phase_predictions,
            phase_actuals=phase_actuals,
            bonus_predictions=bonus_predictions,
            bonus_actuals=bonus_actuals,
        )

        score = int(breakdown["Pontos"].sum()) if not breakdown.empty else 0

        ranking_rows.append(
            {
                "Usuário": username,
                "user_id": user_id,
                "Pontuação": score,
            }
        )

    ranking = pd.DataFrame(ranking_rows)
    if ranking.empty:
        return pd.DataFrame(columns=["Posição", "Usuário", "Pontuação"])

    ranking = ranking.sort_values(
        "Pontuação", ascending=False).reset_index(drop=True)
    ranking.insert(0, "Posição", ranking.index + 1)

    return ranking


def load_ranking_inputs():
    profiles = load_table("profiles")
    matches = load_table("matches", order_by="match_no")
    predictions = load_table("predictions")
    actual_results = load_table("actual_results")
    phase_predictions = load_table("phase_predictions")
    phase_actuals = load_table("phase_actuals")
    bonus_predictions = load_table("bonus_predictions")
    bonus_actuals = load_table("bonus_actuals")

    return {
        "profiles": profiles,
        "matches": matches,
        "predictions": predictions,
        "actual_results": actual_results,
        "phase_predictions": phase_predictions,
        "phase_actuals": phase_actuals,
        "bonus_predictions": bonus_predictions,
        "bonus_actuals": bonus_actuals,
    }


def calculate_ranking() -> pd.DataFrame:
    data = load_ranking_inputs()

    return calculate_ranking_cached(
        profiles=data["profiles"],
        matches=data["matches"],
        predictions=data["predictions"],
        actual_results=data["actual_results"],
        phase_predictions=data["phase_predictions"],
        phase_actuals=data["phase_actuals"],
        bonus_predictions=data["bonus_predictions"],
        bonus_actuals=data["bonus_actuals"],
    )

# ============================================================
# SIDEBAR
# ============================================================


def render_auth_sidebar():
    with st.sidebar:
        render_logo_sidebar()

        st.markdown("### Acesse sua conta")

        tab_login, tab_create = st.tabs(["Login", "Criar usuário"])

        with tab_login:
            username = st.text_input("Usuário", key="login_username")
            password = st.text_input(
                "Senha", type="password", key="login_password")

            if st.button("Entrar", key="btn_login", use_container_width=True):
                ok, msg = login_user(username, password)

                if ok:
                    st.success(msg)
                    clear_data_cache()
                    st.rerun()
                else:
                    st.error(msg)

        with tab_create:
            new_username = st.text_input("Novo usuário", key="new_username")
            new_password = st.text_input(
                "Nova senha", type="password", key="new_password")

            if st.button("Cadastrar", key="btn_create_user", use_container_width=True):
                ok, msg = create_user(new_username, new_password)

                if ok:
                    st.success(msg)
                    clear_data_cache()
                else:
                    st.error(msg)


def render_logged_sidebar():
    with st.sidebar:
        render_logo_sidebar()

        username = st.session_state.get("username", "")

        st.markdown(
            f"""
            <div class="sidebar-user-card">
                <p><b>Usuário logado</b></p>
                <p>{username}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        next_lock = next_open_lock_info()
        if next_lock is None:
            st.warning("Todos os prazos de palpites estão encerrados.")
        else:
            next_key, next_at = next_lock
            st.info(
                f"Próximo prazo: {get_lock_label_from_key(next_key)} até {next_at.strftime('%d/%m/%Y %H:%M')}.")

        if st.button("Sair", key="btn_logout", use_container_width=True):
            logout()
            st.session_state.pop("main_menu", None)
            st.session_state.pop("selected_phase_predictions", None)
            clear_data_cache()
            st.rerun()

        st.divider()

        menu_options = [
            "Início",
            "Ranking",
            "Meus palpites",
            "Regras",
        ]

        if is_admin():
            menu_options.append("Admin")

        page = st.radio(
            "Menu",
            menu_options,
            key="main_menu",
        )

        return page


# ============================================================
# PÁGINA: INÍCIO / CHECKLIST
# ============================================================

def render_home_page():
    if not st.session_state.get("is_logged_in", False):
        st.warning("Faça login para ver suas pendências.")
        return

    user_id = st.session_state["user_id"]
    username = st.session_state.get("username", "")

    pending_matches, pending_extras = build_missing_items_for_user(user_id)
    matches = load_table("matches", order_by="match_no")
    predictions = load_table("predictions")

    total_matches = len(matches) if not matches.empty else 0

    if not predictions.empty and "user_id" in predictions.columns:
        user_pred_count = len(predictions[predictions["user_id"] == user_id])
    else:
        user_pred_count = 0

    next_lock = next_open_lock_info()
    lock_schedule = build_lock_schedule_df()

    st.markdown(
        f"""
        <div class="section-card">
            <h3 style="margin-bottom:0.25rem;">Olá, {username}</h3>
            <p style="color:#6b7280;margin-bottom:0;">
                Use este painel para acompanhar o que falta preencher, ver os prazos por fase e exportar suas previsões.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_box("Jogos preenchidos", f"{user_pred_count}/{total_matches}")

    with col2:
        metric_box("Jogos pendentes", str(len(pending_matches)))

    with col3:
        if next_lock is None:
            metric_box("Próximo prazo", "Todos travados")
        else:
            next_key, next_at = next_lock
            metric_box("Próximo prazo", get_lock_label_from_key(next_key))

    if next_lock is None:
        st.warning(
            "Todos os prazos de cadastro/alteração de palpites estão encerrados.")
    else:
        next_key, next_at = next_lock
        st.success(
            f"Próximo fechamento: {get_lock_label_from_key(next_key)} em {next_at.strftime('%d/%m/%Y %H:%M')}."
        )

    with st.expander("Ver prazos por fase", expanded=True):
        st.dataframe(lock_schedule.drop(columns=[
                     "Chave no secrets.toml"], errors="ignore"), use_container_width=True, hide_index=True)

    st.download_button(
        label="Baixar minhas previsões em Excel",
        data=build_user_prediction_export(user_id),
        file_name=f"kapitalo_cup_previsoes_{username}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()

    tab_games, tab_extras = st.tabs(["Jogos pendentes", "Extras pendentes"])

    with tab_games:
        st.markdown("### Jogos que faltam preencher")

        if pending_matches.empty:
            st.success("Você já preencheu todos os jogos cadastrados na base.")
        else:
            st.caption(
                "A lista mostra primeiro os jogos cadastrados na base. No começo, aparecem só jogos da fase de grupos; quando novos jogos forem cadastrados pelo admin, eles também aparecerão aqui."
            )
            st.dataframe(pending_matches, use_container_width=True,
                         hide_index=True, height=360)

    with tab_extras:
        st.markdown("### Extras pendentes")

        if pending_extras.empty:
            st.success("Você já preencheu campeão e artilheiro.")
        else:
            st.dataframe(pending_extras, use_container_width=True,
                         hide_index=True, height=320)


# ============================================================
# PÁGINA: RANKING
# ============================================================


def render_ranking():
    if st_autorefresh is not None:
        st_autorefresh(interval=60_000, key="ranking_autorefresh")

    data = load_ranking_inputs()

    ranking = calculate_ranking_cached(
        profiles=data["profiles"],
        matches=data["matches"],
        predictions=data["predictions"],
        actual_results=data["actual_results"],
        phase_predictions=data["phase_predictions"],
        phase_actuals=data["phase_actuals"],
        bonus_predictions=data["bonus_predictions"],
        bonus_actuals=data["bonus_actuals"],
    )

    if ranking.empty:
        st.info("Ainda não existem usuários cadastrados.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_box("Participantes", str(len(ranking)))

    with col2:
        metric_box("Líder", str(ranking.iloc[0]["Usuário"]))

    with col3:
        metric_box("Maior pontuação", str(int(ranking["Pontuação"].max())))

    tab_table, tab_detail = st.tabs(["Tabela geral", "Detalhe dos pontos"])

    with tab_table:
        st.markdown("### Tabela de classificação")

        display_ranking = ranking.drop(columns=["user_id"], errors="ignore")

        st.dataframe(
            display_ranking,
            use_container_width=True,
            hide_index=True,
            height=420,
        )

    with tab_detail:
        st.markdown("### Detalhe dos pontos por jogador")

        user_options = ranking["Usuário"].tolist()

        selected_username = st.selectbox(
            "Selecione um jogador",
            user_options,
            key="ranking_detail_user",
        )

        selected_row = ranking[ranking["Usuário"] == selected_username].iloc[0]
        selected_user_id = selected_row["user_id"]

        breakdown = build_score_breakdown_for_user(
            user_id=selected_user_id,
            matches=data["matches"],
            predictions=data["predictions"],
            actual_results=data["actual_results"],
            phase_predictions=data["phase_predictions"],
            phase_actuals=data["phase_actuals"],
            bonus_predictions=data["bonus_predictions"],
            bonus_actuals=data["bonus_actuals"],
        )

        total_points = int(breakdown["Pontos"].sum()
                           ) if not breakdown.empty else 0

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            metric_box("Jogador", selected_username)

        with col_b:
            metric_box("Pontuação total", str(total_points))

        with col_c:
            metric_box("Itens pontuados", str(len(breakdown)))

        if breakdown.empty:
            st.info(
                "Esse jogador ainda não pontuou ou ainda não há resultados oficiais cadastrados.")
            return

        summary = (
            breakdown
            .groupby("Categoria", as_index=False)["Pontos"]
            .sum()
            .sort_values("Pontos", ascending=False)
        )

        st.markdown("#### Resumo por categoria")
        st.dataframe(summary, use_container_width=True, hide_index=True)

        category_options = [
            "Todas"] + sorted(breakdown["Categoria"].dropna().unique().tolist())

        selected_category = st.selectbox(
            "Filtrar categoria",
            category_options,
            key="ranking_detail_category",
        )

        detail_view = breakdown.copy()

        if selected_category != "Todas":
            detail_view = detail_view[detail_view["Categoria"]
                                      == selected_category].copy()

        st.markdown("#### Pontos conquistados")
        st.dataframe(detail_view, use_container_width=True,
                     hide_index=True, height=420)


# ============================================================
# PÁGINA: MEUS PALPITES
# ============================================================


def render_bonus_predictions_section(user_id: str, teams: list[str], supabase, key_suffix: str = "main"):
    """Escolha de campeão e artilheiro dentro da tela de palpites da fase de grupos."""
    st.markdown("### Extras antes da Copa")
    render_stage_lock_message("extras", label="Extras — campeão e artilheiro")

    existing_bonus = load_table("bonus_predictions")

    if not existing_bonus.empty and "user_id" in existing_bonus.columns:
        user_bonus = existing_bonus[existing_bonus["user_id"] == user_id].copy(
        )
    else:
        user_bonus = pd.DataFrame()

    default_champion = ""
    default_top_scorer = ""

    if not user_bonus.empty:
        default_champion = user_bonus.iloc[0].get("champion") or ""
        default_top_scorer = user_bonus.iloc[0].get("top_scorer") or ""

    champion_options = [""] + teams
    champion_index = champion_options.index(
        default_champion) if default_champion in champion_options else 0
    extras_locked = is_stage_locked("extras")

    col1, col2, col3 = st.columns([1.2, 1.2, 0.8])

    with col1:
        champion = st.selectbox(
            "Campeão",
            champion_options,
            index=champion_index,
            key=f"bonus_champion_inline_{key_suffix}",
            disabled=extras_locked,
        )

    with col2:
        top_scorer = st.text_input(
            "Artilheiro",
            value=default_top_scorer,
            key=f"bonus_top_scorer_inline_{key_suffix}",
            disabled=extras_locked,
        )

    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(
            "Salvar extras",
            key=f"save_bonus_inline_{key_suffix}",
            use_container_width=True,
            disabled=extras_locked,
        ):
            if is_stage_locked("extras"):
                st.error(
                    f"Não é possível alterar extras. O prazo encerrou em {stage_lock_text('extras')}.")
                st.stop()

            payload = {
                "user_id": user_id,
                "champion": champion if champion else None,
                "top_scorer": top_scorer.strip() if top_scorer else None,
            }

            try:
                supabase.table("bonus_predictions").upsert(
                    payload,
                    on_conflict="user_id",
                ).execute()

                clear_data_cache()
                st.success("Extras salvos.")
                st.rerun()

            except Exception as exc:
                st.error(f"Erro ao salvar extras: {exc}")

    st.caption("Campeão e artilheiro valem 100 pontos cada. Eles ficam disponíveis na fase de grupos e travam no prazo de extras.")


def make_group_editor_df(group_matches: pd.DataFrame, user_predictions: pd.DataFrame) -> pd.DataFrame:
    """Monta a tabela editável de um grupo com valores salvos como default."""
    rows = []

    for _, match in sort_matches_for_display(group_matches).iterrows():
        match_id = match.get("match_id", "")
        existing = pd.DataFrame()

        if not user_predictions.empty and "match_id" in user_predictions.columns:
            existing = user_predictions[user_predictions["match_id"].astype(
                str) == str(match_id)]

        home_goals = None
        away_goals = None

        if not existing.empty:
            home_goals = safe_int(
                existing.iloc[0].get("home_goals"), default=None)
            away_goals = safe_int(
                existing.iloc[0].get("away_goals"), default=None)

        rows.append(
            {
                "match_id": match_id,
                "Horário": format_kickoff(match.get("kickoff_at")),
                "Mandante": match.get("home_team", ""),
                "Gols mandante": home_goals,
                "Gols visitante": away_goals,
                "Visitante": match.get("away_team", ""),
            }
        )

    return pd.DataFrame(rows)


def editor_df_to_prediction_payloads(editor_df: pd.DataFrame, user_id: str, stage: str) -> tuple[list[str], list[dict]]:
    """Converte a tabela editável em payloads. Não salva nada quando há linha incompleta."""
    invalid_rows = []
    payload_rows = []

    if editor_df is None or editor_df.empty:
        return ["Nenhum jogo encontrado nesta tela."], []

    for _, row in editor_df.iterrows():
        match_id = row.get("match_id")
        home_team = row.get("Mandante", "")
        away_team = row.get("Visitante", "")
        label = f"{row.get('Horário', '')} — {home_team} x {away_team}"
        home_value = row.get("Gols mandante")
        away_value = row.get("Gols visitante")

        if pd.isna(home_value) or pd.isna(away_value) or home_value is None or away_value is None:
            invalid_rows.append(label)
            continue

        try:
            home_int = int(home_value)
            away_int = int(away_value)
        except Exception:
            invalid_rows.append(label)
            continue

        if home_int < 0 or away_int < 0:
            invalid_rows.append(label)
            continue

        payload_rows.append(
            {
                "user_id": user_id,
                "match_id": match_id,
                "home_goals": home_int,
                "away_goals": away_int,
                "advancing_team": None if is_group_stage(stage) else infer_advancing_team(home_team, away_team, home_int, away_int, None),
            }
        )

    return invalid_rows, payload_rows


def group_table_from_editor(group_matches: pd.DataFrame, editor_df: pd.DataFrame) -> pd.DataFrame:
    """Simula a tabela do grupo usando o que está no editor, mesmo antes de salvar."""
    if editor_df is None or editor_df.empty:
        return simulate_group_table(group_matches, pd.DataFrame())

    pred_rows = []
    for _, row in editor_df.iterrows():
        hg = row.get("Gols mandante")
        ag = row.get("Gols visitante")
        if pd.isna(hg) or pd.isna(ag) or hg is None or ag is None:
            continue
        try:
            pred_rows.append(
                {
                    "match_id": row.get("match_id"),
                    "home_goals": int(hg),
                    "away_goals": int(ag),
                }
            )
        except Exception:
            continue

    return simulate_group_table(group_matches, pd.DataFrame(pred_rows))


def compact_group_table(df: pd.DataFrame) -> pd.DataFrame:
    """Tabela simulada menor para exibir no modo agrupado."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Pos", "Seleção", "J", "V", "E", "D", "SG", "Pts"])

    out = df.copy()
    out = out.drop(columns=["GP", "GC"], errors="ignore")

    wanted_cols = [col for col in ["Pos", "Seleção", "J",
                                   "V", "E", "D", "SG", "Pts"] if col in out.columns]
    return out[wanted_cols]


def group_table_from_input_rows(group_matches: pd.DataFrame, input_rows: list[dict]) -> pd.DataFrame:
    """Simula a tabela do grupo usando os valores atualmente submetidos no formulário."""
    pred_rows = []

    for row in input_rows:
        home_value = row.get("home_goals")
        away_value = row.get("away_goals")

        if home_value is None or away_value is None:
            continue

        try:
            pred_rows.append(
                {
                    "match_id": row.get("match_id"),
                    "home_goals": int(home_value),
                    "away_goals": int(away_value),
                }
            )
        except Exception:
            continue

    table = simulate_group_table(group_matches, pd.DataFrame(pred_rows))
    return compact_group_table(table)


def build_user_template_excel(user_id: str, selected_stage: str | None = None) -> bytes:
    """Gera um Excel-template para o usuário preencher fora do app e importar de volta.

    Quando selected_stage é informado, o template vem apenas com os jogos daquela fase.
    Isso é melhor para fases futuras, porque o usuário baixa/preenche só o bloco que está aberto.
    """
    matches = sort_matches_for_display(
        load_table("matches", order_by="match_no"))
    predictions = load_table("predictions")
    bonus_predictions = load_table("bonus_predictions")

    if matches.empty:
        return create_excel_bytes({"Palpites": pd.DataFrame()})

    if selected_stage and "stage" in matches.columns:
        matches = matches[matches["stage"] == selected_stage].copy()
        matches = sort_matches_for_display(matches)

    if matches.empty:
        return create_excel_bytes({"Palpites": pd.DataFrame({"Mensagem": ["Nenhum jogo encontrado para esta fase."]})})

    user_predictions = pd.DataFrame()
    if not predictions.empty and "user_id" in predictions.columns:
        user_predictions = predictions[predictions["user_id"] == user_id].copy(
        )

    match_cols = [
        col for col in ["match_id", "stage", "group_name", "kickoff_at", "home_team", "away_team"]
        if col in matches.columns
    ]
    out = matches[match_cols].copy()
    if not user_predictions.empty:
        pred_cols = [col for col in ["match_id", "home_goals", "away_goals",
                                     "advancing_team"] if col in user_predictions.columns]
        out = out.merge(user_predictions[pred_cols], on="match_id", how="left")
    else:
        out["home_goals"] = ""
        out["away_goals"] = ""
        out["advancing_team"] = ""

    out["Horário"] = out.apply(
        lambda r: format_kickoff(r.get("kickoff_at")), axis=1)
    out = out.rename(
        columns={
            "match_id": "match_id",
            "stage": "Fase",
            "group_name": "Grupo",
            "home_team": "Mandante",
            "away_team": "Visitante",
            "home_goals": "Gols mandante",
            "away_goals": "Gols visitante",
            "advancing_team": "Classificado",
        }
    )

    ordered = [
        "match_id", "Fase", "Grupo", "Horário", "Mandante",
        "Gols mandante", "Gols visitante", "Visitante", "Classificado",
    ]
    out = out[[c for c in ordered if c in out.columns]]

    champion = ""
    top_scorer = ""
    if not bonus_predictions.empty and "user_id" in bonus_predictions.columns:
        b = bonus_predictions[bonus_predictions["user_id"] == user_id].copy()
        if not b.empty:
            champion = b.iloc[0].get("champion") or ""
            top_scorer = b.iloc[0].get("top_scorer") or ""

    extras = pd.DataFrame(
        [
            {"Campo": "Campeão", "Valor": champion},
            {"Campo": "Artilheiro", "Valor": top_scorer},
        ]
    )

    instrucoes = pd.DataFrame(
        {
            "Instruções": [
                "Preencha as colunas Gols mandante e Gols visitante.",
                "Na fase de grupos, deixe Classificado vazio.",
                "Em mata-mata, se o placar estiver empatado, preencha Classificado com Mandante ou Visitante.",
                "Não altere a coluna match_id.",
                "Na aba Extras, preencha Campeão e Artilheiro.",
            ]
        }
    )

    return create_excel_bytes({"Palpites": out, "Extras": extras, "Instruções": instrucoes})


def predictions_excel_to_payloads(uploaded_file, user_id: str, matches: pd.DataFrame, selected_stage: str | None = None) -> tuple[pd.DataFrame, list[dict], dict, list[str]]:
    """Lê o template importado e transforma em payloads para Supabase.

    A leitura é feita linha a linha, sempre usando o match_id da própria linha.
    Isso evita que um valor digitado em uma linha seja reaproveitado por engano
    para outros jogos. Se houver qualquer erro, nada é salvo.
    """
    errors: list[str] = []
    payloads: list[dict] = []
    bonus_payload: dict = {}

    try:
        xls = pd.ExcelFile(uploaded_file)
        df = pd.read_excel(xls, sheet_name="Palpites", dtype={"match_id": str})
    except Exception as exc:
        return pd.DataFrame(), [], {}, [f"Não consegui ler a aba Palpites do Excel: {exc}"]

    if df.empty:
        return df, [], {}, ["A aba Palpites está vazia."]

    # Remove colunas totalmente vazias que às vezes aparecem quando o Excel é editado.
    df = df.dropna(axis=1, how="all").copy()

    required = {"match_id", "Gols mandante", "Gols visitante"}
    missing_cols = required.difference(set(df.columns))
    if missing_cols:
        return df, [], {}, ["Faltam colunas no Excel: " + ", ".join(sorted(missing_cols))]

    # Garante que cada linha seja tratada de forma independente.
    df["match_id"] = df["match_id"].astype(str).str.strip()
    df = df[df["match_id"].notna() & (df["match_id"] != "") & (
        df["match_id"].str.lower() != "nan")].copy()

    duplicated_ids = sorted(
        df.loc[df["match_id"].duplicated(), "match_id"].unique().tolist())
    if duplicated_ids:
        errors.append("Existem match_id duplicados no Excel: " +
                      ", ".join(duplicated_ids[:20]))

    matches_by_id = {}
    if not matches.empty and "match_id" in matches.columns:
        for _, match in matches.iterrows():
            matches_by_id[str(match.get("match_id")).strip()] = match.to_dict()

    def parse_excel_goal_cell(value, row_label: str, col_label: str) -> int | None:
        """Lê uma célula de gol. Aceita só inteiros 0-20.

        Valores como '2x1', '2-1', 'dois' ou negativos são erro da linha,
        não são propagados para outros jogos.
        """
        if value is None or pd.isna(value):
            return None

        text = str(value).strip()
        if text == "":
            return None

        # Excel pode ler 2.0; aceitamos quando é inteiro exato.
        try:
            number_float = float(text.replace(",", "."))
            if not number_float.is_integer():
                errors.append(
                    f"{row_label}: {col_label} precisa ser inteiro. Valor informado: {text}")
                return None
            number = int(number_float)
        except Exception:
            errors.append(
                f"{row_label}: {col_label} inválido. Use só um número de 0 a 20. Valor informado: {text}")
            return None

        if number < 0 or number > 20:
            errors.append(
                f"{row_label}: {col_label} fora do intervalo 0-20. Valor informado: {text}")
            return None

        return number

    preview_rows = []

    for excel_idx, row in df.iterrows():
        match_id = str(row.get("match_id", "")).strip()
        if not match_id:
            continue

        match = matches_by_id.get(match_id)
        if not match:
            errors.append(
                f"Linha {excel_idx + 2}: match_id não encontrado na base: {match_id}")
            continue

        home_team = match.get("home_team", row.get("Mandante", ""))
        away_team = match.get("away_team", row.get("Visitante", ""))
        stage = match.get("stage", row.get("Fase", ""))
        row_label = f"Linha {excel_idx + 2} ({match_id}) — {home_team} x {away_team}"

        if selected_stage and str(stage) != str(selected_stage):
            errors.append(
                f"{row_label}: este jogo pertence à fase {stage}, mas o template selecionado é {selected_stage}.")
            preview_rows.append(
                {
                    "Status": "Fase diferente do template",
                    "match_id": match_id,
                    "Fase": stage,
                    "Grupo": match.get("group_name", ""),
                    "Horário": format_kickoff(match.get("kickoff_at")),
                    "Jogo": f"{home_team} x {away_team}",
                    "Palpite": "",
                    "Classificado": "",
                }
            )
            continue

        if is_stage_locked(stage):
            errors.append(
                f"{row_label}: fase travada ({stage}). Esse palpite não pode mais ser alterado por importação.")
            preview_rows.append(
                {
                    "Status": "Fase travada",
                    "match_id": match_id,
                    "Fase": stage,
                    "Grupo": match.get("group_name", ""),
                    "Horário": format_kickoff(match.get("kickoff_at")),
                    "Jogo": f"{home_team} x {away_team}",
                    "Palpite": "",
                    "Classificado": "",
                }
            )
            continue

        home_goals = parse_excel_goal_cell(
            row.get("Gols mandante"), row_label, "Gols mandante")
        away_goals = parse_excel_goal_cell(
            row.get("Gols visitante"), row_label, "Gols visitante")
        selected_adv = row.get(
            "Classificado", "") if "Classificado" in df.columns else ""
        selected_adv = "" if pd.isna(
            selected_adv) else str(selected_adv).strip()

        status = "OK"
        final_adv = None

        if home_goals is None or away_goals is None:
            status = "Faltam gols ou há valor inválido"
            # Só adiciona mensagem genérica se a célula está vazia; valores inválidos já foram detalhados acima.
            if (row.get("Gols mandante") is None or pd.isna(row.get("Gols mandante")) or str(row.get("Gols mandante")).strip() == "") or (
                row.get("Gols visitante") is None or pd.isna(
                    row.get("Gols visitante")) or str(row.get("Gols visitante")).strip() == ""
            ):
                errors.append(
                    f"{row_label}: preencha Gols mandante e Gols visitante.")
        else:
            if is_knockout_stage(stage):
                final_adv = infer_advancing_team(
                    home_team, away_team, home_goals, away_goals, selected_adv)
                if not final_adv:
                    status = "Falta classificado"
                    errors.append(
                        f"{row_label}: empate em mata-mata exige Classificado.")

        preview_rows.append(
            {
                "Status": status,
                "match_id": match_id,
                "Fase": stage,
                "Grupo": match.get("group_name", ""),
                "Horário": format_kickoff(match.get("kickoff_at")),
                "Jogo": f"{home_team} x {away_team}",
                "Palpite": "" if home_goals is None or away_goals is None else f"{home_goals} x {away_goals}",
                "Classificado": final_adv or selected_adv,
            }
        )

        if status == "OK":
            payloads.append(
                {
                    "user_id": user_id,
                    "match_id": match_id,
                    "home_goals": int(home_goals),
                    "away_goals": int(away_goals),
                    "advancing_team": final_adv,
                }
            )

    try:
        if "Extras" in xls.sheet_names:
            extras = pd.read_excel(xls, sheet_name="Extras")
            if {"Campo", "Valor"}.issubset(extras.columns):
                extra_map = {
                    norm_text(row.get("Campo")): "" if pd.isna(row.get("Valor")) else str(row.get("Valor")).strip()
                    for _, row in extras.iterrows()
                }
                champion = extra_map.get(
                    "campeão") or extra_map.get("campeao") or ""
                top_scorer = extra_map.get("artilheiro") or ""
                if champion or top_scorer:
                    bonus_payload = {
                        "user_id": user_id,
                        "champion": champion or None,
                        "top_scorer": top_scorer or None,
                    }
    except Exception:
        pass

    preview = pd.DataFrame(preview_rows)
    return preview, payloads, bonus_payload, errors


def render_excel_template_import_page(user_id: str, username: str, supabase, matches: pd.DataFrame):
    st.markdown("### Template em Excel")
    st.caption(
        "Baixe e importe um template de uma fase por vez. "
        "Fases já travadas não aparecem para download e também são bloqueadas na importação."
    )

    if matches.empty or "stage" not in matches.columns:
        st.warning("Nenhuma fase encontrada na tabela de jogos.")
        return

    all_stages = sort_matches_for_display(
        matches)["stage"].dropna().drop_duplicates().tolist()
    stage_options = [
        stage for stage in all_stages if not is_stage_locked(stage)]

    if not stage_options:
        st.warning(
            "Não há fases abertas para baixar/importar template neste momento.")
        return

    selected_template_stage = st.selectbox(
        "Template para qual fase aberta?",
        stage_options,
        key="template_stage_selector",
    )

    stage_slug = re.sub(r"[^A-Za-z0-9]+", "_",
                        selected_template_stage).strip("_").lower() or "todos"

    st.download_button(
        "Baixar template selecionado",
        data=build_user_template_excel(user_id, selected_template_stage),
        file_name=f"kapitalo_cup_template_{username}_{stage_slug}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="download_prediction_template",
    )

    uploaded = st.file_uploader(
        "Importar template preenchido",
        type=["xlsx"],
        key="upload_prediction_template",
    )

    if uploaded is None:
        st.info(
            "Depois de preencher o arquivo, importe aqui para conferir antes de salvar.")
        return

    preview, payloads, bonus_payload, errors = predictions_excel_to_payloads(
        uploaded, user_id, matches, selected_template_stage)

    st.markdown("#### Conferência da importação")
    if preview.empty:
        st.warning("Não encontrei jogos válidos no arquivo importado.")
    else:
        st.dataframe(preview, use_container_width=True,
                     hide_index=True, height=460)

    if errors:
        st.error("Existem linhas para revisar. Nada será salvo enquanto houver erro.")
        st.dataframe(pd.DataFrame({"Revisar": errors}),
                     use_container_width=True, hide_index=True)
        return

    st.success(
        f"Arquivo validado: {len(payloads)} palpites prontos para salvar.")
    if bonus_payload:
        st.info("O arquivo também contém campeão/artilheiro para salvar.")

    if st.button("Salvar importação no app", use_container_width=True, key="save_prediction_template_import"):
        try:
            if payloads:
                # Guarda extra: antes de salvar, confere novamente se nenhum jogo pertence a fase travada.
                payload_match_ids = {str(item.get("match_id"))
                                     for item in payloads}
                locked_payloads = []
                for _, mrow in matches[matches["match_id"].astype(str).isin(payload_match_ids)].iterrows():
                    if is_stage_locked(mrow.get("stage", "")):
                        locked_payloads.append(
                            f"{mrow.get('home_team', '')} x {mrow.get('away_team', '')} ({mrow.get('stage', '')})")
                if locked_payloads:
                    st.error(
                        "Importação bloqueada: existem jogos de fase travada no arquivo. Nada foi salvo.")
                    st.dataframe(pd.DataFrame(
                        {"Jogos travados": locked_payloads}), use_container_width=True, hide_index=True)
                    return
                supabase.table("predictions").upsert(
                    payloads, on_conflict="user_id,match_id").execute()
            if bonus_payload:
                supabase.table("bonus_predictions").upsert(
                    bonus_payload, on_conflict="user_id").execute()
            clear_data_cache()
            st.success("Importação salva com sucesso.")
            st.rerun()
        except Exception as exc:
            st.error(f"Erro ao salvar importação: {exc}")


def build_user_predictions_overview(user_id: str, matches: pd.DataFrame) -> pd.DataFrame:
    predictions = load_table("predictions")
    bonus_predictions = load_table("bonus_predictions")

    user_predictions = pd.DataFrame()
    if not predictions.empty and "user_id" in predictions.columns:
        user_predictions = predictions[predictions["user_id"] == user_id].copy(
        )

    out = matches.copy()
    if not user_predictions.empty:
        cols = [c for c in ["match_id", "home_goals", "away_goals",
                            "advancing_team", "updated_at"] if c in user_predictions.columns]
        out = out.merge(user_predictions[cols], on="match_id", how="left")
    else:
        out["home_goals"] = pd.NA
        out["away_goals"] = pd.NA
        out["advancing_team"] = ""

    rows = []
    for _, row in sort_matches_for_display(out).iterrows():
        hg = row.get("home_goals")
        ag = row.get("away_goals")
        filled = not (pd.isna(hg) or pd.isna(ag))
        rows.append(
            {
                "Status": "Salvo" if filled else "Pendente",
                "Fase": row.get("stage", ""),
                "Grupo": row.get("group_name", ""),
                "Horário": format_kickoff(row.get("kickoff_at")),
                "Jogo": f"{row.get('home_team', '')} x {row.get('away_team', '')}",
                "Palpite": "" if not filled else f"{safe_int(hg)} x {safe_int(ag)}",
                "Classificado": row.get("advancing_team") or "",
            }
        )

    overview = pd.DataFrame(rows)

    champion = ""
    top_scorer = ""
    if not bonus_predictions.empty and "user_id" in bonus_predictions.columns:
        b = bonus_predictions[bonus_predictions["user_id"] == user_id].copy()
        if not b.empty:
            champion = b.iloc[0].get("champion") or ""
            top_scorer = b.iloc[0].get("top_scorer") or ""

    return overview, champion, top_scorer


def render_predictions_overview_page(user_id: str, matches: pd.DataFrame):
    st.markdown("### Conferência geral dos meus palpites")
    overview, champion, top_scorer = build_user_predictions_overview(
        user_id, matches)

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_box(
            "Jogos salvos", f"{int((overview['Status'] == 'Salvo').sum())}/{len(overview)}" if not overview.empty else "0/0")
    with c2:
        metric_box("Campeão", champion or "Pendente")
    with c3:
        metric_box("Artilheiro", top_scorer or "Pendente")

    status_filter = st.radio("Filtro", [
                             "Todos", "Pendentes", "Salvos"], horizontal=True, key="overview_status_filter")
    view = overview.copy()
    if status_filter == "Pendentes":
        view = view[view["Status"] == "Pendente"]
    elif status_filter == "Salvos":
        view = view[view["Status"] == "Salvo"]

    st.dataframe(view, use_container_width=True, hide_index=True, height=520)


def render_grouped_group_predictions(
    user_id: str,
    supabase,
    matches: pd.DataFrame,
    user_predictions: pd.DataFrame,
    selected_stage: str,
):
    """Modo agrupado mais leve, usando st.form para evitar rerun a cada número digitado.

    Funciona para grupos e para mata-mata. Em mata-mata, o classificado é automático
    quando há vencedor; se houver empate, o usuário escolhe quem passa.
    """
    stage_matches = sort_matches_for_display(
        matches[matches["stage"] == selected_stage].copy())
    if stage_matches.empty:
        st.info("Não há jogos nesta fase.")
        return

    is_groups = is_group_stage(selected_stage)

    st.markdown(
        """
        <div class="section-card">
            <h3 style="margin-bottom:0.25rem;">Preenchimento agrupado rápido</h3>
            <p style="color:#6b7280;margin-bottom:0;">
                Preencha vários jogos sem a página processar a cada número. Nada é salvo até clicar no botão de salvar.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_groups and "group_name" in stage_matches.columns and stage_matches["group_name"].notna().any():
        blocks = sorted(stage_matches["group_name"].dropna().unique().tolist())
        unit_label = "grupos"
    else:
        blocks = [
            f"Jogos {i + 1}-{min(i + 4, len(stage_matches))}" for i in range(0, len(stage_matches), 4)]
        unit_label = "blocos de jogos"

    # Para deixar a tela mais simples e rápida, mostramos sempre 4 grupos/blocos por página.
    blocks_per_page = 4
    total_pages = max(
        1, (len(blocks) + blocks_per_page - 1) // blocks_per_page)

    if total_pages > 1:
        page_number = st.selectbox(
            "Página",
            list(range(1, total_pages + 1)),
            format_func=lambda x: f"Página {x} de {total_pages}",
            key=f"grouped_page_number_{selected_stage}",
        )
    else:
        page_number = 1

    st.caption(f"Mostrando até 4 {unit_label} por página, em duas colunas.")

    start_idx = (page_number - 1) * blocks_per_page
    visible_blocks = blocks[start_idx:start_idx + blocks_per_page]

    invalid_rows: list[str] = []
    payload_rows: list[dict] = []
    all_group_preview: list[tuple[str, pd.DataFrame]] = []
    visible_match_count = 0

    with st.form(key=f"grouped_predictions_form_{selected_stage}_{page_number}_{blocks_per_page}"):
        cols = st.columns(2)

        for idx, block in enumerate(visible_blocks):
            with cols[idx % 2]:
                if is_groups:
                    block_matches = sort_matches_for_display(
                        stage_matches[stage_matches["group_name"] == block].copy())
                    st.markdown(f"### Grupo {block}")
                else:
                    block_start = (blocks.index(block)) * 4
                    block_matches = stage_matches.iloc[block_start:block_start + 4].copy()
                    st.markdown(f"### {block}")

                group_match_ids: list[str] = []
                preview_input_rows: list[dict] = []

                for _, match in block_matches.iterrows():
                    visible_match_count += 1
                    match_id = str(match.get("match_id", ""))
                    group_match_ids.append(match_id)
                    home_team = match.get("home_team", "")
                    away_team = match.get("away_team", "")
                    kickoff_text = format_kickoff(match.get("kickoff_at"))
                    stage = match.get("stage", selected_stage)

                    existing = pd.DataFrame()
                    if not user_predictions.empty and "match_id" in user_predictions.columns:
                        existing = user_predictions[user_predictions["match_id"].astype(
                            str) == match_id]

                    default_home = ""
                    default_away = ""
                    default_adv = ""
                    if not existing.empty:
                        default_home = str(
                            safe_int(existing.iloc[0].get("home_goals")))
                        default_away = str(
                            safe_int(existing.iloc[0].get("away_goals")))
                        default_adv = existing.iloc[0].get(
                            "advancing_team") or ""

                    st.caption(kickoff_text)
                    c_home, c_hg, c_x, c_ag, c_away = st.columns(
                        [2.6, 0.75, 0.15, 0.75, 2.6])
                    with c_home:
                        st.markdown(
                            f"<div style='font-weight:700;font-size:0.84rem;padding-top:0.3rem;'>{home_team}</div>", unsafe_allow_html=True)
                    with c_hg:
                        home_value_raw = st.text_input(
                            f"Gols mandante {match_id}",
                            value=default_home,
                            key=f"fast_home_{match_id}",
                            label_visibility="collapsed",
                            max_chars=2,
                            disabled=is_stage_locked(stage),
                        )
                    with c_x:
                        st.markdown(
                            "<div style='text-align:center;font-weight:900;padding-top:0.35rem;'>×</div>", unsafe_allow_html=True)
                    with c_ag:
                        away_value_raw = st.text_input(
                            f"Gols visitante {match_id}",
                            value=default_away,
                            key=f"fast_away_{match_id}",
                            label_visibility="collapsed",
                            max_chars=2,
                            disabled=is_stage_locked(stage),
                        )
                    with c_away:
                        st.markdown(
                            f"<div style='font-weight:700;font-size:0.84rem;padding-top:0.3rem;'>{away_team}</div>", unsafe_allow_html=True)

                    home_value = parse_score_input(home_value_raw)
                    away_value = parse_score_input(away_value_raw)
                    selected_adv = ""

                    if is_knockout_stage(stage):
                        needs_adv = home_value is not None and away_value is not None and home_value == away_value
                        if needs_adv:
                            opts = ["", home_team, away_team]
                            idx_adv = opts.index(
                                default_adv) if default_adv in opts else 0
                            selected_adv = st.selectbox(
                                f"Classificado no empate — {home_team} x {away_team}",
                                opts,
                                index=idx_adv,
                                key=f"fast_adv_{match_id}",
                                disabled=is_stage_locked(stage),
                            )
                        elif home_value is not None and away_value is not None:
                            selected_adv = infer_advancing_team(
                                home_team, away_team, home_value, away_value, None) or ""
                            st.caption(f"Classificado: {selected_adv}")
                        else:
                            selected_adv = default_adv

                    label = f"{kickoff_text} — {home_team} x {away_team}"
                    if home_value is None or away_value is None:
                        invalid_rows.append(label)
                    else:
                        final_adv = None
                        if is_knockout_stage(stage):
                            final_adv = infer_advancing_team(
                                home_team, away_team, home_value, away_value, selected_adv)
                            if not final_adv:
                                invalid_rows.append(
                                    label + " — escolha classificado")
                                continue
                        payload_rows.append(
                            {
                                "user_id": user_id,
                                "match_id": match_id,
                                "home_goals": home_value,
                                "away_goals": away_value,
                                "advancing_team": final_adv,
                            }
                        )
                        preview_input_rows.append(
                            {"match_id": match_id, "home_goals": home_value,
                                "away_goals": away_value}
                        )

                if is_groups:
                    preview_table = group_table_from_input_rows(
                        block_matches, preview_input_rows)
                    all_group_preview.append((str(block), preview_table))

        action_col1, action_col2 = st.columns([1, 2])

        with action_col1:
            refresh_preview = st.form_submit_button(
                "↻ Atualizar tabela",
                use_container_width=True,
                disabled=is_stage_locked(selected_stage),
                help="Atualiza a classificação simulada com os placares digitados, sem salvar no banco.",
            )

        with action_col2:
            submitted = st.form_submit_button(
                f"Salvar todos os jogos desta view ({visible_match_count} jogos)",
                use_container_width=True,
                disabled=is_stage_locked(selected_stage),
            )

    if refresh_preview:
        st.session_state["grouped_preview_refreshed_at"] = now_app_tz().strftime(
            "%d/%m/%Y %H:%M:%S")
        if invalid_rows:
            st.info(
                "Tabela atualizada com os placares preenchidos. Jogos ainda vazios ficam como não jogados na simulação."
            )
        else:
            st.success(
                "Tabela simulada atualizada com todos os placares desta view.")

    if submitted:
        save_prediction_payloads_or_show_errors(
            supabase,
            payload_rows,
            invalid_rows,
            "Palpites desta view salvos com sucesso.",
        )

    if all_group_preview:
        st.markdown("### Classificação simulada")
        st.caption(
            "Use o botão ↻ Atualizar tabela para recalcular a simulação com os placares digitados sem salvar no banco.")
        preview_cols = st.columns(2)
        for i, (group_name, preview_table) in enumerate(all_group_preview):
            with preview_cols[i % 2]:
                st.markdown(f"**Grupo {group_name}**")
                st.dataframe(preview_table, use_container_width=True,
                             hide_index=True, height=180)


def render_card_group_predictions(
    user_id: str,
    username: str,
    supabase,
    matches: pd.DataFrame,
    user_predictions: pd.DataFrame,
    teams: list[str],
):
    """Modo original simplificado: um grupo/jogo por vez com cards."""
    st.download_button(
        label="Baixar minhas previsões em Excel",
        data=build_user_prediction_export(user_id),
        file_name=f"kapitalo_cup_previsoes_{username}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="download_user_predictions_from_predictions_page",
    )

    stages = matches["stage"].dropna().unique(
    ).tolist() if "stage" in matches.columns else []

    if not stages:
        st.warning("A tabela de jogos não possui a coluna `stage` preenchida.")
        return

    top_col1, top_col2, top_col3 = st.columns([1.2, 1.2, 1])

    with top_col1:
        selected_stage = st.selectbox("Fase", stages, key="pred_stage")

    selected_stage_locked = is_stage_locked(selected_stage)
    render_stage_lock_message(
        selected_stage, label=f"Fase selecionada — {selected_stage}")

    filtered = matches[matches["stage"] == selected_stage].copy()

    selected_group = None

    with top_col2:
        if "group_name" in filtered.columns and filtered["group_name"].notna().any():
            groups = sorted(filtered["group_name"].dropna().unique().tolist())
            selected_group = st.selectbox("Grupo", groups, key="pred_group")
            filtered = filtered[filtered["group_name"] == selected_group]
        else:
            st.selectbox("Grupo", ["Não aplicável"],
                         disabled=True, key="pred_group_disabled")

    saved_ids = set()
    if not user_predictions.empty and "match_id" in user_predictions.columns:
        saved_ids = set(user_predictions["match_id"].astype(str).tolist())

    filtered_ids = set(filtered["match_id"].astype(
        str).tolist()) if "match_id" in filtered.columns else set()
    saved_in_screen = len(saved_ids.intersection(filtered_ids))
    total_in_screen = len(filtered)

    with top_col3:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <span class="pill pill-red">{total_in_screen} jogos</span>
            <span class="pill pill-green">{saved_in_screen} salvos</span>
            """,
            unsafe_allow_html=True,
        )

    filtered = sort_matches_for_display(filtered)

    visible_prediction_rows = [
        {
            "match_id": match["match_id"],
            "stage": match.get("stage", selected_stage),
            "home_team": match.get("home_team", ""),
            "away_team": match.get("away_team", ""),
            "match_no": match.get("match_no", ""),
            "label": (
                f"{format_kickoff(match.get('kickoff_at'))} — "
                f"{match.get('home_team', '')} x {match.get('away_team', '')}"
            ),
        }
        for _, match in filtered.iterrows()
    ]

    save_scope_label = f"Grupo {selected_group}" if selected_group and is_group_stage(
        selected_stage) else "jogos desta tela"

    with st.container(border=True):
        st.markdown(f"#### Salvar todos os palpites — {save_scope_label}")
        st.caption(
            "Preencha os placares visíveis abaixo e salve tudo de uma vez. "
            "Se algo estiver incompleto, o app só avisa o que falta e mantém a tela aberta."
        )

        if st.button(
            f"Salvar todos os palpites de {save_scope_label}",
            key=f"save_all_top_{selected_stage}_{selected_group or 'all'}",
            use_container_width=True,
            disabled=selected_stage_locked or filtered.empty,
        ):
            if is_stage_locked(selected_stage):
                st.error(
                    f"Não é possível alterar estes jogos. O prazo de {selected_stage} encerrou em {stage_lock_text(selected_stage)}."
                )
                return

            invalid_rows, payload_rows = build_prediction_payloads_from_state(
                visible_prediction_rows,
                user_id,
            )
            save_prediction_payloads_or_show_errors(
                supabase,
                payload_rows,
                invalid_rows,
                f"Todos os palpites de {save_scope_label} foram salvos.",
            )

    if selected_group:
        st.markdown(f"### Grupo {selected_group}")

    if selected_group and not filtered.empty and is_group_stage(selected_stage):
        with st.expander("Tabela simulada do grupo com seus palpites salvos", expanded=True):
            group_table = simulate_group_table(filtered, user_predictions)
            st.dataframe(group_table, use_container_width=True,
                         hide_index=True)

    for _, match in filtered.iterrows():
        match_id = match["match_id"]
        match_id_str = str(match_id)
        stage = match.get("stage", selected_stage)
        match_locked = is_stage_locked(stage)
        home_team = match["home_team"]
        away_team = match["away_team"]
        group_name = match.get("group_name", "")
        kickoff_text = format_kickoff(match.get("kickoff_at"))

        existing = pd.DataFrame()

        if not user_predictions.empty:
            existing = user_predictions[user_predictions["match_id"] == match_id]

        default_home = None
        default_away = None
        default_advancing = ""

        if not existing.empty:
            default_home = safe_int(
                existing.iloc[0].get("home_goals"), default=None)
            default_away = safe_int(
                existing.iloc[0].get("away_goals"), default=None)
            default_advancing = existing.iloc[0].get("advancing_team") or ""

        st.divider()

        lock_badge = '<span class="pill pill-red">Travado</span>' if match_locked else '<span class="pill pill-green">Aberto</span>'

        st.markdown(
            f"""
            <div class="match-title">{home_team} x {away_team}</div>
            <div class="match-meta">
                {kickoff_text} {f"• Grupo {group_name}" if group_name else ""} &nbsp; {lock_badge}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if is_knockout_stage(stage):
            col1, col2, col3, col4, col5 = st.columns(
                [0.55, 0.08, 0.55, 0.9, 0.5])
        else:
            col1, col2, col3, col5 = st.columns([0.55, 0.08, 0.55, 0.5])

        with col1:
            home_goals = st.number_input(
                home_team,
                min_value=0,
                max_value=20,
                value=default_home,
                step=1,
                key=f"pred_home_{match_id}",
                disabled=match_locked,
            )

        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                "<div style='text-align:center;font-weight:900;font-size:1.15rem;color:#111827;'>×</div>",
                unsafe_allow_html=True,
            )

        with col3:
            away_goals = st.number_input(
                away_team,
                min_value=0,
                max_value=20,
                value=default_away,
                step=1,
                key=f"pred_away_{match_id}",
                disabled=match_locked,
            )

        advancing_team = None

        if is_knockout_stage(stage):
            with col4:
                inferred_advancing = infer_advancing_team(
                    home_team, away_team, home_goals, away_goals, default_advancing)

                if home_goals is not None and away_goals is not None and safe_int(home_goals) != safe_int(away_goals):
                    advancing_team = inferred_advancing
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(f"**Classificado:** {advancing_team}")
                else:
                    advancing_options = ["", home_team, away_team]
                    advancing_index = 0

                    if default_advancing in advancing_options:
                        advancing_index = advancing_options.index(
                            default_advancing)

                    advancing_team = st.selectbox(
                        "Classificado se empatar",
                        advancing_options,
                        index=advancing_index,
                        key=f"pred_adv_{match_id}",
                        disabled=match_locked,
                    )

        with col5:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(
                "Salvar",
                key=f"save_pred_{match_id}",
                use_container_width=True,
                disabled=match_locked,
            ):
                if is_stage_locked(stage):
                    st.error(
                        f"Não é possível alterar este jogo. O prazo de {stage} encerrou em {stage_lock_text(stage)}.")
                    return

                if home_goals is None or away_goals is None:
                    st.error(
                        f"Preencha o placar de {home_team} x {away_team} antes de salvar.")
                    return

                final_advancing = None
                if is_knockout_stage(stage):
                    final_advancing = infer_advancing_team(
                        home_team, away_team, home_goals, away_goals, advancing_team)
                    if not final_advancing:
                        st.error(
                            "Como o palpite está empatado, selecione quem se classifica antes de salvar.")
                        return

                payload = {
                    "user_id": user_id,
                    "match_id": match_id,
                    "home_goals": int(home_goals),
                    "away_goals": int(away_goals),
                    "advancing_team": final_advancing,
                }

                try:
                    supabase.table("predictions").upsert(
                        payload,
                        on_conflict="user_id,match_id",
                    ).execute()

                    clear_data_cache()
                    st.success("Palpite salvo.")
                    st.rerun()

                except Exception as exc:
                    st.error(f"Erro ao salvar palpite: {exc}")

        if match_id_str in saved_ids:
            status_pill("Salvo", "green")


def render_match_predictions_page():
    if not st.session_state.get("is_logged_in", False):
        st.warning("Você precisa fazer login para registrar palpites.")
        return

    user_id = st.session_state["user_id"]
    username = st.session_state.get("username", "")
    supabase = get_client()
    matches = sort_matches_for_display(
        load_table("matches", order_by="match_no"))

    if matches.empty:
        st.warning(
            "Nenhum jogo encontrado. Rode o seed com `python -m src.seed`.")
        return

    teams = get_all_teams(matches)
    predictions = load_table("predictions")

    if not predictions.empty and "user_id" in predictions.columns:
        user_predictions = predictions[predictions["user_id"] == user_id].copy(
        )
    else:
        user_predictions = pd.DataFrame()

    st.markdown(
        """
        <div class="section-card">
            <h3 style="margin-bottom:0.25rem;">Meus palpites</h3>
            <p style="color:#6b7280;margin-bottom:0;">
                Preencha pelo app, use o modo agrupado rápido ou baixe/importe um template em Excel.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Campeão e artilheiro", expanded=True):
        render_bonus_predictions_section(
            user_id, teams, supabase, key_suffix="top")

    main_tab_app, main_tab_excel, main_tab_overview = st.tabs(
        ["Preencher no app", "Excel template", "Conferência geral"]
    )

    with main_tab_excel:
        render_excel_template_import_page(user_id, username, supabase, matches)

    with main_tab_overview:
        render_predictions_overview_page(user_id, matches)

    with main_tab_app:
        stages = matches["stage"].dropna().unique(
        ).tolist() if "stage" in matches.columns else []

        if not stages:
            st.warning(
                "A tabela de jogos não possui a coluna `stage` preenchida.")
            return

        fill_mode = st.radio(
            "Modo de preenchimento",
            ["Preenchimento agrupado rápido", "Por grupo / jogo a jogo"],
            horizontal=True,
            key="prediction_fill_mode",
        )

        selected_stage = st.selectbox(
            "Fase", stages, key="prediction_stage_main")
        render_stage_lock_message(
            selected_stage, label=f"Fase selecionada — {selected_stage}")

        if fill_mode == "Preenchimento agrupado rápido":
            render_grouped_group_predictions(
                user_id, supabase, matches, user_predictions, selected_stage)
        else:
            # Mantém o modo antigo de cards para revisão jogo a jogo.
            st.session_state["pred_stage"] = selected_stage
            render_card_group_predictions(
                user_id, username, supabase, matches, user_predictions, teams)

    # Botão final de "Salvar todos" removido/comentado a pedido.
    # Mantemos apenas os botões no topo do modo por grupo e no fim do bloco agrupado.


def render_predictions_page():
    """Página única de palpites.

    Não existe mais seleção manual de classificados por fase.
    Campeão/artilheiro aparecem no topo da fase de grupos e,
    no mata-mata, o classificado é consequência do placar salvo em cada jogo.
    """
    render_match_predictions_page()

# ============================================================
# PÁGINA: CLASSIFICADOS E EXTRAS
# ============================================================


def render_phase_predictions_page():
    if not st.session_state.get("is_logged_in", False):
        st.warning(
            "Você precisa fazer login para preencher classificados e extras.")
        return

    user_id = st.session_state["user_id"]
    username = st.session_state.get("username", "")
    supabase = get_client()
    matches = load_table("matches", order_by="match_no")
    teams = get_all_teams(matches)

    if not teams:
        st.warning("Nenhuma seleção encontrada. Rode o seed dos jogos primeiro.")
        return

    st.markdown(
        """
        <div class="section-card">
            <h3 style="margin-bottom:0.25rem;">Classificados e extras</h3>
            <p style="color:#6b7280;margin-bottom:0;">
                Use esta aba para prever classificados por fase, campeão e artilheiro.
                Depois do prazo, suas previsões ficam disponíveis apenas para consulta e exportação.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.download_button(
        label="Baixar minhas previsões em Excel",
        data=build_user_prediction_export(user_id),
        file_name=f"kapitalo_cup_previsoes_{username}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="download_user_predictions_from_phase_page",
    )

    phase_config = {
        "Oitavas": 16,
        "Quartas": 8,
        "Semis": 4,
        "Final": 2,
    }

    existing_phase = load_table("phase_predictions")

    if not existing_phase.empty and "user_id" in existing_phase.columns:
        existing_phase = existing_phase[existing_phase["user_id"] == user_id].copy(
        )
    else:
        existing_phase = pd.DataFrame()

    selected_phase = st.selectbox(
        "Fase para preencher",
        list(phase_config.keys()),
        key="selected_phase_predictions",
    )

    phase_locked = is_stage_locked(selected_phase)
    render_stage_lock_message(
        selected_phase, label=f"Classificados — {selected_phase}")

    max_teams = phase_config[selected_phase]

    default_selected = set()

    if not existing_phase.empty:
        default_selected = set(
            existing_phase[existing_phase["phase"]
                           == selected_phase]["team"].tolist()
        )

    st.markdown(f"### {selected_phase}")
    st.caption(f"Selecione até {max_teams} seleções.")

    selected_teams = []

    cols_per_row = 4
    cols = st.columns(cols_per_row)

    for i, team in enumerate(teams):
        col = cols[i % cols_per_row]

        with col:
            checked = st.checkbox(
                team,
                value=team in default_selected,
                key=f"phase_checkbox_{selected_phase}_{team}",
                disabled=phase_locked,
            )

            if checked:
                selected_teams.append(team)

    selected_count = len(selected_teams)

    st.markdown(f"**Selecionados:** {selected_count} / {max_teams}")

    if selected_count > max_teams:
        st.error(
            f"Você selecionou {selected_count} seleções, mas o máximo para "
            f"{selected_phase} é {max_teams}."
        )

    col_save, col_clear = st.columns([1, 1])

    with col_save:
        if st.button(
            f"Salvar {selected_phase}",
            key=f"save_phase_checkbox_{selected_phase}",
            disabled=phase_locked or selected_count > max_teams,
            use_container_width=True,
        ):
            if is_stage_locked(selected_phase):
                st.error(
                    f"Não é possível alterar {selected_phase}. O prazo encerrou em {stage_lock_text(selected_phase)}.")
                st.stop()

            try:
                supabase.table("phase_predictions").delete().eq(
                    "user_id", user_id
                ).eq(
                    "phase", selected_phase
                ).execute()

                rows = [
                    {
                        "user_id": user_id,
                        "phase": selected_phase,
                        "team": team,
                    }
                    for team in selected_teams
                ]

                if rows:
                    supabase.table("phase_predictions").insert(rows).execute()

                clear_data_cache()
                st.success(f"{selected_phase} salvo com sucesso.")
                st.rerun()

            except Exception as exc:
                st.error(f"Erro ao salvar {selected_phase}: {exc}")

    with col_clear:
        if st.button(
            f"Limpar seleção de {selected_phase}",
            key=f"clear_phase_{selected_phase}",
            use_container_width=True,
            disabled=phase_locked,
        ):
            for team in teams:
                key = f"phase_checkbox_{selected_phase}_{team}"
                if key in st.session_state:
                    st.session_state[key] = False

            st.rerun()

    st.divider()

    st.subheader("Resumo salvo")

    updated_phase = load_table("phase_predictions")

    if not updated_phase.empty and "user_id" in updated_phase.columns:
        updated_phase = updated_phase[updated_phase["user_id"] == user_id].copy(
        )

    if updated_phase.empty:
        st.info("Você ainda não salvou classificados.")
    else:
        summary = (
            updated_phase
            .groupby("phase")["team"]
            .apply(lambda x: ", ".join(sorted(x)))
            .reset_index()
            .rename(columns={"phase": "Fase", "team": "Seleções"})
        )

        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Extras")

    existing_bonus = load_table("bonus_predictions")

    if not existing_bonus.empty and "user_id" in existing_bonus.columns:
        user_bonus = existing_bonus[existing_bonus["user_id"] == user_id].copy(
        )
    else:
        user_bonus = pd.DataFrame()

    default_champion = ""
    default_top_scorer = ""

    if not user_bonus.empty:
        default_champion = user_bonus.iloc[0].get("champion") or ""
        default_top_scorer = user_bonus.iloc[0].get("top_scorer") or ""

    champion_options = [""] + teams
    champion_index = champion_options.index(
        default_champion) if default_champion in champion_options else 0

    extras_locked = is_stage_locked("extras")
    render_stage_lock_message("extras", label="Extras — campeão e artilheiro")

    col1, col2 = st.columns(2)

    with col1:
        champion = st.selectbox(
            "Campeão",
            champion_options,
            index=champion_index,
            key="bonus_champion",
            disabled=extras_locked,
        )

    with col2:
        top_scorer = st.text_input(
            "Artilheiro",
            value=default_top_scorer,
            key="bonus_top_scorer",
            disabled=extras_locked,
        )

    if st.button(
        "Salvar extras",
        key="save_bonus",
        use_container_width=True,
        disabled=extras_locked,
    ):
        if is_stage_locked("extras"):
            st.error(
                f"Não é possível alterar extras. O prazo encerrou em {stage_lock_text('extras')}.")
            st.stop()

        payload = {
            "user_id": user_id,
            "champion": champion if champion else None,
            "top_scorer": top_scorer.strip() if top_scorer else None,
        }

        try:
            supabase.table("bonus_predictions").upsert(
                payload,
                on_conflict="user_id",
            ).execute()

            clear_data_cache()
            st.success("Extras salvos.")
            st.rerun()

        except Exception as exc:
            st.error(f"Erro ao salvar extras: {exc}")


# ============================================================
# PÁGINA: REGRAS
# ============================================================


def render_rules_page():
    hero(
        "Regras da Kapitalo Cup",
        "Pontue acertando resultados, placares exatos, classificados em jogos de mata-mata, campeão e artilheiro.",
    )

    rules = pd.DataFrame(
        [
            {
                "Fase": "Primeira Fase / Grupos",
                "Jogos": 72,
                "Resultado": 7,
                "Placar exato": "+7",
                "Classificado": 0,
                "Total possível": 1008,
            },
            {
                "Fase": "16-avos de Final",
                "Jogos": 16,
                "Resultado": 10,
                "Placar exato": "+10",
                "Classificado": 10,
                "Total possível": 480,
            },
            {
                "Fase": "Oitavas de Final",
                "Jogos": 8,
                "Resultado": 12,
                "Placar exato": "+12",
                "Classificado": 12,
                "Total possível": 288,
            },
            {
                "Fase": "Quartas de Final",
                "Jogos": 4,
                "Resultado": 15,
                "Placar exato": "+15",
                "Classificado": 15,
                "Total possível": 180,
            },
            {
                "Fase": "Semifinais",
                "Jogos": 2,
                "Resultado": 20,
                "Placar exato": "+20",
                "Classificado": 20,
                "Total possível": 120,
            },
            {
                "Fase": "3º e 4º Lugar",
                "Jogos": 1,
                "Resultado": 15,
                "Placar exato": "+15",
                "Classificado": 15,
                "Total possível": 45,
            },
            {
                "Fase": "Final",
                "Jogos": 1,
                "Resultado": 25,
                "Placar exato": "+25",
                "Classificado": 25,
                "Total possível": 75,
            },
            {
                "Fase": "Extras",
                "Jogos": 0,
                "Resultado": "-",
                "Placar exato": "-",
                "Classificado": "-",
                "Total possível": 200,
            },
        ]
    )

    st.markdown("### Pontuação por fase")
    st.dataframe(rules, use_container_width=True, hide_index=True)

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="rules-card">
            <h3>Resultado</h3>
            <p>Você pontua se acertar vitória, empate ou derrota.</p>
            <p>Na fase de grupos, não há pontos por classificação.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="rules-card">
            <h3>Mata-mata</h3>
            <p>O classificado é consequência do seu palpite do jogo.</p>
            <p>Se você colocar empate, precisa escolher quem passa.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="rules-card">
            <h3>Extras</h3>
            <p><b>Campeão:</b> 100 pontos</p>
            <p><b>Artilheiro:</b> 100 pontos</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================================
# PÁGINA: ADMIN
# ============================================================


def render_admin_page():
    if not is_admin():
        st.error("Área restrita ao administrador.")
        return

    st.markdown(
        """
        <div class="section-card">
            <h3 style="margin-bottom:0.25rem;">Painel do administrador</h3>
            <p style="color:#6b7280;margin-bottom:0;">
                Cadastre resultados oficiais, envie mensagens para o Google Chat, registre extras reais e exporte todas as previsões.
                Classificados de mata-mata são definidos pelo resultado oficial de cada jogo.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.download_button(
        label="Baixar todas as previsões dos usuários em Excel",
        data=build_all_users_predictions_export(),
        file_name="kapitalo_cup_todas_previsoes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="admin_download_all_predictions",
    )

    supabase = get_client()
    matches = sort_matches_for_display(
        load_table("matches", order_by="match_no"))

    if matches.empty:
        st.warning("Nenhum jogo encontrado.")
        return

    tab_results, tab_chat, tab_bonus_actuals = st.tabs(
        [
            "Resultados dos jogos",
            "Google Chat",
            "Extras reais",
        ]
    )

    with tab_results:
        st.markdown("### Resultados oficiais")

        actuals = load_table("actual_results")

        top_col1, top_col2, top_col3 = st.columns([1.2, 1.2, 1])

        stages = matches["stage"].dropna().unique().tolist()

        with top_col1:
            selected_stage = st.selectbox("Fase", stages, key="admin_stage")

        filtered = matches[matches["stage"] == selected_stage].copy()

        with top_col2:
            if "group_name" in filtered.columns and filtered["group_name"].notna().any():
                groups = sorted(
                    filtered["group_name"].dropna().unique().tolist())
                selected_group = st.selectbox(
                    "Grupo", groups, key="admin_group")
                filtered = filtered[filtered["group_name"] == selected_group]
            else:
                st.selectbox("Grupo", ["Não aplicável"],
                             disabled=True, key="admin_group_disabled")

        with top_col3:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <span class="pill pill-red">{len(filtered)} jogos nesta tela</span>
                """,
                unsafe_allow_html=True,
            )

        filtered = sort_matches_for_display(filtered)

        for _, match in filtered.iterrows():
            match_id = match["match_id"]
            stage = match.get("stage", selected_stage)
            home_team = match["home_team"]
            away_team = match["away_team"]
            match_no = match.get("match_no", "")
            kickoff_text = format_kickoff(match.get("kickoff_at"))

            existing = pd.DataFrame()

            if not actuals.empty and "match_id" in actuals.columns:
                existing = actuals[actuals["match_id"] == match_id]

            default_home = 0
            default_away = 0
            default_advancing = ""

            if not existing.empty:
                default_home = safe_int(existing.iloc[0].get("home_goals"))
                default_away = safe_int(existing.iloc[0].get("away_goals"))
                default_advancing = existing.iloc[0].get(
                    "advancing_team") or ""

            st.divider()

            st.markdown(
                f"""
                <div class="match-title">{home_team} x {away_team}</div>
                <div class="match-meta">{kickoff_text}</div>
                """,
                unsafe_allow_html=True,
            )

            if is_knockout_stage(stage):
                col1, col2, col3, col4 = st.columns([0.8, 0.10, 0.8, 1.0])
            else:
                col1, col2, col3 = st.columns([0.8, 0.10, 0.8])

            with col1:
                home_goals = st.number_input(
                    f"Gols {home_team}",
                    min_value=0,
                    max_value=20,
                    value=default_home,
                    step=1,
                    key=f"actual_home_{match_id}",
                )

            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    "<div style='text-align:center;font-weight:900;font-size:1.35rem;color:#111827;'>×</div>",
                    unsafe_allow_html=True,
                )

            with col3:
                away_goals = st.number_input(
                    f"Gols {away_team}",
                    min_value=0,
                    max_value=20,
                    value=default_away,
                    step=1,
                    key=f"actual_away_{match_id}",
                )

            advancing_team = None

            if is_knockout_stage(stage):
                with col4:
                    inferred_advancing = infer_advancing_team(
                        home_team, away_team, home_goals, away_goals, default_advancing)

                    if safe_int(home_goals) != safe_int(away_goals):
                        advancing_team = inferred_advancing
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.markdown(f"**Classificado:** {advancing_team}")
                        st.caption("Definido automaticamente pelo resultado.")
                    else:
                        advancing_options = ["", home_team, away_team]
                        advancing_index = 0

                        if default_advancing in advancing_options:
                            advancing_index = advancing_options.index(
                                default_advancing)

                        advancing_team = st.selectbox(
                            "Classificado se empatar",
                            advancing_options,
                            index=advancing_index,
                            key=f"actual_adv_{match_id}",
                        )
            else:
                pass

            save_col1, save_col2 = st.columns([1, 4])

            with save_col1:
                if st.button("Salvar", key=f"save_actual_{match_id}", use_container_width=True):
                    final_advancing = None
                    if is_knockout_stage(stage):
                        final_advancing = infer_advancing_team(
                            home_team, away_team, home_goals, away_goals, advancing_team)
                        if not final_advancing:
                            st.error(
                                "Como o resultado está empatado, selecione o classificado antes de salvar.")
                            st.stop()

                    payload = {
                        "match_id": match_id,
                        "home_goals": int(home_goals),
                        "away_goals": int(away_goals),
                        "advancing_team": final_advancing,
                    }

                    try:
                        supabase.table("actual_results").upsert(
                            payload,
                            on_conflict="match_id",
                        ).execute()

                        clear_data_cache()
                        st.success("Resultado oficial salvo.")
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Erro ao salvar resultado: {exc}")

            with save_col2:
                if not existing.empty:
                    status_pill("Resultado já cadastrado", "green")
                else:
                    status_pill("Resultado pendente")

    with tab_chat:
        render_google_chat_admin_page(matches)

    with tab_bonus_actuals:
        st.markdown("### Extras reais")

        teams = get_all_teams(matches)

        bonus_actuals = load_table("bonus_actuals")

        default_champion = ""
        default_top_scorer = ""

        if not bonus_actuals.empty:
            default_champion = bonus_actuals.iloc[0].get("champion") or ""
            default_top_scorer = bonus_actuals.iloc[0].get("top_scorer") or ""

        champion_options = [""] + teams
        champion_index = champion_options.index(
            default_champion) if default_champion in champion_options else 0

        col1, col2 = st.columns(2)

        with col1:
            champion = st.selectbox(
                "Campeão real",
                champion_options,
                index=champion_index,
                key="actual_bonus_champion",
            )

        with col2:
            top_scorer = st.text_input(
                "Artilheiro real",
                value=default_top_scorer,
                key="actual_bonus_top_scorer",
            )

        if st.button("Salvar extras reais", key="save_actual_bonus", use_container_width=True):
            payload = {
                "id": 1,
                "champion": champion if champion else None,
                "top_scorer": top_scorer.strip() if top_scorer else None,
            }

            try:
                supabase.table("bonus_actuals").upsert(
                    payload,
                    on_conflict="id",
                ).execute()

                clear_data_cache()
                st.success("Extras reais salvos.")
                st.rerun()

            except Exception as exc:
                st.error(f"Erro ao salvar extras reais: {exc}")

# ============================================================
# APP PRINCIPAL
# ============================================================


def main():
    is_logged_in = st.session_state.get("is_logged_in", False)

    if not is_logged_in:
        render_auth_sidebar()

        hero(
            "Kapitalo Cup",
            "O bolão da Copa do Mundo 2026. Faça login para registrar seus palpites.",
        )

        st.markdown(
            """
            <div class="section-card">
                <h3 style="margin-bottom:0.25rem;">Bem-vindo à Kapitalo Cup</h3>
                <p style="color:#6b7280;margin-bottom:0;">
                    Faça login ou crie seu usuário no menu lateral para acessar seus palpites,
                    pendências, ranking e exportações. Para deixar o carregamento inicial mais rápido,
                    o ranking só é carregado quando você clicar no botão abaixo.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_regras, tab_ranking = st.tabs(["Regras", "Ranking"])

        with tab_regras:
            render_rules_page()

        with tab_ranking:
            st.info(
                "O ranking consulta o banco e pode levar alguns segundos. "
                "Clique no botão abaixo apenas quando quiser carregar a classificação."
            )
            if st.button("Carregar ranking", key="load_public_ranking", use_container_width=True):
                render_ranking()

        return

    page = render_logged_sidebar()

    if page == "Início":
        hero(
            "Painel da Kapitalo Cup",
            "Veja o que falta preencher, acompanhe os prazos e exporte suas previsões.",
        )
        render_home_page()

    elif page == "Ranking":
        hero(
            "Ranking da Kapitalo Cup",
            "Acompanhe a classificação geral e veja onde cada jogador ganhou seus pontos.",
        )
        render_ranking()

    elif page == "Meus palpites":
        hero(
            "Meus palpites",
            "Preencha seus placares por grupo. Classificado só aparece em jogos de mata-mata.",
        )
        render_predictions_page()

    elif page == "Regras":
        render_rules_page()

    elif page == "Admin":
        hero(
            "Admin da Kapitalo Cup",
            "Atualize resultados oficiais, classificados reais, extras e exporte as previsões.",
        )
        render_admin_page()


if __name__ == "__main__":
    main()
