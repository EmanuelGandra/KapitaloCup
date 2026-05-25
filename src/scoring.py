from __future__ import annotations

import pandas as pd

STAGE_POINTS = {
    "Grupos": {"outcome": 5, "exact": 5, "advance": 5},
    "Dezesseis-avos": {"outcome": 8, "exact": 8, "advance": 8},
    "Oitavas": {"outcome": 10, "exact": 10, "advance": 10},
    "Quartas": {"outcome": 13, "exact": 13, "advance": 13},
    "Semifinais": {"outcome": 16, "exact": 16, "advance": 16},
    "3º Lugar": {"outcome": 10, "exact": 10, "advance": 10},
    "Final": {"outcome": 20, "exact": 20, "advance": 20},
}

PHASE_POINTS = {
    "Classificados aos 32-avos": 5,
}

BONUS_POINTS = {"champion": 75, "top_scorer": 75}


def outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "H"
    if home_goals < away_goals:
        return "A"
    return "D"


def score_match(row: pd.Series) -> int:
    pts = STAGE_POINTS.get(row["stage"], {"outcome": 0, "exact": 0, "advance": 0})
    score = 0
    pred_outcome = outcome(int(row["pred_home_goals"]), int(row["pred_away_goals"]))
    actual_outcome = outcome(int(row["actual_home_goals"]), int(row["actual_away_goals"]))
    if pred_outcome == actual_outcome:
        score += pts["outcome"]
    if int(row["pred_home_goals"]) == int(row["actual_home_goals"]) and int(row["pred_away_goals"]) == int(row["actual_away_goals"]):
        score += pts["exact"]
    if row.get("pred_advancing_team") and row.get("actual_advancing_team") and row["pred_advancing_team"] == row["actual_advancing_team"]:
        score += pts["advance"]
    return score


def compute_ranking(profiles: pd.DataFrame, matches: pd.DataFrame, predictions: pd.DataFrame, actuals: pd.DataFrame,
                    phase_predictions: pd.DataFrame, phase_actuals: pd.DataFrame,
                    bonus_predictions: pd.DataFrame, bonus_actuals: pd.DataFrame) -> pd.DataFrame:
    if profiles.empty:
        return pd.DataFrame(columns=["username", "total_points"])

    scores = profiles[["id", "username"]].copy()
    scores["match_points"] = 0
    scores["phase_points"] = 0
    scores["bonus_points"] = 0

    if not predictions.empty and not actuals.empty and not matches.empty:
        merged = predictions.merge(actuals, on="match_id", how="inner", suffixes=("_pred", "_actual"))
        merged = merged.merge(matches[["match_id", "stage"]], on="match_id", how="left")
        if not merged.empty:
            merged = merged.rename(columns={
                "home_goals_pred": "pred_home_goals",
                "away_goals_pred": "pred_away_goals",
                "home_goals_actual": "actual_home_goals",
                "away_goals_actual": "actual_away_goals",
                "advancing_team_pred": "pred_advancing_team",
                "advancing_team_actual": "actual_advancing_team",
            })
            merged["points"] = merged.apply(score_match, axis=1)
            by_user = merged.groupby("user_id")["points"].sum().reset_index()
            scores = scores.merge(by_user, left_on="id", right_on="user_id", how="left")
            scores["match_points"] = scores["points"].fillna(0).astype(int)
            scores = scores.drop(columns=[c for c in ["user_id", "points"] if c in scores.columns])

    if not phase_predictions.empty and not phase_actuals.empty:
        phase_hits = phase_predictions.merge(phase_actuals, on=["phase", "team"], how="inner")
        if not phase_hits.empty:
            phase_hits["points"] = phase_hits["phase"].map(PHASE_POINTS).fillna(0).astype(int)
            by_user = phase_hits.groupby("user_id")["points"].sum().reset_index()
            scores = scores.merge(by_user, left_on="id", right_on="user_id", how="left")
            scores["phase_points"] = scores["points"].fillna(0).astype(int)
            scores = scores.drop(columns=[c for c in ["user_id", "points"] if c in scores.columns])

    if not bonus_predictions.empty and not bonus_actuals.empty:
        actual = bonus_actuals.iloc[0].to_dict()
        bp = bonus_predictions.copy()
        bp["points"] = 0
        bp.loc[bp["champion"].fillna("") == (actual.get("champion") or ""), "points"] += BONUS_POINTS["champion"]
        bp.loc[bp["top_scorer"].fillna("") == (actual.get("top_scorer") or ""), "points"] += BONUS_POINTS["top_scorer"]
        by_user = bp.groupby("user_id")["points"].sum().reset_index()
        scores = scores.merge(by_user, left_on="id", right_on="user_id", how="left")
        scores["bonus_points"] = scores["points"].fillna(0).astype(int)
        scores = scores.drop(columns=[c for c in ["user_id", "points"] if c in scores.columns])

    scores["total_points"] = scores[["match_points", "phase_points", "bonus_points"]].sum(axis=1)
    return scores.sort_values(["total_points", "match_points"], ascending=False).reset_index(drop=True)
