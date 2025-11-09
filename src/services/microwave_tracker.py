"""
Microwave Tracker
=================
Track players who heat up quickly - stats in first 3 minutes and first 5 minutes.
Uses per-minute rates and Q1 performance to estimate early game production.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from pathlib import Path
from src.analysis.hot_hand_tracker import HotHandTracker


class MicrowaveTracker:
    """
    Track and analyze players who start hot (first 3 min, first 5 min)
    Factors in opponent shot distribution and player shot preferences
    """
    
    def __init__(self):
        self.hot_hand_tracker = HotHandTracker(blend_mode="latest")
        self._load_game_data()
    
    def _load_game_data(self):
        """Load game-level data to calculate team shot distributions"""
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
    
    def _get_opponent_shot_distribution(self, opponent_team: str) -> Dict:
        """
        Get opponent's defensive shot distribution - what % of shots they allow from each zone
        
        This calculates what opponents shoot AGAINST this team by:
        1. Finding all games where opponent_team played
        2. Getting the OTHER team's stats in those games (what was shot against opponent_team)
        3. Averaging to get shot distribution allowed
        
        Returns:
            Dict with percentages: {'three_point_pct': 0.39, 'paint_pct': 0.35, 'midrange_pct': 0.26}
        """
        if self.games_df is None:
            # Return league averages
            return {
                'three_point_pct': 0.39,  # ~39% of shots are 3s
                'paint_pct': 0.35,        # ~35% are paint
                'midrange_pct': 0.26      # ~26% are midrange
            }
        
        # Get all games where opponent_team played
        opp_team_abbr = opponent_team.upper()
        opp_games = self.games_df[self.games_df['TEAM_ABBREVIATION'] == opp_team_abbr]
        
        if len(opp_games) == 0:
            return {
                'three_point_pct': 0.39,
                'paint_pct': 0.35,
                'midrange_pct': 0.26
            }
        
        # For each game, get the opponent's stats (what was shot AGAINST opponent_team)
        # We need to find the other team in each game
        opponent_shots = []
        
        for _, game_row in opp_games.iterrows():
            game_id = game_row.get('GAME_ID')
            if pd.isna(game_id):
                continue
            
            # Find the OTHER team in this game (the one that shot against opponent_team)
            other_team_game = self.games_df[
                (self.games_df['GAME_ID'] == game_id) & 
                (self.games_df['TEAM_ABBREVIATION'] != opp_team_abbr)
            ]
            
            if len(other_team_game) > 0:
                other_team = other_team_game.iloc[0]
                # This is what opponents shoot against opponent_team
                opponent_shots.append({
                    'FGA': other_team.get('FGA', 0),
                    'FG3A': other_team.get('FG3A', 0),
                    'FG2A': other_team.get('FGA', 0) - other_team.get('FG3A', 0)
                })
        
        if len(opponent_shots) == 0:
            # Fallback: use league averages
            return {
                'three_point_pct': 0.39,
                'paint_pct': 0.35,
                'midrange_pct': 0.26
            }
        
        # Calculate averages of what opponents shoot against this team
        shots_df = pd.DataFrame(opponent_shots)
        avg_fga = shots_df['FGA'].mean()
        avg_fg3a = shots_df['FG3A'].mean()
        avg_fg2a = shots_df['FG2A'].mean()
        
        # Estimate paint vs midrange from 2PA
        # Use defensive rating if available, otherwise use league average split
        # Teams with worse defense typically allow more paint shots
        paint_pct_of_2pa = 0.45  # Conservative estimate (can be refined with DEF_RATING)
        midrange_pct_of_2pa = 0.55
        
        total_shots = avg_fga
        if total_shots == 0:
            return {
                'three_point_pct': 0.39,
                'paint_pct': 0.35,
                'midrange_pct': 0.26
            }
        
        three_point_pct = avg_fg3a / total_shots
        paint_pct = (avg_fg2a * paint_pct_of_2pa) / total_shots
        midrange_pct = (avg_fg2a * midrange_pct_of_2pa) / total_shots
        
        # Normalize to sum to 1.0
        total = three_point_pct + paint_pct + midrange_pct
        if total > 0:
            three_point_pct /= total
            paint_pct /= total
            midrange_pct /= total
        
        return {
            'three_point_pct': three_point_pct,
            'paint_pct': paint_pct,
            'midrange_pct': midrange_pct,
            'fg3a_allowed': avg_fg3a,
            'fga_allowed': avg_fga
        }
    
    def _get_player_shot_distribution(self, player: pd.Series) -> Dict:
        """
        Get player's shot distribution - what % of their shots are from each zone
        
        Returns:
            Dict with percentages: {'three_point_pct': 0.45, 'paint_pct': 0.30, 'midrange_pct': 0.25}
        """
        fga = player.get('FGA', 0)
        fg3a = player.get('FG3A', 0)
        fg2a = fga - fg3a
        
        if fga == 0:
            # Estimate based on player type
            ppg = player.get('PTS', 0)
            if ppg >= 25:
                # Superstars often shoot more 3s
                return {'three_point_pct': 0.40, 'paint_pct': 0.35, 'midrange_pct': 0.25}
            elif ppg >= 18:
                return {'three_point_pct': 0.35, 'paint_pct': 0.40, 'midrange_pct': 0.25}
            else:
                return {'three_point_pct': 0.30, 'paint_pct': 0.45, 'midrange_pct': 0.25}
        
        three_point_pct = fg3a / fga
        
        # Estimate paint vs midrange from 2PA
        # Guards/forwards: more midrange, bigs: more paint
        reb_per_game = player.get('REB', 0)
        if reb_per_game >= 8:
            # Big man - more paint
            paint_pct_of_2pa = 0.60
        elif reb_per_game >= 5:
            # Forward - balanced
            paint_pct_of_2pa = 0.50
        else:
            # Guard - more midrange
            paint_pct_of_2pa = 0.40
        
        paint_pct = (fg2a * paint_pct_of_2pa) / fga if fga > 0 else 0
        midrange_pct = (fg2a * (1 - paint_pct_of_2pa)) / fga if fga > 0 else 0
        
        # Normalize
        total = three_point_pct + paint_pct + midrange_pct
        if total > 0:
            three_point_pct /= total
            paint_pct /= total
            midrange_pct /= total
        
        return {
            'three_point_pct': three_point_pct,
            'paint_pct': paint_pct,
            'midrange_pct': midrange_pct,
            'fg3a': fg3a,
            'fga': fga
        }
    
    def _calculate_shot_matchup_advantage(self, player_dist: Dict, opponent_dist: Dict) -> float:
        """
        Calculate matchup advantage based on shot distribution alignment
        
        Returns multiplier (1.0 = neutral, >1.0 = favorable, <1.0 = unfavorable)
        
        Logic:
        - If player shoots 50% 3s and opponent allows 50% 3s = perfect match (1.15x)
        - If player shoots 20% 3s and opponent allows 50% 3s = less relevant (1.0x)
        - If player shoots 50% 3s and opponent allows 20% 3s = mismatch (0.95x)
        - Weight by how much of player's shots are in each category
        """
        # Calculate alignment for each shot type
        # Alignment = overlap between player's shot % and opponent's allowed %
        # Higher overlap = better match
        
        # For each shot type, calculate how well they align
        # Use the overlap (min) weighted by player's usage of that shot type
        three_overlap = min(player_dist['three_point_pct'], opponent_dist['three_point_pct'])
        paint_overlap = min(player_dist['paint_pct'], opponent_dist['paint_pct'])
        midrange_overlap = min(player_dist['midrange_pct'], opponent_dist['midrange_pct'])
        
        # Weight by player's shot distribution (their primary shot types matter more)
        three_weighted = three_overlap * player_dist['three_point_pct']
        paint_weighted = paint_overlap * player_dist['paint_pct']
        midrange_weighted = midrange_overlap * player_dist['midrange_pct']
        
        # Total weighted alignment (0.0 to 1.0)
        total_alignment = three_weighted + paint_weighted + midrange_weighted
        
        # Also check for mismatches (player's strength vs opponent's weakness)
        # If player shoots 50% 3s but opponent only allows 20% 3s = bad match
        three_mismatch = player_dist['three_point_pct'] - opponent_dist['three_point_pct']
        paint_mismatch = player_dist['paint_pct'] - opponent_dist['paint_pct']
        midrange_mismatch = player_dist['midrange_pct'] - opponent_dist['midrange_pct']
        
        # Penalty for large mismatches in player's primary shot types
        mismatch_penalty = 0.0
        if player_dist['three_point_pct'] > 0.4:  # 3PT specialist
            if three_mismatch > 0.15:  # Player shoots way more 3s than opponent allows
                mismatch_penalty += 0.05
        if player_dist['paint_pct'] > 0.4:  # Paint specialist
            if paint_mismatch > 0.15:  # Player shoots way more paint than opponent allows
                mismatch_penalty += 0.05
        
        # Convert to multiplier
        # Perfect match (high alignment, no mismatch) = 1.15x
        # Good match = 1.10x
        # Neutral = 1.0x
        # Poor match = 0.95x
        base_multiplier = 1.0
        if total_alignment >= 0.20 and mismatch_penalty == 0:  # Strong alignment, no mismatch
            base_multiplier = 1.15
        elif total_alignment >= 0.15 and mismatch_penalty == 0:  # Good alignment
            base_multiplier = 1.10
        elif total_alignment >= 0.12:  # Decent alignment
            base_multiplier = 1.05
        elif total_alignment < 0.08 or mismatch_penalty > 0.05:  # Poor alignment or big mismatch
            base_multiplier = 0.95
        
        matchup_multiplier = base_multiplier - mismatch_penalty
        return max(0.90, min(1.20, matchup_multiplier))  # Clamp between 0.90x and 1.20x
    
    def get_microwave_stats(self, player_name: str, opponent_team: str = None, season: str = '2025-26') -> Optional[Dict]:
        """
        Get microwave stats for a player (first 3 min, first 5 min)
        
        Returns:
            Dict with estimated stats for first 3 min and first 5 min
        """
        player = self.hot_hand_tracker.get_player_baseline(player_name)
        if player is None:
            return None
        
        # Get game log for Q1 analysis
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
        
        # Calculate per-minute rates
        ppg = player.get('PTS', 0)
        rpg = player.get('REB', 0)
        apg = player.get('AST', 0)
        mpg = player.get('MIN', 0)
        fg3m = player.get('FG3M', 0)
        
        if mpg == 0:
            return None
        
        # Per-minute rates
        pts_per_min = ppg / mpg
        reb_per_min = rpg / mpg
        ast_per_min = apg / mpg
        fg3_per_min = fg3m / mpg
        
        # Early game multiplier (players often start hot or cold)
        # Use Q1 data if available, otherwise estimate based on player type
        early_multiplier = self._get_early_game_multiplier(player_name, game_log, pts_per_min)
        
        # Get shot distribution matchup advantage
        player_shot_dist = self._get_player_shot_distribution(player)
        shot_matchup_multiplier = 1.0
        opponent_shot_dist = None
        
        if opponent_team:
            opponent_shot_dist = self._get_opponent_shot_distribution(opponent_team)
            shot_matchup_multiplier = self._calculate_shot_matchup_advantage(
                player_shot_dist, opponent_shot_dist
            )
        
        # Combined multiplier (early game + shot matchup)
        combined_multiplier = early_multiplier * shot_matchup_multiplier
        
        # Estimate first 3 minutes (assuming player is on court)
        # Factor in shot matchup advantage
        first_3_min_pts = pts_per_min * 3 * combined_multiplier
        first_3_min_reb = reb_per_min * 3 * early_multiplier  # Rebounds not affected by shot type
        first_3_min_ast = ast_per_min * 3 * early_multiplier  # Assists not affected by shot type
        first_3_min_3s = fg3_per_min * 3 * combined_multiplier
        
        # Estimate first 5 minutes
        first_5_min_pts = pts_per_min * 5 * combined_multiplier
        first_5_min_reb = reb_per_min * 5 * early_multiplier
        first_5_min_ast = ast_per_min * 5 * early_multiplier
        first_5_min_3s = fg3_per_min * 5 * combined_multiplier
        
        # Calculate microwave score (how hot they start)
        # Higher score = more likely to heat up quickly
        # Factor in scoring opportunities from shot matchup
        base_score = (
            (first_3_min_pts * 2) +  # Points weighted 2x
            (first_3_min_reb * 0.5) +
            (first_3_min_ast * 1) +
            (first_3_min_3s * 1.5)  # 3s weighted higher (quick scoring)
        )
        
        # Bonus for shot matchup advantage
        shot_matchup_bonus = (shot_matchup_multiplier - 1.0) * 2.0  # Up to +0.4 bonus
        microwave_score = base_score * (1.0 + shot_matchup_bonus * 0.1)  # Up to 4% boost
        
        result = {
            'player_name': player_name,
            'team': player.get('TEAM_ABBREVIATION', ''),
            'season_ppg': ppg,
            'season_mpg': mpg,
            'early_multiplier': early_multiplier,
            'shot_matchup_multiplier': shot_matchup_multiplier,
            'combined_multiplier': combined_multiplier,
            'microwave_score': microwave_score,
            'first_3_min': {
                'points': first_3_min_pts,
                'rebounds': first_3_min_reb,
                'assists': first_3_min_ast,
                'threes': first_3_min_3s,
            },
            'first_5_min': {
                'points': first_5_min_pts,
                'rebounds': first_5_min_reb,
                'assists': first_5_min_ast,
                'threes': first_5_min_3s,
            },
            'per_min_rates': {
                'points': pts_per_min,
                'rebounds': reb_per_min,
                'assists': ast_per_min,
                'threes': fg3_per_min,
            },
            'player_shot_distribution': player_shot_dist,
        }
        
        if opponent_shot_dist:
            result['opponent_shot_distribution'] = opponent_shot_dist
        
        return result
    
    def _get_early_game_multiplier(self, player_name: str, game_log: Optional[pd.DataFrame], 
                                    pts_per_min: float) -> float:
        """
        Estimate how player performs in early game vs average
        Returns multiplier (1.0 = average, >1.0 = starts hot, <1.0 = starts cold)
        """
        # Base multiplier based on player archetype
        if pts_per_min >= 0.7:  # High scorers (25+ ppg)
            base_multiplier = 1.15  # Superstars often start hot
        elif pts_per_min >= 0.5:  # Good scorers (18+ ppg)
            base_multiplier = 1.10
        elif pts_per_min >= 0.35:  # Role players (12+ ppg)
            base_multiplier = 1.05
        else:
            base_multiplier = 1.0
        
        # If we have Q1 data, use it to adjust
        if game_log is not None and len(game_log) > 0:
            # Estimate Q1 performance from game log
            # We don't have Q1 data directly, but we can use first quarter tendencies
            # For now, use base multiplier
            # TODO: If Q1 data becomes available, use it here
            pass
        
        return base_multiplier
    
    def get_all_microwave_players(self, predictions_df: pd.DataFrame, 
                                   season: str = '2025-26') -> pd.DataFrame:
        """
        Get microwave stats for all players in predictions
        
        Returns DataFrame sorted by microwave score (highest first)
        """
        results = []
        
        # Get unique players
        players = predictions_df['player_name'].unique()
        
        for player_name in players:
            try:
                # Get opponent from predictions
                player_preds = predictions_df[predictions_df['player_name'] == player_name]
                opponent = None
                if len(player_preds) > 0:
                    pred_row = player_preds.iloc[0]
                    opponent = pred_row.get('opponent', '')
                
                # Get microwave stats with opponent context
                stats = self.get_microwave_stats(player_name, opponent_team=opponent, season=season)
                if stats:
                    # Add prediction info if available
                    if len(player_preds) > 0:
                        pred_row = player_preds.iloc[0]
                        stats['opponent'] = opponent
                        stats['team'] = pred_row.get('team', stats.get('team', ''))
                        stats['expected_minutes'] = pred_row.get('minutes', stats.get('season_mpg', 0))
                        stats['pred_points'] = pred_row.get('pred_points', 0)
                        stats['pred_rebounds'] = pred_row.get('pred_rebounds', 0)
                        stats['pred_assists'] = pred_row.get('pred_assists', 0)
                    
                    results.append(stats)
            except Exception as e:
                # Skip players with errors
                continue
        
        if not results:
            return pd.DataFrame()
        
        # Expand nested dicts for easier DataFrame creation
        expanded_results = []
        for result in results:
            expanded = {
                'player_name': result['player_name'],
                'team': result.get('team', ''),
                'opponent': result.get('opponent', ''),
                'season_ppg': result['season_ppg'],
                'season_mpg': result['season_mpg'],
                'early_multiplier': result['early_multiplier'],
                'shot_matchup_multiplier': result.get('shot_matchup_multiplier', 1.0),
                'combined_multiplier': result.get('combined_multiplier', result['early_multiplier']),
                'microwave_score': result['microwave_score'],
                'expected_minutes': result.get('expected_minutes', result['season_mpg']),
                'pred_points': result.get('pred_points', 0),
                'pred_rebounds': result.get('pred_rebounds', 0),
                'pred_assists': result.get('pred_assists', 0),
            }
            
            # Add shot distribution data
            if 'player_shot_distribution' in result:
                psd = result['player_shot_distribution']
                expanded['player_3pt_pct'] = psd.get('three_point_pct', 0)
                expanded['player_paint_pct'] = psd.get('paint_pct', 0)
                expanded['player_midrange_pct'] = psd.get('midrange_pct', 0)
            
            if 'opponent_shot_distribution' in result:
                osd = result['opponent_shot_distribution']
                expanded['opp_3pt_pct_allowed'] = osd.get('three_point_pct', 0)
                expanded['opp_paint_pct_allowed'] = osd.get('paint_pct', 0)
                expanded['opp_midrange_pct_allowed'] = osd.get('midrange_pct', 0)
            # Expand first_3_min
            for stat in ['points', 'rebounds', 'assists', 'threes']:
                expanded[f'first_3_min_{stat}'] = result['first_3_min'].get(stat, 0)
            # Expand first_5_min
            for stat in ['points', 'rebounds', 'assists', 'threes']:
                expanded[f'first_5_min_{stat}'] = result['first_5_min'].get(stat, 0)
            # Expand per_min_rates
            for stat in ['points', 'rebounds', 'assists', 'threes']:
                expanded[f'per_min_{stat}'] = result['per_min_rates'].get(stat, 0)
            
            expanded_results.append(expanded)
        
        df = pd.DataFrame(expanded_results)
        # Sort by microwave score (highest first)
        df = df.sort_values('microwave_score', ascending=False)
        
        return df
    
    def get_microwave_leaderboard(self, predictions_df: pd.DataFrame, 
                                   stat_type: str = 'points',
                                   time_window: str = '3min',
                                   season: str = '2025-26') -> pd.DataFrame:
        """
        Get leaderboard of players by microwave stats
        
        Args:
            stat_type: 'points', 'rebounds', 'assists', 'threes'
            time_window: '3min' or '5min'
        
        Returns:
            DataFrame sorted by stat in time window
        """
        df = self.get_all_microwave_players(predictions_df, season=season)
        
        if len(df) == 0:
            return pd.DataFrame()
        
        # Extract stat from nested dict
        time_key = 'first_3_min' if time_window == '3min' else 'first_5_min'
        stat_key = stat_type if stat_type != 'threes' else 'threes'
        
        if time_key in df.columns:
            # If it's already expanded, use directly
            col_name = f'{time_key}_{stat_key}'
            if col_name in df.columns:
                df = df.sort_values(col_name, ascending=False)
        else:
            # Need to expand nested dict
            df[f'{time_key}_{stat_key}'] = df.apply(
                lambda row: row.get(time_key, {}).get(stat_key, 0) if isinstance(row.get(time_key), dict) else 0,
                axis=1
            )
            df = df.sort_values(f'{time_key}_{stat_key}', ascending=False)
        
        return df

