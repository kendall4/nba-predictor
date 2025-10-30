from src.features.matchup_features import MatchupFeatureBuilder
from src.analysis.value_analyzer import ValueAnalyzer
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime
import pandas as pd

print("=" * 70)
print("🏀 TODAY'S NBA PREDICTIONS - October 22, 2025")
print("=" * 70)

# Get today's actual games using live scoreboard
try:
    print("\n📅 Fetching today's games from NBA API...")
    board = scoreboard.ScoreBoard()
    games = board.games.get_dict()
    
    todays_games = []
    for game in games:
        home = game['homeTeam']['teamTricode']
        away = game['awayTeam']['teamTricode']
        home_score = game['homeTeam']['score']
        away_score = game['awayTeam']['score']
        status = game['gameStatusText']
        
        todays_games.append({
            'home': home,
            'away': away,
            'status': status
        })
        
        print(f"  {away} @ {home} - {status}")
    
    if len(todays_games) == 0:
        print("\n⚠️  No games found via API. Using example games:")
        # Fallback to games you mentioned
        todays_games = [
            {'home': 'NYK', 'away': 'BOS', 'status': 'Final'},  # Celtics won
            # Add more games happening today
        ]
        
except Exception as e:
    print(f"\n⚠️  Could not fetch live games: {e}")
    print("Using games you mentioned:")
    todays_games = [
        {'home': 'NYK', 'away': 'BOS', 'status': 'Example'},
        {'home': 'LAL', 'away': 'MIN', 'status': 'Example'},
        {'home': 'PHX', 'away': 'LAC', 'status': 'Example'},
    ]

print(f"\n✅ Found {len(todays_games)} games")

# Analyze all players
print("\n" + "=" * 70)
print("🔮 GENERATING PREDICTIONS...")
print("=" * 70)

analyzer = ValueAnalyzer()

# Get predictions for today's games
predictions = analyzer.analyze_games(todays_games)

print(f"\n✅ Generated predictions for {len(predictions)} players")

# Show top value plays
print("\n" + "=" * 70)
print("💎 TOP 20 VALUE PLAYS FOR TODAY")
print("=" * 70)

top_plays = predictions.head(20)

for i, (idx, player) in enumerate(top_plays.iterrows(), 1):
    print(f"\n{i}. {player['player_name']} ({player['team']} vs {player['opponent']})")
    print(f"   📊 Minutes: {player['minutes']:.1f} | Opp DEF: {player['opponent_def_rating']:.1f}")
    print(f"   🏃 Expected Pace: {player['expected_pace']:.1f}")
    print(f"   ")
    print(f"   🎯 PREDICTIONS:")
    print(f"      Points:   {player['pred_points']:.1f} (Season avg: {player['line_points']:.1f})")
    print(f"      Rebounds: {player['pred_rebounds']:.1f} (Season avg: {player['line_rebounds']:.1f})")
    print(f"      Assists:  {player['pred_assists']:.1f} (Season avg: {player['line_assists']:.1f})")
    
    if player['overall_value'] > 1:
        print(f"   💰 VALUE: {player['overall_value']:.1f} → BET OVER")
    elif player['overall_value'] < -1:
        print(f"   💰 VALUE: {player['overall_value']:.1f} → BET UNDER")
    else:
        print(f"   💰 VALUE: {player['overall_value']:.1f} → NEUTRAL")

# Save predictions
predictions.to_csv('predictions_today.csv', index=False)

print("\n" + "=" * 70)
print("✅ PREDICTIONS COMPLETE!")
print(f"💾 Saved to predictions_today.csv")
print("\n💡 How to use:")
print("  1. Compare predictions vs actual Vegas odds")
print("  2. High value score + weak opponent defense = GOOD BET")
print("  3. Low value score + strong opponent defense = AVOID")
print("=" * 70)

# ==============================
# Optional Tools and Diagnostics
# ==============================

USE_ALT_LINE_OPTIMIZER = True
USE_LIVE_SGP_ANALYZER = False
RUN_CONSISTENCY_CHECKS = True

