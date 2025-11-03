"""
Player Detail View Component
============================
Reusable component for displaying player stats and mobile-style visualizations
Can be accessed from clicking player names anywhere in the app
"""

import streamlit as st
import pandas as pd
from src.services.mobile_style_visualizer import MobileStyleVisualizer
from src.services.advanced_stats import AdvancedStatsCalculator
from src.services.injury_tracker import InjuryTracker
import os


def render_player_detail(player_name: str, predictions_df: pd.DataFrame = None):
    """
    Render a comprehensive player detail view with mobile-style visualizations
    
    Args:
        player_name: Name of player to display
        predictions_df: Optional predictions dataframe (for getting current game context)
    """
    if not player_name:
        st.info("Select a player to view details")
        return
    
    mobile_viz = MobileStyleVisualizer()
    adv_stats = AdvancedStatsCalculator()
    injury_tracker = InjuryTracker()
    
    # Header with player name and injury status
    st.subheader(f"📊 {player_name}")
    
    # Injury status
    try:
        injury_status = injury_tracker.get_player_status(player_name)
        if injury_status['status'] != 'Unknown':
            status_color = {
                'Healthy': '🟢',
                'Questionable': '🟡',
                'Out': '🔴'
            }
            icon = status_color.get(injury_status['status'], '⚪')
            st.write(f"{icon} **Status:** {injury_status['status']}")
            if injury_status.get('injury'):
                st.caption(f"Injury: {injury_status['injury']}")
    except:
        pass
    
    # Get current game context if predictions available
    opponent = None
    team = None
    if predictions_df is not None and len(predictions_df) > 0:
        player_pred = predictions_df[predictions_df['player_name'] == player_name]
        if len(player_pred) > 0:
            opponent = player_pred.iloc[0].get('opponent')
            team = player_pred.iloc[0].get('team')
            if opponent:
                st.caption(f"Today: {team} vs {opponent}")
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📈 Visualizations", "📊 Advanced Stats", "📋 Game Log"])
    
    with tab1:
        # Mobile-style visualizations (main feature)
        st.markdown("### Performance Visualizations")
        
        # Time period selection
        time_period = st.selectbox(
            "Time Period",
            options=["Last 1 Game", "Last 5 Games", "Last 10 Games", "Last 20 Games", "Head-to-Head"],
            key=f"detail_period_{player_name}"
        )
        
        # Stat category selection
        stat_categories = {
            'PTS': ('PTS', 'Points'),
            'AST': ('AST', 'Assists'),
            'REB': ('REB', 'Rebounds'),
            'FG3M': ('FG3M', '3-Pointers Made'),
            'PTS+REB+AST': (None, 'PTS + REB + AST')
        }
        selected_stat_key = st.selectbox(
            "Stat Category",
            options=list(stat_categories.keys()),
            key=f"detail_stat_{player_name}"
        )
        
        stat_col, stat_label = stat_categories[selected_stat_key]
        
        # Get suggested line based on average
        summary = mobile_viz.get_stat_summary(player_name, stat_col if stat_col else 'PTS', n_games=5)
        suggested_line = summary['average'] if summary else 20.0
        
        # Over/under line input
        col1, col2 = st.columns([2, 1])
        with col1:
            over_under_line = st.number_input(
                "Over/Under Line",
                min_value=0.0,
                value=float(suggested_line),
                step=0.5,
                key=f"detail_line_{player_name}"
            )
        with col2:
            st.metric("Avg", f"{summary['average']:.1f}")
        
        # Show percentage statistics
        periods = {'H2H': 5, 'L5': 5, 'L10': 10, 'L20': 20, '2025': 100}
        pct_stats = mobile_viz.get_percentage_stats(
            player_name, 
            stat_col if stat_col else 'PTS',
            over_under_line,
            periods
        )
        
        st.markdown("#### % Statistics")
        pct_cols = st.columns(len(periods))
        for idx, (period, pct) in enumerate(pct_stats.items()):
            with pct_cols[idx]:
                st.metric(period, f"{pct:.0f}%")
        
        # Show average and median
        summary = mobile_viz.get_stat_summary(
            player_name, 
            stat_col if stat_col else 'PTS',
            n_games=5
        )
        avg_col, median_col = st.columns(2)
        with avg_col:
            st.metric("Average", f"{summary['average']:.1f}")
        with median_col:
            st.metric("Median", f"{summary['median']:.0f}")
        
        # Show chart based on selected time period
        if time_period == "Head-to-Head":
            # Use opponent from game context or allow selection
            h2h_opponent = opponent if opponent else st.selectbox(
                "Select Opponent (H2H)",
                options=["LAL", "GSW", "BOS", "MIA", "PHI", "MIL", "DEN", "PHX"],  # Common teams
                key=f"h2h_opp_{player_name}"
            )
            n_games = 5
            fig = mobile_viz.create_mobile_style_chart(
                player_name,
                stat_col if stat_col else 'PTS',
                stat_label,
                over_under_line,
                'H2H',
                n_games,
                h2h_opponent
            )
        else:
            n_games_map = {
                'Last 1 Game': 1, 
                'Last 5 Games': 5, 
                'Last 10 Games': 10,
                'Last 20 Games': 20
            }
            n_games = n_games_map.get(time_period, 5)
            period_label = {
                'Last 1 Game': 'L1', 
                'Last 5 Games': 'L5', 
                'Last 10 Games': 'L10',
                'Last 20 Games': 'L20'
            }.get(time_period, 'L5')
            fig = mobile_viz.create_mobile_style_chart(
                player_name,
                stat_col if stat_col else 'PTS',
                stat_label,
                over_under_line,
                period_label,
                n_games,
                None
            )
        
        if fig:
            st.plotly_chart(fig, use_container_width=True, key=f"detail_chart_{player_name}")
        else:
            st.info(f"No data available for {player_name}")
    
    with tab2:
        # Advanced stats
        st.markdown("### Advanced Statistics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Rebound Chances (Last 5 Games)**")
            reb_chances = adv_stats.calculate_rebound_chances_from_games(player_name, n=5)
            if reb_chances:
                st.metric("Avg Rebound Chances/Game", f"{reb_chances['avg_rebound_chances']:.1f}")
                st.metric("Avg Actual Rebounds", f"{reb_chances['avg_rebounds']:.1f}")
                st.metric("Conversion Rate", f"{reb_chances['rebound_chance_rate']:.1%}")
        
        with col2:
            st.markdown("**Potential Assists (Last 5 Games)**")
            pot_assists = adv_stats.calculate_potential_assists_from_games(player_name, n=5)
            if pot_assists:
                st.metric("Avg Potential Assists/Game", f"{pot_assists['avg_potential_assists']:.1f}")
                st.metric("Avg Actual Assists", f"{pot_assists['avg_assists']:.1f}")
                st.metric("Conversion Rate", f"{pot_assists['conversion_rate']:.1%}")
        
        # Last 5 games table
        st.markdown("### Last 5 Games Performance")
        last_n_games = adv_stats.get_last_n_games_stats(player_name, n=5)
        if last_n_games is not None and len(last_n_games) > 0:
            display_cols = ['GAME_DATE', 'MATCHUP', 'PTS', 'REB', 'AST', 'MIN']
            available_cols = [c for c in display_cols if c in last_n_games.columns]
            st.dataframe(last_n_games[available_cols], use_container_width=True, hide_index=True)
    
    with tab3:
        # Game log
        st.markdown("### Recent Game Log")
        from src.analysis.hot_hand_tracker import HotHandTracker
        tracker = HotHandTracker()
        
        logs = tracker.get_player_gamelog(player_name, season='2025-26')
        if logs is None or len(logs) == 0:
            logs = tracker.get_player_gamelog(player_name, season='2024-25')
        
        if logs is not None and len(logs) > 0:
            show_cols = [c for c in ['GAME_DATE', 'MATCHUP', 'PTS', 'REB', 'AST', 'FG3M', 'MIN'] if c in logs.columns]
            st.dataframe(logs[show_cols].head(20), use_container_width=True, hide_index=True)
        else:
            st.info("No game log data available")


def make_player_clickable(player_name: str, key_prefix: str = "player") -> bool:
    """
    Create a clickable button/link for player name
    Returns True if clicked
    
    Args:
        player_name: Player name to display
        key_prefix: Unique key prefix for this button
    """
    session_key = f"selected_player_{key_prefix}"
    
    # Check if this player is already selected
    if st.session_state.get(session_key) == player_name:
        # Show as selected
        if st.button(f"👤 {player_name}", key=f"btn_{key_prefix}_{player_name}", type="primary"):
            st.session_state[session_key] = player_name
            return True
    else:
        # Show as unselected
        if st.button(f"👤 {player_name}", key=f"btn_{key_prefix}_{player_name}"):
            st.session_state[session_key] = player_name
            # Don't use st.rerun() - let Streamlit handle the rerun naturally
            return True
    
    return False

