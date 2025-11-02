"""
Lineup Tracker Service
=====================
Fetches confirmed starting lineups from multiple sources (prioritizes free sources).
1. NBA.com (FREE - no API key needed) - primary source
2. Rotowire API (paid subscription) - fallback if available
"""

import requests
import pandas as pd
from typing import Dict, Optional, List
import os
from datetime import datetime
from bs4 import BeautifulSoup
import re

class LineupTracker:
    """
    Fetch expected lineups from Rotowire API
    
    Setup:
    1. Get API key from Rotowire (contact them)
    2. Set environment variable: ROTOWIRE_API_KEY=your_key_here
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.rotowire_api_key = api_key or os.getenv('ROTOWIRE_API_KEY')
        self.rotowire_base_url = "https://api.rotowire.com/v1"
        self.nba_lineup_url = "https://www.nba.com/players/todays-lineups"
        self.cache = {}
    
    def get_todays_lineups(self, date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get confirmed lineups for today's games
        Tries NBA.com first (FREE), falls back to Rotowire if API key available
        
        Args:
            date: YYYY-MM-DD format (defaults to today)
        
        Returns:
            DataFrame with columns: game_id, team, player_name, position, confirmed
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        cache_key = f"lineups_{date}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Try NBA.com first (FREE, no API key needed)
        nba_lineups = self._get_nba_com_lineups()
        if nba_lineups is not None and len(nba_lineups) > 0:
            self.cache[cache_key] = nba_lineups
            return nba_lineups
        
        # Fallback to Rotowire if API key available
        if self.rotowire_api_key:
            rotowire_lineups = self._get_rotowire_lineups(date)
            if rotowire_lineups is not None and len(rotowire_lineups) > 0:
                self.cache[cache_key] = rotowire_lineups
                return rotowire_lineups
        
        return None
    
    def _get_nba_com_lineups(self) -> Optional[pd.DataFrame]:
        """Fetch lineups from NBA.com (FREE)"""
        max_retries = 2
        import time
        for attempt in range(max_retries + 1):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(self.nba_lineup_url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    # Try to parse JSON if the page is an API endpoint
                    try:
                        data = response.json()
                        # If it's JSON, parse it
                        if isinstance(data, dict) and 'lineups' in data:
                            return pd.DataFrame(data['lineups'])
                    except:
                        pass
                    
                    # Otherwise, parse HTML
                    soup = BeautifulSoup(response.content, 'html.parser')
                    lineups = self._parse_nba_com_html(soup)
                    
                    if lineups and len(lineups) > 0:
                        return pd.DataFrame(lineups)
                    return None
                else:
                    if attempt >= max_retries:
                        pass  # Silent fail, will try Rotowire
                    return None
                    
            except Exception as e:
                if attempt >= max_retries:
                    pass  # Silent fail
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return None
        
        return None
    
    def _parse_nba_com_html(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse NBA.com lineup page HTML"""
        lineups = []
        
        # Try to find lineup data in script tags (NBA.com often uses React/JSON)
        scripts = soup.find_all('script', type='application/json')
        for script in scripts:
            try:
                import json
                data = json.loads(script.string)
                # Try to find lineup data in JSON structure
                if isinstance(data, dict):
                    # Common patterns: look for games, lineups, players, etc.
                    for key in ['games', 'lineups', 'matchups', 'events']:
                        if key in data:
                            lineup_data = self._extract_lineups_from_json(data[key])
                            if lineup_data:
                                lineups.extend(lineup_data)
                                return lineups  # Found it, return
            except:
                continue
        
        # Fallback: Try using NBA API boxscore endpoints for games in progress
        # Note: Boxscores only available during/after games, not pre-game
        # But we can get actual starters from START_POSITION field
        try:
            from nba_api.live.nba.endpoints import scoreboard
            from nba_api.stats.endpoints import boxscoretraditionalv2
            
            board = scoreboard.ScoreBoard()
            games = board.games.get_dict()
            
            # Try to get lineups from boxscore for each game that has started
            for game in games:
                game_id = game.get('gameId')
                game_status = game.get('gameStatusText', '').upper()
                
                # Only try if game has started or is in progress
                if not game_id or 'FINAL' not in game_status and 'LIVE' not in game_status and 'IN PROGRESS' not in game_status:
                    continue
                
                try:
                    # BoxscoreTraditionalV2 has START_POSITION field - perfect for getting starters!
                    boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
                    dfs = boxscore.get_data_frames()
                    
                    if len(dfs) > 0:
                        player_stats = dfs[0]  # PlayerStats dataframe
                        
                        # Filter players with START_POSITION (not empty/null) - these are starters
                        starters = player_stats[
                            (player_stats['START_POSITION'].notna()) & 
                            (player_stats['START_POSITION'] != '')
                        ]
                        
                        if len(starters) > 0:
                            for _, player in starters.iterrows():
                                lineups.append({
                                    'game_id': str(game_id),
                                    'team': player.get('TEAM_ABBREVIATION', ''),
                                    'player_name': player.get('PLAYER_NAME', ''),
                                    'position': player.get('START_POSITION', ''),
                                    'confirmed': True  # Actual game data = confirmed
                                })
                except Exception:
                    continue
        except Exception as e:
            # Silent fail - boxscores not available pre-game
            pass
        
        return lineups
    
    def _extract_lineups_from_json(self, data) -> List[Dict]:
        """Extract lineup data from JSON structure"""
        lineups = []
        # This will depend on NBA.com's actual JSON structure
        # For now, return empty - we'll enhance when we see actual structure
        return lineups
    
    def _get_rotowire_lineups(self, date: str) -> Optional[pd.DataFrame]:
        """Fetch lineups from Rotowire API (paid, requires API key)"""
        if not self.rotowire_api_key:
            return None
        
        max_retries = 2
        import time
        for attempt in range(max_retries + 1):
            try:
                url = f"{self.rotowire_base_url}/nba/lineups"
                headers = {
                    'Authorization': f'Bearer {self.rotowire_api_key}',
                    'Content-Type': 'application/json'
                }
                params = {
                    'date': date,
                    'apikey': self.rotowire_api_key
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    lineups = []
                    if isinstance(data, list):
                        for game in data:
                            self._parse_lineup_game(game, lineups)
                    elif isinstance(data, dict):
                        if 'games' in data:
                            for game in data['games']:
                                self._parse_lineup_game(game, lineups)
                        elif 'lineups' in data:
                            return pd.DataFrame(data['lineups'])
                    
                    if lineups:
                        return pd.DataFrame(lineups)
                    return None
                else:
                    if attempt >= max_retries:
                        pass  # Silent fail
                    return None
                    
            except Exception as e:
                if attempt >= max_retries:
                    pass
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                return None
        
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

