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

def calculate_h2h_hit_rate(tracker, player_name, opponent, stat_type, line_value):
    """Calculate H2H hit rate using HotHandTracker's consistency_h2h method"""
    try:
        # Map stat names to stat_type format
        stat_map = {
            'PTS': 'points',
            'REB': 'rebounds',
            'AST': 'assists'
        }
        stat_type_key = stat_map.get(stat_type, 'points')
        
        result = tracker.consistency_h2h(player_name, stat_type_key, line_value, opponent, season='2025-26')
        if result and result.get('hit_rate') is not None:
            return round(result['hit_rate'] * 100, 1)  # Convert to percentage
    except Exception:
        pass
    return None

def calculate_matchup_hit_rate(tracker, player_name, opponent, stat_col, line_value):
    """Calculate hit rate for all games against this specific opponent (individual matchup)"""
    try:
        # Get game logs for both seasons
        h2h_games = []
        for season in ['2025-26', '2024-25']:
            game_log = tracker.get_player_gamelog(player_name, season=season)
            if game_log is not None and len(game_log) > 0:
                game_log = game_log.copy()
                game_log['OPP'] = game_log['MATCHUP'].apply(tracker._parse_opponent_from_matchup)
                h2h = game_log[game_log['OPP'] == opponent]
                if len(h2h) > 0:
                    h2h_games.append(h2h)
        
        if not h2h_games:
            return None
        
        # Combine all H2H games
        h2h_combined = pd.concat(h2h_games, ignore_index=True) if len(h2h_games) > 1 else h2h_games[0]
        
        if stat_col not in h2h_combined.columns:
            return None
        
        # Calculate hit rate for all games vs this opponent
        valid = h2h_combined[pd.notna(h2h_combined[stat_col])]
        if len(valid) == 0:
            return None
        
        exceeded = (valid[stat_col] > line_value).sum()
        total = len(valid)
        
        if total == 0:
            return None
        
        hit_rate = (exceeded / total) * 100
        return round(hit_rate, 1)
    except Exception:
        pass
    return None

def calculate_implied_probability(prediction, line, stat_type='points'):
    """Calculate implied probability from prediction vs line using normal distribution"""
    from src.utils.odds_utils import calculate_implied_prob_from_line
    
    # Use different std_dev based on stat type
    if stat_type == 'points':
        std_dev = prediction * 0.20  # 20% variance for points
    elif stat_type == 'rebounds':
        std_dev = prediction * 0.25  # 25% variance for rebounds
    elif stat_type == 'assists':
        std_dev = prediction * 0.30  # 30% variance for assists
    else:
        std_dev = prediction * 0.20
    
    prob = calculate_implied_prob_from_line(line, prediction, std_dev)
    return prob * 100  # Convert to percentage

def get_opponent_rank(opponent_team, stat_type):
    """Get opponent's defensive rank for the stat"""
    try:
        from src.services.team_stats_analyzer import TeamStatsAnalyzer
        analyzer = TeamStatsAnalyzer()
        profile = analyzer.get_team_defensive_profile(opponent_team)
        
        if profile:
            if stat_type == 'points':
                return profile.get('points_allowed_rank')
            elif stat_type == 'rebounds':
                # Use total rebounds allowed rank (or could use defensive rating)
                return profile.get('defensive_ranking')  # Placeholder - would need rebounds allowed rank
            elif stat_type == 'assists':
                return profile.get('assists_allowed_rank')
    except Exception:
        pass
    return None

