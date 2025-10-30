"""
H2H Stats Utility
=================
Get detailed head-to-head statistics for a player vs specific opponent.
Shows averages, best/worst games, trends, etc.
"""

import pandas as pd
from src.analysis.hot_hand_tracker import HotHandTracker

def get_h2h_summary(player_name, opponent_tricode, season='2025-26'):
    """
    Get comprehensive H2H summary
    
    Returns dict with:
    - games: Total games vs opponent
    - avg_stats: Average PTS/REB/AST
    - best_game: Best performance
    - worst_game: Worst performance
    - trend: Recent vs older games
    """
    tracker = HotHandTracker(blend_mode="latest")
    
    # Get both seasons for H2H
    h2h_games = []
    for seas in [season, '2024-25']:
        logs = tracker.get_player_gamelog(player_name, season=seas)
        if logs is not None and not logs.empty:
            logs = logs.copy()
            logs['OPP'] = logs['MATCHUP'].apply(tracker._parse_opponent_from_matchup)
            h2h = logs[logs['OPP'] == opponent_tricode]
            if len(h2h) > 0:
                h2h_games.append(h2h)
    
    if not h2h_games:
        return None
    
    h2h_df = pd.concat(h2h_games, ignore_index=True)
    if 'GAME_DATE' in h2h_df.columns:
        h2h_df = h2h_df.sort_values('GAME_DATE', ascending=False)
    
    summary = {
        'player': player_name,
        'opponent': opponent_tricode,
        'total_games': len(h2h_df),
        'avg_pts': h2h_df['PTS'].mean() if 'PTS' in h2h_df.columns else 0,
        'avg_reb': h2h_df['REB'].mean() if 'REB' in h2h_df.columns else 0,
        'avg_ast': h2h_df['AST'].mean() if 'AST' in h2h_df.columns else 0,
        'best_game': {},
        'worst_game': {},
        'recent_vs_older': {}
    }
    
    # Best/worst games
    if 'PTS' in h2h_df.columns and len(h2h_df) > 0:
        best_idx = h2h_df['PTS'].idxmax()
        worst_idx = h2h_df['PTS'].idxmin()
        summary['best_game'] = {
            'pts': float(h2h_df.loc[best_idx, 'PTS']),
            'reb': float(h2h_df.loc[best_idx, 'REB']) if 'REB' in h2h_df.columns else 0,
            'ast': float(h2h_df.loc[best_idx, 'AST']) if 'AST' in h2h_df.columns else 0,
            'date': h2h_df.loc[best_idx, 'GAME_DATE'] if 'GAME_DATE' in h2h_df.columns else 'N/A'
        }
        summary['worst_game'] = {
            'pts': float(h2h_df.loc[worst_idx, 'PTS']),
            'reb': float(h2h_df.loc[worst_idx, 'REB']) if 'REB' in h2h_df.columns else 0,
            'ast': float(h2h_df.loc[worst_idx, 'AST']) if 'AST' in h2h_df.columns else 0,
            'date': h2h_df.loc[worst_idx, 'GAME_DATE'] if 'GAME_DATE' in h2h_df.columns else 'N/A'
        }
    
    # Recent (last 3) vs older
    if len(h2h_df) >= 3:
        recent = h2h_df.head(3)
        older = h2h_df.iloc[3:]
        summary['recent_vs_older'] = {
            'recent_avg_pts': float(recent['PTS'].mean()) if 'PTS' in recent.columns else 0,
            'older_avg_pts': float(older['PTS'].mean()) if 'PTS' in older.columns else 0,
            'trend': 'improving' if recent['PTS'].mean() > older['PTS'].mean() else 'declining'
        }
    
    return summary

def display_h2h_summary(summary):
    """Pretty print H2H summary"""
    if summary is None:
        print("❌ No H2H data found")
        return
    
    print(f"\n{'='*70}")
    print(f"H2H: {summary['player']} vs {summary['opponent']}")
    print(f"{'='*70}")
    print(f"\n📊 Total Games: {summary['total_games']}")
    print(f"\n📈 Averages:")
    print(f"   Points:   {summary['avg_pts']:.1f}")
    print(f"   Rebounds: {summary['avg_reb']:.1f}")
    print(f"   Assists:  {summary['avg_ast']:.1f}")
    
    if summary['best_game']:
        print(f"\n🏆 Best Game:")
        print(f"   {summary['best_game']['date']}: {summary['best_game']['pts']:.0f} PTS, "
              f"{summary['best_game']['reb']:.0f} REB, {summary['best_game']['ast']:.0f} AST")
    
    if summary['worst_game']:
        print(f"\n📉 Worst Game:")
        print(f"   {summary['worst_game']['date']}: {summary['worst_game']['pts']:.0f} PTS, "
              f"{summary['worst_game']['reb']:.0f} REB, {summary['worst_game']['ast']:.0f} AST")
    
    if summary['recent_vs_older']:
        print(f"\n📊 Trend (Recent 3 vs Older):")
        print(f"   Recent: {summary['recent_vs_older']['recent_avg_pts']:.1f} PPG")
        print(f"   Older:  {summary['recent_vs_older']['older_avg_pts']:.1f} PPG")
        print(f"   Status: {summary['recent_vs_older']['trend'].upper()}")

if __name__ == "__main__":
    # Example usage
    summary = get_h2h_summary('Luka Dončić', 'BOS', season='2025-26')
    display_h2h_summary(summary)

