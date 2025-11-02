"""
Player Performance Visualizations
==================================
Create interactive charts for player performance over different time periods
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Optional, List
from src.analysis.hot_hand_tracker import HotHandTracker


class PlayerVisualizer:
    """
    Create visualizations for player performance stats
    """
    
    def __init__(self):
        self.hot_hand_tracker = HotHandTracker()
    
    def get_game_log_for_visualization(self, player_name: str, n: int = 5, season: str = '2025-26',
                                       opponent: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get game log data formatted for visualization
        
        Args:
            player_name: Player to visualize
            n: Number of games (1, 5, 10, etc.)
            season: Season to analyze
            opponent: Optional opponent team abbreviation for H2H (e.g., 'LAL', 'GSW')
        
        Returns:
            DataFrame with game data ready for charts
        """
        if opponent:
            # Head-to-head mode
            consistency = self.hot_hand_tracker.consistency_h2h(player_name, 'points', 0, opponent, season)
            # Get full H2H game log
            current_season_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
            prev_season_log = self.hot_hand_tracker.get_player_gamelog(player_name, season='2024-25')
            
            h2h_games = []
            if current_season_log is not None and len(current_season_log) > 0:
                current_season_log['OPP'] = current_season_log['MATCHUP'].apply(
                    self.hot_hand_tracker._parse_opponent_from_matchup
                )
                h2h_current = current_season_log[current_season_log['OPP'] == opponent].copy()
                if len(h2h_current) > 0:
                    h2h_games.append(h2h_current)
            
            if prev_season_log is not None and len(prev_season_log) > 0:
                prev_season_log['OPP'] = prev_season_log['MATCHUP'].apply(
                    self.hot_hand_tracker._parse_opponent_from_matchup
                )
                h2h_prev = prev_season_log[prev_season_log['OPP'] == opponent].copy()
                if len(h2h_prev) > 0:
                    h2h_games.append(h2h_prev)
            
            if not h2h_games:
                return None
            
            combined = pd.concat(h2h_games, ignore_index=True) if len(h2h_games) > 1 else h2h_games[0]
            if 'GAME_DATE' in combined.columns:
                combined = combined.sort_values('GAME_DATE', ascending=False)
            return combined.head(n)
        else:
            # Regular last N games
            game_log = self.hot_hand_tracker.get_player_gamelog(player_name, season=season)
            if game_log is None or len(game_log) == 0:
                return None
            
            return game_log.head(n)
    
    def create_bar_chart(self, df: pd.DataFrame, stat: str, player_name: str, 
                        time_period: str = "Last 5 Games") -> go.Figure:
        """
        Create a bar chart for a specific stat
        
        Args:
            df: Game log DataFrame
            stat: Stat to visualize ('points', 'rebounds', 'assists', 'threes', 'combined')
            player_name: Player name for title
            time_period: Label for time period (e.g., "Last 5 Games", "H2H vs LAL")
        
        Returns:
            Plotly figure
        """
        if df is None or len(df) == 0:
            return None
        
        # Map stat names to columns
        stat_map = {
            'points': ('PTS', 'Points'),
            'rebounds': ('REB', 'Rebounds'),
            'assists': ('AST', 'Assists'),
            'threes': ('FG3M', '3-Pointers Made'),
            'combined': (None, 'PTS + REB + AST')  # Will calculate
        }
        
        if stat not in stat_map:
            return None
        
        col_name, display_name = stat_map[stat]
        
        # Prepare data
        chart_df = df.copy()
        
        # Create game labels (game number or date)
        if 'GAME_DATE' in chart_df.columns:
            chart_df['Game'] = pd.to_datetime(chart_df['GAME_DATE']).dt.strftime('%m/%d')
        elif 'MATCHUP' in chart_df.columns:
            chart_df['Game'] = chart_df['MATCHUP'].str[:10]  # Truncate matchup
        else:
            chart_df['Game'] = [f"Game {i+1}" for i in range(len(chart_df))]
        
        # Reverse order so most recent is on right
        chart_df = chart_df.sort_values('GAME_DATE' if 'GAME_DATE' in chart_df.columns else chart_df.index[0], 
                                        ascending=True).reset_index(drop=True)
        
        # Get values
        if stat == 'combined':
            # Sum of PTS + REB + AST
            if all(c in chart_df.columns for c in ['PTS', 'REB', 'AST']):
                chart_df['Value'] = (
                    chart_df['PTS'].fillna(0) + 
                    chart_df['REB'].fillna(0) + 
                    chart_df['AST'].fillna(0)
                )
            else:
                chart_df['Value'] = 0
        else:
            if col_name not in chart_df.columns:
                return None
            chart_df['Value'] = chart_df[col_name].fillna(0)
        
        # Create bar chart
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=chart_df['Game'],
            y=chart_df['Value'],
            name=display_name,
            marker_color='#00e5b0',  # Match app theme
            marker_line_color='#00b3a4',
            marker_line_width=1.5,
            text=chart_df['Value'].round(1),
            textposition='outside',
            textfont=dict(size=11, color='#E6F6F3')
        ))
        
        # Calculate average line
        avg_value = chart_df['Value'].mean()
        fig.add_hline(
            y=avg_value,
            line_dash="dash",
            line_color="#BFFFEF",
            annotation_text=f"Avg: {avg_value:.1f}",
            annotation_position="right",
            annotation_font_size=10
        )
        
        # Styling
        fig.update_layout(
            title={
                'text': f"{player_name} - {display_name} ({time_period})",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': '#BFFFEF'}
            },
            xaxis_title="Game",
            yaxis_title=display_name,
            template='plotly_dark',
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#E6F6F3', size=12),
            xaxis=dict(gridcolor='rgba(255,255,255,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(255,255,255,0.1)', showgrid=True),
            height=400,
            margin=dict(l=50, r=50, t=60, b=50),
            showlegend=False
        )
        
        return fig
    
    def create_multi_stat_comparison(self, df: pd.DataFrame, player_name: str,
                                     time_period: str = "Last 5 Games") -> go.Figure:
        """
        Create a chart comparing multiple stats side-by-side
        """
        if df is None or len(df) == 0:
            return None
        
        # Prepare data
        chart_df = df.copy()
        
        if 'GAME_DATE' in chart_df.columns:
            chart_df['Game'] = pd.to_datetime(chart_df['GAME_DATE']).dt.strftime('%m/%d')
            chart_df = chart_df.sort_values('GAME_DATE', ascending=True).reset_index(drop=True)
        else:
            chart_df['Game'] = [f"Game {i+1}" for i in range(len(chart_df))]
        
        # Get all stat columns
        stats_to_plot = []
        if 'PTS' in chart_df.columns:
            stats_to_plot.append(('PTS', 'Points', '#00e5b0'))
        if 'REB' in chart_df.columns:
            stats_to_plot.append(('REB', 'Rebounds', '#00b3a4'))
        if 'AST' in chart_df.columns:
            stats_to_plot.append(('AST', 'Assists', '#00ffff'))
        if 'FG3M' in chart_df.columns:
            stats_to_plot.append(('FG3M', '3PM', '#66ff99'))
        
        if not stats_to_plot:
            return None
        
        fig = go.Figure()
        
        for col, label, color in stats_to_plot:
            fig.add_trace(go.Bar(
                x=chart_df['Game'],
                y=chart_df[col].fillna(0),
                name=label,
                marker_color=color,
                text=chart_df[col].fillna(0).round(1),
                textposition='outside',
                textfont=dict(size=9, color='#E6F6F3')
            ))
        
        fig.update_layout(
            title={
                'text': f"{player_name} - Multi-Stat Comparison ({time_period})",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': '#BFFFEF'}
            },
            xaxis_title="Game",
            yaxis_title="Value",
            barmode='group',
            template='plotly_dark',
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='#E6F6F3', size=12),
            xaxis=dict(gridcolor='rgba(255,255,255,0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(255,255,255,0.1)', showgrid=True),
            height=450,
            margin=dict(l=50, r=50, t=60, b=50),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color='#E6F6F3')
            )
        )
        
        return fig

