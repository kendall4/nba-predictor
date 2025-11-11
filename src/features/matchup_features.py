import pandas as pd
import numpy as np
import joblib
import os
from typing import Dict, Optional

class MatchupFeatureBuilder:
    """
    Build prediction features by combining:
    - Player stats
    - Opponent defense (DEF_RATING)
    - Team pace (PACE)
    """

    def __init__(self, blend_mode: str = "mean"):
        # Load both seasons for players
        p1 = pd.read_csv('data/raw/player_stats_2024-25.csv')
        p1['SEASON'] = '2024-25'
        p2 = pd.read_csv('data/raw/player_stats_2025-26.csv')
        p2['SEASON'] = '2025-26'
        players_all = pd.concat([p1, p2], ignore_index=True)

        # Load both seasons for team pace/ratings
        t1 = pd.read_csv('data/raw/team_pace_2024-25.csv')
        t1['SEASON'] = '2024-25'
        t2 = pd.read_csv('data/raw/team_pace_2025-26.csv')
        t2['SEASON'] = '2025-26'
        pace_all = pd.concat([t1, t2], ignore_index=True)

        # Filter to NBA teams (30)
        nba_teams = [
            'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET',
            'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN',
            'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS',
            'TOR', 'UTA', 'WAS'
        ]
        players_all = players_all[players_all['TEAM_ABBREVIATION'].isin(nba_teams)]

        # Deduplicate players across seasons
        if blend_mode == 'latest':
            # Keep latest season row per player
            players_all = (
                players_all.sort_values('SEASON')
                .drop_duplicates(subset=['PLAYER_ID'], keep='last')
            )
        else:
            # Average numeric stats across seasons, then attach latest team
            numeric_cols = ['PTS', 'REB', 'AST', 'FG_PCT', 'GP', 'MIN']
            per_player_avg = (
                players_all
                .groupby(['PLAYER_ID', 'PLAYER_NAME'], as_index=False)[numeric_cols]
                .mean()
            )
            latest_team = (
                players_all.sort_values('SEASON')
                .drop_duplicates(subset=['PLAYER_ID'], keep='last')[['PLAYER_ID', 'TEAM_ABBREVIATION']]
            )
            players_all = per_player_avg.merge(latest_team, on='PLAYER_ID', how='left')
        # Ensure we have a TEAM_ABBREVIATION on pace data via mapping from player data
        team_map = (
            players_all[['TEAM_ID', 'TEAM_ABBREVIATION', 'SEASON']]
            .drop_duplicates()
        )

        # Prefer latest season abbreviation mapping if dup TEAM_IDs
        team_map = (
            team_map.sort_values('SEASON', ascending=True)  # ensure 2025-26 sorts after 2024-25 if string? safer to map order
            .drop_duplicates(subset=['TEAM_ID'], keep='last')
            [['TEAM_ID', 'TEAM_ABBREVIATION']]
        )

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

        # Try to load ML models (if trained)
        self.ml_models = {}
        self.use_ml = False
        model_dir = 'src/models/saved'
        for stat in ['PTS', 'REB', 'AST']:
            model_path = f"{model_dir}/{stat}_predictor.pkl"
            if os.path.exists(model_path):
                try:
                    self.ml_models[stat] = joblib.load(model_path)
                    self.use_ml = True
                except Exception as e:
                    print(f"⚠️  Could not load {stat} model: {e}")
        
        if self.use_ml:
            print(f"✅ Loaded data (two-season blend: {blend_mode})")
            print(f"  Players: {len(self.players)} rows across 2024-25 and 2025-26")
            print(f"  Teams:   {len(self.pace)} teams with blended ratings")
            print(f"  🤖 ML Models: Loaded ({', '.join(self.ml_models.keys())})")
        else:
            print(f"✅ Loaded data (two-season blend: {blend_mode})")
            print(f"  Players: {len(self.players)} rows across 2024-25 and 2025-26")
            print(f"  Teams:   {len(self.pace)} teams with blended ratings")
            print(f"  📊 Using heuristic predictions (train ML models for better accuracy)")
    
    def get_player_features(self, player_name, opponent_team, system_fit_weight: float = 0.0, 
                           recent_form_weight: float = 0.0, h2h_weight: float = 0.0):
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
        - Predicted points/rebounds/assists
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
        
        # System fit adjustment (if enabled)
        system_fit_multiplier = 1.0
        offensive_fit = 1.0
        defensive_matchup = 1.0
        
        # Recent form adjustment (if enabled) - Skip if weight is 0 to save time
        recent_form_multiplier = 1.0
        if recent_form_weight > 0:
            try:
                # Use in-memory cache first (fastest)
                if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                    game_log = self._gamelog_cache[player_name]
                else:
                    # Fallback to file cache
                    if not hasattr(self, '_hot_tracker'):
                        from src.analysis.hot_hand_tracker import HotHandTracker
                        self._hot_tracker = HotHandTracker(blend_mode="latest")
                    game_log = self._hot_tracker.get_player_gamelog(player_name, season='2025-26', use_cache=True)
                    # Cache in memory for next time
                    if game_log is not None and len(game_log) > 0:
                        if not hasattr(self, '_gamelog_cache'):
                            self._gamelog_cache = {}
                        self._gamelog_cache[player_name] = game_log
                
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
                    
                    # Apply weight: 1.0 + (form - 1.0) * weight
                    recent_form_multiplier = 1.0 + (avg_form - 1.0) * recent_form_weight
            except Exception:
                # If recent form check fails, continue without it
                pass
        
        # H2H adjustment (if enabled) - Skip if weight is 0 to save time
        h2h_multiplier = 1.0
        if h2h_weight > 0:
            try:
                # Use cached H2H data if available
                h2h_cache_key = f"{player_name}_{opponent_team}"
                if hasattr(self, '_h2h_cache') and h2h_cache_key in self._h2h_cache:
                    h2h = self._h2h_cache[h2h_cache_key]
                else:
                    from src.utils.h2h_stats import get_h2h_summary
                    # Use cached game logs if available (faster)
                    if hasattr(self, '_gamelog_cache') and player_name in self._gamelog_cache:
                        # Create a temporary tracker with cached logs
                        from src.analysis.hot_hand_tracker import HotHandTracker
                        if not hasattr(self, '_hot_tracker'):
                            self._hot_tracker = HotHandTracker(blend_mode="latest")
                        
                        # Get H2H from cached logs directly (faster than full get_h2h_summary)
                        game_log = self._gamelog_cache[player_name]
                        if game_log is not None and 'MATCHUP' in game_log.columns:
                            game_log = game_log.copy()
                            # Parse opponent from matchup string (e.g., "LAL vs. GSW" or "LAL @ GSW")
                            def parse_opp(matchup_str):
                                if pd.isna(matchup_str):
                                    return None
                                matchup_str = str(matchup_str)
                                if ' vs. ' in matchup_str:
                                    parts = matchup_str.split(' vs. ')
                                elif ' @ ' in matchup_str:
                                    parts = matchup_str.split(' @ ')
                                else:
                                    return None
                                if len(parts) == 2:
                                    # Return the opponent (second part)
                                    return parts[1].strip()
                                return None
                            
                            game_log['OPP'] = game_log['MATCHUP'].apply(parse_opp)
                            h2h_games = game_log[game_log['OPP'] == opponent_team]
                            if len(h2h_games) >= 2:
                                h2h = {
                                    'total_games': len(h2h_games),
                                    'avg_pts': float(h2h_games['PTS'].mean()) if 'PTS' in h2h_games.columns else 0,
                                    'avg_reb': float(h2h_games['REB'].mean()) if 'REB' in h2h_games.columns else 0,
                                    'avg_ast': float(h2h_games['AST'].mean()) if 'AST' in h2h_games.columns else 0
                                }
                            else:
                                h2h = None
                        else:
                            h2h = get_h2h_summary(player_name, opponent_team, season='2025-26')
                    else:
                        h2h = get_h2h_summary(player_name, opponent_team, season='2025-26')
                    
                    # Cache H2H result
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
                    
                    # Apply weight
                    h2h_multiplier = 1.0 + (avg_h2h - 1.0) * h2h_weight
            except Exception:
                # If H2H check fails, continue without it
                pass
        
        if system_fit_weight > 0:
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
                
                # Apply weighted system fit
                # system_fit_multiplier = 1.0 + (fit_data['fit_score'] - 1.0) * system_fit_weight
                # More nuanced: blend offensive fit and defensive matchup
                system_fit_multiplier = 1.0 + (
                    (offensive_fit - 1.0) * 0.6 + (defensive_matchup - 1.0) * 0.4
                ) * system_fit_weight
                
            except Exception:
                # If system profile fails, continue without it
                pass
        
        # Build features
        features = {
            'player_name': player_name,
            'team': player['TEAM_ABBREVIATION'],
            'opponent': opponent_team,
            
            # Player averages
            'season_ppg': player['PTS'],
            'season_rpg': player['REB'],
            'season_apg': player['AST'],
            'season_fg_pct': player['FG_PCT'],
            'games_played': player['GP'],
            'minutes': player['MIN'],
            
            # Matchup factors
            'expected_pace': expected_pace,
            'opponent_def_rating': def_rating,  # Use capped value
            'opponent_off_rating': float(opp['OFF_RATING']) if float(opp['OFF_RATING']) <= 130 else 110.0,  # Cap OFF_RATING too
            'pace_factor': pace_factor,
            'def_factor': def_factor,
            
            # System fit (if enabled)
            'system_fit_multiplier': system_fit_multiplier,
            'offensive_fit': offensive_fit,
            'defensive_matchup': defensive_matchup,
            
            # Recent form and H2H (if enabled)
            'recent_form_multiplier': recent_form_multiplier,
            'h2h_multiplier': h2h_multiplier,
        }
        
        # PREDICTION: Use ML if available, else heuristics
        if self.use_ml and all(stat in self.ml_models for stat in ['PTS', 'REB', 'AST']):
            # Build feature array (same order as training)
            feature_array = np.array([[
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
                features['def_factor']
            ]])
            
            # ML predictions
            base_points = float(self.ml_models['PTS'].predict(feature_array)[0])
            base_rebounds = float(self.ml_models['REB'].predict(feature_array)[0])
            base_assists = float(self.ml_models['AST'].predict(feature_array)[0])
            
            # Apply all multipliers if enabled
            combined_multiplier = system_fit_multiplier * recent_form_multiplier * h2h_multiplier
            features['predicted_points'] = base_points * combined_multiplier
            features['predicted_rebounds'] = base_rebounds * combined_multiplier
            features['predicted_assists'] = base_assists * combined_multiplier
        else:
            # Fallback to heuristics (simple multipliers)
            # Apply all multipliers if enabled
            base_points = player['PTS'] * pace_factor * def_factor
            base_rebounds = player['REB'] * pace_factor
            base_assists = player['AST'] * pace_factor
            
            combined_multiplier = system_fit_multiplier * recent_form_multiplier * h2h_multiplier
            features['predicted_points'] = base_points * combined_multiplier
            features['predicted_rebounds'] = base_rebounds * combined_multiplier
            features['predicted_assists'] = base_assists * combined_multiplier
        
        return features
    
    def get_all_matchups(self, games_today, system_fit_weight: float = 0.0, 
                        recent_form_weight: float = 0.0, h2h_weight: float = 0.0):
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
        
        # Pre-initialize analyzers if weights are enabled (to cache instances)
        if system_fit_weight > 0:
            if not hasattr(self, '_profile_analyzer'):
                from src.services.system_profile_analyzer import SystemProfileAnalyzer
                self._profile_analyzer = SystemProfileAnalyzer()
                # Pre-cache all team profiles for today's games
                for team in game_teams:
                    self._profile_analyzer.get_offensive_profile(team)
                    self._profile_analyzer.get_defensive_profile(team)
        
        # Pre-fetch and cache game logs for all players if recent form or H2H is enabled
        if recent_form_weight > 0 or h2h_weight > 0:
            if not hasattr(self, '_hot_tracker'):
                from src.analysis.hot_hand_tracker import HotHandTracker
                self._hot_tracker = HotHandTracker(blend_mode="latest")
            
            # In-memory cache for game logs (avoid repeated file reads)
            if not hasattr(self, '_gamelog_cache'):
                self._gamelog_cache = {}
            
            # Pre-fetch game logs for all players (uses file cache, so fast if already cached)
            # This ensures all logs are in memory before we start processing
            all_player_names = set()
            for game in games_today:
                home_players = players_today[players_today['TEAM_ABBREVIATION'] == game['home']]
                away_players = players_today[players_today['TEAM_ABBREVIATION'] == game['away']]
                for _, p in home_players.iterrows():
                    all_player_names.add(p['PLAYER_NAME'])
                for _, p in away_players.iterrows():
                    all_player_names.add(p['PLAYER_NAME'])
            
            # Pre-load game logs into memory cache (only if not already cached)
            for player_name in all_player_names:
                if player_name not in self._gamelog_cache:
                    try:
                        log = self._hot_tracker.get_player_gamelog(player_name, season='2025-26', use_cache=True)
                        if log is not None and len(log) > 0:
                            self._gamelog_cache[player_name] = log
                    except Exception:
                        pass  # If fetch fails, will try again later
        
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
            
            for _, player in home_players.iterrows():
                features = self.get_player_features(
                    player['PLAYER_NAME'], away, 
                    system_fit_weight=system_fit_weight,
                    recent_form_weight=recent_form_weight,
                    h2h_weight=h2h_weight
                )
                if features:
                    all_features.append(features)
            
            for _, player in away_players.iterrows():
                features = self.get_player_features(
                    player['PLAYER_NAME'], home,
                    system_fit_weight=system_fit_weight,
                    recent_form_weight=recent_form_weight,
                    h2h_weight=h2h_weight
                )
                if features:
                    all_features.append(features)
        
        return pd.DataFrame(all_features)


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