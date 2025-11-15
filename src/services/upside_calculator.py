"""
Upside Calculator
=================
Calculates player upside/ceiling potential beyond season averages.
Accounts for:
- Career highs and best games (what they've achieved before)
- Variance/volatility (how unpredictable they are)
- Per-minute rates (ceiling if minutes increase)
- Star status (high-usage players have more upside)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from pathlib import Path


class UpsideCalculator:
    """
    Calculate player upside potential for predictions
    """
    
    def __init__(self):
        self._upside_cache = {}  # Cache calculated upside metrics
    
    def calculate_upside_metrics(self, player_name: str, stat_type: str = 'points',
                                 cached_game_log: Optional[pd.DataFrame] = None,
                                 season_avg: float = 0.0, minutes: float = 0.0) -> Dict:
        """
        Calculate upside metrics for a player and stat type
        
        Args:
            player_name: Player name
            stat_type: 'points', 'rebounds', or 'assists'
            cached_game_log: Optional cached game log DataFrame
            season_avg: Season average for the stat
            minutes: Average minutes per game
        
        Returns:
            Dict with upside metrics and multiplier
        """
        cache_key = f"{player_name}_{stat_type}"
        if cache_key in self._upside_cache:
            return self._upside_cache[cache_key]
        
        if cached_game_log is None or len(cached_game_log) == 0:
            # No game log data - return default (no upside boost)
            return self._default_upside(season_avg, minutes, stat_type)
        
        # Map stat type to column
        stat_col_map = {
            'points': 'PTS',
            'rebounds': 'REB',
            'assists': 'AST'
        }
        
        stat_col = stat_col_map.get(stat_type, 'PTS')
        if stat_col not in cached_game_log.columns:
            return self._default_upside(season_avg, minutes, stat_type)
        
        # Filter valid games (non-null, non-zero minutes)
        valid_games = cached_game_log[
            (pd.notna(cached_game_log[stat_col])) & 
            (pd.notna(cached_game_log.get('MIN', pd.Series([1] * len(cached_game_log))))) &
            (cached_game_log.get('MIN', pd.Series([1] * len(cached_game_log))) > 0)
        ].copy()
        
        if len(valid_games) < 5:  # Need at least 5 games for meaningful stats
            return self._default_upside(season_avg, minutes, stat_type)
        
        stat_values = valid_games[stat_col].values
        minutes_values = valid_games.get('MIN', pd.Series([minutes] * len(valid_games))).values
        
        # Calculate key metrics
        career_high = float(np.max(stat_values))
        career_90th = float(np.percentile(stat_values, 90))
        career_75th = float(np.percentile(stat_values, 75))
        std_dev = float(np.std(stat_values))
        mean_value = float(np.mean(stat_values))
        
        # Per-minute rate
        per_minute_rate = mean_value / np.mean(minutes_values) if np.mean(minutes_values) > 0 else 0
        
        # Calculate upside factors
        # 1. Career high vs season avg (how much higher can they go?)
        if season_avg > 0:
            career_high_ratio = career_high / season_avg
        else:
            career_high_ratio = 1.0
        
        # 2. 90th percentile vs season avg (top 10% performance)
        if season_avg > 0:
            percentile_90_ratio = career_90th / season_avg
        else:
            percentile_90_ratio = 1.0
        
        # 3. Volatility (std dev as % of mean) - higher = more unpredictable = more upside potential
        if mean_value > 0:
            volatility = std_dev / mean_value
        else:
            volatility = 0.0
        
        # 4. Per-minute ceiling (if they get 5+ more minutes, what's possible?)
        minutes_ceiling = minutes + 5.0  # Assume 5 more minutes
        per_minute_ceiling = per_minute_rate * minutes_ceiling
        
        # Calculate upside multiplier
        # Base multiplier starts at 1.0 (no boost)
        upside_multiplier = 1.0
        
        # Factor 1: Career high potential (if they've done it before, they can do it again)
        if career_high_ratio > 1.5:  # Career high is 50%+ above season avg
            upside_multiplier += 0.08  # +8% boost
        elif career_high_ratio > 1.3:  # Career high is 30%+ above
            upside_multiplier += 0.05  # +5% boost
        elif career_high_ratio > 1.2:  # Career high is 20%+ above
            upside_multiplier += 0.03  # +3% boost
        
        # Factor 2: 90th percentile performance (top 10% games)
        if percentile_90_ratio > 1.4:  # Top games are 40%+ above avg
            upside_multiplier += 0.06  # +6% boost
        elif percentile_90_ratio > 1.25:  # Top games are 25%+ above
            upside_multiplier += 0.04  # +4% boost
        
        # Factor 3: Volatility (high variance = more upside potential)
        if volatility > 0.35:  # Very volatile (35%+ std dev)
            upside_multiplier += 0.05  # +5% boost
        elif volatility > 0.25:  # Moderately volatile
            upside_multiplier += 0.03  # +3% boost
        
        # Factor 4: Star status (high usage players have more upside)
        # Based on season averages - if they're a high scorer, they have more upside
        if stat_type == 'points':
            if season_avg >= 25:  # Superstar scorer
                upside_multiplier += 0.06  # +6% boost
            elif season_avg >= 18:  # Star scorer
                upside_multiplier += 0.04  # +4% boost
        elif stat_type == 'rebounds':
            if season_avg >= 12:  # Elite rebounder
                upside_multiplier += 0.05  # +5% boost
            elif season_avg >= 8:  # Strong rebounder
                upside_multiplier += 0.03  # +3% boost
        elif stat_type == 'assists':
            if season_avg >= 8:  # Elite playmaker
                upside_multiplier += 0.05  # +5% boost
            elif season_avg >= 5:  # Strong playmaker
                upside_multiplier += 0.03  # +3% boost
        
        # Factor 5: Per-minute efficiency (if they're efficient, more minutes = more upside)
        if minutes > 0 and per_minute_rate > 0:
            # If per-minute ceiling is significantly higher than season avg, boost
            if per_minute_ceiling > season_avg * 1.15:  # 15%+ higher with more minutes
                upside_multiplier += 0.04  # +4% boost
            elif per_minute_ceiling > season_avg * 1.10:  # 10%+ higher
                upside_multiplier += 0.02  # +2% boost
        
        # Cap multiplier at reasonable range (1.0 to 1.30 = 0% to 30% boost)
        upside_multiplier = min(1.30, max(1.0, upside_multiplier))
        
        result = {
            'upside_multiplier': upside_multiplier,
            'career_high': career_high,
            'career_90th': career_90th,
            'career_75th': career_75th,
            'volatility': volatility,
            'per_minute_rate': per_minute_rate,
            'per_minute_ceiling': per_minute_ceiling,
            'career_high_ratio': career_high_ratio,
            'percentile_90_ratio': percentile_90_ratio,
            'games_analyzed': len(valid_games),
            'has_data': True
        }
        
        self._upside_cache[cache_key] = result
        return result
    
    def _default_upside(self, season_avg: float, minutes: float, stat_type: str) -> Dict:
        """Return default upside metrics when no game log data available"""
        return {
            'upside_multiplier': 1.0,
            'career_high': season_avg * 1.5,  # Estimate
            'career_90th': season_avg * 1.25,  # Estimate
            'career_75th': season_avg * 1.15,  # Estimate
            'volatility': 0.20,  # Default moderate volatility
            'per_minute_rate': season_avg / minutes if minutes > 0 else 0,
            'per_minute_ceiling': season_avg * 1.1,  # Estimate
            'career_high_ratio': 1.5,
            'percentile_90_ratio': 1.25,
            'games_analyzed': 0,
            'has_data': False
        }
    
    def get_upside_multiplier(self, player_name: str, stat_type: str,
                              cached_game_log: Optional[pd.DataFrame] = None,
                              season_avg: float = 0.0, minutes: float = 0.0,
                              weight: float = 1.0) -> float:
        """
        Get upside multiplier for a player/stat combination
        
        Args:
            player_name: Player name
            stat_type: 'points', 'rebounds', or 'assists'
            cached_game_log: Optional cached game log
            season_avg: Season average for the stat
            minutes: Average minutes per game
            weight: Weight to apply (0.0 = no upside, 1.0 = full upside)
        
        Returns:
            Multiplier (1.0 = no change, >1.0 = upside boost)
        """
        if weight <= 0:
            return 1.0
        
        metrics = self.calculate_upside_metrics(
            player_name, stat_type, cached_game_log, season_avg, minutes
        )
        
        base_multiplier = metrics['upside_multiplier']
        
        # Apply weight: 1.0 + (mult - 1.0) * weight
        # If weight = 0.5, only apply half of the upside boost
        final_multiplier = 1.0 + (base_multiplier - 1.0) * weight
        
        return final_multiplier


if __name__ == "__main__":
    # Test the calculator
    print("=" * 70)
    print("🧪 UPSIDE CALCULATOR TEST")
    print("=" * 70)
    
    calculator = UpsideCalculator()
    
    # Create sample game log data
    np.random.seed(42)
    sample_games = pd.DataFrame({
        'PTS': np.random.normal(20, 6, 50),  # Mean 20, std 6
        'REB': np.random.normal(8, 3, 50),   # Mean 8, std 3
        'AST': np.random.normal(5, 2, 50),   # Mean 5, std 2
        'MIN': [35] * 50
    })
    # Ensure non-negative
    sample_games['PTS'] = sample_games['PTS'].clip(lower=0)
    sample_games['REB'] = sample_games['REB'].clip(lower=0)
    sample_games['AST'] = sample_games['AST'].clip(lower=0)
    
    # Add a career high outlier
    sample_games.loc[0, 'PTS'] = 45  # Career high
    
    print("\n📊 Testing with sample data:")
    print(f"  Season avg PTS: {sample_games['PTS'].mean():.1f}")
    print(f"  Career high: {sample_games['PTS'].max():.1f}")
    print(f"  90th percentile: {np.percentile(sample_games['PTS'], 90):.1f}")
    
    metrics = calculator.calculate_upside_metrics(
        'Test Player', 'points', sample_games, 
        season_avg=sample_games['PTS'].mean(),
        minutes=35.0
    )
    
    print(f"\n✅ Upside Metrics:")
    print(f"  Upside Multiplier: {metrics['upside_multiplier']:.3f}x")
    print(f"  Career High Ratio: {metrics['career_high_ratio']:.2f}x")
    print(f"  90th Percentile Ratio: {metrics['percentile_90_ratio']:.2f}x")
    print(f"  Volatility: {metrics['volatility']:.2%}")
    print(f"  Per-Minute Rate: {metrics['per_minute_rate']:.3f}")
    
    print("\n✅ Upside Calculator ready!")

