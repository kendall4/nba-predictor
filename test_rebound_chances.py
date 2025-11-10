"""
Test script to diagnose rebound chances analyzer
"""
import pandas as pd
import sys
import traceback
from pathlib import Path

print("=" * 70)
print("Testing Rebound Chances Analyzer")
print("=" * 70)

# Test 1: Check if we can import
print("\n1. Testing imports...")
try:
    from src.services.rebound_chances_analyzer import ReboundChancesAnalyzer
    print("✅ Import successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 2: Check if data files exist
print("\n2. Checking data files...")
data_files = [
    'data/raw/team_pace_2025-26.csv',
    'data/raw/team_pace_2024-25.csv',
    'data/raw/games_2025-26.csv',
    'data/raw/games_2024-25.csv',
    'data/raw/player_stats_2025-26.csv',
    'data/raw/player_stats_2024-25.csv',
]

for file in data_files:
    exists = Path(file).exists()
    status = "✅" if exists else "❌"
    print(f"  {status} {file}")

# Test 3: Initialize analyzer
print("\n3. Initializing ReboundChancesAnalyzer...")
try:
    import time
    start_time = time.time()
    analyzer = ReboundChancesAnalyzer()
    elapsed = time.time() - start_time
    print(f"✅ Initialization successful (took {elapsed:.2f} seconds)")
    print(f"   Team stats loaded: {analyzer.team_stats is not None}")
    print(f"   Games data loaded: {analyzer.games_df is not None}")
    if analyzer.team_stats is not None:
        print(f"   Team stats shape: {analyzer.team_stats.shape}")
    if analyzer.games_df is not None:
        print(f"   Games data shape: {analyzer.games_df.shape}")
except Exception as e:
    print(f"❌ Initialization failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 4: Create sample predictions DataFrame
print("\n4. Creating sample predictions DataFrame...")
try:
    # Create minimal test data
    sample_predictions = pd.DataFrame({
        'player_name': ['LeBron James', 'Anthony Davis', 'Stephen Curry'],
        'team': ['LAL', 'LAL', 'GSW'],
        'opponent': ['GSW', 'GSW', 'LAL'],
        'minutes': [35.0, 32.0, 34.0],
        'pred_rebounds': [7.5, 10.2, 4.8],
        'line_rebounds': [7.5, 10.5, 5.5],
        'pred_points': [25.0, 28.0, 30.0],
        'pred_assists': [8.0, 3.0, 6.5],
        'overall_value': [1.5, 2.0, 1.2],
    })
    print(f"✅ Sample predictions created: {len(sample_predictions)} players")
    print("\nSample data:")
    print(sample_predictions[['player_name', 'team', 'opponent', 'minutes']])
except Exception as e:
    print(f"❌ Failed to create sample predictions: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 5: Test analyze_all_players
print("\n5. Testing analyze_all_players...")
try:
    import time
    start_time = time.time()
    print("   Calculating rebound chances (this may take a moment)...")
    rebound_df = analyzer.analyze_all_players(sample_predictions, season='2025-26')
    elapsed = time.time() - start_time
    print(f"✅ Analysis completed in {elapsed:.2f} seconds")
    
    if rebound_df is None or len(rebound_df) == 0:
        print("⚠️  Warning: No results returned")
    else:
        print(f"✅ Got results for {len(rebound_df)} players")
        print("\nResults:")
        print(rebound_df[['player_name', 'opponent', 'rebound_chances', 'reb_per_min']].head())
except Exception as e:
    print(f"❌ Analysis failed: {e}")
    traceback.print_exc()
    print("\nChecking if it's a player lookup issue...")
    # Test individual player
    try:
        print("\n6. Testing individual player calculation...")
        result = analyzer.calculate_rebound_chances('LeBron James', 'GSW', 35.0)
        if result:
            print(f"✅ Individual calculation works: {result['rebound_chances']:.1f} chances")
        else:
            print("⚠️  Individual calculation returned None")
    except Exception as e2:
        print(f"❌ Individual calculation failed: {e2}")
        traceback.print_exc()

print("\n" + "=" * 70)
print("Test complete!")
print("=" * 70)

