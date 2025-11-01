"""
EV+ Tab - High Expected Value Bets
====================================
Shows bets with positive expected value, similar to premium betting apps
"""

import streamlit as st
import pandas as pd
import numpy as np
from src.analysis.alt_line_optimizer import AltLineOptimizer
from src.analysis.bet_generator import BetGenerator
from src.utils.odds_utils import american_to_implied_prob, implied_prob_to_percent
import os

def render(predictions, games):
    st.header("⚡ EV+")
    st.caption("Browse all bets with EV, Implied Probability, and Edge calculations")
    
    # Check for API key
    api_key = None
    try:
        api_key = st.secrets.get('ODDS_API_KEY')
    except (AttributeError, FileNotFoundError):
        pass
    
    if not api_key:
        api_key = os.getenv('ODDS_API_KEY')
    
    if not api_key:
        st.warning("⚠️ ODDS_API_KEY not set. EV+ requires live odds data.")
        st.info("""
        To enable EV+:
        1. Get free API key from https://the-odds-api.com/
        2. **Streamlit Cloud**: Add to app settings → Secrets
        3. **Local**: Add to `.streamlit/secrets.toml` or `.env`
        """)
        return
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        stat_filter = st.selectbox("Stat", options=["points", "rebounds", "assists"], index=0, key="ev_plus_stat")
    with col2:
        only_ev_plus = st.checkbox("Show only EV+ bets", value=False, help="Filter to only positive EV bets", key="ev_plus_only_positive")
        min_ev = st.slider("Min EV (if filtering)", 0.0, 0.5, 0.05, 0.01, help="Minimum Expected Value", key="ev_plus_min_ev") if only_ev_plus else None
    with col3:
        sort_by = st.selectbox("Sort by", options=["EV (highest)", "EV (lowest)", "Odds (highest)", "Odds (lowest)", "Line"], index=0, key="ev_plus_sort")
    with col4:
        show_mainline_only = st.checkbox("Mainline only (≤ +200)", value=False, key="ev_plus_mainline")
        show_longshot_only = st.checkbox("Longshots only (≥ +500)", value=False, key="ev_plus_longshot")
    
    # Generate EV+ bets
    generator = BetGenerator(odds_api_key=api_key)
    optimizer = AltLineOptimizer()
    
    if st.button("🔍 Find EV+ Bets", type="primary", use_container_width=True, key="ev_plus_find_bets"):
        with st.spinner("Analyzing odds and calculating EV..."):
            try:
                # Get all bets for this stat (include all EV values)
                bets_df = generator.generate_all_bets(
                    predictions,
                    stat_type=stat_filter,
                    min_ev=-1.0,  # Include all bets (negative EV too)
                    include_negative_ev=True
                )
                
                if bets_df is None or len(bets_df) == 0:
                    st.warning("No odds data available or no matching players found.")
                    st.info("💡 Try generating predictions first, or check if there are games today.")
                    st.info("💡 Make sure ODDS_API_KEY is set and odds are available for today's games.")
                    return
            except Exception as e:
                st.error(f"Error fetching odds: {e}")
                st.info("💡 Check your ODDS_API_KEY and try again.")
                return
            
            # Apply filters
            filtered_bets = bets_df.copy()
            
            # Filter to EV+ only if checkbox is checked
            if only_ev_plus and min_ev is not None:
                filtered_bets = filtered_bets[filtered_bets['ev'] >= min_ev]
            
            # Filter by bet type (mainline/longshot)
            if show_mainline_only:
                filtered_bets = filtered_bets[filtered_bets['is_mainline']]
            if show_longshot_only:
                filtered_bets = filtered_bets[filtered_bets['is_longshot']]
            
            if len(filtered_bets) == 0:
                st.warning("No bets found matching filters.")
                st.info("💡 Adjust filters or try a different stat.")
                return
            
            # Rename for clarity
            ev_plus_bets = filtered_bets
            
            # Sort
            if sort_by == "EV (highest)":
                ev_plus_bets = ev_plus_bets.sort_values('ev', ascending=False)
            elif sort_by == "EV (lowest)":
                ev_plus_bets = ev_plus_bets.sort_values('ev', ascending=True)
            elif sort_by == "Odds (highest)":
                ev_plus_bets = ev_plus_bets.sort_values('odds', ascending=False)
            elif sort_by == "Odds (lowest)":
                ev_plus_bets = ev_plus_bets.sort_values('odds', ascending=True)
            else:
                ev_plus_bets = ev_plus_bets.sort_values('line', ascending=True)
            
            ev_positive_count = (ev_plus_bets['ev'] > 0).sum()
            if only_ev_plus:
                st.success(f"✅ Found {len(ev_plus_bets)} EV+ bets (EV >= {min_ev:.1%})")
            else:
                st.success(f"✅ Found {len(ev_plus_bets)} bets ({ev_positive_count} EV+)")
            
            # Display bets in card format
            for idx, bet in ev_plus_bets.iterrows():
                # Color code by EV
                ev_icon = "🔥" if bet['ev'] > 0.1 else "✅" if bet['ev'] > 0.05 else "💰" if bet['ev'] > 0 else "⚠️" if bet['ev'] > -0.05 else "❌"
                ev_color = bet['ev'] > 0
                
                with st.expander(
                    f"{ev_icon} {bet['player']} {bet['direction']} {bet['line']} {bet['stat'].capitalize()} "
                    f"({bet['odds']:+d}) - EV: {bet['ev']:+.1%}",
                    expanded=idx < 3
                ):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Odds", f"{bet['odds']:+d}")
                        st.caption(f"IP: {implied_prob_to_percent(bet['odds'])}")
                    
                    with col2:
                        st.metric("Model IP", f"{bet['probability']:.1%}")
                        fv_str = f"+{bet['fv_odds']}" if bet['fv_odds'] > 0 else str(bet['fv_odds'])
                        st.caption(f"FV: {fv_str}")
                    
                    with col3:
                        st.metric("EV", f"{bet['ev']:+.1%}")
                        st.caption(f"Units: {bet['units']:.2f}u")
                    
                    with col4:
                        st.metric("Prediction", f"{bet['prediction']:.1f}")
                        st.caption(f"Book: {bet['book'].upper()}")
                    
                    # Edge calculation
                    model_prob = bet['probability']
                    implied_prob = american_to_implied_prob(bet['odds'])
                    edge = model_prob - implied_prob
                    
                    if edge > 0.1:
                        st.success(f"🔥 Strong Edge: {edge:.1%} (Model says {model_prob:.1%}, Book says {implied_prob:.1%})")
                    elif edge > 0.05:
                        st.info(f"✅ Good Edge: {edge:.1%}")
                    else:
                        st.caption(f"Edge: {edge:+.1%}")
            
            # Summary table
            st.markdown("---")
            st.subheader("📊 EV+ Summary")
            summary_df = ev_plus_bets[[
                'player', 'stat', 'direction', 'line', 'odds', 
                'probability', 'ev', 'units', 'book'
            ]].copy()
            summary_df.columns = [
                'Player', 'Stat', 'Direction', 'Line', 'Odds',
                'Model IP', 'EV', 'Units', 'Book'
            ]
            # Add Implied Prob column and Edge
            summary_df['Implied IP'] = summary_df['Odds'].apply(implied_prob_to_percent)
            # Calculate Edge: Model IP - Implied IP
            model_ip_decimal = ev_plus_bets['probability'].values
            implied_ip_decimal = ev_plus_bets['odds'].apply(american_to_implied_prob).values
            summary_df['Edge'] = (model_ip_decimal - implied_ip_decimal)
            summary_df['Edge'] = summary_df['Edge'].apply(lambda x: f"{x:+.1%}")
            summary_df = summary_df[['Player', 'Stat', 'Direction', 'Line', 'Odds', 'Implied IP', 'Model IP', 'Edge', 'EV', 'Units', 'Book']]
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            # Stats summary
            ev_positive = (ev_plus_bets['ev'] > 0).sum()
            ev_strong = (ev_plus_bets['ev'] > 0.1).sum()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Bets", len(ev_plus_bets))
            with col2:
                st.metric("EV+ Bets", ev_positive, f"{ev_positive/len(ev_plus_bets)*100:.0f}%")
            with col3:
                st.metric("Strong EV+ (10%+)", ev_strong)
            
            # Download CSV
            csv = ev_plus_bets.to_csv(index=False)
            st.download_button(
                "📥 Download EV+ Bets (CSV)",
                csv,
                f"ev_plus_{stat_filter}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True,
                key="ev_plus_download_csv"
            )
    
    # Show info about EV+
    with st.expander("ℹ️ About EV+"):
        st.markdown("""
        **Expected Value (EV)** measures the average profit per $1 bet over time.
        
        - **Positive EV (+EV)**: Long-term profitable bet
        - **Negative EV (-EV)**: Long-term losing bet
        - **Model IP**: Your model's calculated probability
        - **Implied IP**: Sportsbook's implied probability (from odds)
        - **Edge**: Difference between model IP and implied IP
        - **Units**: Recommended bet size (Kelly Criterion, fractional)
        
        **How to use:**
        1. Set minimum EV threshold (default 5%)
        2. Select stat type
        3. Click "Find EV+ Bets"
        4. Review bets sorted by EV
        5. Bet sizes are calculated using fractional Kelly (25% of full Kelly)
        """)

