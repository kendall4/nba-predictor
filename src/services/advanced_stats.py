"""
Advanced Stats Calculator
==========================
Calculate rebound chances, potential assists, and other advanced metrics
from player stats and game logs.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from src.analysis.hot_hand_tracker import HotHandTracker

class AdvancedStatsCalculator:
    """
    Calculate advanced stats like:
    - Rebound chances (based on team rebounding rate, opponent shooting, etc.)
    - Potential assists (based on team assists, usage, etc.)
    - Last N games performance with filters
    """
    
    def __init__(self):
        self.hot_hand_tracker = HotHandTracker()
    
    def calculate_rebound_chances(self, player_name: str, opponent_team: str, expected_minutes: float, 
                                   season='2025-26') -> Dict:
        """
        Calculate expected rebound chances for a player
        
        Rebound chances = opportunities where player could get a rebound
        Based on:
        - Team's offensive rebound rate
        - Opponent's defensive rebound rate  
        - Player's rebounding rate per minute
        - Expected pace (more possessions = more rebounds)
        - Minutes played
        """
        # Get player baseline stats
        player = self.hot_hand_tracker.get_player_baseline(player_name)
        if player is None:
            return None
        
        # Get recent game logs to calculate actual rebounding rates
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
        if game_log is not None and len(game_log) > 0:
            # Use last 10 games for rebounding rate
            recent = game_log.head(10)
            avg_reb = recent['REB'].mean() if 'REB' in recent.columns else player['REB']
            avg_min = recent['MIN'].mean() if 'MIN' in recent.columns else player['MIN']
            reb_per_min = avg_reb / avg_min if avg_min > 0 else 0
        else:
            reb_per_min = player['REB'] / player['MIN'] if player['MIN'] > 0 else 0
        
        # Estimate total rebound opportunities
        # In NBA, there are roughly 2x rebounds per game as actual rebounds (missed shots)
        # Offensive rebound chances ~= opponent missed shots when player is on court
        # Defensive rebound chances ~= team missed shots when player is on court
        # For simplicity, estimate total chances based on pace and minutes
        
        # Estimate pace (assume average ~98)
        estimated_pace = 98.0
        
        # Rebound opportunities per game (roughly 2x actual rebounds due to team rebounding)
        # More accurate: use team OREB% and opponent DREB%
        # Simplified: player gets roughly 1.5-2x their average rebounds in opportunities
        rebound_chances_per_min = reb_per_min * 2.0  # Conservative estimate
        
        # Expected rebound chances for this game
        expected_chances = rebound_chances_per_min * expected_minutes
        
        # Factor in opponent rebounding (if opponent is good at rebounding, fewer chances)
        # For now, assume average (can be enhanced with opponent data)
        opponent_factor = 1.0
        
        total_chances = expected_chances * opponent_factor
        
        return {
            'player_name': player_name,
            'opponent': opponent_team,
            'expected_minutes': expected_minutes,
            'reb_per_min': reb_per_min,
            'rebound_chances': total_chances,
            'rebound_chance_rate': reb_per_min / rebound_chances_per_min if rebound_chances_per_min > 0 else 0
        }
    
    def calculate_potential_assists(self, player_name: str, opponent_team: str, expected_minutes: float,
                                    season='2025-26') -> Dict:
        """
        Calculate potential assists for a player
        
        Potential assists = passes that lead to scoring opportunities
        Based on:
        - Player's assist rate per minute
        - Team's assist rate
        - Usage rate (players with ball more = more potential assists)
        - Opponent's assist defense
        """
        player = self.hot_hand_tracker.get_player_baseline(player_name)
        if player is None:
            return None
        
        # Get recent game logs for assist rate
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
        if game_log is not None and len(game_log) > 0:
            recent = game_log.head(10)
            avg_ast = recent['AST'].mean() if 'AST' in recent.columns else player['AST']
            avg_min = recent['MIN'].mean() if 'MIN' in recent.columns else player['MIN']
            ast_per_min = avg_ast / avg_min if avg_min > 0 else 0
        else:
            ast_per_min = player['AST'] / player['MIN'] if player['MIN'] > 0 else 0
        
        # Potential assists are roughly 2-3x actual assists (not all passes convert)
        # Players with high usage (ball handlers) have more potential assists
        # Estimate: potential assists = assists * 2.5 (varies by player type)
        usage_multiplier = 2.5
        
        # For guards/high usage players, higher multiplier
        if ast_per_min > 0.15:  # High assist rate (likely guard/playmaker)
            usage_multiplier = 3.0
        elif ast_per_min < 0.05:  # Low assist rate (likely big man)
            usage_multiplier = 2.0
        
        potential_assists_per_min = ast_per_min * usage_multiplier
        expected_potential_assists = potential_assists_per_min * expected_minutes
        
        return {
            'player_name': player_name,
            'opponent': opponent_team,
            'expected_minutes': expected_minutes,
            'ast_per_min': ast_per_min,
            'potential_assists': expected_potential_assists,
            'conversion_rate': ast_per_min / potential_assists_per_min if potential_assists_per_min > 0 else 0
        }
    
    def get_last_n_games_stats(self, player_name: str, n: int = 5, season: str = '2025-26',
                               filters: Optional[Dict] = None) -> Optional[pd.DataFrame]:
        """
        Get last N games stats with optional filters
        
        Args:
            player_name: Player to analyze
            n: Number of recent games (default 5)
            season: Season to analyze
            filters: Optional dict with filters like:
                - 'min_points': Minimum points in game
                - 'min_rebounds': Minimum rebounds
                - 'min_assists': Minimum assists
                - 'opponent': Filter by opponent team
                - 'home_away': 'Home' or 'Away'
        
        Returns:
            DataFrame with last N games stats
        """
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
        if game_log is None or len(game_log) == 0:
            return None
        
        # Get last N games
        recent = game_log.head(n).copy()
        
        # Apply filters if provided
        if filters:
            if 'min_points' in filters and 'PTS' in recent.columns:
                recent = recent[recent['PTS'] >= filters['min_points']]
            if 'min_rebounds' in filters and 'REB' in recent.columns:
                recent = recent[recent['REB'] >= filters['min_rebounds']]
            if 'min_assists' in filters and 'AST' in recent.columns:
                recent = recent[recent['AST'] >= filters['min_assists']]
            if 'opponent' in filters and 'MATCHUP' in recent.columns:
                opp = filters['opponent']
                recent = recent[recent['MATCHUP'].str.contains(opp, case=False, na=False)]
            if 'home_away' in filters and 'MATCHUP' in recent.columns:
                ha = filters['home_away'].lower()
                if ha == 'home':
                    recent = recent[recent['MATCHUP'].str.contains('vs.', case=False, na=False)]
                elif ha == 'away':
                    recent = recent[recent['MATCHUP'].str.contains('@', case=False, na=False)]
        
        return recent
    
    def calculate_rebound_chances_from_games(self, player_name: str, n: int = 5, season: str = '2025-26') -> Dict:
        """Calculate rebound chances based on last N games"""
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
        if game_log is None or len(game_log) == 0:
            return None
        
        recent = game_log.head(n)
        
        # Calculate average rebounds and estimate chances
        avg_reb = recent['REB'].mean() if 'REB' in recent.columns else 0
        # MIN column might not always be in game log, use baseline if available
        if 'MIN' in recent.columns:
            avg_min = recent['MIN'].mean()
        else:
            # Get from baseline player stats
            player = self.hot_hand_tracker.get_player_baseline(player_name)
            avg_min = player['MIN'] if player is not None else 0
        
        # Estimate rebound chances (roughly 2x actual rebounds)
        avg_chances = avg_reb * 2.0
        
        return {
            'player_name': player_name,
            'games_analyzed': len(recent),
            'avg_rebounds': avg_reb,
            'avg_minutes': avg_min,
            'avg_rebound_chances': avg_chances,
            'rebound_chance_rate': avg_reb / avg_chances if avg_chances > 0 else 0
        }
    
    def calculate_potential_assists_from_games(self, player_name: str, n: int = 5, season: str = '2025-26') -> Dict:
        """Calculate potential assists based on last N games"""
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
        if game_log is None or len(game_log) == 0:
            return None
        
        recent = game_log.head(n)
        
        avg_ast = recent['AST'].mean() if 'AST' in recent.columns else 0
        # MIN column might not always be in game log
        if 'MIN' in recent.columns:
            avg_min = recent['MIN'].mean()
            ast_per_min = avg_ast / avg_min if avg_min > 0 else 0
        else:
            # Get from baseline
            player = self.hot_hand_tracker.get_player_baseline(player_name)
            avg_min = player['MIN'] if player is not None else 0
            ast_per_min = avg_ast / avg_min if avg_min > 0 else 0
        
        # Estimate potential assists (2.5x actual assists for average player)
        multiplier = 3.0 if ast_per_min > 0.15 else 2.5 if avg_ast > 5 else 2.0
        avg_potential = avg_ast * multiplier
        
        return {
            'player_name': player_name,
            'games_analyzed': len(recent),
            'avg_assists': avg_ast,
            'avg_minutes': avg_min,
            'avg_potential_assists': avg_potential,
            'conversion_rate': avg_ast / avg_potential if avg_potential > 0 else 0
        }

