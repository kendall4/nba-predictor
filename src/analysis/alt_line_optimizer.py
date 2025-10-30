import pandas as pd
import numpy as np
from scipy.stats import norm

class AltLineOptimizer:
    """
    Find best value across DraftKings alternate lines
    Compare EV of main line vs alt lines
    """
    
    def __init__(self):
        print("✅ Alt Line Optimizer ready")
    
    def american_to_decimal(self, american_odds):
        """Convert American odds to decimal"""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    
    def american_to_implied_prob(self, american_odds):
        """Convert American odds to implied probability"""
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)
    
    def calculate_probability_over(self, prediction, line, std_dev=None):
        """
        Calculate probability prediction is OVER the line
        Using normal distribution assumption
        
        std_dev: standard deviation (use ~20% of prediction if unknown)
        """
        if std_dev is None:
            std_dev = prediction * 0.20  # Assume 20% variance
        
        # Z-score
        z = (line - prediction) / std_dev
        
        # Probability of being over the line
        prob_over = 1 - norm.cdf(z)
        
        return prob_over
    
    def calculate_ev(self, probability, american_odds):
        """Calculate expected value"""
        decimal_odds = self.american_to_decimal(american_odds)
        
        # EV = (Probability × Payout) - (1 - Probability) × Stake
        # For $1 bet:
        ev = (probability * (decimal_odds - 1)) - (1 - probability)
        
        return ev
    
    def optimize_lines(self, player_name, stat_type, prediction, alt_lines):
        """
        Find the alt line with best expected value
        
        alt_lines = [
            {'line': 15.5, 'over': -110, 'under': -110},
            {'line': 17.5, 'over': +150, 'under': -190},
            {'line': 19.5, 'over': +250, 'under': -350},
        ]
        """
        
        results = []
        
        for line_info in alt_lines:
            line = line_info['line']
            over_odds = line_info['over']
            under_odds = line_info['under']
            
            # Probability of going OVER
            prob_over = self.calculate_probability_over(prediction, line)
            prob_under = 1 - prob_over
            
            # Expected value for each direction
            ev_over = self.calculate_ev(prob_over, over_odds)
            ev_under = self.calculate_ev(prob_under, under_odds)
            
            # Which direction is better?
            if ev_over > ev_under:
                best_direction = 'OVER'
                best_ev = ev_over
                best_odds = over_odds
                best_prob = prob_over
            else:
                best_direction = 'UNDER'
                best_ev = ev_under
                best_odds = under_odds
                best_prob = prob_under
            
            results.append({
                'line': line,
                'direction': best_direction,
                'odds': best_odds,
                'probability': best_prob,
                'ev': best_ev,
                'ev_percent': ev_over * 100
            })
        
        # Sort by EV
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('ev', ascending=False)
        
        best = results_df.iloc[0]
        
        return {
            'player': player_name,
            'stat': stat_type,
            'prediction': prediction,
            'all_lines': results_df,
            'best_line': best['line'],
            'best_direction': best['direction'],
            'best_odds': best['odds'],
            'best_probability': best['probability'],
            'best_ev': best['ev']
        }
    
    def display_optimization(self, result):
        """Pretty print the results"""
        
        print("\n" + "=" * 70)
        print(f"💎 ALT LINE OPTIMIZER - {result['player']}")
        print("=" * 70)
        
        print(f"\n🎯 AI Prediction: {result['prediction']:.1f} {result['stat']}")
        
        print(f"\n📊 ALL AVAILABLE LINES:\n")
        
        for _, line in result['all_lines'].iterrows():
            ev_color = "✅" if line['ev'] > 0.1 else "⚠️" if line['ev'] > 0 else "❌"
            
            print(f"{ev_color} {line['direction']} {line['line']}")
            print(f"   Odds: {line['odds']:+d}")
            print(f"   Probability: {line['probability']:.1%}")
            print(f"   Expected Value: {line['ev']:+.1%}")
            print()
        
        print("=" * 70)
        print(f"🔥 BEST VALUE:")
        print(f"   {result['best_direction']} {result['best_line']} at {result['best_odds']:+d}")
        print(f"   Probability: {result['best_probability']:.1%}")
        print(f"   Expected Value: {result['best_ev']:+.1%}")
        
        if result['best_ev'] > 0.15:
            print(f"\n💰 STRONG BET - Great value!")
        elif result['best_ev'] > 0.05:
            print(f"\n💵 DECENT BET - Positive EV")
        elif result['best_ev'] > 0:
            print(f"\n⚠️ SLIGHT EDGE - Small positive EV")
        else:
            print(f"\n❌ NO VALUE - Skip this one")
        
        print("=" * 70)


# Test it
if __name__ == "__main__":
    print("=" * 70)
    print("💎 DRAFTKINGS ALT LINE OPTIMIZER - Testing")
    print("=" * 70)
    
    optimizer = AltLineOptimizer()
    
    # Example: Anfernee Simons points
    print("\n📝 Example: Anfernee Simons - Points")
    
    # Your model predicts 18.2 points
    # DraftKings has these lines:
    alt_lines = [
        {'line': 14.5, 'over': -150, 'under': +120},
        {'line': 16.5, 'over': -110, 'under': -110},  # Main line
        {'line': 18.5, 'over': +120, 'under': -150},
        {'line': 20.5, 'over': +200, 'under': -260},
        {'line': 22.5, 'over': +320, 'under': -450},
    ]
    
    result = optimizer.optimize_lines(
        player_name='Anfernee Simons',
        stat_type='points',
        prediction=18.2,
        alt_lines=alt_lines
    )
    
    optimizer.display_optimization(result)
    
    print("\n💡 Interpretation:")
    print("   The optimizer found which line gives you the best")
    print("   risk/reward ratio based on your AI prediction!")