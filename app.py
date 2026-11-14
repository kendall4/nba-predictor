import streamlit as st
import pandas as pd
from src.features.matchup_features import MatchupFeatureBuilder
from src.analysis.value_analyzer import ValueAnalyzer
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime, timedelta
from src.analysis.hot_hand_tracker import HotHandTracker
from dotenv import load_dotenv
import os

# Load environment variables from .env file (if it exists)
load_dotenv()

# Suppress verbose urllib3 timeout warnings from NBA API
import logging
import warnings
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*timeout.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*HTTPSConnectionPool.*", category=UserWarning)

from src.ui.nba import leaderboard as ui_leader
from src.ui.nba import predictions as ui_preds
from src.ui.nba import hot_hand as ui_hot
from src.ui.nba import live_sgp as ui_sgp
from src.ui.nba import game_script as ui_game_script
from src.ui.nba import triple_double as ui_triple_double
from src.ui.nba import lines_explorer as ui_lines
from src.ui.nba import player_explorer as ui_player
from src.ui.nba import games as ui_games
from src.ui.nba import line_shopping as ui_shopping
from src.ui.nba import ev_plus as ui_ev_plus
from src.ui.nba import edge_finder as ui_edge_finder
from src.ui.nba import player_vs as ui_player_vs
from src.ui.nba import longshot_value as ui_longshot
from src.ui.nba import performance_tracker as ui_performance
from src.ui.nba import parlay_builder as ui_parlay
from src.ui.nba import clv_cashout as ui_clv
from src.ui.nba import rebound_chances as ui_rebound
from src.ui.nba import microwave as ui_microwave
from src.ui.nba import defensive_schemes as ui_defensive_schemes
from src.ui.nba import live_tracker as ui_live_tracker
from src.ui.nba import live_ev as ui_live_ev
from src.ui.nba import correlation as ui_correlation
from src.ui.nba import accuracy_analysis as ui_accuracy
from src.ui.nba import narrative_tracker as ui_narrative
from src.ui.nba import fade_tracker as ui_fade
from src.utils.prediction_columns import normalize_prediction_dataframe
from src.ui.nba import prop_lens as ui_prop_lens
from src.ui.nba import prop_performance as ui_prop_performance
from src.ui.nba import game_picks as ui_game_picks
from src.ui.nba import game_centric as ui_game_centric
from src.ui.nba.theme import inject_global_nba_theme

# Page config - optimized for mobile
st.set_page_config(
    page_title="NBA Performance Predictor",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="auto"  # Collapsible sidebar for mobile
)

inject_global_nba_theme()

# Title
st.title("🏀 NBA Performance Predictor")
st.markdown(
    "<div style='font-size: 1.05rem; opacity: 0.88; color: #8899a0;'>Kendall's Player Performance Analysis</div>",
    unsafe_allow_html=True,
)
st.markdown("---")

