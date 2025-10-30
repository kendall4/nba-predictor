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

# Show today's games
st.header("📅 Today's Games")
with st.spinner("Fetching today's games..."):
    games = get_todays_games()

cols = st.columns(min(len(games), 4))
for i, game in enumerate(games):
    with cols[i % 4]:
        st.info(f"**{game['away']}** @ **{game['home']}**\n\n{game['status']}")

st.markdown("---")

# Generate predictions button
if st.button("🔮 Generate Predictions", type="primary", use_container_width=True):
    
    with st.spinner("Analyzing all players... This takes ~30 seconds"):
        analyzer = ValueAnalyzer()
        predictions = analyzer.analyze_games(games)
        
        # Filter by minutes
        predictions = predictions[predictions['minutes'] >= min_minutes]
        
        # Filter by value
        predictions = predictions[predictions['overall_value'] >= min_value]
        
        # Sort by value
        predictions = predictions.sort_values('overall_value', ascending=False)
    
    st.success(f"✅ Generated predictions for {len(predictions)} players!")
    
    # Top Value Plays
    st.header("💎 Top Value Plays")
    
    top_n = min(10, len(predictions))
    
    for i in range(top_n):
        player = predictions.iloc[i]
        
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
            
            pred_col1, pred_col2, pred_col3 = st.columns(3)
            
            with pred_col1:
                st.metric(
                    "Points", 
                    f"{player['pred_points']:.1f}",
                    f"{player['point_value']:+.1f} vs avg"
                )
            
            with pred_col2:
                st.metric(
                    "Rebounds", 
                    f"{player['pred_rebounds']:.1f}",
                    f"{player['rebound_value']:+.1f} vs avg"
                )
            
            with pred_col3:
                st.metric(
                    "Assists", 
                    f"{player['pred_assists']:.1f}",
                    f"{player['assist_value']:+.1f} vs avg"
                )
    
    # Full data table
    st.markdown("---")
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
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Download button
    csv = predictions.to_csv(index=False)
    st.download_button(
        "📥 Download Full Predictions (CSV)",
        csv,
        "nba_predictions.csv",
        "text/csv",
        use_container_width=True
    )

    # =============================
    # Consistency & Alt-Line EV UI
    # =============================
    if enable_consistency or enable_ev:
        st.markdown("---")
        st.header("🧪 Consistency & Alt Lines")

        # Player selection
        player_list = predictions['player_name'].unique().tolist()
        default_player = player_list[0] if player_list else ""
        selected_player = st.selectbox("Select Player", options=player_list, index=0 if default_player else None)

        # Stat selection
        stat = st.selectbox("Stat", options=["points", "rebounds", "assists", "threes"], index=0)

        # Suggested line: use season avg from predictions row
        sel_row = predictions[predictions['player_name'] == selected_player].head(1)
        suggested_line = 0.0
        if len(sel_row) == 1:
            if stat == 'points':
                suggested_line = float(sel_row.iloc[0]['line_points'])
            elif stat == 'rebounds':
                suggested_line = float(sel_row.iloc[0]['line_rebounds'])
            elif stat == 'assists':
                suggested_line = float(sel_row.iloc[0]['line_assists'])
            else:
                # If threes not available, default to 2.5
                suggested_line = 2.5

        line_value = st.number_input("Line (can override)", min_value=0.0, max_value=100.0, value=float(suggested_line), step=0.5)

        # Run Consistency
        if enable_consistency:
            st.subheader("📈 Consistency (2025-26)")
            tracker = HotHandTracker(blend_mode="latest")
            N_LIST = [5, 6, 7, 8, 10, 15]

            # Build quick opponent map from today's games
            opp_map = {}
            for g in games:
                opp_map[g['home']] = g['away']
                opp_map[g['away']] = g['home']

            # Determine player's team to find today's opponent if scheduled
            opp_text = None
            if len(sel_row) == 1:
                team = sel_row.iloc[0]['team']
                opp_text = opp_map.get(team)

            cols_cons = st.columns(3)
            with cols_cons[0]:
                st.markdown("**Last N Games**")
                for n in N_LIST:
                    rate = tracker.consistency_last_n(selected_player, stat, line_value, n=n, season='2025-26')
                    st.write(f"Last {n}: {rate['hits']}/{rate['games']} → {rate['hit_rate']:.0%}")
            with cols_cons[1]:
                st.markdown("**Head-to-Head (Today)**")
                if isinstance(opp_text, str):
                    h2h = tracker.consistency_h2h(selected_player, stat, line_value, opponent_tricode=opp_text, season='2025-26')
                    st.write(f"vs {opp_text}: {h2h['hits']}/{h2h['games']} → {h2h['hit_rate']:.0%}")
                else:
                    st.write("No opponent mapped for today")
            with cols_cons[2]:
                st.markdown("**Full Season**")
                seas = tracker.consistency_season(selected_player, stat, line_value, season='2025-26')
                st.write(f"2025-26: {seas['hits']}/{seas['games']} → {seas['hit_rate']:.0%}")

        # Alt-line EV (points only, using model prediction)
        if enable_ev and stat == 'points' and len(sel_row) == 1:
            st.subheader("💎 Alt Line EV (sample ladder)")
            pred_points = float(sel_row.iloc[0]['pred_points']) if 'pred_points' in sel_row.columns else None
            if pred_points is not None:
                base = float(line_value)
                ladder = [
                    {"line": max(0.5, base - 4.0), "over": -160, "under": 130},
                    {"line": base - 2.0, "over": -120, "under": 100},
                    {"line": base, "over": -110, "under": -110},
                    {"line": base + 2.0, "over": 120, "under": -150},
                    {"line": base + 4.0, "over": 220, "under": -280},
                ]
                optimizer = AltLineOptimizer()
                result = optimizer.optimize_lines(
                    player_name=selected_player,
                    stat_type='points',
                    prediction=pred_points,
                    alt_lines=ladder
                )
                # Present summary
                best_line = result['best_line']; best_dir = result['best_direction']; best_odds = result['best_odds']; best_ev = result['best_ev']
                st.write(f"Best: {best_dir} {best_line} at {best_odds:+} | EV {best_ev:+.1%}")
                # Show table
                st.dataframe(result['all_lines'], use_container_width=True)
            else:
                st.info("Prediction not available for points.")

# Footer
st.markdown("---")
st.markdown("<div style='opacity:0.8'>Built with: NBA API, Machine Learning, Python</div>", unsafe_allow_html=True)
st.markdown("<div style='opacity:0.6'>Training Data: 2024-25 and 2025-26</div>", unsafe_allow_html=True)