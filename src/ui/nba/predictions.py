import streamlit as st

def render(predictions):
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
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    csv = predictions.to_csv(index=False)
    st.download_button("📥 Download Full Predictions (CSV)", csv, "nba_predictions.csv", "text/csv", use_container_width=True)


