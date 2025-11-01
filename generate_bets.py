#!/usr/bin/env python3
"""
Quick Bet Generator Script
==========================
Run this to generate mainline and longshot betting recommendations.

Usage:
    python generate_bets.py [stat_type] [min_ev]
    
Examples:
    python generate_bets.py points 0.0
    python generate_bets.py rebounds 0.05
    python generate_bets.py assists -0.02
"""

import sys
import os
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from src.analysis.bet_generator import BetGenerator
from src.features.matchup_features import MatchupFeatureBuilder
from nba_api.live.nba.endpoints import scoreboard

def get_todays_games():
    """Get today's NBA games with timeout handling"""
    max_retries = 1
    import time
    for attempt in range(max_retries + 1):
        try:
            board = scoreboard.ScoreBoard()
            games = board.games.get_dict()
            
            game_list = []
            for game in games:
                game_list.append({
                    'home': game['homeTeam']['teamTricode'],
                    'away': game['awayTeam']['teamTricode'],
                    'status': game['gameStatusText']
                })
            
            return game_list if len(game_list) > 0 else None
        except Exception as e:
            if attempt >= max_retries:
                print(f"⚠️  Error fetching games: {e}")
                return None
            time.sleep(0.5)  # Quick retry delay

def main():
    # Parse arguments
    stat_type = sys.argv[1] if len(sys.argv) > 1 else 'points'
    min_ev = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    
    print("=" * 80)
    print(f"🎯 BET GENERATOR - {stat_type.upper()} PROPS")
    print("=" * 80)
    
    # Get today's games
    print("\n📅 Fetching today's games...")
    games = get_todays_games()
    
    if games is None or len(games) == 0:
        print("⚠️  No games found today. Using fallback games.")
        games = [
            {'home': 'LAL', 'away': 'GSW', 'status': 'Example'},
            {'home': 'BOS', 'away': 'MIA', 'status': 'Example'}
        ]
    
    print(f"✅ Found {len(games)} games today")
    for game in games:
        print(f"   {game['away']} @ {game['home']}")
    
    # Generate predictions
    print(f"\n🤖 Generating predictions for {stat_type}...")
    builder = MatchupFeatureBuilder()
    predictions = builder.get_all_matchups(games)
    
    if predictions is None or len(predictions) == 0:
        print("❌ Failed to generate predictions")
        return
    
    print(f"✅ Generated predictions for {len(predictions)} players")
    
    # Check for prediction column
    pred_col = f'pred_{stat_type}'
    if pred_col not in predictions.columns:
        print(f"❌ No predictions available for {stat_type}")
        print(f"   Available columns: {predictions.columns.tolist()}")
        return
    
    # Filter to players with predictions
    predictions = predictions[pd.notna(predictions[pred_col])]
    print(f"✅ {len(predictions)} players with {stat_type} predictions")
    
    # Initialize bet generator
    print(f"\n💰 Initializing bet generator...")
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        print("⚠️  ODDS_API_KEY not set. Will use mock odds if available.")
        print("   Set it with: export ODDS_API_KEY=your_key_here")
    
    generator = BetGenerator(odds_api_key=api_key)
    
    # Generate bets
    print(f"\n📊 Generating betting recommendations...")
    bets_df = generator.generate_all_bets(
        predictions,
        stat_type=stat_type,
        min_ev=min_ev - 0.01,  # Slightly lower threshold, filter later
        include_negative_ev=False
    )
    
    if bets_df is None or len(bets_df) == 0:
        print("⚠️  No bets generated.")
        print("   Possible reasons:")
        print("   - No odds available from sportsbooks")
        print("   - No matching player names between predictions and odds")
        print("   - All bets have negative EV")
        return
    
    print(f"✅ Generated {len(bets_df)} betting options")
    
    # Display results
    generator.print_bets(
        bets_df,
        separate_mainline_longshot=True,
        min_ev=min_ev,
        max_display=200  # Show up to 200 bets
    )
    
    # Save to CSV
    output_file = f'bets_{stat_type}_{pd.Timestamp.now().strftime("%Y%m%d")}.csv'
    bets_df.to_csv(output_file, index=False)
    print(f"\n💾 Saved all bets to: {output_file}")

if __name__ == "__main__":
    main()

