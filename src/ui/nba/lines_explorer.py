import streamlit as st
import pandas as pd
import numpy as np
from src.utils.odds_utils import calculate_implied_prob_from_line
from src.analysis.alt_line_optimizer import AltLineOptimizer
from src.services.odds_aggregator import OddsAggregator

def round_to_sportsbook_line(line):
    """
    Round line to sportsbook format (whole or .5)
    """
    if pd.isna(line):
        return line
    rounded = round(line * 2) / 2  # Round to nearest 0.5
    return rounded

def find_matching_odds(player_name, stat, target_line, odds_df, allowed_books=None):
    """
    Find best matching odds for a player/stat/line combination
    Only returns lines that have BOTH over AND under odds available
    
    Args:
        player_name: Player name
        stat: Stat type (points, rebounds, assists)
        target_line: Target line value
        odds_df: DataFrame with odds data
        allowed_books: List of book names to filter by (None = all books)
    
    Returns: (over_odds, under_odds, best_book, sportsbook_line) or (None, None, None, None)
    """
    if odds_df is None or len(odds_df) == 0:
        return None, None, None, None
    
    # Check if required columns exist
    required_cols = ['player', 'stat', 'line', 'over_odds', 'under_odds', 'book']
    if not all(col in odds_df.columns for col in required_cols):
        return None, None, None, None
    
    # Filter by allowed books if specified
    working_df = odds_df.copy()
    if allowed_books is not None and len(allowed_books) > 0:
        working_df = working_df[working_df['book'].isin(allowed_books)]
        if len(working_df) == 0:
            return None, None, None, None
    
    # Normalize player name for matching
    def normalize_name(name):
        if pd.isna(name):
            return ""
        return str(name).lower().strip().replace('.', '').replace("'", '')
    
    target_name_norm = normalize_name(player_name)
    stat_lower = stat.lower()
    
    # Filter by stat (try various matches)
    stat_match = working_df[
        working_df['stat'].astype(str).str.contains(stat_lower, case=False, na=False)
    ].copy()
    
    if len(stat_match) == 0:
        return None, None, None, None
    
    # Normalize player names in odds_df for matching
    stat_match['player_norm'] = stat_match['player'].apply(normalize_name)
    
    # Try to find exact player name match, then fuzzy match
    player_match = stat_match[
        stat_match['player_norm'].str.contains(target_name_norm, case=False, na=False)
    ]
    
    if len(player_match) == 0:
        # Try last name match
        last_name = player_name.split()[-1] if len(player_name.split()) > 0 else player_name
        player_match = stat_match[
            stat_match['player'].astype(str).str.contains(last_name, case=False, na=False)
        ]
    
    if len(player_match) == 0:
        return None, None, None, None
    
    # CRITICAL: Only keep rows that have BOTH over AND under odds
    player_match = player_match[
        (player_match['over_odds'].notna()) & 
        (player_match['under_odds'].notna()) &
        (player_match['over_odds'] != None) &
        (player_match['under_odds'] != None)
    ]
    
    if len(player_match) == 0:
        return None, None, None, None
    
    # Find closest line match (use rounded target line)
    target_line_rounded = round_to_sportsbook_line(target_line)
    player_match = player_match.copy()
    player_match['line_diff'] = abs(player_match['line'] - target_line_rounded)
    closest = player_match.nsmallest(1, 'line_diff')
    
    if len(closest) == 0:
        return None, None, None, None
    
    best_match = closest.iloc[0]
    over_odds = int(best_match['over_odds']) if pd.notna(best_match.get('over_odds')) and best_match.get('over_odds') is not None else None
    under_odds = int(best_match['under_odds']) if pd.notna(best_match.get('under_odds')) and best_match.get('under_odds') is not None else None
    book = str(best_match.get('book', 'N/A'))
    sportsbook_line = float(best_match['line']) if pd.notna(best_match.get('line')) else None
    
    # Final check: must have both over and under
    if over_odds is None or under_odds is None:
        return None, None, None, None
    
    return over_odds, under_odds, book, sportsbook_line

@st.cache_data(ttl=300)  # Cache for 5 minutes
def _fetch_cached_odds_no_debug():
    """Cached function to fetch odds (without debug for caching)"""
    aggregator = OddsAggregator()
    if aggregator.api_key:
        return aggregator.get_player_props(debug=False)
    return None

