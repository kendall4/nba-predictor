"""
Step 1: Build Training Dataset
===============================
This script creates training data by:
1. Loading historical games (2024-25, 2025-26)
2. For each game, matching player features with ACTUAL outcomes
3. The "target" is what the player ACTUALLY scored in that game
4. The "features" are: season averages, opponent defense, pace, etc.

This teaches the model: "Given these conditions, player X scored Y"
"""

import pandas as pd
import numpy as np
from pathlib import Path
import os

# We'll need game-by-game player stats (we'll fetch if not cached)
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players as static_players
import time

def load_season_data():
    """Load our aggregated season stats"""
    players_2024 = pd.read_csv('data/raw/player_stats_2024-25.csv')
    players_2025 = pd.read_csv('data/raw/player_stats_2025-26.csv')
    pace_2024 = pd.read_csv('data/raw/team_pace_2024-25.csv')
    pace_2025 = pd.read_csv('data/raw/team_pace_2025-26.csv')
    
    # Merge seasons
    players_all = pd.concat([
        players_2024.assign(SEASON='2024-25'),
        players_2025.assign(SEASON='2025-26')
    ], ignore_index=True)
    
    pace_all = pd.concat([
        pace_2024.assign(SEASON='2024-25'),
        pace_2025.assign(SEASON='2025-26')
    ], ignore_index=True)
    
    return players_all, pace_all

def lookup_player_id(player_name):
    """Find NBA API player ID"""
    matches = [p for p in static_players.get_players() 
               if p['full_name'].lower() == player_name.lower()]
    if not matches:
        matches = [p for p in static_players.get_players() 
                   if player_name.lower() in p['full_name'].lower()]
    return matches[0]['id'] if matches else None

def get_player_gamelog_cached(player_id, season, cache_dir='data/cache/gamelogs'):
    """Get game-by-game stats (what player ACTUALLY did each game)"""
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = f"{cache_dir}/player_{player_id}_{season.replace('/', '-')}.csv"
    
    if os.path.exists(cache_path):
        return pd.read_csv(cache_path)
    
    # Fetch from NBA API
    try:
        time.sleep(0.6)  # Rate limit
        logs = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star='Regular Season'
        )
        df = logs.get_data_frames()[0]
        df.to_csv(cache_path, index=False)
        return df
    except Exception as e:
        print(f"Error fetching {player_id} {season}: {e}")
        return None

def build_training_examples(season='2025-26', sample_size=None):
    """
    Build training dataset: features + actual outcomes
    
    Returns DataFrame with columns:
    - Feature columns (season_ppg, opponent_def_rating, etc.)
    - Target columns (actual_PTS, actual_REB, actual_AST)
    """
    print(f"📊 Building training data for {season}...")
    
    players_all, pace_all = load_season_data()
    
    # Filter to season
    players_season = players_all[players_all['SEASON'] == season].copy()
    pace_season = pace_all[pace_all['SEASON'] == season].copy()
    
    # Build team abbreviation mapping
    team_map = (
        players_season[['TEAM_ID', 'TEAM_ABBREVIATION']]
        .drop_duplicates()
    )
    pace_season = pace_season.merge(team_map, on='TEAM_ID', how='left')
    
    # Sample players if requested (for faster testing)
    if sample_size:
        players_season = players_season.sample(n=min(sample_size, len(players_season)))
    
    training_rows = []
    
    print(f"Processing {len(players_season)} players...")
    
    for idx, player_row in players_season.iterrows():
        player_name = player_row['PLAYER_NAME']
        player_id = player_row.get('PLAYER_ID')
        
        if pd.isna(player_id):
            # Try to look up ID
            player_id = lookup_player_id(player_name)
            if player_id is None:
                continue
        
        # Get this player's game-by-game stats (the TARGETS)
        gamelog = get_player_gamelog_cached(int(player_id), season)
        if gamelog is None or len(gamelog) == 0:
            continue
        
        # For each game in the log, build features
        for _, game_row in gamelog.iterrows():
            matchup_str = game_row.get('MATCHUP', '')
            # Parse opponent (e.g., "LAL vs. GSW" or "LAL @ GSW")
            if 'vs.' in matchup_str:
                parts = matchup_str.split(' vs. ')
            elif '@' in matchup_str:
                parts = matchup_str.split(' @ ')
            else:
                continue
            
            if len(parts) != 2:
                continue
            
            player_team = parts[0].strip()
            opponent_team = parts[1].strip()
            
            # Get player's season stats up to this point (rolling average)
            # For simplicity, use full season average (we can improve this later)
            player_season = player_row
            
            # Get opponent's pace/defense
            opp_pace = pace_season[pace_season['TEAM_ABBREVIATION'] == opponent_team]
            if len(opp_pace) == 0:
                continue
            opp_pace = opp_pace.iloc[0]
            
            # Get player's team pace
            team_pace = pace_season[pace_season['TEAM_ABBREVIATION'] == player_team]
            if len(team_pace) == 0:
                continue
            team_pace = team_pace.iloc[0]
            
            # Calculate features (same as prediction features)
            expected_pace = (team_pace['PACE'] + opp_pace['PACE']) / 2
            pace_factor = expected_pace / 100.0
            def_factor = opp_pace['DEF_RATING'] / 112.0
            
            # ACTUAL outcomes from this game (what we're trying to predict)
            actual_pts = game_row.get('PTS', 0)
            actual_reb = game_row.get('REB', 0)
            actual_ast = game_row.get('AST', 0)
            
            # Skip if missing data
            if pd.isna(actual_pts) or pd.isna(actual_reb) or pd.isna(actual_ast):
                continue
            
            training_rows.append({
                # FEATURES (inputs to model)
                'player_name': player_name,
                'season_ppg': player_season['PTS'],
                'season_rpg': player_season['REB'],
                'season_apg': player_season['AST'],
                'season_fg_pct': player_season['FG_PCT'],
                'games_played': player_season['GP'],
                'minutes': player_season['MIN'],
                'expected_pace': expected_pace,
                'opponent_def_rating': opp_pace['DEF_RATING'],
                'opponent_off_rating': opp_pace['OFF_RATING'],
                'pace_factor': pace_factor,
                'def_factor': def_factor,
                'opponent': opponent_team,
                
                # TARGETS (what we're predicting)
                'actual_PTS': float(actual_pts),
                'actual_REB': float(actual_reb),
                'actual_AST': float(actual_ast),
            })
        
        if (idx + 1) % 10 == 0:
            print(f"  Processed {idx + 1}/{len(players_season)} players...")
    
    df = pd.DataFrame(training_rows)
    print(f"\n✅ Built {len(df)} training examples")
    print(f"   Average actual points: {df['actual_PTS'].mean():.1f}")
    print(f"   Average actual rebounds: {df['actual_REB'].mean():.1f}")
    print(f"   Average actual assists: {df['actual_AST'].mean():.1f}")
    
    return df

if __name__ == "__main__":
    # Build for both seasons (or start with 2025-26)
    print("=" * 70)
    print("🏋️  TRAINING DATA BUILDER")
    print("=" * 70)
    
    # Start with 2025-26 (more recent = better predictions)
    df = build_training_examples(season='2025-26', sample_size=None)
    
    # Save training data
    os.makedirs('data/processed', exist_ok=True)
    df.to_csv('data/processed/training_data_2025-26.csv', index=False)
    print(f"\n💾 Saved to data/processed/training_data_2025-26.csv")
    print("\n📊 Preview:")
    print(df[['player_name', 'season_ppg', 'actual_PTS', 'opponent_def_rating']].head(10))
    print("\n✅ Ready for training!")

