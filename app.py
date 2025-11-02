import streamlit as st
import pandas as pd
from src.features.matchup_features import MatchupFeatureBuilder
from src.analysis.value_analyzer import ValueAnalyzer
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime
from src.analysis.hot_hand_tracker import HotHandTracker

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
from src.ui.nba import lines_explorer as ui_lines
from src.ui.nba import player_explorer as ui_player
from src.ui.nba import games as ui_games
from src.ui.nba import line_shopping as ui_shopping
from src.ui.nba import ev_plus as ui_ev_plus

# Page config - optimized for mobile
st.set_page_config(
    page_title="NBA Performance Predictor",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="auto"  # Collapsible sidebar for mobile
)

# Global style overrides: dark background, blue-green accents
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Space+Grotesk:wght@400;600&display=swap');

        html, body, [class^="block-container"] {
            background-color: #000000 !important;
            color: #E6F6F3 !important;
            font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif;
        }

        h1, h2, h3, h4, h5, h6 {
            color: #BFFFEF !important;
            letter-spacing: 0.3px;
        }

        /* Card-like containers */
        .st-expander, .stDataFrame, .stMetric, .stAlert, .stMarkdown, .stButton > button {
            border-radius: 10px !important;
        }

        /* Buttons: blue-green accent */
        .stButton > button {
            background: linear-gradient(135deg, #00e5b0, #00b3a4) !important;
            color: #001412 !important;
            border: none !important;
            box-shadow: 0 4px 16px rgba(0, 229, 176, 0.25);
        }
        .stButton > button:hover {
            filter: brightness(1.05);
        }

        /* Info/Success/Error containers to fit dark theme */
        .stAlert[data-baseweb="notification"] {
            background-color: #0a0f0e !important;
            border: 1px solid #063a33 !important;
        }

        /* Dataframe tweaks */
        .stDataFrame table {
            color: #E6F6F3 !important;
        }
        .stDataFrame thead tr th {
            background-color: #071614 !important;
            color: #BFFFEF !important;
        }
        .stDataFrame tbody tr:nth-child(odd) {
            background-color: #050b0a !important;
        }
        .stDataFrame tbody tr:nth-child(even) {
            background-color: #0a1412 !important;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            background-color: #060909 !important;
            border-right: 1px solid #0f2220 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Title
st.title("🏀 NBA Performance Predictor")
st.markdown("<div style='font-family: Space Grotesk; font-size: 1.05rem; opacity: 0.9;'>Kendall's Player Performance Analysis</div>", unsafe_allow_html=True)
st.markdown("---")

# Tabs: NBA (existing) and NFL (light start)
tab_nba, tab_nfl = st.tabs(["🏀 NBA", "🏈 NFL (beta)"])

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    min_minutes = st.slider("Minimum Minutes Played", 0, 40, 15)
    min_value = st.slider("Minimum Value Score", -5.0, 5.0, 0.0)
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
    filter_injured = st.toggle("Filter injured/out players", value=True, help="Excludes players marked 'Out' from predictions")
    include_questionable = st.toggle("Include questionable players", value=True, help="Shows players with 'Questionable' status (with warning)")

# Get today's games
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_todays_games():
    """Get today's games with timeout handling, times converted to CST"""
    from pytz import timezone
    import pytz
    
    max_retries = 1
    for attempt in range(max_retries + 1):
        try:
            board = scoreboard.ScoreBoard()
            games = board.games.get_dict()
            
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
                # Combine status and time if we have it
                if game_time_str and 'Final' not in status_text and 'LIVE' not in status_text:
                    display_status = f"{status_text} ({game_time_str})" if status_text else game_time_str
                else:
                    display_status = status_text
                
                game_list.append({
                    'home': game['homeTeam']['teamTricode'],
                    'away': game['awayTeam']['teamTricode'],
                    'status': display_status,
                    'raw_status': game.get('gameStatusText', ''),
                    'game_time_cst': game_time_str
                })
            
            if len(game_list) > 0:
                return game_list
            else:
                # Fallback if no games today
                return [
                    {'home': 'LAL', 'away': 'GSW', 'status': 'Example', 'raw_status': 'Example', 'game_time_cst': None},
                    {'home': 'BOS', 'away': 'MIA', 'status': 'Example', 'raw_status': 'Example', 'game_time_cst': None}
                ]
        except Exception as e:
            if attempt >= max_retries:
                # Return fallback games on final failure
                return [
                    {'home': 'LAL', 'away': 'GSW', 'status': 'Example', 'raw_status': 'Example', 'game_time_cst': None},
                    {'home': 'BOS', 'away': 'MIA', 'status': 'Example', 'raw_status': 'Example', 'game_time_cst': None}
                ]
            import time
            time.sleep(0.5)  # Quick retry delay

with tab_nba:
    # Show today's games
    st.header("📅 Today's Games")
    # Remove blocking spinner - use cached data instead
    games = get_todays_games()

    cols = st.columns(min(len(games), 4))
    for i, game in enumerate(games):
        with cols[i % 4]:
            st.info(f"**{game['away']}** @ **{game['home']}**\n\n{game['status']}")

    st.markdown("---")

    # Preload all data on app start for faster tab switching
    @st.cache_resource
    def preload_matchup_builder():
        """Preload MatchupFeatureBuilder once (shared across sessions)"""
        from src.features.matchup_features import MatchupFeatureBuilder
        return MatchupFeatureBuilder(blend_mode="latest")
    
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
    
    # Preload builder and injury tracker
    if 'builder_loaded' not in st.session_state:
        with st.spinner("🔄 Preloading data..."):
            st.session_state['builder'] = preload_matchup_builder()
            st.session_state['injury_tracker'] = preload_injury_data()
            st.session_state['builder_loaded'] = True

    # Predictions cache in session
    if 'predictions' not in st.session_state:
        st.session_state['predictions'] = None
    if 'predictions_raw' not in st.session_state:
        st.session_state['predictions_raw'] = None  # Store raw predictions before filters

    # Controls for predictions
    st.subheader("Predictions Workspace")
    c1, c2 = st.columns([1, 2])
    with c1:
        generate = st.button("🔮 Generate/Refresh Predictions", type="primary", use_container_width=True)
    with c2:
        st.caption("Generates predictions once and reuses them across tabs for faster UX.")

    if generate or st.session_state['predictions'] is None:
        # Show a status message but don't block the UI
        status_placeholder = st.empty()
        status_placeholder.info("🔄 Generating predictions... This may take a moment")
        
        # Use preloaded builder if available
        from src.analysis.value_analyzer import ValueAnalyzer
        analyzer = ValueAnalyzer()
        if 'builder' in st.session_state:
            # Use preloaded builder (already loaded, faster)
            analyzer.builder = st.session_state['builder']
        
        # Generate ALL predictions first (before filters) - this ensures NOP players are included
        predictions_raw = analyzer.analyze_games(games)
        st.session_state['predictions_raw'] = predictions_raw
        
        # Debug: Show teams found
        if len(predictions_raw) > 0:
            teams_found = sorted(predictions_raw['team'].unique().tolist())
            status_placeholder.info(f"🔄 Generating predictions... Found players from {len(teams_found)} teams: {', '.join(teams_found)}")
        
        # Apply filters
        predictions = predictions_raw.copy()
        predictions = predictions[predictions['minutes'] >= min_minutes]
        predictions = predictions[predictions['overall_value'] >= min_value]
        
        # Show debug info about filtering
        if len(predictions_raw) > 0 and len(predictions) < len(predictions_raw):
            filtered_out = len(predictions_raw) - len(predictions)
            status_placeholder.info(f"🔄 Filtered out {filtered_out} players (min_minutes={min_minutes}, min_value={min_value}). Showing {len(predictions)} players.")
        
        # Filter out injured/out players if enabled
        # Use preloaded injury tracker if available
        if filter_injured:
            if 'injury_tracker' in st.session_state:
                injury_tracker = st.session_state['injury_tracker']
            else:
                from src.services.injury_tracker import InjuryTracker
                import os
                injury_tracker = InjuryTracker(api_key=os.getenv('ROTOWIRE_API_KEY'))
            
            # Sort first, then only check top players (faster)
            predictions_sorted = predictions.sort_values('overall_value', ascending=False)
            top_n_to_check = min(50, len(predictions_sorted))  # Only check top 50
            top_players = predictions_sorted.head(top_n_to_check)
            rest_players = predictions_sorted.iloc[top_n_to_check:]
            
            healthy_players = []
            injured_count = 0
            questionable_count = 0
            
            if top_n_to_check > 0:
                st.write(f"Checking injury status for top {top_n_to_check} players...")
                progress_bar = st.progress(0)
                
                for idx, (_, row) in enumerate(top_players.iterrows()):
                    player_name = row['player_name']
                    try:
                        status = injury_tracker.get_player_status(player_name)
                        
                        # Filter out "Out" status
                        if status['status'] == 'Out':
                            injured_count += 1
                            continue
                        
                        # Optionally filter "Questionable" based on toggle
                        if status['status'] == 'Questionable' and not include_questionable:
                            questionable_count += 1
                            continue
                        
                        if status['status'] == 'Questionable':
                            questionable_count += 1
                        
                        healthy_players.append(row)
                    except Exception:
                        # If injury check fails, include player (fail-safe)
                        healthy_players.append(row)
                    
                    # Update progress every player
                    progress_bar.progress((idx + 1) / top_n_to_check)
                
                progress_bar.empty()
            
            # Include rest of players without injury check (assume healthy)
            # This speeds things up significantly
            for _, row in rest_players.iterrows():
                healthy_players.append(row)
            
            status_msg = []
            if injured_count > 0:
                status_msg.append(f"❌ {injured_count} out")
            if questionable_count > 0 and include_questionable:
                status_msg.append(f"⚠️ {questionable_count} questionable")
            if status_msg:
                st.info("Injury filter: " + " | ".join(status_msg))
            
            predictions = pd.DataFrame(healthy_players)
        predictions = predictions.sort_values('overall_value', ascending=False)
        st.session_state['predictions'] = predictions
        status_placeholder.empty()
    st.success(f"✅ Generated predictions for {len(st.session_state['predictions'])} players!")

    predictions = st.session_state['predictions']
    if predictions is None or len(predictions) == 0:
        st.info("Generate predictions to enable the sub-tabs below.")
        st.stop()

    # Sub-tabs inside NBA
    tab_leader, tab_predict, tab_hot, tab_sgp, tab_lines, tab_player, tab_games, tab_shopping, tab_ev_plus = st.tabs([
        "🏆 Leaderboard", "📈 Predictions", "🔥 Hot Hand", "🎰 Live SGP", "📊 Lines Explorer", "🧑‍💻 Player Explorer", "🗓️ Games", "💰 Line Shopping", "⚡ EV+"
    ])

    with tab_leader:
        ui_leader.render(predictions)

    with tab_predict:
        ui_preds.render(predictions)

    with tab_hot:
        ui_hot.render(predictions, games)

    with tab_sgp:
        ui_sgp.render()

    with tab_lines:
        ui_lines.render(predictions)

    with tab_player:
        ui_player.render(predictions)

    with tab_games:
        ui_games.render(predictions, games)
    
    with tab_shopping:
        ui_shopping.render(predictions)
    
    with tab_ev_plus:
        ui_ev_plus.render(predictions, games)

with tab_nfl:
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

# Footer
st.markdown("---")
st.markdown("<div style='opacity:0.8'>Built with: NBA API, Machine Learning, Python</div>", unsafe_allow_html=True)
st.markdown("<div style='opacity:0.6'>Training Data: 2024-25 and 2025-26</div>", unsafe_allow_html=True)