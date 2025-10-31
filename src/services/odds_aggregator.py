"""
Odds Aggregator Service
=======================
Fetches and compares alt lines across multiple sportsbooks using The Odds API.

Supports: DraftKings, FanDuel, Fanatics, ESPN Bet, BetMGM, Caesars, etc.
"""

import requests
import pandas as pd
import os
from typing import List, Dict, Optional
import time

class OddsAggregator:
    """
    Aggregate odds from multiple sportsbooks using The Odds API
    
    Setup:
    1. Get free API key from https://the-odds-api.com/
    2. Set environment variable: ODDS_API_KEY=your_key_here
    3. Free tier: 500 requests/month
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ODDS_API_KEY')
        if not self.api_key:
            print("⚠️  ODDS_API_KEY not found. Set it in .env or pass as argument.")
            print("   Get free key: https://the-odds-api.com/")
        self.base_url = "https://api.the-odds-api.com/v4"
        self.regions = ['us']  # US odds
        self.markets = ['player_props']  # Player props (points, rebounds, etc.)
        self.books = ['draftkings', 'fanduel', 'fanduel', 'espnbet', 'betmgm', 'caesars', 'pointsbet']
    
    def get_player_props(self, sport='basketball_nba', event_id: Optional[str] = None):
        """
        Get player props for NBA games
        
        Args:
            sport: 'basketball_nba'
            event_id: Specific game ID (optional, gets all today's games if None)
        
        Returns:
            DataFrame with columns: player, stat, line, over_odds, under_odds, book
        """
        if not self.api_key:
            return None
        
        try:
            if event_id:
                url = f"{self.base_url}/sports/{sport}/events/{event_id}/odds"
            else:
                url = f"{self.base_url}/sports/{sport}/odds"
            
            params = {
                'apiKey': self.api_key,
                'regions': ','.join(self.regions),
                'markets': ','.join(self.markets),
                'bookmakers': ','.join(self.books[:5])  # Limit to avoid rate limits
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse player props
            props = []
            for event in data:
                if 'bookmakers' not in event:
                    continue
                
                game_id = event.get('id', 'unknown')
                home_team = event.get('home_team', '')
                away_team = event.get('away_team', '')
                
                for bookmaker in event['bookmakers']:
                    book_name = bookmaker.get('key', 'unknown')
                    if 'markets' not in bookmaker:
                        continue
                    
                    for market in bookmaker['markets']:
                        if market.get('key') != 'player_props':
                            continue
                        
                        for outcome in market.get('outcomes', []):
                            player_name = outcome.get('name', '')
                            stat_type = outcome.get('description', '')  # e.g., "Points", "Rebounds"
                            point = outcome.get('point', 0)
                            price = outcome.get('price', 0)
                            
                            # Determine over/under from outcome type
                            is_over = 'over' in outcome.get('description', '').lower() or 'over' in stat_type.lower()
                            
                            props.append({
                                'game_id': game_id,
                                'home_team': home_team,
                                'away_team': away_team,
                                'player': player_name,
                                'stat': stat_type,
                                'line': point,
                                'odds': price,
                                'type': 'over' if is_over else 'under',
                                'book': book_name
                            })
            
            if not props:
                return pd.DataFrame()
            
            df = pd.DataFrame(props)
            
            # Group by player/stat/line and pivot to get over/under side by side
            comparison = []
            for (player, stat, line, book), group in df.groupby(['player', 'stat', 'line', 'book']):
                over_row = group[group['type'] == 'over']
                under_row = group[group['type'] == 'under']
                
                comparison.append({
                    'player': player,
                    'stat': stat,
                    'line': line,
                    'book': book,
                    'over_odds': int(over_row['odds'].iloc[0]) if len(over_row) > 0 else None,
                    'under_odds': int(under_row['odds'].iloc[0]) if len(under_row) > 0 else None
                })
            
            return pd.DataFrame(comparison)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching odds: {e}")
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 401:
                    print("   Invalid API key")
                elif e.response.status_code == 429:
                    print("   Rate limit exceeded. Free tier: 500 requests/month")
            return None
        except Exception as e:
            print(f"❌ Error parsing odds: {e}")
            return None
    
    def compare_books(self, player_name: str, stat: str, line: float):
        """
        Compare same prop across all books
        
        Returns best odds for over and under
        """
        props_df = self.get_player_props()
        if props_df is None or len(props_df) == 0:
            return None
        
        # Filter to specific player/stat/line
        filtered = props_df[
            (props_df['player'].str.contains(player_name, case=False, na=False)) &
            (props_df['stat'].str.contains(stat, case=False, na=False)) &
            (props_df['line'] == line)
        ]
        
        if len(filtered) == 0:
            return None
        
        # Find best odds
        over_best = filtered[filtered['over_odds'].notna()].nlargest(1, 'over_odds')
        under_best = filtered[filtered['under_odds'].notna()].nsmallest(1, 'under_odds')
        
        return {
            'over': {
                'book': over_best['book'].iloc[0] if len(over_best) > 0 else None,
                'odds': int(over_best['over_odds'].iloc[0]) if len(over_best) > 0 else None
            },
            'under': {
                'book': under_best['book'].iloc[0] if len(under_best) > 0 else None,
                'odds': int(under_best['under_odds'].iloc[0]) if len(under_best) > 0 else None
            },
            'all_books': filtered.to_dict('records')
        }
    
    def get_alt_lines(self, player_name: str, stat: str = 'points'):
        """
        Get all alt lines for a player/stat across books
        
        Returns DataFrame with all available lines and odds
        """
        props_df = self.get_player_props()
        if props_df is None or len(props_df) == 0:
            return None
        
        filtered = props_df[
            (props_df['player'].str.contains(player_name, case=False, na=False)) &
            (props_df['stat'].str.contains(stat, case=False, na=False))
        ]
        
        if len(filtered) == 0:
            return None
        
        # Group by line and show all books
        return filtered.sort_values(['line', 'over_odds'], ascending=[True, False])


if __name__ == "__main__":
    # Test
    aggregator = OddsAggregator()
    
    if aggregator.api_key:
        print("✅ Odds Aggregator initialized")
        print("\n📊 Fetching today's player props...")
        props = aggregator.get_player_props()
        
        if props is not None and len(props) > 0:
            print(f"   Found {len(props)} props")
            print("\nSample:")
            print(props.head(10))
        else:
            print("   No props found or API error")
    else:
        print("⚠️  Set ODDS_API_KEY environment variable to use")

