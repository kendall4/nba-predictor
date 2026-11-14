import pandas as pd
import numpy as np
import joblib
import os
from typing import Dict, Optional

from src.features.opponent_context_adjustments import (
    compute_league_baselines_from_pace,
    compute_league_fg3_share_from_players,
    rebound_opponent_multiplier,
    scoring_profile_multiplier,
    player_paint_and_perimeter_index,
    threes_opponent_multiplier,
    shot_zone_context_multipliers,
)
from src.features.player_derived_advanced import (
    player_derived_advanced_rates,
    efficiency_volatility_nudge,
)
from src.data_collection.player_advanced_tracking_cache import (
    row_for_player_id,
    tracking_features_from_row,
)

class MatchupFeatureBuilder:
    """
    Build prediction features by combining:
    - Player stats
    - Opponent defense (DEF_RATING)
    - Team pace (PACE)
    """

    def __init__(self, blend_mode: str = "mean"):
        # Load prior + primary seasons (nba_api/CSV; BDL season averages are GOAT-tier only)
        try:
            from src.config.nba_seasons import PREV_NBA_SEASON, PRIMARY_NBA_SEASON
        except Exception:
            PREV_NBA_SEASON, PRIMARY_NBA_SEASON = "2025-26", "2026-27"
        self.prev_season = PREV_NBA_SEASON
        self.primary_season = PRIMARY_NBA_SEASON

        p1 = pd.read_csv(f'data/raw/player_stats_{PREV_NBA_SEASON}.csv')
        p1['SEASON'] = PREV_NBA_SEASON
        p2 = pd.read_csv(f'data/raw/player_stats_{PRIMARY_NBA_SEASON}.csv')
        p2['SEASON'] = PRIMARY_NBA_SEASON
        players_all = pd.concat([p1, p2], ignore_index=True)

        # Load both seasons for team pace/ratings
        t1 = pd.read_csv(f'data/raw/team_pace_{PREV_NBA_SEASON}.csv')
        t1['SEASON'] = PREV_NBA_SEASON
        t2 = pd.read_csv(f'data/raw/team_pace_{PRIMARY_NBA_SEASON}.csv')
        t2['SEASON'] = PRIMARY_NBA_SEASON
        pace_all = pd.concat([t1, t2], ignore_index=True)

        # Filter to NBA teams (use BDL when enabled, else hardcoded)
        _nba_teams_hardcoded = [
            'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET',
            'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN',
            'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS',
            'TOR', 'UTA', 'WAS'
        ]
        try:
            from src.services.balldontlie_client import get_nba_team_abbreviations, is_balldontlie_enabled
            if is_balldontlie_enabled():
                bdl_teams = get_nba_team_abbreviations()
                nba_teams = bdl_teams if bdl_teams else _nba_teams_hardcoded
            else:
                nba_teams = _nba_teams_hardcoded
        except Exception:
            nba_teams = _nba_teams_hardcoded
        players_all = players_all[players_all['TEAM_ABBREVIATION'].isin(nba_teams)]

        # Deduplicate players across seasons
        if blend_mode == 'latest':
            # CRITICAL: Only use players who have primary-season data
            players_primary = players_all[players_all['SEASON'] == self.primary_season]
            player_ids_active = players_primary['PLAYER_ID'].unique()
            
            players_all = players_all[players_all['PLAYER_ID'].isin(player_ids_active)]
            
            # Keep latest season row per player (should all be primary season now)
            players_all = (
                players_all.sort_values('SEASON')
                .drop_duplicates(subset=['PLAYER_ID'], keep='last')
            )
            
            # Filter out players with very low activity
            # MIN column is already per-game from the NBA API (PerGame mode)
            if 'GP' in players_all.columns and 'MIN' in players_all.columns:
                players_all = players_all[
                    (players_all['GP'] >= 3) &
                    (players_all['MIN'] >= 5.0)
                ].copy()
        else:
            # Average numeric stats across seasons, then attach latest team/id/season
            numeric_cols = [
                c for c in [
                    'PTS', 'REB', 'AST', 'FG_PCT', 'GP', 'MIN',
                    'FG3M', 'STL', 'BLK', 'TOV',
                ] if c in players_all.columns
            ]
            per_player_avg = (
                players_all
                .groupby(['PLAYER_ID', 'PLAYER_NAME'], as_index=False)[numeric_cols]
                .mean()
            )
            latest_meta_cols = ['PLAYER_ID', 'TEAM_ABBREVIATION']
            for c in ('TEAM_ID', 'SEASON'):
                if c in players_all.columns:
                    latest_meta_cols.append(c)
            latest_team = (
                players_all.sort_values('SEASON')
                .drop_duplicates(subset=['PLAYER_ID'], keep='last')[latest_meta_cols]
            )
            players_all = per_player_avg.merge(latest_team, on='PLAYER_ID', how='left')
        # Ensure we have a TEAM_ABBREVIATION on pace data via mapping from player data
        _team_map_cols = [c for c in ['TEAM_ID', 'TEAM_ABBREVIATION', 'SEASON'] if c in players_all.columns]
        team_map = (
            players_all[_team_map_cols]
            .drop_duplicates()
        )

        # Prefer latest season abbreviation mapping if dup TEAM_IDs
        if 'TEAM_ID' in team_map.columns and 'SEASON' in team_map.columns:
            team_map = (
                team_map.sort_values('SEASON', ascending=True)
                .drop_duplicates(subset=['TEAM_ID'], keep='last')
                [['TEAM_ID', 'TEAM_ABBREVIATION']]
            )
        elif 'TEAM_ID' in team_map.columns:
            team_map = team_map.drop_duplicates(subset=['TEAM_ID'], keep='last')[['TEAM_ID', 'TEAM_ABBREVIATION']]
        else:
            team_map = team_map.drop_duplicates(subset=['TEAM_ABBREVIATION'], keep='last')

        # Attach TEAM_ABBREVIATION to pace
        pace_all = pace_all.merge(team_map, on='TEAM_ID', how='left')
        pace_all = pace_all[pace_all['TEAM_ABBREVIATION'].isin(nba_teams)]

        # Blend pace and ratings across seasons at team level
        metrics = ['PACE', 'OFF_RATING', 'DEF_RATING']
        if blend_mode == 'latest':
            # Take latest season available for each team
            pace_all = (
                pace_all.sort_values('SEASON')  # ensure '2025-26' is after '2024-25'
                .drop_duplicates(subset=['TEAM_ABBREVIATION'], keep='last')
            )
            pace_blended = pace_all[['TEAM_ABBREVIATION'] + metrics].copy()
        else:
            # Default: mean across seasons (robust simple blend)
            pace_blended = (
                pace_all.groupby('TEAM_ABBREVIATION', as_index=False)[metrics].mean()
            )

        self.players = players_all
        self.pace = pace_blended
        # League baselines for opponent glass / shooting (rebound + scoring profile adjustments)
        self._league_pace_baselines = compute_league_baselines_from_pace(self.pace)
        self._league_fg3_share = compute_league_fg3_share_from_players(self.players)
        # Median TS% among rotation players — baseline for individual efficiency nudge
        self._league_ts_baseline = 0.56
        try:
            _tss = []
            for _, pr in self.players.iterrows():
                if float(pr.get("MIN", 0) or 0) >= 10.0:
                    _tss.append(player_derived_advanced_rates(pr)["ts_pct"])
            if _tss:
                self._league_ts_baseline = float(np.median(_tss))
        except Exception:
            pass

        # Optional: NBA shot-location team profiles (rim / 3pt volume + FG% allowed). Requires cache CSVs.
        self._shot_off, self._shot_def = None, None
        try:
            from src.services.team_shot_matchup import load_shot_zone_profiles
            self._shot_off, self._shot_def = load_shot_zone_profiles(self.primary_season)
            if self._shot_off is None or self._shot_def is None:
                self._shot_off, self._shot_def = load_shot_zone_profiles(self.prev_season)
        except Exception:
            self._shot_off, self._shot_def = None, None

        # Optional: league NBA advanced + scoring + hustle + PT tracking (merged CSV in data/cache)
        self._adv_tracking_df = None
        self._adv_tracking_season_used: Optional[str] = None
        try:
            from src.config.nba_seasons import ADV_TRACKING_FALLBACK_SEASON, PRIMARY_NBA_SEASON
            from src.data_collection.player_advanced_tracking_cache import load_player_advanced_tracking

            self._adv_tracking_df, self._adv_tracking_season_used = load_player_advanced_tracking(
                PRIMARY_NBA_SEASON,
                fallback_season=ADV_TRACKING_FALLBACK_SEASON,
                allow_fallback=True,
            )
        except Exception:
            self._adv_tracking_df = None
            self._adv_tracking_season_used = None

        # Optional: load touches/tracking (free nba_api data) for ball-dominance in assists
        self.touches_df = None
        try:
            from src.data_collection.nba_touches import load_cached_touches
            season_for_touches = self.primary_season
            self.touches_df = load_cached_touches(season=season_for_touches)
            if self.touches_df is None or len(self.touches_df) == 0:
                self.touches_df = load_cached_touches(season=self.prev_season)
            if self.touches_df is not None and len(self.touches_df) > 0:
                pass  # Will use in get_player_features for ball-dominance
        except Exception:
            pass

        # Try to load ML models (if trained)
        self.ml_models = {}
        self.use_ml = False
        self.ml_feature_cols = None
        model_dir = 'src/models/saved'
        for stat in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M']:
            model_path = f"{model_dir}/{stat}_predictor.pkl"
            if os.path.exists(model_path):
                try:
                    self.ml_models[stat] = joblib.load(model_path)
                    if stat in ('PTS', 'REB', 'AST'):
                        self.use_ml = True
                except Exception as e:
                    print(f"⚠️  Could not load {stat} model: {e}")
        feat_path = f"{model_dir}/feature_columns.pkl"
        if os.path.exists(feat_path):
            try:
                self.ml_feature_cols = joblib.load(feat_path)
            except Exception:
                pass
        
        _sz = (
            self._shot_off is not None
            and self._shot_def is not None
            and len(self._shot_off) > 0
            and len(self._shot_def) > 0
        )
        _sz_note = "  🎯 Shot zones: loaded (rim/3P matchup multipliers ON)" if _sz else (
            "  🎯 Shot zones: no cache — run shot-zone fetch in Game tab (multipliers skip)"
        )
        _at = self._adv_tracking_df is not None and len(self._adv_tracking_df) > 0
        try:
            from src.config.nba_seasons import PRIMARY_NBA_SEASON as _PRIMARY_SEASON
        except Exception:
            _PRIMARY_SEASON = self.primary_season
        if _at:
            _su = self._adv_tracking_season_used or "?"
            if _su == _PRIMARY_SEASON:
                _at_note = f"  📡 NBA advanced/tracking: **{_su}** cache (TS%, USG%, hustle, PT)"
            else:
                _at_note = (
                    f"  📡 NBA advanced/tracking: **{_su}** cache (fallback — refresh for {_PRIMARY_SEASON} when possible)"
                )
        else:
            _at_note = (
                "  📡 NBA advanced/tracking: no cache — run `python -m src.data_collection.player_advanced_tracking_cache` "
                f"or Game tab (targets {self.primary_season} first)"
            )
        _season_span = f"{self.prev_season} and {self.primary_season}"
        if self.use_ml:
            print(f"✅ Loaded data (two-season blend: {blend_mode})")
            print(f"  Players: {len(self.players)} rows across {_season_span}")
            print(f"  Teams:   {len(self.pace)} teams with blended ratings")
            print(f"  🤖 ML Models: Loaded ({', '.join(self.ml_models.keys())})")
            print(_sz_note)
            print(_at_note)
        else:
            print(f"✅ Loaded data (two-season blend: {blend_mode})")
            print(f"  Players: {len(self.players)} rows across {_season_span}")
            print(f"  Teams:   {len(self.pace)} teams with blended ratings")
            print(f"  📊 Using heuristic predictions (train ML models for better accuracy)")
            print(_sz_note)
            print(_at_note)
    
    def get_player_features(self, player_name, opponent_team, system_fit_weight: float = 0.0, 
                           recent_form_weight: float = 0.0, h2h_weight: float = 0.0,
                           rest_days_weight: float = 0.0, home_away_weight: float = 0.0,
                           play_style_weight: float = 0.0, upside_weight: float = 0.0,
                           game_date=None, is_home=False):
        """
        Build features for: Player X vs Opponent Y
        
        Args:
            player_name: Name of player
            opponent_team: Opponent team abbreviation
            system_fit_weight: Weight for system fit adjustment (0.0 = disabled, 1.0 = full weight)
            recent_form_weight: Weight for recent form (last 5 games) adjustment
            h2h_weight: Weight for head-to-head performance adjustment
        
        Returns dict with:
        - Player's season averages
        - Opponent's defensive rating
        - Expected pace of game
        - Predicted points/rebounds/assists (team matchup + individual efficiency + optional shot zones)
        - Individual: derived TS%, eFG%, 3PAr, FTr, reb activity; rebound_context_mult / scoring_context_mult / threes_context_mult
        - System fit adjustments (if enabled)
        - Recent form adjustments (if enabled)
        - H2H adjustments (if enabled)
        """
        
        # Find player - try exact match first, then case-insensitive, then fuzzy
        player = self.players[self.players['PLAYER_NAME'] == player_name]
        if len(player) == 0:
            # Try case-insensitive match
            player = self.players[self.players['PLAYER_NAME'].str.lower() == player_name.lower()]
        if len(player) == 0:
            # Try fuzzy match (contains)
            player = self.players[self.players['PLAYER_NAME'].str.contains(player_name, case=False, na=False)]
        if len(player) == 0:
            # Last try: match by last name
            last_name = player_name.split()[-1] if len(player_name.split()) > 0 else player_name
            player = self.players[self.players['PLAYER_NAME'].str.contains(last_name, case=False, na=False)]
        
        if len(player) == 0:
            return None
        
        player = player.iloc[0]
        adv_rates = player_derived_advanced_rates(player)
        try:
            _pid = int(player["PLAYER_ID"]) if pd.notna(player.get("PLAYER_ID")) else 0
        except (TypeError, ValueError):
            _pid = 0
        atr = tracking_features_from_row(row_for_player_id(self._adv_tracking_df, _pid))
        
        # Safety check: Filter out inactive players (GP < 3 or MIN < 5 per game)
        # MIN is already per-game from the NBA API (PerGame mode)
        if 'GP' in player.index and 'MIN' in player.index:
            gp = player.get('GP', 0)
            mpg = player.get('MIN', 0)
            if gp < 3 or mpg < 5.0:
                return None
        
        # Get player's team pace
        player_team = self.pace[self.pace['TEAM_ABBREVIATION'] == player['TEAM_ABBREVIATION']]
        if len(player_team) == 0:
            return None
        player_team = player_team.iloc[0]
        
        # Get opponent's defense & pace
        opp = self.pace[self.pace['TEAM_ABBREVIATION'] == opponent_team]
        if len(opp) == 0:
            return None
        opp = opp.iloc[0]
        
        # Calculate expected game pace (average of both teams)
        # Cap PACE values to reasonable range (90-105) to prevent inflation
        # Normal NBA pace is ~95-100 possessions per 48 minutes
        player_pace = float(player_team['PACE'])
        opp_pace = float(opp['PACE'])
        if player_pace > 105 or player_pace < 90:
            player_pace = 98.0  # Use league average
        if opp_pace > 105 or opp_pace < 90:
            opp_pace = 98.0  # Use league average
        
        expected_pace = (player_pace + opp_pace) / 2
        
        # Pace adjustment factor (high pace = more opportunities)
        pace_factor = expected_pace / 100.0  # 100 is average pace
        
        # Defense adjustment (high DEF_RATING = weak defense = more points allowed)
        # NBA average DEF_RATING is ~112-115
        # Cap DEF_RATING to reasonable range (100-130) to prevent inflated predictions
        def_rating = float(opp['DEF_RATING'])
        if def_rating > 130 or def_rating < 80:
            # If value seems wrong (too high/low), use league average
            # This handles data quality issues
            def_rating = 112.0
        def_factor = def_rating / 112.0

        # --- Opponent glass + scoring-profile adjustments (on top of DEF_RATING / pace) ---
        reb_ctx = rebound_opponent_multiplier(opp, self._league_pace_baselines)
        paint_idx, perim_idx = player_paint_and_perimeter_index(player, self._league_fg3_share)
        scr_ctx = scoring_profile_multiplier(
            player, opp, def_factor, self._league_pace_baselines, self._league_fg3_share
        )
        thr_ctx = threes_opponent_multiplier(opp, perim_idx)

        sz_pts, sz_thr, sz_meta = shot_zone_context_multipliers(
            player["TEAM_ABBREVIATION"],
            opponent_team,
            paint_idx,
            perim_idx,
            self._shot_off,
            self._shot_def,
        )
        scr_ctx = float(scr_ctx * sz_pts)
        thr_ctx = float(thr_ctx * sz_thr)
        # Individual efficiency vs league (prefer NBA Advanced TS% when cache exists)
        ts_for_eff = float(adv_rates["ts_pct"])
        if atr.get("api_adv_tracking_loaded") and atr.get("api_ts_pct") is not None:
            try:
                tsv = float(atr["api_ts_pct"])
                ts_for_eff = (tsv / 100.0) if tsv > 1.5 else tsv
                ts_for_eff = float(np.clip(ts_for_eff, 0.35, 0.75))
            except (TypeError, ValueError):
                pass
        eff_nudge = efficiency_volatility_nudge(ts_for_eff, self._league_ts_baseline)
        scr_ctx = float(scr_ctx * eff_nudge)
        
        # System fit adjustment (if enabled)
        system_fit_multiplier = 1.0
        offensive_fit = 1.0
        defensive_matchup = 1.0
        
        # Rest days adjustment (if enabled)
        rest_days_multiplier = 1.0
        rest_days_info = None
        
        # Home/away adjustment (if enabled)
        home_away_multiplier = 1.0
        home_away_info = None
        
        # Play style matchup adjustment (if enabled)
        play_style_multiplier = 1.0
        play_style_info = None
        
        # Usage and ball dominance adjustment for assists (always enabled)
        usage_ball_dominance_multiplier = 1.0
        usage_ball_info = None
        
        # Ball dominance: prefer touches/possessions (free tracking) when available, else assist rate
        try:
            ball_dominance_from_touches = None
            touches_column_used = None
            if getattr(self, 'touches_df', None) is not None and len(self.touches_df) > 0:
                touch_row = self.touches_df[self.touches_df['PLAYER_NAME'] == player_name]
                if len(touch_row) == 0:
                    touch_row = self.touches_df[self.touches_df['PLAYER_NAME'].str.lower() == player_name.lower()]
                if len(touch_row) > 0:
                    row = touch_row.iloc[0]
                    for c in row.index:
                        if c in ('PLAYER_ID', 'PLAYER_NAME', 'TEAM_ABBREVIATION'):
                            continue
                        try:
                            v = float(row[c])
                            if pd.isna(v) or v < 0:
                                continue
                            if 'POSS' in c.upper() or 'TOUCH' in c.upper() or (c.upper() == 'MIN' and v <= 12):
                                ball_dominance_from_touches = v
                                touches_column_used = c
                                break
                        except (TypeError, ValueError):
                            continue
                    if ball_dominance_from_touches is None:
                        for c in row.index:
                            if 'POSSESSIONS' in c and c != 'PT_MEASURE':
                                try:
                                    ball_dominance_from_touches = float(row[c])
                                    touches_column_used = c
                                    break
                                except (TypeError, ValueError):
                                    continue
            
            # Calculate usage rate and ball dominance for assists
            game_log = None
            if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                game_log = self._gamelog_cache[player_name]
            
            if game_log is not None and len(game_log) > 0:
                recent = game_log.head(10)
                
                # Calculate usage rate (FGA + FTA per minute)
                if 'FGA' in recent.columns and 'FTA' in recent.columns and 'MIN' in recent.columns:
                    total_fga = recent['FGA'].sum()
                    total_fta = recent['FTA'].sum()
                    total_min = recent['MIN'].sum()
                    
                    if total_min > 0:
                        usage_rate = (total_fga + total_fta) / total_min  # Per minute
                        # Normalize: league average is ~1.5-2.0 per minute
                        # High usage = >2.0, Medium = 1.5-2.0, Low = <1.5
                        if usage_rate > 2.0:
                            usage_multiplier = 1.10  # +10% for high usage
                        elif usage_rate > 1.5:
                            usage_multiplier = 1.05  # +5% for medium-high usage
                        else:
                            usage_multiplier = 1.0   # Neutral for low usage
                    else:
                        usage_multiplier = 1.0
                else:
                    usage_multiplier = 1.0
                
                # Ball dominance: use touches/possessions (tracking) if available, else assist rate
                if ball_dominance_from_touches is not None and touches_column_used and touches_column_used in self.touches_df.columns:
                    series = self.touches_df[touches_column_used].dropna()
                    if len(series) >= 10:
                        p66 = series.quantile(0.66)
                        p33 = series.quantile(0.33)
                        if ball_dominance_from_touches >= p66:
                            ball_dominance_multiplier = 1.12  # primary ball handler
                        elif ball_dominance_from_touches >= p33:
                            ball_dominance_multiplier = 1.06  # secondary
                        else:
                            ball_dominance_multiplier = 1.0
                    else:
                        ball_dominance_multiplier = 1.0
                elif 'AST' in recent.columns and 'MIN' in recent.columns:
                    avg_ast = recent['AST'].mean()
                    avg_min = recent['MIN'].mean()
                    
                    if avg_min > 0:
                        ast_per_min = avg_ast / avg_min
                        if ast_per_min > 0.15:
                            ball_dominance_multiplier = 1.12
                        elif ast_per_min > 0.08:
                            ball_dominance_multiplier = 1.06
                        else:
                            ball_dominance_multiplier = 1.0
                        if avg_min >= 35:
                            ball_dominance_multiplier *= 1.05
                        elif avg_min >= 30:
                            ball_dominance_multiplier *= 1.02
                    else:
                        ball_dominance_multiplier = 1.0
                else:
                    ball_dominance_multiplier = 1.0
                
                # Combined multiplier
                usage_ball_dominance_multiplier = usage_multiplier * ball_dominance_multiplier
                
                usage_ball_info = {
                    'usage_multiplier': usage_multiplier,
                    'ball_dominance_multiplier': ball_dominance_multiplier,
                    'combined_multiplier': usage_ball_dominance_multiplier,
                    'usage_rate': usage_rate if 'usage_rate' in locals() else None,
                    'ast_per_min': ast_per_min if 'ast_per_min' in locals() else None
                }
            else:
                # Fallback: use touches (tracking) if available, else season assist rate
                if ball_dominance_from_touches is not None and touches_column_used and getattr(self, 'touches_df', None) is not None and touches_column_used in self.touches_df.columns:
                    series = self.touches_df[touches_column_used].dropna()
                    if len(series) >= 10:
                        p66 = series.quantile(0.66)
                        p33 = series.quantile(0.33)
                        if ball_dominance_from_touches >= p66:
                            usage_ball_dominance_multiplier = 1.10
                        elif ball_dominance_from_touches >= p33:
                            usage_ball_dominance_multiplier = 1.05
                        else:
                            usage_ball_dominance_multiplier = 1.0
                    else:
                        usage_ball_dominance_multiplier = 1.0
                else:
                    season_ast = player.get('AST', 0)
                    season_min = player.get('MIN', 0)
                    if season_min > 0:
                        ast_per_min = season_ast / season_min
                        if ast_per_min > 0.15:
                            usage_ball_dominance_multiplier = 1.10
                        elif ast_per_min > 0.08:
                            usage_ball_dominance_multiplier = 1.05
                        else:
                            usage_ball_dominance_multiplier = 1.0
                    else:
                        usage_ball_dominance_multiplier = 1.0
        except Exception:
            # If calculation fails, use neutral multiplier
            usage_ball_dominance_multiplier = 1.0
        
        # Upside/ceiling adjustment (if enabled)
        upside_points_multiplier = 1.0
        upside_rebounds_multiplier = 1.0
        upside_assists_multiplier = 1.0
        upside_info = None
        
        # Recent form adjustment - Always calculate, weight applied when combining
        raw_recent_form_multiplier = 1.0
        try:
            game_log = self._gamelog_cache.get(player_name) if hasattr(self, '_gamelog_cache') else None
            
            if game_log is not None and len(game_log) >= 5:
                last_5_pts = game_log.head(5)['PTS'].mean()
                last_5_reb = game_log.head(5)['REB'].mean()
                last_5_ast = game_log.head(5)['AST'].mean()
                
                # Compare to season average
                season_pts = player['PTS']
                season_reb = player['REB']
                season_ast = player['AST']
                
                # Calculate form factor (1.0 = same as season, >1.0 = hot, <1.0 = cold)
                pts_form = last_5_pts / season_pts if season_pts > 0 else 1.0
                reb_form = last_5_reb / season_reb if season_reb > 0 else 1.0
                ast_form = last_5_ast / season_ast if season_ast > 0 else 1.0
                
                # Weighted average form (points weighted more)
                avg_form = (pts_form * 0.5) + (reb_form * 0.25) + (ast_form * 0.25)
                
                # Store raw multiplier (weight will be applied when combining)
                raw_recent_form_multiplier = avg_form
        except Exception:
            # If recent form check fails, continue without it
            pass
        
        # Apply weight: 1.0 + (raw - 1.0) * weight
        # Ensure raw multiplier is valid number
        if not isinstance(raw_recent_form_multiplier, (int, float)) or pd.isna(raw_recent_form_multiplier):
            raw_recent_form_multiplier = 1.0
        recent_form_multiplier = 1.0 + (raw_recent_form_multiplier - 1.0) * recent_form_weight
        # Ensure final multiplier is valid
        if not isinstance(recent_form_multiplier, (int, float)) or pd.isna(recent_form_multiplier) or recent_form_multiplier <= 0:
            recent_form_multiplier = 1.0
        
        # H2H adjustment - Always calculate, weight applied when combining
        raw_h2h_multiplier = 1.0
        try:
            # Use cached H2H data if available
            h2h_cache_key = f"{player_name}_{opponent_team}"
            if hasattr(self, '_h2h_cache') and h2h_cache_key in self._h2h_cache:
                h2h = self._h2h_cache[h2h_cache_key]
            else:
                # Calculate H2H from cached game logs (fastest, no new tracker instances)
                h2h = None
                try:
                    if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                        game_log = self._gamelog_cache[player_name]
                        if game_log is not None and 'OPP' in game_log.columns and len(game_log) > 0:
                            h2h_games = game_log[game_log['OPP'] == opponent_team]
                            if len(h2h_games) >= 2:
                                h2h = {
                                    'total_games': len(h2h_games),
                                    'avg_pts': float(h2h_games['PTS'].mean()) if 'PTS' in h2h_games.columns else 0,
                                    'avg_reb': float(h2h_games['REB'].mean()) if 'REB' in h2h_games.columns else 0,
                                    'avg_ast': float(h2h_games['AST'].mean()) if 'AST' in h2h_games.columns else 0
                                }
                except Exception:
                    # If H2H calculation fails, skip it
                    h2h = None
                
                # Cache H2H result (even if None, to avoid repeated failed calls)
                if not hasattr(self, '_h2h_cache'):
                    self._h2h_cache = {}
                self._h2h_cache[h2h_cache_key] = h2h
            
            if h2h and h2h.get('total_games', 0) >= 2:
                # Compare H2H average to season average
                h2h_pts = h2h.get('avg_pts', 0)
                h2h_reb = h2h.get('avg_reb', 0)
                h2h_ast = h2h.get('avg_ast', 0)
                
                season_pts = player['PTS']
                season_reb = player['REB']
                season_ast = player['AST']
                
                # Calculate H2H factor
                pts_h2h = h2h_pts / season_pts if season_pts > 0 else 1.0
                reb_h2h = h2h_reb / season_reb if season_reb > 0 else 1.0
                ast_h2h = h2h_ast / season_ast if season_ast > 0 else 1.0
                
                # Weighted average
                avg_h2h = (pts_h2h * 0.5) + (reb_h2h * 0.25) + (ast_h2h * 0.25)
                
                # Store raw multiplier (weight will be applied when combining)
                raw_h2h_multiplier = avg_h2h
        except Exception:
            # If H2H check fails, continue without it
            pass
        
        # Apply weight: 1.0 + (raw - 1.0) * weight
        # Ensure raw multiplier is valid number
        if not isinstance(raw_h2h_multiplier, (int, float)) or pd.isna(raw_h2h_multiplier):
            raw_h2h_multiplier = 1.0
        h2h_multiplier = 1.0 + (raw_h2h_multiplier - 1.0) * h2h_weight
        # Ensure final multiplier is valid
        if not isinstance(h2h_multiplier, (int, float)) or pd.isna(h2h_multiplier) or h2h_multiplier <= 0:
            h2h_multiplier = 1.0
        
        # Rest days adjustment - Always calculate, weight applied when combining
        raw_rest_days_multiplier = 1.0
        rest_days_info = None
        if game_date is not None:
            try:
                from src.services.rest_days_calculator import RestDaysCalculator
                if not hasattr(self, '_rest_calculator'):
                    self._rest_calculator = RestDaysCalculator()
                
                player_minutes = player['MIN']
                rest_info = self._rest_calculator.get_rest_adjustment(
                    player['TEAM_ABBREVIATION'], 
                    game_date,
                    player_minutes=player_minutes
                )
                
                rest_mult = rest_info['multiplier']
                # Store raw multiplier (weight will be applied when combining)
                raw_rest_days_multiplier = rest_mult
                rest_days_info = rest_info
            except Exception:
                pass
        
        # Apply weight: 1.0 + (raw - 1.0) * weight
        # Ensure raw multiplier is valid number
        if not isinstance(raw_rest_days_multiplier, (int, float)) or pd.isna(raw_rest_days_multiplier):
            raw_rest_days_multiplier = 1.0
        rest_days_multiplier = 1.0 + (raw_rest_days_multiplier - 1.0) * rest_days_weight
        # Ensure final multiplier is valid
        if not isinstance(rest_days_multiplier, (int, float)) or pd.isna(rest_days_multiplier) or rest_days_multiplier <= 0:
            rest_days_multiplier = 1.0
        
        # Home/away adjustment - Always calculate, weight applied when combining
        raw_home_away_multiplier = 1.0
        home_away_info = None
        try:
            from src.services.home_away_analyzer import HomeAwayAnalyzer
            if not hasattr(self, '_home_away_analyzer'):
                self._home_away_analyzer = HomeAwayAnalyzer()
            
            # Get team record if available (from pace data)
            team_record = None
            if 'W' in player_team.index and 'L' in player_team.index:
                wins = float(player_team.get('W', 0))
                losses = float(player_team.get('L', 0))
                total = wins + losses
                if total > 0:
                    team_record = {
                        'wins': wins,
                        'losses': losses,
                        'win_pct': wins / total
                    }
            
            # Get team multiplier
            team_mult = self._home_away_analyzer.get_home_away_multiplier(
                player['TEAM_ABBREVIATION'],
                is_home=is_home,
                team_record=team_record
            )
            
            # Try to get player-specific split from cached game log
            player_split = None
            if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                game_log = self._gamelog_cache[player_name]
                player_split = self._home_away_analyzer.get_player_home_away_split(
                    player_name,
                    cached_game_log=game_log
                )
            
            # Use player split if available, otherwise use team multiplier
            if player_split and player_split.get('has_data', False):
                if is_home:
                    player_mult = player_split['home_multiplier']
                else:
                    player_mult = player_split['away_multiplier']
                # Blend player and team (70% player, 30% team)
                final_mult = player_mult * 0.7 + team_mult * 0.3
            else:
                final_mult = team_mult
            
            # Store raw multiplier (weight will be applied when combining)
            raw_home_away_multiplier = final_mult
            home_away_info = {
                'is_home': is_home,
                'team_multiplier': team_mult,
                'player_multiplier': player_split.get('home_multiplier' if is_home else 'away_multiplier', None) if player_split else None
            }
        except Exception:
            pass
        
        # Apply weight: 1.0 + (raw - 1.0) * weight
        # Ensure raw multiplier is valid number
        if not isinstance(raw_home_away_multiplier, (int, float)) or pd.isna(raw_home_away_multiplier):
            raw_home_away_multiplier = 1.0
        home_away_multiplier = 1.0 + (raw_home_away_multiplier - 1.0) * home_away_weight
        # Ensure final multiplier is valid
        if not isinstance(home_away_multiplier, (int, float)) or pd.isna(home_away_multiplier) or home_away_multiplier <= 0:
            home_away_multiplier = 1.0
        
        # Play style matchup adjustment - Always calculate, weight applied when combining
        raw_play_style_multiplier = 1.0
        play_style_info = None
        try:
            from src.services.system_profile_analyzer import SystemProfileAnalyzer
            if not hasattr(self, '_profile_analyzer'):
                self._profile_analyzer = SystemProfileAnalyzer()
            profile_analyzer = self._profile_analyzer
            
            # Get offensive play style profile (player's team)
            team_off_style = profile_analyzer.get_play_style_profile(player['TEAM_ABBREVIATION'])
            
            # Get defensive play style profile (opponent)
            opp_def_style = profile_analyzer.get_defensive_play_style_profile(opponent_team)
            
            # Calculate matchup advantage
            style_advantage = profile_analyzer.calculate_play_style_matchup_advantage(
                team_off_style, opp_def_style
            )
            
            # Store raw multiplier (weight will be applied when combining)
            raw_play_style_multiplier = style_advantage
            play_style_info = {
                'team_style': team_off_style.get('primary_style', 'Balanced'),
                'opponent_weakness': opp_def_style.get('weaknesses', {}),
                'advantage': style_advantage
            }
        except Exception:
            pass
        
        # Apply weight: 1.0 + (raw - 1.0) * weight
        # Ensure raw multiplier is valid number
        if not isinstance(raw_play_style_multiplier, (int, float)) or pd.isna(raw_play_style_multiplier):
            raw_play_style_multiplier = 1.0
        play_style_multiplier = 1.0 + (raw_play_style_multiplier - 1.0) * play_style_weight
        # Ensure final multiplier is valid
        if not isinstance(play_style_multiplier, (int, float)) or pd.isna(play_style_multiplier) or play_style_multiplier <= 0:
            play_style_multiplier = 1.0
        
        # Upside/ceiling adjustment - Always calculate, weight applied when combining
        raw_upside_points_multiplier = 1.0
        raw_upside_rebounds_multiplier = 1.0
        raw_upside_assists_multiplier = 1.0
        upside_info = None
        try:
            from src.services.upside_calculator import UpsideCalculator
            if not hasattr(self, '_upside_calculator'):
                self._upside_calculator = UpsideCalculator()
            
            # Get cached game log if available
            game_log = None
            if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                game_log = self._gamelog_cache[player_name]
            
            # Calculate raw upside multipliers (get base multiplier, not weighted)
            points_metrics = self._upside_calculator.calculate_upside_metrics(
                player_name, 'points', game_log, player['PTS'], player['MIN']
            )
            rebounds_metrics = self._upside_calculator.calculate_upside_metrics(
                player_name, 'rebounds', game_log, player['REB'], player['MIN']
            )
            assists_metrics = self._upside_calculator.calculate_upside_metrics(
                player_name, 'assists', game_log, player['AST'], player['MIN']
            )
            
            # Get raw multipliers (weight will be applied when combining)
            raw_upside_points_multiplier = points_metrics.get('upside_multiplier', 1.0)
            raw_upside_rebounds_multiplier = rebounds_metrics.get('upside_multiplier', 1.0)
            raw_upside_assists_multiplier = assists_metrics.get('upside_multiplier', 1.0)
            
            upside_info = {
                'points_multiplier': raw_upside_points_multiplier,
                'rebounds_multiplier': raw_upside_rebounds_multiplier,
                'assists_multiplier': raw_upside_assists_multiplier,
                'points_career_high': points_metrics.get('career_high', 0),
                'points_90th': points_metrics.get('career_90th', 0),
                'points_volatility': points_metrics.get('volatility', 0),
                'has_data': points_metrics.get('has_data', False)
            }
        except Exception:
            pass
        
        # Apply weight: 1.0 + (raw - 1.0) * weight
        # Ensure raw multipliers are valid numbers
        if not isinstance(raw_upside_points_multiplier, (int, float)) or pd.isna(raw_upside_points_multiplier):
            raw_upside_points_multiplier = 1.0
        if not isinstance(raw_upside_rebounds_multiplier, (int, float)) or pd.isna(raw_upside_rebounds_multiplier):
            raw_upside_rebounds_multiplier = 1.0
        if not isinstance(raw_upside_assists_multiplier, (int, float)) or pd.isna(raw_upside_assists_multiplier):
            raw_upside_assists_multiplier = 1.0
        upside_points_multiplier = 1.0 + (raw_upside_points_multiplier - 1.0) * upside_weight
        upside_rebounds_multiplier = 1.0 + (raw_upside_rebounds_multiplier - 1.0) * upside_weight
        upside_assists_multiplier = 1.0 + (raw_upside_assists_multiplier - 1.0) * upside_weight
        # Ensure final multipliers are valid
        if not isinstance(upside_points_multiplier, (int, float)) or pd.isna(upside_points_multiplier) or upside_points_multiplier <= 0:
            upside_points_multiplier = 1.0
        if not isinstance(upside_rebounds_multiplier, (int, float)) or pd.isna(upside_rebounds_multiplier) or upside_rebounds_multiplier <= 0:
            upside_rebounds_multiplier = 1.0
        if not isinstance(upside_assists_multiplier, (int, float)) or pd.isna(upside_assists_multiplier) or upside_assists_multiplier <= 0:
            upside_assists_multiplier = 1.0
        
        # Return from injury / days since last game adjustment
        # Only apply if player has been out for a SIGNIFICANT time (60+ days)
        return_from_injury_multiplier = 1.0
        days_since_last_game = None
        try:
            # Get game log if available
            game_log = None
            if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                game_log = self._gamelog_cache[player_name]
            
            if game_log is not None and len(game_log) > 0 and 'GAME_DATE' in game_log.columns:
                from datetime import datetime, timedelta
                try:
                    # Ensure game log is sorted by date (newest first)
                    game_log_sorted = game_log.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)
                    # Get most recent game date
                    last_game_date = pd.to_datetime(game_log_sorted.iloc[0]['GAME_DATE'])
                    if game_date:
                        current_date = pd.to_datetime(game_date)
                        days_since_last_game = (current_date - last_game_date).days
                        
                        # Only apply if player has been out for a VERY long time (60+ days)
                        # Most players playing regularly won't hit this
                        if days_since_last_game >= 60:  # Out 60+ days (major injury)
                            return_from_injury_multiplier = 0.95  # -5% for major injury return
                        # Less than 60 days = no adjustment (players are active)
                except Exception:
                    pass
        except Exception:
            pass
        
        # Minutes restriction detection
        # Only apply if there's a SIGNIFICANT drop (50% or more)
        minutes_restriction_multiplier = 1.0
        try:
            game_log = None
            if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                game_log = self._gamelog_cache[player_name]
            
            if game_log is not None and len(game_log) >= 3 and 'MIN' in game_log.columns:
                # Ensure game log is sorted by date (newest first) for recent minutes check
                if 'GAME_DATE' in game_log.columns:
                    game_log_sorted = game_log.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)
                else:
                    game_log_sorted = game_log
                recent_minutes = game_log_sorted.head(3)['MIN'].mean()
                season_minutes = player.get('MIN', 0) / max(1, player.get('GP', 1))
                
                # Only apply if recent minutes are < 50% of season average (major restriction)
                # This catches only severe restrictions, not minor fluctuations
                if season_minutes > 0 and recent_minutes < season_minutes * 0.50:
                    # Major minutes restriction - apply proportional reduction
                    minutes_restriction_multiplier = recent_minutes / season_minutes
                    # Cap at 0.90 minimum (don't reduce more than 10%)
                    minutes_restriction_multiplier = max(0.90, minutes_restriction_multiplier)
        except Exception:
            pass
        
        # Recent games count check (games played in last 30 days)
        # Only apply if player has played VERY little (1 game or less in 30 days)
        recent_activity_multiplier = 1.0
        try:
            game_log = None
            if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                game_log = self._gamelog_cache[player_name]
            
            if game_log is not None and len(game_log) > 0 and 'GAME_DATE' in game_log.columns:
                from datetime import datetime, timedelta
                try:
                    if game_date:
                        # Ensure game log is sorted by date (newest first)
                        game_log_sorted = game_log.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)
                        cutoff_date = pd.to_datetime(game_date) - timedelta(days=30)
                        recent_games = game_log_sorted[pd.to_datetime(game_log_sorted['GAME_DATE']) >= cutoff_date]
                        recent_games_count = len(recent_games)
                        
                        # Only apply if player has played 1 game or less (essentially inactive)
                        # Most active players won't hit this
                        if recent_games_count <= 1:  # 1 game or less in last 30 days
                            recent_activity_multiplier = 0.97  # -3% for essentially inactive players
                        # 2+ games = no adjustment (player is active)
                except Exception:
                    pass
        except Exception:
            pass
        
        # System fit adjustment - Always calculate, weight applied when combining
        raw_system_fit_multiplier = 1.0
        offensive_fit = 1.0
        defensive_matchup = 1.0
        try:
            from src.services.system_profile_analyzer import SystemProfileAnalyzer
            # Use cached instance if available (profiles are cached internally)
            if not hasattr(self, '_profile_analyzer'):
                self._profile_analyzer = SystemProfileAnalyzer()
            profile_analyzer = self._profile_analyzer
            
            # Get offensive profile (player's team) - cached internally
            team_off_profile = profile_analyzer.get_offensive_profile(player['TEAM_ABBREVIATION'])
            
            # Get defensive profile (opponent) - cached internally
            opponent_def_profile = profile_analyzer.get_defensive_profile(opponent_team)
            
            # Calculate player-system fit
            player_stats = {
                'PTS': player['PTS'],
                'REB': player['REB'],
                'AST': player['AST'],
                'MIN': player['MIN']
            }
            
            fit_data = profile_analyzer.calculate_player_system_fit(
                player_stats, team_off_profile, opponent_def_profile
            )
            
            offensive_fit = fit_data['offensive_fit']
            defensive_matchup = fit_data['defensive_matchup']
            
            # Calculate raw system fit multiplier (blend offensive fit and defensive matchup)
            # More nuanced: blend offensive fit and defensive matchup
            raw_system_fit_multiplier = 1.0 + (
                (offensive_fit - 1.0) * 0.6 + (defensive_matchup - 1.0) * 0.4
            )
            
        except Exception:
            # If system profile fails, continue without it
            pass
        
        # Apply weight: 1.0 + (raw - 1.0) * weight
        # Ensure raw multiplier is valid number
        if not isinstance(raw_system_fit_multiplier, (int, float)) or pd.isna(raw_system_fit_multiplier):
            raw_system_fit_multiplier = 1.0
        system_fit_multiplier = 1.0 + (raw_system_fit_multiplier - 1.0) * system_fit_weight
        # Ensure final multiplier is valid
        if not isinstance(system_fit_multiplier, (int, float)) or pd.isna(system_fit_multiplier) or system_fit_multiplier <= 0:
            system_fit_multiplier = 1.0
        
        # Build features
        features = {
            'player_name': player_name,
            'team': player['TEAM_ABBREVIATION'],
            'opponent': opponent_team,
            
            # Player averages
            'season_ppg': player['PTS'],
            'season_rpg': player['REB'],
            'season_apg': player['AST'],
            'season_3pg': float(player.get('FG3M', 0)),  # 3-pointers made per game
            'season_spg': float(player.get('STL', 0)),   # Steals per game
            'season_bpg': float(player.get('BLK', 0)),   # Blocks per game
            'season_tpg': float(player.get('TOV', 0)),  # Turnovers per game
            'season_fg_pct': player['FG_PCT'],
            'games_played': player['GP'],
            'minutes': player['MIN'],
            # Derived individual advanced-style rates (from box totals — no separate API)
            'player_ts_pct': adv_rates["ts_pct"],
            'player_efg_pct': adv_rates["efg_pct"],
            'player_three_point_ar': adv_rates["three_point_ar"],
            'player_ft_rate': adv_rates["ft_rate"],
            'player_oreb_activity_36': adv_rates["oreb_pct_activity"],
            'player_dreb_activity_36': adv_rates["dreb_pct_activity"],
            'efficiency_context_mult': eff_nudge,
            
            # Matchup factors
            'expected_pace': expected_pace,
            'opponent_def_rating': def_rating,  # Use capped value
            'opponent_off_rating': float(opp['OFF_RATING']) if float(opp['OFF_RATING']) <= 130 else 110.0,  # Cap OFF_RATING too
            'pace_factor': pace_factor,
            'def_factor': def_factor,
            'rebound_context_mult': reb_ctx,
            'scoring_context_mult': scr_ctx,
            'threes_context_mult': thr_ctx,
            'paint_profile_index': paint_idx,
            'perimeter_profile_index': perim_idx,
            'shot_zone_pts_mult': sz_pts,
            'shot_zone_threes_mult': sz_thr,
            'shot_zone_meta': sz_meta,
            
            # System fit (if enabled)
            'system_fit_multiplier': system_fit_multiplier,
            'offensive_fit': offensive_fit,
            'defensive_matchup': defensive_matchup,
            
            # Recent form and H2H (if enabled)
            'recent_form_multiplier': recent_form_multiplier,
            'h2h_multiplier': h2h_multiplier,
            'rest_days_multiplier': rest_days_multiplier,
            'rest_days_info': rest_days_info,
            'home_away_multiplier': home_away_multiplier,
            'home_away_info': home_away_info,
            'play_style_multiplier': play_style_multiplier,
            'play_style_info': play_style_info,
            'upside_points_multiplier': upside_points_multiplier,
            'upside_rebounds_multiplier': upside_rebounds_multiplier,
            'upside_assists_multiplier': upside_assists_multiplier,
            'upside_info': upside_info,
            'usage_ball_dominance_multiplier': usage_ball_dominance_multiplier,
            'usage_ball_info': usage_ball_info,
        }
        
        # PREDICTION: Use ML if available, else heuristics
        if self.use_ml and all(stat in self.ml_models for stat in ['PTS', 'REB', 'AST']):
            # Build feature array matching training column order
            base_vals = [
                features['season_ppg'],
                features['season_rpg'],
                features['season_apg'],
                features['season_fg_pct'],
                features['games_played'],
                features['minutes'],
                features['expected_pace'],
                features['opponent_def_rating'],
                features['opponent_off_rating'],
                features['pace_factor'],
                features['def_factor'],
            ]
            extra_vals = [
                features.get('season_spg', 0),
                features.get('season_bpg', 0),
                features.get('season_tpg', 0),
                features.get('season_3pg', 0),
            ]
            feature_array = np.array([base_vals + extra_vals])

            # ML predictions for core stats
            base_points = float(self.ml_models['PTS'].predict(feature_array)[0])
            base_rebounds = float(self.ml_models['REB'].predict(feature_array)[0])
            base_assists = float(self.ml_models['AST'].predict(feature_array)[0])

            # Collect all multipliers
            multipliers = [
                system_fit_multiplier, recent_form_multiplier, h2h_multiplier,
                rest_days_multiplier, home_away_multiplier, play_style_multiplier,
                return_from_injury_multiplier, minutes_restriction_multiplier, recent_activity_multiplier
            ]

            reductions = [m for m in multipliers if m < 1.0]
            boosts = [m for m in multipliers if m >= 1.0]

            if len(reductions) > 0:
                avg_reduction = max(0.90, sum(reductions) / len(reductions))
                boost_product = 1.0
                for b in boosts:
                    boost_product *= b
                base_multiplier = avg_reduction * boost_product
            else:
                base_multiplier = 1.0
                for m in multipliers:
                    base_multiplier *= m

            if not isinstance(base_multiplier, (int, float)) or pd.isna(base_multiplier) or base_multiplier <= 0:
                base_multiplier = 1.0

            features['predicted_points'] = (
                base_points * base_multiplier * upside_points_multiplier * scr_ctx
            )
            features['predicted_rebounds'] = (
                base_rebounds * base_multiplier * upside_rebounds_multiplier * reb_ctx
            )
            features['predicted_assists'] = base_assists * base_multiplier * upside_assists_multiplier * usage_ball_dominance_multiplier

            # ML predictions for secondary stats (STL, BLK, TOV, FG3M) — fall back to heuristic if model absent
            season_3pg = features.get('season_3pg', 0)
            season_spg = features.get('season_spg', 0)
            season_bpg = features.get('season_bpg', 0)
            season_tpg = features.get('season_tpg', 0)

            if 'FG3M' in self.ml_models:
                features['predicted_threes'] = max(
                    0.0,
                    float(self.ml_models['FG3M'].predict(feature_array)[0]) * base_multiplier * thr_ctx,
                )
            else:
                features['predicted_threes'] = max(
                    0.0, season_3pg * base_multiplier * pace_factor * thr_ctx
                )

            if 'STL' in self.ml_models:
                features['predicted_steals'] = max(0.0, float(self.ml_models['STL'].predict(feature_array)[0]) * base_multiplier)
            else:
                features['predicted_steals'] = max(0.0, season_spg * base_multiplier * pace_factor)

            if 'BLK' in self.ml_models:
                features['predicted_blocks'] = max(0.0, float(self.ml_models['BLK'].predict(feature_array)[0]) * base_multiplier)
            else:
                features['predicted_blocks'] = max(0.0, season_bpg * base_multiplier)

            if 'TOV' in self.ml_models:
                features['predicted_turnovers'] = max(0.0, float(self.ml_models['TOV'].predict(feature_array)[0]) * base_multiplier)
            else:
                features['predicted_turnovers'] = max(0.0, season_tpg * base_multiplier * pace_factor)
        else:
            # Fallback to heuristics (simple multipliers)
            # Apply all multipliers if enabled
            base_points = player['PTS'] * pace_factor * def_factor * scr_ctx
            base_rebounds = player['REB'] * pace_factor * reb_ctx
            base_assists = player['AST'] * pace_factor
            
            # Collect all multipliers
            multipliers = [
                system_fit_multiplier, recent_form_multiplier, h2h_multiplier,
                rest_days_multiplier, home_away_multiplier, play_style_multiplier,
                return_from_injury_multiplier, minutes_restriction_multiplier, recent_activity_multiplier
            ]
            
            # Prevent compounding reductions by averaging reductions instead of multiplying
            reductions = [m for m in multipliers if m < 1.0]
            boosts = [m for m in multipliers if m >= 1.0]
            
            if len(reductions) > 0:
                # Average the reductions (less aggressive than multiplying)
                avg_reduction = sum(reductions) / len(reductions)
                # Cap reduction at 0.90 (max 10% reduction from all factors combined)
                avg_reduction = max(0.90, avg_reduction)
                # Multiply boosts normally
                boost_product = 1.0
                for b in boosts:
                    boost_product *= b
                base_multiplier = avg_reduction * boost_product
            else:
                # All multipliers are boosts or neutral, multiply normally
                base_multiplier = 1.0
                for m in multipliers:
                    base_multiplier *= m
            
            if not isinstance(base_multiplier, (int, float)) or pd.isna(base_multiplier) or base_multiplier <= 0:
                base_multiplier = 1.0

            features['predicted_points'] = base_points * base_multiplier * upside_points_multiplier
            features['predicted_rebounds'] = base_rebounds * base_multiplier * upside_rebounds_multiplier
            features['predicted_assists'] = base_assists * base_multiplier * upside_assists_multiplier * usage_ball_dominance_multiplier
            
            # Add predictions for other stats
            season_3pg = features.get('season_3pg', 0)
            season_spg = features.get('season_spg', 0)
            season_bpg = features.get('season_bpg', 0)
            season_tpg = features.get('season_tpg', 0)
            
            features['predicted_threes'] = max(0.0, season_3pg * base_multiplier * pace_factor * thr_ctx)
            features['predicted_steals'] = max(0.0, season_spg * base_multiplier * pace_factor)
            features['predicted_blocks'] = max(0.0, season_bpg * base_multiplier)
            features['predicted_turnovers'] = max(0.0, season_tpg * base_multiplier * pace_factor)

        for _k, _v in atr.items():
            if _v is not None or _k == "api_adv_tracking_loaded":
                features[_k] = _v
        if self._adv_tracking_season_used:
            features["api_adv_tracking_season"] = self._adv_tracking_season_used

        # Final validation: ensure all predictions are valid numbers
        validation_failures = []
        for pred_key in ['predicted_points', 'predicted_rebounds', 'predicted_assists', 
                         'predicted_threes', 'predicted_steals', 'predicted_blocks', 'predicted_turnovers']:
            if pred_key in features:
                pred_value = features[pred_key]
                if not isinstance(pred_value, (int, float)) or pd.isna(pred_value) or pred_value < 0:
                    # Log validation failure for debugging
                    validation_failures.append({
                        'stat': pred_key,
                        'invalid_value': pred_value,
                        'player': player_name
                    })
                    # Fallback to season average if prediction is invalid
                    if pred_key == 'predicted_points':
                        features[pred_key] = float(player.get('PTS', 0))
                    elif pred_key == 'predicted_rebounds':
                        features[pred_key] = float(player.get('REB', 0))
                    elif pred_key == 'predicted_assists':
                        features[pred_key] = float(player.get('AST', 0))
                    elif pred_key == 'predicted_threes':
                        features[pred_key] = float(player.get('FG3M', 0))
                    elif pred_key == 'predicted_steals':
                        features[pred_key] = float(player.get('STL', 0))
                    elif pred_key == 'predicted_blocks':
                        features[pred_key] = float(player.get('BLK', 0))
                    elif pred_key == 'predicted_turnovers':
                        features[pred_key] = float(player.get('TOV', 0))
                else:
                    features[pred_key] = float(pred_value)
        
        # Log validation failures if any (for debugging)
        if validation_failures:
            try:
                failure_summary = {}
                for failure in validation_failures:
                    stat = failure['stat']
                    if stat not in failure_summary:
                        failure_summary[stat] = []
                    failure_summary[stat].append(failure['player'])
                
                # Print summary (will appear in terminal/logs)
                for stat, players in failure_summary.items():
                    if len(players) <= 5:
                        print(f"⚠️  Validation failure: {stat} invalid for {len(players)} player(s): {', '.join(players)}")
                    else:
                        print(f"⚠️  Validation failure: {stat} invalid for {len(players)} players (sample: {', '.join(players[:5])}...)")
            except (BrokenPipeError, OSError):
                # Ignore if output is redirected or pipe is broken
                pass
        
        return features
    
    def get_all_matchups(self, games_today, system_fit_weight: float = 0.0, 
                        recent_form_weight: float = 0.0, h2h_weight: float = 0.0,
                        rest_days_weight: float = 0.0, home_away_weight: float = 0.0,
                        play_style_weight: float = 0.0, upside_weight: float = 0.0,
                        apply_teammate_absence: bool = True,
                        apply_historical_teammate_nudge: bool = True):
        """
        Get features for all players in today's games
        
        Args:
            games_today: List of games [{'home': 'LAL', 'away': 'GSW'}, ...]
            system_fit_weight: Weight for system fit adjustment (0.0 = disabled, 1.0 = full weight)
            recent_form_weight: Weight for recent form adjustment (0.0 = disabled, 1.0 = full weight)
            h2h_weight: Weight for head-to-head adjustment (0.0 = disabled, 1.0 = full weight)
        """
        all_features = []
        
        # Pre-filter players to only those in today's games (performance optimization)
        game_teams = set()
        for game in games_today:
            game_teams.add(game['home'])
            game_teams.add(game['away'])
        players_today = self.players[self.players['TEAM_ABBREVIATION'].isin(game_teams)]

        # When BDL enabled: restrict to current rosters (active players) so we don't include traded/cut
        try:
            from src.services.balldontlie_client import get_active_player_names_set, is_balldontlie_enabled
            if is_balldontlie_enabled():
                active_names = get_active_player_names_set()
                if active_names is not None and len(active_names) > 0 and 'PLAYER_NAME' in players_today.columns:
                    before = len(players_today)
                    players_today = players_today[players_today['PLAYER_NAME'].isin(active_names)]
                    if before > len(players_today):
                        try:
                            print(f"🔧 BDL active filter: {before} → {len(players_today)} players (roster-only)", flush=True)
                        except (BrokenPipeError, OSError):
                            pass
        except Exception:
            pass

        # Safety filter: Only include active players (GP >= 3, MIN >= 5 per game)
        # MIN is already per-game from the NBA API (PerGame mode)
        players_before_filter = len(players_today)
        players_after_filter = players_before_filter
        if 'GP' in players_today.columns and 'MIN' in players_today.columns:
            players_today = players_today[
                (players_today['GP'] >= 3) &
                (players_today['MIN'] >= 5.0)
            ].copy()
            players_after_filter = len(players_today)
        
        # Pre-initialize analyzers (always needed since we always calculate factors)
        if not hasattr(self, '_profile_analyzer'):
            from src.services.system_profile_analyzer import SystemProfileAnalyzer
            self._profile_analyzer = SystemProfileAnalyzer()
            # Pre-cache all team profiles for today's games
            for team in game_teams:
                self._profile_analyzer.get_offensive_profile(team)
                self._profile_analyzer.get_defensive_profile(team)
        
        if not hasattr(self, '_hot_tracker'):
            from src.analysis.hot_hand_tracker import HotHandTracker
            self._hot_tracker = HotHandTracker(blend_mode="latest")
        
        if not hasattr(self, '_gamelog_cache'):
            self._gamelog_cache = {}
        if not hasattr(self, '_h2h_cache'):
            self._h2h_cache = {}

        # Batch pre-load game logs only when a factor needs them. Otherwise this
        # hammers stats.nba.com on cache miss and can hang the UI for many minutes.
        need_gamelogs = (
            float(recent_form_weight or 0) > 0
            or float(h2h_weight or 0) > 0
            or float(home_away_weight or 0) > 0
            or float(rest_days_weight or 0) > 0
        )
        if need_gamelogs:
            all_player_names = players_today['PLAYER_NAME'].unique().tolist()
            uncached = [n for n in all_player_names if n not in self._gamelog_cache]
            if uncached:
                batch = self._hot_tracker.batch_load_gamelogs(uncached, season=self.primary_season)
                # Pre-parse OPP column so H2H doesn't have to copy + parse per player
                def _parse_opp(m):
                    if pd.isna(m):
                        return None
                    parts = str(m).split(' ')
                    return parts[2].strip() if len(parts) >= 3 else str(m)[-3:].upper()
                for name, df in batch.items():
                    if df is None or not hasattr(df, 'columns'):
                        continue
                    if 'MATCHUP' in df.columns and 'OPP' not in df.columns:
                        df['OPP'] = df['MATCHUP'].apply(_parse_opp)
                self._gamelog_cache.update(batch)
        
        # Build features for each player
        for game in games_today:
            home = game['home']
            away = game['away']
            
            home_players = players_today[players_today['TEAM_ABBREVIATION'] == home]
            away_players = players_today[players_today['TEAM_ABBREVIATION'] == away]
            
            if 'PLAYER_ID' in home_players.columns:
                home_players = home_players.drop_duplicates(subset=['PLAYER_ID'])
            else:
                home_players = home_players.drop_duplicates(subset=['PLAYER_NAME'])
            if 'PLAYER_ID' in away_players.columns:
                away_players = away_players.drop_duplicates(subset=['PLAYER_ID'])
            else:
                away_players = away_players.drop_duplicates(subset=['PLAYER_NAME'])
            
            # Get game date if available
            from datetime import datetime, date
            game_date = None
            if 'game_date' in game:
                if isinstance(game['game_date'], date):
                    game_date = game['game_date']
                elif isinstance(game['game_date'], str):
                    try:
                        game_date = datetime.strptime(game['game_date'], '%Y-%m-%d').date()
                    except:
                        game_date = date.today()
            else:
                game_date = date.today()  # Default to today
            
            for _, player in home_players.iterrows():
                features = self.get_player_features(
                    player['PLAYER_NAME'], away, 
                    system_fit_weight=system_fit_weight,
                    recent_form_weight=recent_form_weight,
                    h2h_weight=h2h_weight,
                    rest_days_weight=rest_days_weight,
                    home_away_weight=home_away_weight,
                    play_style_weight=play_style_weight,
                    upside_weight=upside_weight,
                    game_date=game_date,
                    is_home=True
                )
                if features:
                    all_features.append(features)
            
            for _, player in away_players.iterrows():
                features = self.get_player_features(
                    player['PLAYER_NAME'], home,
                    system_fit_weight=system_fit_weight,
                    recent_form_weight=recent_form_weight,
                    h2h_weight=h2h_weight,
                    rest_days_weight=rest_days_weight,
                    home_away_weight=home_away_weight,
                    play_style_weight=play_style_weight,
                    upside_weight=upside_weight,
                    game_date=game_date,
                    is_home=False
                )
                if features:
                    all_features.append(features)
        
        result_df = pd.DataFrame(all_features)

        absence_index = {}
        if len(result_df) > 0 and (apply_teammate_absence or apply_historical_teammate_nudge):
            try:
                from src.features.teammate_absence_adjustments import (
                    build_slate_teammate_absence_index,
                )

                absence_index = build_slate_teammate_absence_index(set(game_teams), self.players)
            except Exception:
                absence_index = {}

        # Teammate OUT vacuum (mild boost to remaining rotation; separate emphasis columns)
        if apply_teammate_absence and len(result_df) > 0 and absence_index:
            try:
                from src.features.teammate_absence_adjustments import (
                    apply_teammate_absence_to_matchup_df,
                )

                result_df = apply_teammate_absence_to_matchup_df(
                    result_df, absence_index, roster_df=self.players, enabled=True
                )
            except Exception:
                pass

        # Light: historical game-level with/without vs one primary star OUT (extra PTS/AST cap)
        if apply_historical_teammate_nudge and len(result_df) > 0 and absence_index:
            try:
                from src.features.historical_teammate_out_nudge import (
                    apply_historical_teammate_out_nudges,
                )

                result_df = apply_historical_teammate_out_nudges(
                    result_df,
                    absence_index,
                    self.players,
                    season=self.primary_season,
                    enabled=True,
                )
            except Exception:
                pass
        
        # Debug: Show summary of players processed
        if len(result_df) > 0:
            try:
                unique_players = result_df['player_name'].nunique()
                unique_teams = result_df['team'].nunique()
                print(f"✅ Generated predictions for {len(result_df)} player-matchups ({unique_players} unique players, {unique_teams} teams)")
            except (BrokenPipeError, OSError):
                pass
        else:
            try:
                print(f"⚠️  No predictions generated. Players filtered: {players_before_filter} → {players_after_filter}")
            except (BrokenPipeError, OSError):
                pass
        
        return result_df


