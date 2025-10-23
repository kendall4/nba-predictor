import pandas as pd

print("=" * 70)
print("📊 EXPLORING 2024-25 TRAINING DATA")
print("=" * 70)

# Load all the data
games = pd.read_csv('data/raw/games_2024-25.csv')
pace = pd.read_csv('data/raw/team_pace_2024-25.csv')
players = pd.read_csv('data/raw/player_stats_2024-25.csv')

print(f"\n📈 DATA SUMMARY:")
print(f"  Total games: {len(games):,}")
print(f"  Total players: {len(players):,}")
print(f"  Teams: {len(pace)}")

print(f"\n🏃 PACE INSIGHTS:")
fastest = pace.nlargest(1, 'PACE')[['TEAM_NAME', 'PACE']].iloc[0]
slowest = pace.nsmallest(1, 'PACE')[['TEAM_NAME', 'PACE']].iloc[0]
print(f"  Fastest: {fastest['TEAM_NAME']} ({fastest['PACE']:.1f} possessions/48min)")
print(f"  Slowest: {slowest['TEAM_NAME']} ({slowest['PACE']:.1f} possessions/48min)")
print(f"  Difference: {fastest['PACE'] - slowest['PACE']:.1f} more possessions per game!")

print(f"\n🛡️  DEFENSE INSIGHTS:")
best_def = pace.nsmallest(1, 'DEF_RATING')[['TEAM_NAME', 'DEF_RATING']].iloc[0]
worst_def = pace.nlargest(1, 'DEF_RATING')[['TEAM_NAME', 'DEF_RATING']].iloc[0]
print(f"  Best defense: {best_def['TEAM_NAME']} ({best_def['DEF_RATING']:.1f} rating)")
print(f"  Worst defense: {worst_def['TEAM_NAME']} ({worst_def['DEF_RATING']:.1f} rating)")

print(f"\n⭐ TOP PERFORMERS:")
top5 = players.nlargest(5, 'PTS')[['PLAYER_NAME', 'TEAM_ABBREVIATION', 'GP', 'PTS', 'REB', 'AST']]
print(top5.to_string(index=False))

print("\n" + "=" * 70)
print("✅ You have complete training data!")
print("🎯 Next: Build features (player + opponent + pace)")
print("=" * 70)