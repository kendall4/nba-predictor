import streamlit as st
import pandas as pd

def render(predictions):
    st.header("📊 Lines Explorer")
    st.caption("Browse by stat across all players; filter and sort by value")
    rows = []
    for _, r in predictions.iterrows():
        rows.append({"Player": r['player_name'], "Team": r['team'], "Opponent": r['opponent'], "Stat": "points", "Line": r['line_points'], "Pred": r['pred_points'], "Value": r['point_value']})
        rows.append({"Player": r['player_name'], "Team": r['team'], "Opponent": r['opponent'], "Stat": "rebounds", "Line": r['line_rebounds'], "Pred": r['pred_rebounds'], "Value": r['rebound_value']})
        rows.append({"Player": r['player_name'], "Team": r['team'], "Opponent": r['opponent'], "Stat": "assists", "Line": r['line_assists'], "Pred": r['pred_assists'], "Value": r['assist_value']})
    lines_df = pd.DataFrame(rows)
    stat_filter = st.multiselect("Filter stats", options=["points","rebounds","assists"], default=["points","rebounds","assists"])
    team_filter = st.multiselect("Filter teams", options=sorted(predictions['team'].unique().tolist()))
    opp_filter = st.multiselect("Filter opponents", options=sorted(predictions['opponent'].unique().tolist()))
    min_value_filter = st.slider("Minimum value", -10.0, 10.0, 0.0, 0.5)
    df = lines_df[lines_df['Stat'].isin(stat_filter)].copy()
    if team_filter:
        df = df[df['Team'].isin(team_filter)]
    if opp_filter:
        df = df[df['Opponent'].isin(opp_filter)]
    df = df[df['Value'] >= min_value_filter]
    df = df.sort_values('Value', ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)


