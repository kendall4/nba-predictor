import pandas as pd
import numpy as np
from datetime import datetime
from nba_api.stats.static import players as static_players
from nba_api.stats.endpoints import playergamelog
import os
import time
import warnings

STAT_COL_MAP = {
    'points': 'PTS',
    'rebounds': 'REB',
    'assists': 'AST',
    'threes': 'FG3M'
}

class HotHandTracker:
    """
    Track players who start hot (5+ or 10+ in Q1)
    Predict if they'll stay hot based on historical patterns
    Also provides consistency checks (last N, H2H, season 2025-26).
    """

    def __init__(self, blend_mode: str = "mean", cache_dir: str = "data/cache"):
        p1 = pd.read_csv('data/raw/player_stats_2024-25.csv')
        p1['SEASON'] = '2024-25'
        p2 = pd.read_csv('data/raw/player_stats_2025-26.csv')
        p2['SEASON'] = '2025-26'
        players_all = pd.concat([p1, p2], ignore_index=True)

        if blend_mode == "latest":
            players_all = (
                players_all.sort_values('SEASON')
                .drop_duplicates(subset=['PLAYER_ID'], keep='last')
            )
        else:
            num_cols = ['PTS','REB','AST','FG_PCT','GP','MIN']
            players_all = (
                players_all
                .groupby(['PLAYER_ID','PLAYER_NAME','TEAM_ABBREVIATION'], as_index=False)[num_cols]
                .mean()
            )

        self.players = players_all
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

        # Safe print for Streamlit (avoid BrokenPipeError)
        try:
            print("✅ Hot Hand Tracker loaded (two-season baselines)")
            print(f"   {len(self.players)} players analyzed")
            print("\n⚠️  NOTE: Using season-level data for hot-hand logic; gamelogs fetched on-demand for consistency")
        except (BrokenPipeError, OSError):
            # Streamlit context - print statements can cause pipe errors
            pass

    def get_player_baseline(self, player_name):
        """Get player's blended season averages"""
        player = self.players[self.players['PLAYER_NAME'] == player_name]
        if len(player) == 0:
            return None
        return player.iloc[0]

    # ---------------------------
    # Consistency: helper methods
    # ---------------------------
    def _lookup_player_id(self, player_name):
        result = [p for p in static_players.get_players() if p['full_name'].lower() == player_name.lower()]
        if not result:
            result = [p for p in static_players.get_players() if player_name.lower() in p['full_name'].lower()]
        return result[0]['id'] if result else None

    def _player_log_cache_path(self, player_id, season):
        safe_season = season.replace('/', '-')
        return os.path.join(self.cache_dir, f"player_log_{player_id}_{safe_season}.csv")

    def get_player_gamelog(self, player_name, season='2025-26', use_cache=True):
        """
        Fetch player's game log for the season. Caches to data/cache/.
        """
        pid = self._lookup_player_id(player_name)
        if pid is None:
            return None

        cache_path = self._player_log_cache_path(pid, season)
        if use_cache and os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                if df is not None and len(df) > 0:
                    return df
                # If cached file is empty, don't use it - fetch fresh
            except Exception:
                pass

        # Fetch from NBA API with retry logic and timeout handling
        max_retries = 1  # Reduced to 1 retry for faster failure
        df = None
        
        for attempt in range(max_retries + 1):
            try:
                logs = playergamelog.PlayerGameLog(
                    player_id=pid, 
                    season=season, 
                    season_type_all_star='Regular Season'
                )
                df = logs.get_data_frames()[0]
                
                # Check if dataframe is empty (no games in season yet)
                if df is not None and len(df) > 0:
                    break  # Success, exit retry loop
                elif df is not None and len(df) == 0:
                    # Empty dataframe - season might not have started yet
                    # Try previous season as fallback (only if current season is 2025-26)
                    if season == '2025-26':
                        try:
                            logs_prev = playergamelog.PlayerGameLog(player_id=pid, season='2024-25', season_type_all_star='Regular Season')
                            df_prev = logs_prev.get_data_frames()[0]
                            if df_prev is not None and len(df_prev) > 0:
                                df = df_prev  # Use fallback data
                                break  # Success with fallback
                        except Exception:
                            pass
                    # If still empty after fallback attempt, continue to next attempt or return None
                    if df is not None and len(df) == 0:
                        # Don't return empty df - try again or return None
                        continue
                
            except Exception as e:
                error_str = str(e).lower()
                is_timeout = (
                    'timeout' in error_str or
                    'read timed out' in error_str or
                    'connection' in error_str or
                    'HTTPSConnectionPool' in str(e)
                )
                
                # If it's the last attempt, try fallback then give up
                if attempt >= max_retries:
                    # Quick fallback to previous season if current season fails
                    if season == '2025-26':
                        try:
                            logs_prev = playergamelog.PlayerGameLog(player_id=pid, season='2024-25', season_type_all_star='Regular Season')
                            df_prev = logs_prev.get_data_frames()[0]
                            if df_prev is not None and len(df_prev) > 0:
                                df = df_prev  # Use fallback data
                                break  # Success with fallback
                        except Exception:
                            pass
                    # If we still don't have data after fallback, return None
                    if df is None or (df is not None and len(df) == 0):
                        return None
                    break  # We got fallback data
                
                # For timeouts, quick retry (reduced delays)
                if is_timeout:
                    delay = 0.5  # Much shorter delay - just 500ms
                    time.sleep(delay)
                else:
                    # For non-timeout errors, give up immediately
                    return None
        
        # If we got here but df is still None or empty, something went wrong
        if df is None or len(df) == 0:
            return None
        
        wanted_cols = ['GAME_DATE', 'MATCHUP', 'PTS', 'REB', 'AST', 'FG3M']
        for c in wanted_cols:
            if c not in df.columns:
                df[c] = np.nan
        df = df.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)

        # Only cache if we have actual data (don't cache empty dataframes)
        if len(df) > 0:
            try:
                df.to_csv(cache_path, index=False)
            except Exception:
                pass

        return df

    def _parse_opponent_from_matchup(self, matchup_str, team_abbr=None):
        """
        MATCHUP examples: 'BOS vs NYK', 'LAL @ GSW'
        Extract and return opponent tricode.
        """
        if not isinstance(matchup_str, str):
            return None
        parts = matchup_str.split(' ')
        if len(parts) >= 3:
            return parts[2].strip()
        return matchup_str[-3:].upper()

    def _calc_hit_rate(self, df, stat_type, line):
        col = STAT_COL_MAP.get(stat_type)
        if col is None or df is None or df.empty:
            return {'games': 0, 'hits': 0, 'hit_rate': 0.0}
        valid = df[pd.notna(df[col])]
        if valid.empty:
            return {'games': 0, 'hits': 0, 'hit_rate': 0.0}
        hits = (valid[col] >= line).sum()
        games = len(valid)
        return {'games': games, 'hits': int(hits), 'hit_rate': hits / games if games else 0.0}

    # ---------------------------
    # Public consistency APIs
    # ---------------------------
    def consistency_last_n(self, player_name, stat_type, line, n=5, season='2025-26'):
        df = self.get_player_gamelog(player_name, season=season)
        if df is None or df.empty:
            return {'player': player_name, 'scope': f'Last {n}', 'stat': stat_type, 'line': line, 'games': 0, 'hits': 0, 'hit_rate': 0.0}
        sample = df.head(n).copy()
        rate = self._calc_hit_rate(sample, stat_type, line)
        rate.update({'player': player_name, 'scope': f'Last {n}', 'stat': stat_type, 'line': line})
        return rate

    def consistency_season(self, player_name, stat_type, line, season='2025-26'):
        df = self.get_player_gamelog(player_name, season=season)
        rate = self._calc_hit_rate(df, stat_type, line)
        rate.update({'player': player_name, 'scope': f'Season {season}', 'stat': stat_type, 'line': line})
        return rate

    def consistency_h2h(self, player_name, stat_type, line, opponent_tricode, season='2025-26'):
        """
        Get H2H consistency. If current season has < 5 games, include previous season.
        Returns last 5 H2H games total (prioritizing current season, then previous).
        """
        h2h_games = []
        
        # Try current season first
        df_current = self.get_player_gamelog(player_name, season=season)
        if df_current is not None and not df_current.empty:
            df_current = df_current.copy()
            df_current['OPP'] = df_current['MATCHUP'].apply(self._parse_opponent_from_matchup)
            h2h_current = df_current[df_current['OPP'] == opponent_tricode]
            if len(h2h_current) > 0:
                h2h_games.append(h2h_current)
        
        # If we don't have at least 5 games, try previous season
        total_h2h = len(h2h_games[0]) if h2h_games else 0
        if total_h2h < 5:
            prev_season = '2024-25' if season == '2025-26' else '2025-26'
            df_prev = self.get_player_gamelog(player_name, season=prev_season)
            if df_prev is not None and not df_prev.empty:
                df_prev = df_prev.copy()
                df_prev['OPP'] = df_prev['MATCHUP'].apply(self._parse_opponent_from_matchup)
                h2h_prev = df_prev[df_prev['OPP'] == opponent_tricode]
                if len(h2h_prev) > 0:
                    h2h_games.append(h2h_prev)
        
        # Combine all H2H games and take last 5
        if not h2h_games:
            return {'player': player_name, 'scope': f'H2H vs {opponent_tricode}', 'stat': stat_type, 'line': line, 'games': 0, 'hits': 0, 'hit_rate': 0.0}
        
        h2h_combined = pd.concat(h2h_games, ignore_index=True)
        # Sort by date descending (newest first), take last 5
        if 'GAME_DATE' in h2h_combined.columns:
            h2h_combined = h2h_combined.sort_values('GAME_DATE', ascending=False)
        h2h_final = h2h_combined.head(5)
        
        rate = self._calc_hit_rate(h2h_final, stat_type, line)
        rate.update({'player': player_name, 'scope': f'H2H vs {opponent_tricode} (last 5)', 'stat': stat_type, 'line': line})
        return rate

    # ---------------------------
    # Existing hot-hand logic
    # ---------------------------
    def estimate_consistency_rate(self, player_name, stat_type='points', threshold=5):
        """
        Estimate continuation based on player archetype from season averages.
        
        Args:
            player_name: Player name
            stat_type: 'points', 'rebounds', or 'assists'
            threshold: Hot threshold for Q1 (default varies by stat type)
        """
        player = self.get_player_baseline(player_name)
        if player is None:
            return None

        mpg = player['MIN']
        ppg = player['PTS']
        rpg = player['REB']
        apg = player['AST']
        
        # Default thresholds if not provided
        if stat_type == 'points':
            stat_value = ppg
            if threshold == 5:  # Use default thresholds
                threshold = 5 if ppg < 20 else 10
        elif stat_type == 'rebounds':
            stat_value = rpg
            if threshold == 5:  # Use default thresholds
                threshold = 3 if rpg < 8 else 5
        elif stat_type == 'assists':
            stat_value = apg
            if threshold == 5:  # Use default thresholds
                threshold = 2 if apg < 6 else 4
        else:
            stat_value = ppg  # Fallback to points
        
        # Points archetypes
        if stat_type == 'points':
            if ppg >= 25 and mpg >= 32:
                archetype = "SUPERSTAR"; q2_rate = 0.85; q3_rate = 0.80; q4_rate = 0.75; all_quarters = 0.65
            elif ppg >= 18 and mpg >= 28:
                archetype = "STAR"; q2_rate = 0.75; q3_rate = 0.65; q4_rate = 0.60; all_quarters = 0.45
            elif ppg >= 12 and mpg >= 20:
                archetype = "STARTER"; q2_rate = 0.65; q3_rate = 0.55; q4_rate = 0.50; all_quarters = 0.35
            else:
                archetype = "ROLE PLAYER"; q2_rate = 0.50; q3_rate = 0.40; q4_rate = 0.35; all_quarters = 0.25
        
        # Rebounds archetypes (based on RPG and position/role)
        elif stat_type == 'rebounds':
            if rpg >= 12 and mpg >= 30:
                archetype = "ELITE REBOUNDER"; q2_rate = 0.80; q3_rate = 0.75; q4_rate = 0.70; all_quarters = 0.60
            elif rpg >= 8 and mpg >= 25:
                archetype = "STRONG REBOUNDER"; q2_rate = 0.70; q3_rate = 0.65; q4_rate = 0.60; all_quarters = 0.50
            elif rpg >= 5 and mpg >= 20:
                archetype = "SOLID REBOUNDER"; q2_rate = 0.60; q3_rate = 0.55; q4_rate = 0.50; all_quarters = 0.40
            else:
                archetype = "OCCASIONAL REBOUNDER"; q2_rate = 0.50; q3_rate = 0.45; q4_rate = 0.40; all_quarters = 0.30
        
        # Assists archetypes (based on APG and role)
        elif stat_type == 'assists':
            if apg >= 8 and mpg >= 30:
                archetype = "ELITE PLAYMAKER"; q2_rate = 0.85; q3_rate = 0.80; q4_rate = 0.75; all_quarters = 0.65
            elif apg >= 5 and mpg >= 25:
                archetype = "STRONG PLAYMAKER"; q2_rate = 0.75; q3_rate = 0.70; q4_rate = 0.65; all_quarters = 0.55
            elif apg >= 3 and mpg >= 20:
                archetype = "SOLID PLAYMAKER"; q2_rate = 0.65; q3_rate = 0.60; q4_rate = 0.55; all_quarters = 0.45
            else:
                archetype = "OCCASIONAL PLAYMAKER"; q2_rate = 0.55; q3_rate = 0.50; q4_rate = 0.45; all_quarters = 0.35
        
        else:
            # Fallback
            archetype = "AVERAGE"; q2_rate = 0.60; q3_rate = 0.55; q4_rate = 0.50; all_quarters = 0.40

        return {
            'player_name': player_name,
            'stat_type': stat_type,
            'archetype': archetype,
            'season_ppg': ppg,
            'season_rpg': rpg,
            'season_apg': apg,
            'season_mpg': mpg,
            'season_stat': stat_value,
            'threshold': threshold,
            'q2_continuation': q2_rate,
            'q3_continuation': q3_rate,
            'q4_continuation': q4_rate,
            'all_quarters_rate': all_quarters,
        }

    def predict_from_hot_q1(self, player_name, q1_stat_value, stat_type='points', threshold=None):
        """
        Player just got X stat in Q1. Predict their final total based on player archetype.
        
        Args:
            player_name: Player name
            q1_stat_value: Stat value in Q1 (points, rebounds, or assists)
            stat_type: 'points', 'rebounds', or 'assists'
            threshold: Hot threshold (auto-determined if None)
        """
        # Auto-determine threshold if not provided
        if threshold is None:
            player = self.get_player_baseline(player_name)
            if player is None:
                return {'error': f'Player "{player_name}" not found'}
            
            if stat_type == 'points':
                threshold = 5 if player['PTS'] < 20 else 10
            elif stat_type == 'rebounds':
                threshold = 3 if player['REB'] < 8 else 5
            elif stat_type == 'assists':
                threshold = 2 if player['AST'] < 6 else 4
            else:
                threshold = 5
        
        consistency = self.estimate_consistency_rate(player_name, stat_type=stat_type, threshold=threshold)
        if consistency is None:
            return {
                'error': f'Player "{player_name}" not found',
                'note': 'Check spelling or update to 2025-26 season data'
            }

        if q1_stat_value >= threshold:
            expected_q2 = q1_stat_value * consistency['q2_continuation']
            expected_q3 = q1_stat_value * consistency['q3_continuation']
            expected_q4 = q1_stat_value * consistency['q4_continuation']
            predicted_total = q1_stat_value + expected_q2 + expected_q3 + expected_q4
            
            # Get season average for the stat type
            if stat_type == 'points':
                season_avg = consistency['season_ppg']
            elif stat_type == 'rebounds':
                season_avg = consistency['season_rpg']
            elif stat_type == 'assists':
                season_avg = consistency['season_apg']
            else:
                season_avg = consistency['season_stat']
            
            above_avg = predicted_total - season_avg
            
            return {
                'player_name': player_name,
                'stat_type': stat_type,
                'archetype': consistency['archetype'],
                'q1_actual': q1_stat_value,
                'predicted_q2': expected_q2,
                'predicted_q3': expected_q3,
                'predicted_q4': expected_q4,
                'predicted_total': predicted_total,
                'season_average': season_avg,
                'vs_average': above_avg,
                'consistency_score': consistency['all_quarters_rate'],
                'confidence': 'HIGH' if consistency['all_quarters_rate'] > 0.5 else 'MEDIUM' if consistency['all_quarters_rate'] > 0.35 else 'LOW',
                'threshold': threshold
            }
        else:
            # Get season average for the stat type
            if stat_type == 'points':
                season_avg = consistency['season_ppg']
            elif stat_type == 'rebounds':
                season_avg = consistency['season_rpg']
            elif stat_type == 'assists':
                season_avg = consistency['season_apg']
            else:
                season_avg = consistency['season_stat']
            
            return {
                'player_name': player_name,
                'stat_type': stat_type,
                'q1_actual': q1_stat_value,
                'season_average': season_avg,
                'threshold': threshold,
                'note': f'Below {threshold} {stat_type} threshold - not a hot start'
            }