# Test it
if __name__ == "__main__":
    print("=" * 70)
    print("🔧 TESTING FEATURE BUILDER")
    print("=" * 70)
    
    builder = MatchupFeatureBuilder()
    
    # Example: Luka Doncic vs Celtics
    print("\n📊 Example: Luka Dončić vs BOS")
    features = builder.get_player_features('Luka Dončić', 'BOS')
    
    if features:
        print(f"\nPlayer: {features['player_name']}")
        print(f"Season average: {features['season_ppg']:.1f} PPG")
        print(f"Expected pace: {features['expected_pace']:.1f}")
        print(f"Opponent defense: {features['opponent_def_rating']:.1f}")
        print(f"\n🎯 PREDICTION:")
        print(f"  Points: {features['predicted_points']:.1f}")
        print(f"  Rebounds: {features['predicted_rebounds']:.1f}")
        print(f"  Assists: {features['predicted_assists']:.1f}")
    else:
        print("❌ Could not find player or team")
    
    # Example: All players in Lakers vs Warriors
    print("\n" + "=" * 70)
    print("📊 Example: All Lakers vs Warriors players")
    games = [{'home': 'LAL', 'away': 'GSW'}]
    all_matchups = builder.get_all_matchups(games)
    
    print(f"\n✅ Generated features for {len(all_matchups)} players")
    print("\nTop 5 predicted scorers:")
    top5 = all_matchups.nlargest(5, 'predicted_points')[
        ['player_name', 'team', 'season_ppg', 'predicted_points', 'opponent_def_rating']
    ]
    print(top5.to_string(index=False))
    
    print("\n" + "=" * 70)
    print("✅ Feature builder working!")
    print("🎯 Next: Train ML model on this data")
    print("=" * 70)