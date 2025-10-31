"""
Line Shopping Tab
================
Compare alt lines across sportsbooks and find best odds
"""

import streamlit as st
import pandas as pd
from src.services.odds_aggregator import OddsAggregator
from src.analysis.alt_line_optimizer import AltLineOptimizer

def render(predictions):
    st.header("💰 Line Shopping")
    st.caption("Compare odds across DraftKings, FanDuel, Fanatics, ESPN Bet, and more")
    
    # Check for API key (try Streamlit secrets first, then env var)
    api_key = None
    try:
        api_key = st.secrets.get('ODDS_API_KEY')
    except (AttributeError, FileNotFoundError):
        pass
    
    if not api_key:
        import os
        api_key = os.getenv('ODDS_API_KEY')
    
    if not api_key:
        st.warning("⚠️ ODDS_API_KEY not set. Add it to Streamlit Cloud secrets or your .env file.")
        st.info("""
        To enable line shopping:
        1. Get free API key from https://the-odds-api.com/
        2. **Streamlit Cloud**: Add to app settings → Secrets
        3. **Local**: Add to `.streamlit/secrets.toml` or `.env`
        """)
        return
    
    aggregator = OddsAggregator(api_key=api_key)
    
    # Player selection
    player_list = sorted(predictions['player_name'].unique().tolist())
    selected_player = st.selectbox("Select Player", options=player_list)
    stat = st.selectbox("Stat", options=["points", "rebounds", "assists"], index=0)
    
    # Get prediction for this player
    row = predictions[predictions['player_name'] == selected_player].head(1)
    pred_val = None
    if len(row) == 1:
        if stat == 'points':
            pred_val = float(row.iloc[0]['pred_points'])
        elif stat == 'rebounds':
            pred_val = float(row.iloc[0]['pred_rebounds'])
        elif stat == 'assists':
            pred_val = float(row.iloc[0]['pred_assists'])
    
    if st.button("🔍 Fetch Live Odds", use_container_width=True):
        with st.spinner("Fetching odds from sportsbooks..."):
            alt_lines_df = aggregator.get_alt_lines(selected_player, stat=stat)
            
            # Handle error responses (debug info)
            if isinstance(alt_lines_df, dict) and 'error' in alt_lines_df:
                if alt_lines_df['error'] == 'player_not_found':
                    st.error(f"❌ Player '{selected_player}' not found in sportsbook data")
                    st.info("**Available players (sample):**")
                    if alt_lines_df.get('available_players'):
                        st.write(", ".join(alt_lines_df['available_players']))
                    st.caption(f"Total players available: {alt_lines_df.get('total_players', 0)}")
                    st.info("💡 Try searching with a different name format or check if the player has any props listed")
                elif alt_lines_df['error'] == 'stat_not_found':
                    st.warning(f"⚠️ No '{stat}' props found for '{selected_player}'")
                    st.info(f"**Available stats for this player:** {', '.join(alt_lines_df.get('available_stats', []))}")
                    if alt_lines_df.get('matched_players'):
                        st.caption(f"Matched as: {alt_lines_df['matched_players'][0]}")
                return
            
            if alt_lines_df is None or len(alt_lines_df) == 0:
                st.warning("No odds found for this player/stat combination.")
                st.info("💡 Odds may not be available yet, or player name doesn't match sportsbook format")
            else:
                st.success(f"Found {len(alt_lines_df)} lines across {alt_lines_df['book'].nunique()} books")
                
                # Show comparison table
                st.subheader("📊 All Available Lines")
                display_df = alt_lines_df[['book', 'line', 'over_odds', 'under_odds']].copy()
                display_df.columns = ['Sportsbook', 'Line', 'Over Odds', 'Under Odds']
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                # Calculate EV for each line if we have prediction
                if pred_val is not None:
                    st.subheader("💎 Best Value Lines (by Expected Value)")
                    optimizer = AltLineOptimizer()
                    
                    ev_results = []
                    for _, line_row in alt_lines_df.iterrows():
                        line_val = float(line_row['line'])
                        over_odds = line_row.get('over_odds')
                        under_odds = line_row.get('under_odds')
                        
                        if pd.notna(over_odds) and pd.notna(under_odds):
                            # Calculate EV for both directions
                            prob_over = optimizer.calculate_probability_over(pred_val, line_val)
                            ev_over = optimizer.calculate_ev(prob_over, int(over_odds))
                            ev_under = optimizer.calculate_ev(1 - prob_over, int(under_odds))
                            
                            # Best direction for this line
                            if ev_over > ev_under:
                                best_ev = ev_over
                                best_dir = 'OVER'
                                best_odds = int(over_odds)
                            else:
                                best_ev = ev_under
                                best_dir = 'UNDER'
                                best_odds = int(under_odds)
                            
                            ev_results.append({
                                'Sportsbook': line_row['book'],
                                'Line': line_val,
                                'Direction': best_dir,
                                'Odds': best_odds,
                                'EV': best_ev,
                                'Probability': prob_over if best_dir == 'OVER' else 1 - prob_over
                            })
                    
                    if ev_results:
                        import pandas as pd
                        ev_df = pd.DataFrame(ev_results).sort_values('EV', ascending=False)
                        st.dataframe(ev_df, use_container_width=True, hide_index=True)
                        
                        # Highlight best
                        best = ev_df.iloc[0]
                        st.success(
                            f"🎯 Best Value: {best['Direction']} {best['Line']} at {best['Sportsbook']} "
                            f"({best['Odds']:+}) | EV: {best['EV']:+.1%}"
                        )
                
                # Comparison for specific line
                st.markdown("---")
                st.subheader("📈 Compare Specific Line")
                specific_line = st.number_input("Line to compare", min_value=0.0, max_value=100.0, value=float(row.iloc[0][f'line_{stat}']) if len(row) == 1 else 20.0, step=0.5)
                
                comparison = aggregator.compare_books(selected_player, stat, specific_line)
                if comparison:
                    col1, col2 = st.columns(2)
                    with col1:
                        if comparison['over']['book']:
                            st.metric("Best Over Odds", f"{comparison['over']['odds']:+}", comparison['over']['book'])
                    with col2:
                        if comparison['under']['book']:
                            st.metric("Best Under Odds", f"{comparison['under']['odds']:+}", comparison['under']['book'])
                else:
                    st.info(f"No odds found for {selected_player} {stat} {specific_line}")

