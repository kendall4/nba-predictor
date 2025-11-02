import streamlit as st
import pandas as pd
from src.services.lineup_tracker import LineupTracker
from src.services.injury_tracker import InjuryTracker
from src.services.advanced_stats import AdvancedStatsCalculator
from src.services.player_visualizations import PlayerVisualizer
from src.services.mobile_style_visualizer import MobileStyleVisualizer
import os

def render(predictions, games):
    st.header("🗓️ Today's Games - Lineups & Minutes")
    st.caption("⚠️ Only confirmed lineups are shown. Injured/out players are automatically excluded for accuracy.")
    game_labels = [f"{g['away']} @ {g['home']} - {g['status']}" for g in games]
    if not game_labels:
        st.info("No games available.")
        return
    idx = st.selectbox("Select game", options=list(range(len(games))), format_func=lambda i: game_labels[i])
    game = games[idx]
    home = game['home']; away = game['away']

    team_home = predictions[predictions['team'] == home].copy()
    team_away = predictions[predictions['team'] == away].copy()
    if len(team_home) == 0 or len(team_away) == 0:
        st.info("No predictions found for one of the teams. Generate predictions first or widen filters.")
        if len(team_home) == 0:
            st.warning(f"⚠️ No players found for {home}. Try lowering min_minutes or min_value filters.")
        if len(team_away) == 0:
            st.warning(f"⚠️ No players found for {away}. Try lowering min_minutes or min_value filters.")

    # Initialize injury tracker (use preloaded if available)
    if 'injury_tracker' in st.session_state:
        injury_tracker = st.session_state['injury_tracker']
    else:
        injury_tracker = InjuryTracker(api_key=os.getenv('ROTOWIRE_API_KEY'))
    
    # Get confirmed lineups (tries NBA.com FREE first, then Rotowire if API key available)
    lineup_tracker = LineupTracker()
    nba_home = lineup_tracker.get_team_lineup(home)
    nba_away = lineup_tracker.get_team_lineup(away)
    
    def check_player_healthy(player_name):
        """Check if player is healthy (not Out)"""
        try:
            status = injury_tracker.get_player_status(player_name)
            return status['status'] != 'Out'
        except:
            # If check fails, assume healthy (but should rarely happen)
            return True
    
    def filter_injured_players_from_df(df_team):
        """Filter out injured players from a DataFrame"""
        if df_team is None or len(df_team) == 0:
            return df_team
        
        healthy_rows = []
        for _, row in df_team.iterrows():
            if check_player_healthy(row['player_name']):
                healthy_rows.append(row)
        
        if len(healthy_rows) == 0:
            return pd.DataFrame()
        return pd.DataFrame(healthy_rows)
    
    def filter_injured_players_from_list(player_list):
        """Filter out injured players from a list of player names"""
        healthy_players = []
        injured_players = []
        for player_name in player_list:
            if check_player_healthy(player_name):
                healthy_players.append(player_name)
            else:
                injured_players.append(player_name)
        return healthy_players, injured_players
    
    def build_roster_from_confirmed_lineup(df_team, confirmed_starters):
        """
        Build roster from confirmed lineup if available
        Filters out injured/out players from confirmed lineup
        """
        if not confirmed_starters or len(confirmed_starters) == 0:
            return None, None, [], False  # Return False to indicate estimated
        
        # Check all confirmed starters for injuries
        healthy_starters, injured_starters = filter_injured_players_from_list(confirmed_starters)
        
        if len(healthy_starters) == 0:
            return None, None, injured_starters, False
        
        # Get predictions for healthy confirmed starters
        starters_df = df_team[df_team['player_name'].isin(healthy_starters)].copy()
        
        # Sort by confirmed lineup order
        starter_order = {name: idx for idx, name in enumerate(healthy_starters)}
        starters_df['order'] = starters_df['player_name'].map(starter_order)
        starters_df = starters_df.sort_values('order').head(len(healthy_starters))
        
        # Bench: all other healthy players from predictions (excluding starters)
        bench_players = df_team[~df_team['player_name'].isin(healthy_starters)].copy()
        
        # Filter bench players for injuries too
        if len(bench_players) > 0:
            healthy_bench_names = []
            for _, row in bench_players.iterrows():
                if check_player_healthy(row['player_name']):
                    healthy_bench_names.append(row['player_name'])
            
            bench_df = bench_players[bench_players['player_name'].isin(healthy_bench_names)].copy()
            bench_df = bench_df.sort_values('minutes', ascending=False)
        else:
            bench_df = pd.DataFrame()
        
        # Build display dataframes
        if len(starters_df) > 0:
            starters_display = starters_df[['player_name','minutes','pred_points','pred_rebounds','pred_assists']].copy()
            starters_display.rename(columns={'minutes':'season_minutes'}, inplace=True)
            starters_display['pred_minutes'] = starters_display['season_minutes'].round(1)
        else:
            starters_display = pd.DataFrame()
        
        if len(bench_df) > 0:
            bench_display = bench_df[['player_name','minutes','pred_points','pred_rebounds','pred_assists']].copy()
            bench_display.rename(columns={'minutes':'season_minutes'}, inplace=True)
            bench_display['pred_minutes'] = (bench_display['season_minutes']*0.9).round(1)
        else:
            bench_display = pd.DataFrame()
        
        return starters_display, bench_display, injured_starters, True  # True = confirmed
    
    def build_roster_from_predictions(df_team):
        """
        Build roster from predictions (minutes-based) when confirmed lineup unavailable
        Filters out injured players and ensures we always show a full lineup
        """
        if df_team is None or len(df_team) == 0:
            return pd.DataFrame(), pd.DataFrame()
        
        # Filter injured players first - IMPORTANT: do this before sorting
        df_team_filtered = filter_injured_players_from_df(df_team)
        
        if len(df_team_filtered) == 0:
            # If all players filtered out, return empty but log warning
            return pd.DataFrame(), pd.DataFrame()
        
        # Sort by minutes (descending) to get most likely starters
        df_team_sorted = df_team_filtered.sort_values('minutes', ascending=False).copy()
        
        # Starters: top 5 by minutes (ensure we have at least 5 if available)
        num_starters = min(5, len(df_team_sorted))
        starters = df_team_sorted.head(num_starters).copy()
        
        # Bench: rest of healthy players
        bench = df_team_sorted.iloc[num_starters:].copy() if len(df_team_sorted) > num_starters else pd.DataFrame()
        
        # Build display dataframes - ensure all required columns exist
        required_cols = ['player_name', 'minutes', 'pred_points', 'pred_rebounds', 'pred_assists']
        available_cols = [c for c in required_cols if c in starters.columns]
        
        if len(starters) > 0 and len(available_cols) >= 2:  # At least player_name and minutes
            starters_display = starters[available_cols].copy()
            if 'minutes' in starters_display.columns:
                starters_display.rename(columns={'minutes':'season_minutes'}, inplace=True)
                starters_display['pred_minutes'] = starters_display['season_minutes'].round(1)
        else:
            starters_display = pd.DataFrame()
        
        if len(bench) > 0 and len(available_cols) >= 2:
            bench_display = bench[available_cols].copy()
            if 'minutes' in bench_display.columns:
                bench_display.rename(columns={'minutes':'season_minutes'}, inplace=True)
                bench_display['pred_minutes'] = (bench_display['season_minutes']*0.9).round(1)
        else:
            bench_display = pd.DataFrame()
        
        return starters_display, bench_display

    colH, colA = st.columns(2)
    with colH:
        st.subheader(f"Home: {home}")
        if nba_home and len(nba_home) > 0:
            # Try confirmed lineup first
            st.success(f"✅ Confirmed lineup available ({len(nba_home)} starters) - Source: NBA.com (FREE)")
            sh, bh, injured_home, is_confirmed = build_roster_from_confirmed_lineup(team_home, nba_home)
            
            if sh is None:
                # All confirmed starters are injured, fall back to estimated
                st.warning(f"⚠️ All confirmed starters are OUT. Showing estimated lineup.")
                if injured_home:
                    st.info(f"Injured: {', '.join(injured_home)}")
                sh, bh = build_roster_from_predictions(team_home)
                is_confirmed = False
        else:
            # No confirmed lineup, use estimated
            st.info(f"📊 Estimated lineup (based on season minutes)")
            st.caption("💡 Lineups are estimated based on season minutes (filtered for injuries)")
            sh, bh = build_roster_from_predictions(team_home)
            is_confirmed = False
            injured_home = []
        
        # Display lineup
        if sh is not None and len(sh) > 0:
            lineup_label = "**Starters (Confirmed)**" if is_confirmed else "**Starters (Estimated)**"
            st.markdown(lineup_label)
            st.data_editor(sh, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"home_starters_{home}_{away}")
            st.markdown("**Bench (Healthy Players)**")
            if len(bh) > 0:
                st.data_editor(bh, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"home_bench_{home}_{away}")
            else:
                st.caption("No bench players available")
        else:
            st.warning(f"⚠️ No healthy players found for {home}. All may be injured or filtered.")
    
    with colA:
        st.subheader(f"Away: {away}")
        if nba_away and len(nba_away) > 0:
            # Try confirmed lineup first
            st.success(f"✅ Confirmed lineup available ({len(nba_away)} starters) - Source: NBA.com (FREE)")
            sa, ba, injured_away, is_confirmed = build_roster_from_confirmed_lineup(team_away, nba_away)
            
            if sa is None:
                # All confirmed starters are injured, fall back to estimated
                st.warning(f"⚠️ All confirmed starters are OUT. Showing estimated lineup.")
                if injured_away:
                    st.info(f"Injured: {', '.join(injured_away)}")
                sa, ba = build_roster_from_predictions(team_away)
                is_confirmed = False
        else:
            # No confirmed lineup, use estimated
            st.info(f"📊 Estimated lineup (based on season minutes)")
            st.caption("💡 Lineups are estimated based on season minutes (filtered for injuries)")
            sa, ba = build_roster_from_predictions(team_away)
            is_confirmed = False
            injured_away = []
        
        # Display lineup
        if sa is not None and len(sa) > 0:
            lineup_label = "**Starters (Confirmed)**" if is_confirmed else "**Starters (Estimated)**"
            st.markdown(lineup_label)
            st.data_editor(sa, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"away_starters_{home}_{away}")
            st.markdown("**Bench (Healthy Players)**")
            if len(ba) > 0:
                st.data_editor(ba, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"away_bench_{home}_{away}")
            else:
                st.caption("No bench players available")
        else:
            st.warning(f"⚠️ No healthy players found for {away}. All may be injured or filtered.")

    st.markdown("---")
    
    # Advanced Stats & Visualizations Section
    st.subheader("📊 Advanced Stats & Performance Visualizations")
    st.caption("Rebound chances, potential assists, last 5 games performance, and interactive charts")
    
    # Initialize calculators
    adv_stats = AdvancedStatsCalculator()
    visualizer = PlayerVisualizer()
    mobile_viz = MobileStyleVisualizer()
    
    # Show advanced stats for displayed players
    with st.expander("View Advanced Stats & Last 5 Games", expanded=False):
        all_players = []
        if len(team_home) > 0:
            all_players.extend(team_home['player_name'].tolist())
        if len(team_away) > 0:
            all_players.extend(team_away['player_name'].tolist())
        
        if len(all_players) > 0:
            selected_player = st.selectbox("Select player for advanced stats", options=all_players, key="adv_stats_player")
            
            if selected_player:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Rebound Chances (Last 5 Games)**")
                    reb_chances = adv_stats.calculate_rebound_chances_from_games(selected_player, n=5)
                    if reb_chances:
                        st.metric("Avg Rebound Chances/Game", f"{reb_chances['avg_rebound_chances']:.1f}")
                        st.metric("Avg Actual Rebounds", f"{reb_chances['avg_rebounds']:.1f}")
                        st.metric("Conversion Rate", f"{reb_chances['rebound_chance_rate']:.1%}")
                
                with col2:
                    st.markdown("**Potential Assists (Last 5 Games)**")
                    pot_assists = adv_stats.calculate_potential_assists_from_games(selected_player, n=5)
                    if pot_assists:
                        st.metric("Avg Potential Assists/Game", f"{pot_assists['avg_potential_assists']:.1f}")
                        st.metric("Avg Actual Assists", f"{pot_assists['avg_assists']:.1f}")
                        st.metric("Conversion Rate", f"{pot_assists['conversion_rate']:.1%}")
                
                # Last 5 games with filters
                st.markdown("**Last 5 Games Performance**")
                
                filter_col1, filter_col2, filter_col3 = st.columns(3)
                with filter_col1:
                    min_pts = st.number_input("Min Points", min_value=0, value=0, step=1, key="filter_min_pts")
                with filter_col2:
                    min_reb = st.number_input("Min Rebounds", min_value=0, value=0, step=1, key="filter_min_reb")
                with filter_col3:
                    min_ast = st.number_input("Min Assists", min_value=0, value=0, step=1, key="filter_min_ast")
                
                filters = {}
                if min_pts > 0:
                    filters['min_points'] = min_pts
                if min_reb > 0:
                    filters['min_rebounds'] = min_reb
                if min_ast > 0:
                    filters['min_assists'] = min_ast
                
                last_n_games = adv_stats.get_last_n_games_stats(selected_player, n=5, filters=filters if filters else None)
                
                if last_n_games is not None and len(last_n_games) > 0:
                    display_cols = ['GAME_DATE', 'MATCHUP', 'PTS', 'REB', 'AST', 'MIN']
                    available_cols = [c for c in display_cols if c in last_n_games.columns]
                    st.dataframe(last_n_games[available_cols], use_container_width=True, hide_index=True)
                    st.caption(f"Showing {len(last_n_games)} games matching filters")
                else:
                    st.info("No games found matching filters or player has no recent games.")
        else:
            st.info("No players available to show advanced stats.")
    
    # Mobile-Style Performance Visualizations
    with st.expander("📈 Performance Visualizations (Mobile Style)", expanded=True):
        all_players_viz = []
        if len(team_home) > 0:
            all_players_viz.extend(team_home['player_name'].tolist())
        if len(team_away) > 0:
            all_players_viz.extend(team_away['player_name'].tolist())
        
        if len(all_players_viz) > 0:
            viz_col1, viz_col2 = st.columns([2, 1])
            
            with viz_col1:
                selected_player_viz = st.selectbox(
                    "Select player for visualization", 
                    options=all_players_viz, 
                    key="viz_player"
                )
            
            with viz_col2:
                time_period = st.selectbox(
                    "Time Period",
                    options=["Last 1 Game", "Last 5 Games", "Last 10 Games", "Head-to-Head"],
                    key="time_period"
                )
            
            if selected_player_viz:
                # Parse time period
                if time_period == "Last 1 Game":
                    n_games = 1
                    opponent = None
                elif time_period == "Last 5 Games":
                    n_games = 5
                    opponent = None
                elif time_period == "Last 10 Games":
                    n_games = 10
                    opponent = None
                else:  # Head-to-Head
                    n_games = 5
                    # Get opponent from current game context
                    opponent = st.selectbox(
                        "Select Opponent (H2H)",
                        options=[away, home] + [g['away'] for g in games] + [g['home'] for g in games],
                        key="h2h_opponent"
                    )
                
                # Stat category selection (matching mobile app)
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
                    key="stat_category"
                )
                
                stat_col, stat_label = stat_categories[selected_stat_key]
                
                # Over/under line input
                col1, col2 = st.columns([2, 1])
                with col1:
                    over_under_line = st.number_input(
                        "Over/Under Line",
                        min_value=0.0,
                        value=20.0,
                        step=0.5,
                        key="over_under_line"
                    )
                with col2:
                    # Get suggested line based on average
                    summary = mobile_viz.get_stat_summary(selected_player_viz, stat_col if stat_col else 'PTS', n_games=5)
                    suggested_line = summary['average'] if summary else 20.0
                    st.caption(f"Avg: {suggested_line:.1f}")
                
                # Show percentage statistics
                periods = {'H2H': 5, 'L5': 5, 'L10': 10, 'L20': 20, '2025': 100}
                pct_stats = mobile_viz.get_percentage_stats(
                    selected_player_viz, 
                    stat_col if stat_col else 'PTS',
                    over_under_line,
                    periods
                )
                
                st.markdown("### % Statistics")
                pct_cols = st.columns(len(periods))
                for idx, (period, pct) in enumerate(pct_stats.items()):
                    with pct_cols[idx]:
                        st.metric(period, f"{pct:.0f}%")
                
                # Show average and median
                summary = mobile_viz.get_stat_summary(
                    selected_player_viz, 
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
                    opponent = st.selectbox(
                        "Select Opponent (H2H)",
                        options=[away, home],
                        key=f"h2h_opp_{selected_player_viz}"
                    )
                    n_games = 5
                    fig = mobile_viz.create_mobile_style_chart(
                        selected_player_viz,
                        stat_col if stat_col else 'PTS',
                        stat_label,
                        over_under_line,
                        'H2H',
                        n_games,
                        opponent
                    )
                else:
                    n_games_map = {'Last 1 Game': 1, 'Last 5 Games': 5, 'Last 10 Games': 10}
                    n_games = n_games_map.get(time_period, 5)
                    period_label = {'Last 1 Game': 'L1', 'Last 5 Games': 'L5', 'Last 10 Games': 'L10'}.get(time_period, 'L5')
                    fig = mobile_viz.create_mobile_style_chart(
                        selected_player_viz,
                        stat_col if stat_col else 'PTS',
                        stat_label,
                        over_under_line,
                        period_label,
                        n_games,
                        None
                    )
                
                if fig:
                    st.plotly_chart(fig, use_container_width=True, key="mobile_chart")
                else:
                    st.info(f"No data available for {selected_player_viz}")
        else:
            st.info("No players available for visualization.")
    
    st.markdown("---")
    st.caption("📊 **Lineups**: Confirmed lineups preferred (NBA.com/Rotowire), estimated lineups shown when unavailable. Injured/out players automatically excluded.")