# Test it
if __name__ == "__main__":
    print("=" * 70)
    print("🔥 HOT HAND TRACKER - Testing")
    print("=" * 70)
    
    tracker = HotHandTracker()
    
    # Example: Bam just scored 18 in Q1
    print("\n📊 Example: Bam Adebayo - 18 points in Q1")
    print("=" * 70)
    
    prediction = tracker.predict_from_hot_q1('Bam Adebayo', 18, threshold=5)
    
    if 'error' in prediction:
        print(f"\n❌ {prediction['error']}")
        print(f"   {prediction['note']}")
    elif 'predicted_total' in prediction:
        print(f"\n🔥 HOT START DETECTED!")
        print(f"   Player Type: {prediction['archetype']}")
        print(f"   Q1: {prediction['q1_actual']} points")
        print(f"\n📈 Predicted Scoring:")
        print(f"   Q2: {prediction['predicted_q2']:.1f} points")
        print(f"   Q3: {prediction['predicted_q3']:.1f} points")
        print(f"   Q4: {prediction['predicted_q4']:.1f} points")
        print(f"\n🎯 PREDICTED TOTAL: {prediction['predicted_total']:.1f} points")
        print(f"   Season Average: {prediction['season_average']:.1f}")
        print(f"   vs Average: {prediction['vs_average']:+.1f}")
        print(f"\n💪 Consistency Score: {prediction['consistency_score']:.0%}")
        print(f"   Confidence: {prediction['confidence']}")
        
        if prediction['consistency_score'] < 0.4:
            print(f"\n⚠️  WARNING: {prediction['archetype']}s typically COOL OFF after hot starts")
            print(f"   Consider betting UNDER on their total")
        else:
            print(f"\n✅ {prediction['archetype']}s typically STAY HOT")
            print(f"   Good OVER candidate")
    else:
        print(f"\n{prediction['note']}")
    
    print("\n" + "=" * 70)
    
    # Try different player types
    print("\n📊 Comparing Different Player Types:")
    print("=" * 70)
    
    test_players = [
        ('Giannis Antetokounmpo', 15),  # Superstar
        ('Bam Adebayo', 12),             # Star/Starter
        ('Duncan Robinson', 10),         # Role player
    ]
    
    for player, q1 in test_players:
        pred = tracker.predict_from_hot_q1(player, q1, threshold=5)
        if 'predicted_total' in pred:
            print(f"\n{player} ({pred['archetype']})")
            print(f"  Q1: {q1} → Predicted: {pred['predicted_total']:.1f} (Consistency: {pred['consistency_score']:.0%})")