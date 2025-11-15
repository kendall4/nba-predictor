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
            # Clickable link to view full player details
            if st.button(f"📊 View Full Stats & Visualizations", key=f"view_player_{i}_{player_name}"):
                st.session_state['selected_player_for_detail'] = player['player_name']
                st.session_state['selected_player_predictions'] = predictions.to_dict('records')
            
            # Show detail view if this player is selected
            if st.session_state.get('selected_player_for_detail') == player['player_name']:
                from src.ui.components.player_detail_view import render_player_detail
                st.markdown("---")
                render_player_detail(player['player_name'], predictions)
                st.markdown("---")
            
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
                st.metric("Overall Value", f"{player['overall_value']:.2f}")
            st.markdown("#### 💰 Value Scores (by Stat)")
            v1, v2, v3 = st.columns(3)
            with v1:
                delta_color = "normal" if player['point_value'] > 0 else "inverse"
                st.metric("Points Value", f"{player['point_value']:+.1f}", 
                         delta="OVER" if player['point_value'] > 0 else "UNDER",
                         delta_color=delta_color)
            with v2:
                delta_color = "normal" if player['rebound_value'] > 0 else "inverse"
                st.metric("Rebounds Value", f"{player['rebound_value']:+.1f}", 
                         delta="OVER" if player['rebound_value'] > 0 else "UNDER",
                         delta_color=delta_color)
            with v3:
                delta_color = "normal" if player['assist_value'] > 0 else "inverse"
                st.metric("Assists Value", f"{player['assist_value']:+.1f}", 
                         delta="OVER" if player['assist_value'] > 0 else "UNDER",
                         delta_color=delta_color)
            st.markdown("#### 🎯 Predictions vs Season Average")
            p1, p2, p3 = st.columns(3)
            with p1:
                st.metric("Points", f"{player['pred_points']:.1f}", f"{player['point_value']:+.1f} vs avg")
            with p2:
                st.metric("Rebounds", f"{player['pred_rebounds']:.1f}", f"{player['rebound_value']:+.1f} vs avg")
            with p3:
                st.metric("Assists", f"{player['pred_assists']:.1f}", f"{player['assist_value']:+.1f} vs avg")
            
            # Prediction Factors Breakdown
            st.markdown("#### ⚙️ Prediction Factors")
            
            # Convert player Series to dict for easier access
            player_dict = player.to_dict() if hasattr(player, 'to_dict') else dict(player)
            
            # Collect all factors
            factors = []
            
            # System Fit
            if 'system_fit_multiplier' in player_dict and player_dict.get('system_fit_multiplier', 1.0) != 1.0:
                sys_fit = player_dict.get('system_fit_multiplier', 1.0)
                off_fit = player_dict.get('offensive_fit', 1.0)
                def_match = player_dict.get('defensive_matchup', 1.0)
                factors.append(('System Fit', sys_fit, 
                               f"Off: {off_fit:.2f}x, Def: {def_match:.2f}x"))
            
            # Recent Form
            if 'recent_form_multiplier' in player_dict and player_dict.get('recent_form_multiplier', 1.0) != 1.0:
                factors.append(('Recent Form', player_dict.get('recent_form_multiplier', 1.0), 'Last 5 games vs season avg'))
            
            # H2H
            if 'h2h_multiplier' in player_dict and player_dict.get('h2h_multiplier', 1.0) != 1.0:
                factors.append(('Head-to-Head', player_dict.get('h2h_multiplier', 1.0), 'Historical vs this opponent'))
            
            # Rest Days
            if 'rest_days_multiplier' in player_dict and player_dict.get('rest_days_multiplier', 1.0) != 1.0:
                rest_info = player_dict.get('rest_days_info', {})
                if isinstance(rest_info, str):
                    try:
                        import json
                        rest_info = json.loads(rest_info) if rest_info else {}
                    except:
                        rest_info = {}
                rest_desc = rest_info.get('adjustment_type', 'Rest days') if rest_info else 'Rest days'
                factors.append(('Rest Days', player_dict.get('rest_days_multiplier', 1.0), rest_desc))
            
            # Home/Away
            if 'home_away_multiplier' in player_dict and player_dict.get('home_away_multiplier', 1.0) != 1.0:
                ha_info = player_dict.get('home_away_info', {})
                if isinstance(ha_info, str):
                    try:
                        import json
                        ha_info = json.loads(ha_info) if ha_info else {}
                    except:
                        ha_info = {}
                is_home = ha_info.get('is_home', False) if ha_info else False
                ha_desc = 'Home game' if is_home else 'Away game'
                factors.append(('Home/Away', player_dict.get('home_away_multiplier', 1.0), ha_desc))
            
            # Play Style
            if 'play_style_multiplier' in player_dict and player_dict.get('play_style_multiplier', 1.0) != 1.0:
                ps_info = player_dict.get('play_style_info', {})
                if isinstance(ps_info, str):
                    try:
                        import json
                        ps_info = json.loads(ps_info) if ps_info else {}
                    except:
                        ps_info = {}
                style = ps_info.get('team_style', 'Unknown') if ps_info else 'Unknown'
                factors.append(('Play Style', player_dict.get('play_style_multiplier', 1.0), f"Team style: {style}"))
            
            # Upside
            if 'upside_points_multiplier' in player_dict and player_dict.get('upside_points_multiplier', 1.0) != 1.0:
                factors.append(('Upside (Points)', player_dict.get('upside_points_multiplier', 1.0), 'Ceiling potential'))
            if 'upside_rebounds_multiplier' in player_dict and player_dict.get('upside_rebounds_multiplier', 1.0) != 1.0:
                factors.append(('Upside (Rebounds)', player_dict.get('upside_rebounds_multiplier', 1.0), 'Ceiling potential'))
            if 'upside_assists_multiplier' in player_dict and player_dict.get('upside_assists_multiplier', 1.0) != 1.0:
                factors.append(('Upside (Assists)', player_dict.get('upside_assists_multiplier', 1.0), 'Ceiling potential'))
            
            # Display factors (show directly, no nested expander)
            if factors:
                for factor_name, multiplier, description in factors:
                    col1, col2 = st.columns([2, 3])
                    with col1:
                        delta_color = "normal" if multiplier > 1.0 else "inverse"
                        st.metric(factor_name, f"{multiplier:.3f}x", 
                                 delta=f"{((multiplier - 1.0) * 100):+.1f}%", 
                                 delta_color=delta_color)
                    with col2:
                        st.caption(description)
            else:
                st.info("All factors are neutral (1.0x) - predictions based on season averages and matchup only")


