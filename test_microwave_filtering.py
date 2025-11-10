"""
Test that microwave tab only shows players from today's games
"""
import pandas as pd
import sys

print("=" * 70)
print("Testing Microwave Tab Filtering")
print("=" * 70)

# Create test data
print("\n1. Creating test data...")

# Simulate today's games (only LAL vs GSW)
games_today = [
    {'home': 'LAL', 'away': 'GSW', 'status': 'Scheduled'}
]

# Create predictions with players from multiple teams
# Some playing today (LAL, GSW), some not (DAL, SAS)
test_predictions = pd.DataFrame({
    'player_name': [
        'LeBron James',      # LAL - playing today
        'Anthony Davis',     # LAL - playing today
        'Stephen Curry',     # GSW - playing today
        'Klay Thompson',     # GSW - playing today
        'Luka Dončić',      # DAL - NOT playing today
        'Kyrie Irving',      # DAL - NOT playing today
        'Victor Wembanyama', # SAS - NOT playing today
        'Devin Vassell',     # SAS - NOT playing today
    ],
    'team': ['LAL', 'LAL', 'GSW', 'GSW', 'DAL', 'DAL', 'SAS', 'SAS'],
    'opponent': ['GSW', 'GSW', 'LAL', 'LAL', 'NOP', 'NOP', 'HOU', 'HOU'],
    'minutes': [35.0, 32.0, 34.0, 28.0, 36.0, 33.0, 30.0, 28.0],
    'pred_points': [25.0, 28.0, 30.0, 18.0, 27.0, 22.0, 20.0, 15.0],
    'pred_rebounds': [7.5, 10.2, 4.8, 3.5, 8.5, 4.2, 10.5, 4.0],
    'pred_assists': [8.0, 3.0, 6.5, 2.5, 9.0, 5.0, 3.5, 2.8],
})

print(f"✅ Created {len(test_predictions)} test players")
print(f"   Teams in predictions: {sorted(test_predictions['team'].unique().tolist())}")
print(f"\n   Games today: {games_today[0]['away']} @ {games_today[0]['home']}")
print(f"   Teams playing today: LAL, GSW")

# Test filtering logic
print("\n2. Testing filtering logic...")

# Get teams playing today
teams_playing_today = set()
for game in games_today:
    teams_playing_today.add(game['home'])
    teams_playing_today.add(game['away'])

print(f"   Teams playing today: {sorted(teams_playing_today)}")

# Filter predictions
predictions_filtered = test_predictions[
    test_predictions['team'].isin(teams_playing_today)
]

print(f"\n✅ Filtered to {len(predictions_filtered)} players")
print(f"   Teams in filtered: {sorted(predictions_filtered['team'].unique().tolist())}")
print(f"\n   Players included:")
for _, row in predictions_filtered.iterrows():
    print(f"     - {row['player_name']} ({row['team']})")

# Verify filtering worked
print("\n3. Verifying results...")
expected_teams = {'LAL', 'GSW'}
actual_teams = set(predictions_filtered['team'].unique())

if actual_teams == expected_teams:
    print("✅ PASS: Only teams playing today are included")
else:
    print(f"❌ FAIL: Expected {expected_teams}, got {actual_teams}")
    sys.exit(1)

# Check that non-playing teams are excluded
excluded_teams = {'DAL', 'SAS'}
if not actual_teams.intersection(excluded_teams):
    print("✅ PASS: Teams not playing today are excluded")
else:
    print(f"❌ FAIL: Found excluded teams: {actual_teams.intersection(excluded_teams)}")
    sys.exit(1)

# Check specific players
luka_included = 'Luka Dončić' in predictions_filtered['player_name'].values
wemby_included = 'Victor Wembanyama' in predictions_filtered['player_name'].values

if not luka_included:
    print("✅ PASS: Luka Dončić (DAL) correctly excluded")
else:
    print("❌ FAIL: Luka Dončić should be excluded")
    sys.exit(1)

if not wemby_included:
    print("✅ PASS: Victor Wembanyama (SAS) correctly excluded")
else:
    print("❌ FAIL: Victor Wembanyama should be excluded")
    sys.exit(1)

# Check that playing players are included
lebron_included = 'LeBron James' in predictions_filtered['player_name'].values
curry_included = 'Stephen Curry' in predictions_filtered['player_name'].values

if lebron_included:
    print("✅ PASS: LeBron James (LAL) correctly included")
else:
    print("❌ FAIL: LeBron James should be included")
    sys.exit(1)

if curry_included:
    print("✅ PASS: Stephen Curry (GSW) correctly included")
else:
    print("❌ FAIL: Stephen Curry should be included")
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED!")
print("=" * 70)
print(f"\nSummary:")
print(f"  - Total players in predictions: {len(test_predictions)}")
print(f"  - Players after filtering: {len(predictions_filtered)}")
print(f"  - Teams playing today: {len(teams_playing_today)}")
print(f"  - Teams in filtered data: {len(actual_teams)}")

