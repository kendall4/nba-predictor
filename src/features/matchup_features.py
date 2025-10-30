import pandas as pd
import numpy as np

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

        print(f"✅ Loaded data (two-season blend: {blend_mode})")
        print(f"  Players: {len(self.players)} rows across 2024-25 and 2025-26")
        print(f"  Teams:   {len(self.pace)} teams with blended ratings")
    
    def get_player_features(self, player_name, opponent_team):
        """
        Build features for: Player X vs Opponent Y
        
        Returns dict with:
        - Player's season averages
        - Opponent's defensive rating
        - Expected pace of game
        - Predicted points/rebounds/assists
        """
        
        # Find player
        player = self.players[self.players['PLAYER_NAME'] == player_name]
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
        expected_pace = (player_team['PACE'] + opp['PACE']) / 2
        
        # Pace adjustment factor (high pace = more opportunities)
        pace_factor = expected_pace / 100.0  # 100 is average pace
        
        # Defense adjustment (high DEF_RATING = weak defense = more points allowed)
        # NBA average DEF_RATING is ~112-115
        def_factor = opp['DEF_RATING'] / 112.0
        
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
            'opponent_def_rating': opp['DEF_RATING'],
            'opponent_off_rating': opp['OFF_RATING'],
            'pace_factor': pace_factor,
            'def_factor': def_factor,
            
            # Simple prediction (we'll improve this with ML later)
            'predicted_points': player['PTS'] * pace_factor * def_factor,
            'predicted_rebounds': player['REB'] * pace_factor,
            'predicted_assists': player['AST'] * pace_factor,
        }
        
        return features
    
    def get_all_matchups(self, games_today):
        """
        Get features for all players in today's games
        
        games_today format:
        [
            {'home': 'LAL', 'away': 'GSW'},
            {'home': 'BOS', 'away': 'MIA'},
        ]
        """
        all_features = []
        
        for game in games_today:
            home = game['home']
            away = game['away']
            
            # Get all players from both teams
            home_players = self.players[self.players['TEAM_ABBREVIATION'] == home]
            away_players = self.players[self.players['TEAM_ABBREVIATION'] == away]

            # Safety: ensure unique players per team (in case of residual duplicates)
            if 'PLAYER_ID' in home_players.columns:
                home_players = home_players.drop_duplicates(subset=['PLAYER_ID'])
            else:
                home_players = home_players.drop_duplicates(subset=['PLAYER_NAME'])
            if 'PLAYER_ID' in away_players.columns:
                away_players = away_players.drop_duplicates(subset=['PLAYER_ID'])
            else:
                away_players = away_players.drop_duplicates(subset=['PLAYER_NAME'])
            
            # Build features for each player
            for _, player in home_players.iterrows():
                features = self.get_player_features(player['PLAYER_NAME'], away)
                if features:
                    all_features.append(features)
            
            for _, player in away_players.iterrows():
                features = self.get_player_features(player['PLAYER_NAME'], home)
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