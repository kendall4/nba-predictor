import streamlit as st
import pandas as pd
import numpy as np
from src.utils.odds_utils import calculate_implied_prob_from_line, american_to_implied_prob
from src.analysis.alt_line_optimizer import AltLineOptimizer
from src.services.odds_aggregator import OddsAggregator

def round_to_sportsbook_line(line):
    """
    Round line to sportsbook format (whole number or .5)
    
    Rounds to nearest 0.5 increment using standard rounding:
    - 0.0-0.24 -> round down to .0
    - 0.25-0.74 -> round to .5
    - 0.75-0.99 -> round up to next whole number
    
    Examples:
        24.3 -> 24.5 (0.3 is in 0.25-0.74 range)
        24.7 -> 25.0 (0.7 is in 0.75-0.99 range)
        24.2 -> 24.0 (0.2 is in 0.0-0.24 range)
        24.5 -> 24.5 (already .5)
    """
    if pd.isna(line):
        return line
    
    # Get the integer and decimal parts
    integer_part = int(line)
    decimal_part = abs(line - integer_part)  # Handle negative numbers
    
    # Determine rounding based on decimal part
    # Prefer whole numbers when possible, use .5 as fallback
    # - 0.00-0.49 -> round to whole number (.0)
    # - 0.50-0.74 -> round to .5
    # - 0.75-0.99 -> round up to next whole number
    if decimal_part < 0.5:
        # Round down to whole number (prefer whole numbers)
        return float(integer_part) if line >= 0 else float(integer_part - 1)
    elif decimal_part < 0.75:
        # Round to .5 (only when clearly in middle range)
        return float(integer_part) + (0.5 if line >= 0 else -0.5)
    else:
        # Round up to next whole number
        return float(integer_part) + (1.0 if line >= 0 else -1.0)

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

@st.cache_data(ttl=43200)  # Cache for 12 hours (once per day - saves API quota)
def _fetch_cached_odds_no_debug():
    """Cached function to fetch odds (without debug for caching)"""
    aggregator = OddsAggregator()
    
    # First try disk cache
    cached_odds = aggregator.load_cached_odds()
    if cached_odds is not None and len(cached_odds) > 0:
        return cached_odds
    
    # No cache, try API
    if aggregator.api_key:
        props = aggregator.get_player_props(debug=False)
        # If quota exceeded, return cached data if available
        if props == "QUOTA_EXCEEDED":
            cached_odds = aggregator.load_cached_odds()
            if cached_odds is not None and len(cached_odds) > 0:
                return cached_odds
        return props
    return None