# Sport switcher (NOT Streamlit tabs) — tabs execute every pane on every rerun,
# which made WNBA/NFL/MLB hang the NBA page. Only the selected sport runs.
_sport = st.radio(
    "Sport",
    ["🏀 NBA", "🏀 WNBA", "🏈 NFL (beta)", "⚾ MLB (beta)"],
    index=0,
    horizontal=True,
    key="app_sport_selector",
    label_visibility="collapsed",
)
st.caption("NBA-only by default — other sports load only when selected.")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    min_minutes = st.slider("Minimum Minutes Played", 0, 40, 10, help="Filter players by their season average minutes per game")
    min_value = st.slider("Minimum Value Score", -10.0, 5.0, -5.0, help="Filter players by their overall value score (can be negative). For leaderboard/predictions, use negative values to show more players.")
    st.markdown("---")
    st.markdown("**How to use:**")
    st.markdown("1. View today's games")
    st.markdown("2. See AI predictions")
    st.markdown("3. Find value plays")
    st.markdown("4. Compare to Vegas odds")
    st.markdown("---")
    st.subheader("🧪 Consistency & Odds")
    enable_consistency = st.toggle("Enable Consistency Checker", value=True)
    enable_ev = st.toggle("Enable Alt-Line EV (points)", value=True)
    st.markdown("---")
    st.subheader("🏥 Injury Filtering")
    filter_injured = st.toggle("Filter injured/out players", value=True, help="Excludes players marked 'Out' from predictions. This applies to ALL tabs.")
    include_questionable = st.toggle("Include questionable players", value=True, help="Shows players with 'Questionable' status (with warning)")
    st.caption(
        "Predictions also apply a **small teammate-out bump** when stars are OUT (usage vacuum). "
        "See **Props → Teammate outs** expander for emphasis projections."
    )
    
    # Debug toggle to bypass injury filter (for troubleshooting)
    debug_bypass_injury = st.toggle(
        "🔧 Debug: Bypass injury filter", 
        value=False, 
        help="Temporarily disable injury filter for debugging. Use this if you suspect the injury filter is incorrectly filtering players."
    )
    if debug_bypass_injury:
        filter_injured = False
        st.warning("⚠️ Debug mode: Injury filter is bypassed")
    st.markdown("---")
    st.subheader("📈 Prediction logging")
    st.toggle(
        "Log predictions when generating (Accuracy tab)",
        value=st.session_state.get("track_predictions", True),
        key="track_predictions",
        help="Saves each prop prediction to data/prediction_tracking/ for bias & MAE analysis after you enter actuals.",
    )
    st.markdown("---")
    
    # Odds Management Section
    st.subheader("📊 Odds & API Status")
    try:
        from src.services.odds_manager import OddsManager
        import os
        
        # Get API key
        api_key = None
        try:
            api_key = st.secrets.get('ODDS_API_KEY')
        except (AttributeError, FileNotFoundError):
            pass
        if not api_key:
            api_key = os.getenv('ODDS_API_KEY')
        
        if api_key:
            manager = OddsManager(api_key=api_key)
            
            # Quota status (The Odds API: x-requests-* = billing period, usually monthly — not "today")
            quota_status = manager.get_quota_status()
            if quota_status['max_daily'] > 0:
                remaining = quota_status['remaining']
                used = quota_status['requests_today']
                total = quota_status['max_daily']
                pct_used = quota_status['percentage_used']
                
                # Color coding
                if pct_used >= 90:
                    st.error(
                        f"⚠️ Odds API quota (this billing month): {used}/{total} used "
                        f"({pct_used:.0f}%) — {remaining} left"
                    )
                elif pct_used >= 75:
                    st.warning(
                        f"📊 Odds API quota (this billing month): {used}/{total} used "
                        f"({pct_used:.0f}%) — {remaining} left"
                    )
                else:
                    st.info(
                        f"📊 Odds API quota (this billing month): {used}/{total} used "
                        f"({pct_used:.0f}%) — {remaining} left"
                    )
                st.caption(
                    "Resets on your The Odds API plan’s renewal date (not the 1st of the calendar month). "
                    "**Each sidebar “Refresh Odds”** ≈ **1 request** (event list) **+ 1 per NBA game** that day "
                    "(not parallel duplicates — The Odds API is per-game). "
                    "~12 games → **~13 requests** in one refresh."
                )
            else:
                st.caption("📊 Quota status unavailable")
            
            # Cache info
            cache_info = manager.get_cache_info()
            if cache_info['has_session_cache'] or cache_info['has_disk_cache']:
                age = cache_info['cache_age_hours']
                size = cache_info['cache_size']
                if age is not None:
                    if age < 1:
                        st.caption(f"💾 Cache: {size} props, {age*60:.0f} min old")
                    else:
                        st.caption(f"💾 Cache: {size} props, {age:.1f} hours old")
                else:
                    st.caption(f"💾 Cache: {size} props available")
            
            # Refresh button (with cooldown to prevent accidental multiple clicks)
            if 'last_odds_refresh' not in st.session_state:
                st.session_state['last_odds_refresh'] = None
            
            col1, col2 = st.columns([2, 1])
            with col1:
                refresh_disabled = False
                refresh_help = (
                    "Only this button pulls player props from The Odds API (many requests per refresh). "
                    "Tabs use disk/session cache until you refresh."
                )
                if st.session_state['last_odds_refresh']:
                    time_since_refresh = (datetime.now() - st.session_state['last_odds_refresh']).total_seconds()
                    if time_since_refresh < 60:  # 1 minute cooldown
                        refresh_disabled = True
                        refresh_help = f"⏳ Cooldown: {60 - int(time_since_refresh)}s remaining"
                
                if st.button("🔄 Refresh Odds", help=refresh_help, disabled=refresh_disabled):
                    manager.clear_session_cache()
                    with st.spinner("Fetching fresh odds..."):
                        odds_df = manager.get_odds_df(force_refresh=True)
                        st.session_state['last_odds_refresh'] = datetime.now()
                        if odds_df is not None and len(odds_df) > 0:
                            st.success(f"✅ Refreshed {len(odds_df)} props")
                        else:
                            st.warning("⚠️ No odds available")
            with col2:
                if st.button("🗑️ Clear Cache", help="Clear session cache (will reload from disk/API)"):
                    manager.clear_session_cache()
                    st.success("✅ Cache cleared")
        else:
            st.caption("💡 Set ODDS_API_KEY to enable odds features")
    except Exception as e:
        st.caption(f"⚠️ Odds manager unavailable: {str(e)[:50]}")
    
    st.markdown("---")
    st.subheader("⚙️ Prediction Weights")
    st.caption("Adjust how much different factors influence predictions")
    
    col1, col2 = st.columns(2)
    with col1:
        system_fit_weight = st.slider(
            "System Fit Weight", 0.0, 1.0, 0.0, 0.1,
            help="How much offensive/defensive system profiles affect predictions. Higher = more weight on player-system fit. Default 0 while stats.nba.com is flaky."
        )
        st.caption("💡 Offensive style (pace, efficiency) + defensive matchup")
    
    with col2:
        # Default 0: form/H2H hit stats.nba.com gamelogs and can hang for many minutes when
        # the API is down (cache miss). Enable only when nba.com is healthy.
        recent_form_weight = st.slider(
            "Recent Form Weight", 0.0, 1.0, 0.0, 0.1,
            help="How much recent performance (last 5 games) affects predictions. Higher = more weight on hot/cold streaks. Uses stats.nba.com gamelogs — leave at 0 if the API is timing out."
        )
        st.caption("💡 Last 5 games vs season average (needs nba.com — keep 0 if slow)")
    
    h2h_weight = st.slider(
        "Head-to-Head Weight", 0.0, 1.0, 0.0, 0.1,
        help="How much historical performance vs this opponent affects predictions. Higher = more weight on H2H trends. Uses stats.nba.com gamelogs — leave at 0 if the API is timing out."
    )
    st.caption("💡 Player's historical stats vs this specific opponent")
    
    st.markdown("---")
    st.markdown("#### 🆕 Advanced Factors")
    
    rest_days_weight = st.slider(
        "Rest Days Weight", 0.0, 1.0, 0.0, 0.1,
        help="Weight for rest days adjustment (B2B penalties for high-usage, boosts for bench)"
    )
    
    home_away_weight = st.slider(
        "Home/Away Weight", 0.0, 1.0, 0.0, 0.1,
        help="Weight for home/away performance adjustments based on team records"
    )
    
    play_style_weight = st.slider(
        "Play Style Weight", 0.0, 1.0, 0.0, 0.1,
        help="Weight for play style matchup advantages (P&R, isolation, fast break, etc.)"
    )
    
    upside_weight = st.slider(
        "Upside/Ceiling Weight", 0.0, 1.0, 0.0, 0.1,
        help="Weight for player upside potential (career highs, volatility, star status). Higher = more consideration of ceiling vs floor."
    )
    st.caption("💡 Accounts for players who rarely hit thresholds but have the ability/talent to do so")

    st.markdown("---")
    st.subheader("🎯 Prop probability view")
    st.caption(
        "Sliders only change how **means → P(over)** at the posted line (same matchup & shot-zone pipeline). "
        "Logging for the Accuracy tab stays **disciplined** (dream = 0) for clean calibration."
    )
    dream_optimism_slider = st.slider(
        "Dream / optimism",
        0,
        100,
        0,
        help="0 = disciplined. Higher = slightly higher effective mean and sharper over probabilities for exploration.",
    )
    use_nb_dist = st.toggle("Negative Binomial (count props)", value=True)
    rebound_variance_slider = st.slider(
        "Rebound variance emphasis",
        0,
        100,
        50,
        help="Higher = more tail variance on rebound props only.",
    )

    from src.ui.components.bet_ticket_ui import render_ticket_panel
    render_ticket_panel()

def _teams_that_played_on_date(target_date):
    """Return set of team tricodes (home + away) that played on target_date. Used for B2B detection."""
    games = get_games_for_date(target_date)
    teams = set()
    for g in games or []:
        h, a = g.get("home"), g.get("away")
        if h:
            teams.add(h)
        if a:
            teams.add(a)
    return teams


