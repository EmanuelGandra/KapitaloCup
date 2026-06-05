from pathlib import Path
import base64
import io
import re
from datetime import datetime

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

    div[data-testid="stNumberInput"] input {{
        text-align: center;
        font-weight: 900;
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

@st.cache_data(ttl=300, show_spinner=False)
def cached_table(table_name: str, order_by: str | None = None) -> pd.DataFrame:
    try:
        return fetch_df(table_name, order_by=order_by)
    except Exception:
        return pd.DataFrame()


def clear_data_cache():
    cached_table.clear()
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


def stage_points_for_match(stage: str) -> dict:
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
    phase = norm_text(phase)

    if (
        "dezesseis" in phase
        or "16 avos" in phase
        or "16avos" in phase
        or "round of 32" in phase
        or "r32" in phase
        or "32" in phase
    ):
        return 10

    if (
        "oitavas" in phase
        or "8 avos" in phase
        or "8avos" in phase
        or "round of 16" in phase
        or "r16" in phase
    ):
        return 12

    if "quartas" in phase:
        return 15

    if "semis" in phase or "semi" in phase:
        return 20

    if "terceiro" in phase or "3" in phase:
        return 15

    if "final" in phase:
        return 25

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
        return pd.to_datetime(raw_value)
    except Exception:
        return pd.to_datetime(default_value)


def is_stage_locked(stage_or_phase: str) -> bool:
    return pd.Timestamp(datetime.now()) >= get_stage_lock_at(stage_or_phase)


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
    now = pd.Timestamp(datetime.now())
    future_rows = []

    for lock_key in DEFAULT_STAGE_LOCKS:
        lock_at = get_stage_lock_at(lock_key)
        if lock_at > now:
            future_rows.append((lock_key, lock_at))

    if not future_rows:
        return None

    return sorted(future_rows, key=lambda item: item[1])[0]


def build_lock_schedule_df() -> pd.DataFrame:
    now = pd.Timestamp(datetime.now())
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
    """Formata o horário salvo no Supabase em horário do Brasil/São Paulo.

    O campo kickoff_at está sendo salvo como timestamp local do Brasil, sem
    conversão de timezone. Por isso, aqui apenas formatamos o valor.
    """
    if value is None or pd.isna(value) or str(value).strip() == "":
        return "Horário a definir"

    dt = pd.to_datetime(value, errors="coerce")

    if pd.isna(dt):
        return "Horário a definir"

    return dt.strftime("%d/%m/%Y %H:%M")


def sort_matches_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Ordena jogos por horário de realização e usa match_no como desempate.

    Jogos sem kickoff_at ficam no final.
    """
    if df.empty:
        return df

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
    matches = load_table("matches", order_by="match_no")
    matches = sort_matches_for_display(matches)
    predictions = load_table("predictions")
    phase_predictions = load_table("phase_predictions")
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

        ordered_cols = [
            col
            for col in [
                "match_no",
                "stage",
                "group_name",
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
                "home_team",
                "away_team",
                "home_goals",
                "away_goals",
                "advancing_team",
                "updated_at",
                "match_id",
            ]
        )

    if not phase_predictions.empty and "user_id" in phase_predictions.columns:
        classificados = phase_predictions[phase_predictions["user_id"] == user_id].copy(
        )
    else:
        classificados = pd.DataFrame(columns=["phase", "team"])

    if not bonus_predictions.empty and "user_id" in bonus_predictions.columns:
        extras = bonus_predictions[bonus_predictions["user_id"] == user_id].copy(
        )
    else:
        extras = pd.DataFrame(columns=["champion", "top_scorer"])

    pending_matches, pending_extras = build_missing_items_for_user(user_id)

    return create_excel_bytes(
        {
            "Palpites jogos": jogos,
            "Classificados": classificados,
            "Extras": extras,
            "Pendencias jogos": pending_matches,
            "Pendencias extras": pending_extras,
        }
    )


def build_all_users_predictions_export() -> bytes:
    profiles = load_table("profiles")
    matches = load_table("matches", order_by="match_no")
    matches = sort_matches_for_display(matches)
    predictions = load_table("predictions")
    phase_predictions = load_table("phase_predictions")
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

                for _, row in user_pred.iterrows():
                    rows.append(
                        {
                            "Tipo": "Jogo",
                            "Fase": row.get("stage", ""),
                            "Grupo": row.get("group_name", ""),
                            "Jogo": f"{row.get('home_team', '')} x {row.get('away_team', '')}",
                            "Horário": format_kickoff(row.get("kickoff_at")),
                            "Seleção/Item": "",
                            "Gols casa": row.get("home_goals", ""),
                            "Gols fora": row.get("away_goals", ""),
                            "Classificado/Campeão": row.get("advancing_team", ""),
                            "Artilheiro": "",
                            "Atualizado em": row.get("updated_at", ""),
                            "match_id": row.get("match_id", ""),
                            "match_no": row.get("match_no", ""),
                        }
                    )

        if not phase_predictions.empty and "user_id" in phase_predictions.columns:
            user_phase = phase_predictions[phase_predictions["user_id"] == user_id].copy(
            )

            for _, row in user_phase.iterrows():
                rows.append(
                    {
                        "Tipo": "Classificado",
                        "Fase": row.get("phase", ""),
                        "Grupo": "",
                        "Jogo": "",
                        "Seleção/Item": row.get("team", ""),
                        "Gols casa": "",
                        "Gols fora": "",
                        "Classificado/Campeão": "",
                        "Artilheiro": "",
                        "Atualizado em": "",
                        "match_id": "",
                        "match_no": "",
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
                        "Jogo": "",
                        "Seleção/Item": "",
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
    matches = load_table("matches", order_by="match_no")
    matches = sort_matches_for_display(matches)
    predictions = load_table("predictions")
    phase_predictions = load_table("phase_predictions")
    bonus_predictions = load_table("bonus_predictions")

    if matches.empty:
        pending_matches = pd.DataFrame(
            columns=["Fase", "Grupo", "Jogo", "match_id"])
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

    phase_config = {
        "16-avos": 32,
        "Oitavas": 16,
        "Quartas": 8,
        "Semis": 4,
        "Final": 2,
    }

    extras_rows = []

    if not phase_predictions.empty and "user_id" in phase_predictions.columns:
        user_phase = phase_predictions[phase_predictions["user_id"] == user_id].copy(
        )
    else:
        user_phase = pd.DataFrame()

    for phase, expected_count in phase_config.items():
        selected_count = 0

        if not user_phase.empty:
            selected_count = len(user_phase[user_phase["phase"] == phase])

        if selected_count < expected_count:
            extras_rows.append(
                {
                    "Tipo": "Classificados",
                    "Item": phase,
                    "Status": f"Faltam {expected_count - selected_count} de {expected_count}",
                    "Prazo": stage_lock_text(phase),
                    "Status prazo": "Travado" if is_stage_locked(phase) else "Aberto",
                }
            )

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
        extras_rows.append({"Tipo": "Extra", "Item": "Campeão", "Status": "Pendente", "Prazo": stage_lock_text(
            "extras"), "Status prazo": "Travado" if is_stage_locked("extras") else "Aberto"})

    if not scorer_ok:
        extras_rows.append({"Tipo": "Extra", "Item": "Artilheiro", "Status": "Pendente", "Prazo": stage_lock_text(
            "extras"), "Status prazo": "Travado" if is_stage_locked("extras") else "Aberto"})

    pending_extras = pd.DataFrame(extras_rows)

    return pending_matches.reset_index(drop=True), pending_extras.reset_index(drop=True)


def simulate_group_table(group_matches: pd.DataFrame, user_predictions: pd.DataFrame) -> pd.DataFrame:
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

    if user_predictions.empty:
        return pd.DataFrame(table.values()).sort_values(["Pts", "SG", "GP"], ascending=[False, False, False])

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
    df["SG"] = df["GP"] - df["GC"]
    df = df.sort_values(["Pts", "SG", "GP", "Seleção"], ascending=[
                        False, False, False, True]).reset_index(drop=True)
    df.insert(0, "Pos", df.index + 1)

    return df


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
                            "Categoria": "Jogo",
                            "Fase": row.get("stage", ""),
                            "Item": match_label,
                            "Detalhe": f"Classificado correto: {row.get('advancing_team_pred')}",
                            "Pontos": stage_points["qualified"],
                        }
                    )

    if (
        not phase_predictions.empty
        and not phase_actuals.empty
        and {"phase", "team"}.issubset(phase_predictions.columns)
        and {"phase", "team"}.issubset(phase_actuals.columns)
    ):
        user_phase = phase_predictions[phase_predictions["user_id"] == user_id].copy(
        )

        if not user_phase.empty:
            pp = user_phase.copy()
            pa = phase_actuals.copy()

            pp["phase_norm"] = pp["phase"].apply(norm_text)
            pp["team_norm"] = pp["team"].apply(norm_text)
            pa["phase_norm"] = pa["phase"].apply(norm_text)
            pa["team_norm"] = pa["team"].apply(norm_text)

            merged_phase = pp.merge(
                pa[["phase_norm", "team_norm"]],
                on=["phase_norm", "team_norm"],
                how="inner",
            )

            for _, row in merged_phase.iterrows():
                pts = points_for_phase_prediction(row.get("phase", ""))

                if pts > 0:
                    rows.append(
                        {
                            "Categoria": "Classificados",
                            "Fase": row.get("phase", ""),
                            "Item": row.get("team", ""),
                            "Detalhe": "Seleção classificada corretamente",
                            "Pontos": pts,
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
        user_id = user["id"]
        username = user["username"]

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
    ranking = ranking.sort_values(
        "Pontuação", ascending=False).reset_index(drop=True)
    ranking.insert(0, "Posição", ranking.index + 1)

    return ranking


def load_ranking_inputs():
    profiles = load_table("profiles")
    matches = load_table("matches", order_by="match_no")
    matches = sort_matches_for_display(matches)
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
            "Classificados e extras",
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
    matches = sort_matches_for_display(matches)
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
        st.dataframe(lock_schedule.drop(columns=["Chave no secrets.toml"], errors="ignore"), use_container_width=True, hide_index=True)

    st.download_button(
        label="Baixar minhas previsões em Excel",
        data=build_user_prediction_export(user_id),
        file_name=f"kapitalo_cup_previsoes_{username}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()

    tab_games, tab_extras = st.tabs(
        ["Jogos pendentes", "Classificados e extras pendentes"])

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
        st.markdown("### Extras e classificados pendentes")

        if pending_extras.empty:
            st.success(
                "Você já preencheu os classificados e extras previstos no sistema.")
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


def render_predictions_page():
    if not st.session_state.get("is_logged_in", False):
        st.warning("Você precisa fazer login para registrar palpites.")
        return

    user_id = st.session_state["user_id"]
    username = st.session_state.get("username", "")
    supabase = get_client()
    matches = load_table("matches", order_by="match_no")
    matches = sort_matches_for_display(matches)

    if matches.empty:
        st.warning(
            "Nenhum jogo encontrado. Rode o seed com `python -m src.seed`.")
        return

    predictions = load_table("predictions")

    if not predictions.empty and "user_id" in predictions.columns:
        user_predictions = predictions[predictions["user_id"] == user_id].copy(
        )
    else:
        user_predictions = pd.DataFrame()

    st.markdown(
        """
        <div class="section-card">
            <h3 style="margin-bottom:0.25rem;">Preencha seus palpites</h3>
            <p style="color:#6b7280;margin-bottom:0;">
                Escolha a fase e, na fase de grupos, preencha um grupo por vez.
                A tabela do grupo é simulada automaticamente com os placares que você salvou.
                Os jogos sem palpite salvo começam vazios para evitar salvar 0x0 sem querer.
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

    if selected_group:
        st.markdown(f"### Grupo {selected_group}")

    if selected_group and not filtered.empty and is_group_stage(selected_stage):
        with st.expander("Tabela simulada do grupo com seus palpites salvos", expanded=True):
            group_table = simulate_group_table(filtered, user_predictions)
            st.dataframe(group_table, use_container_width=True,
                         hide_index=True)

    filtered = sort_matches_for_display(filtered)

    # Guarda os jogos visíveis na tela para permitir salvar o grupo inteiro.
    # Precisa ser inicializado antes do loop de cards; caso contrário,
    # o Streamlit quebra quando tenta fazer append no primeiro jogo.
    visible_prediction_rows = []

    for _, match in filtered.iterrows():
        match_id = match["match_id"]
        match_id_str = str(match_id)
        stage = match.get("stage", selected_stage)
        match_locked = is_stage_locked(stage)
        home_team = match["home_team"]
        away_team = match["away_team"]
        match_no = match.get("match_no", "")
        group_name = match.get("group_name", "")
        kickoff_text = format_kickoff(match.get("kickoff_at"))

        existing = pd.DataFrame()

        if not user_predictions.empty:
            existing = user_predictions[user_predictions["match_id"] == match_id]

        default_home = None
        default_away = None
        default_advancing = ""

        if not existing.empty:
            default_home = safe_int(existing.iloc[0].get("home_goals"))
            default_away = safe_int(existing.iloc[0].get("away_goals"))
            default_advancing = existing.iloc[0].get("advancing_team") or ""

        visible_prediction_rows.append(
            {
                "match_id": match_id,
                "stage": stage,
                "home_team": home_team,
                "away_team": away_team,
                "match_no": match_no,
                "label": f"Jogo {match_no} — {kickoff_text} — {home_team} x {away_team}",
            }
        )

        st.markdown('<div class="match-card">', unsafe_allow_html=True)

        saved_badge = '<span class="pill pill-green">Palpite salvo</span>' if not existing.empty else '<span class="pill">Ainda não salvo</span>'
        lock_badge = '<span class="pill pill-red">Travado</span>' if match_locked else '<span class="pill pill-blue">Aberto</span>'

        st.markdown(
            f"""
            <div class="match-title">{home_team} x {away_team}</div>
            <div class="match-meta">
                Jogo {match_no} • {kickoff_text} {f"• Grupo {group_name}" if group_name else ""} &nbsp; {saved_badge} &nbsp; {lock_badge}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if is_knockout_stage(stage):
            col1, col2, col3, col4 = st.columns([1.4, 0.28, 1.4, 1.2])
        else:
            col1, col2, col3 = st.columns([1.4, 0.28, 1.4])

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
                "<div style='text-align:center;font-weight:900;font-size:1.35rem;color:#111827;'>×</div>",
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
                advancing_options = ["", home_team, away_team]
                advancing_index = 0

                if default_advancing in advancing_options:
                    advancing_index = advancing_options.index(
                        default_advancing)

                advancing_team = st.selectbox(
                    "Classificado",
                    advancing_options,
                    index=advancing_index,
                    key=f"pred_adv_{match_id}",
                    disabled=match_locked,
                )
        else:
            st.caption(
                "Fase de grupos: aqui você preenche apenas o placar. Classificados são preenchidos na aba Classificados e extras.")

        save_col1, save_col2 = st.columns([1, 4])

        with save_col1:
            if st.button(
                "Salvar",
                key=f"save_pred_{match_id}",
                use_container_width=True,
                disabled=match_locked,
            ):
                if is_stage_locked(stage):
                    st.error(
                        f"Não é possível alterar este jogo. O prazo de {stage} encerrou em {stage_lock_text(stage)}.")
                    st.stop()

                if home_goals is None or away_goals is None:
                    st.error(
                        f"Preencha o placar de {home_team} x {away_team} antes de salvar.")
                    st.stop()

                payload = {
                    "user_id": user_id,
                    "match_id": match_id,
                    "home_goals": int(home_goals),
                    "away_goals": int(away_goals),
                    "advancing_team": advancing_team if advancing_team else None,
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

        with save_col2:
            if match_id_str in saved_ids:
                status_pill("Já preenchido", "green")
            else:
                status_pill("Pendente")

        st.markdown("</div>", unsafe_allow_html=True)

    if selected_group and is_group_stage(selected_stage) and not filtered.empty:
        st.divider()
        st.markdown("### Salvar grupo inteiro")
        st.caption(
            "Use este botão para salvar todos os jogos do grupo selecionado de uma vez. "
            "Jogos ainda vazios serão listados para você preencher antes de salvar."
        )

        if st.button(
            f"Salvar todos os palpites do Grupo {selected_group}",
            key=f"save_all_group_{selected_stage}_{selected_group}",
            use_container_width=True,
            disabled=selected_stage_locked,
        ):
            if is_stage_locked(selected_stage):
                st.error(
                    f"Não é possível alterar este grupo. O prazo de {selected_stage} encerrou em {stage_lock_text(selected_stage)}."
                )
                st.stop()

            invalid_rows = []
            payload_rows = []

            for item in visible_prediction_rows:
                match_id = item["match_id"]
                home_key = f"pred_home_{match_id}"
                away_key = f"pred_away_{match_id}"
                home_value = st.session_state.get(home_key)
                away_value = st.session_state.get(away_key)

                if home_value is None or away_value is None:
                    invalid_rows.append(item["label"])
                    continue

                payload_rows.append(
                    {
                        "user_id": user_id,
                        "match_id": match_id,
                        "home_goals": int(home_value),
                        "away_goals": int(away_value),
                        "advancing_team": None,
                    }
                )

            if invalid_rows:
                st.error(
                    "Não foi possível salvar o grupo inteiro. Preencha os placares destes jogos:"
                )
                st.write(pd.DataFrame(
                    {"Jogos sem placar preenchido": invalid_rows}))
                st.stop()

            if not payload_rows:
                st.warning("Não há jogos para salvar neste grupo.")
                st.stop()

            try:
                supabase.table("predictions").upsert(
                    payload_rows,
                    on_conflict="user_id,match_id",
                ).execute()

                clear_data_cache()
                st.success(
                    f"Todos os palpites do Grupo {selected_group} foram salvos.")
                st.rerun()

            except Exception as exc:
                st.error(f"Erro ao salvar o grupo inteiro: {exc}")


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
    matches = sort_matches_for_display(matches)
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
        "16-avos": 32,
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
        "Pontue acertando resultados, placares exatos, classificados, campeão e artilheiro.",
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
            <p>Exemplo: apostou 2x1 e o jogo foi 1x0, acertou o vencedor.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="rules-card">
            <h3>Placar exato</h3>
            <p>Você ganha bônus se acertar exatamente o placar do jogo.</p>
            <p>Exemplo: apostou 2x1 e o jogo terminou 2x1.</p>
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
                Cadastre resultados oficiais, classificados reais, extras reais e exporte todas as previsões.
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
    matches = load_table("matches", order_by="match_no")
    matches = sort_matches_for_display(matches)

    if matches.empty:
        st.warning("Nenhum jogo encontrado.")
        return

    tab_results, tab_schedule, tab_phase_actuals, tab_bonus_actuals = st.tabs(
        [
            "Resultados dos jogos",
            "Horários dos jogos",
            "Classificados reais",
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

            st.markdown('<div class="match-card">', unsafe_allow_html=True)

            result_badge = '<span class="pill pill-green">Resultado salvo</span>' if not existing.empty else '<span class="pill">Ainda não salvo</span>'

            st.markdown(
                f"""
                <div class="match-title">{home_team} x {away_team}</div>
                <div class="match-meta">Jogo {match_no} • {kickoff_text} &nbsp; {result_badge}</div>
                """,
                unsafe_allow_html=True,
            )

            if is_knockout_stage(stage):
                col1, col2, col3, col4 = st.columns([1.4, 0.28, 1.4, 1.2])
            else:
                col1, col2, col3 = st.columns([1.4, 0.28, 1.4])

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
                    advancing_options = ["", home_team, away_team]
                    advancing_index = 0

                    if default_advancing in advancing_options:
                        advancing_index = advancing_options.index(
                            default_advancing)

                    advancing_team = st.selectbox(
                        "Classificado",
                        advancing_options,
                        index=advancing_index,
                        key=f"actual_adv_{match_id}",
                    )
            else:
                st.caption(
                    "Fase de grupos: cadastre apenas o placar. Classificados reais ficam na aba Classificados reais.")

            save_col1, save_col2 = st.columns([1, 4])

            with save_col1:
                if st.button("Salvar", key=f"save_actual_{match_id}", use_container_width=True):
                    payload = {
                        "match_id": match_id,
                        "home_goals": int(home_goals),
                        "away_goals": int(away_goals),
                        "advancing_team": advancing_team if advancing_team else None,
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

            st.markdown("</div>", unsafe_allow_html=True)

    with tab_schedule:
        st.markdown("### Horários dos jogos")
        st.caption(
            "Cadastre ou ajuste os horários em horário do Brasil/São Paulo. "
            "O app usa esses horários para ordenar os jogos."
        )

        schedule_matches = sort_matches_for_display(matches)
        stages_schedule = schedule_matches["stage"].dropna().unique().tolist() if "stage" in schedule_matches.columns else []

        if not stages_schedule:
            st.info("Nenhuma fase encontrada na tabela de jogos.")
        else:
            selected_schedule_stage = st.selectbox(
                "Fase",
                stages_schedule,
                key="admin_schedule_stage",
            )

            schedule_filtered = schedule_matches[schedule_matches["stage"] == selected_schedule_stage].copy()

            if "group_name" in schedule_filtered.columns and schedule_filtered["group_name"].notna().any():
                schedule_groups = ["Todos"] + sorted(schedule_filtered["group_name"].dropna().unique().tolist())
                selected_schedule_group = st.selectbox(
                    "Grupo",
                    schedule_groups,
                    key="admin_schedule_group",
                )

                if selected_schedule_group != "Todos":
                    schedule_filtered = schedule_filtered[schedule_filtered["group_name"] == selected_schedule_group]

            schedule_filtered = sort_matches_for_display(schedule_filtered)

            for _, match in schedule_filtered.iterrows():
                match_id = match["match_id"]
                match_no = match.get("match_no", "")
                home_team = match.get("home_team", "")
                away_team = match.get("away_team", "")
                current_kickoff = match.get("kickoff_at")
                current_dt = pd.to_datetime(current_kickoff, errors="coerce")

                if pd.isna(current_dt):
                    default_date = datetime.now().date()
                    default_time = datetime.now().time().replace(second=0, microsecond=0)
                else:
                    default_date = current_dt.date()
                    default_time = current_dt.time().replace(second=0, microsecond=0)

                with st.container(border=True):
                    st.markdown(f"**Jogo {match_no} — {home_team} x {away_team}**")
                    st.caption(f"Atual: {format_kickoff(current_kickoff)}")

                    col_date, col_time, col_button = st.columns([1, 1, 1])

                    with col_date:
                        new_date = st.date_input(
                            "Data",
                            value=default_date,
                            key=f"kickoff_date_{match_id}",
                        )

                    with col_time:
                        new_time = st.time_input(
                            "Horário Brasil",
                            value=default_time,
                            key=f"kickoff_time_{match_id}",
                        )

                    with col_button:
                        st.markdown("<br>", unsafe_allow_html=True)

                        if st.button("Salvar horário", key=f"save_kickoff_{match_id}", use_container_width=True):
                            kickoff_value = f"{new_date} {new_time.strftime('%H:%M:%S')}"

                            try:
                                supabase.table("matches").update(
                                    {"kickoff_at": kickoff_value}
                                ).eq(
                                    "match_id", match_id
                                ).execute()

                                clear_data_cache()
                                st.success("Horário salvo.")
                                st.rerun()

                            except Exception as exc:
                                st.error(f"Erro ao salvar horário: {exc}")


    with tab_phase_actuals:
        st.markdown("### Classificados reais")

        teams = get_all_teams(matches)

        if not teams:
            st.warning("Nenhuma seleção encontrada.")
            return

        phase_config = {
            "16-avos": 32,
            "Oitavas": 16,
            "Quartas": 8,
            "Semis": 4,
            "Final": 2,
        }

        selected_phase = st.selectbox(
            "Fase para atualizar",
            list(phase_config.keys()),
            key="admin_selected_actual_phase",
        )

        max_teams = phase_config[selected_phase]

        existing_actuals = load_table("phase_actuals")

        default_selected = set()

        if not existing_actuals.empty:
            default_selected = set(
                existing_actuals[existing_actuals["phase"]
                                 == selected_phase]["team"].tolist()
            )

        st.caption(
            f"Selecione até {max_teams} seleções para {selected_phase}.")

        selected_teams = []

        cols_per_row = 4
        cols = st.columns(cols_per_row)

        for i, team in enumerate(teams):
            col = cols[i % cols_per_row]

            with col:
                checked = st.checkbox(
                    team,
                    value=team in default_selected,
                    key=f"actual_phase_checkbox_{selected_phase}_{team}",
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
                f"Salvar classificados reais — {selected_phase}",
                key=f"save_actual_phase_checkbox_{selected_phase}",
                disabled=selected_count > max_teams,
                use_container_width=True,
            ):
                try:
                    supabase.table("phase_actuals").delete().eq(
                        "phase", selected_phase
                    ).execute()

                    rows = [
                        {
                            "phase": selected_phase,
                            "team": team,
                        }
                        for team in selected_teams
                    ]

                    if rows:
                        supabase.table("phase_actuals").insert(rows).execute()

                    clear_data_cache()
                    st.success(
                        f"Classificados reais de {selected_phase} salvos.")
                    st.rerun()

                except Exception as exc:
                    st.error(f"Erro ao salvar classificados reais: {exc}")

        with col_clear:
            if st.button(
                f"Limpar classificados reais — {selected_phase}",
                key=f"clear_actual_phase_{selected_phase}",
                use_container_width=True,
            ):
                for team in teams:
                    key = f"actual_phase_checkbox_{selected_phase}_{team}"
                    if key in st.session_state:
                        st.session_state[key] = False

                st.rerun()

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

    elif page == "Classificados e extras":
        hero(
            "Classificados e extras",
            "Escolha os classificados por fase, campeão e artilheiro.",
        )
        render_phase_predictions_page()

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
