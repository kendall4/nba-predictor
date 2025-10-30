import streamlit as st
import pandas as pd
from src.analysis.live_sgp_analyzer import LiveSGPAnalyzer

def render():
    st.header("🎰 Live SGP Analyzer")
    st.caption("Enter legs (demo) — integrate live data feed later.")
    legs_df = st.data_editor(pd.DataFrame([
        {"player":"Player A","stat":"points","line":20,"current":14},
        {"player":"Player B","stat":"rebounds","line":8,"current":6}
    ]), num_rows="dynamic", use_container_width=True)
    time_left = st.number_input("Time left (seconds)", min_value=0, max_value=3600, value=240, step=10)
    odds = st.number_input("Parlay odds (American)", value=10000, step=100)
    if st.button("Analyze Parlay", use_container_width=True):
        sgp = LiveSGPAnalyzer()
        analysis = sgp.analyze_parlay(legs=legs_df.to_dict('records'), time_left_seconds=int(time_left), odds=int(odds))
        sgp.display_analysis(analysis)