# Get games for a specific date
def _espn_games_for_date(target_date):
    """Fast ESPN scoreboard (avoids stats.nba.com hangs)."""
    import requests
    date_iso = target_date.strftime('%Y-%m-%d')
    espn = requests.get(
        'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
        params={'dates': target_date.strftime('%Y%m%d')},
        timeout=15,
    )
    espn.raise_for_status()
    abbr_map = {'GS': 'GSW', 'NO': 'NOP', 'NY': 'NYK', 'SA': 'SAS', 'UTAH': 'UTA', 'WSH': 'WAS'}
    out = []
    for ev in (espn.json().get('events') or []):
        comp = (ev.get('competitions') or [{}])[0]
        home = away = None
        for c in comp.get('competitors') or []:
            ab = abbr_map.get(c.get('team', {}).get('abbreviation'), c.get('team', {}).get('abbreviation'))
            if c.get('homeAway') == 'home':
                home = ab
            elif c.get('homeAway') == 'away':
                away = ab
        if home and away:
            status = ((ev.get('status') or {}).get('type') or {}).get('shortDetail') or (
                ((ev.get('status') or {}).get('type') or {}).get('description') or ''
            )
            out.append({
                'home': home,
                'away': away,
                'status': status,
                'raw_status': status,
                'game_time_cst': None,
                'game_date': date_iso,
            })
    return out


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_games_for_date(target_date=None):
    """Get games for a specific date (defaults to today) with timeout handling, times converted to CST"""
    from pytz import timezone
    import pytz
    from datetime import datetime, timedelta
    
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

    # Prefer ESPN when NBA.com is known-bad / skipped — scoreboardv2 can hang 30–120s+.
    prefer_espn = os.getenv("NBA_SKIP_AUTO_REFRESH", "").lower() in ("1", "true", "yes") or (
        os.getenv("NBA_PREFER_ESPN_GAMES", "1").lower() in ("1", "true", "yes")
    )
    if prefer_espn:
        try:
            espn_games = _espn_games_for_date(target_date)
            if espn_games:
                return espn_games
        except Exception:
            pass
    
    # Try BALLDONTLIE first when enabled (ALL-STAR: games). Revert: BALLDONTLIE_ENABLED=0 or remove key
    try:
        from src.services.balldontlie_client import get_games_for_date as bdl_get_games, is_balldontlie_enabled
        if is_balldontlie_enabled():
            date_str_bdl = target_date.strftime('%Y-%m-%d')
            bdl_list = bdl_get_games(date_str_bdl)
            if bdl_list and len(bdl_list) > 0:
                # Ensure game_date on each item for consistency
                for g in bdl_list:
                    g.setdefault('game_date', date_str_bdl)
                return bdl_list
    except Exception:
        pass

    max_retries = 0  # don't burn minutes retrying a dead stats.nba.com
    for attempt in range(max_retries + 1):
        try:
            # Try to get games for the target date
            # NBA API ScoreBoard only returns today's games
            # For future dates, we'll need to use the schedule endpoint
            from nba_api.stats.endpoints import scoreboardv2
            
            # Convert date to format needed by API (MM/DD/YYYY)
            date_str = target_date.strftime('%m/%d/%Y')
            
            # Always use scoreboardv2 with specific date to avoid timezone issues
            # (ScoreBoard() returns "current" games which might be yesterday's late at night)
            try:
                board_data = scoreboardv2.ScoreboardV2(game_date=date_str, timeout=12)
                game_headers = board_data.game_header.get_dict()
                line_scores = board_data.line_score.get_dict()
                
                # Get headers for indexing
                header_headers = game_headers.get('headers', [])
                line_headers = line_scores.get('headers', [])
                header_data = game_headers.get('data', [])
                line_data = line_scores.get('data', [])
                
                # Find column indices
                game_id_idx = header_headers.index('GAME_ID') if 'GAME_ID' in header_headers else 2
                home_team_id_idx = header_headers.index('HOME_TEAM_ID') if 'HOME_TEAM_ID' in header_headers else 6
                visitor_team_id_idx = header_headers.index('VISITOR_TEAM_ID') if 'VISITOR_TEAM_ID' in header_headers else 7
                status_text_idx = header_headers.index('GAME_STATUS_TEXT') if 'GAME_STATUS_TEXT' in header_headers else 4
                
                line_game_id_idx = line_headers.index('GAME_ID') if 'GAME_ID' in line_headers else 2
                line_team_id_idx = line_headers.index('TEAM_ID') if 'TEAM_ID' in line_headers else 3
                line_team_abbr_idx = line_headers.index('TEAM_ABBREVIATION') if 'TEAM_ABBREVIATION' in line_headers else 4
                
                # Build mapping of game_id -> {home_team_id: tricode, visitor_team_id: tricode}
                game_teams = {}
                for line in line_data:
                    game_id = line[line_game_id_idx]
                    team_id = line[line_team_id_idx]
                    team_abbr = line[line_team_abbr_idx]
                    if game_id not in game_teams:
                        game_teams[game_id] = {}
                    game_teams[game_id][team_id] = team_abbr
                
                # Convert to format expected by rest of code
                game_list_from_schedule = []
                for header in header_data:
                    game_id = header[game_id_idx]
                    home_team_id = header[home_team_id_idx]
                    visitor_team_id = header[visitor_team_id_idx]
                    status = header[status_text_idx] if len(header) > status_text_idx else ''
                    # Ensure status is always a string (API might return int)
                    if not isinstance(status, str):
                        status = str(status) if status else ''
                    
                    teams = game_teams.get(game_id, {})
                    home_tricode = teams.get(home_team_id)
                    away_tricode = teams.get(visitor_team_id)
                    
                    if home_tricode and away_tricode:
                        game_list_from_schedule.append({
                            'homeTeam': {'teamTricode': home_tricode},
                            'awayTeam': {'teamTricode': away_tricode},
                            'gameStatusText': status,
                            'gameDateTimeUTC': None
                        })
                games = game_list_from_schedule
            except Exception as e:
                # If scoreboardv2 fails, return empty
                games = []
            
            # Timezone conversion: NBA API returns ET, convert to CST
            et_tz = timezone('US/Eastern')
            cst_tz = timezone('US/Central')
            
            game_list = []
            for game in games:
                # Get game time if available
                game_time_str = None
                if 'gameDateTimeUTC' in game:
                    try:
                        # Parse UTC time and convert to CST
                        from datetime import datetime
                        utc_time = datetime.fromisoformat(game['gameDateTimeUTC'].replace('Z', '+00:00'))
                        # Convert UTC -> ET -> CST (or direct UTC -> CST)
                        et_time = utc_time.astimezone(et_tz)
                        cst_time = et_time.astimezone(cst_tz)
                        # Format as "7:30 PM CST" (cross-platform safe)
                        hour = cst_time.hour
                        if hour == 0:
                            hour_str = "12"
                        elif hour > 12:
                            hour_str = str(hour - 12)
                        else:
                            hour_str = str(hour)
                        minute_str = f"{cst_time.minute:02d}"
                        am_pm = "AM" if cst_time.hour < 12 else "PM"
                        game_time_str = f"{hour_str}:{minute_str} {am_pm} CST"
                    except:
                        pass
                
                # Fallback: try gameTimeUTC or gameDateTimeEt
                if not game_time_str:
                    for time_key in ['gameTimeUTC', 'gameDateTimeEt', 'gameDateTime']:
                        if time_key in game and game[time_key]:
                            try:
                                from datetime import datetime
                                # Try parsing various formats
                                time_val = game[time_key]
                                if isinstance(time_val, str):
                                    # Try ISO format
                                    dt = datetime.fromisoformat(time_val.replace('Z', '+00:00'))
                                    cst_time = dt.astimezone(cst_tz)
                                    # Format as "7:30 PM CST" (cross-platform safe)
                                    hour = cst_time.hour
                                    if hour == 0:
                                        hour_str = "12"
                                    elif hour > 12:
                                        hour_str = str(hour - 12)
                                    else:
                                        hour_str = str(hour)
                                    minute_str = f"{cst_time.minute:02d}"
                                    am_pm = "AM" if cst_time.hour < 12 else "PM"
                                    game_time_str = f"{hour_str}:{minute_str} {am_pm} CST"
                                    break
                            except:
                                continue
                
                status_text = game.get('gameStatusText', '')
                # Ensure status_text is always a string (API might return int)
                if not isinstance(status_text, str):
                    status_text = str(status_text) if status_text else ''
                
                # Combine status and time if we have it
                if game_time_str and 'Final' not in status_text and 'LIVE' not in status_text:
                    display_status = f"{status_text} ({game_time_str})" if status_text else game_time_str
                else:
                    display_status = status_text
                
                game_list.append({
                    'home': game['homeTeam']['teamTricode'],
                    'away': game['awayTeam']['teamTricode'],
                    'status': display_status,
                    'raw_status': status_text,  # Already converted to string above
                    'game_time_cst': game_time_str,
                    'game_date': target_date.strftime('%Y-%m-%d')
                })
            
            if len(game_list) > 0:
                return game_list
            # Empty slate from NBA API — try ESPN below
            break
        except Exception as e:
            if attempt >= max_retries:
                break
            import time
            time.sleep(0.5)  # Quick retry delay

    # ESPN fallback when stats.nba.com / BDL are unavailable
    try:
        out = _espn_games_for_date(target_date)
        if out:
            return out
    except Exception:
        pass
    return []

