#!/usr/bin/env python3
"""
Test/Debug Script for Odds API
===============================
Run this from terminal to test and debug the odds API without Streamlit.

Usage:
    python test_odds_api.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.services.odds_aggregator import OddsAggregator

def print_separator(title=""):
    """Print a visual separator"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print('='*60)
    else:
        print('-'*60)

def test_api_connection():
    """Test basic API connection and authentication"""
    print_separator("Testing Odds API Connection")
    
    # Check API key
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        print("❌ ODDS_API_KEY not found in environment variables")
        print("\n💡 To set it:")
        print("   1. Create a .env file in the project root")
        print("   2. Add: ODDS_API_KEY=your_key_here")
        print("   3. Get free key: https://the-odds-api.com/")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    return True

def test_get_player_props():
    """Test fetching player props"""
    print_separator("Testing Player Props Fetch")
    
    aggregator = OddsAggregator()
    
    if not aggregator.api_key:
        print("❌ No API key available")
        return None
    
    print(f"📡 Fetching player props (sport: basketball_nba)")
    print(f"   Regions: {aggregator.regions}")
    print(f"   Books: {aggregator.books[:5]}...")  # Show first 5
    print(f"   Markets: player_props")
    print()
    
    try:
        props = aggregator.get_player_props(debug=True)
        
        if props is None:
            print("\n❌ API returned None - likely an error occurred")
            print("   Check the error messages above for details")
            return None
        
        if len(props) == 0:
            print("\n⚠️  API returned empty DataFrame")
            print("   Possible reasons:")
            print("   - No NBA games scheduled for today")
            print("   - Player props not available yet")
            print("   - Market 'player_props' not supported by selected books")
            return pd.DataFrame()
        
        print(f"\n✅ Success! Retrieved {len(props)} player props")
        print(f"   Unique players: {props['player'].nunique() if 'player' in props.columns else 'N/A'}")
        print(f"   Unique stats: {props['stat'].unique().tolist() if 'stat' in props.columns else 'N/A'}")
        
        # Show sample
        print("\n📊 Sample data (first 5 rows):")
        print(props.head().to_string())
        
        return props
        
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_alternative_markets():
    """Test different market names"""
    print_separator("Testing Alternative Markets")
    
    aggregator = OddsAggregator()
    
    if not aggregator.api_key:
        print("❌ No API key available")
        return
    
    # Try different market names
    markets_to_try = [
        'player_props',
        'player_points',
        'player_rebounds',
        'player_assists',
    ]
    
    for market in markets_to_try:
        print(f"\n🔍 Trying market: '{market}'")
        try:
            # Temporarily modify the aggregator
            original_url = aggregator.base_url
            url = f"{original_url}/sports/basketball_nba/odds"
            params = {
                'api_key': aggregator.api_key,
                'regions': ','.join(aggregator.regions),
                'markets': market,
                'bookmakers': ','.join(aggregator.books[:3]),  # Just test with 3 books
                'oddsFormat': 'american',
                'dateFormat': 'iso'
            }
            
            import requests
            response = requests.get(url, params=params, timeout=20)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Events returned: {len(data)}")
                if len(data) > 0:
                    first_event = data[0]
                    print(f"   📋 First event: {first_event.get('home_team')} vs {first_event.get('away_team')}")
                    if 'bookmakers' in first_event and len(first_event['bookmakers']) > 0:
                        first_book = first_event['bookmakers'][0]
                        available_markets = [m.get('key') for m in first_book.get('markets', [])]
                        print(f"   📊 Available markets in {first_book.get('key')}: {available_markets[:5]}")
            else:
                print(f"   ❌ Error: {response.text[:200]}")
                
        except Exception as e:
            print(f"   ❌ Exception: {str(e)[:100]}")

def test_rate_limits():
    """Check API rate limits"""
    print_separator("Checking API Rate Limits")
    
    aggregator = OddsAggregator()
    
    if not aggregator.api_key:
        print("❌ No API key available")
        return
    
    try:
        import requests
        url = f"{aggregator.base_url}/sports/basketball_nba/odds"
        params = {
            'api_key': aggregator.api_key,
            'regions': 'us',
            'markets': 'player_props',
            'bookmakers': 'draftkings',
            'oddsFormat': 'american'
        }
        
        response = requests.get(url, params=params, timeout=20)
        
        # Check rate limit headers
        remaining = response.headers.get('x-requests-remaining', 'unknown')
        used = response.headers.get('x-requests-used', 'unknown')
        limit = response.headers.get('x-requests-limit', 'unknown')
        
        print(f"📊 Rate Limit Status:")
        print(f"   Used: {used}")
        print(f"   Remaining: {remaining}")
        print(f"   Limit: {limit}")
        
        if remaining != 'unknown':
            remaining_int = int(remaining) if remaining.isdigit() else 0
            if remaining_int < 10:
                print(f"   ⚠️  Warning: Only {remaining_int} requests remaining!")
        
    except Exception as e:
        print(f"❌ Error checking rate limits: {e}")

def main():
    """Main test function"""
    print("\n" + "="*60)
    print("  ODDS API TEST & DEBUG SCRIPT")
    print("="*60)
    
    # Test 1: API Connection
    if not test_api_connection():
        return
    
    # Test 2: Rate Limits
    test_rate_limits()
    
    # Test 3: Get Player Props
    props = test_get_player_props()
    
    # Test 4: Alternative Markets (if main test failed)
    if props is None or (isinstance(props, pd.DataFrame) and len(props) == 0):
        print("\n" + "="*60)
        print("  Main test returned no data, trying alternative markets...")
        test_alternative_markets()
    
    print_separator("Test Complete")
    print("\n💡 Tips:")
    print("   - If you see 401 errors: Check your API key")
    print("   - If you see 429 errors: You've hit rate limits (500/month free)")
    print("   - If empty results: Check if there are games today")
    print("   - If market not found: Try different market names")

if __name__ == "__main__":
    import pandas as pd
    main()

