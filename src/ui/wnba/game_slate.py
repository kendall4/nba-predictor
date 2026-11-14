"""Per-game WNBA slate view with top prop edges."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from src.ui.nba.theme import hero


def render(predictions: Optional[pd.DataFrame], games: list, selected_date=None) -> None:
    hero("Game slate", "Top model edges by matchup", emoji="🏀")
    if not games:
        st.info("No WNBA games on this date.")
        return
    if predictions is None or len(predictions) == 0:
        st.info("Generate predictions in **Model workspace** above.")
        for g in games:
            st.caption(f"{g.get('away', '?')} @ {g.get('home', '?')} — {g.get('status', '')}")
        return

    for g in games:
        home, away = g.get("home"), g.get("away")
        st.subheader(f"{away} @ {home}")
        st.caption(g.get("status", ""))
        mask = (predictions["team"].isin([home, away])) & (predictions["opponent"].isin([home, away]))
        game_df = predictions[mask].copy()
        if len(game_df) == 0:
            st.caption("No player projections for this game.")
            continue
        show = game_df.sort_values("overall_value", ascending=False).head(8)
        cols = [
            "player_name",
            "team",
            "pred_points",
            "line_points",
            "point_value",
            "pred_rebounds",
            "line_rebounds",
            "rebound_value",
            "pred_assists",
            "line_assists",
            "assist_value",
            "overall_value",
        ]
        cols = [c for c in cols if c in show.columns]
        st.dataframe(show[cols], use_container_width=True, hide_index=True)
