"""
Team Stats Analyzer
===================
Analyzes team defensive statistics to show what each team allows.
Used in Player Explorer to show matchup advantages/disadvantages.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from pathlib import Path


class TeamStatsAnalyzer:
    """
    Analyze team defensive stats to show:
    - What teams allow (points, rebounds, assists, 3s)
    - How they rank vs league average
    - Matchup advantages for players
    """
    
    def __init__(self):
        self.team_stats = None
        self.defensive_matchups = None
        self._load_team_data()
    
    def _load_team_data(self):
        """Load team defensive stats from CSV files"""
        current_season = '2025-26'
        prev_season = '2024-25'
        
        try:
            # Try current season first
            team_file = Path(f'data/raw/team_pace_{current_season}.csv')
            
            if team_file.exists():
                self.team_stats = pd.read_csv(team_file)
            else:
                # Fallback to previous season
                team_file = Path(f'data/raw/team_pace_{prev_season}.csv')
                if team_file.exists():
                    self.team_stats = pd.read_csv(team_file)
            
            # Load defensive matchups if available
            matchup_file = Path(f'data/raw/defensive_matchups_{current_season}.csv')
            if not matchup_file.exists():
                matchup_file = Path(f'data/raw/defensive_matchups_{prev_season}.csv')
            
            if matchup_file.exists():
                self.defensive_matchups = pd.read_csv(matchup_file)
        except Exception as e:
            print(f"Warning: Could not load team stats: {e}")
            self.team_stats = None
            self.defensive_matchups = None
    
    def get_team_defensive_profile(self, team_abbr: str) -> Optional[Dict]:
        """
        Get comprehensive defensive profile for a team
        
        Args:
            team_abbr: Team abbreviation (e.g., 'LAL', 'GSW')
        
        Returns:
            Dict with defensive stats and rankings
        """
        if self.team_stats is None or len(self.team_stats) == 0:
            return None
        
        # Normalize team abbreviation
        team_abbr = team_abbr.upper()
        
        # Find team in stats
        # Team abbreviations might be in different columns
        team_row = None
        if 'TEAM_ABBREVIATION' in self.team_stats.columns:
            team_row = self.team_stats[self.team_stats['TEAM_ABBREVIATION'] == team_abbr]
        elif 'TEAM_ID' in self.team_stats.columns:
            # Try to match by team name
            team_name_map = {
                'ATL': 'Hawks', 'BOS': 'Celtics', 'BKN': 'Nets', 'CHA': 'Hornets',
                'CHI': 'Bulls', 'CLE': 'Cavaliers', 'DAL': 'Mavericks', 'DEN': 'Nuggets',
                'DET': 'Pistons', 'GSW': 'Warriors', 'HOU': 'Rockets', 'IND': 'Pacers',
                'LAC': 'Clippers', 'LAL': 'Lakers', 'MEM': 'Grizzlies', 'MIA': 'Heat',
                'MIL': 'Bucks', 'MIN': 'Timberwolves', 'NOP': 'Pelicans', 'NYK': 'Knicks',
                'OKC': 'Thunder', 'ORL': 'Magic', 'PHI': '76ers', 'PHX': 'Suns',
                'POR': 'Trail Blazers', 'SAC': 'Kings', 'SAS': 'Spurs', 'TOR': 'Raptors',
                'UTA': 'Jazz', 'WAS': 'Wizards'
            }
            team_name = team_name_map.get(team_abbr, '')
            if team_name and 'TEAM_NAME' in self.team_stats.columns:
                team_row = self.team_stats[self.team_stats['TEAM_NAME'].str.contains(team_name, case=False, na=False)]
        
        if team_row is None or len(team_row) == 0:
            return None
        
        team = team_row.iloc[0]
        
        # Calculate league averages for comparison
        league_avg_def_rating = self.team_stats['DEF_RATING'].mean() if 'DEF_RATING' in self.team_stats.columns else 112.0
        
        # Note: OPP_* columns may not be in the team_pace file - use defensive percentages instead
        # If OPP columns exist, use them; otherwise estimate from defensive ratings
        if 'OPP_OREB' in self.team_stats.columns:
            league_avg_oreb_allowed = self.team_stats['OPP_OREB'].mean()
            league_avg_dreb_allowed = self.team_stats['OPP_DREB'].mean()
        else:
            # Estimate from league averages (typical NBA: ~10 OReb, ~32 DReb per game)
            league_avg_oreb_allowed = 10.0
            league_avg_dreb_allowed = 32.0
        
        if 'OPP_AST' in self.team_stats.columns:
            league_avg_ast_allowed = self.team_stats['OPP_AST'].mean()
        else:
            league_avg_ast_allowed = 25.0  # League average assists allowed
        
        if 'OPP_PTS' in self.team_stats.columns:
            league_avg_pts_allowed = self.team_stats['OPP_PTS'].mean()
        else:
            # Estimate from defensive rating (DEF_RATING ~= points allowed per 100 possessions)
            # With average pace ~98, DEF_RATING translates roughly to points allowed
            league_avg_pts_allowed = league_avg_def_rating * 0.98  # Rough conversion
        
        # Get defensive rating
        def_rating = float(team.get('DEF_RATING', league_avg_def_rating))
        
        # Calculate rankings (1 = best defense, 30 = worst)
        if 'DEF_RATING' in self.team_stats.columns:
            def_ranking = self.team_stats['DEF_RATING'].rank(ascending=True).loc[team_row.index[0]]  # Lower is better
        else:
            def_ranking = None
        
        # Get what they allow (use defensive rating if specific columns don't exist)
        if 'OPP_PTS' in team:
            pts_allowed = float(team['OPP_PTS'])
        else:
            # Estimate from defensive rating
            pts_allowed = def_rating * 0.98  # Rough conversion
        
        if 'OPP_OREB' in team and 'OPP_DREB' in team:
            reb_allowed = float(team['OPP_OREB'] + team['OPP_DREB'])
            oreb_allowed = float(team['OPP_OREB'])
            dreb_allowed = float(team['OPP_DREB'])
        else:
            # Estimate from defensive rebounding percentage (lower DREB_PCT = more rebounds allowed)
            if 'DREB_PCT' in team:
                dreb_pct = float(team['DREB_PCT'])
                # Lower DREB_PCT means more rebounds allowed to opponent
                # Estimate: if DREB_PCT is 10% below average, allow ~2 more rebounds
                avg_dreb_pct = self.team_stats['DREB_PCT'].mean() if 'DREB_PCT' in self.team_stats.columns else 0.73
                reb_factor = (avg_dreb_pct - dreb_pct) / avg_dreb_pct
                reb_allowed = (league_avg_oreb_allowed + league_avg_dreb_allowed) * (1 + reb_factor * 0.1)
                oreb_allowed = league_avg_oreb_allowed * (1 + reb_factor * 0.1)
                dreb_allowed = league_avg_dreb_allowed * (1 + reb_factor * 0.1)
            else:
                reb_allowed = league_avg_oreb_allowed + league_avg_dreb_allowed
                oreb_allowed = league_avg_oreb_allowed
                dreb_allowed = league_avg_dreb_allowed
        
        if 'OPP_AST' in team:
            ast_allowed = float(team['OPP_AST'])
        else:
            # Estimate from defensive rating (worse defense = more assists allowed)
            # Higher DEF_RATING = more assists typically allowed
            def_factor = (def_rating - league_avg_def_rating) / league_avg_def_rating
            ast_allowed = league_avg_ast_allowed * (1 + def_factor * 0.3)
        
        # Calculate vs league average
        pts_vs_avg = pts_allowed - league_avg_pts_allowed
        reb_vs_avg = reb_allowed - (league_avg_oreb_allowed + league_avg_dreb_allowed)
        ast_vs_avg = ast_allowed - league_avg_ast_allowed
        
        # Determine if favorable/unfavorable for players
        # Higher points allowed = favorable for scorers
        # Higher rebounds allowed = favorable for rebounders
        # Higher assists allowed = favorable for playmakers
        
        profile = {
            'team': team_abbr,
            'team_name': team.get('TEAM_NAME', team_abbr),
            
            # Defensive rating (lower is better)
            'defensive_rating': def_rating,
            'defensive_ranking': int(def_ranking) if def_ranking is not None else None,
            'league_avg_def_rating': league_avg_def_rating,
            
            # What they allow per game
            'points_allowed': pts_allowed,
            'points_allowed_vs_avg': pts_vs_avg,
            'points_allowed_rank': self._get_rank('OPP_PTS', pts_allowed, ascending=False),  # Higher allowed = worse defense
            
            'total_rebounds_allowed': reb_allowed,
            'offensive_rebounds_allowed': oreb_allowed,
            'defensive_rebounds_allowed': dreb_allowed,
            'rebounds_allowed_vs_avg': reb_vs_avg,
            
            'assists_allowed': ast_allowed,
            'assists_allowed_vs_avg': ast_vs_avg,
            'assists_allowed_rank': self._get_rank('OPP_AST', ast_allowed, ascending=False),
            
            # League averages for comparison
            'league_avg_points_allowed': league_avg_pts_allowed,
            'league_avg_rebounds_allowed': league_avg_oreb_allowed + league_avg_dreb_allowed,
            'league_avg_assists_allowed': league_avg_ast_allowed,
            
            # Matchup assessment
            'favorable_for_scorers': pts_vs_avg > 2,  # Allows >2 more points than average
            'favorable_for_rebounders': reb_vs_avg > 2,  # Allows >2 more rebounds than average
            'favorable_for_playmakers': ast_vs_avg > 1,  # Allows >1 more assist than average
        }
        
        # Try to get 3PM allowed if available
        if 'OPP_FG3M' in team:
            profile['threes_allowed'] = float(team['OPP_FG3M'])
            league_avg_3pm = self.team_stats['OPP_FG3M'].mean() if 'OPP_FG3M' in self.team_stats.columns else 12.0
            profile['threes_allowed_vs_avg'] = profile['threes_allowed'] - league_avg_3pm
            profile['favorable_for_shooters'] = profile['threes_allowed_vs_avg'] > 0.5
        else:
            profile['threes_allowed'] = None
            profile['threes_allowed_vs_avg'] = None
            profile['favorable_for_shooters'] = None
        
        return profile
    
    def _get_rank(self, column: str, value: float, ascending: bool = True) -> Optional[int]:
        """Get rank of a value in a column (1 = best, 30 = worst)"""
        if self.team_stats is None or column not in self.team_stats.columns:
            return None
        
        if ascending:
            # Lower is better (e.g., defensive rating)
            ranked = self.team_stats[column].rank(ascending=True)
        else:
            # Higher is better (e.g., points allowed means worse defense)
            ranked = self.team_stats[column].rank(ascending=False)
        
        # Find where our value would rank
        sorted_values = sorted(self.team_stats[column].dropna().unique(), reverse=not ascending)
        try:
            rank = sorted_values.index(value) + 1
            return rank
        except:
            return None
    
    def get_matchup_analysis(self, player_name: str, opponent_team: str) -> Optional[Dict]:
        """
        Analyze how a player's strengths match up against opponent's weaknesses
        
        Args:
            player_name: Player name
            opponent_team: Opponent team abbreviation
        
        Returns:
            Dict with matchup analysis
        """
        from src.analysis.hot_hand_tracker import HotHandTracker
        tracker = HotHandTracker()
        
        player = tracker.get_player_baseline(player_name)
        if player is None:
            return None
        
        opponent_profile = self.get_team_defensive_profile(opponent_team)
        if opponent_profile is None:
            return None
        
        # Get player's strengths
        player_ppg = player.get('PTS', 0)
        player_rpg = player.get('REB', 0)
        player_apg = player.get('AST', 0)
        player_3pm = player.get('FG3M', 0)
        
        # Analyze matchup
        analysis = {
            'player': player_name,
            'opponent': opponent_team,
            'opponent_name': opponent_profile['team_name'],
            
            # Points matchup
            'points_matchup': {
                'player_avg': player_ppg,
                'opponent_allows': opponent_profile['points_allowed'],
                'opponent_rank': opponent_profile['points_allowed_rank'],
                'advantage': 'favorable' if opponent_profile['favorable_for_scorers'] else 'neutral' if opponent_profile['points_allowed_vs_avg'] > -1 else 'unfavorable',
                'expected_impact': opponent_profile['points_allowed_vs_avg'] * 0.3  # Rough estimate
            },
            
            # Rebounds matchup
            'rebounds_matchup': {
                'player_avg': player_rpg,
                'opponent_allows': opponent_profile['total_rebounds_allowed'],
                'advantage': 'favorable' if opponent_profile['favorable_for_rebounders'] else 'neutral' if opponent_profile['rebounds_allowed_vs_avg'] > -1 else 'unfavorable',
                'expected_impact': opponent_profile['rebounds_allowed_vs_avg'] * 0.2
            },
            
            # Assists matchup
            'assists_matchup': {
                'player_avg': player_apg,
                'opponent_allows': opponent_profile['assists_allowed'],
                'advantage': 'favorable' if opponent_profile['favorable_for_playmakers'] else 'neutral' if opponent_profile['assists_allowed_vs_avg'] > -0.5 else 'unfavorable',
                'expected_impact': opponent_profile['assists_allowed_vs_avg'] * 0.15
            },
        }
        
        # Add 3s if player shoots them
        if player_3pm > 0.5:
            analysis['threes_matchup'] = {
                'player_avg': player_3pm,
                'opponent_allows': opponent_profile.get('threes_allowed', 0),
                'advantage': 'favorable' if opponent_profile.get('favorable_for_shooters') else 'neutral' if opponent_profile.get('threes_allowed_vs_avg', 0) > -0.3 else 'unfavorable',
                'expected_impact': opponent_profile.get('threes_allowed_vs_avg', 0) * 0.4 if opponent_profile.get('threes_allowed_vs_avg') else 0
            }
        
        return analysis

