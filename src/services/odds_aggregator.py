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
        # Try passed key, then Streamlit secrets, then env var
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get('ODDS_API_KEY')
            except (ImportError, AttributeError, FileNotFoundError):
                pass
        
        if not api_key:
            api_key = os.getenv('ODDS_API_KEY')
        
        self.api_key = api_key
        if not self.api_key:
            print("⚠️  ODDS_API_KEY not found. Set it in Streamlit secrets, .env, or pass as argument.")
            print("   Get free key: https://the-odds-api.com/")
        self.base_url = "https://api.the-odds-api.com/v4"
        self.regions = ['us']  # US odds
        # Note: Player props market may vary by bookmaker - try both common names
        self.markets = ['player_props', 'player_points', 'player_rebounds', 'player_assists']
        self.books = ['draftkings', 'fanduel', 'espnbet', 'betmgm', 'caesars', 'pointsbet']
    
    def get_player_props(self, sport='basketball_nba', event_id: Optional[str] = None, debug: bool = False):
        """
        Get player props for NBA games
        
        Args:
            sport: 'basketball_nba'
            event_id: Specific game ID (optional, gets all today's games if None)
            debug: If True, print detailed API response info
        
        Returns:
            DataFrame with columns: player, stat, line, over_odds, under_odds, book
        """
        if not self.api_key:
            if debug:
                print("⚠️  ODDS_API_KEY not set")
            return None
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if event_id:
                    url = f"{self.base_url}/sports/{sport}/events/{event_id}/odds"
                else:
                    url = f"{self.base_url}/sports/{sport}/odds"
                
                # Per official API docs: player_props is general, or use specific markets:
                # player_points, player_rebounds, player_assists, etc.
                # Using 'player_props' gets all player props in one request
                # IMPORTANT: Parameter name is 'api_key' not 'apiKey' (per official samples)
                params = {
                    'api_key': self.api_key,  # Fixed: use 'api_key' not 'apiKey'
                    'regions': ','.join(self.regions),
                    'markets': 'player_props',  # General market (can also use player_points, player_rebounds, etc.)
                    'bookmakers': ','.join(self.books[:5]),  # Limit to avoid rate limits
                    'oddsFormat': 'american',  # Use American odds format (per API docs)
                    'dateFormat': 'iso'  # Add date format for consistency
                }
                
                response = requests.get(url, params=params, timeout=20)
                
                # Better error handling - check status before raise_for_status
                if response.status_code != 200:
                    error_msg = f"API returned status {response.status_code}"
                    if debug:
                        error_msg += f": {response.text}"
                    if response.status_code == 401:
                        if debug:
                            print(f"❌ Authentication error: Invalid API key")
                        return None
                    elif response.status_code == 429:
                        if debug:
                            print(f"⚠️  Rate limit exceeded")
                        return pd.DataFrame()  # Return empty, don't fail completely
                    elif debug:
                        print(f"❌ API Error: {error_msg}")
                    return None
                
                response.raise_for_status()
                
                # Check rate limits and usage from headers (per official API docs)
                remaining = response.headers.get('x-requests-remaining', 'unknown')
                used = response.headers.get('x-requests-used', 'unknown')
                last_cost = response.headers.get('x-requests-last', 'unknown')
                if remaining != 'unknown' and debug:
                    print(f"📊 API Usage: {used} used, {remaining} remaining (last request cost: {last_cost})")
                
                data = response.json()
                break  # Success, exit retry loop
                
            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    if debug:
                        print(f"⚠️  Request timeout (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    time.sleep(2 * (attempt + 1))
                    continue
                if debug:
                    print(f"❌ Request timeout after {max_retries + 1} attempts")
                return pd.DataFrame()
            except requests.exceptions.RequestException as e:
                # Don't retry on auth errors or client errors
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code in [401, 403]:
                        if debug:
                            print(f"❌ Authentication error: {e.response.status_code}")
                        return None
                    elif e.response.status_code == 429:
                        if debug:
                            print(f"⚠️  Rate limit exceeded (attempt {attempt + 1}/{max_retries + 1})")
                        if attempt < max_retries:
                            time.sleep(5 * (attempt + 1))
                            continue
                if debug:
                    print(f"❌ Request error: {e}")
                return None
            except Exception as e:
                if debug:
                    print(f"❌ Unexpected error: {e}")
                return None
        
        # Process response data (outside retry loop, only if we succeeded)
        # Note: data is only set if we successfully got a response
        if 'data' not in locals():
            # All retries failed, return empty DataFrame
            if debug:
                print("⚠️  All retry attempts failed")
            return pd.DataFrame()
        
        try:
            if debug:
                print(f"🔍 API Response: {len(data)} events")
                if len(data) > 0:
                    first_event = data[0]
                    print(f"   First event: {first_event.get('home_team')} vs {first_event.get('away_team')}")
                    if 'bookmakers' in first_event and len(first_event['bookmakers']) > 0:
                        first_book = first_event['bookmakers'][0]
                        markets = [m.get('key') for m in first_book.get('markets', [])]
                        print(f"   Available markets in {first_book.get('key')}: {markets}")
            
            # Debug: log available markets if no props found
            if not data or len(data) == 0:
                if debug:
                    print("⚠️  No events returned from API")
                    print("💡 Tip: Check if there are NBA games scheduled for today")
                    print(f"   URL called: {url}")
                    print(f"   Parameters: {params}")
                return pd.DataFrame()
            
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
                        market_key = market.get('key', '').lower()
                        # Accept various player prop market names
                        if 'player' not in market_key and 'prop' not in market_key:
                            # Log available markets for debugging
                            if debug and not hasattr(self, '_logged_markets'):
                                available_markets = [m.get('key') for m in bookmaker.get('markets', [])]
                                print(f"📋 Available markets in {book_name}: {available_markets}")
                                self._logged_markets = True
                            continue
                        
                        for outcome in market.get('outcomes', []):
                            # Per official API docs: name="Over"/"Under", description=player name
                            outcome_type = outcome.get('name', '').lower()  # "over" or "under"
                            player_name = outcome.get('description', '')  # Player name is in description
                            
                            # Skip if missing required fields (per API structure)
                            if not player_name or not outcome_type or outcome_type not in ['over', 'under']:
                                continue
                            
                            # Extract stat type from market key (e.g., "player_points", "player_rebounds")
                            # Market keys can be: player_props, player_points, player_rebounds, player_assists, etc.
                            stat_type = ''
                            stat_keywords = {
                                'points': 'points',
                                'point': 'points',
                                'pts': 'points',
                                'rebounds': 'rebounds',
                                'rebound': 'rebounds',
                                'reb': 'rebounds',
                                'board': 'rebounds',
                                'assists': 'assists',
                                'assist': 'assists',
                                'ast': 'assists',
                                'three': 'threes',
                                '3pt': 'threes',
                                '3-pointer': 'threes',
                                'steals': 'steals',
                                'steal': 'steals',
                                'blocks': 'blocks',
                                'block': 'blocks'
                            }
                            
                            # Extract stat from market key (most reliable)
                            market_key_lower = market_key.lower()
                            for keyword, stat in stat_keywords.items():
                                if keyword in market_key_lower:
                                    stat_type = stat
                                    break
                            
                            # If market key didn't reveal stat, try to infer from outcome data
                            if not stat_type:
                                # Try common market key patterns
                                if 'player_points' in market_key_lower or 'points' in market_key_lower:
                                    stat_type = 'points'
                                elif 'player_rebounds' in market_key_lower or 'rebounds' in market_key_lower:
                                    stat_type = 'rebounds'
                                elif 'player_assists' in market_key_lower or 'assists' in market_key_lower:
                                    stat_type = 'assists'
                                else:
                                    # Skip unknown stats - don't add to props
                                    continue
                            
                            # Skip if we still don't have a valid stat type
                            if not stat_type or stat_type == 'unknown':
                                continue
                            
                            point = outcome.get('point', 0)  # Line value
                            price = outcome.get('price', 0)   # Odds (American format)
                            
                            # Skip if missing critical data
                            if not point or not price:
                                continue
                            
                            # Determine over/under from name field
                            is_over = outcome_type == 'over'
                            
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
                if debug:
                    print("⚠️  No player props found in API response")
                    print("💡 Available markets might not include player props, or no games today")
                return pd.DataFrame()
            
            df = pd.DataFrame(props)
            
            if debug:
                print(f"✅ Found {len(df)} player props from {df['book'].nunique()} books")
                print(f"   Unique players: {df['player'].nunique()}")
                print(f"   Unique stats: {df['stat'].unique().tolist()}")
            
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
            if debug:
                print(f"❌ Error fetching odds: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code == 401:
                        print("   Invalid API key")
                    elif e.response.status_code == 429:
                        print("   Rate limit exceeded. Free tier: 500 requests/month")
            return None
        except Exception as e:
            if debug:
                print(f"❌ Error parsing odds: {e}")
                import traceback
                traceback.print_exc()
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
    
    def _normalize_player_name(self, name: str) -> str:
        """Normalize player name for matching (remove accents, special chars)"""
        import unicodedata
        # Remove accents
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        # Remove common prefixes/suffixes
        name = name.replace('Jr.', '').replace('Jr', '').replace('Sr.', '').replace('Sr', '')
        # Remove extra spaces
        name = ' '.join(name.split())
        return name.lower()
    
    def _fuzzy_match_player(self, search_name: str, available_names: pd.Series) -> pd.Series:
        """
        Fuzzy match player name using multiple strategies:
        1. Exact match (case-insensitive)
        2. Contains match
        3. Last name match
        4. Normalized match (no accents)
        """
        search_normalized = self._normalize_player_name(search_name)
        search_parts = search_name.split()
        last_name = search_parts[-1] if len(search_parts) > 0 else search_name
        
        # Try exact match first
        exact_match = available_names[available_names.str.lower() == search_name.lower()]
        if len(exact_match) > 0:
            return exact_match.index
        
        # Try contains match
        contains_match = available_names[available_names.str.contains(search_name, case=False, na=False)]
        if len(contains_match) > 0:
            return contains_match.index
        
        # Try normalized match
        normalized_names = available_names.apply(self._normalize_player_name)
        normalized_match = normalized_names[normalized_names == search_normalized]
        if len(normalized_match) > 0:
            return normalized_match.index
        
        # Try last name match
        last_name_match = available_names[
            available_names.str.contains(last_name, case=False, na=False)
        ]
        if len(last_name_match) > 0:
            return last_name_match.index
        
        return pd.Index([])
    
    def get_alt_lines(self, player_name: str, stat: str = 'points', debug: bool = False):
        """
        Get all alt lines for a player/stat across books
        
        Args:
            player_name: Name of player to search for
            stat: Stat type ('points', 'rebounds', 'assists', etc.)
            debug: If True, enable debug logging
        
        Returns DataFrame with all available lines and odds
        """
        props_df = self.get_player_props(debug=debug)
        if props_df is None or len(props_df) == 0:
            if debug:
                print("⚠️  No player props data available (no games today or API issue)")
            return None
        
        # Normalize stat name
        stat_lower = stat.lower()
        stat_variants = {
            'points': ['point', 'pts', 'scoring'],
            'rebounds': ['rebound', 'reb', 'board'],
            'assists': ['assist', 'ast'],
            'threes': ['three', '3pt', '3-pointer', '3 pointer'],
            'steals': ['steal', 'stl'],
            'blocks': ['block', 'blk']
        }
        
        # Get all available stats for debugging
        available_stats = props_df['stat'].unique().tolist() if len(props_df) > 0 else []
        available_players = props_df['player'].unique().tolist() if len(props_df) > 0 else []
        
        # Try fuzzy player matching
        player_indices = self._fuzzy_match_player(player_name, props_df['player'])
        
        if len(player_indices) == 0:
            # Return debug info
            return {
                'error': 'player_not_found',
                'search_name': player_name,
                'available_players': available_players[:20],  # First 20 for reference
                'total_players': len(available_players)
            }
        
        # Filter by matched players
        player_filtered = props_df.loc[player_indices]
        
        # Filter by stat (try variants)
        stat_match = False
        for variant in [stat_lower] + stat_variants.get(stat_lower, []):
            stat_filtered = player_filtered[
                player_filtered['stat'].str.contains(variant, case=False, na=False)
            ]
            if len(stat_filtered) > 0:
                stat_match = True
                break
        
        if not stat_match:
            # Return debug info
            return {
                'error': 'stat_not_found',
                'search_stat': stat,
                'available_stats': list(set(player_filtered['stat'].unique().tolist())),
                'matched_players': player_filtered['player'].unique().tolist()[:5]
            }
        
        # Group by line and show all books
        result = stat_filtered.sort_values(['line', 'over_odds'], ascending=[True, False])
        return result


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