def _fetch_cached_odds(debug=False):
    """Fetch odds with optional debug output to Streamlit"""
    if not debug:
        # Use cached version for non-debug mode
        return _fetch_cached_odds_no_debug()
    else:
        # Bypass cache for debug mode to see fresh API calls
        try:
            aggregator = OddsAggregator()
            if aggregator.api_key:
                props = aggregator.get_player_props(debug=debug)
                if debug and props is not None:
                    if len(props) == 0:
                        st.warning("⚠️ API returned empty DataFrame - no player props found")
                    else:
                        st.success(f"✅ API returned {len(props)} props")
                return props
            else:
                if debug:
                    st.warning("⚠️ ODDS_API_KEY not set")
        except Exception as e:
            if debug:
                st.error(f"❌ Error in _fetch_cached_odds: {e}")
                import traceback
                st.code(traceback.format_exc())
    return None

def render(predictions):
    st.header("📊 Lines Explorer")
    st.caption("Browse by stat across all players; filter and sort by value with Implied Probability")
    
    # Add option to show IP
    show_ip = st.checkbox("Show Implied Probability (Model IP)", value=True)
    
    # Option to fetch and show actual betting odds
    show_odds = st.checkbox("Show Live Betting Odds", value=True, help="Fetch real odds from sportsbooks (requires ODDS_API_KEY)")
    
    # Debug mode for odds API
    debug_odds = st.checkbox("🐛 Debug Odds API", value=False, help="Show detailed API response and error information")
    
    # Book filter - only show if odds are enabled
    allowed_books = None
    if show_odds:
        all_books = []
        try:
            aggregator = OddsAggregator()
            if aggregator.api_key:
                # Try to get a sample of odds to see available books
                sample_odds = _fetch_cached_odds_no_debug()
                if sample_odds is not None and len(sample_odds) > 0 and 'book' in sample_odds.columns:
                    all_books = sorted(sample_odds['book'].unique().tolist())
        except:
            pass
        
        if len(all_books) > 0:
            with st.expander("📚 Filter Sportsbooks", expanded=False):
                selected_books = st.multiselect(
                    "Select sportsbooks to show",
                    options=all_books,
                    default=all_books,  # Show all by default
                    help="Only lines from selected books will be displayed"
                )
                if len(selected_books) > 0:
                    allowed_books = selected_books
                else:
                    st.warning("⚠️ No books selected - no odds will be shown")
        else:
            # Default books if we can't detect them
            default_books = ['draftkings', 'fanduel', 'espnbet', 'betmgm', 'caesars']
            with st.expander("📚 Filter Sportsbooks", expanded=False):
                selected_books = st.multiselect(
                    "Select sportsbooks to show",
                    options=default_books,
                    default=default_books,
                    help="Only lines from selected books will be displayed"
                )
                if len(selected_books) > 0:
                    allowed_books = selected_books
    
    optimizer = AltLineOptimizer()
    
    # Fetch odds if requested (with caching)
    odds_data = None
    if show_odds:
        try:
            aggregator = OddsAggregator()
            if aggregator.api_key:
                # Fetch odds with optional debug
                with st.spinner("Fetching odds from sportsbooks..."):
                    odds_data = _fetch_cached_odds(debug=debug_odds)
                    
                    if debug_odds:
                        st.info("🔍 Debug Mode: Checking API response...")
                    
                    if odds_data is not None and len(odds_data) > 0:
                        st.success(f"✅ Found odds for {odds_data['player'].nunique()} players ({len(odds_data)} total props)")
                        # Debug: show sample of stats found
                        if 'stat' in odds_data.columns:
                            stats_found = odds_data['stat'].unique().tolist()
                            st.caption(f"Stats available: {', '.join(stats_found[:10])}")
                    elif odds_data is not None and len(odds_data) == 0:
                        st.warning("⚠️ No odds found. API returned empty response.")
                        if debug_odds:
                            st.info("💡 This could mean:\n"
                                  "- No NBA games today\n"
                                  "- Player props not available yet\n"
                                  "- Market 'player_props' not supported by selected books\n"
                                  "- Check console/terminal for detailed API logs")
                    else:
                        # odds_data is None - API error
                        st.warning("⚠️ No odds found. API returned error or no response.")
                        if debug_odds:
                            st.info("💡 Possible issues:\n"
                                  "- Invalid API key\n"
                                  "- Rate limit exceeded\n"
                                  "- Network error\n"
                                  "- Check console/terminal for detailed error logs")
            else:
                st.info("💡 Set ODDS_API_KEY in secrets (.env file or Streamlit secrets) to view live odds")
                if debug_odds:
                    st.code("# In .env file:\nODDS_API_KEY=your_key_here\n\n# Or in Streamlit secrets:\n# ODDS_API_KEY: your_key_here")
        except Exception as e:
            st.error(f"❌ Error fetching odds: {str(e)}")
            if debug_odds:
                import traceback
                st.code(traceback.format_exc())
            odds_data = None
    
    rows = []
    for _, r in predictions.iterrows():
        player_name = r['player_name']
        
        # Points
        pred_points = r['pred_points']
        line_points = r['line_points']
        # Round line to sportsbook format
        line_points_rounded = round_to_sportsbook_line(line_points)
        
        # Get odds if available (returns sportsbook_line too)
        # Only show lines that have BOTH over AND under odds
        over_odds, under_odds, book, sportsbook_line = find_matching_odds(player_name, 'points', line_points, odds_data, allowed_books) if show_odds and odds_data is not None else (None, None, None, None)
        
        # Only add to rows if we have BOTH over and under odds
        if over_odds is not None and under_odds is not None:
            # Use sportsbook line for IP calculation if available, otherwise use rounded model line
            line_for_ip = sportsbook_line if sportsbook_line is not None else line_points_rounded
            ip_points = calculate_implied_prob_from_line(line_for_ip, pred_points) if show_ip else None
            
            over_str = f"{over_odds:+d}"
            under_str = f"{under_odds:+d}"
            
            rows.append({
                "Player": player_name, 
                "Team": r['team'], 
                "Opponent": r['opponent'], 
                "Stat": "points", 
                "Line": line_points_rounded,  # Show rounded line
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
        line_rebounds_rounded = round_to_sportsbook_line(line_rebounds)
        
        over_odds, under_odds, book, sportsbook_line = find_matching_odds(player_name, 'rebounds', line_rebounds, odds_data, allowed_books) if show_odds and odds_data is not None else (None, None, None, None)
        
        # Only add to rows if we have BOTH over and under odds
        if over_odds is not None and under_odds is not None:
            line_for_ip = sportsbook_line if sportsbook_line is not None else line_rebounds_rounded
            ip_rebounds = calculate_implied_prob_from_line(line_for_ip, pred_rebounds, std_dev=pred_rebounds*0.25) if show_ip else None
            
            over_str = f"{over_odds:+d}"
            under_str = f"{under_odds:+d}"
            
            rows.append({
                "Player": player_name, 
                "Team": r['team'], 
                "Opponent": r['opponent'], 
                "Stat": "rebounds", 
                "Line": line_rebounds_rounded,  # Show rounded line
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
        line_assists_rounded = round_to_sportsbook_line(line_assists)
        
        over_odds, under_odds, book, sportsbook_line = find_matching_odds(player_name, 'assists', line_assists, odds_data, allowed_books) if show_odds and odds_data is not None else (None, None, None, None)
        
        # Only add to rows if we have BOTH over and under odds
        if over_odds is not None and under_odds is not None:
            line_for_ip = sportsbook_line if sportsbook_line is not None else line_assists_rounded
            ip_assists = calculate_implied_prob_from_line(line_for_ip, pred_assists, std_dev=pred_assists*0.30) if show_ip else None
            
            over_str = f"{over_odds:+d}"
            under_str = f"{under_odds:+d}"
            
            rows.append({
                "Player": player_name, 
                "Team": r['team'], 
                "Opponent": r['opponent'], 
                "Stat": "assists", 
                "Line": line_assists_rounded,  # Show rounded line
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
        captions.append("💡 IP (Model) = Your model's implied probability that player exceeds the sportsbook line")
    if show_odds:
        captions.append("💰 Odds shown are from live sportsbooks (closest line match)")
    captions.append("📊 Lines rounded to sportsbook format (whole or .5)")
    
    if captions:
        st.caption(" | ".join(captions))


