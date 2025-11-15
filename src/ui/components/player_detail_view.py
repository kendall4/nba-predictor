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
from src.services.nba_com_scraper import NBAComScraper
from src.services.team_stats_analyzer import TeamStatsAnalyzer
from src.ui.nba.lines_explorer import round_to_sportsbook_line
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Visualizations", "📊 Advanced Stats", "📋 Game Log", "🏀 Team Matchup", "⚙️ Prediction Factors"])
    
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
        avg_value = summary['average'] if summary else 20.0
        
        # Round average to sportsbook format for display
        avg_rounded = round_to_sportsbook_line(avg_value)
        
        # Round suggested line to sportsbook format (whole number or .5)
        suggested_line = round_to_sportsbook_line(avg_value)
        
        # Over/under line input
        col1, col2 = st.columns([2, 1])
        with col1:
            input_key = f"detail_line_{player_name}"
            
            # Get initial value - always round it first
            # Round BEFORE creating the widget to avoid session state conflicts
            if input_key in st.session_state:
                # Round any existing value in session state BEFORE widget creation
                stored_value = st.session_state[input_key]
                initial_value = round_to_sportsbook_line(stored_value)
                # Update session state BEFORE widget creation (this is allowed)
                if abs(stored_value - initial_value) > 0.01:
                    st.session_state[input_key] = initial_value
            else:
                initial_value = suggested_line
                # Set initial rounded value in session state
                st.session_state[input_key] = initial_value
            
            # Always use rounded value for the input
            over_under_line = st.number_input(
                "Over/Under Line",
                min_value=0.0,
                value=float(initial_value),
                step=0.5,
                key=input_key,
                format="%.1f"  # Format to show 1 decimal (will be .0 or .5)
            )
            
            # Round the value for use in calculations (don't modify session state after widget)
            over_under_line = round_to_sportsbook_line(over_under_line)
        with col2:
            # Show rounded average (whole number or .5)
            st.metric("Avg", f"{avg_rounded:.1f}")
        
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
        
        # Show average and median (rounded to sportsbook format)
        summary = mobile_viz.get_stat_summary(
            player_name, 
            stat_col if stat_col else 'PTS',
            n_games=5
        )
        avg_col, median_col = st.columns(2)
        with avg_col:
            # Round average to whole number or .5
            avg_rounded = round_to_sportsbook_line(summary['average'])
            st.metric("Average", f"{avg_rounded:.1f}")
        with median_col:
            # Round median to whole number or .5
            median_rounded = round_to_sportsbook_line(summary['median'])
            st.metric("Median", f"{median_rounded:.0f}" if median_rounded == int(median_rounded) else f"{median_rounded:.1f}")
        
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
        
        # Scatter Plot Section
        st.markdown("---")
        st.markdown("#### 📊 Stat Relationship Analysis")
        st.caption("Compare two stats to see correlations and patterns")
        
        scatter_col1, scatter_col2 = st.columns(2)
        with scatter_col1:
            stat_x_options = {
                'Points': ('PTS', 'Points'),
                'Rebounds': ('REB', 'Rebounds'),
                'Assists': ('AST', 'Assists'),
                '3-Pointers': ('FG3M', '3-Pointers Made')
            }
            selected_stat_x = st.selectbox(
                "X-Axis Stat",
                options=list(stat_x_options.keys()),
                index=0,
                key=f"scatter_x_{player_name}"
            )
            stat_x_col, stat_x_label = stat_x_options[selected_stat_x]
            
            # Get line for X-axis stat if available
            line_x = None
            if selected_stat_x == 'Points' and predictions_df is not None:
                player_row = predictions_df[predictions_df['player_name'] == player_name]
                if len(player_row) > 0 and 'line_points' in player_row.columns:
                    line_x = round_to_sportsbook_line(float(player_row.iloc[0]['line_points']))
            elif selected_stat_x == 'Rebounds' and predictions_df is not None:
                player_row = predictions_df[predictions_df['player_name'] == player_name]
                if len(player_row) > 0 and 'line_rebounds' in player_row.columns:
                    line_x = round_to_sportsbook_line(float(player_row.iloc[0]['line_rebounds']))
            elif selected_stat_x == 'Assists' and predictions_df is not None:
                player_row = predictions_df[predictions_df['player_name'] == player_name]
                if len(player_row) > 0 and 'line_assists' in player_row.columns:
                    line_x = round_to_sportsbook_line(float(player_row.iloc[0]['line_assists']))
        
        with scatter_col2:
            stat_y_options = {
                'Points': ('PTS', 'Points'),
                'Rebounds': ('REB', 'Rebounds'),
                'Assists': ('AST', 'Assists'),
                '3-Pointers': ('FG3M', '3-Pointers Made')
            }
            # Remove the selected X-axis stat from Y-axis options
            available_y = {k: v for k, v in stat_y_options.items() if k != selected_stat_x}
            selected_stat_y = st.selectbox(
                "Y-Axis Stat",
                options=list(available_y.keys()),
                index=0 if list(available_y.keys())[0] != selected_stat_x else 1 if len(available_y) > 1 else 0,
                key=f"scatter_y_{player_name}"
            )
            stat_y_col, stat_y_label = available_y[selected_stat_y]
            
            # Get line for Y-axis stat if available
            line_y = None
            if selected_stat_y == 'Points' and predictions_df is not None:
                player_row = predictions_df[predictions_df['player_name'] == player_name]
                if len(player_row) > 0 and 'line_points' in player_row.columns:
                    line_y = round_to_sportsbook_line(float(player_row.iloc[0]['line_points']))
            elif selected_stat_y == 'Rebounds' and predictions_df is not None:
                player_row = predictions_df[predictions_df['player_name'] == player_name]
                if len(player_row) > 0 and 'line_rebounds' in player_row.columns:
                    line_y = round_to_sportsbook_line(float(player_row.iloc[0]['line_rebounds']))
            elif selected_stat_y == 'Assists' and predictions_df is not None:
                player_row = predictions_df[predictions_df['player_name'] == player_name]
                if len(player_row) > 0 and 'line_assists' in player_row.columns:
                    line_y = round_to_sportsbook_line(float(player_row.iloc[0]['line_assists']))
        
        # Scatter plot time period
        scatter_time_period = st.selectbox(
            "Time Period",
            options=['Last 5 Games', 'Last 10 Games', 'Last 20 Games', 'Head-to-Head'],
            index=1,
            key=f"scatter_period_{player_name}"
        )
        
        scatter_n_games = {'Last 5 Games': 5, 'Last 10 Games': 10, 'Last 20 Games': 20}.get(scatter_time_period, 10)
        scatter_opponent = None
        if scatter_time_period == 'Head-to-Head':
            scatter_opponent = opponent if opponent else st.selectbox(
                "Select Opponent (H2H)",
                options=["LAL", "GSW", "BOS", "MIA", "PHI", "MIL", "DEN", "PHX", "DAL", "NYK", "CLE", "MIN"],
                key=f"scatter_h2h_{player_name}"
            )
        
        # Create scatter plot
        scatter_fig = mobile_viz.create_scatter_plot(
            player_name,
            stat_x_col,
            stat_y_col,
            stat_x_label,
            stat_y_label,
            line_x=line_x,
            line_y=line_y,
            n_games=scatter_n_games,
            opponent=scatter_opponent
        )
        
        if scatter_fig:
            st.plotly_chart(scatter_fig, use_container_width=True, key=f"scatter_chart_{player_name}")
            
            # Add interpretation
            st.markdown("**💡 Interpretation:**")
            st.markdown("- **Green dots**: Both stats over their lines")
            st.markdown("- **Pink dots**: Both stats under their lines")
            st.markdown("- **Yellow dots**: Mixed (one over, one under)")
            st.markdown("- **Trend line**: Shows overall relationship pattern")
            st.markdown("- **Correlation**: +1.0 = perfect positive, -1.0 = perfect negative, 0 = no relationship")
        else:
            st.info(f"No data available for scatter plot")
    
    with tab4:
        # Team Matchup Stats
        st.markdown("### 🏀 Team Matchup Analysis")
        
        team_analyzer = TeamStatsAnalyzer()
        
        if opponent:
            st.markdown(f"#### Analyzing matchup vs {opponent}")
            
            # Get team defensive profile
            opponent_profile = team_analyzer.get_team_defensive_profile(opponent)
            
            if opponent_profile:
                # Show defensive rating
                st.markdown("##### 📊 Opponent Defensive Profile")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    def_rating = opponent_profile['defensive_rating']
                    league_avg = opponent_profile['league_avg_def_rating']
                    diff = def_rating - league_avg
                    color = "🟢" if diff > 2 else "🟡" if diff > -2 else "🔴"
                    st.metric(
                        "Defensive Rating",
                        f"{def_rating:.1f}",
                        delta=f"{diff:+.1f} vs avg",
                        delta_color="inverse" if diff > 2 else "normal"
                    )
                    if opponent_profile['defensive_ranking']:
                        st.caption(f"Rank: #{opponent_profile['defensive_ranking']}/30")
                
                with col2:
                    st.metric(
                        "Points Allowed/Game",
                        f"{opponent_profile['points_allowed']:.1f}",
                        delta=f"{opponent_profile['points_allowed_vs_avg']:+.1f} vs avg"
                    )
                    if opponent_profile['points_allowed_rank']:
                        st.caption(f"Rank: #{opponent_profile['points_allowed_rank']}/30")
                
                with col3:
                    st.metric(
                        "Assists Allowed/Game",
                        f"{opponent_profile['assists_allowed']:.1f}",
                        delta=f"{opponent_profile['assists_allowed_vs_avg']:+.1f} vs avg"
                    )
                
                # Rebounding stats
                st.markdown("##### 🏀 Rebounding Defense")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Rebounds Allowed", f"{opponent_profile['total_rebounds_allowed']:.1f}")
                with col2:
                    st.metric("Offensive Rebounds Allowed", f"{opponent_profile['offensive_rebounds_allowed']:.1f}")
                with col3:
                    st.metric("Defensive Rebounds Allowed", f"{opponent_profile['defensive_rebounds_allowed']:.1f}")
                
                # Show matchup analysis
                matchup_analysis = team_analyzer.get_matchup_analysis(player_name, opponent)
                
                if matchup_analysis:
                    st.markdown("---")
                    st.markdown("##### 🎯 Matchup Advantages")
                    
                    # Points matchup
                    pts_matchup = matchup_analysis['points_matchup']
                    advantage_icon = "✅" if pts_matchup['advantage'] == 'favorable' else "⚠️" if pts_matchup['advantage'] == 'neutral' else "❌"
                    st.markdown(f"**Points:** {advantage_icon} {pts_matchup['advantage'].title()}")
                    st.caption(f"Player avg: {pts_matchup['player_avg']:.1f} | Opponent allows: {pts_matchup['opponent_allows']:.1f} | Expected impact: {pts_matchup['expected_impact']:+.1f}")
                    
                    # Rebounds matchup
                    reb_matchup = matchup_analysis['rebounds_matchup']
                    advantage_icon = "✅" if reb_matchup['advantage'] == 'favorable' else "⚠️" if reb_matchup['advantage'] == 'neutral' else "❌"
                    st.markdown(f"**Rebounds:** {advantage_icon} {reb_matchup['advantage'].title()}")
                    st.caption(f"Player avg: {reb_matchup['player_avg']:.1f} | Opponent allows: {reb_matchup['opponent_allows']:.1f} | Expected impact: {reb_matchup['expected_impact']:+.1f}")
                    
                    # Assists matchup
                    ast_matchup = matchup_analysis['assists_matchup']
                    advantage_icon = "✅" if ast_matchup['advantage'] == 'favorable' else "⚠️" if ast_matchup['advantage'] == 'neutral' else "❌"
                    st.markdown(f"**Assists:** {advantage_icon} {ast_matchup['advantage'].title()}")
                    st.caption(f"Player avg: {ast_matchup['player_avg']:.1f} | Opponent allows: {ast_matchup['opponent_allows']:.1f} | Expected impact: {ast_matchup['expected_impact']:+.1f}")
                    
                    # Threes matchup if applicable
                    if 'threes_matchup' in matchup_analysis:
                        three_matchup = matchup_analysis['threes_matchup']
                        advantage_icon = "✅" if three_matchup['advantage'] == 'favorable' else "⚠️" if three_matchup['advantage'] == 'neutral' else "❌"
                        st.markdown(f"**3-Pointers:** {advantage_icon} {three_matchup['advantage'].title()}")
                        st.caption(f"Player avg: {three_matchup['player_avg']:.1f} | Opponent allows: {three_matchup['opponent_allows']:.1f} | Expected impact: {three_matchup['expected_impact']:+.1f}")
                
                # Show league averages for context
                st.markdown("---")
                st.markdown("##### 📊 League Averages (for context)")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("League Avg Points Allowed", f"{opponent_profile['league_avg_points_allowed']:.1f}")
                with col2:
                    st.metric("League Avg Rebounds Allowed", f"{opponent_profile['league_avg_rebounds_allowed']:.1f}")
                with col3:
                    st.metric("League Avg Assists Allowed", f"{opponent_profile['league_avg_assists_allowed']:.1f}")
            else:
                st.warning(f"Could not load defensive stats for {opponent}. Team stats may not be available.")
        else:
            st.info("Select a player with a game today to see matchup analysis. Or select an opponent manually:")
            
            # Manual opponent selection
            team_abbrs = [
                'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET',
                'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN',
                'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS',
                'TOR', 'UTA', 'WAS'
            ]
            selected_opponent = st.selectbox("Select opponent team", options=team_abbrs, key="manual_opponent")
            
            if selected_opponent:
                opponent_profile = team_analyzer.get_team_defensive_profile(selected_opponent)
                if opponent_profile:
                    st.markdown(f"#### Defensive Profile: {opponent_profile['team_name']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Defensive Rating", f"{opponent_profile['defensive_rating']:.1f}")
                        if opponent_profile['defensive_ranking']:
                            st.caption(f"Rank: #{opponent_profile['defensive_ranking']}/30")
                    with col2:
                        st.metric("Points Allowed", f"{opponent_profile['points_allowed']:.1f}")
                    with col3:
                        st.metric("Assists Allowed", f"{opponent_profile['assists_allowed']:.1f}")
                    
                    # Show matchup if player selected
                    if player_name:
                        matchup_analysis = team_analyzer.get_matchup_analysis(player_name, selected_opponent)
                        if matchup_analysis:
                            st.markdown("---")
                            st.markdown("##### Matchup Analysis")
                            pts_matchup = matchup_analysis['points_matchup']
                            st.write(f"**Points:** {pts_matchup['advantage'].title()} matchup")
                            st.caption(f"Player avg: {pts_matchup['player_avg']:.1f} | Opponent allows: {pts_matchup['opponent_allows']:.1f}")
    
    with tab5:
        # Prediction Factors
        st.markdown("### ⚙️ Prediction Factors Breakdown")
        st.caption("See how each weight factor affects this player's predictions")
        
        if predictions_df is not None and len(predictions_df) > 0:
            player_pred = predictions_df[predictions_df['player_name'] == player_name]
            if len(player_pred) > 0:
                player = player_pred.iloc[0]
                
                # Overall prediction summary
                st.markdown("#### 📊 Current Predictions")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Predicted Points", f"{player.get('pred_points', 0):.1f}")
                with col2:
                    st.metric("Predicted Rebounds", f"{player.get('pred_rebounds', 0):.1f}")
                with col3:
                    st.metric("Predicted Assists", f"{player.get('pred_assists', 0):.1f}")
                
                st.markdown("---")
                st.markdown("#### ⚙️ Multiplier Breakdown")
                
                # System Fit
                if 'system_fit_multiplier' in player:
                    st.markdown("##### 🎯 System Fit")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        mult = player['system_fit_multiplier']
                        delta_color = "normal" if mult > 1.0 else "inverse"
                        st.metric("System Fit", f"{mult:.3f}x", 
                                 delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                 delta_color=delta_color)
                    with col2:
                        off_fit = player.get('offensive_fit', 1.0)
                        st.metric("Offensive Fit", f"{off_fit:.3f}x")
                    with col3:
                        def_match = player.get('defensive_matchup', 1.0)
                        st.metric("Defensive Matchup", f"{def_match:.3f}x")
                    st.caption("How well player fits team's offensive system and matches up vs opponent's defense")
                
                # Recent Form
                if 'recent_form_multiplier' in player:
                    st.markdown("##### 📈 Recent Form")
                    mult = player['recent_form_multiplier']
                    delta_color = "normal" if mult > 1.0 else "inverse"
                    st.metric("Recent Form", f"{mult:.3f}x", 
                             delta=f"{((mult - 1.0) * 100):+.1f}%", 
                             delta_color=delta_color)
                    st.caption("Last 5 games performance vs season average")
                
                # H2H
                if 'h2h_multiplier' in player:
                    st.markdown("##### 🆚 Head-to-Head")
                    mult = player['h2h_multiplier']
                    delta_color = "normal" if mult > 1.0 else "inverse"
                    st.metric("H2H Multiplier", f"{mult:.3f}x", 
                             delta=f"{((mult - 1.0) * 100):+.1f}%", 
                             delta_color=delta_color)
                    st.caption("Historical performance vs this specific opponent")
                
                # Rest Days
                if 'rest_days_multiplier' in player:
                    st.markdown("##### 😴 Rest Days")
                    mult = player['rest_days_multiplier']
                    rest_info = player.get('rest_days_info', {})
                    if rest_info:
                        days_rest = rest_info.get('days_rest', 'N/A')
                        adj_type = rest_info.get('adjustment_type', 'Unknown')
                        delta_color = "normal" if mult > 1.0 else "inverse"
                        st.metric("Rest Days", f"{mult:.3f}x", 
                                 delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                 delta_color=delta_color)
                        st.caption(f"{adj_type} ({days_rest} days rest)")
                    else:
                        delta_color = "normal" if mult > 1.0 else "inverse"
                        st.metric("Rest Days", f"{mult:.3f}x", 
                                 delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                 delta_color=delta_color)
                
                # Home/Away
                if 'home_away_multiplier' in player:
                    st.markdown("##### 🏠 Home/Away")
                    mult = player['home_away_multiplier']
                    ha_info = player.get('home_away_info', {})
                    if ha_info:
                        is_home = ha_info.get('is_home', False)
                        location = "Home" if is_home else "Away"
                        delta_color = "normal" if mult > 1.0 else "inverse"
                        st.metric("Home/Away", f"{mult:.3f}x", 
                                 delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                 delta_color=delta_color)
                        st.caption(f"{location} game adjustment")
                    else:
                        delta_color = "normal" if mult > 1.0 else "inverse"
                        st.metric("Home/Away", f"{mult:.3f}x", 
                                 delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                 delta_color=delta_color)
                
                # Play Style
                if 'play_style_multiplier' in player:
                    st.markdown("##### 🎨 Play Style Matchup")
                    mult = player['play_style_multiplier']
                    ps_info = player.get('play_style_info', {})
                    if ps_info:
                        team_style = ps_info.get('team_style', 'Unknown')
                        advantage = ps_info.get('advantage', 1.0)
                        delta_color = "normal" if mult > 1.0 else "inverse"
                        st.metric("Play Style", f"{mult:.3f}x", 
                                 delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                 delta_color=delta_color)
                        st.caption(f"Team style: {team_style} | Advantage: {advantage:.3f}x")
                    else:
                        delta_color = "normal" if mult > 1.0 else "inverse"
                        st.metric("Play Style", f"{mult:.3f}x", 
                                 delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                 delta_color=delta_color)
                
                # Upside
                if 'upside_points_multiplier' in player or 'upside_rebounds_multiplier' in player or 'upside_assists_multiplier' in player:
                    st.markdown("##### ⬆️ Upside/Ceiling Potential")
                    upside_info = player.get('upside_info', {})
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if 'upside_points_multiplier' in player:
                            mult = player['upside_points_multiplier']
                            delta_color = "normal" if mult > 1.0 else "inverse"
                            st.metric("Upside (Points)", f"{mult:.3f}x", 
                                     delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                     delta_color=delta_color)
                            if upside_info and upside_info.get('points_career_high'):
                                st.caption(f"Career high: {upside_info['points_career_high']:.1f}")
                    with col2:
                        if 'upside_rebounds_multiplier' in player:
                            mult = player['upside_rebounds_multiplier']
                            delta_color = "normal" if mult > 1.0 else "inverse"
                            st.metric("Upside (Rebounds)", f"{mult:.3f}x", 
                                     delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                     delta_color=delta_color)
                    with col3:
                        if 'upside_assists_multiplier' in player:
                            mult = player['upside_assists_multiplier']
                            delta_color = "normal" if mult > 1.0 else "inverse"
                            st.metric("Upside (Assists)", f"{mult:.3f}x", 
                                     delta=f"{((mult - 1.0) * 100):+.1f}%", 
                                     delta_color=delta_color)
                    
                    if upside_info and upside_info.get('has_data'):
                        st.caption(f"Based on career highs, volatility, and star status. Career high: {upside_info.get('points_career_high', 0):.1f} pts, 90th percentile: {upside_info.get('points_90th', 0):.1f} pts")
                
                # Combined effect
                st.markdown("---")
                st.markdown("#### 📊 Combined Effect")
                
                # Calculate combined multiplier for each stat
                base_mult = (player.get('system_fit_multiplier', 1.0) * 
                            player.get('recent_form_multiplier', 1.0) * 
                            player.get('h2h_multiplier', 1.0) *
                            player.get('rest_days_multiplier', 1.0) * 
                            player.get('home_away_multiplier', 1.0) * 
                            player.get('play_style_multiplier', 1.0))
                
                pts_combined = base_mult * player.get('upside_points_multiplier', 1.0)
                reb_combined = base_mult * player.get('upside_rebounds_multiplier', 1.0)
                ast_combined = base_mult * player.get('upside_assists_multiplier', 1.0)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Points Combined Mult", f"{pts_combined:.3f}x")
                    st.caption(f"Base: {base_mult:.3f}x × Upside: {player.get('upside_points_multiplier', 1.0):.3f}x")
                with col2:
                    st.metric("Rebounds Combined Mult", f"{reb_combined:.3f}x")
                    st.caption(f"Base: {base_mult:.3f}x × Upside: {player.get('upside_rebounds_multiplier', 1.0):.3f}x")
                with col3:
                    st.metric("Assists Combined Mult", f"{ast_combined:.3f}x")
                    st.caption(f"Base: {base_mult:.3f}x × Upside: {player.get('upside_assists_multiplier', 1.0):.3f}x")
            else:
                st.info("No prediction data available for this player. Generate predictions first.")
        else:
            st.info("No prediction data available. Generate predictions to see factor breakdowns.")
    
    with tab2:
        # Advanced stats
        st.markdown("### Advanced Statistics")
        
        # Get comprehensive stats from NBA.com scraper
        scraper = NBAComScraper()
        comprehensive_stats = scraper.get_comprehensive_player_stats(player_name)
        
        if comprehensive_stats:
            st.markdown("#### 📊 Season Averages")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Points", f"{comprehensive_stats['points_per_game']:.1f}")
                st.metric("Rebounds", f"{comprehensive_stats['rebounds_per_game']:.1f}")
            
            with col2:
                st.metric("Assists", f"{comprehensive_stats['assists_per_game']:.1f}")
                st.metric("Minutes", f"{comprehensive_stats['minutes_per_game']:.1f}")
            
            with col3:
                st.metric("FG%", f"{comprehensive_stats['field_goal_percentage']:.1f}%")
                st.metric("3P%", f"{comprehensive_stats['three_point_percentage']:.1f}%")
            
            with col4:
                st.metric("FT%", f"{comprehensive_stats['free_throw_percentage']:.1f}%")
                if comprehensive_stats.get('three_pointers_made', 0) > 0:
                    st.metric("3PM", f"{comprehensive_stats['three_pointers_made']:.1f}")
            
            # Advanced metrics if available
            if comprehensive_stats.get('true_shooting_percentage'):
                col5, col6 = st.columns(2)
                with col5:
                    st.metric("True Shooting %", f"{comprehensive_stats['true_shooting_percentage']:.1f}%")
                with col6:
                    if comprehensive_stats.get('estimated_usage_rate'):
                        st.metric("Usage Rate (est.)", f"{comprehensive_stats['estimated_usage_rate']:.1f}")
            
            st.markdown("---")
        
        st.markdown("#### 📈 Advanced Metrics (Last 5 Games)")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Rebound Chances**")
            reb_chances = adv_stats.calculate_rebound_chances_from_games(player_name, n=5)
            if reb_chances:
                st.metric("Avg Rebound Chances/Game", f"{reb_chances['avg_rebound_chances']:.1f}")
                st.metric("Avg Actual Rebounds", f"{reb_chances['avg_rebounds']:.1f}")
                st.metric("Conversion Rate", f"{reb_chances['rebound_chance_rate']:.1%}")
        
        with col2:
            st.markdown("**Potential Assists**")
            pot_assists = adv_stats.calculate_potential_assists_from_games(player_name, n=5)
            if pot_assists:
                st.metric("Avg Potential Assists/Game", f"{pot_assists['avg_potential_assists']:.1f}")
                st.metric("Avg Actual Assists", f"{pot_assists['avg_assists']:.1f}")
                st.metric("Conversion Rate", f"{pot_assists['conversion_rate']:.1%}")
        
        # Last 5 games table
        st.markdown("---")
        st.markdown("#### 📋 Last 5 Games Performance")
        last_n_games = adv_stats.get_last_n_games_stats(player_name, n=5)
        if last_n_games is not None and len(last_n_games) > 0:
            display_cols = ['GAME_DATE', 'MATCHUP', 'PTS', 'REB', 'AST', 'MIN', 'FG_PCT', 'FG3_PCT']
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

