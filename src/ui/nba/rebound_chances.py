"""
Rebound Chances Explorer
=========================
Display players sorted by most rebound chances, with detailed breakdown
of factors that determine rebound opportunities.
"""

import streamlit as st
import pandas as pd
from src.services.rebound_chances_analyzer import ReboundChancesAnalyzer


def render(predictions):
    """
    Render the rebound chances analysis page
    
    Args:
        predictions: DataFrame with player predictions including opponent, minutes, etc.
    """
    st.header("🏀 Rebound Chances Analyzer")
    st.caption("Players sorted by most rebound opportunities. Factors: opponent 3PA, shooting %, paint touches, pace, rebounding rate")
    
    if predictions is None or len(predictions) == 0:
        st.info("Generate predictions first to see rebound chances analysis.")
        return
    
    try:
        # Initialize analyzer
        analyzer = ReboundChancesAnalyzer()
    except Exception as e:
        st.error(f"❌ Error initializing rebound analyzer: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return
    
    # Show loading message
    try:
        with st.spinner("Calculating rebound chances for all players..."):
            rebound_df = analyzer.analyze_all_players(predictions, season='2025-26')
    except Exception as e:
        st.error(f"❌ Error calculating rebound chances: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return
    
    if rebound_df is None or len(rebound_df) == 0:
        st.warning("No rebound chances data available. Ensure predictions include opponent information.")
        st.info("💡 Check that predictions have 'opponent' and 'minutes' columns.")
        # Show debug info
        with st.expander("Debug: Predictions columns"):
            st.write(f"Available columns: {list(predictions.columns)}")
            if 'opponent' in predictions.columns:
                st.write(f"Sample opponents: {predictions['opponent'].head(10).tolist()}")
        return
    
    st.success(f"✅ Analyzed {len(rebound_df)} players")
    
    # Filters
    st.markdown("---")
    st.subheader("🔍 Filters")
    
    try:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            min_chances = st.slider("Min Rebound Chances", 0.0, 50.0, 0.0, 1.0)
            min_reb_per_min = st.slider("Min Reb/Min", 0.0, 1.0, 0.0, 0.05)
        
        with col2:
            min_minutes = st.slider("Min Minutes", 0.0, 40.0, 15.0, 1.0)
            show_only_positive_value = st.toggle("Only Positive Value", value=False)
        
        with col3:
            sort_by = st.selectbox(
                "Sort By",
                options=[
                    "Rebound Chances",
                    "Reb/Min",
                    "Pred Rebounds",
                    "Overall Value",
                    "Opponent 3PA",
                    "Opponent Shooting %",
                ],
                index=0
            )
    except Exception as e:
        st.error(f"Error in filters: {str(e)}")
        return
    
    # Apply filters
    try:
        filtered_df = rebound_df.copy()
        filtered_df = filtered_df[filtered_df['rebound_chances'] >= min_chances]
        filtered_df = filtered_df[filtered_df['reb_per_min'] >= min_reb_per_min]
        filtered_df = filtered_df[filtered_df['expected_minutes'] >= min_minutes]
        
        if show_only_positive_value:
            filtered_df = filtered_df[filtered_df['overall_value'] > 0]
        
        # Sort
        sort_column_map = {
            "Rebound Chances": "rebound_chances",
            "Reb/Min": "reb_per_min",
            "Pred Rebounds": "pred_rebounds",
            "Overall Value": "overall_value",
            "Opponent 3PA": "opp_3pa_per_game",
            "Opponent Shooting %": "opp_shooting_pct",
        }
        sort_col = sort_column_map.get(sort_by, "rebound_chances")
        ascending = sort_by == "Opponent Shooting %"  # Lower shooting % is better for rebounds
        filtered_df = filtered_df.sort_values(sort_col, ascending=ascending)
    except Exception as e:
        st.error(f"Error applying filters: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return
    
    if len(filtered_df) == 0:
        st.warning("No players match the current filters. Try adjusting the filter values.")
        return
    
    st.markdown("---")
    st.subheader(f"📊 Rebound Chances Analysis ({len(filtered_df)} players)")
    
    # Main metrics overview
    try:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Rebound Chances", f"{filtered_df['rebound_chances'].mean():.1f}")
        with col2:
            st.metric("Max Rebound Chances", f"{filtered_df['rebound_chances'].max():.1f}")
        with col3:
            st.metric("Avg Reb/Min", f"{filtered_df['reb_per_min'].mean():.2f}")
        with col4:
            st.metric("Avg Opponent 3PA", f"{filtered_df['opp_3pa_per_game'].mean():.1f}")
    except Exception as e:
        st.error(f"Error displaying metrics: {str(e)}")
        return
    
    # Display table
    try:
        st.markdown("#### Top Players by Rebound Chances")
        
        # Create display columns - check which ones exist
        available_cols = []
        col_mapping = {
            'player_name': 'Player',
            'team': 'Team',
            'opponent': 'Opponent',
            'rebound_chances': 'Reb Chances',
            'reb_per_min': 'Reb/Min',
            'pred_rebounds': 'Pred Reb',
            'line_rebounds': 'Line',
            'expected_minutes': 'Min',
            'overall_value': 'Value'
        }
        
        for col in col_mapping.keys():
            if col in filtered_df.columns:
                available_cols.append(col)
        
        if len(available_cols) == 0:
            st.error("No display columns found in data")
            return
        
        # Format the dataframe for display
        display_df = filtered_df[available_cols].copy()
        display_df = display_df.rename(columns=col_mapping)
        
        # Round numeric columns if they exist
        numeric_cols = ['Reb Chances', 'Reb/Min', 'Pred Reb', 'Line', 'Min', 'Value']
        for col in numeric_cols:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').round(1 if col in ['Reb Chances', 'Pred Reb', 'Line', 'Min'] else 2)
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error displaying table: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        return
    
    # Detailed breakdown section
    try:
        st.markdown("---")
        st.subheader("🔬 Factor Breakdown")
        st.caption("Understanding what drives rebound chances for each player")
        
        # Player selector for detailed view
        if 'player_name' not in filtered_df.columns:
            st.warning("Player name column not found in data")
            return
        
        player_list = sorted(filtered_df['player_name'].unique().tolist())
        if len(player_list) == 0:
            st.warning("No players available for detailed analysis")
            return
        
        selected_player = st.selectbox("Select Player for Detailed Analysis", options=player_list)
        
        if selected_player:
            try:
                player_data = filtered_df[filtered_df['player_name'] == selected_player].iloc[0]
                
                st.markdown(f"#### 📋 {selected_player} - Rebound Chances Breakdown")
                
                # Main metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Rebound Chances", f"{player_data['rebound_chances']:.1f}")
                    st.caption(f"Expected opportunities")
                with col2:
                    st.metric("Reb/Min Rate", f"{player_data['reb_per_min']:.2f}")
                    st.caption(f"Player rebounding rate")
                with col3:
                    st.metric("Predicted Rebounds", f"{player_data['pred_rebounds']:.1f}")
                    st.caption(f"Model prediction")
                with col4:
                    st.metric("Expected Minutes", f"{player_data['expected_minutes']:.1f}")
                    st.caption(f"Playing time")
                
                # Opponent factors
                st.markdown("##### 🎯 Opponent Factors")
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    opp_3pa = player_data['opp_3pa_per_game']
                    fg3a_factor = player_data['fg3a_factor']
                    color = "🟢" if fg3a_factor > 1.05 else "🟡" if fg3a_factor > 0.95 else "🔴"
                    st.metric("Opp 3PA/Game", f"{opp_3pa:.1f}", delta=f"{fg3a_factor:.2f}x", delta_color="normal")
                    st.caption(f"{color} More 3s = longer rebounds")
                
                with col2:
                    opp_fg_pct = player_data['opp_shooting_pct']
                    shooting_factor = player_data['shooting_factor']
                    color = "🟢" if shooting_factor > 1.05 else "🟡" if shooting_factor > 0.95 else "🔴"
                    st.metric("Opp FG%", f"{opp_fg_pct:.1%}", delta=f"{shooting_factor:.2f}x", delta_color="normal")
                    st.caption(f"{color} Lower % = more misses")
                
                with col3:
                    opp_paint = player_data['opp_paint_touches']
                    paint_factor = player_data['paint_factor']
                    color = "🟢" if paint_factor > 1.05 else "🟡" if paint_factor > 0.95 else "🔴"
                    st.metric("Opp Paint Touches", f"{opp_paint:.1f}", delta=f"{paint_factor:.2f}x", delta_color="normal")
                    st.caption(f"{color} More paint = contested rebs")
                
                with col4:
                    opp_dreb_pct = player_data['opp_dreb_pct']
                    dreb_factor = player_data['dreb_factor']
                    color = "🟢" if dreb_factor > 1.05 else "🟡" if dreb_factor > 0.95 else "🔴"
                    st.metric("Opp DREB%", f"{opp_dreb_pct:.1%}", delta=f"{dreb_factor:.2f}x", delta_color="normal")
                    st.caption(f"{color} Lower % = more opps")
                
                with col5:
                    opp_pace = player_data['opp_pace']
                    pace_factor = player_data['pace_factor']
                    color = "🟢" if pace_factor > 1.02 else "🟡" if pace_factor > 0.98 else "🔴"
                    st.metric("Opp Pace", f"{opp_pace:.1f}", delta=f"{pace_factor:.2f}x", delta_color="normal")
                    st.caption(f"{color} Higher pace = more rebs")
                
                # Player factors
                st.markdown("##### 👤 Player Factors")
                col1, col2 = st.columns(2)
                
                with col1:
                    position_factor = player_data['position_factor']
                    st.metric("Position Factor", f"{position_factor:.2f}x")
                    if position_factor > 1.1:
                        st.caption("🟢 Big man - more paint opportunities")
                    elif position_factor > 1.0:
                        st.caption("🟡 Forward - moderate opportunities")
                    else:
                        st.caption("🔵 Guard - fewer paint opportunities")
                
                with col2:
                    total_multiplier = (
                        player_data['fg3a_factor'] * 
                        player_data['shooting_factor'] * 
                        player_data['paint_factor'] * 
                        player_data['dreb_factor'] * 
                        player_data['pace_factor'] * 
                        player_data['position_factor']
                    )
                    st.metric("Total Multiplier", f"{total_multiplier:.2f}x")
                    st.caption(f"Combined effect of all factors")
                
                # Explanation
                st.markdown("---")
                st.markdown("##### 📖 How It Works")
                st.info("""
                **Rebound Chances Calculation:**
                
                1. **Base Rate**: Player's rebounding rate per minute × 2.0 (conservative estimate)
                2. **3-Point Factor**: Opponent's 3PA vs league average (more 3s = longer rebounds)
                3. **Shooting Factor**: Opponent's FG% (lower % = more misses = more rebounds)
                4. **Paint Factor**: Opponent's paint touches (more paint attempts = contested rebounds)
                5. **DREB Factor**: Opponent's defensive rebounding % (lower = allows more rebounds)
                6. **Pace Factor**: Opponent's pace (higher = more possessions = more rebounds)
                7. **Position Factor**: Player's position based on rebounding rate (big men get bonus)
                
                **Final Chances** = Base Rate × Minutes × All Factors
                
                Higher rebound chances = more opportunities to grab rebounds, but still depends on player skill.
                """)
            except Exception as e:
                st.error(f"Error displaying player details: {str(e)}")
                import traceback
                with st.expander("Error details"):
                    st.code(traceback.format_exc())
        
        # Top opportunities section
        st.markdown("---")
        st.subheader("🎯 Best Rebound Opportunities")
        
        try:
            # Top 10 by rebound chances
            top_10 = filtered_df.head(10)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### Top 10 by Rebound Chances")
                top_cols = ['player_name', 'team', 'opponent', 'rebound_chances', 'pred_rebounds']
                available_top_cols = [c for c in top_cols if c in top_10.columns]
                if available_top_cols:
                    top_display = top_10[available_top_cols].copy()
                    top_display.columns = ['Player', 'Team', 'Opponent', 'Reb Chances', 'Pred Reb'][:len(available_top_cols)]
                    # Round numeric columns
                    if 'Reb Chances' in top_display.columns:
                        top_display['Reb Chances'] = pd.to_numeric(top_display['Reb Chances'], errors='coerce').round(1)
                    if 'Pred Reb' in top_display.columns:
                        top_display['Pred Reb'] = pd.to_numeric(top_display['Pred Reb'], errors='coerce').round(1)
                    st.dataframe(top_display, use_container_width=True, hide_index=True)
                else:
                    st.warning("Data not available for top players")
            
            with col2:
                st.markdown("##### Best Opponent Matchups")
                # Sort by factors that favor rebounds
                factor_cols = ['fg3a_factor', 'shooting_factor', 'dreb_factor', 'pace_factor']
                available_factors = [c for c in factor_cols if c in filtered_df.columns]
                
                if len(available_factors) > 0:
                    best_matchups = filtered_df.copy()
                    best_matchups['matchup_score'] = 1.0
                    for col in available_factors:
                        best_matchups['matchup_score'] *= pd.to_numeric(best_matchups[col], errors='coerce').fillna(1.0)
                    best_matchups = best_matchups.sort_values('matchup_score', ascending=False).head(10)
                    
                    matchup_cols = ['player_name', 'team', 'opponent', 'matchup_score', 'rebound_chances']
                    available_matchup_cols = [c for c in matchup_cols if c in best_matchups.columns]
                    if available_matchup_cols:
                        matchup_display = best_matchups[available_matchup_cols].copy()
                        matchup_display.columns = ['Player', 'Team', 'Opponent', 'Matchup Score', 'Reb Chances'][:len(available_matchup_cols)]
                        # Round numeric columns
                        if 'Matchup Score' in matchup_display.columns:
                            matchup_display['Matchup Score'] = pd.to_numeric(matchup_display['Matchup Score'], errors='coerce').round(2)
                        if 'Reb Chances' in matchup_display.columns:
                            matchup_display['Reb Chances'] = pd.to_numeric(matchup_display['Reb Chances'], errors='coerce').round(1)
                        st.dataframe(matchup_display, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Data not available for matchups")
                else:
                    st.warning("Factor columns not available")
        except Exception as e:
            st.error(f"Error displaying top opportunities: {str(e)}")
            import traceback
            with st.expander("Error details"):
                st.code(traceback.format_exc())
    except Exception as e:
        st.error(f"Error in detailed breakdown: {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())

