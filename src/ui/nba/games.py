import streamlit as st
import pandas as pd
from src.services.lineup_tracker import LineupTracker

def render(predictions, games):
    st.header("🗓️ Today's Games - Lineups & Minutes")
    st.caption("Select a game to view Rotowire lineups (if available) or auto-estimated lineups")
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

    # Try Rotowire lineups first
    lineup_tracker = LineupTracker()
    rotowire_home = lineup_tracker.get_team_lineup(home)
    rotowire_away = lineup_tracker.get_team_lineup(away)
    
    def build_roster(df_team, rotowire_starters=None):
        """
        Build roster - prefer Rotowire starters if available, else use minutes-based
        """
        if rotowire_starters and len(rotowire_starters) > 0:
            # Use Rotowire starters
            starter_names = rotowire_starters[:5]
            starters = df_team[df_team['player_name'].isin(starter_names)]
            # Fill missing if not all 5 found
            if len(starters) < 5:
                remaining = df_team[~df_team['player_name'].isin(starter_names)].sort_values('minutes', ascending=False).head(5 - len(starters))
                starters = pd.concat([starters, remaining])
            bench = df_team[~df_team['player_name'].isin(starters['player_name'] if len(starters) > 0 else [])].sort_values('minutes', ascending=False)
        else:
            # Fallback: use minutes-based
            starters = df_team.sort_values('minutes', ascending=False).head(5)
            bench = df_team.sort_values('minutes', ascending=False).iloc[5:]
        
        starters_df = starters[['player_name','minutes','pred_points','pred_rebounds','pred_assists']].copy()
        starters_df.rename(columns={'minutes':'season_minutes'}, inplace=True)
        starters_df['pred_minutes'] = starters_df['season_minutes'].round(1)
        bench_df = bench[['player_name','minutes','pred_points','pred_rebounds','pred_assists']].copy()
        bench_df.rename(columns={'minutes':'season_minutes'}, inplace=True)
        bench_df['pred_minutes'] = (bench_df['season_minutes']*0.9).round(1)
        return starters_df, bench_df

    colH, colA = st.columns(2)
    with colH:
        st.subheader(f"Home: {home}")
        if rotowire_home:
            st.success(f"✅ Rotowire lineup available ({len(rotowire_home)} confirmed starters)")
        else:
            st.info("📊 Using estimated lineup (minutes-based)")
        sh, bh = build_roster(team_home, rotowire_starters=rotowire_home)
        st.markdown("**Starters**")
        st.data_editor(sh, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"home_starters_{home}_{away}")
        st.markdown("**Bench**")
        st.data_editor(bh, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"home_bench_{home}_{away}")
    with colA:
        st.subheader(f"Away: {away}")
        if rotowire_away:
            st.success(f"✅ Rotowire lineup available ({len(rotowire_away)} confirmed starters)")
        else:
            st.info("📊 Using estimated lineup (minutes-based)")
        sa, ba = build_roster(team_away, rotowire_starters=rotowire_away)
        st.markdown("**Starters**")
        st.data_editor(sa, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"away_starters_{home}_{away}")
        st.markdown("**Bench**")
        st.data_editor(ba, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"away_bench_{home}_{away}")

    st.markdown("---")
    st.caption("Predicted minutes default to season minutes (bench scaled). Edit as needed; can feed into projections next.")


