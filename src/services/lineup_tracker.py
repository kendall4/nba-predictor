"""
Lineup Tracker Service
=====================
Fetches expected lineups from Rotowire API.
"""

import requests
import pandas as pd
from typing import Dict, Optional, List
import os
from datetime import datetime

class LineupTracker:
    """
    Fetch expected lineups from Rotowire API
    
    Setup:
    1. Get API key from Rotowire (contact them)
    2. Set environment variable: ROTOWIRE_API_KEY=your_key_here
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ROTOWIRE_API_KEY')
        self.base_url = "https://api.rotowire.com/v1"
        self.cache = {}
        
        if not self.api_key:
            print("⚠️  ROTOWIRE_API_KEY not found. Lineup fetching will be unavailable.")
    
    def get_todays_lineups(self, date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get expected lineups for today's games
        
        Args:
            date: YYYY-MM-DD format (defaults to today)
        
        Returns:
            DataFrame with columns: game_id, team, player_name, position, confirmed
        """
        if not self.api_key:
            return None
        
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        cache_key = f"lineups_{date}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        max_retries = 2
        import time
        for attempt in range(max_retries + 1):
            try:
                url = f"{self.base_url}/nba/lineups"
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                params = {
                    'date': date,
                    'apikey': self.api_key  # Some APIs use this format
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Parse lineup data (structure may vary)
                    lineups = []
                    if isinstance(data, list):
                        for game in data:
                            self._parse_lineup_game(game, lineups)
                    elif isinstance(data, dict):
                        if 'games' in data:
                            for game in data['games']:
                                self._parse_lineup_game(game, lineups)
                        elif 'lineups' in data:
                            lineups = pd.DataFrame(data['lineups'])
                            self.cache[cache_key] = lineups
                            return lineups
                    
                    if lineups:
                        df = pd.DataFrame(lineups)
                        self.cache[cache_key] = df
                        return df
                    return None
                    
                elif response.status_code == 401:
                    if attempt >= max_retries:
                        print("❌ Invalid Rotowire API key")
                    return None
                else:
                    if attempt >= max_retries:
                        print(f"⚠️  Rotowire API error: {response.status_code}")
                    return None
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return None
            except Exception as e:
                if attempt >= max_retries:
                    print(f"⚠️  Error fetching Rotowire lineups: {e}")
                return None
    
    def _parse_lineup_game(self, game: dict, lineups: list):
        """Parse a single game's lineup data"""
        game_id = game.get('game_id', '')
        home_team = game.get('home_team', '')
        away_team = game.get('away_team', '')
        
        # Parse home team lineup
        if 'home_lineup' in game:
            for player in game['home_lineup']:
                lineups.append({
                    'game_id': game_id,
                    'team': home_team,
                    'player_name': player.get('name', ''),
                    'position': player.get('position', ''),
                    'confirmed': player.get('confirmed', False)
                })
        
        # Parse away team lineup
        if 'away_lineup' in game:
            for player in game['away_lineup']:
                lineups.append({
                    'game_id': game_id,
                    'team': away_team,
                    'player_name': player.get('name', ''),
                    'position': player.get('position', ''),
                    'confirmed': player.get('confirmed', False)
                })
    
    def get_team_lineup(self, team_abbr: str, date: Optional[str] = None) -> Optional[List[str]]:
        """
        Get expected starting lineup for a specific team
        
        Returns:
            List of player names (starting 5)
        """
        lineups_df = self.get_todays_lineups(date)
        if lineups_df is None or len(lineups_df) == 0:
            return None
        
        team_lineup = lineups_df[
            (lineups_df['team'] == team_abbr) &
            (lineups_df['confirmed'] == True)
        ].head(5)
        
        if len(team_lineup) > 0:
            return team_lineup['player_name'].tolist()
        return None


if __name__ == "__main__":
    tracker = LineupTracker()
    
    if tracker.api_key:
        print("✅ Lineup Tracker initialized")
        lineups = tracker.get_todays_lineups()
        if lineups is not None:
            print(f"Found {len(lineups)} lineup entries")
            print(lineups.head(10))
    else:
        print("⚠️  Set ROTOWIRE_API_KEY to use lineup tracker")