def get_todays_games():
    """Get today's games, or tomorrow's if all games are final"""
    today = datetime.now().date()
    
    # Get today's games
    games_today = get_games_for_date(today)
    
    # Check if all games are final
    if len(games_today) > 0:
        all_final = all(
            'FINAL' in str(game.get('raw_status', '')).upper() or 
            'FINAL' in str(game.get('status', '')).upper()
            for game in games_today
        )
        
        if all_final:
            # All games are final, get tomorrow's games
            tomorrow = today + timedelta(days=1)
            games_tomorrow = get_games_for_date(tomorrow)
            
            if len(games_tomorrow) > 0:
                # Return tomorrow's games
                return games_tomorrow
    
    # Return today's games (or empty if none)
    if len(games_today) > 0:
        return games_today
    else:
        # Fallback if no games today or tomorrow
        return [
            {'home': 'LAL', 'away': 'GSW', 'status': 'Example', 'raw_status': 'Example', 'game_time_cst': None, 'game_date': today.strftime('%Y-%m-%d')},
            {'home': 'BOS', 'away': 'MIA', 'status': 'Example', 'raw_status': 'Example', 'game_time_cst': None, 'game_date': today.strftime('%Y-%m-%d')}
        ]

if _sport == "🏀 NBA":
    # Date selector for viewing different days
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    
    # Let user pick which day to view
    col_date, col_spacer = st.columns([1, 3])
    with col_date:
        date_options = {
            "Today": today,
            "Tomorrow": tomorrow,
            "Yesterday": yesterday
        }
        selected_day = st.selectbox(
            "📅 View games for:",
            options=list(date_options.keys()),
            index=0,  # Default to Today
            key="game_date_selector"
        )
        selected_date = date_options[selected_day]
    
    # Get games for selected date
    games = get_games_for_date(selected_date)
    
    # Debug: show what we got
    if len(games) == 0:
        st.warning(f"⚠️ No games found for {selected_date.strftime('%Y-%m-%d')} - NBA API may not have data for this date yet")
    
    # Date label
    date_label = f"📅 {selected_day}'s Games ({selected_date.strftime('%b %d')})"
    st.header(date_label)

    # Display games in a more flexible layout
    if len(games) > 0:
        # Use up to 4 columns, but adjust based on number of games
        num_cols = min(len(games), 4)
        cols = st.columns(num_cols)
        for i, game in enumerate(games):
            with cols[i % num_cols]:
                status_display = game.get('status', '')
                st.info(f"**{game.get('away', 'TBD')}** @ **{game.get('home', 'TBD')}**\n\n{status_display}")

    st.markdown("---")
    
    # Performance metrics (optional, for debugging)
    with st.expander("⚡ Performance Info", expanded=False):
        st.caption("**Optimization Tips:**")
        st.caption("• Predictions are cached - change filters without regenerating")
        st.caption("• Data preloaded on startup for fast tab switching")
        st.caption("• API calls cached for 5-10 minutes")
        
        if st.button("🗑️ Clear All Cache"):
            st.cache_data.clear()
            st.cache_resource.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Cache cleared! Page will reload...")
            st.rerun()

    st.markdown("---")

    # Preload all data on app start for faster tab switching
    # Note: Cache key includes version to force reload when signature changes
    def _csv_mtime_key():
        """Return CSV mod-time so the builder cache auto-invalidates after data refresh."""
        try:
            from src.config.nba_seasons import PRIMARY_NBA_SEASON
            return int(os.path.getmtime(f'data/raw/player_stats_{PRIMARY_NBA_SEASON}.csv'))
        except FileNotFoundError:
            try:
                return int(os.path.getmtime('data/raw/player_stats_2025-26.csv'))
            except FileNotFoundError:
                return 0

    @st.cache_resource(show_spinner=False)
    def preload_matchup_builder(version=7, csv_mtime=0):
        """Preload MatchupFeatureBuilder once (shared across sessions)

        version + csv_mtime form the cache key — builder auto-reloads
        when the underlying CSV is refreshed (e.g. after trades).
        """
        from src.features.matchup_features import MatchupFeatureBuilder
        # Early season: prefer current-season rows (latest). Mean-blend mixes prior GP
        # into averages and muddies Nov role/minutes — revisit once samples deepen.
        builder = MatchupFeatureBuilder(blend_mode="latest")
        return builder
    
    @st.cache_data(ttl=600)  # Cache injury data for 10 minutes
    def preload_injury_data():
        """Preload ESPN injury data"""
        from src.services.injury_tracker import InjuryTracker
        import os
        tracker = InjuryTracker(api_key=os.getenv('ROTOWIRE_API_KEY'))
        # Force load ESPN injuries by checking a dummy player
        try:
            tracker._get_espn_injuries()
        except:
            pass
        return tracker
    
    # Auto-refresh stale CSVs (player stats, team pace, games) once per session.
    # stats.nba.com is often slow or times out; the collector defaults (120s × 4 retries)
    # can block the app for many minutes. UI path uses short timeouts + few retries.
    def _ensure_fresh_data(max_age_hours=6):
        """Return True if on-disk data is OK to use; False if a refresh was attempted and failed."""
        import time as _time
        skip = os.getenv("NBA_SKIP_AUTO_REFRESH", "").lower() in ("1", "true", "yes")
        if skip:
            print("NBA_SKIP_AUTO_REFRESH set — skipping NBA.com auto-refresh.")
            return True
        try:
            from src.config.nba_seasons import PRIMARY_NBA_SEASON
        except Exception:
            PRIMARY_NBA_SEASON = "2026-27"
        csv_path = f'data/raw/player_stats_{PRIMARY_NBA_SEASON}.csv'
        try:
            age_hours = (_time.time() - os.path.getmtime(csv_path)) / 3600
        except FileNotFoundError:
            age_hours = 999
        if age_hours <= max_age_hours:
            return True
        try:
            from src.data_collection.nba_stats import NBAStatsCollector
            collector = NBAStatsCollector(
                season=PRIMARY_NBA_SEASON,
                api_timeout=12,
                retry_attempts=1,
                retry_base_sleep=1,
            )
            collector.get_player_stats()
            _time.sleep(1)
            collector.get_team_pace_stats()
            _time.sleep(1)
            collector.get_season_games()
            return True
        except Exception as e:
            print(f"Auto-refresh failed (non-fatal): {e}")
            return False

    if 'data_refreshed' not in st.session_state:
        with st.spinner("Checking data freshness…"):
            _fresh_ok = _ensure_fresh_data()
        st.session_state['data_refreshed'] = True
        if not _fresh_ok:
            st.warning(
                "Could not refresh NBA stats from **stats.nba.com** (timeout or rate limit). "
                "Using existing files under `data/raw/`. To skip this check entirely, set env "
                "`NBA_SKIP_AUTO_REFRESH=1`."
            )

    # Preload builder only (local CSVs). Injury tracker is lazy — ESPN fetch on
    # first generate, not on every page refresh.
    _cached_builder = preload_matchup_builder(csv_mtime=_csv_mtime_key())
    st.session_state['builder'] = _cached_builder
    if 'injury_tracker' not in st.session_state:
        st.session_state['injury_tracker'] = None

    # Predictions cache in session
    if 'predictions' not in st.session_state:
        st.session_state['predictions'] = None
    if 'predictions_raw' not in st.session_state:
        st.session_state['predictions_raw'] = None  # Store raw predictions before filters

    # Helper function to apply injury filtering
    def apply_injury_filter(predictions_df, injury_tracker_instance):
        """Apply injury filtering to predictions dataframe
        
        Returns:
            tuple: (filtered_df, injured_count, questionable_count, injured_names, status_breakdown)
            status_breakdown: dict with counts for each status (Healthy, Out, Questionable, Unknown)
        """
        if not filter_injured:
            return predictions_df, 0, 0, [], {}, {}
        
        # Get all unique player names
        player_names = predictions_df['player_name'].unique().tolist()
        
        # Initialize status breakdown
        status_breakdown = {'Healthy': 0, 'Out': 0, 'Questionable': 0, 'Unknown': 0}
        status_samples = {'Out': [], 'Questionable': [], 'Unknown': []}
        
        try:
            # Get all statuses at once (uses cache if available)
            injury_statuses = injury_tracker_instance.get_multiple_statuses(player_names, use_cache=True)
            
            # Create a mapping of player name to status
            status_map = dict(zip(injury_statuses['player'], injury_statuses['status']))
            
            # Filter predictions based on status
            healthy_players = []
            injured_count = 0
            questionable_count = 0
            injured_names = []
            
            for _, row in predictions_df.iterrows():
                player_name = row['player_name']
                status = status_map.get(player_name, 'Unknown')
                
                # Track status breakdown
                if status in status_breakdown:
                    status_breakdown[status] += 1
                else:
                    status_breakdown['Unknown'] += 1
                
                # Collect samples for debugging
                if status == 'Out' and len(status_samples['Out']) < 10:
                    status_samples['Out'].append(player_name)
                elif status == 'Questionable' and len(status_samples['Questionable']) < 10:
                    status_samples['Questionable'].append(player_name)
                elif status == 'Unknown' and len(status_samples['Unknown']) < 10:
                    status_samples['Unknown'].append(player_name)
                
                # Filter out "Out" status
                if status == 'Out':
                    injured_count += 1
                    injured_names.append(player_name)
                    continue
                
                # Optionally filter "Questionable" based on toggle
                if status == 'Questionable' and not include_questionable:
                    questionable_count += 1
                    continue
                
                if status == 'Questionable':
                    questionable_count += 1
                
                healthy_players.append(row)
            
            # Return filtered predictions and stats with detailed breakdown
            filtered_df = pd.DataFrame(healthy_players)
            return filtered_df, injured_count, questionable_count, injured_names, status_breakdown, status_samples
        except Exception as e:
            # If injury check fails, return original predictions with error info
            import traceback
            status_breakdown['Error'] = str(e)
            return predictions_df, 0, 0, [], status_breakdown, {}
    
    # Model workspace — collapsed once you have a slate so **Game** / matchups stay the visual focus
    _preds_ws = st.session_state.get("predictions")
    _ws_expanded = _preds_ws is None or (
        isinstance(_preds_ws, pd.DataFrame) and len(_preds_ws) == 0
    )
    with st.expander("🧮 Model workspace — generate & filter slate", expanded=_ws_expanded):
        st.caption(
            "**Game** and **Prop %** use model output here. Generate once per date, then collapse this panel."
        )
        st.subheader("Predictions Workspace")
        c1, c2 = st.columns([1, 2])
        with c1:
            generate = st.button("🔮 Generate/Refresh Predictions", type="primary", use_container_width=True)
        with c2:
            st.caption("Generates predictions once and reuses them across tabs for faster UX.")

        # Do not auto-run on refresh when predictions is None — that blocked the whole
        # page for minutes (odds fetch / optional nba.com). Require an explicit click.
        if st.session_state['predictions'] is None and not generate:
            st.info("Click **Generate/Refresh Predictions** when ready — page refresh alone will not start a run.")

        if generate:
            # Show a status message but don't block the UI
            status_placeholder = st.empty()
            
            # Show which weights are enabled
            enabled_factors = []
            if system_fit_weight > 0:
                enabled_factors.append(f"System Fit ({system_fit_weight:.1f})")
            if recent_form_weight > 0:
                enabled_factors.append(f"Recent Form ({recent_form_weight:.1f})")
            if h2h_weight > 0:
                enabled_factors.append(f"H2H ({h2h_weight:.1f})")
            if rest_days_weight > 0:
                enabled_factors.append(f"Rest Days ({rest_days_weight:.1f})")
            if home_away_weight > 0:
                enabled_factors.append(f"Home/Away ({home_away_weight:.1f})")
            if play_style_weight > 0:
                enabled_factors.append(f"Play Style ({play_style_weight:.1f})")
            if upside_weight > 0:
                enabled_factors.append(f"Upside ({upside_weight:.1f})")
            
            if enabled_factors:
                status_placeholder.info(f"🔄 Generating predictions with: {', '.join(enabled_factors)}... This may take a moment.")
            else:
                status_placeholder.info("🔄 Generating predictions... This may take a moment")
            
            from src.analysis.value_analyzer import ValueAnalyzer
            analyzer = ValueAnalyzer(builder=st.session_state.get('builder'))
            
            # Generate ALL predictions first (before filters) - this ensures NOP players are included
            # Add timeout protection and progress updates
            try:
                # Show progress message
                progress_msg = "🔄 Generating predictions..."
                if recent_form_weight > 0 or h2h_weight > 0:
                    progress_msg += " (form/H2H may call stats.nba.com — can hang if API is down)"
                
                with st.spinner(progress_msg):
                    # Fast path: skip Odds API + teammate-out nba.com gamelog nudges
                    # (those hang for minutes when stats.nba.com is down).
                    predictions_raw = analyzer.analyze_games(
                        games,
                        odds_lines={},  # empty dict skips odds fetch; uses season-avg lines
                        target_date=selected_date,
                        system_fit_weight=system_fit_weight,
                        recent_form_weight=recent_form_weight,
                        h2h_weight=h2h_weight,
                        rest_days_weight=rest_days_weight,
                        home_away_weight=home_away_weight,
                        play_style_weight=play_style_weight,
                        upside_weight=upside_weight,
                        apply_teammate_absence=False,
                        apply_historical_teammate_nudge=False,
                    )
                    if predictions_raw is not None and len(predictions_raw) > 0:
                        predictions_raw = normalize_prediction_dataframe(predictions_raw)
                st.session_state['predictions_raw'] = predictions_raw
                
                # Automatically track predictions for accuracy analysis (if enabled)
                if predictions_raw is not None and len(predictions_raw) > 0:
                    try:
                        from src.utils.prediction_tracker_helper import track_all_predictions_from_dataframe
                        # Check if tracking is enabled (default: True, can be disabled via session state)
                        tracking_enabled = st.session_state.get('track_predictions', True)
                        track_all_predictions_from_dataframe(
                            predictions_raw,
                            game_date=selected_date,
                            enabled=tracking_enabled
                        )
                        if tracking_enabled:
                            # Silent success - don't clutter UI, but tracking is happening
                            pass
                    except Exception as e:
                        # Silently fail - don't break prediction generation if tracking fails
                        pass
                
                # Clear the spinner and show success
                if predictions_raw is not None and len(predictions_raw) > 0:
                    teams_found = sorted(predictions_raw['team'].unique().tolist())
                    status_placeholder.success(f"✅ Generated {len(predictions_raw)} predictions for {len(teams_found)} teams")
                else:
                    status_placeholder.warning("⚠️ Generated 0 predictions - check if games are scheduled or if there are any players in today's games")
            except Exception as e:
                status_placeholder.error(f"❌ Error generating predictions: {str(e)}")
                import traceback
                # Cannot nest st.expander inside the Model workspace expander
                if st.checkbox("Show full traceback", key="nba_gen_err_traceback"):
                    st.code(traceback.format_exc())
                st.stop()
            
            # Apply filters
            predictions = predictions_raw.copy()
            predictions = predictions[predictions['minutes'] >= min_minutes]
            predictions = predictions[predictions['overall_value'] >= min_value]
            
            # Show comprehensive debug info about filtering
            if len(predictions_raw) > 0:
                filtered_by_minutes = len(predictions_raw[predictions_raw['minutes'] < min_minutes])
                filtered_by_value = len(predictions_raw[predictions_raw['overall_value'] < min_value])
                total_filtered = len(predictions_raw) - len(predictions)
                
                # Detailed breakdown (checkbox — expanders cannot nest inside Model workspace expander)
                if st.checkbox("📊 Show filter breakdown", value=False, key="nba_gen_filter_breakdown"):
                    st.write(f"**Initial predictions generated:** {len(predictions_raw)} players")
                    st.write(f"**After minutes filter (≥{min_minutes} min/game):** {len(predictions_raw) - filtered_by_minutes} players ({filtered_by_minutes} filtered)")
                    st.write(f"**After value filter (≥{min_value}):** {len(predictions)} players ({filtered_by_value} filtered)")
                    if filtered_by_minutes > 0:
                        filtered_minutes_players = predictions_raw[predictions_raw['minutes'] < min_minutes]['player_name'].head(5).tolist()
                        st.write(f"  - Sample filtered by minutes: {', '.join(filtered_minutes_players)}")
                    if filtered_by_value > 0:
                        filtered_value_players = predictions_raw[predictions_raw['overall_value'] < min_value]['player_name'].head(5).tolist()
                        st.write(f"  - Sample filtered by value: {', '.join(filtered_value_players)}")
                
                status_placeholder.info(
                    f"🔄 Filters: {filtered_by_minutes} filtered by minutes (<{min_minutes}), "
                    f"{filtered_by_value} filtered by value (<{min_value}). "
                    f"Showing {len(predictions)}/{len(predictions_raw)} players."
                )
            
            # Filter out injured/out players if enabled
            # Use preloaded injury tracker if available
            injury_tracker = st.session_state.get('injury_tracker')
            if injury_tracker is None and filter_injured:
                from src.services.injury_tracker import InjuryTracker
                injury_tracker = preload_injury_data()
                st.session_state['injury_tracker'] = injury_tracker
            
            if filter_injured and injury_tracker is not None:
                status_placeholder.info(f"🏥 Checking injury status for {len(predictions)} players (using daily cache)...")
                predictions, injured_count, questionable_count, injured_names, status_breakdown, status_samples = apply_injury_filter(predictions, injury_tracker)
                
                if st.checkbox("🏥 Show injury status breakdown", value=False, key="nba_gen_injury_breakdown"):
                    st.write("**Status distribution:**")
                    for status, count in status_breakdown.items():
                        if status != 'Error' and count > 0:
                            st.write(f"  - {status}: {count}")
                    if 'Error' in status_breakdown:
                        st.error(f"⚠️ Error checking injuries: {status_breakdown['Error']}")
                    if status_samples.get('Out'):
                        st.write(f"\n**Sample 'Out' players:** {', '.join(status_samples['Out'][:5])}")
                    if status_samples.get('Questionable'):
                        st.write(f"**Sample 'Questionable' players:** {', '.join(status_samples['Questionable'][:5])}")
                    if status_samples.get('Unknown') and len(status_samples['Unknown']) > 0:
                        st.warning(f"⚠️ {len(status_samples['Unknown'])} players with 'Unknown' status (treated as healthy)")
                        st.write(f"**Sample 'Unknown' players:** {', '.join(status_samples['Unknown'][:5])}")
                
                # Show summary
                status_msg = []
                if injured_count > 0:
                    injured_list = ', '.join(injured_names[:5])
                    if len(injured_names) > 5:
                        injured_list += f" and {len(injured_names) - 5} more"
                    status_msg.append(f"❌ {injured_count} out: {injured_list}")
                if questionable_count > 0 and include_questionable:
                    status_msg.append(f"⚠️ {questionable_count} questionable")
                if status_msg:
                    status_placeholder.info("Injury filter: " + " | ".join(status_msg))
                
                # Warn if many Unknown players
                unknown_count = status_breakdown.get('Unknown', 0)
                if unknown_count > len(predictions) * 0.3:  # More than 30% unknown
                    status_placeholder.warning(
                        f"⚠️ {unknown_count} players have 'Unknown' injury status. "
                        f"Injury tracker may not be working correctly. Consider disabling injury filter if needed."
                    )
                
                # Show final count after injury filter
                status_placeholder.success(
                    f"✅ Final result: {len(predictions)} players after all filters "
                    f"(started with {len(predictions_raw)} players)"
                )
            else:
                # Show final count when injury filter is disabled
                status_placeholder.success(
                    f"✅ Final result: {len(predictions)} players after filters "
                    f"(started with {len(predictions_raw)} players, injury filter disabled)"
                )
            
            predictions = predictions.sort_values('overall_value', ascending=False)
            st.session_state['predictions'] = predictions
            status_placeholder.empty()
    
    # Note: Injury filter is now only applied during prediction generation (lines 644-658)
    # This prevents duplicate filtering and ensures consistent results
    predictions = st.session_state.get("predictions")
    if predictions is not None and len(predictions) > 0:
        _norm = normalize_prediction_dataframe(predictions)
        if _norm is not predictions:
            predictions = _norm
            st.session_state['predictions'] = predictions

    _pr_merge = st.session_state.get("predictions_raw")
    _pred_for_merge = st.session_state.get("predictions")
    if (
        _pr_merge is not None
        and _pred_for_merge is not None
        and len(_pred_for_merge) > 0
    ):
        from src.config.model_aggression import ModelAggression
        from src.analysis.prop_distributions import merge_distribution_into_filtered

        _agg = ModelAggression.from_ui(
            dream_optimism_slider,
            use_nb_dist,
            rebound_variance_slider,
        )
        _merged = merge_distribution_into_filtered(
            _pr_merge, st.session_state["predictions"], _agg
        )
        if _merged is not None and len(_merged) > 0:
            _merged = normalize_prediction_dataframe(_merged)
            st.session_state["predictions"] = _merged
    
    _pred_state = st.session_state.get("predictions")
    if _pred_state is not None and len(_pred_state) == 0:
        st.warning("⚠️ Predictions dataframe is empty after filters.")

    predictions = st.session_state.get("predictions")
    preds_ok = bool(predictions is not None and len(predictions) > 0)
    if not preds_ok:
        st.info(
            "Open **Model workspace** (expand above) and run **Generate** to unlock props, hit rates, EV tools, and line shopping."
        )

    # Sub-tabs — slate-first: Game & Prop % before the raw model grid
    tab_game, tab_prop_lens, tab_prop_pct, tab_game_picks, tab_live, tab_analysis, tab_betting, tab_info, tab_core = st.tabs([
        "🏀 Game",
        "🔍 Prop lens",
        "📈 Prop %",
        "🏆 Game Picks",
        "⚡ Live Games",
        "🔬 Analysis Tools",
        "💰 Betting & Odds",
        "📋 Player & Game Info",
        "🧮 Model & predictions",
    ])

    def _safe_render(label, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception as e:
            st.error(f"Error in {label}: {e}")
            import traceback
            st.code(traceback.format_exc())

    # Game Picks — B2B flags for model (shared by Game + Game Picks tabs)
    prev_date = selected_date - timedelta(days=1)
    teams_played_prev = _teams_that_played_on_date(prev_date)
    games_for_picks = [
        {**g, 'home_b2b': g.get('home') in teams_played_prev, 'away_b2b': g.get('away') in teams_played_prev}
        for g in games
    ]

    # Game Tab - per-game view with winner pick and hot props
    with tab_game:
        _safe_render("Game", ui_game_centric.render, predictions, games=games, games_for_picks=games_for_picks, selected_date=selected_date)

    with tab_prop_lens:
        _safe_render("Prop lens", ui_prop_lens.render_prop_lens, predictions, games, selected_date)

    # Prop % Tab
    with tab_prop_pct:
        _safe_render("Prop %", ui_prop_performance.render, predictions, games=games, selected_date=selected_date)

    with tab_game_picks:
        _safe_render("Game Picks", ui_game_picks.render, predictions, games=games_for_picks, selected_date=selected_date)

    # Live Games Tab
    with tab_live:
        tab_tracker, tab_live_ev, tab_hot, tab_sgp, tab_script = st.tabs([
            "⚡ Live Tracker", "💹 Live EV", "🔥 Hot Hand", "🎰 Live SGP", "📊 Game Script"
        ])
        with tab_tracker:
            _safe_render("Live Tracker", ui_live_tracker.render)
        with tab_live_ev:
            _safe_render("Live EV", ui_live_ev.render, predictions, selected_date)
        with tab_hot:
            _safe_render("Hot Hand", ui_hot.render, predictions, games)
        with tab_sgp:
            _safe_render("Live SGP", ui_sgp.render, predictions)
        with tab_script:
            _safe_render("Game Script", ui_game_script.render)

    # Analysis Tools Tab
    with tab_analysis:
        tab_triple, tab_rebound, tab_microwave, tab_defensive, tab_correlation, tab_accuracy, tab_narrative, tab_fade = st.tabs([
            "🎯 Triple Double", "🏀 Rebound Chances", "🔥 Microwave", "🛡️ Defensive Schemes", "🔗 Correlations", "📊 Accuracy Analysis", "🔥 Narrative Tracker", "📉 Fade Tracker"
        ])
        with tab_triple:
            _safe_render("Triple Double", ui_triple_double.render)
        with tab_rebound:
            _safe_render("Rebound Chances", ui_rebound.render, predictions)
        with tab_microwave:
            _safe_render("Microwave", ui_microwave.render, predictions, games)
        with tab_defensive:
            _safe_render("Defensive Schemes", ui_defensive_schemes.render)
        with tab_correlation:
            _safe_render("Correlations", ui_correlation.render)
        with tab_accuracy:
            _safe_render("Accuracy", ui_accuracy.render)
        with tab_narrative:
            _safe_render("Narrative Tracker", ui_narrative.render)
        with tab_fade:
            _safe_render("Fade Tracker", ui_fade.render)

    # Betting & Odds Tab
    with tab_betting:
        if preds_ok:
            tab_lines, tab_shopping, tab_ev_plus, tab_edge, tab_vs, tab_longshot, tab_parlay, tab_clv, tab_performance, tab_tickets = st.tabs([
                "📊 Lines Explorer", "💰 Line Shopping", "⚡ EV+", "📈 Edge", "⚔️ Vs", "🎯 Longshot Value", "🎫 Parlay Builder", "💰 CLV Cash-Out", "📊 Performance", "🎟️ Tickets"
            ])
            with tab_lines:
                _safe_render("Lines Explorer", ui_lines.render, predictions, games)
            with tab_shopping:
                _safe_render("Line Shopping", ui_shopping.render, predictions)
            with tab_ev_plus:
                _safe_render("EV+", ui_ev_plus.render, predictions, games, selected_date)
            with tab_edge:
                _safe_render("Edge Finder", ui_edge_finder.render, predictions, games, selected_date)
            with tab_vs:
                _safe_render("Player Vs", ui_player_vs.render, predictions)
            with tab_longshot:
                _safe_render("Longshot Value", ui_longshot.render, predictions, games)
            with tab_parlay:
                _safe_render("Parlay Builder", ui_parlay.render, predictions, games, selected_date)
            with tab_clv:
                _safe_render("CLV Cash-Out", ui_clv.render)
            with tab_performance:
                _safe_render("Performance", ui_performance.render)
            with tab_tickets:
                try:
                    from src.ui.components.bet_ticket_ui import render_saved_tickets_grading
                    render_saved_tickets_grading()
                except Exception as e:
                    st.error(f"Tickets: {e}")
        else:
            st.info(
                "Lines Explorer, EV+, Edge, and parlays need a generated slate — expand **Model workspace** above."
            )
            tab_clv, tab_performance, tab_tickets = st.tabs([
                "💰 CLV Cash-Out", "📊 Performance", "🎟️ Tickets"
            ])
            with tab_clv:
                _safe_render("CLV Cash-Out", ui_clv.render)
            with tab_performance:
                _safe_render("Performance", ui_performance.render)
            with tab_tickets:
                try:
                    from src.ui.components.bet_ticket_ui import render_saved_tickets_grading
                    render_saved_tickets_grading()
                except Exception as e:
                    st.error(f"Tickets: {e}")

    # Player & Game Info Tab
    with tab_info:
        if preds_ok:
            tab_player, tab_games = st.tabs(["🧑‍💻 Player Explorer", "🗓️ Games"])
            with tab_player:
                _safe_render("Player Explorer", ui_player.render, predictions)
            with tab_games:
                _safe_render("Games", ui_games.render, predictions, games)
        else:
            st.info(
                "**Player Explorer** and **Games** (lineups vs projections) need a generated slate — use **Model workspace** above."
            )
            if games:
                st.markdown("**Matchups for this date**")
                for g in games:
                    st.caption(f"{g.get('away', '?')} @ {g.get('home', '?')} — {g.get('status', '')}")

    # Leaderboard + raw projection table (after slate-first tabs)
    with tab_core:
        if preds_ok:
            tab_leader, tab_predict = st.tabs(["🏆 Leaderboard", "📈 Predictions"])
            with tab_leader:
                _safe_render("Leaderboard", ui_leader.render, predictions)
            with tab_predict:
                _safe_render("Predictions", ui_preds.render, predictions)
        else:
            st.info(
                "Use **Model workspace** at the top of this page to generate projections, then open this tab for "
                "**Leaderboard** and the full **Predictions** grid."
            )

elif _sport == "🏀 WNBA":
    from src.ui.wnba import main as ui_wnba
    ui_wnba.render()

elif _sport == "🏈 NFL (beta)":
    # NFL Tabs
    tab_rush_pass, tab_player_props = st.tabs([
        "🏈 Rush + Pass TD Analyzer", "📊 Player Props (beta)"
    ])
    
    with tab_rush_pass:
        from src.ui.nfl import rush_pass_td_analyzer as ui_rush_pass
        ui_rush_pass.render()
    
    with tab_player_props:
        st.header("NFL Player Props (beta)")
        st.caption("Start light: receptions, receiving yards, passing yards, TDs, passing TDs, pass attempts")
        st.markdown("---")
        st.subheader("📤 Upload Player Game Logs (CSV)")
        st.caption("Columns suggested: GAME_DATE, OPP, receptions, rec_yards, pass_yards, tds, pass_tds, pass_attempts")
        nfl_file = st.file_uploader("Upload NFL player gamelog CSV", type=["csv"], key="nfl_gamelog")
        if nfl_file is not None:
            try:
                nfl_df = pd.read_csv(nfl_file)
                # Player selection
                # If dataset includes PLAYER column, filter; otherwise ask for name and assume file is already filtered
                player_name = st.text_input("Player Name (optional if file is single-player)", value="")
                if 'PLAYER' in nfl_df.columns and player_name:
                    nfl_df = nfl_df[nfl_df['PLAYER'].str.lower() == player_name.lower()]

                stat_map = {
                    'receptions': 'receptions',
                    'receiving yards': 'rec_yards',
                    'passing yards': 'pass_yards',
                    'touchdowns (any)': 'tds',
                    'passing touchdowns': 'pass_tds',
                    'pass attempts': 'pass_attempts'
                }
                stat_choice = st.selectbox("Stat", options=list(stat_map.keys()))
                stat_col = stat_map[stat_choice]
                prop_line = st.number_input("Line", min_value=0.0, max_value=600.0, value=50.0, step=0.5)

                # Consistency
                st.subheader("📈 Consistency")
                N_LIST = [5, 6, 7, 8, 10, 15]
                def calc_rate(df, col, line):
                    valid = df[pd.notna(df[col])]
                    hits = (valid[col] >= line).sum()
                    games = len(valid)
                    return hits, games, (hits / games) if games else 0.0

                colsN = st.columns(3)
                with colsN[0]:
                    st.markdown("**Last N**")
                    for n in N_LIST:
                        sample = nfl_df.sort_values('GAME_DATE', ascending=False).head(n)
                        h, g, r = calc_rate(sample, stat_col, prop_line)
                        st.write(f"Last {n}: {h}/{g} → {r:.0%}")
                with colsN[1]:
                    st.markdown("**Full Season**")
                    h, g, r = calc_rate(nfl_df, stat_col, prop_line)
                    st.write(f"Season: {h}/{g} → {r:.0%}")
                with colsN[2]:
                    st.markdown("**H2H (OPP column)**")
                    opp = st.text_input("Opponent tricode (e.g., NE, KC)", value="")
                    if opp and 'OPP' in nfl_df.columns:
                        h2h_df = nfl_df[nfl_df['OPP'].str.upper() == opp.upper()]
                        h, g, r = calc_rate(h2h_df, stat_col, prop_line)
                        st.write(f"vs {opp.upper()}: {h}/{g} → {r:.0%}")

                # Alt lines EV (uses normal approx like NBA)
                st.markdown("---")
                st.subheader("💎 Alt Line EV (CSV upload)")
                st.caption("Columns: line, over, under (American odds)")
                nfl_odds = st.file_uploader("Upload alt lines CSV for this prop (optional)", type=["csv"], key="nfl_odds")
                if nfl_odds is not None:
                    try:
                        odds_df = pd.read_csv(nfl_odds)
                        if all(c in odds_df.columns for c in ['line','over','under']):
                            from src.analysis.alt_line_optimizer import AltLineOptimizer
                            optimizer = AltLineOptimizer()
                            # Heuristic prediction: use recent mean as prediction
                            recent = nfl_df.sort_values('GAME_DATE', ascending=False).head(10)
                            pred = float(recent[stat_col].mean()) if stat_col in recent.columns else prop_line
                            result = optimizer.optimize_lines(
                                player_name=player_name or "NFL Player",
                                stat_type=stat_choice,
                                prediction=pred,
                                alt_lines=odds_df[['line','over','under']].to_dict('records')
                            )
                            st.write(f"Best: {result['best_direction']} {result['best_line']} at {int(result['best_odds']):+} | EV {result['best_ev']:+.1%}")
                            st.dataframe(result['all_lines'], use_container_width=True)
                        else:
                            st.error("CSV must contain columns: line, over, under")
                    except Exception as e:
                        st.error(f"Error reading CSV: {e}")
            except Exception as e:
                st.error(f"Error reading NFL gamelog CSV: {e}")

elif _sport == "⚾ MLB (beta)":
    from src.ui.mlb import hr_ev as ui_mlb_hr

    ui_mlb_hr.render()

# Footer
st.markdown("---")
st.markdown("<div style='opacity:0.8'>Built with: NBA API / stats.nba.com, ESPN, Machine Learning, Python</div>", unsafe_allow_html=True)
st.markdown("<div style='opacity:0.6'>Default surface: NBA — switch sports above only when needed</div>", unsafe_allow_html=True)
