"""
Bet Generator - Mainline & Longshot Model
==========================================
Generates betting recommendations with EV, Fair Value, and unit sizing.
Outputs both mainline (conservative) and longshot (high-odds) options.
"""

import pandas as pd
import numpy as np
from scipy.stats import norm
from typing import Dict, List, Optional, Tuple
from src.services.odds_aggregator import OddsAggregator
from src.analysis.alt_line_optimizer import AltLineOptimizer
import os


class BetGenerator:
    """
    Generate betting recommendations with EV calculations
    
    Output format similar to:
    Player Over/Under Line Odds (units - FV: fair_value_odds) @ Sportsbook
    Player Over Line (odds - FV fair_value): EV=X.XX
    """
    
    def __init__(self, odds_api_key: Optional[str] = None):
        self.odds_aggregator = OddsAggregator(api_key=odds_api_key)
        self.optimizer = AltLineOptimizer()
        self.mainline_threshold = +200  # Mainline: odds <= +200
        self.longshot_threshold = +500  # Longshot: odds >= +500
    
    def calculate_fair_value_odds(self, probability: float) -> int:
        """
        Calculate fair value odds (American format) from probability
        
        Args:
            probability: True probability (0-1)
        
        Returns:
            Fair value odds in American format
        """
        if probability >= 1.0:
            return -10000  # Very high probability
        if probability <= 0.0:
            return +10000  # Very low probability
        
        # Convert probability to American odds
        if probability >= 0.5:
            # Favorite (negative odds)
            american_odds = int(-100 * probability / (1 - probability))
            # Round to nearest 5
            return int(round(american_odds / 5) * 5)
        else:
            # Underdog (positive odds)
            american_odds = int((100 * (1 - probability)) / probability)
            # Round to nearest 5
            return int(round(american_odds / 5) * 5)
    
    def kelly_criterion_unit(self, probability: float, odds: int, bankroll_fraction: float = 0.25) -> float:
        """
        Calculate Kelly Criterion bet size (fractional Kelly)
        
        Args:
            probability: True probability
            odds: American odds
            bankroll_fraction: Fraction of full Kelly (0.25 = quarter Kelly, safer)
        
        Returns:
            Unit size (0-1+)
        """
        if probability <= 0 or probability >= 1:
            return 0.0
        
        # Convert American odds to decimal
        if odds > 0:
            decimal_odds = (odds / 100) + 1
        else:
            decimal_odds = (100 / abs(odds)) + 1
        
        # Kelly formula: f = (p * b - q) / b
        # where p = probability, b = odds-1, q = 1-p
        b = decimal_odds - 1
        q = 1 - probability
        
        # Full Kelly
        full_kelly = (probability * b - q) / b
        
        # Only bet if positive
        if full_kelly <= 0:
            return 0.0
        
        # Apply fractional Kelly (safer)
        fractional_kelly = full_kelly * bankroll_fraction
        
        # Cap at reasonable maximum (3 units)
        return min(fractional_kelly, 3.0)
    
    def calculate_std_dev(self, prediction: float, stat_type: str) -> float:
        """
        Estimate standard deviation for a stat prediction
        Based on historical variance patterns
        """
        # Base std dev as percentage of prediction
        base_pct = {
            'points': 0.20,      # Points: 20% variance
            'rebounds': 0.25,    # Rebounds: 25% variance
            'assists': 0.30,     # Assists: 30% variance
            'threes': 0.35,      # Threes: 35% variance (most variable)
            'steals': 0.40,
            'blocks': 0.45
        }
        
        pct = base_pct.get(stat_type.lower(), 0.25)
        return prediction * pct
    
    def analyze_bet(self, player_name: str, stat_type: str, prediction: float,
                   line: float, odds: int, direction: str, book: str) -> Dict:
        """
        Analyze a single bet option
        
        Returns dict with EV, FV, units, etc.
        """
        # Calculate probability
        if direction.lower() == 'over':
            prob = self.optimizer.calculate_probability_over(
                prediction, line,
                std_dev=self.calculate_std_dev(prediction, stat_type)
            )
        else:
            prob = 1 - self.optimizer.calculate_probability_over(
                prediction, line,
                std_dev=self.calculate_std_dev(prediction, stat_type)
            )
        
        # Calculate EV
        ev = self.optimizer.calculate_ev(prob, odds)
        
        # Calculate Fair Value odds
        fv_odds = self.calculate_fair_value_odds(prob)
        
        # Calculate unit size (Kelly)
        units = self.kelly_criterion_unit(prob, odds, bankroll_fraction=0.25)
        
        # Categorize
        is_mainline = odds <= self.mainline_threshold
        is_longshot = odds >= self.longshot_threshold
        
        return {
            'player': player_name,
            'stat': stat_type,
            'direction': direction.upper(),
            'line': line,
            'odds': odds,
            'probability': prob,
            'ev': ev,
            'fv_odds': fv_odds,
            'units': units,
            'book': book,
            'prediction': prediction,
            'is_mainline': is_mainline,
            'is_longshot': is_longshot
        }
    
    def generate_all_bets(self, predictions: pd.DataFrame, 
                         stat_type: str = 'points',
                         min_ev: float = 0.0,
                         include_negative_ev: bool = False) -> pd.DataFrame:
        """
        Generate all betting options from predictions and odds
        
        Args:
            predictions: DataFrame with columns: player_name, pred_points, pred_rebounds, etc.
            stat_type: 'points', 'rebounds', 'assists', etc.
            min_ev: Minimum EV to include
            include_negative_ev: Whether to include negative EV bets
        
        Returns:
            DataFrame with all analyzed bets
        """
        # Get prediction column name
        pred_col = f'pred_{stat_type}'
        if pred_col not in predictions.columns:
            print(f"⚠️  No predictions found for {stat_type}")
            return pd.DataFrame()
        
        # Get odds for all players
        print("📊 Fetching odds from sportsbooks...")
        all_odds = self.odds_aggregator.get_player_props(debug=False)
        
        if all_odds is None or len(all_odds) == 0:
            print("⚠️  No odds data available")
            return pd.DataFrame()
        
        # Filter by stat type
        stat_filtered = all_odds[
            all_odds['stat'].str.contains(stat_type.lower(), case=False, na=False)
        ]
        
        if len(stat_filtered) == 0:
            print(f"⚠️  No {stat_type} odds found")
            return pd.DataFrame()
        
        # Analyze each bet
        results = []
        for _, player_row in predictions.iterrows():
            player_name = player_row['player_name']
            prediction = float(player_row[pred_col])
            
            # Find matching odds
            player_odds = stat_filtered[
                stat_filtered['player'].str.contains(player_name, case=False, na=False)
            ]
            
            if len(player_odds) == 0:
                continue
            
            # Analyze both over and under for each line
            for _, odds_row in player_odds.iterrows():
                line = float(odds_row['line'])
                book = odds_row['book']
                
                # Analyze OVER
                if pd.notna(odds_row.get('over_odds')):
                    over_odds = int(odds_row['over_odds'])
                    bet_analysis = self.analyze_bet(
                        player_name, stat_type, prediction,
                        line, over_odds, 'over', book
                    )
                    if bet_analysis['ev'] >= min_ev or include_negative_ev:
                        results.append(bet_analysis)
                
                # Analyze UNDER
                if pd.notna(odds_row.get('under_odds')):
                    under_odds = int(odds_row['under_odds'])
                    bet_analysis = self.analyze_bet(
                        player_name, stat_type, prediction,
                        line, under_odds, 'under', book
                    )
                    if bet_analysis['ev'] >= min_ev or include_negative_ev:
                        results.append(bet_analysis)
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        return df.sort_values('ev', ascending=False)
    
    def format_bet_line(self, bet: Dict, format_style: str = 'detailed') -> str:
        """
        Format a bet for output
        
        Formats:
        - 'detailed': Player Over Line Odds (units - FV: fv_odds) @ Book
        - 'ev': Player Over Line (odds - FV fv_odds): EV=X.XX
        - 'simple': Player Over Line Odds (units) @ Book
        """
        player = bet['player']
        direction = bet['direction']
        line = bet['line']
        odds = bet['odds']
        units = bet['units']
        fv_odds = bet['fv_odds']
        book = bet['book']
        ev = bet['ev']
        stat = bet['stat'].capitalize()
        
        if format_style == 'detailed':
            odds_str = f"+{odds}" if odds > 0 else str(odds)
            fv_str = f"+{fv_odds}" if fv_odds > 0 else str(fv_odds)
            return f"{player} {direction} {line} {stat} {odds_str} ({units:.2f}u - FV: {fv_str}) @ {book.upper()}"
        
        elif format_style == 'ev':
            odds_str = f"{odds}" if odds < 0 else f"+{odds}"
            fv_str = f"{fv_odds}" if fv_odds < 0 else f"+{fv_odds}"
            return f"{player} {direction} {line} {stat} ({odds_str} - FV {fv_str}): EV={ev:.2f}"
        
        else:  # simple
            odds_str = f"+{odds}" if odds > 0 else str(odds)
            return f"{player} {direction} {line} {stat} {odds_str} ({units:.2f}u) @ {book.upper()}"
    
    def print_bets(self, bets_df: pd.DataFrame, 
                   separate_mainline_longshot: bool = True,
                   min_ev: float = 0.0,
                   max_display: int = 50):
        """
        Print bets in formatted output
        
        Args:
            bets_df: DataFrame of analyzed bets
            separate_mainline_longshot: If True, separate mainline and longshot sections
            min_ev: Minimum EV to display
            max_display: Maximum number of bets to show
        """
        if bets_df is None or len(bets_df) == 0:
            print("⚠️  No bets to display")
            return
        
        # Filter by min EV
        filtered = bets_df[bets_df['ev'] >= min_ev].head(max_display)
        
        if len(filtered) == 0:
            print(f"⚠️  No bets with EV >= {min_ev}")
            return
        
        if separate_mainline_longshot:
            # Separate mainline and longshot
            mainline = filtered[filtered['is_mainline']]
            longshot = filtered[filtered['is_longshot']]
            
            if len(mainline) > 0:
                print("\n" + "=" * 80)
                print("📊 MAINLINE OPTIONS (Odds <= +200)")
                print("=" * 80)
                for _, bet in mainline.iterrows():
                    print(self.format_bet_line(bet, format_style='detailed'))
            
            if len(longshot) > 0:
                print("\n" + "=" * 80)
                print("🚀 LONGSHOT OPTIONS (Odds >= +500)")
                print("=" * 80)
                for _, bet in longshot.iterrows():
                    print(self.format_bet_line(bet, format_style='detailed'))
            
            # Show middle options if any
            middle = filtered[(~filtered['is_mainline']) & (~filtered['is_longshot'])]
            if len(middle) > 0:
                print("\n" + "=" * 80)
                print("📈 MID-RANGE OPTIONS (+200 < Odds < +500)")
                print("=" * 80)
                for _, bet in middle.iterrows():
                    print(self.format_bet_line(bet, format_style='detailed'))
        else:
            # Single sorted list
            print("\n" + "=" * 80)
            print("📊 ALL BETS (Sorted by EV)")
            print("=" * 80)
            for _, bet in filtered.iterrows():
                print(self.format_bet_line(bet, format_style='detailed'))
        
        print("\n" + "=" * 80)
        print(f"✅ Total bets displayed: {len(filtered)}")
        print(f"   Mainline: {len(filtered[filtered['is_mainline']])}")
        print(f"   Longshots: {len(filtered[filtered['is_longshot']])}")
        print(f"   Average EV: {filtered['ev'].mean():.3f}")
        print("=" * 80)


if __name__ == "__main__":
    # Example usage
    print("=" * 80)
    print("🎯 BET GENERATOR - Mainline & Longshot Model")
    print("=" * 80)
    
    # Load predictions (example)
    try:
        predictions = pd.read_csv('predictions_today.csv')
        print(f"✅ Loaded {len(predictions)} player predictions")
    except FileNotFoundError:
        print("⚠️  No predictions file found. Create predictions first.")
        exit(1)
    
    # Initialize generator
    api_key = os.getenv('ODDS_API_KEY')
    generator = BetGenerator(odds_api_key=api_key)
    
    # Generate bets for points
    print("\n📊 Generating bets for POINTS...")
    points_bets = generator.generate_all_bets(
        predictions,
        stat_type='points',
        min_ev=-0.05,  # Include slight negative EV for completeness
        include_negative_ev=False  # Only show positive or near-zero EV
    )
    
    if len(points_bets) > 0:
        generator.print_bets(
            points_bets,
            separate_mainline_longshot=True,
            min_ev=0.0,
            max_display=100
        )
    else:
        print("⚠️  No bets generated. Check predictions and odds availability.")

