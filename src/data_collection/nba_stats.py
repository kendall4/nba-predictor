from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import leaguegamefinder, playergamelog, teamgamelog, leaguedashteamstats
import pandas as pd
import time

class NBAStatsCollector:
    """Using nba_api - the most reliable free option"""
    
    def __init__(self, season='2025-26'):  # Last complete season for training
        print(f"🏀 NBA Stats Collector using nba_api")
        print(f"📅 Season: {season}")
        self.season = season
        self.delay = 0.6  # 600ms between requests to avoid rate limits
    
    def get_season_games(self):
        """Get all games for the season"""
        print(f"\n📅 Getting {self.season} games...")
        
        # Get all season games
        gamefinder = leaguegamefinder.LeagueGameFinder(
            season_nullable=self.season,
            season_type_nullable='Regular Season'
        )
        
        games = gamefinder.get_data_frames()[0]
        
        print(f"✅ Found {len(games)} total games this season")
        print("\nSample games:")
        print(games[['GAME_DATE', 'MATCHUP', 'WL', 'PTS']].head(10))
        
        games.to_csv(f'data/raw/games_{self.season}.csv', index=False)
        print(f"\n💾 Saved to data/raw/games_{self.season}.csv")
        
        return games
    
    def get_team_pace_stats(self):
        """Get team PACE and efficiency - THE GOLD!"""
        print(f"\n🏃 Getting team PACE stats for {self.season}...")
        time.sleep(self.delay)
        
        # Get advanced team stats with PACE
        team_stats = leaguedashteamstats.LeagueDashTeamStats(
            season=self.season,
            season_type_all_star='Regular Season',
            measure_type_detailed_defense='Advanced',
            per_mode_detailed='PerGame'
        )
        
        df = team_stats.get_data_frames()[0]
        
        # Filter out WNBA teams (only keep NBA teams)
        nba_team_names = [
            'Hawks', 'Celtics', 'Nets', 'Hornets', 'Bulls', 'Cavaliers', 'Mavericks', 'Nuggets',
            'Pistons', 'Warriors', 'Rockets', 'Pacers', 'Clippers', 'Lakers', 'Grizzlies', 'Heat',
            'Bucks', 'Timberwolves', 'Pelicans', 'Knicks', 'Thunder', 'Magic', '76ers', 'Suns',
            'Trail Blazers', 'Kings', 'Spurs', 'Raptors', 'Jazz', 'Wizards'
        ]
        
        # Also filter by TEAM_ID if available (NBA team IDs are 1610612737-1610612766)
        if 'TEAM_ID' in df.columns:
            nba_team_ids = list(range(1610612737, 1610612767))
            df = df[df['TEAM_ID'].isin(nba_team_ids)]
        
        # Additional filter by team name keywords to catch any missed teams
        df = df[df['TEAM_NAME'].str.contains('|'.join(nba_team_names), case=False, na=False)]
        
        # Filter out teams with insufficient games (data quality issue)
        # Teams with < 15 games in early season have unreliable stats
        if 'GP' in df.columns:
            min_games = 15
            initial_count = len(df)
            df = df[df['GP'] >= min_games]
            filtered_count = initial_count - len(df)
            if filtered_count > 0:
                print(f"⚠️  Filtered out {filtered_count} teams with < {min_games} games (unreliable early-season data)")
        
        # Validate data quality - flag outliers
        if 'DEF_RATING' in df.columns and 'OFF_RATING' in df.columns and 'PACE' in df.columns:
            outliers = df[
                (df['DEF_RATING'] > 130) | (df['DEF_RATING'] < 80) |
                (df['OFF_RATING'] > 130) | (df['OFF_RATING'] < 80) |
                (df['PACE'] > 110) | (df['PACE'] < 85)
            ]
            if len(outliers) > 0:
                print(f"⚠️  Warning: {len(outliers)} teams have outlier stats (will use defaults in predictions):")
                print(outliers[['TEAM_NAME', 'DEF_RATING', 'OFF_RATING', 'PACE', 'GP']].to_string())
        
        # Show the important columns for predictions
        important_cols = ['TEAM_NAME', 'W', 'L', 'W_PCT', 'OFF_RATING', 'DEF_RATING', 'NET_RATING', 'PACE', 'GP']
        
        print(f"✅ Got stats for {len(df)} NBA teams (filtered)\n")
        print("Top 10 Teams by PACE (possessions per 48 min):")
        print(df[important_cols].sort_values('PACE', ascending=False).head(10))
        
        print("\n💡 Why PACE matters:")
        print("   High PACE = More possessions = More scoring opportunities")
        print("   Low DEF_RATING = Better defense (lower is better)")
        
        # Save it
        df.to_csv(f'data/raw/team_pace_{self.season}.csv', index=False)
        print(f"\n💾 Saved to data/raw/team_pace_{self.season}.csv")
        
        return df
    
    def get_player_stats(self):
        """Get all player stats for the season"""
        print(f"\n⭐ Getting player stats for {self.season}...")
        time.sleep(self.delay)
        
        from nba_api.stats.endpoints import leaguedashplayerstats
        
        player_stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season=self.season,
            season_type_all_star='Regular Season',
            per_mode_detailed='PerGame'
        )
        
        df = player_stats.get_data_frames()[0]
        
        print(f"✅ Got stats for {len(df)} players")
        print("\nTop 10 Scorers:")
        print(df.nlargest(10, 'PTS')[['PLAYER_NAME', 'TEAM_ABBREVIATION', 'PTS', 'REB', 'AST']])
        
        df.to_csv(f'data/raw/player_stats_{self.season}.csv', index=False)
        print(f"\n💾 Saved to data/raw/player_stats_{self.season}.csv")
        
        return df
    
    def get_defensive_matchups(self):
        """
        Get which teams are WEAK vs Guards/Forwards/Centers
        THIS IS THE GOLD for predictions!
        """
        print(f"\n🛡️  Getting defensive matchup data for {self.season}...")
        time.sleep(self.delay)
        
        from nba_api.stats.endpoints import leaguedashptteamdefend
        
        all_defense = []
        
        positions = {
            'Guard': 'G',
            'Forward': 'F',
            'Center': 'C'
        }
        
        for pos_name, pos_code in positions.items():
            print(f"  Fetching {pos_name} defense...")
            time.sleep(self.delay)
            
            defense = leaguedashptteamdefend.LeagueDashPtTeamDefend(
                season=self.season,
                season_type_all_star='Regular Season',
                defense_category=pos_name
            )
            
            df = defense.get_data_frames()[0]
            df['POSITION_DEFENDED'] = pos_name
            all_defense.append(df)
        
        # Combine all positions
        combined = pd.concat(all_defense, ignore_index=True)
        
        print("\n🎯 Teams that ALLOW THE MOST to each position:")
        for pos in positions.keys():
            pos_df = combined[combined['POSITION_DEFENDED'] == pos]
            worst = pos_df.nlargest(3, 'FG_PCT_ALLOWED')[['TEAM_NAME', 'FG_PCT_ALLOWED', 'FREQ']]
            print(f"\n{pos}s (Weak defenses):")
            print(worst)
        
        combined.to_csv(f'data/raw/defensive_matchups_{self.season}.csv', index=False)
        print(f"\n💾 Saved to data/raw/defensive_matchups_{self.season}.csv")
        
        return combined


