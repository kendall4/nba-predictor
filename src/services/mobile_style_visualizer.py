"""
Mobile App Style Visualizations
================================
Creates visualizations matching the mobile app style shown:
- Percentage statistics (% over/under line for different periods)
- Average and median stats
- Bar charts with green/pink colors for over/under
- Date and opponent labels
- Over/under betting line display
"""

import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Dict, Tuple
from src.analysis.hot_hand_tracker import HotHandTracker
import numpy as np


class MobileStyleVisualizer:
    """
    Create mobile app-style visualizations with percentage stats and betting lines
    """
    
    def __init__(self):
        self.hot_hand_tracker = HotHandTracker()
    
    def get_percentage_stats(self, player_name: str, stat: str, line: float,
                            periods: Dict[str, int] = None) -> Dict[str, float]:
        """
        Calculate percentage of games over the line for different periods
        
        Args:
            player_name: Player name
            stat: Stat column name ('PTS', 'AST', 'REB', etc.)
            line: Over/under line (e.g., 29.5)
            periods: Dict of period names to number of games
                    e.g., {'H2H': 5, 'L5': 5, 'L10': 10, 'L20': 20, '2025': 100}
        
        Returns:
            Dict with percentage over line for each period
        """
        if periods is None:
            periods = {'H2H': 5, 'L5': 5, 'L10': 10, 'L20': 20}
        
        results = {}
        
        # Get current season game log
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season='2025-26')
        
        if game_log is None or stat not in game_log.columns:
            return {k: 0.0 for k in periods.keys()}
        
        # Convert to numeric
        game_log[stat] = pd.to_numeric(game_log[stat], errors='coerce')
        game_log = game_log[game_log[stat].notna()].copy()
        
        if len(game_log) == 0:
            return {k: 0.0 for k in periods.keys()}
        
        # Calculate for each period
        for period_name, num_games in periods.items():
            if period_name == 'H2H':
                # H2H would need opponent - skip for now or set to 0
                results['H2H'] = 0.0
            elif period_name in ['L5', 'L10', 'L20']:
                recent = game_log.head(num_games)
                if len(recent) > 0:
                    over_line = (recent[stat] > line).sum()
                    results[period_name] = (over_line / len(recent)) * 100
                else:
                    results[period_name] = 0.0
            elif period_name in ['2025', '2024']:
                # Filter by season year
                if 'GAME_DATE' in game_log.columns:
                    game_log['YEAR'] = pd.to_datetime(game_log['GAME_DATE']).dt.year
                    year_games = game_log[game_log['YEAR'] == int(period_name)]
                    if len(year_games) > 0:
                        over_line = (year_games[stat] > line).sum()
                        results[period_name] = (over_line / len(year_games)) * 100
                    else:
                        results[period_name] = 0.0
                else:
                    results[period_name] = 0.0
        
        return results
    
    def create_mobile_style_chart(self, player_name: str, stat: str, 
                                 stat_label: str, line: float,
                                 time_period: str = "L5", n_games: int = 5,
                                 opponent: Optional[str] = None) -> Optional[go.Figure]:
        """
        Create mobile app-style bar chart with:
        - Green bars for over line, pink for under
        - Date and opponent labels
        - Horizontal line showing the betting line
        - Value labels on bars
        
        Args:
            player_name: Player name
            stat: Stat column ('PTS', 'AST', 'REB', etc.)
            stat_label: Display label ('Points', 'Assists', etc.)
            line: Over/under betting line (e.g., 29.5)
            time_period: Period label ('L5', 'L10', 'H2H', etc.)
            n_games: Number of games to show
            opponent: Optional opponent for H2H
        """
        # Get game log
        if opponent and time_period == 'H2H':
            # H2H logic - extract opponent from MATCHUP
            def extract_opponent(matchup_str):
                """Extract opponent abbreviation from MATCHUP string"""
                if pd.isna(matchup_str):
                    return ''
                matchup = str(matchup_str).upper()
                # Format: "10/22 @ DAL" or "10/22 VS TOR"
                parts = matchup.split()
                if len(parts) >= 2:
                    return parts[-1]  # Last part is usually opponent
                return ''
            
            current_season = self.hot_hand_tracker.get_player_gamelog(player_name, season='2025-26')
            prev_season = self.hot_hand_tracker.get_player_gamelog(player_name, season='2024-25')
            
            h2h_games = []
            if current_season is not None and len(current_season) > 0 and 'MATCHUP' in current_season.columns:
                current_season['OPP'] = current_season['MATCHUP'].apply(extract_opponent)
                h2h_current = current_season[current_season['OPP'] == opponent.upper()].copy()
                if len(h2h_current) > 0:
                    h2h_games.append(h2h_current)
            
            if prev_season is not None and len(prev_season) > 0 and 'MATCHUP' in prev_season.columns:
                prev_season['OPP'] = prev_season['MATCHUP'].apply(extract_opponent)
                h2h_prev = prev_season[prev_season['OPP'] == opponent.upper()].copy()
                if len(h2h_prev) > 0:
                    h2h_games.append(h2h_prev)
            
            if not h2h_games:
                return None
            
            game_log = pd.concat(h2h_games, ignore_index=True) if len(h2h_games) > 1 else h2h_games[0]
            if 'GAME_DATE' in game_log.columns:
                game_log = game_log.sort_values('GAME_DATE', ascending=False)
            game_log = game_log.head(n_games)
        else:
            game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season='2025-26')
            if game_log is None or len(game_log) == 0:
                return None
            game_log = game_log.head(n_games)
        
        if game_log is None or len(game_log) == 0 or stat not in game_log.columns:
            return None
        
        # Convert stat to numeric
        game_log[stat] = pd.to_numeric(game_log[stat], errors='coerce')
        game_log = game_log[game_log[stat].notna()].copy()
        
        if len(game_log) == 0:
            return None
        
        # Sort by date (most recent first, then reverse for display)
        if 'GAME_DATE' in game_log.columns:
            game_log = game_log.sort_values('GAME_DATE', ascending=False).reset_index(drop=True)
        
        # Create labels: date and opponent
        labels = []
        for _, row in game_log.iterrows():
            label_parts = []
            
            # Date
            if 'GAME_DATE' in row:
                try:
                    date_str = pd.to_datetime(row['GAME_DATE']).strftime('%m/%d')
                    label_parts.append(date_str)
                except:
                    pass
            
            # Opponent from MATCHUP
            if 'MATCHUP' in row:
                matchup = str(row['MATCHUP'])
                # Format: "10/22 @ DAL" or "10/22 vs TOR"
                if '@' in matchup or 'vs' in matchup or 'VS' in matchup:
                    parts = matchup.split()
                    if len(parts) >= 2:
                        # Get opponent abbrev (last part usually)
                        opp = parts[-1]
                        if '@' in matchup:
                            label_parts.append(f"@ {opp}")
                        else:
                            label_parts.append(f"vs {opp}")
            
            labels.append(' '.join(label_parts) if label_parts else f"Game {len(labels)+1}")
        
        # Get values
        values = game_log[stat].fillna(0).tolist()
        
        # Determine colors: green for over, pink for under
        colors = ['#4ade80' if v > line else '#f472b6' for v in values]  # Green/pink
        
        # Create figure
        fig = go.Figure()
        
        # Add bars
        for i, (label, value, color) in enumerate(zip(labels, values, colors)):
            fig.add_trace(go.Bar(
                x=[i],
                y=[value],
                name=label,
                marker_color=color,
                text=str(int(value)) if value == int(value) else f"{value:.1f}",
                textposition='outside',
                textfont=dict(size=12, color='white', family='Arial Black'),
                showlegend=False,
                hovertemplate=f"{label}<br>{stat_label}: {value:.1f}<extra></extra>"
            ))
        
        # Add horizontal line for betting line
        fig.add_hline(
            y=line,
            line_dash="solid",
            line_color="white",
            line_width=2,
            annotation_text=f"{line}",
            annotation_position="right",
            annotation_font_size=12,
            annotation_font_color="white"
        )
        
        # Calculate average and median
        avg_value = np.mean(values)
        median_value = np.median(values)
        
        # Style layout
        max_val = max(max(values), line) * 1.15
        fig.update_layout(
            xaxis=dict(
                tickmode='array',
                tickvals=list(range(len(labels))),
                ticktext=labels,
                tickangle=-45,
                showgrid=False,
                zeroline=False,
                tickfont=dict(size=10, color='white')
            ),
            yaxis=dict(
                range=[0, max_val],
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                zeroline=False,
                tickfont=dict(size=10, color='white'),
                title=""
            ),
            template='plotly_dark',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin=dict(l=50, r=80, t=20, b=100),
            showlegend=False,
            hovermode='closest'
        )
        
        # Add average/median annotations
        fig.add_annotation(
            x=0.02, y=0.98,
            xref='paper', yref='paper',
            text=f"Average: {avg_value:.1f}<br>Median: {median_value:.0f}",
            showarrow=False,
            align='left',
            bgcolor='rgba(0,0,0,0.5)',
            bordercolor='white',
            borderwidth=1,
            font=dict(size=11, color='white')
        )
        
        return fig
    
    def get_stat_summary(self, player_name: str, stat: str, n_games: int = 5) -> Dict:
        """
        Get summary stats (average, median, etc.)
        """
        game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season='2025-26')
        if game_log is None or stat not in game_log.columns:
            return {'average': 0, 'median': 0}
        
        game_log[stat] = pd.to_numeric(game_log[stat], errors='coerce')
        recent = game_log.head(n_games)
        recent = recent[recent[stat].notna()]
        
        if len(recent) == 0:
            return {'average': 0, 'median': 0}
        
        return {
            'average': recent[stat].mean(),
            'median': recent[stat].median()
        }

