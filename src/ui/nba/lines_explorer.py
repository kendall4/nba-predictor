import streamlit as st
import pandas as pd
import numpy as np
from src.utils.odds_utils import calculate_implied_prob_from_line
from src.analysis.alt_line_optimizer import AltLineOptimizer
from src.services.odds_aggregator import OddsAggregator

def find_matching_odds(player_name, stat, target_line, odds_df):
    """
    Find best matching odds for a player/stat/line combination
    Returns: (over_odds, under_odds, best_book) or (None, None, None)
    """
    if odds_df is None or len(odds_df) == 0:
        return None, None, None
    
    # Normalize player name for matching
    def normalize_name(name):
        return name.lower().strip().replace('.', '').replace("'", '')
    
    target_name_norm = normalize_name(player_name)
    stat_lower = stat.lower()
    
    # Filter by stat (try various matches)
    stat_match = odds_df[
        odds_df['stat'].str.contains(stat_lower, case=False, na=False)
    ]
    
    if len(stat_match) == 0:
        return None, None, None
    
    # Try to find exact player name match, then fuzzy match
    player_match = stat_match[
        stat_match['player'].apply(lambda x: normalize_name(str(x))).str.contains(target_name_norm, case=False, na=False)
    ]
    
    if len(player_match) == 0:
        # Try last name match
        last_name = player_name.split()[-1] if len(player_name.split()) > 0 else player_name
        player_match = stat_match[
            stat_match['player'].str.contains(last_name, case=False, na=False)
        ]
    
    if len(player_match) == 0:
        return None, None, None
    
    # Find closest line match
    player_match = player_match.copy()
    player_match['line_diff'] = abs(player_match['line'] - target_line)
    closest = player_match.nsmallest(1, 'line_diff')
    
    if len(closest) == 0:
        return None, None, None
    
    best_match = closest.iloc[0]
    return (
        int(best_match['over_odds']) if pd.notna(best_match.get('over_odds')) else None,
        int(best_match['under_odds']) if pd.notna(best_match.get('under_odds')) else None,
        best_match.get('book', 'N/A')
    )

@st.cache_data(ttl=300)  # Cache for 5 minutes
def _fetch_cached_odds():
    """Cached function to fetch odds"""
    aggregator = OddsAggregator()
    if aggregator.api_key:
        return aggregator.get_player_props(debug=False)
    return None

