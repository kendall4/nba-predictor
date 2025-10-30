import streamlit as st
from src.analysis.hot_hand_tracker import HotHandTracker

def render(predictions, games):
    st.header("🔥 Hot Hand Tracker")
    player_list = predictions['player_name'].unique().tolist()
    selected_player = st.selectbox("Select Player", options=player_list)
    q1 = st.number_input("Q1 Points", min_value=0.0, max_value=40.0, value=10.0, step=1.0)
    threshold = st.select_slider("Hot threshold", options=[5, 10], value=5)
    if st.button("Estimate Hot-Hand Outcome", use_container_width=True):
        tracker = HotHandTracker(blend_mode="latest")
        result = tracker.predict_from_hot_q1(selected_player, q1, threshold=int(threshold))
        st.write(result)


