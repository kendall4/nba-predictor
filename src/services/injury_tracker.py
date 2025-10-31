"""
Injury Tracker Service
=====================
Fetches player injury/health status from multiple free sources.
Rotowire API is optional (requires paid subscription).
"""

import requests
import pandas as pd
from typing import Dict, Optional, List
from nba_api.stats.endpoints import commonplayerinfo
from nba_api.stats.static import players as static_players
import os
import time
from bs4 import BeautifulSoup

class InjuryTracker:
    """
    Track player injury status using FREE public sources
    
    Sources (in priority order):
    1. Rotowire API (if API key provided - requires paid subscription)
    2. ESPN NBA Injury Report (FREE - public scraping)
    3. NBA API fallback (defaults to Healthy)
    
    Note: Rotowire requires contacting them for a paid API key.
    The free ESPN fallback works without any API keys!
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.rotowire_api_key = api_key or os.getenv('ROTOWIRE_API_KEY')
        self.base_url = "https://api.rotowire.com/v1"
        self.cache = {}
        self.injuries_df = None  # Cache full injuries list (Rotowire)
        self.espn_injuries_df = None  # Cache ESPN injuries
        self.cache_dir = 'data/cache'
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _lookup_player_id(self, player_name: str) -> Optional[int]:
        """Find NBA API player ID"""
        matches = [p for p in static_players.get_players() 
                   if p['full_name'].lower() == player_name.lower()]
        if not matches:
            matches = [p for p in static_players.get_players() 
                       if player_name.lower() in p['full_name'].lower()]
        return matches[0]['id'] if matches else None
    
    def _get_rotowire_injuries(self) -> Optional[pd.DataFrame]:
        """Fetch all NBA injuries from Rotowire API (requires paid API key)"""
        if not self.rotowire_api_key:
            return None
        
        try:
            url = f"{self.base_url}/nba/injuries"
            headers = {
                'Authorization': f'Bearer {self.rotowire_api_key}',
                'Content-Type': 'application/json'
            }
            # Alternative auth format (if Bearer doesn't work, try API key in params)
            params = {'apikey': self.rotowire_api_key} if 'Bearer' not in headers.get('Authorization', '') else {}
            
            response = requests.get(url, headers=headers if not params else None, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Rotowire returns list of injury objects
                if isinstance(data, list):
                    return pd.DataFrame(data)
                elif isinstance(data, dict) and 'injuries' in data:
                    return pd.DataFrame(data['injuries'])
                return pd.DataFrame(data)
            elif response.status_code == 401:
                print("❌ Invalid Rotowire API key")
                return None
            else:
                print(f"⚠️  Rotowire API error: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️  Error fetching Rotowire injuries: {e}")
            return None
    
    def _parse_espn_status(self, status_text: str) -> str:
        """Parse ESPN status text to standard format"""
        status_lower = status_text.lower()
        if 'out' in status_lower or 'doubtful' in status_lower:
            return 'Out'
        elif 'questionable' in status_lower or 'q' in status_lower:
            return 'Questionable'
        elif 'probable' in status_lower:
            return 'Healthy'  # Probable = likely playing
        return 'Unknown'
    
    def _parse_espn_table_row(self, row) -> Optional[Dict]:
        """Parse a single ESPN injury table row"""
        cols = row.find_all('td')
        if len(cols) < 3:
            return None
        
        player_name = cols[0].get_text(strip=True)
        position = cols[1].get_text(strip=True)
        status_text = cols[2].get_text(strip=True)
        status = self._parse_espn_status(status_text)
        injury_desc = cols[3].get_text(strip=True) if len(cols) > 3 else 'Unknown'
        
        return {
            'player_name': player_name,
            'status': status,
            'injury': injury_desc,
            'position': position
        }
    
    def _get_espn_injuries(self) -> Optional[pd.DataFrame]:
        """
        Fetch NBA injuries from ESPN (FREE - no API key needed)
        Scrapes the public ESPN NBA injury report page
        """
        try:
            url = "https://www.espn.com/nba/injuries"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            injuries = []
            tables = soup.find_all('table', class_='Table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header
                    injury_data = self._parse_espn_table_row(row)
                    if injury_data:
                        injuries.append(injury_data)
            
            return pd.DataFrame(injuries) if injuries else None
            
        except Exception as e:
            print(f"⚠️  Error fetching ESPN injuries: {e}")
            return None
    
    def _match_player_in_df(self, df: pd.DataFrame, player_name: str) -> Optional[pd.Series]:
        """Fuzzy match player name in dataframe"""
        if df is None or len(df) == 0:
            return None
        
        player_match = df[
            df['player_name'].str.contains(player_name, case=False, na=False) |
            df['player_name'].str.contains(player_name.split()[-1], case=False, na=False)
        ]
        
        return player_match.iloc[0] if len(player_match) > 0 else None
    
    def _parse_rotowire_status(self, rotowire_status: str) -> str:
        """Parse Rotowire status to standard format"""
        status_lower = rotowire_status.lower()
        if 'out' in status_lower or 'dtd' in status_lower:
            return 'Out'
        elif 'questionable' in status_lower or 'q' in status_lower:
            return 'Questionable'
        elif 'probable' in status_lower or 'healthy' in status_lower:
            return 'Healthy'
        return 'Questionable'  # Default to questionable if uncertain
    
    def _get_rotowire_status(self, player_name: str) -> Optional[Dict]:
        """Try to get player status from Rotowire API"""
        if not self.rotowire_api_key:
            return None
        
        if self.injuries_df is None:
            self.injuries_df = self._get_rotowire_injuries()
        
        injury_row = self._match_player_in_df(self.injuries_df, player_name)
        if injury_row is None:
            return None
        
        rotowire_status = str(injury_row.get('status', 'Unknown')).lower()
        status = self._parse_rotowire_status(rotowire_status)
        injury_desc = str(injury_row.get('injury', injury_row.get('injury_description', 'Unknown')))
        
        return {
            'player': player_name,
            'status': status,
            'injury': injury_desc,
            'last_updated': pd.Timestamp.now().isoformat(),
            'source': 'rotowire'
        }
    
    def _get_espn_status(self, player_name: str) -> Optional[Dict]:
        """Try to get player status from ESPN (free)"""
        if self.espn_injuries_df is None:
            self.espn_injuries_df = self._get_espn_injuries()
        
        injury_row = self._match_player_in_df(self.espn_injuries_df, player_name)
        if injury_row is None:
            return None
        
        return {
            'player': player_name,
            'status': str(injury_row.get('status', 'Unknown')),
            'injury': str(injury_row.get('injury', 'Unknown')),
            'last_updated': pd.Timestamp.now().isoformat(),
            'source': 'espn_free'
        }
    
    def get_player_status(self, player_name: str) -> Dict:
        """
        Get player injury/health status from multiple sources (FREE by default!)
        
        Returns:
            {
                'player': name,
                'status': 'Healthy' | 'Questionable' | 'Out' | 'Unknown',
                'injury': description if injured,
                'last_updated': timestamp,
                'source': 'rotowire' | 'espn_free' | 'nba_api_fallback'
            }
        """
        # Check cache first
        cache_key = f"injury_{player_name.lower()}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Try Rotowire first if API key is provided (paid service)
        rotowire_result = self._get_rotowire_status(player_name)
        if rotowire_result:
            self.cache[cache_key] = rotowire_result
            return rotowire_result
        
        # FREE FALLBACK: Try ESPN (no API key needed!)
        espn_result = self._get_espn_status(player_name)
        if espn_result:
            self.cache[cache_key] = espn_result
            return espn_result
        
        # Final fallback to NBA API lookup (if no match found)
        player_id = self._lookup_player_id(player_name)
        if player_id is None:
            result = {
                'player': player_name,
                'status': 'Unknown',
                'injury': None,
                'last_updated': None,
                'source': 'nba_api_fallback'
            }
        else:
            # NBA API fallback - defaults to Healthy
            result = {
                'player': player_name,
                'status': 'Healthy',  # Default assumption
                'injury': None,
                'last_updated': pd.Timestamp.now().isoformat(),
                'source': 'nba_api_fallback'
            }
        
        self.cache[cache_key] = result
        return result
    
    def get_multiple_statuses(self, player_names: List[str]) -> pd.DataFrame:
        """Get status for multiple players (cached, fast)"""
        results = []
        for name in player_names:
            status = self.get_player_status(name)
            results.append(status)
            # Reduced sleep since we cache ESPN data (only first call hits API)
            time.sleep(0.2)
        
        return pd.DataFrame(results)
    
    def is_healthy(self, player_name: str) -> bool:
        """Quick check if player is healthy"""
        status = self.get_player_status(player_name)
        return status['status'] == 'Healthy'
    
    def get_injured_players(self, player_list: List[str]) -> pd.DataFrame:
        """Filter to only injured/questionable players"""
        all_status = self.get_multiple_statuses(player_list)
        injured = all_status[all_status['status'].isin(['Questionable', 'Out'])]
        return injured


# Enhanced version with Rotowire fallback (scraping)
class EnhancedInjuryTracker(InjuryTracker):
    """
    Enhanced version that tries Rotowire for more detailed injury reports
    
    Note: Rotowire scraping is fragile and may violate ToS
    Use at your own risk
    """
    
    def get_player_status(self, player_name: str) -> Dict:
        # Try NBA API first
        status = super().get_player_status(player_name)
        
        # If status is Unknown or we want more details, try Rotowire
        if status['status'] == 'Unknown':
            # Rotowire scraping would go here
            # For now, keep NBA API result
            pass
        
        return status


if __name__ == "__main__":
    tracker = InjuryTracker()
    
    test_players = ['LeBron James', 'Luka Dončić', 'Stephen Curry']
    print("🏥 Testing Injury Tracker...")
    
    for player in test_players:
        status = tracker.get_player_status(player)
        print(f"\n{player}:")
        print(f"  Status: {status['status']}")
        if status['injury']:
            print(f"  Injury: {status['injury']}")

