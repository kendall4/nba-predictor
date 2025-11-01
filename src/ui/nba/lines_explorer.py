import streamlit as st
import pandas as pd
from src.utils.odds_utils import calculate_implied_prob_from_line
from src.analysis.alt_line_optimizer import AltLineOptimizer

def render(predictions):
    st.header("📊 Lines Explorer")
    st.caption("Browse by stat across all players; filter and sort by value with Implied Probability")
    
    # Add option to show IP
    show_ip = st.checkbox("Show Implied Probability (Model IP)", value=True)
    
    optimizer = AltLineOptimizer()
    
    rows = []
    for _, r in predictions.iterrows():
        # Points
        pred_points = r['pred_points']
        line_points = r['line_points']
        ip_points = calculate_implied_prob_from_line(line_points, pred_points) if show_ip else None
        
        rows.append({
            "Player": r['player_name'], 
            "Team": r['team'], 
            "Opponent": r['opponent'], 
            "Stat": "points", 
            "Line": line_points, 
            "Pred": pred_points, 
            "Value": r['point_value'],
            "IP": f"{ip_points:.1%}" if ip_points is not None else None
        })
        
        # Rebounds
        pred_rebounds = r['pred_rebounds']
        line_rebounds = r['line_rebounds']
        ip_rebounds = calculate_implied_prob_from_line(line_rebounds, pred_rebounds, std_dev=pred_rebounds*0.25) if show_ip else None
        
        rows.append({
            "Player": r['player_name'], 
            "Team": r['team'], 
            "Opponent": r['opponent'], 
            "Stat": "rebounds", 
            "Line": line_rebounds, 
            "Pred": pred_rebounds, 
            "Value": r['rebound_value'],
            "IP": f"{ip_rebounds:.1%}" if ip_rebounds is not None else None
        })
        
        # Assists
        pred_assists = r['pred_assists']
        line_assists = r['line_assists']
        ip_assists = calculate_implied_prob_from_line(line_assists, pred_assists, std_dev=pred_assists*0.30) if show_ip else None
        
        rows.append({
            "Player": r['player_name'], 
            "Team": r['team'], 
            "Opponent": r['opponent'], 
            "Stat": "assists", 
            "Line": line_assists, 
            "Pred": pred_assists, 
            "Value": r['assist_value'],
            "IP": f"{ip_assists:.1%}" if ip_assists is not None else None
        })
    
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
    
    # Reorder columns to show IP prominently
    if show_ip and 'IP' in df.columns:
        cols = ['Player', 'Team', 'Opponent', 'Stat', 'Line', 'Pred', 'IP', 'Value']
        df = df[[c for c in cols if c in df.columns]]
        df.columns = ['Player', 'Team', 'Opponent', 'Stat', 'Line', 'Pred', 'IP (Model)', 'Value']
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    if show_ip:
        st.caption("💡 IP (Model) = Your model's implied probability that player exceeds the line")