def render(predictions):
    st.header("📊 Lines Explorer")
    st.caption("Browse by stat across all players; filter and sort by value with Implied Probability")
    
    # Add option to show IP
    show_ip = st.checkbox("Show Implied Probability (Model IP)", value=True)
    
    # Option to fetch and show actual betting odds
    show_odds = st.checkbox("Show Live Betting Odds", value=True, help="Fetch real odds from sportsbooks (requires ODDS_API_KEY)")
    
    optimizer = AltLineOptimizer()
    
    # Fetch odds if requested (with caching)
    odds_data = None
    if show_odds:
        try:
            aggregator = OddsAggregator()
            if aggregator.api_key:
                with st.spinner("📊 Fetching live odds from sportsbooks..."):
                    # Use cached data to avoid multiple API calls
                    odds_data = _fetch_cached_odds()
                    if odds_data is not None and len(odds_data) > 0:
                        st.success(f"✅ Found odds for {odds_data['player'].nunique()} players")
                    else:
                        st.warning("⚠️ No odds found. Odds may not be available yet.")
            else:
                st.info("💡 Set ODDS_API_KEY in secrets to view live odds")
        except Exception as e:
            st.error(f"❌ Error fetching odds: {e}")
            odds_data = None
    
    rows = []
    for _, r in predictions.iterrows():
        player_name = r['player_name']
        
        # Points
        pred_points = r['pred_points']
        line_points = r['line_points']
        ip_points = calculate_implied_prob_from_line(line_points, pred_points) if show_ip else None
        
        # Get odds if available
        over_odds, under_odds, book = find_matching_odds(player_name, 'points', line_points, odds_data) if show_odds and odds_data is not None else (None, None, None)
        over_str = f"{over_odds:+d}" if over_odds is not None else "N/A"
        under_str = f"{under_odds:+d}" if under_odds is not None else "N/A"
        odds_str = f"{over_str}/{under_str}" if over_odds is not None or under_odds is not None else None
        
        rows.append({
            "Player": player_name, 
            "Team": r['team'], 
            "Opponent": r['opponent'], 
            "Stat": "points", 
            "Line": line_points, 
            "Pred": pred_points, 
            "Value": r['point_value'],
            "IP": f"{ip_points:.1%}" if ip_points is not None else None,
            "Over Odds": over_str if show_odds else None,
            "Under Odds": under_str if show_odds else None,
            "Book": book if show_odds else None
        })
        
        # Rebounds
        pred_rebounds = r['pred_rebounds']
        line_rebounds = r['line_rebounds']
        ip_rebounds = calculate_implied_prob_from_line(line_rebounds, pred_rebounds, std_dev=pred_rebounds*0.25) if show_ip else None
        
        over_odds, under_odds, book = find_matching_odds(player_name, 'rebounds', line_rebounds, odds_data) if show_odds and odds_data is not None else (None, None, None)
        over_str = f"{over_odds:+d}" if over_odds is not None else "N/A"
        under_str = f"{under_odds:+d}" if under_odds is not None else "N/A"
        
        rows.append({
            "Player": player_name, 
            "Team": r['team'], 
            "Opponent": r['opponent'], 
            "Stat": "rebounds", 
            "Line": line_rebounds, 
            "Pred": pred_rebounds, 
            "Value": r['rebound_value'],
            "IP": f"{ip_rebounds:.1%}" if ip_rebounds is not None else None,
            "Over Odds": over_str if show_odds else None,
            "Under Odds": under_str if show_odds else None,
            "Book": book if show_odds else None
        })
        
        # Assists
        pred_assists = r['pred_assists']
        line_assists = r['line_assists']
        ip_assists = calculate_implied_prob_from_line(line_assists, pred_assists, std_dev=pred_assists*0.30) if show_ip else None
        
        over_odds, under_odds, book = find_matching_odds(player_name, 'assists', line_assists, odds_data) if show_odds and odds_data is not None else (None, None, None)
        over_str = f"{over_odds:+d}" if over_odds is not None else "N/A"
        under_str = f"{under_odds:+d}" if under_odds is not None else "N/A"
        
        rows.append({
            "Player": player_name, 
            "Team": r['team'], 
            "Opponent": r['opponent'], 
            "Stat": "assists", 
            "Line": line_assists, 
            "Pred": pred_assists, 
            "Value": r['assist_value'],
            "IP": f"{ip_assists:.1%}" if ip_assists is not None else None,
            "Over Odds": over_str if show_odds else None,
            "Under Odds": under_str if show_odds else None,
            "Book": book if show_odds else None
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
    
    # Reorder columns to show IP and odds prominently
    base_cols = ['Player', 'Team', 'Opponent', 'Stat', 'Line', 'Pred']
    if show_ip and 'IP' in df.columns:
        base_cols.append('IP')
    if show_odds and 'Over Odds' in df.columns:
        base_cols.extend(['Over Odds', 'Under Odds', 'Book'])
    base_cols.append('Value')
    
    # Only include columns that exist in dataframe
    display_cols = [c for c in base_cols if c in df.columns]
    df = df[display_cols].copy()
    
    # Rename columns for display
    if show_ip and 'IP' in df.columns:
        df = df.rename(columns={'IP': 'IP (Model)'})
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    captions = []
    if show_ip:
        captions.append("💡 IP (Model) = Your model's implied probability that player exceeds the line")
    if show_odds:
        captions.append("💰 Odds shown are from live sportsbooks (closest line match)")
    
    if captions:
        st.caption(" | ".join(captions))