def _fetch_cached_odds(debug=False):
    """Fetch odds with optional debug output to Streamlit"""
    aggregator = OddsAggregator()
    
    # First, try to load from disk cache (even if quota exceeded)
    cached_odds = aggregator.load_cached_odds()
    if cached_odds is not None and len(cached_odds) > 0:
        if debug:
            st.info(f"💾 Using cached odds from disk ({len(cached_odds)} props)")
        # Return cached data, but don't use QUOTA_EXCEEDED marker
        return cached_odds
    
    # No cache available, try API
    if not debug:
        # Use cached version for non-debug mode
        return _fetch_cached_odds_no_debug()
    else:
        # Bypass cache for debug mode to see fresh API calls
        try:
            if aggregator.api_key:
                props = aggregator.get_player_props(debug=debug)
                if props == "QUOTA_EXCEEDED":
                    # If quota exceeded, try to use disk cache
                    cached_odds = aggregator.load_cached_odds()
                    if cached_odds is not None and len(cached_odds) > 0:
                        st.warning("⚠️ API quota exceeded, but found cached odds from earlier today")
                        return cached_odds
                    return props
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
    show_ip = st.checkbox("Show Implied Probability", value=True)
    if show_ip:
        ip_type = st.radio(
            "IP Calculation Method",
            options=["Model IP (prediction vs line)", "Book IP (from odds)", "Both"],
            index=2,  # Default to "Both"
            horizontal=True,
            help="Model IP: Our model's probability player exceeds line | Book IP: Sportsbook's implied probability from odds"
        )
    else:
        ip_type = None
    
    # Option to fetch and show actual betting odds
    show_odds = st.checkbox("Show Live Betting Odds", value=True, help="Fetch real odds from sportsbooks (requires ODDS_API_KEY). Cached for 12 hours to save API quota.")
    
    # Manual refresh button (optional - for when you want fresh odds)
    if show_odds:
        with st.expander("🔄 Manual Odds Refresh", expanded=False):
            st.caption("Odds are cached for 12 hours. Click to force refresh (uses API quota).")
            if st.button("🔄 Refresh Odds Now", help="Bypass cache and fetch fresh odds"):
                # Clear cache for this function
                _fetch_cached_odds_no_debug.clear()
                st.rerun()
    
    # Debug mode for odds API
    debug_odds = st.checkbox("🐛 Debug Odds API", value=False, help="Show detailed API response and error information")
    
    # Book filter - will be set after odds are fetched (see below)
    allowed_books = None
    
    optimizer = AltLineOptimizer()
    
    # Fetch odds if requested (with caching) - MUST happen before book filtering
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
                    
                    if odds_data == "QUOTA_EXCEEDED":
                        # Quota exceeded error - try to load from disk cache
                        aggregator = OddsAggregator()
                        cached_odds = aggregator.load_cached_odds()
                        if cached_odds is not None and len(cached_odds) > 0:
                            st.warning("⚠️ **API Quota Exceeded**, but using cached odds from earlier today")
                            odds_data = cached_odds  # Use cached data instead
                        else:
                            st.error("❌ **API Quota Exceeded**: You've used all your API credits for this month.")
                            st.info("💡 **How to fix:**\n"
                                  "- Check your usage at https://the-odds-api.com/\n"
                                  "- Free tier: 500 requests/month\n"
                                  "- Upgrade your plan or wait for quota reset\n"
                                  "- Lines will still show without live odds (turn off 'Show Live Betting Odds')")
                            allowed_books = None
                    elif odds_data is None:
                        # None means authentication error (401)
                        st.error("❌ **Authentication Error**: Invalid API key. Please check your ODDS_API_KEY.")
                        st.info("💡 **How to fix:**\n"
                              "- Verify your API key at https://the-odds-api.com/\n"
                              "- Update your `.env` file or Streamlit secrets\n"
                              "- Make sure the key is active and not expired")
                        allowed_books = None
                    elif len(odds_data) > 0:
                        st.success(f"✅ Found odds for {odds_data['player'].nunique()} players ({len(odds_data)} total props)")
                        # Debug: show sample of stats found
                        if 'stat' in odds_data.columns:
                            stats_found = odds_data['stat'].unique().tolist()
                            st.caption(f"Stats available: {', '.join(stats_found[:10])}")
                        
                        # Show book filter based on ACTUAL available books in odds data
                        if 'book' in odds_data.columns:
                            actual_books = sorted(odds_data['book'].unique().tolist())
                            if len(actual_books) > 0:
                                with st.expander("📚 Filter Sportsbooks", expanded=False):
                                    # Use session state to remember selection
                                    filter_key = 'lines_explorer_selected_books'
                                    if filter_key not in st.session_state:
                                        st.session_state[filter_key] = actual_books  # Default to all
                                    
                                    selected_books = st.multiselect(
                                        "Select sportsbooks to show",
                                        options=actual_books,
                                        default=st.session_state.get(filter_key, actual_books),
                                        help="Only lines from selected books will be displayed",
                                        key='lines_book_filter'
                                    )
                                    
                                    if len(selected_books) > 0:
                                        allowed_books = selected_books
                                        st.session_state[filter_key] = selected_books
                                    else:
                                        st.warning("⚠️ No books selected - showing all available books")
                                        allowed_books = actual_books
                                        st.session_state[filter_key] = actual_books
                    else:
                        # Empty DataFrame means no events/props found
                        st.warning("⚠️ No odds found. API returned empty response.")
                        if debug_odds:
                            st.info("💡 This could mean:\n"
                                  "- No NBA games today\n"
                                  "- Player props not available yet\n"
                                  "- Market 'player_props' not supported by selected books\n"
                                  "- Check console/terminal for detailed API logs")
                        # Clear book filter if no data
                        allowed_books = None
            else:
                st.info("💡 Set ODDS_API_KEY in secrets (.env file or Streamlit secrets) to view live odds")
                if debug_odds:
                    st.code("# In .env file:\nODDS_API_KEY=your_key_here\n\n# Or in Streamlit secrets:\n# ODDS_API_KEY: your_key_here")
                allowed_books = None
        except Exception as e:
            st.error(f"❌ Error fetching odds: {str(e)}")
            if debug_odds:
                import traceback
                st.code(traceback.format_exc())
            odds_data = None
            allowed_books = None
    
    rows = []
    for _, r in predictions.iterrows():
        player_name = r['player_name']
        
        # Points
        pred_points = r['pred_points']
        line_points = r['line_points']
        # Round line to sportsbook format
        line_points_rounded = round_to_sportsbook_line(line_points)
        
        # Get odds if available (returns sportsbook_line too)
        # Only show lines that have BOTH over AND under odds (if show_odds is enabled AND odds_data is valid DataFrame)
        if show_odds and odds_data is not None and isinstance(odds_data, pd.DataFrame) and len(odds_data) > 0:
            over_odds, under_odds, book, sportsbook_line = find_matching_odds(player_name, 'points', line_points, odds_data, allowed_books)
        else:
            over_odds, under_odds, book, sportsbook_line = (None, None, None, None)
        
        # Only add to rows if we have BOTH over and under odds (when show_odds is enabled)
        # OR if show_odds is disabled, show all lines regardless
        if show_odds:
            # When odds are enabled, only show lines with both over and under
            if over_odds is not None and under_odds is not None:
                # Calculate Model IP (model prediction vs sportsbook line)
                line_for_ip = sportsbook_line if sportsbook_line is not None else line_points_rounded
                model_ip = calculate_implied_prob_from_line(line_for_ip, pred_points) if show_ip else None
            
                # Calculate Book IP (from over odds - this is what the book thinks for OVER)
                book_ip_over = american_to_implied_prob(over_odds) if show_ip and over_odds is not None else None
                
                # Format IP based on user selection
                if show_ip and ip_type:
                    if ip_type == "Model IP (prediction vs line)":
                        ip_display = f"{model_ip:.1%}" if model_ip is not None else None
                    elif ip_type == "Book IP (from odds)":
                        ip_display = f"{book_ip_over:.1%}" if book_ip_over is not None else None
                    else:  # Both
                        model_ip_str = f"{model_ip:.1%}" if model_ip is not None else "N/A"
                        book_ip_str = f"{book_ip_over:.1%}" if book_ip_over is not None else "N/A"
                        ip_display = f"{model_ip_str} / {book_ip_str}"
                else:
                    ip_display = None
                
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
                    "IP": ip_display,
                    "Over Odds": over_str if show_odds else None,
                    "Under Odds": under_str if show_odds else None,
                    "Book": book if show_odds else None
                })
        else:
            # show_odds is False - show all lines without odds requirement
            # Calculate Model IP (model prediction vs line)
            line_for_ip = line_points_rounded
            model_ip = calculate_implied_prob_from_line(line_for_ip, pred_points) if show_ip else None
            
            # Format IP based on user selection (only Model IP available when odds disabled)
            if show_ip and ip_type and ip_type != "Book IP (from odds)":
                if ip_type == "Model IP (prediction vs line)":
                    ip_display = f"{model_ip:.1%}" if model_ip is not None else None
                else:  # Both - but only show model IP when odds disabled
                    model_ip_str = f"{model_ip:.1%}" if model_ip is not None else "N/A"
                    ip_display = f"{model_ip_str} / N/A"
            else:
                ip_display = None
            
            rows.append({
                "Player": player_name, 
                "Team": r['team'], 
                "Opponent": r['opponent'], 
                "Stat": "points", 
                "Line": line_points_rounded,
                "Pred": pred_points, 
                "Value": r['point_value'],
                "IP": ip_display,
                "Over Odds": None,
                "Under Odds": None,
                "Book": None
            })
        
        # Rebounds
        pred_rebounds = r['pred_rebounds']
        line_rebounds = r['line_rebounds']
        line_rebounds_rounded = round_to_sportsbook_line(line_rebounds)
        
        if show_odds and odds_data is not None and isinstance(odds_data, pd.DataFrame) and len(odds_data) > 0:
            over_odds, under_odds, book, sportsbook_line = find_matching_odds(player_name, 'rebounds', line_rebounds, odds_data, allowed_books)
        else:
            over_odds, under_odds, book, sportsbook_line = (None, None, None, None)
        
        if show_odds:
            # Only add to rows if we have BOTH over and under odds
            if over_odds is not None and under_odds is not None:
                line_for_ip = sportsbook_line if sportsbook_line is not None else line_rebounds_rounded
                model_ip = calculate_implied_prob_from_line(line_for_ip, pred_rebounds, std_dev=pred_rebounds*0.25) if show_ip else None
                book_ip_over = american_to_implied_prob(over_odds) if show_ip and over_odds is not None else None
                
                # Format IP based on user selection
                if show_ip and ip_type:
                    if ip_type == "Model IP (prediction vs line)":
                        ip_display = f"{model_ip:.1%}" if model_ip is not None else None
                    elif ip_type == "Book IP (from odds)":
                        ip_display = f"{book_ip_over:.1%}" if book_ip_over is not None else None
                    else:  # Both
                        model_ip_str = f"{model_ip:.1%}" if model_ip is not None else "N/A"
                        book_ip_str = f"{book_ip_over:.1%}" if book_ip_over is not None else "N/A"
                        ip_display = f"{model_ip_str} / {book_ip_str}"
                else:
                    ip_display = None
                
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
                    "IP": ip_display,
                    "Over Odds": over_str if show_odds else None,
                    "Under Odds": under_str if show_odds else None,
                    "Book": book if show_odds else None
                })
        else:
            # show_odds is False - show all lines without odds requirement
            line_for_ip = line_rebounds_rounded
            model_ip = calculate_implied_prob_from_line(line_for_ip, pred_rebounds, std_dev=pred_rebounds*0.25) if show_ip else None
            
            if show_ip and ip_type and ip_type != "Book IP (from odds)":
                if ip_type == "Model IP (prediction vs line)":
                    ip_display = f"{model_ip:.1%}" if model_ip is not None else None
                else:
                    model_ip_str = f"{model_ip:.1%}" if model_ip is not None else "N/A"
                    ip_display = f"{model_ip_str} / N/A"
            else:
                ip_display = None
            
            rows.append({
                "Player": player_name, 
                "Team": r['team'], 
                "Opponent": r['opponent'], 
                "Stat": "rebounds", 
                "Line": line_rebounds_rounded,
                "Pred": pred_rebounds, 
                "Value": r['rebound_value'],
                "IP": ip_display,
                "Over Odds": None,
                "Under Odds": None,
                "Book": None
            })
        
        # Assists
        pred_assists = r['pred_assists']
        line_assists = r['line_assists']
        line_assists_rounded = round_to_sportsbook_line(line_assists)
        
        if show_odds and odds_data is not None and isinstance(odds_data, pd.DataFrame) and len(odds_data) > 0:
            over_odds, under_odds, book, sportsbook_line = find_matching_odds(player_name, 'assists', line_assists, odds_data, allowed_books)
        else:
            over_odds, under_odds, book, sportsbook_line = (None, None, None, None)
        
        if show_odds:
            # Only add to rows if we have BOTH over and under odds
            if over_odds is not None and under_odds is not None:
                line_for_ip = sportsbook_line if sportsbook_line is not None else line_assists_rounded
                model_ip = calculate_implied_prob_from_line(line_for_ip, pred_assists, std_dev=pred_assists*0.30) if show_ip else None
                book_ip_over = american_to_implied_prob(over_odds) if show_ip and over_odds is not None else None
                
                # Format IP based on user selection
                if show_ip and ip_type:
                    if ip_type == "Model IP (prediction vs line)":
                        ip_display = f"{model_ip:.1%}" if model_ip is not None else None
                    elif ip_type == "Book IP (from odds)":
                        ip_display = f"{book_ip_over:.1%}" if book_ip_over is not None else None
                    else:  # Both
                        model_ip_str = f"{model_ip:.1%}" if model_ip is not None else "N/A"
                        book_ip_str = f"{book_ip_over:.1%}" if book_ip_over is not None else "N/A"
                        ip_display = f"{model_ip_str} / {book_ip_str}"
                else:
                    ip_display = None
                
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
                    "IP": ip_display,
                    "Over Odds": over_str if show_odds else None,
                    "Under Odds": under_str if show_odds else None,
                    "Book": book if show_odds else None
                })
        else:
            # show_odds is False - show all lines without odds requirement
            line_for_ip = line_assists_rounded
            model_ip = calculate_implied_prob_from_line(line_for_ip, pred_assists, std_dev=pred_assists*0.25) if show_ip else None
            
            if show_ip and ip_type and ip_type != "Book IP (from odds)":
                if ip_type == "Model IP (prediction vs line)":
                    ip_display = f"{model_ip:.1%}" if model_ip is not None else None
                else:
                    model_ip_str = f"{model_ip:.1%}" if model_ip is not None else "N/A"
                    ip_display = f"{model_ip_str} / N/A"
            else:
                ip_display = None
            
            rows.append({
                "Player": player_name, 
                "Team": r['team'], 
                "Opponent": r['opponent'], 
                "Stat": "assists", 
                "Line": line_assists_rounded,
                "Pred": pred_assists, 
                "Value": r['assist_value'],
                "IP": ip_display,
                "Over Odds": None,
                "Under Odds": None,
                "Book": None
            })
    
    lines_df = pd.DataFrame(rows)
    
    # Check if we have any data - but don't return early, show message instead
    if len(lines_df) == 0:
        st.warning("⚠️ No lines found matching the criteria.")
        if show_odds:
            st.info("💡 If you're filtering by odds, try unchecking 'Show Live Betting Odds' or adjust your book filters.")
        # Create empty DataFrame with expected columns to avoid KeyError
        lines_df = pd.DataFrame(columns=['Player', 'Team', 'Opponent', 'Stat', 'Line', 'Pred', 'Value', 'IP', 'Over Odds', 'Under Odds', 'Book'])
    
    # Ensure required columns exist - add missing columns if needed
    required_cols = ['Stat', 'Team', 'Opponent', 'Value']
    for col in required_cols:
        if col not in lines_df.columns:
            lines_df[col] = None
    
    stat_filter = st.multiselect("Filter stats", options=["points","rebounds","assists"], default=["points","rebounds","assists"])
    team_filter = st.multiselect("Filter teams", options=sorted(predictions['team'].unique().tolist()))
    opp_filter = st.multiselect("Filter opponents", options=sorted(predictions['opponent'].unique().tolist()))
    min_value_filter = st.slider("Minimum value", -10.0, 10.0, 0.0, 0.5)
    
    # Filter data - handle empty DataFrame gracefully
    if len(lines_df) > 0:
        df = lines_df[lines_df['Stat'].isin(stat_filter)].copy()
        if team_filter:
            df = df[df['Team'].isin(team_filter)]
        if opp_filter:
            df = df[df['Opponent'].isin(opp_filter)]
        if 'Value' in df.columns:
            df = df[df['Value'] >= min_value_filter]
        df = df.sort_values('Value', ascending=False)
    else:
        df = lines_df.copy()
    
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
    # Update IP column name based on selection
    if show_ip and 'IP' in df.columns:
        if ip_type == "Model IP (prediction vs line)":
            df = df.rename(columns={'IP': 'Model IP'})
        elif ip_type == "Book IP (from odds)":
            df = df.rename(columns={'IP': 'Book IP'})
        else:  # Both
            df = df.rename(columns={'IP': 'IP (Model / Book)'})
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    captions = []
    if show_ip:
        if ip_type == "Model IP (prediction vs line)":
            captions.append("💡 Model IP = Your model's probability that player exceeds the sportsbook line")
        elif ip_type == "Book IP (from odds)":
            captions.append("💡 Book IP = Sportsbook's implied probability from the odds (what the market thinks)")
        else:  # Both
            captions.append("💡 IP = Model IP (your model) / Book IP (sportsbook odds). Compare to find edge!")
    if show_odds:
        captions.append("💰 Odds shown are from live sportsbooks (closest line match)")
    captions.append("📊 Lines rounded to sportsbook format (whole or .5)")
    
    if captions:
        st.caption(" | ".join(captions))


