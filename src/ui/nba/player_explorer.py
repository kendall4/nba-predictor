import streamlit as st
import pandas as pd
from src.analysis.hot_hand_tracker import HotHandTracker
from src.analysis.alt_line_optimizer import AltLineOptimizer
from src.services.injury_tracker import InjuryTracker
from src.ui.components.player_detail_view import render_player_detail
from src.ui.nba.lines_explorer import round_to_sportsbook_line

def render(predictions):
    st.header("🧑‍💻 Player Explorer")
    st.caption("Search a player, view mobile-style visualizations, advanced stats, and game logs")
    tracker = HotHandTracker(blend_mode="latest")
    names_pred = sorted(predictions['player_name'].unique().tolist())
    names_roster = sorted(tracker.players['PLAYER_NAME'].unique().tolist()) if 'PLAYER_NAME' in tracker.players.columns else []
    all_names = sorted(set(names_pred) | set(names_roster))
    selected_player = st.selectbox("Search Player", options=all_names)
    
    # Show player detail view (main feature with visualizations, advanced stats, game logs)
    if selected_player:
        render_player_detail(selected_player, predictions)
    
    st.markdown("---")
    st.subheader("Lines & Expected Value")
    stat = st.selectbox("Stat", options=["points","rebounds","assists","threes"], index=0)
    base_line = 0.0
    row = predictions[predictions['player_name'] == selected_player].head(1)
    if len(row) == 1:
        if stat == 'points': base_line = float(row.iloc[0]['line_points'])
        elif stat == 'rebounds': base_line = float(row.iloc[0]['line_rebounds'])
        elif stat == 'assists': base_line = float(row.iloc[0]['line_assists'])
    
    # Get logs for threes calculation
    logs = None
    try:
        logs = tracker.get_player_gamelog(selected_player, season='2025-26')
        if logs is None or len(logs) == 0:
            logs = tracker.get_player_gamelog(selected_player, season='2024-25')
    except:
        pass
    
    if stat == 'threes' and logs is not None and 'FG3M' in logs.columns:
        base_line = float(max(2.5, logs['FG3M'].head(10).mean()))
    
    # Round base_line to sportsbook format (whole number or .5)
    base_line = round_to_sportsbook_line(base_line)
    
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
            pred_val = float(logs[sc].head(10).mean()) if len(logs) > 0 else None

    if pred_val is not None:
        # Ensure line_value is rounded to sportsbook format (whole number or .5)
        line_value = round_to_sportsbook_line(line_value)
        
        optimizer = AltLineOptimizer()
        prob_over = optimizer.calculate_probability_over(pred_val, line_value)
        ev_main = optimizer.calculate_ev(prob_over, int(main_odds))
        st.write(f"Model estimate: {pred_val:.2f} {stat} | Line: {line_value} | EV {ev_main:+.1%} (P(over) {prob_over:.1%})")

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
            # Round best line to sportsbook format
            best_line_rounded = round_to_sportsbook_line(result['best_line'])
            st.write(f"Best: {result['best_direction']} {best_line_rounded} at {int(result['best_odds']):+} | EV {result['best_ev']:+.1%}")
            
            # Round all lines in the dataframe before displaying
            if 'all_lines' in result and result['all_lines'] is not None:
                display_df = result['all_lines'].copy()
                if 'line' in display_df.columns:
                    display_df['line'] = display_df['line'].apply(round_to_sportsbook_line)
                st.dataframe(display_df, use_container_width=True)
        else:
            st.error("CSV must contain columns: line, over, under")


