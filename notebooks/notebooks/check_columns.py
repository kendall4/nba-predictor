import pandas as pd

print("Checking column names...\n")

pace = pd.read_csv('data/raw/team_pace_2024-25.csv')
print("PACE CSV columns:")
print(pace.columns.tolist())
print("\nFirst row:")
print(pace.head(1))

print("\n" + "="*50)

players = pd.read_csv('data/raw/player_stats_2024-25.csv')
print("\nPLAYER CSV columns:")
print(players.columns.tolist()[:20])  # First 20 columns