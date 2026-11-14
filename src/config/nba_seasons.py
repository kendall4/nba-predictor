"""
Central NBA season labels for caches, features, and prediction logging.

Predictions and primary raw stats target the current season; some optional NBA.com
caches may fall back to the prior season file if the current-season CSV is missing.
"""

# Season string as used by nba_api / our CSVs (e.g. player_stats_2026-27.csv)
PRIMARY_NBA_SEASON: str = "2026-27"

# Prior completed season — used for early-season blend / fallbacks.
PREV_NBA_SEASON: str = "2025-26"

# Used only when PRIMARY cache file is absent (e.g. API hiccup); clearly labeled in logs/UI.
ADV_TRACKING_FALLBACK_SEASON: str = "2025-26"
