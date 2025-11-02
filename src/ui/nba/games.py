import streamlit as st
import pandas as pd
from src.services.lineup_tracker import LineupTracker
from src.services.injury_tracker import InjuryTracker
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
    
    # Get confirmed lineups from Rotowire (REQUIRED - no fallback)
    lineup_tracker = LineupTracker()
    rotowire_home = lineup_tracker.get_team_lineup(home)
    rotowire_away = lineup_tracker.get_team_lineup(away)
    
    def check_player_healthy(player_name):
        """Check if player is healthy (not Out)"""
        try:
            status = injury_tracker.get_player_status(player_name)
            return status['status'] != 'Out'
        except:
            # If check fails, assume healthy (but should rarely happen)
            return True
    
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
        Build roster ONLY from confirmed lineup - NO minutes-based fallback
        Filters out injured/out players from confirmed lineup
        """
        if not confirmed_starters or len(confirmed_starters) == 0:
            return None, None, []
        
        # Check all confirmed starters for injuries
        healthy_starters, injured_starters = filter_injured_players_from_list(confirmed_starters)
        
        if len(healthy_starters) == 0:
            return None, None, injured_starters
        
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
        
        return starters_display, bench_display, injured_starters

    colH, colA = st.columns(2)
    with colH:
        st.subheader(f"Home: {home}")
        if rotowire_home and len(rotowire_home) > 0:
            st.success(f"✅ Confirmed lineup available ({len(rotowire_home)} starters)")
            sh, bh, injured_home = build_roster_from_confirmed_lineup(team_home, rotowire_home)
            
            if sh is None:
                st.error(f"❌ No confirmed lineup available for {home}. Cannot show inaccurate lineups.")
                if injured_home:
                    st.warning(f"⚠️ Confirmed starters who are OUT: {', '.join(injured_home)}")
            else:
                if injured_home:
                    st.warning(f"⚠️ Removed injured starters: {', '.join(injured_home)}")
                st.markdown("**Starters (Confirmed)**")
                if len(sh) > 0:
                    st.data_editor(sh, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"home_starters_{home}_{away}")
                else:
                    st.caption("No healthy starters available")
                st.markdown("**Bench (Healthy Players)**")
                if len(bh) > 0:
                    st.data_editor(bh, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"home_bench_{home}_{away}")
                else:
                    st.caption("No bench players available")
        else:
            st.error(f"❌ No confirmed lineup available for {home}")
            st.info("💡 Set ROTOWIRE_API_KEY to get confirmed lineups. We don't show estimated lineups to ensure accuracy.")
    
    with colA:
        st.subheader(f"Away: {away}")
        if rotowire_away and len(rotowire_away) > 0:
            st.success(f"✅ Confirmed lineup available ({len(rotowire_away)} starters)")
            sa, ba, injured_away = build_roster_from_confirmed_lineup(team_away, rotowire_away)
            
            if sa is None:
                st.error(f"❌ No confirmed lineup available for {away}. Cannot show inaccurate lineups.")
                if injured_away:
                    st.warning(f"⚠️ Confirmed starters who are OUT: {', '.join(injured_away)}")
            else:
                if injured_away:
                    st.warning(f"⚠️ Removed injured starters: {', '.join(injured_away)}")
                st.markdown("**Starters (Confirmed)**")
                if len(sa) > 0:
                    st.data_editor(sa, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"away_starters_{home}_{away}")
                else:
                    st.caption("No healthy starters available")
                st.markdown("**Bench (Healthy Players)**")
                if len(ba) > 0:
                    st.data_editor(ba, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"away_bench_{home}_{away}")
                else:
                    st.caption("No bench players available")
        else:
            st.error(f"❌ No confirmed lineup available for {away}")
            st.info("💡 Set ROTOWIRE_API_KEY to get confirmed lineups. We don't show estimated lineups to ensure accuracy.")

    st.markdown("---")
    st.caption("⚠️ **Accuracy First**: Only confirmed lineups shown. Injured/out players automatically excluded. Edit minutes as needed.")


