"""
Rest Days Calculator
====================
Calculates days of rest for teams and applies performance multipliers based on:
- Back-to-back games (B2B): Penalty for high-usage players, boost for bench
- 1 day rest: Neutral
- 2+ days rest: Boost for all players
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path


class RestDaysCalculator:
    """
    Calculate rest days and apply performance adjustments
    """
    
    def __init__(self):
        self.team_schedules = {}  # Cache team schedules
        self._load_schedules()
    
    def _load_schedules(self):
        """Load game schedules for all teams (cached)"""
        # Try both seasons
        for season in ['2025-26', '2024-25']:
            schedule_file = Path(f'data/raw/games_{season}.csv')
            if schedule_file.exists():
                try:
                    games = pd.read_csv(schedule_file)
                    if 'GAME_DATE' in games.columns:
                        # Parse dates
                        games['GAME_DATE'] = pd.to_datetime(games['GAME_DATE'], errors='coerce')
                        games = games.dropna(subset=['GAME_DATE'])
                        
                        # Group by team
                        for team_abbr in games['TEAM_ABBREVIATION'].unique():
                            team_games = games[games['TEAM_ABBREVIATION'] == team_abbr].copy()
                            team_games = team_games.sort_values('GAME_DATE')
                            
                            if team_abbr not in self.team_schedules:
                                self.team_schedules[team_abbr] = []
                            
                            # Add to schedule (avoid duplicates by game_id)
                            seen_game_ids = set()
                            for _, game in team_games.iterrows():
                                game_id = str(game.get('GAME_ID', ''))
                                if game_id in seen_game_ids:
                                    continue
                                seen_game_ids.add(game_id)
                                
                                game_date = game['GAME_DATE']
                                if pd.notna(game_date):
                                    if isinstance(game_date, pd.Timestamp):
                                        date_obj = game_date.date()
                                    elif isinstance(game_date, str):
                                        try:
                                            date_obj = pd.to_datetime(game_date).date()
                                        except:
                                            continue
                                    else:
                                        continue
                                    
                                    self.team_schedules[team_abbr].append({
                                        'date': date_obj,
                                        'game_id': game_id,
                                        'opponent': self._extract_opponent(game.get('MATCHUP', ''))
                                    })
                        
                        # Sort each team's schedule
                        for team_abbr in self.team_schedules:
                            self.team_schedules[team_abbr].sort(key=lambda x: x['date'])
                        
                        break  # Use first available season
                except Exception as e:
                    print(f"⚠️  Could not load schedule from {schedule_file}: {e}")
                    continue
    
    def _extract_opponent(self, matchup_str: str) -> Optional[str]:
        """Extract opponent team abbreviation from matchup string"""
        if pd.isna(matchup_str):
            return None
        
        matchup_str = str(matchup_str)
        # Format: "LAL @ GSW" or "GSW vs. LAL"
        parts = matchup_str.split()
        if len(parts) >= 3:
            # Get the team that's not the current team
            if '@' in matchup_str or 'vs.' in matchup_str or 'vs' in matchup_str:
                # Return the other team
                return parts[-1] if len(parts) > 1 else None
        return None
    
    def get_rest_days(self, team_abbr: str, game_date: datetime.date) -> int:
        """
        Calculate days of rest for a team before a game
        
        Args:
            team_abbr: Team abbreviation (e.g., 'LAL')
            game_date: Date of the game (date object)
        
        Returns:
            Days of rest (0 = back-to-back, 1 = 1 day rest, 2+ = 2+ days rest)
        """
        if team_abbr not in self.team_schedules:
            return 1  # Default to 1 day rest if schedule not available
        
        team_games = self.team_schedules[team_abbr]
        
        # Find the previous game
        previous_game_date = None
        for game in team_games:
            if game['date'] < game_date:
                previous_game_date = game['date']
            elif game['date'] == game_date:
                # Found today's game, use previous
                break
        
        if previous_game_date is None:
            return 2  # First game of season or no previous game found
        
        # Calculate days between games
        days_rest = (game_date - previous_game_date).days
        
        return max(0, days_rest)  # Ensure non-negative
    
    def calculate_rest_multiplier(self, days_rest: int, player_usage: str = 'medium', 
                                  player_minutes: float = 25.0) -> float:
        """
        Calculate performance multiplier based on rest days and player profile
        
        Args:
            days_rest: Days of rest (0 = B2B, 1 = 1 day, 2+ = 2+ days)
            player_usage: 'high', 'medium', 'low' (based on minutes/role)
            player_minutes: Average minutes per game
        
        Returns:
            Multiplier (1.0 = no change, >1.0 = boost, <1.0 = penalty)
        """
        # Determine usage level if not provided
        if player_usage == 'medium':
            if player_minutes >= 35:
                player_usage = 'high'
            elif player_minutes <= 20:
                player_usage = 'low'
        
        # Back-to-back (0 days rest)
        if days_rest == 0:
            if player_usage == 'high':
                # High-usage players: -7% penalty
                return 0.93
            elif player_usage == 'low':
                # Bench players: +8% boost (more minutes on B2B)
                return 1.08
            else:
                # Medium usage: -3% penalty
                return 0.97
        
        # 1 day rest
        elif days_rest == 1:
            # Neutral for all players
            return 1.0
        
        # 2+ days rest
        else:
            # Boost for all players (more rest = better performance)
            if days_rest == 2:
                return 1.03  # +3% boost
            elif days_rest >= 3:
                return 1.05  # +5% boost for 3+ days
            else:
                return 1.02  # Slight boost for 2 days
        
        return 1.0  # Default
    
    def get_rest_adjustment(self, team_abbr: str, game_date: datetime.date,
                           player_minutes: float = 25.0, player_usage: Optional[str] = None) -> Dict:
        """
        Get complete rest adjustment info for a player
        
        Args:
            team_abbr: Team abbreviation
            game_date: Date of the game
            player_minutes: Player's average minutes
            player_usage: 'high', 'medium', 'low' (auto-determined if None)
        
        Returns:
            Dict with 'days_rest', 'multiplier', 'adjustment_type'
        """
        days_rest = self.get_rest_days(team_abbr, game_date)
        
        # Auto-determine usage if not provided
        if player_usage is None:
            if player_minutes >= 35:
                player_usage = 'high'
            elif player_minutes <= 20:
                player_usage = 'low'
            else:
                player_usage = 'medium'
        
        multiplier = self.calculate_rest_multiplier(days_rest, player_usage, player_minutes)
        
        # Determine adjustment type
        if days_rest == 0:
            adjustment_type = 'B2B'
        elif days_rest == 1:
            adjustment_type = '1 Day Rest'
        elif days_rest == 2:
            adjustment_type = '2 Days Rest'
        else:
            adjustment_type = f'{days_rest}+ Days Rest'
        
        return {
            'days_rest': days_rest,
            'multiplier': multiplier,
            'adjustment_type': adjustment_type,
            'player_usage': player_usage
        }


if __name__ == "__main__":
    # Test the calculator
    print("=" * 70)
    print("🧪 REST DAYS CALCULATOR TEST")
    print("=" * 70)
    
    calculator = RestDaysCalculator()
    
    # Test with today's date
    today = datetime.now().date()
    
    test_teams = ['LAL', 'GSW', 'BOS', 'MIA']
    print(f"\n📅 Testing rest days for {today}:")
    print("-" * 70)
    
    for team in test_teams:
        if team in calculator.team_schedules:
            days_rest = calculator.get_rest_days(team, today)
            print(f"{team}: {days_rest} days rest")
            
            # Test multipliers
            high_usage_mult = calculator.calculate_rest_multiplier(days_rest, 'high', 36.0)
            low_usage_mult = calculator.calculate_rest_multiplier(days_rest, 'low', 15.0)
            
            print(f"  High usage (36 min): {high_usage_mult:.3f}x")
            print(f"  Low usage (15 min): {low_usage_mult:.3f}x")
        else:
            print(f"{team}: Schedule not found")
    
    print("\n✅ Rest Days Calculator ready!")

