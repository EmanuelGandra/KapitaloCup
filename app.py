from pathlib import Path

import pandas as pd
import streamlit as st
import base64
from pathlib import Path
import base64

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
PRIMARY_COLOR = "#be0439"
LOGO_PATH = Path("aux/Logo.png")


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

    /* Força tema claro mesmo se o navegador estiver em dark mode */
    html,
    body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"] {{
        background-color: #fafafa !important;
        color: #111827 !important;
    }}

    /* Área principal */
    [data-testid="stMainBlockContainer"],
    .block-container {{
        background: transparent !important;
        color: #111827 !important;
    }}

    /* Textos gerais fora da sidebar */
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6,
    .stApp p,
    .stApp span,
    .stApp label,
    .stApp div {{
        color: inherit;
    }}

    /* Cards e containers */
    .section-card,
    .match-card,
    .metric-box,
    .rules-card {{
        background-color: #ffffff !important;
        color: #111827 !important;
        border-color: #e5e7eb !important;
    }}

    /* Textos dentro dos cards */
    .section-card *,
    .match-card *,
    .metric-box *,
    .rules-card * {{
        color: #111827 !important;
    }}

    /* Dataframes e tabelas */
    [data-testid="stDataFrame"],
    [data-testid="stTable"] {{
        background-color: #ffffff !important;
        color: #111827 !important;
    }}

    /* Inputs fora da sidebar */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] div,
    [data-testid="stMultiSelect"] div,
    textarea {{
        background-color: #ffffff !important;
        color: #111827 !important;
    }}

    /* Labels fora da sidebar */
    [data-testid="stTextInput"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label {{
        color: #111827 !important;
    }}

    /* Selectbox/dropdowns */
    [data-baseweb="select"],
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="menu"] * {{
        background-color: #ffffff !important;
        color: #111827 !important;
    }}

    /* Tabs fora da sidebar */
    [data-baseweb="tab-list"] {{
        background-color: transparent !important;
    }}

    [data-baseweb="tab"] {{
        color: #111827 !important;
    }}

    [data-baseweb="tab"] p,
    [data-baseweb="tab"] span,
    [data-baseweb="tab"] div {{
        color: #111827 !important;
    }}

    /* Botões fora da sidebar */
    .stButton > button {{
        background-color: #ffffff !important;
        color: #111827 !important;
        border: 1px solid #d1d5db !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
    }}

    .stButton > button p,
    .stButton > button span {{
        color: #111827 !important;
    }}

    /* Métricas nativas, alertas e captions */
    [data-testid="stMetric"],
    [data-testid="stMetric"] *,
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] * {{
        color: #111827 !important;
    }}

    /* Expander */
    [data-testid="stExpander"],
    [data-testid="stExpander"] * {{
        background-color: #ffffff !important;
        color: #111827 !important;
    }}

    /* Checkboxes */
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] span,
    [data-testid="stCheckbox"] p {{
        color: #111827 !important;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #be0439 0%, #9e0031 100%) !important;
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

    .hero-card {{
        background: linear-gradient(135deg, #c3043c 0%, #8d002d 70%);
        color: white;
        padding: 2rem;
        border-radius: 26px;
        box-shadow: 0 20px 45px rgba(195,4,60,0.24);
        margin-bottom: 1.25rem;
        border: 1px solid rgba(255,255,255,0.22);
    }}

    .hero-card *,
    .hero-title,
    .hero-subtitle {{
        color: #ffffff !important;
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
        color: #111827 !important;
    }}

    .match-meta {{
        font-size: 0.85rem;
        color: #6b7280 !important;
        margin-bottom: 0.75rem;
    }}

    .pill {{
        display: inline-block;
        padding: 0.25rem 0.65rem;
        border-radius: 999px;
        background: #f3f4f6;
        color: #374151 !important;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid #e5e7eb;
    }}

    .pill-red {{
        background: #fff1f2;
        color: #be123c !important;
        border: 1px solid #fecdd3;
    }}

    .pill-green {{
        background: #ecfdf5;
        color: #047857 !important;
        border: 1px solid #bbf7d0;
    }}

    .pill-gold {{
        background: #fffbeb;
        color: #92400e !important;
        border: 1px solid #fde68a;
    }}

    .pill-blue {{
        background: #eff6ff;
        color: #1d4ed8 !important;
        border: 1px solid #bfdbfe;
    }}

    .metric-box {{
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 8px 22px rgba(0,0,0,0.045);
    }}

    .metric-label {{
        color: #6b7280 !important;
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}

    .metric-value {{
        color: #111827 !important;
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
        color: #111827 !important;
        font-size: 1.05rem;
        margin-bottom: 0.5rem;
    }}

    .rules-card p {{
        color: #4b5563 !important;
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
        color: #ffffff !important;
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


@st.cache_data(ttl=45, show_spinner=False)
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


def stage_points_for_match(stage: str) -> dict:
    stage = norm_text(stage)

    if "grupo" in stage or "group" in stage or "primeira" in stage:
        return {"result": 5, "exact": 5, "qualified": 0}

    if "dezesseis" in stage or "32" in stage:
        return {"result": 8, "exact": 8, "qualified": 8}

    if "oitavas" in stage or "16" in stage:
        return {"result": 10, "exact": 10, "qualified": 10}

    if "quartas" in stage or "quarter" in stage:
        return {"result": 13, "exact": 13, "qualified": 13}

    if "semi" in stage:
        return {"result": 16, "exact": 16, "qualified": 16}

    if "3" in stage or "terceiro" in stage or "third" in stage:
        return {"result": 10, "exact": 10, "qualified": 10}

    if "final" in stage:
        return {"result": 20, "exact": 20, "qualified": 20}

    return {"result": 0, "exact": 0, "qualified": 0}


def points_for_phase_prediction(phase: str) -> int:
    phase = norm_text(phase)

    if "oitavas" in phase or "16" in phase:
        return 10

    if "quartas" in phase:
        return 13

    if "semis" in phase or "semi" in phase:
        return 16

    if "final" in phase:
        return 20

    if "terceiro" in phase or "3" in phase:
        return 10

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
            <div style="
                width: 100%;
                margin: -1.2rem 0 1rem 0;
                padding: 0;
                text-align: center;
            ">
                <img
                    src="data:image/png;base64,{logo_base64}"
                    style="
                        width: 100%;
                        max-width: 100%;
                        display: block;
                        margin: 0 auto;
                        border-radius: 0;
                    "
                />
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
                for col in ["match_id", "match_no", "stage", "group_name", "home_team", "away_team"]
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
                        "Pontos": 75,
                    }
                )

            if pred_top_scorer and actual_top_scorer and pred_top_scorer == actual_top_scorer:
                rows.append(
                    {
                        "Categoria": "Extras",
                        "Fase": "Extras",
                        "Item": pred.get("top_scorer", ""),
                        "Detalhe": "Artilheiro correto",
                        "Pontos": 75,
                    }
                )

    if not rows:
        return pd.DataFrame(columns=["Categoria", "Fase", "Item", "Detalhe", "Pontos"])

    df = pd.DataFrame(rows)
    return df.sort_values(["Categoria", "Fase", "Item"]).reset_index(drop=True)


@st.cache_data(ttl=45, show_spinner=False)
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

        if st.button("Sair", key="btn_logout", use_container_width=True):
            logout()
            st.session_state.pop("main_menu", None)
            st.session_state.pop("selected_phase_predictions", None)
            clear_data_cache()
            st.rerun()

        st.divider()

        menu_options = [
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
    supabase = get_client()

    matches = load_table("matches", order_by="match_no")

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
                O campo de classificado só aparece para jogos de mata-mata.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stages = matches["stage"].dropna().unique(
    ).tolist() if "stage" in matches.columns else []

    if not stages:
        st.warning("A tabela de jogos não possui a coluna `stage` preenchida.")
        return

    top_col1, top_col2, top_col3 = st.columns([1.2, 1.2, 1])

    with top_col1:
        selected_stage = st.selectbox("Fase", stages, key="pred_stage")

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

    filtered = filtered.sort_values(
        "match_no") if "match_no" in filtered.columns else filtered

    for _, match in filtered.iterrows():
        match_id = match["match_id"]
        match_id_str = str(match_id)
        stage = match.get("stage", selected_stage)
        home_team = match["home_team"]
        away_team = match["away_team"]
        match_no = match.get("match_no", "")
        group_name = match.get("group_name", "")

        existing = pd.DataFrame()

        if not user_predictions.empty:
            existing = user_predictions[user_predictions["match_id"] == match_id]

        default_home = 0
        default_away = 0
        default_advancing = ""

        if not existing.empty:
            default_home = safe_int(existing.iloc[0].get("home_goals"))
            default_away = safe_int(existing.iloc[0].get("away_goals"))
            default_advancing = existing.iloc[0].get("advancing_team") or ""

        st.markdown('<div class="match-card">', unsafe_allow_html=True)

        saved_badge = '<span class="pill pill-green">Palpite salvo</span>' if not existing.empty else '<span class="pill">Ainda não salvo</span>'

        st.markdown(
            f"""
            <div class="match-title">{home_team} x {away_team}</div>
            <div class="match-meta">
                Jogo {match_no} {f"• Grupo {group_name}" if group_name else ""} &nbsp; {saved_badge}
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
                )
        else:
            st.caption(
                "Fase de grupos: aqui você preenche apenas o placar. Classificados são preenchidos na aba Classificados e extras.")

        save_col1, save_col2 = st.columns([1, 4])

        with save_col1:
            if st.button("Salvar", key=f"save_pred_{match_id}", use_container_width=True):
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


# ============================================================
# PÁGINA: CLASSIFICADOS E EXTRAS
# ============================================================

def render_phase_predictions_page():
    if not st.session_state.get("is_logged_in", False):
        st.warning(
            "Você precisa fazer login para preencher classificados e extras.")
        return

    user_id = st.session_state["user_id"]
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
                Nos jogos da fase de grupos, não há campo de classificado jogo a jogo.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
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
            disabled=selected_count > max_teams,
            use_container_width=True,
        ):
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

    col1, col2 = st.columns(2)

    with col1:
        champion = st.selectbox(
            "Campeão",
            champion_options,
            index=champion_index,
            key="bonus_champion",
        )

    with col2:
        top_scorer = st.text_input(
            "Artilheiro",
            value=default_top_scorer,
            key="bonus_top_scorer",
        )

    if st.button("Salvar extras", key="save_bonus", use_container_width=True):
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
                "Resultado": 5,
                "Placar exato": "+5",
                "Classificado": "Não se aplica por jogo",
                "Total possível": 880,
            },
            {
                "Fase": "Oitavas de Final",
                "Jogos": 8,
                "Resultado": 10,
                "Placar exato": "+10",
                "Classificado": 10,
                "Total possível": 240,
            },
            {
                "Fase": "Quartas de Final",
                "Jogos": 4,
                "Resultado": 13,
                "Placar exato": "+13",
                "Classificado": 13,
                "Total possível": 156,
            },
            {
                "Fase": "Semifinais",
                "Jogos": 2,
                "Resultado": 16,
                "Placar exato": "+16",
                "Classificado": 16,
                "Total possível": 96,
            },
            {
                "Fase": "3º e 4º Lugar",
                "Jogos": 1,
                "Resultado": 10,
                "Placar exato": "+10",
                "Classificado": 10,
                "Total possível": 30,
            },
            {
                "Fase": "Final",
                "Jogos": 1,
                "Resultado": 20,
                "Placar exato": "+20",
                "Classificado": 20,
                "Total possível": 60,
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
            <p><b>Campeão:</b> 75 pontos</p>
            <p><b>Artilheiro:</b> 75 pontos</p>
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
                Cadastre resultados oficiais, classificados reais e extras reais.
                O campo de classificado aparece somente para jogos de mata-mata.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    supabase = get_client()
    matches = load_table("matches", order_by="match_no")

    if matches.empty:
        st.warning("Nenhum jogo encontrado.")
        return

    tab_results, tab_phase_actuals, tab_bonus_actuals = st.tabs(
        [
            "Resultados dos jogos",
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

        filtered = filtered.sort_values(
            "match_no") if "match_no" in filtered.columns else filtered

        for _, match in filtered.iterrows():
            match_id = match["match_id"]
            stage = match.get("stage", selected_stage)
            home_team = match["home_team"]
            away_team = match["away_team"]
            match_no = match.get("match_no", "")

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
                <div class="match-meta">Jogo {match_no} &nbsp; {result_badge}</div>
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

    with tab_phase_actuals:
        st.markdown("### Classificados reais")

        teams = get_all_teams(matches)

        if not teams:
            st.warning("Nenhuma seleção encontrada.")
            return

        phase_config = {
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

        tab_ranking, tab_regras = st.tabs(["Ranking", "Regras"])

        with tab_ranking:
            render_ranking()

        with tab_regras:
            render_rules_page()

        return

    page = render_logged_sidebar()

    if page == "Ranking":
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
            "Atualize resultados oficiais, classificados reais e extras.",
        )
        render_admin_page()


if __name__ == "__main__":
    main()