from src.analysis.alt_line_optimizer import AltLineOptimizer
from src.analysis.live_sgp_analyzer import LiveSGPAnalyzer
from src.analysis.hot_hand_tracker import HotHandTracker

# ------------------------------
# Consistency checks (config)
# ------------------------------
consistency_targets = []

# Auto-fill some targets from top plays if not specified
if RUN_CONSISTENCY_CHECKS and not consistency_targets and len(predictions) > 0:
    auto_sample = predictions.head(5)
    for _, row in auto_sample.iterrows():
        consistency_targets.append({
            'player': row['player_name'],
            'stat': 'points',
            'line': float(row['line_points'])
        })

if RUN_CONSISTENCY_CHECKS and consistency_targets:
    print("\n" + "=" * 70)
    print("📈 CONSISTENCY CHECKS")
    print("=" * 70)
    tracker = HotHandTracker(blend_mode="latest")
    N_LIST = [5, 6, 7, 8, 10, 15]
    # Build quick opponent map from today's games
    opp_map = {}
    for g in todays_games:
        opp_map[g['home']] = g['away']
        opp_map[g['away']] = g['home']

    for target in consistency_targets:
        player = target['player']
        stat = target['stat']
        line = float(target['line'])
        print(f"\n— {player} | {stat} ≥ {line}")

        # last N windows
        for n in N_LIST:
            rate = tracker.consistency_last_n(player, stat, line, n=n, season='2025-26')
            print(f"  Last {n}: {rate['hits']}/{rate['games']} hit → {rate['hit_rate']:.0%}")

        # H2H vs today's opponent if known (use player's team from predictions)
        row = predictions[predictions['player_name'] == player].head(1)
        if len(row) == 1:
            team = row.iloc[0]['team']
            opp = opp_map.get(team)
            if isinstance(opp, str):
                h2h = tracker.consistency_h2h(player, stat, line, opponent_tricode=opp, season='2025-26')
                print(f"  H2H vs {opp}: {h2h['hits']}/{h2h['games']} → {h2h['hit_rate']:.0%}")

        # full season
        seas = tracker.consistency_season(player, stat, line, season='2025-26')
        print(f"  Season 2025-26: {seas['hits']}/{seas['games']} → {seas['hit_rate']:.0%}")

# ------------------------------
# Alt Line Optimizer (optional)
# ------------------------------
if USE_ALT_LINE_OPTIMIZER and len(predictions) > 0:
    print("\n" + "=" * 70)
    print("💎 ALT LINE OPTIMIZER (sample)")
    print("=" * 70)
    optimizer = AltLineOptimizer()
    sample = predictions.head(3)
    for _, p in sample.iterrows():
        base = float(p['line_points'])
        alt_lines = [
            {'line': max(0.5, base - 4.0), 'over': -160, 'under': +130},
            {'line': base - 2.0, 'over': -120, 'under': +100},
            {'line': base, 'over': -110, 'under': -110},
            {'line': base + 2.0, 'over': +120, 'under': -150},
            {'line': base + 4.0, 'over': +220, 'under': -280},
        ]
        result = optimizer.optimize_lines(
            player_name=p['player_name'],
            stat_type='points',
            prediction=float(p['pred_points']),
            alt_lines=alt_lines
        )
        optimizer.display_optimization(result)

# ------------------------------
# Live SGP Analyzer (optional)
# ------------------------------
if USE_LIVE_SGP_ANALYZER:
    print("\n" + "=" * 70)
    print("🎰 LIVE SGP ANALYZER (scaffold)")
    print("=" * 70)
    sgp = LiveSGPAnalyzer()
    legs = [
        {'player': 'Player A', 'stat': 'points', 'line': 20, 'current': 14},
        {'player': 'Player B', 'stat': 'rebounds', 'line': 8, 'current': 6},
    ]
    analysis = sgp.analyze_parlay(legs=legs, time_left_seconds=240, odds=10000)
    sgp.display_analysis(analysis)