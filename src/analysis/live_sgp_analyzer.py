import pandas as pd
import numpy as np
from scipy.stats import poisson

class LiveSGPAnalyzer:
    """
    Analyze live Same Game Parlays
    Calculate probability each leg hits
    Find expected value vs odds
    """
    
    def __init__(self):
        p1 = pd.read_csv('data/raw/player_stats_2024-25.csv'); p1['SEASON'] = '2024-25'
        p2 = pd.read_csv('data/raw/player_stats_2025-26.csv'); p2['SEASON'] = '2025-26'
        self.players = pd.concat([p1, p2], ignore_index=True).sort_values('SEASON').drop_duplicates(subset=['PLAYER_ID'], keep='last')
        print("✅ Live SGP Analyzer ready (latest season baselines)")
    
    def get_player_rate(self, player_name, stat_type):
        """
        Get player's per-minute rate for a stat
        stat_type: 'points', 'rebounds', 'assists', 'threes'
        """
        player = self.players[self.players['PLAYER_NAME'] == player_name]
        
        if len(player) == 0:
            return None
        
        player = player.iloc[0]
        
        # Calculate per-minute rates
        minutes = player['MIN']
        
        if stat_type == 'points':
            return player['PTS'] / minutes if minutes > 0 else 0
        elif stat_type == 'rebounds':
            return player['REB'] / minutes if minutes > 0 else 0
        elif stat_type == 'assists':
            return player['AST'] / minutes if minutes > 0 else 0
        elif stat_type == 'threes':
            return player.get('FG3M', 0) / minutes if minutes > 0 else 0
        
        return 0
    
    def poisson_probability(self, expected, need_more):
        """
        Calculate probability of getting AT LEAST 'need_more' 
        given expected value using Poisson distribution
        """
        if need_more <= 0:
            return 1.0  # Already hit
        
        # P(X >= k) = 1 - P(X < k) = 1 - P(X <= k-1)
        prob = 1 - poisson.cdf(need_more - 1, expected)
        return prob
    
    def analyze_leg(self, player_name, stat_type, line, current_value, time_left_seconds):
        """
        Analyze single parlay leg
        
        Returns: {
            'player': name,
            'stat': stat_type,
            'line': threshold,
            'current': current value,
            'needed': how many more,
            'probability': chance of hitting,
            'confidence': HIGH/MEDIUM/LOW
        }
        """
        
        # How many more needed?
        needed = line - current_value
        
        if needed <= 0:
            return {
                'player': player_name,
                'stat': stat_type,
                'line': line,
                'current': current_value,
                'needed': 0,
                'probability': 1.0,
                'status': '✅ ALREADY HIT',
                'confidence': 'LOCKED'
            }
        
        # Get player's rate for this stat
        rate_per_min = self.get_player_rate(player_name, stat_type)
        
        if rate_per_min is None:
            return None
        
        # Calculate expected value in remaining time
        minutes_left = time_left_seconds / 60
        expected = rate_per_min * minutes_left
        
        # Calculate probability using Poisson
        probability = self.poisson_probability(expected, needed)
        
        # Confidence levels
        if probability >= 0.7:
            confidence = 'HIGH'
            status = '✅'
        elif probability >= 0.4:
            confidence = 'MEDIUM'
            status = '⚠️'
        else:
            confidence = 'LOW'
            status = '❌'
        
        return {
            'player': player_name,
            'stat': stat_type,
            'line': line,
            'current': current_value,
            'needed': needed,
            'expected': expected,
            'probability': probability,
            'confidence': confidence,
            'status': status,
            'rate_per_min': rate_per_min
        }
    
    def analyze_parlay(self, legs, time_left_seconds, odds):
        """
        Analyze entire SGP
        
        legs = [
            {'player': 'Draymond Green', 'stat': 'rebounds', 'line': 10, 'current': 7},
            {'player': 'Aaron Gordon', 'stat': 'rebounds', 'line': 10, 'current': 9},
            {'player': 'Al Horford', 'stat': 'threes', 'line': 4, 'current': 3},
        ]
        
        odds: +125000 (American odds format)
        time_left_seconds: 230 (3:50 remaining)
        """
        
        results = []
        probabilities = []
        
        for leg in legs:
            analysis = self.analyze_leg(
                leg['player'],
                leg['stat'],
                leg['line'],
                leg['current'],
                time_left_seconds
            )
            
            if analysis:
                results.append(analysis)
                probabilities.append(analysis['probability'])
        
        # Combined probability (all must hit)
        combined_prob = np.prod(probabilities)
        
        # Convert American odds to decimal
        if odds > 0:
            decimal_odds = (odds / 100) + 1
        else:
            decimal_odds = (100 / abs(odds)) + 1
        
        # Expected Value
        expected_value = (combined_prob * decimal_odds) - 1
        
        # Recommendation
        if expected_value > 0.2:  # 20%+ EV
            recommendation = "🔥 GREAT VALUE - LET IT RIDE!"
        elif expected_value > 0:
            recommendation = "💰 POSITIVE EV - HOLD"
        elif expected_value > -0.3:
            recommendation = "⚠️ NEUTRAL - YOUR CALL"
        else:
            recommendation = "❌ NEGATIVE EV - CONSIDER CASH OUT"
        
        return {
            'legs': results,
            'combined_probability': combined_prob,
            'odds': odds,
            'decimal_odds': decimal_odds,
            'expected_value': expected_value,
            'recommendation': recommendation,
            'time_left': time_left_seconds
        }
    
    def display_analysis(self, analysis):
        """Pretty print the analysis"""
        
        print("\n" + "=" * 70)
        print("🎰 LIVE SGP ANALYSIS")
        print("=" * 70)
        
        minutes = int(analysis['time_left'] / 60)
        seconds = int(analysis['time_left'] % 60)
        print(f"\n⏱️  Time Remaining: {minutes}:{seconds:02d}")
        print(f"💰 Odds: +{analysis['odds']}")
        
        print(f"\n📊 INDIVIDUAL LEGS:\n")
        
        for i, leg in enumerate(analysis['legs'], 1):
            print(f"{i}. {leg['player']} - {leg['stat'].upper()}")
            print(f"   Line: {leg['line']} | Current: {leg['current']} | Need: {leg['needed']}")
            print(f"   Expected in time left: {leg['expected']:.1f}")
            print(f"   {leg['status']} Probability: {leg['probability']:.1%} ({leg['confidence']})")
            print()
        
        print("=" * 70)
        print(f"🎯 COMBINED PROBABILITY: {analysis['combined_probability']:.2%}")
        print(f"💵 EXPECTED VALUE: {analysis['expected_value']:+.1%}")
        print(f"\n{analysis['recommendation']}")
        print("=" * 70)


# Test it
if __name__ == "__main__":
    print("=" * 70)
    print("🎰 LIVE SGP ANALYZER - Testing")
    print("=" * 70)
    
    analyzer = LiveSGPAnalyzer()
    
    # Your actual parlay from the game!
    print("\n📝 Example: Your Warriors/Nuggets Parlay")
    print("   Q4, 3:50 remaining, tied 117-117")
    
    legs = [
        {'player': 'Draymond Green', 'stat': 'rebounds', 'line': 10, 'current': 7},
        {'player': 'Aaron Gordon', 'stat': 'rebounds', 'line': 10, 'current': 9},
        {'player': 'Al Horford', 'stat': 'threes', 'line': 4, 'current': 3},
    ]
    
    analysis = analyzer.analyze_parlay(
        legs=legs,
        time_left_seconds=230,  # 3:50
        odds=125000  # +125000
    )
    
    analyzer.display_analysis(analysis)
    
    print("\n💡 What happened in real game:")
    print("   ❌ Draymond finished with 8 (needed 10)")
    print("   ❌ Gordon finished with 8 (needed 10)")  
    print("   ✅ Horford finished with 4 (hit it!)")
    print("   Result: Lost by 1 rebound on 2 different legs 😭")