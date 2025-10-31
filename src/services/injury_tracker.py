"""
Injury Tracker Service
=====================
Fetches player injury/health status from Rotowire API.
Falls back to NBA API if Rotowire unavailable.
"""

import requests
import pandas as pd
from typing import Dict, Optional, List
from nba_api.stats.endpoints import commonplayerinfo
from nba_api.stats.static import players as static_players
import os
import time

class InjuryTracker:
    """
    Track player injury status
    
    Sources:
    1. NBA API (player info - basic status)
    2. Rotowire (via scraping fallback - not implemented yet)
    3. ESPN (via scraping fallback - not implemented yet)
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.rotowire_api_key = api_key or os.getenv('ROTOWIRE_API_KEY')
        self.base_url = "https://api.rotowire.com/v1"
        self.cache = {}
        self.injuries_df = None  # Cache full injuries list
        self.cache_dir = 'data/cache'
        os.makedirs(self.cache_dir, exist_ok=True)
        
        if not self.rotowire_api_key:
            print("⚠️  ROTOWIRE_API_KEY not found. Using NBA API fallback.")
    
    def _lookup_player_id(self, player_name: str) -> Optional[int]:
        """Find NBA API player ID"""
        matches = [p for p in static_players.get_players() 
                   if p['full_name'].lower() == player_name.lower()]
        if not matches:
            matches = [p for p in static_players.get_players() 
                       if player_name.lower() in p['full_name'].lower()]
        return matches[0]['id'] if matches else None
    
    def _get_rotowire_injuries(self) -> Optional[pd.DataFrame]:
        """Fetch all NBA injuries from Rotowire API"""
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
    
    def get_player_status(self, player_name: str) -> Dict:
        """
        Get player injury/health status from Rotowire API
        
        Returns:
            {
                'player': name,
                'status': 'Healthy' | 'Questionable' | 'Out' | 'Unknown',
                'injury': description if injured,
                'last_updated': timestamp
            }
        """
        # Check cache first
        cache_key = f"injury_{player_name.lower()}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Try Rotowire first (cache the full list to avoid repeated API calls)
        if self.rotowire_api_key:
            if self.injuries_df is None:
                self.injuries_df = self._get_rotowire_injuries()
            injuries_df = self.injuries_df
            if injuries_df is not None and len(injuries_df) > 0:
                # Match player by name (fuzzy match)
                player_match = injuries_df[
                    injuries_df['player_name'].str.contains(player_name, case=False, na=False) |
                    injuries_df['player_name'].str.contains(player_name.split()[-1], case=False, na=False)
                ]
                
                if len(player_match) > 0:
                    injury_row = player_match.iloc[0]
                    # Rotowire status mapping (common fields: status, injury_type, injury_description)
                    rotowire_status = str(injury_row.get('status', 'Unknown')).lower()
                    
                    # Map Rotowire status to our format
                    if 'out' in rotowire_status or 'dtd' in rotowire_status:
                        status = 'Out'
                    elif 'questionable' in rotowire_status or 'q' in rotowire_status:
                        status = 'Questionable'
                    elif 'probable' in rotowire_status or 'healthy' in rotowire_status:
                        status = 'Healthy'
                    else:
                        status = 'Questionable'  # Default to questionable if uncertain
                    
                    result = {
                        'player': player_name,
                        'status': status,
                        'injury': str(injury_row.get('injury', injury_row.get('injury_description', 'Unknown'))),
                        'last_updated': pd.Timestamp.now().isoformat(),
                        'source': 'rotowire'
                    }
                    self.cache[cache_key] = result
                    return result
        
        # Fallback to NBA API lookup (if no Rotowire match found)
        player_id = self._lookup_player_id(player_name)
        if player_id is None:
            result = {
                'player': player_name,
                'status': 'Unknown',
                'injury': None,
                'last_updated': None,
                'source': 'nba_api_fallback'
            }
            self.cache[cache_key] = result
            return result
        
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
        """Get status for multiple players"""
        results = []
        for name in player_names:
            status = self.get_player_status(name)
            results.append(status)
            time.sleep(0.6)  # Rate limit between requests
        
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

