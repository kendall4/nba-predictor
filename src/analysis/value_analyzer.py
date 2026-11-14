import pandas as pd
import sys
import os
sys.path.append('src')
from features.matchup_features import MatchupFeatureBuilder
from services.odds_manager import OddsManager

class ValueAnalyzer:
    """
    Find VALUE PLAYS:
    - Compare our predictions vs Vegas odds lines
    - Find players we predict to BEAT their over/under
    """
    
    _builder = None

    def __init__(self, force_reload: bool = False, builder=None):
        if builder is not None:
            self.builder = builder
            ValueAnalyzer._builder = builder
        elif ValueAnalyzer._builder is None or force_reload:
            ValueAnalyzer._builder = MatchupFeatureBuilder(blend_mode="latest")
            self.builder = ValueAnalyzer._builder
        else:
            self.builder = ValueAnalyzer._builder
    
    def analyze_games(self, games_today, odds_lines=None, target_date=None, system_fit_weight: float = 0.0,
                     recent_form_weight: float = 0.0, h2h_weight: float = 0.0,
                     rest_days_weight: float = 0.0, home_away_weight: float = 0.0,
                     play_style_weight: float = 0.0, upside_weight: float = 0.0,
                     apply_teammate_absence: bool = True,
                     apply_historical_teammate_nudge: bool = True):
        """
        Analyze all players in today's games
        
        Args:
            games_today: [{'home': 'LAL', 'away': 'GSW'}, ...]
            odds_lines: {'Luka Dončić': {'points': 28.5, 'rebounds': 8.5}, ...}
            target_date: datetime.date object for the target date (None = today)
            system_fit_weight: Weight for system fit adjustment (0.0 = disabled, 1.0 = full weight)
            recent_form_weight: Weight for recent form (last 5 games) adjustment
            h2h_weight: Weight for head-to-head performance adjustment
            apply_teammate_absence / apply_historical_teammate_nudge: injury vacuum nudges
                (historical path hits stats.nba.com gamelogs — disable when API is down)
        """
        
        # Get predictions for all players
        predictions = self.builder.get_all_matchups(
            games_today, 
            system_fit_weight=system_fit_weight,
            recent_form_weight=recent_form_weight,
            h2h_weight=h2h_weight,
            rest_days_weight=rest_days_weight,
            home_away_weight=home_away_weight,
            play_style_weight=play_style_weight,
            upside_weight=upside_weight,
            apply_teammate_absence=apply_teammate_absence,
            apply_historical_teammate_nudge=apply_historical_teammate_nudge,
        )
        
        # If no odds provided, try to fetch real odds from API/cache
        if odds_lines is None:
            odds_lines = self._fetch_real_odds(target_date=target_date)
            
            # If still no odds, fall back to season averages (but warn user)
            if not odds_lines:
                print("⚠️  No real odds available - using season averages as fallback")
                print("   💡 To get real odds: Set ODDS_API_KEY in .env or Streamlit secrets")
                odds_lines = {}
                for _, player in predictions.iterrows():
                    odds_lines[player['player_name']] = {
                        'points': player['season_ppg'],
                        'rebounds': player['season_rpg'],
                        'assists': player['season_apg'],
                        'threes': float(player.get('season_3pg', player.get('FG3M', 0)) or 0),
                    }
            else:
                print(f"✅ Using real odds from API/cache for {len(odds_lines)} players")
        
        # Calculate value scores
        values = []
        debug_count = 0
        for _, player in predictions.iterrows():
            name = player['player_name']
            
            # Get odds for this player (use season averages as fallback if not in odds_lines)
            if name in odds_lines:
                odds = odds_lines[name]
                has_real_odds = True
            else:
                # Player not in odds - use season averages as fallback for display
                odds = {
                    'points': player['season_ppg'],
                    'rebounds': player['season_rpg'],
                    'assists': player['season_apg'],
                    'threes': float(player.get('season_3pg', player.get('FG3M', 0)) or 0),
                }
                has_real_odds = False
            
            # Calculate value: how much we predict OVER the line
            # Only calculate value for stats where we have REAL odds (not season averages)
            point_value = 0.0
            reb_value = 0.0
            ast_value = 0.0
            thr_value = 0.0
            point_weight = 0.0
            reb_weight = 0.0
            ast_weight = 0.0
            thr_weight = 0.0
            
            if has_real_odds and 'points' in odds:
                point_value = player['predicted_points'] - odds['points']
                point_weight = 2.0  # Points worth 2x
            if has_real_odds and 'rebounds' in odds:
                reb_value = player['predicted_rebounds'] - odds['rebounds']
                reb_weight = 1.0
            if has_real_odds and 'assists' in odds:
                ast_value = player['predicted_assists'] - odds['assists']
                ast_weight = 1.5  # Assists worth 1.5x
            pred_thr = float(player.get('predicted_threes', 0) or 0)
            if has_real_odds and 'threes' in odds:
                thr_value = pred_thr - float(odds['threes'])
                thr_weight = 1.2
            
            # Calculate overall_value only from stats we have real odds for
            # If no real odds at all, set to 0 (neutral, don't skip player)
            total_weight = point_weight + reb_weight + ast_weight + thr_weight
            if total_weight > 0:
                # Scale to maintain similar value ranges
                overall_value = (
                    point_value * point_weight +
                    reb_value * reb_weight +
                    ast_value * ast_weight +
                    thr_value * thr_weight
                ) * (5.7 / total_weight)  # 5.7 = prior 4.5 + threes weight slot (~1.2)
            else:
                # No real odds available - set to 0 (neutral value, include player)
                overall_value = 0.0
            
            # Debug: Show value calculation for first few players
            if debug_count < 5:
                try:
                    print(f"\n💰 DEBUG Value for {name}:")
                    print(f"   Predicted: PTS={player['predicted_points']:.1f}, REB={player['predicted_rebounds']:.1f}, AST={player['predicted_assists']:.1f}")
                    pts_line = odds.get('points', 'N/A')
                    reb_line = odds.get('rebounds', 'N/A')
                    ast_line = odds.get('assists', 'N/A')
                    thr_line = odds.get('threes', 'N/A')
                    print(f"   Odds Line: PTS={pts_line}, REB={reb_line}, AST={ast_line}, 3PM={thr_line}")
                    print(
                        f"   Value: PTS={point_value:.2f}, REB={reb_value:.2f}, AST={ast_value:.2f}, 3PM={thr_value:.2f}"
                    )
                    print(f"   Overall Value: {overall_value:.2f}")
                except (BrokenPipeError, OSError):
                    pass
                debug_count += 1
            
            _rec = {
                'player_name': name,
                'team': player['team'],
                'opponent': player['opponent'],
                
                # Predictions
                'pred_points': player['predicted_points'],
                'pred_rebounds': player['predicted_rebounds'],
                'pred_assists': player['predicted_assists'],
                'pred_threes': player.get('predicted_threes', 0.0),
                'pred_steals': player.get('predicted_steals', 0.0),
                'pred_blocks': player.get('predicted_blocks', 0.0),
                'pred_turnovers': player.get('predicted_turnovers', 0.0),
                
                # Lines (use season avg as fallback for display, but value calc only uses real odds)
                'line_points': odds.get('points', player['season_ppg']),
                'line_rebounds': odds.get('rebounds', player['season_rpg']),
                'line_assists': odds.get('assists', player['season_apg']),
                'line_threes': odds.get(
                    'threes',
                    float(player.get('season_3pg', player.get('FG3M', 0)) or 0),
                ),
                # For calibration: True only when this stat's line came from the book, not season fallback
                'line_points_is_book': bool(has_real_odds and 'points' in odds),
                'line_rebounds_is_book': bool(has_real_odds and 'rebounds' in odds),
                'line_assists_is_book': bool(has_real_odds and 'assists' in odds),
                'line_threes_is_book': bool(has_real_odds and 'threes' in odds),
                
                # Value scores (positive = bet OVER, negative = bet UNDER)
                # These are the PRIMARY metrics - separate for each stat
                'point_value': point_value,
                'rebound_value': reb_value,
                'assist_value': ast_value,
                'threes_value': thr_value,
                
                # Overall value (weighted combination, kept for backward compatibility)
                'overall_value': overall_value,
                
                # Context
                'opponent_def_rating': player['opponent_def_rating'],
                'expected_pace': player['expected_pace'],
                'minutes': player['minutes'],
                
                # System fit data (if available)
                'system_fit_multiplier': player.get('system_fit_multiplier', 1.0),
                'offensive_fit': player.get('offensive_fit', 1.0),
                'defensive_matchup': player.get('defensive_matchup', 1.0),
                'recent_form_multiplier': player.get('recent_form_multiplier', 1.0),
                'h2h_multiplier': player.get('h2h_multiplier', 1.0),
                
                # New weight factors (if available)
                'rest_days_multiplier': player.get('rest_days_multiplier', 1.0),
                'home_away_multiplier': player.get('home_away_multiplier', 1.0),
                'play_style_multiplier': player.get('play_style_multiplier', 1.0),
                'upside_points_multiplier': player.get('upside_points_multiplier', 1.0),
                'upside_rebounds_multiplier': player.get('upside_rebounds_multiplier', 1.0),
                'upside_assists_multiplier': player.get('upside_assists_multiplier', 1.0),
                
                # Additional info (for detailed views)
                'rest_days_info': player.get('rest_days_info'),
                'home_away_info': player.get('home_away_info'),
                'play_style_info': player.get('play_style_info'),
                'upside_info': player.get('upside_info'),
                # Opponent glass + shot-profile adjustments (see opponent_context_adjustments)
                'rebound_context_mult': player.get('rebound_context_mult', 1.0),
                'scoring_context_mult': player.get('scoring_context_mult', 1.0),
                'threes_context_mult': player.get('threes_context_mult', 1.0),
                'paint_profile_index': player.get('paint_profile_index', 0.0),
                'perimeter_profile_index': player.get('perimeter_profile_index', 0.0),
                'shot_zone_pts_mult': player.get('shot_zone_pts_mult', 1.0),
                'shot_zone_threes_mult': player.get('shot_zone_threes_mult', 1.0),
                'shot_zones_active': bool(
                    (player.get('shot_zone_meta') or {}).get('shot_zones_active', False)
                ),
                'player_ts_pct': player.get('player_ts_pct'),
                'player_efg_pct': player.get('player_efg_pct'),
                'player_three_point_ar': player.get('player_three_point_ar'),
                'player_ft_rate': player.get('player_ft_rate'),
                'efficiency_context_mult': player.get('efficiency_context_mult', 1.0),
                # Teammate absence (star OUT vacuum) — main preds already mildly adjusted in matchup builder
                'key_teammates_out': player.get('key_teammates_out', '') or '',
                'teammate_absence_pts_mult': float(player.get('teammate_absence_pts_mult', 1.0) or 1.0),
                'star_teammates_out_count': int(player.get('star_teammates_out_count', 0) or 0),
                'pred_points_absence_emphasis': float(player.get('pred_points_absence_emphasis', player.get('predicted_points', 0)) or 0),
                'pred_rebounds_absence_emphasis': float(player.get('pred_rebounds_absence_emphasis', player.get('predicted_rebounds', 0)) or 0),
                'pred_assists_absence_emphasis': float(player.get('pred_assists_absence_emphasis', player.get('predicted_assists', 0)) or 0),
                'hist_teammate_out_pts_mult': float(player.get('hist_teammate_out_pts_mult', 1.0) or 1.0),
                'hist_teammate_out_ast_mult': float(player.get('hist_teammate_out_ast_mult', 1.0) or 1.0),
                'hist_teammate_out_note': player.get('hist_teammate_out_note', '') or '',
            }
            for _pk, _pv in player.items():
                if isinstance(_pk, str) and _pk.startswith("api_"):
                    _rec[_pk] = _pv
            values.append(_rec)
        
        if len(values) == 0:
            # Return empty DataFrame with expected columns if no values
            return pd.DataFrame(columns=[
                'player_name', 'team', 'opponent', 'pred_points', 'pred_rebounds', 'pred_assists',
                'pred_threes',
                'line_points', 'line_rebounds', 'line_assists', 'line_threes',
                'line_points_is_book', 'line_rebounds_is_book', 'line_assists_is_book', 'line_threes_is_book',
                'point_value', 'rebound_value',
                'assist_value', 'threes_value', 'overall_value', 'opponent_def_rating', 'expected_pace', 'minutes',
                'system_fit_multiplier', 'offensive_fit', 'defensive_matchup', 'recent_form_multiplier',
                'h2h_multiplier', 'rest_days_multiplier', 'home_away_multiplier', 'play_style_multiplier',
                'upside_points_multiplier', 'upside_rebounds_multiplier', 'upside_assists_multiplier',
                'rest_days_info', 'home_away_info', 'play_style_info', 'upside_info',
                'rebound_context_mult', 'scoring_context_mult', 'threes_context_mult',
                'paint_profile_index', 'perimeter_profile_index',
                'shot_zone_pts_mult', 'shot_zone_threes_mult', 'shot_zones_active',
                'player_ts_pct', 'player_efg_pct', 'player_three_point_ar', 'player_ft_rate',
                'efficiency_context_mult',
                'key_teammates_out', 'teammate_absence_pts_mult', 'star_teammates_out_count',
                'pred_points_absence_emphasis', 'pred_rebounds_absence_emphasis', 'pred_assists_absence_emphasis',
                'hist_teammate_out_pts_mult', 'hist_teammate_out_ast_mult', 'hist_teammate_out_note',
            ])
        
        df = pd.DataFrame(values)
        
        # Debug: Show overall_value distribution
        if len(df) > 0 and 'overall_value' in df.columns:
            try:
                print(f"\n📊 Value Distribution Summary:")
                print(f"   Total players: {len(df)}")
                print(f"   Positive value: {len(df[df['overall_value'] > 0])} players")
                print(f"   Value >= 0: {len(df[df['overall_value'] >= 0])} players")
                print(f"   Value >= -2: {len(df[df['overall_value'] >= -2.0])} players")
                print(f"   Value >= -5: {len(df[df['overall_value'] >= -5.0])} players")
                print(f"   Min value: {df['overall_value'].min():.2f}")
                print(f"   Max value: {df['overall_value'].max():.2f}")
                print(f"   Mean value: {df['overall_value'].mean():.2f}")
                print(f"   Median value: {df['overall_value'].median():.2f}")
            except (BrokenPipeError, OSError):
                pass
        
        if 'overall_value' in df.columns:
            return df.sort_values('overall_value', ascending=False)
        else:
            return df
    
    def _fetch_real_odds(self, target_date=None) -> dict:
        """
        Fetch real odds using OddsManager (centralized, cached)
        
        Args:
            target_date: datetime.date object for the target date (None = today)
        
        Returns:
            dict: {player_name: {'points': line, 'rebounds': line, 'assists': line}, ...}
            Empty dict if no odds available
        """
        try:
            # Use OddsManager for centralized caching and quota management
            manager = OddsManager()
            odds_lines = manager.get_odds_dict(force_refresh=False, target_date=target_date)
            return odds_lines
        except Exception as e:
            # If anything fails, return empty dict (will fall back to season averages)
            try:
                print(f"⚠️  Error fetching real odds: {e}")
            except (BrokenPipeError, OSError):
                pass
            return {}
    
    def get_top_values(self, games_today, min_value=2.0, top_n=10):
        """Get the best value plays"""
        
        all_values = self.analyze_games(games_today)
        
        # Filter for significant value
        top_values = all_values[all_values['overall_value'] >= min_value].head(top_n)
        
        return top_values


