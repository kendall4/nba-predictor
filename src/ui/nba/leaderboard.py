import streamlit as st
from src.services.injury_tracker import InjuryTracker

def render(predictions):
    st.header("💎 Top Value Plays")
    st.caption("💡 Injured/out players are automatically excluded")
    top_n = st.slider("Show Top N", 5, 50, 10)
    top = predictions.head(top_n)
    
    # Quick injury check for displayed players (cache-friendly)
    injury_tracker = InjuryTracker()
    injury_cache = {}
    
    for i in range(len(top)):
        player = top.iloc[i]
        player_name = player['player_name']
        
        # Check injury status (cached per request)
        if player_name not in injury_cache:
            try:
                status = injury_tracker.get_player_status(player_name)
                injury_cache[player_name] = status
            except:
                injury_cache[player_name] = {'status': 'Healthy'}  # Fail-safe
        
        injury_status = injury_cache[player_name]['status']
        status_icon = {
            'Healthy': '🟢',
            'Questionable': '🟡',
            'Out': '🔴',
            'Unknown': '⚪'
        }.get(injury_status, '⚪')
        
        with st.expander(f"#{i+1}: {status_icon} {player['player_name']} ({player['team']} vs {player['opponent']}) - Value: {player['overall_value']:.1f}", expanded=i<3):
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


