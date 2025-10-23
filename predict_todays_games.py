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