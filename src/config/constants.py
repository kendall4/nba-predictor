"""
App-wide constants.

Keep magic numbers here so they're easy to find and change in one place.
"""

# ---------------------------------------------------------------------------
# Betting thresholds (BetGenerator)
# ---------------------------------------------------------------------------
MAINLINE_ODDS_THRESHOLD = +200   # Lines at or below this are treated as mainline
LONGSHOT_ODDS_THRESHOLD = +500   # Lines at or above this are treated as longshotss

# Kelly criterion fraction (0.25 = quarter-Kelly, safer sizing)
KELLY_FRACTION = 0.25

# ---------------------------------------------------------------------------
# Stat standard-deviation defaults (BetGenerator._get_default_std_dev)
# These are coefficients-of-variation (CV) applied to the prediction.
# Combined stats get lower CV because component correlations reduce variance.
# ---------------------------------------------------------------------------
STAT_STD_DEV_PCT: dict[str, float] = {
    'points':    0.20,
    'rebounds':  0.25,
    'assists':   0.30,
    'threes':    0.35,
    'steals':    0.40,
    'blocks':    0.45,
    'turnovers': 0.35,
    # Combined — lower because P/R/A are positively correlated (~0.3-0.5)
    'pra': 0.18,
    'pr':  0.19,
    'ra':  0.22,
    'pa':  0.20,
}

# Minimum std_dev to avoid dividing by zero on very low-volume props
MIN_STD_DEV = 0.5

# Blend ratio for player-specific vs default std_dev (player-specific weight)
PLAYER_STD_DEV_BLEND = 0.70   # 70% player-specific, 30% league default

# ---------------------------------------------------------------------------
# League-wide baselines (MatchupFeatureBuilder)
# ---------------------------------------------------------------------------
LEAGUE_TRUE_SHOOTING_PCT = 0.56   # 2024-25 NBA average TS%

# ---------------------------------------------------------------------------
# NBA seasons
# ---------------------------------------------------------------------------
CURRENT_SEASON = '2026-27'
PREV_SEASON = '2025-26'

# Minimum games in a player's game log to trust historical std_dev
MIN_GAMES_FOR_STD_DEV = 5

# ---------------------------------------------------------------------------
# NBA API
# ---------------------------------------------------------------------------
SEASON_TYPE_REGULAR = 'Regular Season'
