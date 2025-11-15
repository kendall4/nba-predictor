"""
Home/Away Analyzer
==================
Analyzes home/away performance splits for teams and players.
Applies adjustments based on team records and historical performance.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from pathlib import Path


class HomeAwayAnalyzer:
    """
    Analyze and apply home/away performance adjustments
    """
    
    def __init__(self):
        self.team_splits = {}  # Cache team home/away splits
        self.player_splits = {}  # Cache player home/away splits
        self._load_splits()
    
    def _load_splits(self):
        """Load home/away splits from game logs (lazy load when needed)"""
        # This will be populated from game logs when needed
        # For now, use team record-based heuristics
        pass
    
    def calculate_team_home_advantage(self, team_abbr: str, team_record: Optional[Dict] = None) -> float:
        """
        Calculate home advantage multiplier based on team quality
        
        Args:
            team_abbr: Team abbreviation
            team_record: Dict with 'wins', 'losses', 'win_pct' (optional)
        
        Returns:
            Home advantage multiplier (1.0 = neutral, >1.0 = home boost)
        """
        # Base home advantage: +3% for all teams
        base_advantage = 1.03
        
        # If we have team record, adjust based on quality
        if team_record and 'win_pct' in team_record:
            win_pct = team_record['win_pct']
            
            # Good teams (win_pct > 0.55) have stronger home advantage
            if win_pct > 0.55:
                return 1.05  # +5% for good teams
            elif win_pct < 0.45:
                return 1.02  # +2% for bad teams (less home advantage)
        
        return base_advantage
    
    def calculate_away_penalty(self, team_abbr: str, team_record: Optional[Dict] = None) -> float:
        """
        Calculate away game penalty
        
        Args:
            team_abbr: Team abbreviation
            team_record: Dict with team record info
        
        Returns:
            Away penalty multiplier (1.0 = neutral, <1.0 = penalty)
        """
        # Base away penalty: -3% for all teams
        base_penalty = 0.97
        
        # If we have team record, adjust based on quality
        if team_record and 'win_pct' in team_record:
            win_pct = team_record['win_pct']
            
            # Good teams handle away games better
            if win_pct > 0.55:
                return 0.98  # -2% for good teams (less penalty)
            elif win_pct < 0.45:
                return 0.95  # -5% for bad teams (bigger penalty)
        
        return base_penalty
    
    def get_home_away_multiplier(self, team_abbr: str, is_home: bool, 
                                  team_record: Optional[Dict] = None) -> float:
        """
        Get home/away multiplier for a team
        
        Args:
            team_abbr: Team abbreviation
            is_home: True if home game, False if away
            team_record: Optional team record dict
        
        Returns:
            Performance multiplier
        """
        if is_home:
            return self.calculate_team_home_advantage(team_abbr, team_record)
        else:
            return self.calculate_away_penalty(team_abbr, team_record)
    
    def get_player_home_away_split(self, player_name: str, 
                                    cached_game_log: Optional[pd.DataFrame] = None) -> Dict:
        """
        Calculate player's home/away performance split
        
        Args:
            player_name: Player name
            cached_game_log: Optional cached game log DataFrame
        
        Returns:
            Dict with 'home_multiplier', 'away_multiplier', 'home_ppg', 'away_ppg'
        """
        # Default: no player-specific adjustment
        default = {
            'home_multiplier': 1.0,
            'away_multiplier': 1.0,
            'home_ppg': None,
            'away_ppg': None,
            'has_data': False
        }
        
        if cached_game_log is None or len(cached_game_log) == 0:
            return default
        
        # Check if we have home/away indicator in game log
        # NBA API game logs typically have MATCHUP column like "LAL @ GSW" or "GSW vs. LAL"
        if 'MATCHUP' not in cached_game_log.columns:
            return default
        
        try:
            # Parse home/away from matchup
            game_log = cached_game_log.copy()
            game_log['IS_HOME'] = ~game_log['MATCHUP'].str.contains('@', na=False)
            
            # Calculate home vs away averages
            home_games = game_log[game_log['IS_HOME'] == True]
            away_games = game_log[game_log['IS_HOME'] == False]
            
            if len(home_games) < 5 or len(away_games) < 5:
                # Not enough data
                return default
            
            home_ppg = home_games['PTS'].mean() if 'PTS' in home_games.columns else 0
            away_ppg = away_games['PTS'].mean() if 'PTS' in away_games.columns else 0
            
            if home_ppg == 0 or away_ppg == 0:
                return default
            
            # Calculate multipliers relative to overall average
            overall_ppg = game_log['PTS'].mean() if 'PTS' in game_log.columns else 0
            if overall_ppg > 0:
                home_multiplier = home_ppg / overall_ppg
                away_multiplier = away_ppg / overall_ppg
            else:
                home_multiplier = 1.0
                away_multiplier = 1.0
            
            return {
                'home_multiplier': float(home_multiplier),
                'away_multiplier': float(away_multiplier),
                'home_ppg': float(home_ppg),
                'away_ppg': float(away_ppg),
                'has_data': True
            }
        except Exception:
            return default


if __name__ == "__main__":
    # Test the analyzer
    print("=" * 70)
    print("🧪 HOME/AWAY ANALYZER TEST")
    print("=" * 70)
    
    analyzer = HomeAwayAnalyzer()
    
    # Test team multipliers
    test_teams = [
        ('LAL', {'win_pct': 0.60}),
        ('DET', {'win_pct': 0.35}),
        ('BOS', {'win_pct': 0.65})
    ]
    
    print("\n📊 Team Home/Away Multipliers:")
    print("-" * 70)
    for team, record in test_teams:
        home_mult = analyzer.get_home_away_multiplier(team, is_home=True, team_record=record)
        away_mult = analyzer.get_home_away_multiplier(team, is_home=False, team_record=record)
        print(f"{team} (Win%: {record['win_pct']:.2f}):")
        print(f"  Home: {home_mult:.3f}x (+{(home_mult-1)*100:.1f}%)")
        print(f"  Away: {away_mult:.3f}x ({(away_mult-1)*100:.1f}%)")
    
    print("\n✅ Home/Away Analyzer ready!")