def render(predictions):
    st.header("📊 Props")
    st.caption("💡 Player-stat combinations ranked by value with hit rates and prediction factors")
    
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
            pred_pts = player['pred_points']
            hit_3 = calculate_hit_rate(game_log, 'PTS', line_pts, 3)
            hit_5 = calculate_hit_rate(game_log, 'PTS', line_pts, 5)
            hit_8 = calculate_hit_rate(game_log, 'PTS', line_pts, 8)
            hit_10 = calculate_hit_rate(game_log, 'PTS', line_pts, 10)
            h2h_hit = calculate_h2h_hit_rate(tracker, player_name, opponent, 'PTS', line_pts) if opponent else None
            matchup_hit = calculate_matchup_hit_rate(tracker, player_name, opponent, 'PTS', line_pts) if opponent else None
            ip = calculate_implied_probability(pred_pts, line_pts, 'points')
            opp_rank = get_opponent_rank(opponent, 'points')
            
            stat_rows.append({
                'player_name': player_name,
                'team': team,
                'opponent': opponent,
                'stat': 'Points',
                'stat_short': 'PTS',
                'prediction': round(pred_pts, 1),
                'line': line_pts,
                'value': round(player['point_value'], 2),
                'hit_3': hit_3 if hit_3 is not None else None,
                'hit_5': hit_5 if hit_5 is not None else None,
                'hit_8': hit_8 if hit_8 is not None else None,
                'hit_10': hit_10 if hit_10 is not None else None,
                'h2h': h2h_hit if h2h_hit is not None else None,
                'matchup': matchup_hit if matchup_hit is not None else None,
                'ip': round(ip, 0) if ip else None,
                'opp_rank': opp_rank,
                'player_data': player
            })
        
        # Rebounds row
        if 'pred_rebounds' in player and 'line_rebounds' in player and 'rebound_value' in player:
            line_reb = player['line_rebounds']
            pred_reb = player['pred_rebounds']
            hit_3 = calculate_hit_rate(game_log, 'REB', line_reb, 3)
            hit_5 = calculate_hit_rate(game_log, 'REB', line_reb, 5)
            hit_8 = calculate_hit_rate(game_log, 'REB', line_reb, 8)
            hit_10 = calculate_hit_rate(game_log, 'REB', line_reb, 10)
            h2h_hit = calculate_h2h_hit_rate(tracker, player_name, opponent, 'REB', line_reb) if opponent else None
            matchup_hit = calculate_matchup_hit_rate(tracker, player_name, opponent, 'REB', line_reb) if opponent else None
            ip = calculate_implied_probability(pred_reb, line_reb, 'rebounds')
            opp_rank = get_opponent_rank(opponent, 'rebounds')
            
            stat_rows.append({
                'player_name': player_name,
                'team': team,
                'opponent': opponent,
                'stat': 'Rebounds',
                'stat_short': 'REB',
                'prediction': round(pred_reb, 1),
                'line': line_reb,
                'value': round(player['rebound_value'], 2),
                'hit_3': hit_3 if hit_3 is not None else None,
                'hit_5': hit_5 if hit_5 is not None else None,
                'hit_8': hit_8 if hit_8 is not None else None,
                'hit_10': hit_10 if hit_10 is not None else None,
                'h2h': h2h_hit if h2h_hit is not None else None,
                'matchup': matchup_hit if matchup_hit is not None else None,
                'ip': round(ip, 0) if ip else None,
                'opp_rank': opp_rank,
                'player_data': player
            })
        
        # Assists row
        if 'pred_assists' in player and 'line_assists' in player and 'assist_value' in player:
            line_ast = player['line_assists']
            pred_ast = player['pred_assists']
            hit_3 = calculate_hit_rate(game_log, 'AST', line_ast, 3)
            hit_5 = calculate_hit_rate(game_log, 'AST', line_ast, 5)
            hit_8 = calculate_hit_rate(game_log, 'AST', line_ast, 8)
            hit_10 = calculate_hit_rate(game_log, 'AST', line_ast, 10)
            h2h_hit = calculate_h2h_hit_rate(tracker, player_name, opponent, 'AST', line_ast) if opponent else None
            matchup_hit = calculate_matchup_hit_rate(tracker, player_name, opponent, 'AST', line_ast) if opponent else None
            ip = calculate_implied_probability(pred_ast, line_ast, 'assists')
            opp_rank = get_opponent_rank(opponent, 'assists')
            
            stat_rows.append({
                'player_name': player_name,
                'team': team,
                'opponent': opponent,
                'stat': 'Assists',
                'stat_short': 'AST',
                'prediction': round(pred_ast, 1),
                'line': line_ast,
                'value': round(player['assist_value'], 2),
                'hit_3': hit_3 if hit_3 is not None else None,
                'hit_5': hit_5 if hit_5 is not None else None,
                'hit_8': hit_8 if hit_8 is not None else None,
                'hit_10': hit_10 if hit_10 is not None else None,
                'h2h': h2h_hit if h2h_hit is not None else None,
                'matchup': matchup_hit if matchup_hit is not None else None,
                'ip': round(ip, 0) if ip else None,
                'opp_rank': opp_rank,
                'player_data': player
            })
    
    if not stat_rows:
        st.warning("No prediction data available")
        return
    
    # Create DataFrame and sort by value (descending)
    display_df = pd.DataFrame(stat_rows)
    display_df = display_df.sort_values('value', ascending=False)
    
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
        filtered_df = filtered_df[filtered_df['stat'] == stat_filter]
    
    filtered_df = filtered_df[filtered_df['value'] >= min_value]
    
    if show_direction == 'OVER Only':
        filtered_df = filtered_df[filtered_df['value'] > 0]
    elif show_direction == 'UNDER Only':
        filtered_df = filtered_df[filtered_df['value'] < 0]
    
    # Reset index after filtering
    filtered_df = filtered_df.reset_index(drop=True)
    
    # Toggle for prediction factors
    show_factors = st.toggle("Show Prediction Factors", value=False,
                            help="Show detailed multiplier breakdowns for each prediction")
    
    # Display as cards (similar to mobile app)
    for idx, row in filtered_df.iterrows():
        # Determine if this is an OVER or UNDER bet
        is_over = row['value'] > 0
        bet_direction = "Over" if is_over else "Under"
        
        # Seamless table-like layout
        with st.container():
            # Helper function to format percentage
            def format_percentage(val):
                if val is not None and not pd.isna(val):
                    try:
                        val_int = int(val)
                        return f"{val_int}%"
                    except (ValueError, TypeError):
                        return "—"
                return "—"
            
            # Get all values
            opp_rank = row.get('opp_rank')
            try:
                opp_rank_display = f"#{int(opp_rank)}" if opp_rank is not None and not pd.isna(opp_rank) else "—"
            except (ValueError, TypeError):
                opp_rank_display = "—"
            ip_display = format_percentage(row.get('ip'))
            l3_display = format_percentage(row.get('hit_3'))
            l5_display = format_percentage(row.get('hit_5'))
            l8_display = format_percentage(row.get('hit_8'))
            l10_display = format_percentage(row.get('hit_10'))
            h2h_display = format_percentage(row.get('h2h'))
            matchup_display = format_percentage(row.get('matchup'))
            value_color = "🟢" if row['value'] > 1.0 else "🟡" if row['value'] > 0 else "🔴"
            
            # Row 1: Player name
            st.markdown(f"**{row['player_name']} ({row['team']})**")
            
            # Row 2: Stat/Prop
            st.markdown(f"{bet_direction} {row['line']:.1f} {row['stat']}")
            
            # Row 3: All percentages in one row with | separator (two spaces on each side)
            st.markdown(
                f"IP: {ip_display}  |  "
                f"L3: {l3_display}  |  "
                f"L5: {l5_display}  |  "
                f"L8: {l8_display}  |  "
                f"L10: {l10_display}  |  "
                f"H2H: {h2h_display}  |  "
                f"Matchup: {matchup_display}  |  "
                f"OPP: {opp_rank_display} {row['opponent']}  |  "
                f"{value_color} **{row['value']:+.2f}**"
            )
            
            # Show prediction factors if enabled
            if show_factors:
                with st.expander(f"⚙️ Prediction Factors", expanded=False):
                    player_data = row['player_data']
                    stat_type = row['stat'].lower()
                    
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
                        st.write(f"**Prediction:** {row['prediction']:.1f}")
                        st.write(f"**Value:** {row['value']:+.2f}")
                        hit_5_val = row.get('hit_5')
                        if hit_5_val is not None and not pd.isna(hit_5_val):
                            try:
                                st.write(f"**5-Game Hit Rate:** {int(hit_5_val)}%")
                            except (ValueError, TypeError):
                                pass
                        ip_val = row.get('ip')
                        if ip_val is not None and not pd.isna(ip_val):
                            try:
                                st.write(f"**Implied Probability:** {int(ip_val)}%")
                            except (ValueError, TypeError):
                                pass
            
            st.markdown("---")
    
    # Summary stats
    st.markdown("### Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Plays", len(filtered_df))
    with col2:
        over_count = len(filtered_df[filtered_df['value'] > 0])
        st.metric("OVER Plays", over_count)
    with col3:
        under_count = len(filtered_df[filtered_df['value'] < 0])
        st.metric("UNDER Plays", under_count)
    with col4:
        avg_value = filtered_df['value'].mean()
        st.metric("Avg Value", f"{avg_value:+.2f}")
    
    # Download
    download_cols = ['player_name', 'team', 'opponent', 'stat', 'prediction', 'line', 
                     'value', 'hit_3', 'hit_5', 'hit_8', 'hit_10', 'h2h', 'matchup', 'ip']
    # Only include columns that exist in the dataframe
    available_cols = [col for col in download_cols if col in filtered_df.columns]
    download_df = filtered_df[available_cols].copy()
    csv = download_df.to_csv(index=False)
    st.download_button("📥 Download Predictions (CSV)", csv, 
                      "nba_predictions.csv", "text/csv", use_container_width=True)


