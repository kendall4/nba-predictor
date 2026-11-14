"""
Light historical nudge when a star teammate is OUT
===================================================
Uses game-level with/without splits (same season logs) for **one** primary star who is out.
Applies a **small** extra PTS/AST multiplier on top of injury-vacuum logic — capped and
skipped when sample sizes are too small. Does not replace `teammate_absence_adjustments`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.features.teammate_absence_adjustments import _normalize_name

_MIN_GAMES_PER_BUCKET = 5
_CAP_PTS = 0.04
_CAP_AST = 0.03
_PTS_SIGNAL = 0.35  # fraction of relative PTS gap applied
_AST_SIGNAL = 0.30


def _pick_primary_star_out(
    team: str, star_outs: List[str], roster_df: pd.DataFrame
) -> Optional[str]:
    """Highest season PPG among listed star outs on this team."""
    if not star_outs or roster_df is None or len(roster_df) == 0:
        return None
    best_name = None
    best_pts = -1.0
    for name in star_outs:
        rows = roster_df[
            (roster_df["TEAM_ABBREVIATION"] == team) & (roster_df["PLAYER_NAME"] == name)
        ]
        if rows.empty:
            continue
        pts = float(rows.iloc[0].get("PTS", 0) or 0)
        if pts > best_pts:
            best_pts = pts
            best_name = name
    return best_name or (star_outs[0] if star_outs else None)


def _nudge_from_split(
    subject: str,
    other: str,
    season: str,
    tracker: Any,
    split_cache: Dict[Tuple[str, str, str], Tuple[float, float, str]],
) -> Tuple[float, float, str]:
    key = (subject, other, season)
    if key in split_cache:
        return split_cache[key]

    from src.analysis.game_level_with_without import compute_game_level_with_without

    res = compute_game_level_with_without(
        subject, other, "teammate", season=season, tracker=tracker
    )
    if res.get("error"):
        out = (1.0, 1.0, "no_logs")
        split_cache[key] = out
        return out

    op = res["other_played"]
    oa = res["other_absent"]
    if op["n"] < _MIN_GAMES_PER_BUCKET or oa["n"] < _MIN_GAMES_PER_BUCKET:
        out = (1.0, 1.0, "small_sample")
        split_cache[key] = out
        return out

    if op["pts"] is None or oa["pts"] is None:
        out = (1.0, 1.0, "missing")
        split_cache[key] = out
        return out

    rel = (float(oa["pts"]) - float(op["pts"])) / max(float(op["pts"]), 6.0)
    raw_pts = rel * _PTS_SIGNAL
    pts_m = 1.0 + max(-_CAP_PTS, min(_CAP_PTS, raw_pts))

    ast_m = 1.0
    if op.get("ast") is not None and oa.get("ast") is not None:
        rel_a = (float(oa["ast"]) - float(op["ast"])) / max(float(op["ast"]), 2.0)
        raw_a = rel_a * _AST_SIGNAL
        ast_m = 1.0 + max(-_CAP_AST, min(_CAP_AST, raw_a))

    note = f"{other.split()[-1]} n={op['n']}/{oa['n']}"
    out = (round(pts_m, 4), round(ast_m, 4), note)
    split_cache[key] = out
    return out


def apply_historical_teammate_out_nudges(
    df: pd.DataFrame,
    absence_index: Dict[str, Dict],
    roster_df: pd.DataFrame,
    *,
    season: str = "2025-26",
    enabled: bool = True,
) -> pd.DataFrame:
    """
    For each row: if team has **star_outs**, pick highest-PPG star out; if subject != that star,
    apply cached PTS/AST nudge from historical teammate with/without split.
    """
    if not enabled or df is None or len(df) == 0:
        return df

    df = df.copy()
    for c, v in [
        ("hist_teammate_out_pts_mult", 1.0),
        ("hist_teammate_out_ast_mult", 1.0),
        ("hist_teammate_out_note", ""),
    ]:
        if c not in df.columns:
            df[c] = v

    try:
        from src.analysis.hot_hand_tracker import HotHandTracker

        tracker = HotHandTracker(blend_mode="latest")
    except Exception:
        return df

    split_cache: Dict[Tuple[str, str, str], Tuple[float, float, str]] = {}

    for idx, row in df.iterrows():
        team = row.get("team")
        pname = row.get("player_name")
        if not team or not pname or team not in absence_index:
            continue

        star_outs = absence_index[team].get("star_outs") or []
        if not star_outs:
            continue

        other = _pick_primary_star_out(team, star_outs, roster_df)
        if not other or _normalize_name(pname) == _normalize_name(other):
            continue

        pts_m, ast_m, note = _nudge_from_split(
            str(pname), str(other), season, tracker, split_cache
        )

        if "predicted_points" in df.columns and pts_m != 1.0:
            df.at[idx, "predicted_points"] = float(row["predicted_points"]) * pts_m
        if "predicted_assists" in df.columns and ast_m != 1.0:
            df.at[idx, "predicted_assists"] = float(row["predicted_assists"]) * ast_m

        df.at[idx, "hist_teammate_out_pts_mult"] = pts_m
        df.at[idx, "hist_teammate_out_ast_mult"] = ast_m
        df.at[idx, "hist_teammate_out_note"] = note

    return df
