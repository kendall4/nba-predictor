"""
NBA.com Lineup Tracker (FREE)
==============================
Fetches confirmed starting lineups from NBA.com's public lineup page.
No API key required - uses web scraping of https://www.nba.com/players/todays-lineups
"""

import requests
import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime
from bs4 import BeautifulSoup
import time
import re

class NBALineupTracker:
    """
    Fetch confirmed starting lineups from NBA.com (FREE - no API key needed!)
    
    Uses the public lineup page: https://www.nba.com/players/todays-lineups
    """
    
    def __init__(self):
        self.base_url = "https://www.nba.com/players/todays-lineups"
        self.cache = {}
        
    def get_todays_lineups(self, date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get confirmed lineups for today's games from NBA.com
        
        Args:
            date: YYYY-MM-DD format (defaults to today)
        
        Returns:
            DataFrame with columns: team, player_name, position, confirmed
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        cache_key = f"nba_lineups_{date}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(self.base_url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    lineups = self._parse_lineups_page(soup)
                    
                    if lineups and len(lineups) > 0:
                        df = pd.DataFrame(lineups)
                        self.cache[cache_key] = df
                        return df
                    return None
                else:
                    if attempt >= max_retries:
                        print(f"⚠️  NBA.com lineup page returned status {response.status_code}")
                    return None
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return None
            except Exception as e:
                if attempt >= max_retries:
                    print(f"⚠️  Error fetching NBA.com lineups: {e}")
                return None
    
    def _parse_lineups_page(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse NBA.com lineup page HTML"""
        lineups = []
        
        # Try multiple selectors - NBA.com structure may vary
        # Look for game sections, team names, and player lists
        game_sections = soup.find_all(['div', 'section'], class_=re.compile(r'game|matchup|lineup', re.I))
        
        if not game_sections:
            # Try finding by team abbreviations (common pattern)
            team_elements = soup.find_all(text=re.compile(r'\b(ATL|BOS|BKN|CHA|CHI|CLE|DAL|DEN|DET|GSW|HOU|IND|LAC|LAL|MEM|MIA|MIL|MIN|NOP|NYK|OKC|ORL|PHI|PHX|POR|SAC|SAS|TOR|UTA|WAS)\b'))
            
            # If we find team names, try to parse around them
            if team_elements:
                # Try to find lineup tables or lists near team names
                for team_elem in team_elements[:10]:  # Limit search
                    parent = team_elem.parent if hasattr(team_elem, 'parent') else None
                    if parent:
                        # Look for player names in nearby elements
                        players = parent.find_all(['a', 'span', 'div'], text=re.compile(r'[A-Z][a-z]+ [A-Z][a-z]+'))
                        if players:
                            team_abbr = team_elem.strip()
                            for player_elem in players[:5]:  # First 5 = starters
                                player_name = player_elem.get_text(strip=True)
                                if len(player_name.split()) >= 2:  # Valid name format
                                    lineups.append({
                                        'team': team_abbr,
                                        'player_name': player_name,
                                        'position': None,
                                        'confirmed': True  # NBA.com shows confirmed lineups
                                    })
        else:
            # Parse structured game sections
            for section in game_sections:
                team_info = self._extract_team_from_section(section)
                if team_info:
                    lineups.extend(team_info)
        
        # If we still don't have data, try fallback: use NBA API scoreboard
        if len(lineups) == 0:
            lineups = self._fallback_nba_api_lineups()
        
        return lineups
    
    def _extract_team_from_section(self, section) -> List[Dict]:
        """Extract team lineup from a game section"""
        lineups = []
        # Try to find team name and players
        team_match = section.find(text=re.compile(r'\b(ATL|BOS|BKN|CHA|CHI|CLE|DAL|DEN|DET|GSW|HOU|IND|LAC|LAL|MEM|MIA|MIL|MIN|NOP|NYK|OKC|ORL|PHI|PHX|POR|SAC|SAS|TOR|UTA|WAS)\b'))
        if team_match:
            team_abbr = team_match.strip()
            # Find player elements in this section
            player_elements = section.find_all(['a', 'span', 'div'], text=re.compile(r'^[A-Z][a-z]+ [A-Z]'))
            for player_elem in player_elements[:5]:
                player_name = player_elem.get_text(strip=True)
                if len(player_name.split()) >= 2:
                    lineups.append({
                        'team': team_abbr,
                        'player_name': player_name,
                        'position': None,
                        'confirmed': True
                    })
        return lineups
    
    def _fallback_nba_api_lineups(self) -> List[Dict]:
        """Fallback: Try to get lineups from NBA API scoreboard endpoint"""
        try:
            from nba_api.live.nba.endpoints import scoreboard
            board = scoreboard.ScoreBoard()
            games = board.games.get_dict()
            
            lineups = []
            for game in games:
                # NBA API scoreboard doesn't directly provide lineups, but we can extract team info
                home_team = game['homeTeam']['teamTricode']
                away_team = game['awayTeam']['teamTricode']
                
                # Try to get lineup from boxscore (if available)
                # This is a simplified fallback - actual implementation would need boxscore endpoint
                # For now, return empty and let the calling code handle it
                pass
            
            return lineups
        except Exception:
            return []
    
    def get_team_lineup(self, team_abbr: str, date: Optional[str] = None) -> Optional[List[str]]:
        """
        Get confirmed starting lineup for a specific team from NBA.com
        
        Returns:
            List of player names (starting 5) or None if not available
        """
        lineups_df = self.get_todays_lineups(date)
        if lineups_df is None or len(lineups_df) == 0:
            return None
        
        team_lineup = lineups_df[lineups_df['team'] == team_abbr].head(5)
        
        if len(team_lineup) > 0:
            return team_lineup['player_name'].tolist()
        return None


if __name__ == "__main__":
    tracker = NBALineupTracker()
    
    print("✅ NBA.com Lineup Tracker initialized (FREE - no API key needed)")
    lineups = tracker.get_todays_lineups()
    if lineups is not None:
        print(f"Found {len(lineups)} lineup entries")
        print(lineups.head(20))
    else:
        print("⚠️  Could not fetch lineups from NBA.com")

