"""WNBA Performance Predictor — main Streamlit tab."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.analysis.wnba_value_analyzer import WNBAValueAnalyzer
from src.config.wnba_seasons import PRIMARY_WNBA_SEASON, RAW_DATA_DIR
from src.features.wnba_matchup_features import WNBAMatchupFeatureBuilder
from src.services.wnba_games import get_games_for_date
from src.services.wnba_odds_manager import WNBAOddsManager
from src.ui.nba import leaderboard as ui_leader
from src.ui.nba import predictions as ui_preds
from src.ui.nba.theme import hero
from src.ui.wnba import game_slate as ui_game
from src.ui.wnba import prop_pct as ui_prop_pct
from src.utils.prediction_columns import normalize_prediction_dataframe


def _ensure_fresh_wnba_data(max_age_hours: int = 12) -> bool:
    # Also honor NBA_SKIP — Streamlit runs ALL sport tabs on every page load.
    skip = os.getenv("WNBA_SKIP_AUTO_REFRESH", "").lower() in ("1", "true", "yes")
    skip = skip or os.getenv("NBA_SKIP_AUTO_REFRESH", "").lower() in ("1", "true", "yes")
    if skip:
        return True
    csv_path = os.path.join(RAW_DATA_DIR, f"player_stats_{PRIMARY_WNBA_SEASON}.csv")
    try:
        age_hours = (time.time() - os.path.getmtime(csv_path)) / 3600
    except FileNotFoundError:
        # Missing CSV: do NOT auto-call stats.nba.com (can hang the whole app for minutes).
        print("WNBA CSV missing — skipping auto-refresh (set refresh manually).")
        return False
    if age_hours <= max_age_hours:
        return True
    try:
        from src.data_collection.wnba_stats import WNBAStatsCollector

        collector = WNBAStatsCollector(season=PRIMARY_WNBA_SEASON, api_timeout=12, retry_attempts=1)
        collector.get_player_stats()
        time.sleep(0.5)
        collector.get_team_pace_stats()
        return True
    except Exception as e:
        print(f"WNBA auto-refresh failed: {e}")
        return False


def render() -> None:
    st.header("🏀 WNBA Performance Predictor")
    st.caption(
        "Pace + defense matchups, recent form, and optional **The Odds API** (`basketball_wnba`) lines. "
        f"Season **{PRIMARY_WNBA_SEASON}** · data under `{RAW_DATA_DIR}/`."
    )

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    date_options = {"Today": today, "Tomorrow": tomorrow, "Yesterday": yesterday}
    selected_day = st.selectbox(
        "📅 View games for:",
        options=list(date_options.keys()),
        index=0,
        key="wnba_game_date_selector",
    )
    selected_date = date_options[selected_day]

    col_refresh, col_quota = st.columns([1, 2])
    with col_refresh:
        api_key = os.getenv("ODDS_API_KEY")
        try:
            api_key = api_key or st.secrets.get("ODDS_API_KEY")
        except Exception:
            pass
        if api_key and st.button("🔄 Refresh WNBA odds", key="wnba_refresh_odds"):
            mgr = WNBAOddsManager(api_key=api_key)
            with st.spinner("Fetching WNBA props from The Odds API…"):
                df = mgr.get_odds_df(force_refresh=True, target_date=selected_date)
            if df is not None and len(df) > 0:
                st.success(f"Cached {len(df)} WNBA prop rows for {selected_date}")
            else:
                err = mgr.aggregator._last_odds_http_error
                st.warning(err or "No WNBA odds returned (off-season, no lines, or API issue).")
    with col_quota:
        if api_key:
            try:
                qs = WNBAOddsManager(api_key=api_key).get_quota_status()
                if qs.get("max_daily", 0) > 0:
                    st.caption(
                        f"Odds API quota: {qs['requests_today']}/{qs['max_daily']} used · "
                        f"{qs['remaining']} left this billing period"
                    )
            except Exception:
                pass

    if "wnba_data_refreshed" not in st.session_state:
        with st.spinner("Checking WNBA stats freshness…"):
            ok = _ensure_fresh_wnba_data()
        st.session_state["wnba_data_refreshed"] = True
        if not ok:
            st.warning(
                f"Could not refresh WNBA stats from stats.nba.com. "
                f"Run `python scripts/refresh_wnba_data.py` or add CSVs under `{RAW_DATA_DIR}/`. "
                "Set `WNBA_SKIP_AUTO_REFRESH=1` to skip this check."
            )

    games = get_games_for_date(selected_date)
    st.subheader(f"📅 {selected_day}'s Games ({selected_date.strftime('%b %d')})")
    if games:
        cols = st.columns(min(len(games), 4))
        for i, g in enumerate(games):
            with cols[i % len(cols)]:
                st.info(f"**{g['away']}** @ **{g['home']}**\n\n{g.get('status', '')}")
    else:
        st.warning(
            f"No WNBA games on {selected_date.strftime('%Y-%m-%d')} (off-season or schedule not posted yet)."
        )

    st.markdown("---")

    min_minutes = st.slider(
        "Minimum minutes (season avg)",
        0,
        40,
        10,
        key="wnba_min_minutes",
    )
    min_value = st.slider(
        "Minimum value score",
        -10.0,
        5.0,
        -5.0,
        key="wnba_min_value",
    )
    recent_w = st.slider("Recent form weight", 0.0, 1.0, 0.2, 0.05, key="wnba_recent_w")
    h2h_w = st.slider("H2H weight", 0.0, 1.0, 0.15, 0.05, key="wnba_h2h_w")
    home_w = st.slider("Home/away weight", 0.0, 1.0, 0.0, 0.05, key="wnba_home_w")

    if "wnba_predictions" not in st.session_state:
        st.session_state["wnba_predictions"] = None
    if "wnba_predictions_raw" not in st.session_state:
        st.session_state["wnba_predictions_raw"] = None

    with st.expander("🧮 Model workspace — generate slate", expanded=st.session_state["wnba_predictions"] is None):
        generate = st.button("🔮 Generate WNBA predictions", type="primary", key="wnba_generate")
        # Button-only: Streamlit runs this tab on every NBA page refresh too.
        if st.session_state["wnba_predictions"] is None and not generate:
            st.info("Click **Generate WNBA predictions** when ready — refresh alone will not start a run.")
        if generate:
            @st.cache_resource(show_spinner=False)
            def _load_builder(_v=1):
                return WNBAMatchupFeatureBuilder(blend_mode="latest")

            try:
                builder = _load_builder()
            except FileNotFoundError as e:
                st.error(str(e))
                if st.button("Try refresh WNBA stats now", key="wnba_manual_refresh"):
                    from src.data_collection.wnba_stats import WNBAStatsCollector

                    with st.spinner("Pulling WNBA stats…"):
                        c = WNBAStatsCollector(
                            season=PRIMARY_WNBA_SEASON, api_timeout=12, retry_attempts=1
                        )
                        c.get_player_stats()
                        c.get_team_pace_stats()
                    st.cache_resource.clear()
                    st.rerun()
                return

            if not games:
                st.info("Add games on this date before generating.")
            else:
                analyzer = WNBAValueAnalyzer(builder=builder)
                with st.spinner("Building WNBA projections…"):
                    try:
                        raw = analyzer.analyze_games(
                            games,
                            target_date=selected_date,
                            recent_form_weight=recent_w,
                            h2h_weight=h2h_w,
                            home_away_weight=home_w,
                        )
                        raw = normalize_prediction_dataframe(raw)
                        st.session_state["wnba_predictions_raw"] = raw
                        filtered = raw.copy()
                        if len(filtered) > 0:
                            filtered = filtered[filtered["minutes"] >= min_minutes]
                            filtered = filtered[filtered["overall_value"] >= min_value]
                            filtered = filtered.sort_values("overall_value", ascending=False)
                        st.session_state["wnba_predictions"] = filtered
                        if len(filtered) > 0:
                            st.success(f"✅ {len(filtered)} players ({len(raw)} before filters)")
                        else:
                            st.warning("No players after filters — try lower min minutes/value.")
                    except Exception as e:
                        st.error(f"Prediction error: {e}")

    predictions = st.session_state.get("wnba_predictions")
    preds_ok = predictions is not None and len(predictions) > 0
    if not preds_ok:
        st.info("Generate predictions above to unlock Game, Prop %, Leaderboard, and Predictions tabs.")

    tab_game, tab_prop, tab_core = st.tabs(["🏀 Game", "📈 Prop %", "🧮 Leaderboard & grid"])

    def _safe(label, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception as e:
            st.error(f"{label}: {e}")

    with tab_game:
        _safe("Game", ui_game.render, predictions, games, selected_date)

    with tab_prop:
        _safe("Prop %", ui_prop_pct.render, predictions, games, selected_date)

    with tab_core:
        if preds_ok:
            sub_leader, sub_preds = st.tabs(["🏆 Leaderboard", "📈 Predictions"])
            with sub_leader:
                hero("Top value", "WNBA prop edges vs lines", emoji="💎")
                _safe("Leaderboard", ui_leader.render, predictions)
            with sub_preds:
                _safe("Predictions", ui_preds.render, predictions)
        else:
            st.info("Generate predictions to view leaderboard and full grid.")
