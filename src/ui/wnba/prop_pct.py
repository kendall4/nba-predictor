"""WNBA Prop % — hit rates from WNBA game logs."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from src.analysis.wnba_gamelog_tracker import WNBAGamelogTracker
from src.config.wnba_seasons import PRIMARY_WNBA_SEASON
from src.ui.nba.predictions import calculate_implied_probability
from src.ui.nba.theme import hero
from src.utils.hit_rate import calc_hit_rate


def render(predictions: Optional[pd.DataFrame], games: list, selected_date=None) -> None:
    hero("Prop %", "Last-N and season hit rates vs posted lines", emoji="📈")
    if predictions is None or len(predictions) == 0:
        st.info("Generate predictions first.")
        return

    stat = st.selectbox("Stat", ["Points", "Rebounds", "Assists", "Threes"], key="wnba_prop_stat")
    stat_map = {
        "Points": ("PTS", "pred_points", "line_points", "points"),
        "Rebounds": ("REB", "pred_rebounds", "line_rebounds", "rebounds"),
        "Assists": ("AST", "pred_assists", "line_assists", "assists"),
        "Threes": ("FG3M", "pred_threes", "line_threes", "threes"),
    }
    gl_col, pred_col, line_col, type_key = stat_map[stat]

    if "wnba_prop_tracker" not in st.session_state:
        st.session_state["wnba_prop_tracker"] = WNBAGamelogTracker(blend_mode="latest")
    tracker: WNBAGamelogTracker = st.session_state["wnba_prop_tracker"]

    value_keys = {
        "points": "point_value",
        "rebounds": "rebound_value",
        "assists": "assist_value",
        "threes": "threes_value",
    }
    val_col = value_keys[type_key]

    rows = []
    for _, row in predictions.iterrows():
        name = row["player_name"]
        line = float(row.get(line_col, 0) or 0)
        pred = float(row.get(pred_col, 0) or 0)
        gl = tracker.get_player_gamelog(name, season=PRIMARY_WNBA_SEASON)
        l5 = calc_hit_rate(gl, gl_col, line, 5) if gl is not None else (0, 0, 0.0)
        l10 = calc_hit_rate(gl, gl_col, line, 10) if gl is not None else (0, 0, 0.0)
        season = calc_hit_rate(gl, gl_col, line, None) if gl is not None else (0, 0, 0.0)
        model_ip = calculate_implied_probability(pred, line, type_key)
        rows.append(
            {
                "Player": name,
                "Team": row.get("team"),
                "Opp": row.get("opponent"),
                "Line": line,
                "Model": round(pred, 1),
                "Model IP%": round(model_ip, 1),
                "L5%": round(l5[2] * 100, 1) if l5[1] else None,
                "L10%": round(l10[2] * 100, 1) if l10[1] else None,
                "Season%": round(season[2] * 100, 1) if season[1] else None,
                "Value": round(float(row.get(val_col, 0) or 0), 2),
            }
        )

    df = pd.DataFrame(rows)
    if len(df) == 0:
        st.warning("No rows to display.")
        return
    sort_col = st.selectbox("Sort by", ["Value", "Model IP%", "L5%", "Season%"], key="wnba_prop_sort")
    ascending = sort_col not in ("Value", "Model IP%", "L5%", "Season%")
    df = df.sort_values(sort_col, ascending=ascending, na_position="last")
    st.dataframe(df, use_container_width=True, hide_index=True)

    player = st.selectbox("Player detail", [""] + df["Player"].tolist(), key="wnba_prop_player")
    if player:
        prow = predictions[predictions["player_name"] == player].iloc[0]
        line = float(prow.get(line_col, 0) or 0)
        gl = tracker.get_player_gamelog(player, season=PRIMARY_WNBA_SEASON)
        if gl is not None and gl_col in gl.columns:
            st.markdown(f"**Last 10 {stat}** vs line **{line}**")
            recent = gl.head(10)[[ "GAME_DATE", "MATCHUP", gl_col]].copy()
            recent["Hit"] = recent[gl_col] > line
            st.dataframe(recent, use_container_width=True, hide_index=True)
