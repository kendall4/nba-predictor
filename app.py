import streamlit as st
import pandas as pd
from src.features.matchup_features import MatchupFeatureBuilder
from src.analysis.value_analyzer import ValueAnalyzer
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime

# Page config
st.set_page_config(
    page_title="NBA Performance Predictor",
    page_icon="🏀",
    layout="wide"
)

# Title
st.title("🏀 NBA Performance Predictor")
st.markdown("### AI-Powered Player Performance Analysis")
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

# Footer
st.markdown("---")
st.markdown("**Built with:** NBA API, Machine Learning, Python")
st.markdown("**Training Data:** 2024-25 Complete Season")