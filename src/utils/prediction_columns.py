"""
Normalize prediction DataFrame columns across tabs.

ValueAnalyzer outputs ``pred_points`` / ``pred_rebounds`` / …; older or alternate
pipelines may use ``predicted_*``. EV+, Edge, Longshot, and bet_generator expect ``pred_*``.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd


# canonical -> alternate column name
_PRED_ALIASES: Dict[str, str] = {
    "pred_points": "predicted_points",
    "pred_rebounds": "predicted_rebounds",
    "pred_assists": "predicted_assists",
    "pred_threes": "predicted_threes",
    "pred_steals": "predicted_steals",
    "pred_blocks": "predicted_blocks",
    "pred_turnovers": "predicted_turnovers",
}


def normalize_prediction_dataframe(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """
    Add ``pred_*`` columns from ``predicted_*`` when missing. Returns same instance if no changes.
    """
    if df is None or len(df) == 0:
        return df

    need_copy = False
    for canonical, alt in _PRED_ALIASES.items():
        if canonical not in df.columns and alt in df.columns:
            need_copy = True
            break

    if not need_copy:
        return df

    out = df.copy()
    for canonical, alt in _PRED_ALIASES.items():
        if canonical not in out.columns and alt in out.columns:
            out[canonical] = out[alt]
    return out


def prediction_columns_ok(df: pd.DataFrame | None, need: list[str] | None = None) -> tuple[bool, list[str]]:
    """Return (all present, missing list). ``need`` defaults to core PTS/REB/AST."""
    if df is None or len(df) == 0:
        return False, ["(empty dataframe)"]
    cols = need or ["pred_points", "pred_rebounds", "pred_assists"]
    missing = [c for c in cols if c not in df.columns]
    return len(missing) == 0, missing
