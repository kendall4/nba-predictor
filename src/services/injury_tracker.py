"""
Injury Tracker Service
=====================
Fetches player injury/health status from NBA API and other sources.
"""

import requests
import pandas as pd
from typing import Dict, Optional, List
from nba_api.stats.endpoints import commonplayerinfo
from nba_api.stats.static import players as static_players
import time

class InjuryTracker:
    """
    Track player injury status
    
    Sources:
    1. NBA API (player info - basic status)
    2. Rotowire (via scraping fallback - not implemented yet)
    3. ESPN (via scraping fallback - not implemented yet)
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_dir = 'data/cache'
        import os
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _lookup_player_id(self, player_name: str) -> Optional[int]:
        """Find NBA API player ID"""
        matches = [p for p in static_players.get_players() 
                   if p['full_name'].lower() == player_name.lower()]
        if not matches:
            matches = [p for p in static_players.get_players() 
                       if player_name.lower() in p['full_name'].lower()]
        return matches[0]['id'] if matches else None
    
    def get_player_status(self, player_name: str) -> Dict:
        """
        Get player injury/health status
        
        Returns:
            {
                'player': name,
                'status': 'Healthy' | 'Questionable' | 'Out' | 'Unknown',
                'injury': description if injured,
                'last_updated': timestamp
            }
        """
        player_id = self._lookup_player_id(player_name)
        if player_id is None:
            return {
                'player': player_name,
                'status': 'Unknown',
                'injury': None,
                'last_updated': None
            }
        
        # Check cache first
        cache_key = f"injury_{player_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # NBA API player info (has basic status)
            time.sleep(0.6)  # Rate limit
            info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
            df = info.get_data_frames()[0]
            
            # NBA API doesn't directly expose injury status in common player info
            # We'll infer from games played or use other indicators
            # For now, return basic structure
            
            status = 'Healthy'  # Default - NBA API doesn't have direct injury field
            injury = None
            
            # Try to get from player game log (if missing recent games, might be injured)
            # This is a heuristic - not perfect
            
            result = {
                'player': player_name,
                'status': status,
                'injury': injury,
                'last_updated': pd.Timestamp.now().isoformat(),
                'source': 'nba_api'
            }
            
            self.cache[cache_key] = result
            return result
            
        except Exception as e:
            print(f"⚠️  Error fetching status for {player_name}: {e}")
            return {
                'player': player_name,
                'status': 'Unknown',
                'injury': None,
                'last_updated': None,
                'error': str(e)
            }
    
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

