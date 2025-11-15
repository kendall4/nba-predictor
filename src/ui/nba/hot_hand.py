import streamlit as st
from src.analysis.hot_hand_tracker import HotHandTracker

def render(predictions, games):
    st.header("🔥 Hot Hand Tracker")
    st.caption("Predict final game totals based on Q1 performance")
    
    player_list = predictions['player_name'].unique().tolist()
    selected_player = st.selectbox("Select Player", options=player_list)
    
    # Stat type selection
    stat_type = st.selectbox(
        "Stat Type",
        options=['points', 'rebounds', 'assists'],
        format_func=lambda x: x.capitalize()
    )
    
    # Dynamic input based on stat type
    if stat_type == 'points':
        q1_value = st.number_input("Q1 Points", min_value=0.0, max_value=40.0, value=10.0, step=1.0)
        threshold_options = [5, 10, 15]
        default_threshold = 5
    elif stat_type == 'rebounds':
        q1_value = st.number_input("Q1 Rebounds", min_value=0.0, max_value=15.0, value=4.0, step=0.5)
        threshold_options = [3, 5, 7]
        default_threshold = 3
    else:  # assists
        q1_value = st.number_input("Q1 Assists", min_value=0.0, max_value=12.0, value=3.0, step=0.5)
        threshold_options = [2, 4, 6]
        default_threshold = 2
    
    threshold = st.select_slider("Hot threshold", options=threshold_options, value=default_threshold)
    
    if st.button("Estimate Hot-Hand Outcome", use_container_width=True):
        tracker = HotHandTracker(blend_mode="latest")
        result = tracker.predict_from_hot_q1(
            selected_player, 
            q1_value, 
            stat_type=stat_type,
            threshold=float(threshold)
        )
        
        if 'error' in result:
            st.error(result['error'])
            if 'note' in result:
                st.caption(result['note'])
        elif 'note' in result:
            st.warning(result['note'])
        else:
            # Display results in a nice format
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Q1 Actual", f"{result['q1_actual']:.1f}")
                st.caption(f"Threshold: {result['threshold']}")
            
            with col2:
                st.metric("Predicted Total", f"{result['predicted_total']:.1f}")
                st.caption(f"Season Avg: {result['season_average']:.1f}")
            
            with col3:
                vs_avg = result['vs_average']
                delta_color = "normal" if vs_avg >= 0 else "inverse"
                st.metric("Vs Average", f"{vs_avg:+.1f}", delta=f"{vs_avg:+.1f}")
                st.caption(f"Confidence: {result['confidence']}")
            
            st.markdown("---")
            st.markdown(f"**Archetype:** {result['archetype']}")
            st.markdown(f"**Consistency Score:** {result['consistency_score']:.2f}")
            
            # Quarter-by-quarter breakdown
            st.markdown("#### 📊 Quarter-by-Quarter Prediction")
            quarters_data = {
                'Q1': result['q1_actual'],
                'Q2': result['predicted_q2'],
                'Q3': result['predicted_q3'],
                'Q4': result['predicted_q4']
            }
            
            cols = st.columns(4)
            for i, (q, val) in enumerate(quarters_data.items()):
                with cols[i]:
                    st.metric(q, f"{val:.1f}")


