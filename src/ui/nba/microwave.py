"""
Microwave Tab
=============
Show players who heat up quickly - stats in first 3 minutes and first 5 minutes.
"""

import streamlit as st
import pandas as pd
from src.services.microwave_tracker import MicrowaveTracker


def render(predictions, games):
    """
    Render the Microwave analysis page
    
    Args:
        predictions: DataFrame with player predictions
        games: List of today's games [{'home': 'LAL', 'away': 'GSW'}, ...]
    """
    st.header("🔥 Microwave - Quick Start Tracker")
    st.caption("Players who heat up fast: Estimated stats in first 3 minutes and first 5 minutes")
    
    if predictions is None or len(predictions) == 0:
        st.info("Generate predictions first to see microwave analysis.")
        return
    
    if games is None or len(games) == 0:
        st.info("No games scheduled for today.")
        return
    
    # Get teams playing today
    teams_playing_today = set()
    for game in games:
        teams_playing_today.add(game['home'])
        teams_playing_today.add(game['away'])
    
    # Filter predictions to only players from teams playing today
    predictions_filtered = predictions.copy()
    predictions_filtered = predictions_filtered[
        predictions_filtered['team'].isin(teams_playing_today)
    ]
    
    if len(predictions_filtered) == 0:
        st.warning("No players found from teams playing today.")
        st.info(f"Teams playing today: {', '.join(sorted(teams_playing_today))}")
        return
    
    num_players_today = len(predictions_filtered['player_name'].unique())
    num_games = len(games)
    st.success(f"✅ {num_players_today} players from {num_games} game(s) today")
    st.caption(f"Teams playing: {', '.join(sorted(teams_playing_today))}")
    
    try:
        tracker = MicrowaveTracker()
    except Exception as e:
        st.error(f"❌ Error initializing microwave tracker: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return
    
    # Filters
    st.markdown("---")
    st.subheader("🔍 Filters")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        stat_type = st.selectbox(
            "Stat Type",
            options=["points", "rebounds", "assists", "threes"],
            index=0,
            key="microwave_stat_type"
        )
        time_window = st.selectbox(
            "Time Window",
            options=["3min", "5min"],
            index=0,
            format_func=lambda x: "First 3 Minutes" if x == "3min" else "First 5 Minutes",
            key="microwave_time_window"
        )
    
    with col2:
        min_minutes = st.slider("Min Minutes", 0.0, 40.0, 15.0, 1.0, key="microwave_min_minutes")
        min_microwave_score = st.slider("Min Microwave Score", 0.0, 20.0, 0.0, 0.5, key="microwave_min_score")
    
    with col3:
        sort_by = st.selectbox(
            "Sort By",
            options=[
                "Microwave Score",
                f"First {time_window} {stat_type.title()}",
                "Season PPG",
                "Expected Minutes"
            ],
            index=0,
            key="microwave_sort_by"
        )
    
    # Calculate microwave stats
    try:
        calc_status = st.empty()
        num_players = len(predictions_filtered['player_name'].unique())
        calc_status.info(f"🔄 Calculating microwave stats for {num_players} players playing today...")
        
        microwave_df = tracker.get_all_microwave_players(predictions_filtered, season='2025-26')
        
        calc_status.empty()
    except Exception as e:
        calc_status.empty()
        st.error(f"❌ Error calculating microwave stats: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return
    
    if microwave_df is None or len(microwave_df) == 0:
        st.warning("No microwave data available.")
        return
    
    # Apply filters
    filtered_df = microwave_df.copy()
    filtered_df = filtered_df[filtered_df['expected_minutes'] >= min_minutes]
    filtered_df = filtered_df[filtered_df['microwave_score'] >= min_microwave_score]
    
    # Sort
    sort_map = {
        "Microwave Score": "microwave_score",
        f"First {time_window} {stat_type.title()}": f"first_{time_window}_{stat_type}",
        "Season PPG": "season_ppg",
        "Expected Minutes": "expected_minutes"
    }
    sort_col = sort_map.get(sort_by, "microwave_score")
    if sort_col in filtered_df.columns:
        filtered_df = filtered_df.sort_values(sort_col, ascending=False)
    
    if len(filtered_df) == 0:
        st.warning("No players match the current filters.")
        return
    
    st.success(f"✅ Analyzed {len(filtered_df)} players")
    
    # Main display
    st.markdown("---")
    st.subheader(f"🔥 Microwave Leaders ({len(filtered_df)} players)")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        avg_3min_pts = filtered_df['first_3_min_points'].mean()
        st.metric("Avg First 3 Min Points", f"{avg_3min_pts:.1f}")
    with col2:
        avg_5min_pts = filtered_df['first_5_min_points'].mean()
        st.metric("Avg First 5 Min Points", f"{avg_5min_pts:.1f}")
    with col3:
        max_microwave = filtered_df['microwave_score'].max()
        st.metric("Max Microwave Score", f"{max_microwave:.1f}")
    with col4:
        hot_starters = len(filtered_df[filtered_df['microwave_score'] > 5.0])
        st.metric("Hot Starters (>5.0)", f"{hot_starters}")
    
    # Display table
    st.markdown("#### Top Microwave Players")
    
    display_cols = [
        'player_name', 'team', 'opponent', 'microwave_score',
        'first_3_min_points', 'first_3_min_rebounds', 'first_3_min_assists', 'first_3_min_threes',
        'first_5_min_points', 'first_5_min_rebounds', 'first_5_min_assists', 'first_5_min_threes',
        'season_ppg', 'expected_minutes'
    ]
    
    available_cols = [c for c in display_cols if c in filtered_df.columns]
    display_df = filtered_df[available_cols].copy()
    
    # Rename for display
    rename_map = {
        'player_name': 'Player',
        'team': 'Team',
        'opponent': 'Opponent',
        'microwave_score': 'Microwave Score',
        'shot_matchup_multiplier': 'Shot Matchup',
        'combined_multiplier': 'Combined Mult',
        'first_3_min_points': '3Min PTS',
        'first_3_min_rebounds': '3Min REB',
        'first_3_min_assists': '3Min AST',
        'first_3_min_threes': '3Min 3PM',
        'first_5_min_points': '5Min PTS',
        'first_5_min_rebounds': '5Min REB',
        'first_5_min_assists': '5Min AST',
        'first_5_min_threes': '5Min 3PM',
        'player_3pt_pct': 'Player 3PT%',
        'opp_3pt_pct_allowed': 'Opp 3PT% Allowed',
        'season_ppg': 'Season PPG',
        'expected_minutes': 'Min'
    }
    
    display_df = display_df.rename(columns=rename_map)
    
    # Round numeric columns
    numeric_cols = [c for c in display_df.columns if c not in ['Player', 'Team', 'Opponent']]
    for col in numeric_cols:
        if col in display_df.columns:
            display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(1)
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Detailed view
    st.markdown("---")
    st.subheader("🔬 Player Detail")
    
    player_list = sorted(filtered_df['player_name'].unique().tolist())
    selected_player = st.selectbox("Select Player", options=player_list, key="microwave_player_select")
    
    if selected_player:
        player_data = filtered_df[filtered_df['player_name'] == selected_player].iloc[0]
        
        st.markdown(f"#### 📋 {selected_player} - Microwave Breakdown")
        
        # First 3 minutes
        st.markdown("##### ⚡ First 3 Minutes")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Points", f"{player_data['first_3_min_points']:.1f}")
        with col2:
            st.metric("Rebounds", f"{player_data['first_3_min_rebounds']:.1f}")
        with col3:
            st.metric("Assists", f"{player_data['first_3_min_assists']:.1f}")
        with col4:
            st.metric("3PM", f"{player_data['first_3_min_threes']:.1f}")
        
        # First 5 minutes
        st.markdown("##### ⚡ First 5 Minutes")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Points", f"{player_data['first_5_min_points']:.1f}")
        with col2:
            st.metric("Rebounds", f"{player_data['first_5_min_rebounds']:.1f}")
        with col3:
            st.metric("Assists", f"{player_data['first_5_min_assists']:.1f}")
        with col4:
            st.metric("3PM", f"{player_data['first_5_min_threes']:.1f}")
        
        # Context
        st.markdown("##### 📊 Context")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Microwave Score", f"{player_data['microwave_score']:.1f}")
            st.caption("Higher = starts hotter")
        with col2:
            st.metric("Season PPG", f"{player_data['season_ppg']:.1f}")
        with col3:
            st.metric("Early Multiplier", f"{player_data['early_multiplier']:.2f}x")
            st.caption("Early game vs average")
        with col4:
            shot_mult = player_data.get('shot_matchup_multiplier', 1.0)
            color = "🟢" if shot_mult > 1.05 else "🟡" if shot_mult > 0.95 else "🔴"
            st.metric("Shot Matchup", f"{shot_mult:.2f}x", delta=f"{color}")
            st.caption("Shot type alignment")
        
        # Shot Distribution Matchup
        st.markdown("##### 🎯 Shot Distribution Matchup")
        
        if 'player_3pt_pct' in player_data and 'opp_3pt_pct_allowed' in player_data:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**3-Point Shots**")
                player_3pt = player_data.get('player_3pt_pct', 0) * 100
                opp_3pt = player_data.get('opp_3pt_pct_allowed', 0) * 100
                st.metric("Player Shoots", f"{player_3pt:.1f}%")
                st.metric("Opp Allows", f"{opp_3pt:.1f}%")
                alignment_3pt = min(player_3pt, opp_3pt) / max(player_3pt, opp_3pt) if max(player_3pt, opp_3pt) > 0 else 0
                if alignment_3pt > 0.8:
                    st.success("✅ Great match")
                elif alignment_3pt > 0.6:
                    st.info("🟡 Good match")
                else:
                    st.warning("⚠️ Weak match")
            
            with col2:
                st.markdown("**Paint Shots**")
                player_paint = player_data.get('player_paint_pct', 0) * 100
                opp_paint = player_data.get('opp_paint_pct_allowed', 0) * 100
                st.metric("Player Shoots", f"{player_paint:.1f}%")
                st.metric("Opp Allows", f"{opp_paint:.1f}%")
                alignment_paint = min(player_paint, opp_paint) / max(player_paint, opp_paint) if max(player_paint, opp_paint) > 0 else 0
                if alignment_paint > 0.8:
                    st.success("✅ Great match")
                elif alignment_paint > 0.6:
                    st.info("🟡 Good match")
                else:
                    st.warning("⚠️ Weak match")
            
            with col3:
                st.markdown("**Midrange Shots**")
                player_mid = player_data.get('player_midrange_pct', 0) * 100
                opp_mid = player_data.get('opp_midrange_pct_allowed', 0) * 100
                st.metric("Player Shoots", f"{player_mid:.1f}%")
                st.metric("Opp Allows", f"{opp_mid:.1f}%")
                alignment_mid = min(player_mid, opp_mid) / max(player_mid, opp_mid) if max(player_mid, opp_mid) > 0 else 0
                if alignment_mid > 0.8:
                    st.success("✅ Great match")
                elif alignment_mid > 0.6:
                    st.info("🟡 Good match")
                else:
                    st.warning("⚠️ Weak match")
        else:
            st.info("Shot distribution data not available for this player")
        
        # Explanation
        st.markdown("---")
        st.info("""
        **How Microwave Stats Work:**
        
        - **First 3/5 Minutes**: Estimated stats based on per-minute rates × combined multiplier
        - **Early Multiplier**: Adjusts for players who typically start hot (superstars often 1.15x)
        - **Shot Matchup Multiplier**: Factors in how well player's shot profile matches opponent's allowed profile
          - If player shoots 45% 3s and opponent allows 50% 3s = favorable matchup
          - If player shoots 20% 3s and opponent allows 50% 3s = less relevant
        - **Combined Multiplier**: Early multiplier × Shot matchup multiplier
        - **Microwave Score**: Weighted combination of early stats (points 2x, 3s 1.5x) + shot matchup bonus
        
        **Shot Distribution:**
        - **3-Point %**: What % of player's shots are 3s vs what % opponent allows
        - **Paint %**: What % of player's shots are in paint vs what % opponent allows  
        - **Midrange %**: What % of player's shots are midrange vs what % opponent allows
        
        **Note**: These are estimates based on season averages and player archetypes. 
        Actual first 3/5 minute stats may vary based on game flow, matchups, and lineup decisions.
        """)

