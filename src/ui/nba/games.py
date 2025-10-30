import streamlit as st

def render(predictions, games):
    st.header("🗓️ Today's Games - Lineups & Minutes")
    st.caption("Select a game to view auto-estimated lineups and edit predicted minutes.")
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

    def build_roster(df_team):
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
        sh, bh = build_roster(team_home)
        st.markdown("**Starters**")
        st.data_editor(sh, use_container_width=True, hide_index=True, num_rows="dynamic")
        st.markdown("**Bench**")
        st.data_editor(bh, use_container_width=True, hide_index=True, num_rows="dynamic")
    with colA:
        st.subheader(f"Away: {away}")
        sa, ba = build_roster(team_away)
        st.markdown("**Starters**")
        st.data_editor(sa, use_container_width=True, hide_index=True, num_rows="dynamic")
        st.markdown("**Bench**")
        st.data_editor(ba, use_container_width=True, hide_index=True, num_rows="dynamic")

    st.markdown("---")
    st.caption("Predicted minutes default to season minutes (bench scaled). Edit as needed; can feed into projections next.")


