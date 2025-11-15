import streamlit as st
import pandas as pd
import numpy as np

def calculate_hit_rate(game_log, stat_col, line_value, n_games):
    """Calculate hit rate (% of games where player exceeded line) over last N games"""
    if game_log is None or len(game_log) == 0:
        return None
    
    if stat_col not in game_log.columns:
        return None
    
    # Get last N games
    recent = game_log.head(n_games)
    
    if len(recent) == 0:
        return None
    
    # Count how many games exceeded the line
    exceeded = (recent[stat_col] > line_value).sum()
    total = len(recent)
    
    if total == 0:
        return None
    
    hit_rate = (exceeded / total) * 100
    return round(hit_rate, 1)

def render(predictions):
    st.header("📊 All Predictions")
    st.caption("💡 Each row shows a player-stat combination with hit rates and value")
    
    # Load game log tracker for hit rate calculations
    from src.analysis.hot_hand_tracker import HotHandTracker
    tracker = HotHandTracker(blend_mode="latest")
    
    # Transform predictions to player-stat combinations with hit rates
    stat_rows = []
    
    for _, player in predictions.iterrows():
        player_name = player['player_name']
        team = player.get('team', '')
        opponent = player.get('opponent', '')
        
        # Get game log for this player (cached)
        game_log = tracker.get_player_gamelog(player_name, season='2025-26')
        if game_log is None or len(game_log) == 0:
            game_log = tracker.get_player_gamelog(player_name, season='2024-25')
        
        # Points row
        if 'pred_points' in player and 'line_points' in player and 'point_value' in player:
            line_pts = player['line_points']
            hit_3 = calculate_hit_rate(game_log, 'PTS', line_pts, 3)
            hit_5 = calculate_hit_rate(game_log, 'PTS', line_pts, 5)
            hit_10 = calculate_hit_rate(game_log, 'PTS', line_pts, 10)
            
            stat_rows.append({
                'Player': player_name,
                'Team': team,
                'Opponent': opponent,
                'Stat': 'Points',
                'Prediction': round(player['pred_points'], 1),
                'Hit Rate (3)': hit_3 if hit_3 is not None else 'N/A',
                'Hit Rate (5)': hit_5 if hit_5 is not None else 'N/A',
                'Hit Rate (10)': hit_10 if hit_10 is not None else 'N/A',
                'Value': round(player['point_value'], 2),
                'player_name': player_name,
                'stat_type': 'points',
                'line': line_pts,
                'player_data': player  # Keep full player data for factors
            })
        
        # Rebounds row
        if 'pred_rebounds' in player and 'line_rebounds' in player and 'rebound_value' in player:
            line_reb = player['line_rebounds']
            hit_3 = calculate_hit_rate(game_log, 'REB', line_reb, 3)
            hit_5 = calculate_hit_rate(game_log, 'REB', line_reb, 5)
            hit_10 = calculate_hit_rate(game_log, 'REB', line_reb, 10)
            
            stat_rows.append({
                'Player': player_name,
                'Team': team,
                'Opponent': opponent,
                'Stat': 'Rebounds',
                'Prediction': round(player['pred_rebounds'], 1),
                'Hit Rate (3)': hit_3 if hit_3 is not None else 'N/A',
                'Hit Rate (5)': hit_5 if hit_5 is not None else 'N/A',
                'Hit Rate (10)': hit_10 if hit_10 is not None else 'N/A',
                'Value': round(player['rebound_value'], 2),
                'player_name': player_name,
                'stat_type': 'rebounds',
                'line': line_reb,
                'player_data': player
            })
        
        # Assists row
        if 'pred_assists' in player and 'line_assists' in player and 'assist_value' in player:
            line_ast = player['line_assists']
            hit_3 = calculate_hit_rate(game_log, 'AST', line_ast, 3)
            hit_5 = calculate_hit_rate(game_log, 'AST', line_ast, 5)
            hit_10 = calculate_hit_rate(game_log, 'AST', line_ast, 10)
            
            stat_rows.append({
                'Player': player_name,
                'Team': team,
                'Opponent': opponent,
                'Stat': 'Assists',
                'Prediction': round(player['pred_assists'], 1),
                'Hit Rate (3)': hit_3 if hit_3 is not None else 'N/A',
                'Hit Rate (5)': hit_5 if hit_5 is not None else 'N/A',
                'Hit Rate (10)': hit_10 if hit_10 is not None else 'N/A',
                'Value': round(player['assist_value'], 2),
                'player_name': player_name,
                'stat_type': 'assists',
                'line': line_ast,
                'player_data': player
            })
    
    if not stat_rows:
        st.warning("No prediction data available")
        return
    
    # Create DataFrame and sort by value (descending)
    display_df = pd.DataFrame(stat_rows)
    display_df = display_df.sort_values('Value', ascending=False)
    
    # Add rank column
    display_df.insert(0, 'Rank', range(1, len(display_df) + 1))
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        stat_filter = st.selectbox("Filter by Stat", 
                                  options=['All', 'Points', 'Rebounds', 'Assists'],
                                  key='predictions_stat_filter')
    with col2:
        min_value = st.number_input("Min Value Score", 
                                   min_value=-10.0, max_value=10.0, value=-5.0, step=0.5,
                                   key='predictions_min_value')
    with col3:
        show_direction = st.selectbox("Show", 
                                     options=['All', 'OVER Only', 'UNDER Only'],
                                     key='predictions_direction')
    
    # Apply filters
    filtered_df = display_df.copy()
    
    if stat_filter != 'All':
        filtered_df = filtered_df[filtered_df['Stat'] == stat_filter]
    
    filtered_df = filtered_df[filtered_df['Value'] >= min_value]
    
    if show_direction == 'OVER Only':
        filtered_df = filtered_df[filtered_df['Value'] > 0]
    elif show_direction == 'UNDER Only':
        filtered_df = filtered_df[filtered_df['Value'] < 0]
    
    # Re-rank after filtering
    filtered_df = filtered_df.reset_index(drop=True)
    filtered_df['Rank'] = range(1, len(filtered_df) + 1)
    
    # Toggle for prediction factors
    show_factors = st.toggle("Show Prediction Factors", value=False,
                            help="Show detailed multiplier breakdowns for each prediction")
    
    # Display main table
    display_cols = ['Rank', 'Player', 'Team', 'Opponent', 'Stat', 'Prediction', 
                    'Hit Rate (3)', 'Hit Rate (5)', 'Hit Rate (10)', 'Value']
    display_df_final = filtered_df[display_cols].copy()
    
    st.dataframe(display_df_final, use_container_width=True, hide_index=True)
    
    # Show prediction factors if enabled
    if show_factors:
        st.markdown("---")
        st.subheader("⚙️ Prediction Factors Breakdown")
        
        # Show factors for top N players
        top_n = st.slider("Show factors for top N plays", 5, 50, 10, key='predictions_factors_top_n')
        top_plays = filtered_df.head(top_n)
        
        for idx, row in top_plays.iterrows():
            player_data = row['player_data']
            stat_type = row['stat_type']
            
            with st.expander(f"{row['Rank']}. {row['Player']} - {row['Stat']} (Value: {row['Value']:+.2f})", expanded=False):
                # Convert player_data Series to dict if needed
                player_dict = player_data.to_dict() if hasattr(player_data, 'to_dict') else dict(player_data)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Multipliers:**")
                    factors = []
                    
                    # System Fit
                    if 'system_fit_multiplier' in player_dict and player_dict.get('system_fit_multiplier', 1.0) != 1.0:
                        factors.append(('System Fit', player_dict.get('system_fit_multiplier', 1.0)))
                    
                    # Recent Form
                    if 'recent_form_multiplier' in player_dict and player_dict.get('recent_form_multiplier', 1.0) != 1.0:
                        factors.append(('Recent Form', player_dict.get('recent_form_multiplier', 1.0)))
                    
                    # H2H
                    if 'h2h_multiplier' in player_dict and player_dict.get('h2h_multiplier', 1.0) != 1.0:
                        factors.append(('H2H', player_dict.get('h2h_multiplier', 1.0)))
                    
                    # Rest Days
                    if 'rest_days_multiplier' in player_dict and player_dict.get('rest_days_multiplier', 1.0) != 1.0:
                        factors.append(('Rest Days', player_dict.get('rest_days_multiplier', 1.0)))
                    
                    # Home/Away
                    if 'home_away_multiplier' in player_dict and player_dict.get('home_away_multiplier', 1.0) != 1.0:
                        factors.append(('Home/Away', player_dict.get('home_away_multiplier', 1.0)))
                    
                    # Play Style
                    if 'play_style_multiplier' in player_dict and player_dict.get('play_style_multiplier', 1.0) != 1.0:
                        factors.append(('Play Style', player_dict.get('play_style_multiplier', 1.0)))
                    
                    # Upside (stat-specific)
                    if stat_type == 'points' and 'upside_points_multiplier' in player_dict:
                        mult = player_dict.get('upside_points_multiplier', 1.0)
                        if mult != 1.0:
                            factors.append(('Upside', mult))
                    elif stat_type == 'rebounds' and 'upside_rebounds_multiplier' in player_dict:
                        mult = player_dict.get('upside_rebounds_multiplier', 1.0)
                        if mult != 1.0:
                            factors.append(('Upside', mult))
                    elif stat_type == 'assists' and 'upside_assists_multiplier' in player_dict:
                        mult = player_dict.get('upside_assists_multiplier', 1.0)
                        if mult != 1.0:
                            factors.append(('Upside', mult))
                    
                    # Usage/Ball Dominance (for assists)
                    if stat_type == 'assists' and 'usage_ball_dominance_multiplier' in player_dict:
                        mult = player_dict.get('usage_ball_dominance_multiplier', 1.0)
                        if mult != 1.0:
                            factors.append(('Usage/Ball Dominance', mult))
                    
                    if factors:
                        for factor_name, multiplier in factors:
                            delta_color = "normal" if multiplier > 1.0 else "inverse"
                            st.metric(factor_name, f"{multiplier:.3f}x",
                                     delta=f"{((multiplier - 1.0) * 100):+.1f}%",
                                     delta_color=delta_color)
                    else:
                        st.info("All factors neutral (1.0x)")
                
                with col2:
                    st.markdown("**Context:**")
                    st.write(f"**Line:** {row['line']:.1f}")
                    st.write(f"**Prediction:** {row['Prediction']:.1f}")
                    st.write(f"**Value:** {row['Value']:+.2f}")
                    if row['Hit Rate (5)'] != 'N/A':
                        st.write(f"**5-Game Hit Rate:** {row['Hit Rate (5)']}%")
    
    # Summary stats
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Plays", len(filtered_df))
    with col2:
        over_count = len(filtered_df[filtered_df['Value'] > 0])
        st.metric("OVER Plays", over_count)
    with col3:
        under_count = len(filtered_df[filtered_df['Value'] < 0])
        st.metric("UNDER Plays", under_count)
    with col4:
        avg_value = filtered_df['Value'].mean()
        st.metric("Avg Value", f"{avg_value:+.2f}")
    
    # Download
    download_df = filtered_df[display_cols].copy()
    csv = download_df.to_csv(index=False)
    st.download_button("📥 Download Filtered Predictions (CSV)", csv, 
                      "nba_predictions_filtered.csv", "text/csv", use_container_width=True)


