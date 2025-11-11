"""
System Profile Analyzer
=======================
Analyzes team offensive and defensive system profiles and calculates
player-system fit scores. Some players thrive in certain systems.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from pathlib import Path


class SystemProfileAnalyzer:
    """
    Analyze team system profiles (offensive and defensive styles)
    and calculate how well players fit into those systems.
    """
    
    def __init__(self):
        self.team_stats = None
        self.league_averages = {}
        self._team_profiles_cache = {}  # Cache team profiles to avoid recalculating
        self._load_team_data()
    
    def _load_team_data(self):
        """Load team stats for profile analysis"""
        current_season = '2025-26'
        prev_season = '2024-25'
        
        try:
            team_file = Path(f'data/raw/team_pace_{current_season}.csv')
            if not team_file.exists():
                team_file = Path(f'data/raw/team_pace_{prev_season}.csv')
            
            if team_file.exists():
                self.team_stats = pd.read_csv(team_file)
                
                # Team name to abbreviation mapping
                team_name_map = {
                    'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
                    'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
                    'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
                    'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
                    'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Los Angeles Clippers': 'LAC',
                    'Memphis Grizzlies': 'MEM', 'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL',
                    'Minnesota Timberwolves': 'MIN', 'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK',
                    'Oklahoma City Thunder': 'OKC', 'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI',
                    'Phoenix Suns': 'PHX', 'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC',
                    'San Antonio Spurs': 'SAS', 'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA',
                    'Washington Wizards': 'WAS'
                }
                
                # Add TEAM_ABBREVIATION if it doesn't exist
                if 'TEAM_ABBREVIATION' not in self.team_stats.columns and 'TEAM_NAME' in self.team_stats.columns:
                    self.team_stats['TEAM_ABBREVIATION'] = self.team_stats['TEAM_NAME'].map(team_name_map)
                    # Filter to only NBA teams (exclude WNBA)
                    self.team_stats = self.team_stats[self.team_stats['TEAM_ABBREVIATION'].notna()]
                
                # Calculate league averages (only for NBA teams)
                if 'PACE' in self.team_stats.columns:
                    self.league_averages['pace'] = self.team_stats['PACE'].mean()
                if 'OFF_RATING' in self.team_stats.columns:
                    self.league_averages['off_rating'] = self.team_stats['OFF_RATING'].mean()
                if 'DEF_RATING' in self.team_stats.columns:
                    self.league_averages['def_rating'] = self.team_stats['DEF_RATING'].mean()
        except Exception as e:
            print(f"Warning: Could not load team stats: {e}")
            self.team_stats = None
    
    def get_offensive_profile(self, team_abbr: str) -> Dict:
        """
        Get team's offensive system profile (cached)
        
        Returns:
            Dict with offensive style characteristics:
            - pace_tier: 'Fast', 'Average', 'Slow'
            - efficiency_tier: 'High', 'Average', 'Low'
            - style: 'Run-and-Gun', 'Half-Court', 'Balanced', etc.
            - shot_preference: '3PT Heavy', 'Paint Heavy', 'Balanced'
        """
        team_abbr = team_abbr.upper()
        
        # Check cache first
        cache_key = f"off_{team_abbr}"
        if cache_key in self._team_profiles_cache:
            return self._team_profiles_cache[cache_key]
        
        if self.team_stats is None:
            profile = self._default_profile()
            self._team_profiles_cache[cache_key] = profile
            return profile
        
        team_row = self.team_stats[
            self.team_stats['TEAM_ABBREVIATION'] == team_abbr
        ]
        
        if len(team_row) == 0:
            profile = self._default_profile()
            self._team_profiles_cache[cache_key] = profile
            return profile
        
        team = team_row.iloc[0]
        avg_pace = self.league_averages.get('pace', 98.0)
        avg_off_rating = self.league_averages.get('off_rating', 110.0)
        
        pace = float(team.get('PACE', avg_pace))
        off_rating = float(team.get('OFF_RATING', avg_off_rating))
        
        # Pace tier
        if pace >= avg_pace + 2:
            pace_tier = 'Fast'
        elif pace <= avg_pace - 2:
            pace_tier = 'Slow'
        else:
            pace_tier = 'Average'
        
        # Efficiency tier
        if off_rating >= avg_off_rating + 3:
            efficiency_tier = 'High'
        elif off_rating <= avg_off_rating - 3:
            efficiency_tier = 'Low'
        else:
            efficiency_tier = 'Average'
        
        # Style classification
        if pace_tier == 'Fast' and efficiency_tier == 'High':
            style = 'Run-and-Gun'
        elif pace_tier == 'Slow' and efficiency_tier == 'High':
            style = 'Half-Court Precision'
        elif pace_tier == 'Fast' and efficiency_tier == 'Low':
            style = 'High-Volume'
        elif pace_tier == 'Slow' and efficiency_tier == 'Low':
            style = 'Grind-It-Out'
        else:
            style = 'Balanced'
        
        profile = {
            'pace': pace,
            'pace_tier': pace_tier,
            'off_rating': off_rating,
            'efficiency_tier': efficiency_tier,
            'style': style,
            'pace_vs_avg': pace - avg_pace,
            'off_rating_vs_avg': off_rating - avg_off_rating
        }
        
        # Cache the profile
        self._team_profiles_cache[cache_key] = profile
        return profile
    
    def get_defensive_profile(self, team_abbr: str) -> Dict:
        """
        Get team's defensive system profile (cached)
        
        Returns:
            Dict with defensive style characteristics:
            - pressure: 'High', 'Average', 'Low'
            - efficiency: 'Elite', 'Good', 'Average', 'Poor'
            - style: 'Aggressive', 'Conservative', 'Balanced'
        """
        team_abbr = team_abbr.upper()
        
        # Check cache first
        cache_key = f"def_{team_abbr}"
        if cache_key in self._team_profiles_cache:
            return self._team_profiles_cache[cache_key]
        
        if self.team_stats is None:
            profile = self._default_defensive_profile()
            self._team_profiles_cache[cache_key] = profile
            return profile
        
        team_row = self.team_stats[
            self.team_stats['TEAM_ABBREVIATION'] == team_abbr
        ]
        
        if len(team_row) == 0:
            profile = self._default_defensive_profile()
            self._team_profiles_cache[cache_key] = profile
            return profile
        
        team = team_row.iloc[0]
        avg_def_rating = self.league_averages.get('def_rating', 112.0)
        
        def_rating = float(team.get('DEF_RATING', avg_def_rating))
        
        # Lower DEF_RATING = better defense
        if def_rating <= avg_def_rating - 5:
            efficiency = 'Elite'
            pressure = 'High'
        elif def_rating <= avg_def_rating - 2:
            efficiency = 'Good'
            pressure = 'High'
        elif def_rating >= avg_def_rating + 5:
            efficiency = 'Poor'
            pressure = 'Low'
        elif def_rating >= avg_def_rating + 2:
            efficiency = 'Below Average'
            pressure = 'Average'
        else:
            efficiency = 'Average'
            pressure = 'Average'
        
        # Style
        if efficiency in ['Elite', 'Good'] and pressure == 'High':
            style = 'Aggressive'
        elif efficiency in ['Elite', 'Good'] and pressure == 'Average':
            style = 'Disciplined'
        elif efficiency in ['Poor', 'Below Average']:
            style = 'Permissive'
        else:
            style = 'Balanced'
        
        profile = {
            'def_rating': def_rating,
            'efficiency': efficiency,
            'pressure': pressure,
            'style': style,
            'def_rating_vs_avg': def_rating - avg_def_rating
        }
        
        # Cache the profile
        self._team_profiles_cache[cache_key] = profile
        return profile
    
    def calculate_player_system_fit(self, player_stats: Dict, team_off_profile: Dict, 
                                     opponent_def_profile: Dict) -> Dict:
        """
        Calculate how well a player fits the offensive system and matches up vs defensive system
        
        Args:
            player_stats: Dict with player stats (PTS, REB, AST, MIN, etc.)
            team_off_profile: Offensive profile from get_offensive_profile()
            opponent_def_profile: Defensive profile from get_defensive_profile()
        
        Returns:
            Dict with fit scores and adjustments
        """
        ppg = player_stats.get('PTS', 0)
        rpg = player_stats.get('REB', 0)
        apg = player_stats.get('AST', 0)
        mpg = player_stats.get('MIN', 0)
        
        if mpg == 0:
            return {'fit_score': 1.0, 'offensive_fit': 1.0, 'defensive_matchup': 1.0}
        
        # Calculate per-minute rates
        pts_per_min = ppg / mpg
        reb_per_min = rpg / mpg
        ast_per_min = apg / mpg
        
        # OFFENSIVE SYSTEM FIT
        # Players who score more per minute benefit from fast pace
        # Players who assist more benefit from high-efficiency systems
        # Players who rebound more benefit from slower, more physical systems
        
        pace_tier = team_off_profile.get('pace_tier', 'Average')
        efficiency_tier = team_off_profile.get('efficiency_tier', 'Average')
        style = team_off_profile.get('style', 'Balanced')
        
        offensive_fit = 1.0
        
        # Pace fit: High-scoring players (pts/min) benefit from fast pace
        if pace_tier == 'Fast':
            if pts_per_min >= 0.6:  # High scorer
                offensive_fit *= 1.10
            elif pts_per_min >= 0.4:  # Medium scorer
                offensive_fit *= 1.05
        elif pace_tier == 'Slow':
            if reb_per_min >= 0.25:  # Good rebounder
                offensive_fit *= 1.08
            elif ast_per_min >= 0.15:  # Good playmaker
                offensive_fit *= 1.05
        
        # Efficiency fit: Playmakers benefit from high-efficiency systems
        if efficiency_tier == 'High':
            if ast_per_min >= 0.15:  # Good playmaker
                offensive_fit *= 1.08
            if pts_per_min >= 0.5:  # Efficient scorer
                offensive_fit *= 1.05
        
        # Style-specific fits
        if style == 'Run-and-Gun':
            # Fast-break players, transition scorers
            if pts_per_min >= 0.6 and ast_per_min >= 0.12:
                offensive_fit *= 1.12
        elif style == 'Half-Court Precision':
            # Efficient scorers, good shooters
            if pts_per_min >= 0.5 and ast_per_min >= 0.10:
                offensive_fit *= 1.10
        
        # DEFENSIVE MATCHUP
        # How well player's strengths match opponent's weaknesses
        
        def_efficiency = opponent_def_profile.get('efficiency', 'Average')
        def_pressure = opponent_def_profile.get('pressure', 'Average')
        def_style = opponent_def_profile.get('style', 'Balanced')
        
        defensive_matchup = 1.0
        
        # Against poor defense: All players benefit, but scorers benefit most
        if def_efficiency in ['Poor', 'Below Average']:
            if pts_per_min >= 0.5:
                defensive_matchup *= 1.15
            elif pts_per_min >= 0.35:
                defensive_matchup *= 1.10
            else:
                defensive_matchup *= 1.05
        
        # Against elite defense: Efficient players handle it better
        elif def_efficiency == 'Elite':
            if pts_per_min >= 0.6:  # Superstars can still score
                defensive_matchup *= 0.95
            elif pts_per_min >= 0.4:
                defensive_matchup *= 0.90
            else:
                defensive_matchup *= 0.85
        
        # Against aggressive defense: Playmakers can exploit
        if def_style == 'Aggressive':
            if ast_per_min >= 0.15:  # Playmakers can find open teammates
                defensive_matchup *= 1.08
        
        # Combined fit score
        fit_score = (offensive_fit * 0.6) + (defensive_matchup * 0.4)
        
        return {
            'fit_score': fit_score,
            'offensive_fit': offensive_fit,
            'defensive_matchup': defensive_matchup,
            'pace_fit': 1.0 if pace_tier == 'Average' else (1.05 if pace_tier == 'Fast' and pts_per_min >= 0.5 else 1.0),
            'efficiency_fit': 1.0 if efficiency_tier == 'Average' else (1.05 if efficiency_tier == 'High' and ast_per_min >= 0.12 else 1.0)
        }
    
    def _default_profile(self) -> Dict:
        """Return default offensive profile"""
        return {
            'pace': 98.0,
            'pace_tier': 'Average',
            'off_rating': 110.0,
            'efficiency_tier': 'Average',
            'style': 'Balanced',
            'pace_vs_avg': 0.0,
            'off_rating_vs_avg': 0.0
        }
    
    def _default_defensive_profile(self) -> Dict:
        """Return default defensive profile"""
        return {
            'def_rating': 112.0,
            'efficiency': 'Average',
            'pressure': 'Average',
            'style': 'Balanced',
            'def_rating_vs_avg': 0.0
        }

