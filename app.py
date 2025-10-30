import streamlit as st
import pandas as pd
from src.features.matchup_features import MatchupFeatureBuilder
from src.analysis.value_analyzer import ValueAnalyzer
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime
from src.analysis.hot_hand_tracker import HotHandTracker
from src.analysis.alt_line_optimizer import AltLineOptimizer

# Page config
st.set_page_config(
    page_title="NBA Performance Predictor",
    page_icon="🏀",
    layout="wide"
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

# Get today's games
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_todays_games():
    try:
        board = scoreboard.ScoreBoard()
        games = board.games.get_dict()
        
        game_list = []
        for game in games:
            game_list.append({
                'home': game['homeTeam']['teamTricode'],
                'away': game['awayTeam']['teamTricode'],
                'status': game['gameStatusText']
            })
        
        if len(game_list) == 0:
            # Fallback games
            game_list = [
                {'home': 'LAL', 'away': 'GSW', 'status': 'Example'},
                {'home': 'BOS', 'away': 'MIA', 'status': 'Example'}
            ]
        
        return game_list
    except Exception as e:
        st.error(f"Error fetching games: {e}")
        return [
            {'home': 'LAL', 'away': 'GSW', 'status': 'Example'},
            {'home': 'BOS', 'away': 'MIA', 'status': 'Example'}
        ]

with tab_nba:
    # Show today's games
    st.header("📅 Today's Games")
    with st.spinner("Fetching today's games..."):
        games = get_todays_games()

    cols = st.columns(min(len(games), 4))
    for i, game in enumerate(games):
        with cols[i % 4]:
            st.info(f"**{game['away']}** @ **{game['home']}**\n\n{game['status']}")

    st.markdown("---")

    # Predictions cache in session
    if 'predictions' not in st.session_state:
        st.session_state['predictions'] = None

    # Controls for predictions
    st.subheader("Predictions Workspace")
    c1, c2 = st.columns([1, 2])
    with c1:
        generate = st.button("🔮 Generate/Refresh Predictions", type="primary", use_container_width=True)
    with c2:
        st.caption("Generates predictions once and reuses them across tabs for faster UX.")

    if generate or st.session_state['predictions'] is None:
        with st.spinner("Analyzing all players... This takes ~30 seconds"):
            analyzer = ValueAnalyzer()
            predictions = analyzer.analyze_games(games)
            predictions = predictions[predictions['minutes'] >= min_minutes]
            predictions = predictions[predictions['overall_value'] >= min_value]
            predictions = predictions.sort_values('overall_value', ascending=False)
            st.session_state['predictions'] = predictions
        st.success(f"✅ Generated predictions for {len(st.session_state['predictions'])} players!")

    predictions = st.session_state['predictions']
    if predictions is None or len(predictions) == 0:
        st.info("Generate predictions to enable the sub-tabs below.")
        st.stop()

    # Sub-tabs inside NBA
    tab_leader, tab_predict, tab_hot, tab_sgp, tab_lines = st.tabs([
        "🏆 Leaderboard", "📈 Predictions", "🔥 Hot Hand", "🎰 Live SGP", "📊 Lines Explorer"
    ])

    with tab_leader:
        st.header("💎 Top Value Plays")
        top_n = st.slider("Show Top N", 5, 50, 10)
        top = predictions.head(top_n)
        for i in range(len(top)):
            player = top.iloc[i]
            with st.expander(f"#{i+1}: {player['player_name']} ({player['team']} vs {player['opponent']}) - Value: {player['overall_value']:.1f}", expanded=i<3):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Minutes", f"{player['minutes']:.0f}")
                    st.metric("Expected Pace", f"{player['expected_pace']:.1f}")
                with col2:
                    st.metric("Opponent DEF", f"{player['opponent_def_rating']:.1f}")
                    if player['overall_value'] > 1:
                        st.success("📈 BET OVER")
                    elif player['overall_value'] < -1:
                        st.error("📉 BET UNDER")
                    else:
                        st.info("➡️ NEUTRAL")
                with col3:
                    st.metric("Value Score", f"{player['overall_value']:.2f}")
                st.markdown("#### 🎯 Predictions vs Season Average")
                p1, p2, p3 = st.columns(3)
                with p1:
                    st.metric("Points", f"{player['pred_points']:.1f}", f"{player['point_value']:+.1f} vs avg")
                with p2:
                    st.metric("Rebounds", f"{player['pred_rebounds']:.1f}", f"{player['rebound_value']:+.1f} vs avg")
                with p3:
                    st.metric("Assists", f"{player['pred_assists']:.1f}", f"{player['assist_value']:+.1f} vs avg")

    with tab_predict:
        st.header("📊 All Predictions")
        display_df = predictions[[
            'player_name', 'team', 'opponent', 
            'pred_points', 'pred_rebounds', 'pred_assists',
            'overall_value', 'expected_pace', 'opponent_def_rating'
        ]].copy()
        display_df.columns = [
            'Player', 'Team', 'Opponent',
            'Pred Points', 'Pred Rebounds', 'Pred Assists',
            'Value Score', 'Pace', 'Opp DEF'
        ]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        csv = predictions.to_csv(index=False)
        st.download_button("📥 Download Full Predictions (CSV)", csv, "nba_predictions.csv", "text/csv", use_container_width=True)

    with tab_hot:
        st.header("🔥 Hot Hand Tracker")
        player_list = predictions['player_name'].unique().tolist()
        selected_player = st.selectbox("Select Player", options=player_list)
        q1 = st.number_input("Q1 Points", min_value=0.0, max_value=40.0, value=10.0, step=1.0)
        threshold = st.select_slider("Hot threshold", options=[5, 10], value=5)
        if st.button("Estimate Hot-Hand Outcome", use_container_width=True):
            tracker = HotHandTracker(blend_mode="latest")
            result = tracker.predict_from_hot_q1(selected_player, q1, threshold=int(threshold))
            st.write(result)

    with tab_sgp:
        st.header("🎰 Live SGP Analyzer")
        st.caption("Enter legs (demo) — integrate live data feed later.")
        legs_df = st.experimental_data_editor(pd.DataFrame([
            {"player":"Player A","stat":"points","line":20,"current":14},
            {"player":"Player B","stat":"rebounds","line":8,"current":6}
        ]), num_rows="dynamic", use_container_width=True)
        time_left = st.number_input("Time left (seconds)", min_value=0, max_value=3600, value=240, step=10)
        odds = st.number_input("Parlay odds (American)", value=10000, step=100)
        if st.button("Analyze Parlay", use_container_width=True):
            from src.analysis.live_sgp_analyzer import LiveSGPAnalyzer
            sgp = LiveSGPAnalyzer()
            analysis = sgp.analyze_parlay(legs=legs_df.to_dict('records'), time_left_seconds=int(time_left), odds=int(odds))
            sgp.display_analysis(analysis)

    with tab_lines:
        st.header("📊 Lines Explorer")
        st.caption("Browse by stat across all players; filter and sort by value")
        # Build long-format table from predictions
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
            df = df[df['Opponent'].inisin(opp_filter)]
        df = df[df['Value'] >= min_value_filter]
        df = df.sort_values('Value', ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)

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