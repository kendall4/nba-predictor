import pandas as pd

print("=" * 60)
print("📊 EXPLORING YOUR NBA DATA")
print("=" * 60)

# Load the team pace data
pace = pd.read_csv('data/raw/team_pace_stats.csv')

print("\n🏃 FASTEST PACE TEAMS (More possessions = more scoring opportunities):")
print(pace[['TEAM_NAME', 'PACE', 'OFF_RATING', 'DEF_RATING']].sort_values('PACE', ascending=False).head(5))

print("\n🐌 SLOWEST PACE TEAMS:")
print(pace[['TEAM_NAME', 'PACE', 'OFF_RATING', 'DEF_RATING']].sort_values('PACE', ascending=True).head(5))

# Load player stats
players = pd.read_csv('data/raw/player_stats.csv')

print("\n⭐ TOP 5 SCORERS (2024-25 season):")
print(players.nlargest(5, 'PTS')[['PLAYER_NAME', 'TEAM_ABBREVIATION', 'PTS', 'REB', 'AST']])

print("\n" + "=" * 60)
print("✅ Your data looks good! Ready for next step")
print("=" * 60)