# Test it
if __name__ == "__main__":
    print("=" * 70)
    print("💎 VALUE ANALYZER - Find the Best Bets!")
    print("=" * 70)
    
    analyzer = ValueAnalyzer()
    
    # Example: Lakers vs Warriors, Celtics vs Heat
    games = [
        {'home': 'LAL', 'away': 'GSW'},
        {'home': 'BOS', 'away': 'MIA'}
    ]
    
    print("\n🎯 Analyzing all players in today's games...")
    values = analyzer.get_top_values(games, min_value=0.0, top_n=10)
    
    print(f"\n💎 TOP 10 VALUE PLAYS:\n")
    print("=" * 70)
    
    for idx, player in values.iterrows():
        print(f"\n{idx+1}. {player['player_name']} ({player['team']} vs {player['opponent']})")
        print(f"   Minutes: {player['minutes']:.1f}")
        print(f"   Opponent DEF: {player['opponent_def_rating']:.1f} | Pace: {player['expected_pace']:.1f}")
        print(f"   ")
        print(f"   POINTS:  Pred {player['pred_points']:.1f} vs Line {player['line_points']:.1f} → {player['point_value']:+.1f}")
        print(f"   REBOUNDS: Pred {player['pred_rebounds']:.1f} vs Line {player['line_rebounds']:.1f} → {player['rebound_value']:+.1f}")
        print(f"   ASSISTS: Pred {player['pred_assists']:.1f} vs Line {player['line_assists']:.1f} → {player['assist_value']:+.1f}")
        print(f"   ")
        print(f"   💰 OVERALL VALUE SCORE: {player['overall_value']:.2f}")
        print(f"   {'='*66}")
    
    print("\n" + "=" * 70)
    print("✅ Value analyzer working!")
    print("\n💡 How to use:")
    print("  1. Positive value = Predict OVER the line → Bet OVER")
    print("  2. Negative value = Predict UNDER the line → Bet UNDER")
    print("  3. Higher value score = More confident play")
    print("\n🎯 Next: Apply to TODAY'S 2025-26 games!")
    print("=" * 70)