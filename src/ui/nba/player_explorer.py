import streamlit as st
import pandas as pd
from src.analysis.hot_hand_tracker import HotHandTracker
from src.analysis.alt_line_optimizer import AltLineOptimizer

def render(predictions):
    st.header("🧑‍💻 Player Explorer")
    st.caption("Search a player, view recent logs, check lines and EV")
    tracker = HotHandTracker(blend_mode="latest")
    names_pred = sorted(predictions['player_name'].unique().tolist())
    names_roster = sorted(tracker.players['PLAYER_NAME'].unique().tolist()) if 'PLAYER_NAME' in tracker.players.columns else []
    all_names = sorted(set(names_pred) | set(names_roster))
    selected_player = st.selectbox("Search Player", options=all_names)
    recent_n = st.slider("Recent games", 3, 20, 10)
    
    # Fetch gamelogs with timeout handling
    logs = None
    with st.spinner(f"Loading {selected_player}'s game logs..."):
        try:
            logs = tracker.get_player_gamelog(selected_player, season='2025-26')
        except Exception as e:
            st.warning(f"⚠️ Could not fetch gamelogs: {e}")
            st.info("💡 Try again or check if player name matches NBA API format")
            logs = None
    
    if logs is None or len(logs) == 0:
        st.info("No gamelogs found for 2025-26. Gamelogs are cached after first fetch - try again in a moment.")
    else:
        show_cols = [c for c in ['GAME_DATE','MATCHUP','PTS','REB','AST','FG3M'] if c in logs.columns]
        st.subheader("Recent Game Logs")
        st.dataframe(logs[show_cols].head(recent_n), use_container_width=True, hide_index=True)
        
        # Show H2H summary if player has opponent today
        row = predictions[predictions['player_name'] == selected_player].head(1)
        if len(row) == 1:
            opp = row.iloc[0]['opponent']
            st.markdown("---")
            st.subheader(f"H2H vs {opp}")
            try:
                from src.utils.h2h_stats import get_h2h_summary
                h2h_summary = get_h2h_summary(selected_player, opp, season='2025-26')
                if h2h_summary:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Games", h2h_summary['total_games'])
                        st.metric("Avg PTS", f"{h2h_summary['avg_pts']:.1f}")
                    with col2:
                        st.metric("Avg REB", f"{h2h_summary['avg_reb']:.1f}")
                        st.metric("Avg AST", f"{h2h_summary['avg_ast']:.1f}")
                    with col3:
                        if h2h_summary.get('recent_vs_older'):
                            trend = h2h_summary['recent_vs_older']['trend']
                            st.write(f"**Trend:** {trend.upper()}")
                            st.write(f"Recent 3: {h2h_summary['recent_vs_older']['recent_avg_pts']:.1f} PPG")
                else:
                    st.info("No H2H data available (will include previous season if needed)")
            except Exception as e:
                st.caption(f"H2H summary unavailable: {e}")

    st.markdown("---")
    st.subheader("Lines & Expected Value")
    stat = st.selectbox("Stat", options=["points","rebounds","assists","threes"], index=0)
    base_line = 0.0
    row = predictions[predictions['player_name'] == selected_player].head(1)
    if len(row) == 1:
        if stat == 'points': base_line = float(row.iloc[0]['line_points'])
        elif stat == 'rebounds': base_line = float(row.iloc[0]['line_rebounds'])
        elif stat == 'assists': base_line = float(row.iloc[0]['line_assists'])
    if stat == 'threes' and logs is not None and 'FG3M' in logs.columns:
        base_line = float(max(2.5, logs['FG3M'].head(recent_n).mean()))
    line_value = st.number_input("Main line", min_value=0.0, max_value=100.0, value=float(base_line), step=0.5)
    main_odds = st.number_input("Main line odds (American)", value=-110, step=5)

    pred_val = None
    if len(row) == 1:
        if stat == 'points' and 'pred_points' in row.columns:
            pred_val = float(row.iloc[0]['pred_points'])
        elif stat == 'rebounds' and 'pred_rebounds' in row.columns:
            pred_val = float(row.iloc[0]['pred_rebounds'])
        elif stat == 'assists' and 'pred_assists' in row.columns:
            pred_val = float(row.iloc[0]['pred_assists'])
    if pred_val is None and logs is not None:
        col_map = {'points':'PTS','rebounds':'REB','assists':'AST','threes':'FG3M'}
        sc = col_map.get(stat)
        if sc in logs.columns:
            pred_val = float(logs[sc].head(recent_n).mean())

    if pred_val is not None:
        optimizer = AltLineOptimizer()
        prob_over = optimizer.calculate_probability_over(pred_val, line_value)
        ev_main = optimizer.calculate_ev(prob_over, int(main_odds))
        st.write(f"Model estimate: {pred_val:.2f} {stat} | EV {ev_main:+.1%} (P(over) {prob_over:.1%})")

    st.markdown("---")
    st.subheader("📤 Upload Alt Lines CSV (optional)")
    st.caption("Columns: line, over, under (American odds)")
    file = st.file_uploader("Upload alt lines CSV", type=["csv"], key="player_explorer_csv")
    if file is not None and pred_val is not None:
        odds_df = pd.read_csv(file)
        if all(c in odds_df.columns for c in ['line','over','under']):
            optimizer = AltLineOptimizer()
            result = optimizer.optimize_lines(
                player_name=selected_player,
                stat_type=stat,
                prediction=pred_val,
                alt_lines=odds_df[['line','over','under']].to_dict('records')
            )
            st.write(f"Best: {result['best_direction']} {result['best_line']} at {int(result['best_odds']):+} | EV {result['best_ev']:+.1%}")
            st.dataframe(result['all_lines'], use_container_width=True)
        else:
            st.error("CSV must contain columns: line, over, under")


