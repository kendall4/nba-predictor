import pandas as pd
import sys
sys.path.append('src')
from features.matchup_features import MatchupFeatureBuilder

class ValueAnalyzer:
    """
    Find VALUE PLAYS:
    - Compare our predictions vs Vegas odds lines
    - Find players we predict to BEAT their over/under
    """
    
    # Cache the builder instance to avoid reloading data every time
    _builder = None
    
    def __init__(self):
        # Reuse builder instance if already created (performance optimization)
        if ValueAnalyzer._builder is None:
            ValueAnalyzer._builder = MatchupFeatureBuilder(blend_mode="latest")
        self.builder = ValueAnalyzer._builder
    
    def analyze_games(self, games_today, odds_lines=None):
        """
        Analyze all players in today's games
        
        games_today: [{'home': 'LAL', 'away': 'GSW'}, ...]
        odds_lines: {'Luka Dončić': {'points': 28.5, 'rebounds': 8.5}, ...}
        """
        
        # Get predictions for all players
        predictions = self.builder.get_all_matchups(games_today)
        
        # If no odds provided, create mock odds (season average + small variance)
        if odds_lines is None:
            print("📊 Using season averages as mock 'odds lines'")
            odds_lines = {}
            for _, player in predictions.iterrows():
                odds_lines[player['player_name']] = {
                    'points': player['season_ppg'],
                    'rebounds': player['season_rpg'],
                    'assists': player['season_apg']
                }
        
        # Calculate value scores
        values = []
        for _, player in predictions.iterrows():
            name = player['player_name']
            
            if name not in odds_lines:
                continue
            
            odds = odds_lines[name]
            
            # Calculate value: how much we predict OVER the line
            point_value = player['predicted_points'] - odds['points']
            reb_value = player['predicted_rebounds'] - odds['rebounds']
            ast_value = player['predicted_assists'] - odds['assists']
            
            # Value score (positive = we predict OVER the line)
            overall_value = (
                point_value * 2 +  # Points worth 2x
                reb_value * 1 +
                ast_value * 1.5    # Assists worth 1.5x
            )
            
            values.append({
                'player_name': name,
                'team': player['team'],
                'opponent': player['opponent'],
                
                # Predictions
                'pred_points': player['predicted_points'],
                'pred_rebounds': player['predicted_rebounds'],
                'pred_assists': player['predicted_assists'],
                
                # Lines
                'line_points': odds['points'],
                'line_rebounds': odds['rebounds'],
                'line_assists': odds['assists'],
                
                # Value (positive = bet OVER, negative = bet UNDER)
                'point_value': point_value,
                'rebound_value': reb_value,
                'assist_value': ast_value,
                'overall_value': overall_value,
                
                # Context
                'opponent_def_rating': player['opponent_def_rating'],
                'expected_pace': player['expected_pace'],
                'minutes': player['minutes']
            })
        
        return pd.DataFrame(values).sort_values('overall_value', ascending=False)
    
    def get_top_values(self, games_today, min_value=2.0, top_n=10):
        """Get the best value plays"""
        
        all_values = self.analyze_games(games_today)
        
        # Filter for significant value
        top_values = all_values[all_values['overall_value'] >= min_value].head(top_n)
        
        return top_values


# Test it
if __name__ == "__main__":
    print("=" * 70)
    print("💎 VALUE ANALYZER - Find the Best Bets!")
    print("=" * 70)
    
    analyzer = ValueAnalyzer()
    
    # Example: Lakers vs Warriors, Celtics vs Heat
    games = [
        {'home': 'LAL', 'away': 'GSW'},
        {'home': 'BOS', 'away': 'MIA'}
    ]
    
    print("\n🎯 Analyzing all players in today's games...")
    values = analyzer.get_top_values(games, min_value=0.0, top_n=10)
    
    print(f"\n💎 TOP 10 VALUE PLAYS:\n")
    print("=" * 70)
    
    for idx, player in values.iterrows():
        print(f"\n{idx+1}. {player['player_name']} ({player['team']} vs {player['opponent']})")
        print(f"   Minutes: {player['minutes']:.1f}")
        print(f"   Opponent DEF: {player['opponent_def_rating']:.1f} | Pace: {player['expected_pace']:.1f}")
        print(f"   ")
        print(f"   POINTS:  Pred {player['pred_points']:.1f} vs Line {player['line_points']:.1f} → {player['point_value']:+.1f}")
        print(f"   REBOUNDS: Pred {player['pred_rebounds']:.1f} vs Line {player['line_rebounds']:.1f} → {player['rebound_value']:+.1f}")
        print(f"   ASSISTS: Pred {player['pred_assists']:.1f} vs Line {player['line_assists']:.1f} → {player['assist_value']:+.1f}")
        print(f"   ")
        print(f"   💰 OVERALL VALUE SCORE: {player['overall_value']:.2f}")
        print(f"   {'='*66}")
    
    print("\n" + "=" * 70)
    print("✅ Value analyzer working!")
    print("\n💡 How to use:")
    print("  1. Positive value = Predict OVER the line → Bet OVER")
    print("  2. Negative value = Predict UNDER the line → Bet UNDER")
    print("  3. Higher value score = More confident play")
    print("\n🎯 Next: Apply to TODAY'S 2025-26 games!")
    print("=" * 70)