if __name__ == "__main__":
    print("=" * 70)
    print("🏀 NBA STATS COLLECTOR - TRAINING DATA")
    print("=" * 70)
    print("\n📚 Strategy:")
    print("  1. Collect COMPLETE 2025-26 season data (for training)")
    print("  2. Build & validate ML model")
    print("  3. Apply to 2025-26 games (for predictions)")
    print("\n" + "=" * 70)
    
    # Get LAST COMPLETE season data for training
    collector = NBAStatsCollector(season='2025-26')
    
    try:
        # Test 1: Get all season games
        games = collector.get_season_games()
        
        # Test 2: Get team PACE stats (crucial for predictions!)
        print("\n" + "=" * 70)
        pace_stats = collector.get_team_pace_stats()
        
        # Test 3: Get player stats
        print("\n" + "=" * 70)
        players = collector.get_player_stats()
        
        # Test 4: Get defensive matchups (THE GOLD!)
        print("\n" + "=" * 70)
        try:
            defense = collector.get_defensive_matchups()
            has_defense = True
        except Exception as e:
            print(f"⚠️  Defensive matchups error: {e}")
            print("We still have DEF_RATING in pace stats - good enough!")
            has_defense = False
        
        print("\n" + "=" * 70)
        print("✅ SUCCESS! You have 2025-26 TRAINING DATA:")
        print(f"  📊 Team PACE stats (with DEF_RATING)")
        print(f"  👤 Player stats for all players")
        print(f"  🎮 All {len(games)} games from last season")
        if has_defense:
            print(f"  🛡️  Defensive matchups by position")
        print("\n📂 Check data/raw/ folder for CSV files")
        print("\n🎯 Next: Build ML model to predict player performance!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Wait a minute and try again (rate limit)")