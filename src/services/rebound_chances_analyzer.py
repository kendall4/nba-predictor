"""
Rebound Chances Analyzer
=========================
Calculate comprehensive rebound chances for players based on:
- Opposing team's 3-point attempts per game
- Opposing team's shooting percentage
- Opposing team's paint touches (estimated from 2PA and paint attempts)
- Team pace (more possessions = more rebound opportunities)
- Player's rebounding rate and minutes
- Opponent's defensive rebounding percentage
- Player's matchup positioning
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
from src.analysis.hot_hand_tracker import HotHandTracker
from src.services.team_stats_analyzer import TeamStatsAnalyzer


class ReboundChancesAnalyzer:
    """
    Analyze rebound chances for players considering all relevant factors
    """
    
    def __init__(self):
        try:
            self.hot_hand_tracker = HotHandTracker(blend_mode="latest")
            self.team_analyzer = TeamStatsAnalyzer()
            self._load_team_data()
            self._load_game_data()
        except Exception as e:
            # Store error for debugging
            self._init_error = str(e)
            raise
    
    def _load_team_data(self):
        """Load team statistics"""
        current_season = '2025-26'
        prev_season = '2024-25'
        
        try:
            # Load team pace stats
            team_file = Path(f'data/raw/team_pace_{current_season}.csv')
            if not team_file.exists():
                team_file = Path(f'data/raw/team_pace_{prev_season}.csv')
            
            if team_file.exists():
                self.team_stats = pd.read_csv(team_file)
                # Filter to NBA teams only
                nba_team_ids = list(range(1610612737, 1610612767))
                if 'TEAM_ID' in self.team_stats.columns:
                    self.team_stats = self.team_stats[self.team_stats['TEAM_ID'].isin(nba_team_ids)]
            else:
                self.team_stats = None
        except Exception as e:
            print(f"Warning: Could not load team stats: {e}")
            self.team_stats = None
    
    def _load_game_data(self):
        """Load game-level data to calculate team averages"""
        current_season = '2025-26'
        prev_season = '2024-25'
        
        try:
            game_file = Path(f'data/raw/games_{current_season}.csv')
            if not game_file.exists():
                game_file = Path(f'data/raw/games_{prev_season}.csv')
            
            if game_file.exists():
                self.games_df = pd.read_csv(game_file)
                # Filter to NBA teams
                nba_teams = [
                    'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET',
                    'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN',
                    'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS',
                    'TOR', 'UTA', 'WAS'
                ]
                self.games_df = self.games_df[self.games_df['TEAM_ABBREVIATION'].isin(nba_teams)]
            else:
                self.games_df = None
        except Exception as e:
            print(f"Warning: Could not load game data: {e}")
            self.games_df = None
    
    def _get_team_shooting_stats(self, team_abbr: str) -> Dict:
        """Get team's shooting statistics from game data"""
        if self.games_df is None:
            return {}
        
        team_games = self.games_df[self.games_df['TEAM_ABBREVIATION'] == team_abbr.upper()]
        if len(team_games) == 0:
            return {}
        
        # Calculate averages
        stats = {
            'fg3a_per_game': team_games['FG3A'].mean() if 'FG3A' in team_games.columns else 35.0,  # League avg ~35
            'fg_pct': team_games['FG_PCT'].mean() if 'FG_PCT' in team_games.columns else 0.45,  # League avg ~45%
            'fg3_pct': team_games['FG3_PCT'].mean() if 'FG3_PCT' in team_games.columns else 0.36,  # League avg ~36%
            'fga_per_game': team_games['FGA'].mean() if 'FGA' in team_games.columns else 90.0,
            'fgm_per_game': team_games['FGM'].mean() if 'FGM' in team_games.columns else 40.0,
            'fg3m_per_game': team_games['FG3M'].mean() if 'FG3M' in team_games.columns else 12.5,
        }
        
        # Estimate 2-point attempts (total FGA - 3PA)
        stats['fg2a_per_game'] = stats['fga_per_game'] - stats['fg3a_per_game']
        stats['fg2m_per_game'] = stats['fgm_per_game'] - stats['fg3m_per_game']
        
        # Estimate paint touches (roughly 40-50% of 2PA are in the paint)
        # Big men get more paint touches, guards get fewer
        stats['estimated_paint_touches'] = stats['fg2a_per_game'] * 0.45  # Conservative estimate
        
        return stats
    
    def _get_opponent_team_stats(self, opponent_team: str) -> Dict:
        """Get opponent team's defensive and shooting statistics"""
        if self.team_stats is None:
            return {}
        
        # Find team in stats
        team_abbr = opponent_team.upper()
        team_row = None
        
        if 'TEAM_ABBREVIATION' in self.team_stats.columns:
            team_row = self.team_stats[self.team_stats['TEAM_ABBREVIATION'] == team_abbr]
        
        if team_row is None or len(team_row) == 0:
            # Try team name mapping
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
            return {}
        
        team = team_row.iloc[0]
        
        # Get opponent's shooting stats from game data
        opponent_shooting = self._get_team_shooting_stats(team_abbr)
        
        stats = {
            'pace': float(team.get('PACE', 98.0)),  # League avg ~98
            'def_rating': float(team.get('DEF_RATING', 112.0)),
            'dreb_pct': float(team.get('DREB_PCT', 0.73)),  # Defensive rebounding percentage
            'oreb_pct': float(team.get('OREB_PCT', 0.27)),  # Offensive rebounding percentage
            'efg_pct': float(team.get('EFG_PCT', 0.54)),  # Effective field goal percentage
        }
        
        # Merge with shooting stats
        stats.update(opponent_shooting)
        
        return stats
    
    def calculate_rebound_chances(self, player_name: str, opponent_team: str, 
                                   expected_minutes: float = None, 
                                   season: str = '2025-26') -> Optional[Dict]:
        """
        Calculate comprehensive rebound chances for a player
        
        Factors considered:
        1. Opponent's 3-point attempts (more 3s = longer rebounds, more opportunities)
        2. Opponent's shooting percentage (lower % = more misses = more rebounds)
        3. Opponent's paint touches (more paint attempts = more contested rebounds)
        4. Player's rebounding rate per minute
        5. Opponent's defensive rebounding percentage (lower = more opportunities)
        6. Team pace (higher pace = more possessions = more rebounds)
        7. Expected minutes played
        """
        # Get player baseline stats
        player = self.hot_hand_tracker.get_player_baseline(player_name)
        if player is None:
            return None
        
        # Get player's game log for recent rebounding rate
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
        if game_log is not None and len(game_log) > 0:
            recent = game_log.head(10)
            avg_reb = recent['REB'].mean() if 'REB' in recent.columns else player.get('REB', 0)
            avg_min = recent['MIN'].mean() if 'MIN' in recent.columns else player.get('MIN', 0)
            reb_per_min = avg_reb / avg_min if avg_min > 0 else 0
        else:
            avg_reb = player.get('REB', 0)
            avg_min = player.get('MIN', 0)
            reb_per_min = avg_reb / avg_min if avg_min > 0 else 0
        
        # Use expected minutes if provided, otherwise use player's average
        if expected_minutes is None:
            expected_minutes = avg_min
        
        # Get opponent team stats
        opponent_stats = self._get_opponent_team_stats(opponent_team)
        if not opponent_stats:
            # Fallback to league averages
            opponent_stats = {
                'pace': 98.0,
                'fg3a_per_game': 35.0,
                'fg_pct': 0.45,
                'fg3_pct': 0.36,
                'dreb_pct': 0.73,
                'estimated_paint_touches': 25.0,
            }
        
        # Base rebound chances calculation
        # Start with player's rebounding rate per minute
        base_chances_per_min = reb_per_min * 2.0  # Conservative: 2x actual rebounds = opportunities
        
        # Factor 1: Opponent's 3-point attempts
        # More 3s = longer rebounds, more opportunities for perimeter players
        # But also more makes = fewer rebounds
        # Net effect: Higher 3PA = slightly more opportunities (long rebounds)
        league_avg_3pa = 35.0
        fg3a_factor = 1.0 + (opponent_stats['fg3a_per_game'] - league_avg_3pa) / league_avg_3pa * 0.15
        
        # Factor 2: Opponent's shooting percentage
        # Lower shooting % = more misses = more rebounds
        league_avg_fg_pct = 0.45
        shooting_factor = 1.0 + (league_avg_fg_pct - opponent_stats['fg_pct']) / league_avg_fg_pct * 0.25
        
        # Factor 3: Opponent's paint touches
        # More paint attempts = more contested rebounds in paint area
        # Big men benefit more from this
        league_avg_paint_touches = 25.0
        paint_factor = 1.0 + (opponent_stats.get('estimated_paint_touches', league_avg_paint_touches) - league_avg_paint_touches) / league_avg_paint_touches * 0.20
        
        # Factor 4: Opponent's defensive rebounding percentage
        # Lower DREB% = opponent allows more rebounds = more opportunities
        league_avg_dreb_pct = 0.73
        dreb_factor = 1.0 + (league_avg_dreb_pct - opponent_stats['dreb_pct']) / league_avg_dreb_pct * 0.30
        
        # Factor 5: Pace
        # Higher pace = more possessions = more rebound opportunities
        league_avg_pace = 98.0
        pace_factor = opponent_stats['pace'] / league_avg_pace
        
        # Combine all factors
        adjusted_chances_per_min = base_chances_per_min * fg3a_factor * shooting_factor * paint_factor * dreb_factor * pace_factor
        
        # Calculate total expected chances
        expected_chances = adjusted_chances_per_min * expected_minutes
        
        # Player position factor (big men get more opportunities)
        # Estimate from rebounds per game
        if avg_reb >= 8:
            position_factor = 1.15  # Big men
        elif avg_reb >= 5:
            position_factor = 1.05  # Forwards
        else:
            position_factor = 1.0  # Guards
        
        final_chances = expected_chances * position_factor
        
        return {
            'player_name': player_name,
            'opponent': opponent_team,
            'expected_minutes': expected_minutes,
            'reb_per_min': reb_per_min,
            'rebound_chances': final_chances,
            'base_chances_per_min': base_chances_per_min,
            'adjusted_chances_per_min': adjusted_chances_per_min,
            'factors': {
                'fg3a_factor': fg3a_factor,
                'shooting_factor': shooting_factor,
                'paint_factor': paint_factor,
                'dreb_factor': dreb_factor,
                'pace_factor': pace_factor,
                'position_factor': position_factor,
            },
            'opponent_stats': {
                'fg3a_per_game': opponent_stats.get('fg3a_per_game', 0),
                'fg_pct': opponent_stats.get('fg_pct', 0),
                'estimated_paint_touches': opponent_stats.get('estimated_paint_touches', 0),
                'dreb_pct': opponent_stats.get('dreb_pct', 0),
                'pace': opponent_stats.get('pace', 0),
            },
            'conversion_rate': reb_per_min / adjusted_chances_per_min if adjusted_chances_per_min > 0 else 0
        }
    
    def analyze_all_players(self, predictions_df: pd.DataFrame, season: str = '2025-26') -> pd.DataFrame:
        """
        Analyze rebound chances for all players in predictions
        
        Returns DataFrame sorted by rebound chances (highest first)
        """
        results = []
        
        # Check required columns
        required_cols = ['player_name', 'opponent']
        missing_cols = [col for col in required_cols if col not in predictions_df.columns]
        if missing_cols:
            print(f"Warning: Missing columns in predictions: {missing_cols}")
            return pd.DataFrame()
        
        total_players = len(predictions_df)
        processed = 0
        errors = 0
        
        for idx, row in predictions_df.iterrows():
            player_name = row.get('player_name')
            opponent = row.get('opponent')
            expected_minutes = row.get('minutes', 30.0)
            
            # Skip if missing critical data
            if pd.isna(player_name) or pd.isna(opponent) or not player_name or not opponent:
                continue
            
            # Ensure opponent is string and uppercase
            opponent = str(opponent).upper().strip()
            
            try:
                chances = self.calculate_rebound_chances(
                    player_name=player_name,
                    opponent_team=opponent,
                    expected_minutes=float(expected_minutes) if not pd.isna(expected_minutes) else 30.0,
                    season=season
                )
                processed += 1
            except Exception as e:
                # Skip players with errors (invalid opponent, missing data, etc.)
                errors += 1
                # Only print every 10th error to avoid spam
                if errors <= 5 or errors % 10 == 0:
                    print(f"Warning: Skipped {player_name} vs {opponent}: {str(e)[:50]}")
                continue
            
            if chances:
                # Add player info from predictions
                result = {
                    'player_name': player_name,
                    'team': row.get('team', ''),
                    'opponent': opponent,
                    'expected_minutes': float(expected_minutes) if not pd.isna(expected_minutes) else 30.0,
                    'rebound_chances': chances['rebound_chances'],
                    'reb_per_min': chances['reb_per_min'],
                    'pred_rebounds': float(row.get('pred_rebounds', 0)) if not pd.isna(row.get('pred_rebounds')) else 0,
                    'line_rebounds': float(row.get('line_rebounds', 0)) if not pd.isna(row.get('line_rebounds')) else 0,
                    'overall_value': float(row.get('overall_value', 0)) if not pd.isna(row.get('overall_value')) else 0,
                    # Factors
                    'opp_3pa_per_game': chances['opponent_stats']['fg3a_per_game'],
                    'opp_shooting_pct': chances['opponent_stats']['fg_pct'],
                    'opp_paint_touches': chances['opponent_stats']['estimated_paint_touches'],
                    'opp_dreb_pct': chances['opponent_stats']['dreb_pct'],
                    'opp_pace': chances['opponent_stats']['pace'],
                    # Factor multipliers
                    'fg3a_factor': chances['factors']['fg3a_factor'],
                    'shooting_factor': chances['factors']['shooting_factor'],
                    'paint_factor': chances['factors']['paint_factor'],
                    'dreb_factor': chances['factors']['dreb_factor'],
                    'pace_factor': chances['factors']['pace_factor'],
                    'position_factor': chances['factors']['position_factor'],
                }
                results.append(result)
        
        if not results:
            print(f"Warning: No valid rebound chances calculated. Processed: {processed}, Errors: {errors}")
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        # Sort by rebound chances (highest first)
        df = df.sort_values('rebound_chances', ascending=False)
        
        print(f"Rebound chances analysis complete: {len(df)} players processed successfully")
        
        return df

