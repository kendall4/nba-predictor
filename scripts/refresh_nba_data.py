#!/usr/bin/env python3
"""
Refresh local NBA data used by the app (run on your machine — needs stats.nba.com access).

1. games_*.csv, team_pace_*.csv, player_stats_*.csv, defensive_matchups_*.csv (2024-25 + 2025-26)
2. data/cache/player_advanced_tracking_*.csv (advanced + scoring; add --full for hustle + tracking)

Usage (from repo root):

    venv/bin/python scripts/refresh_nba_data.py
    venv/bin/python scripts/refresh_nba_data.py --full
    venv/bin/python scripts/refresh_nba_data.py --seasons 2025-26
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--seasons",
        nargs="+",
        default=["2025-26", "2026-27"],
        help="Season labels matching nba_api / CSV names",
    )
    ap.add_argument(
        "--skip-defense",
        action="store_true",
        help="Skip defensive_matchups fetch (3 extra NBA calls per season)",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="Include hustle + player-tracking tables (~8 NBA calls per season)",
    )
    ap.add_argument(
        "--skip-tracking-cache",
        action="store_true",
        help="Only refresh raw CSVs under data/raw/",
    )
    args = ap.parse_args()

    from src.data_collection.nba_stats import NBAStatsCollector
    from src.data_collection.player_advanced_tracking_cache import (
        refresh_player_advanced_tracking_cache,
    )

    for season in args.seasons:
        print("\n" + "=" * 70)
        print(f"Raw CSVs: {season}")
        print("=" * 70)
        c = NBAStatsCollector(season=season)
        c.get_season_games()
        time.sleep(1.0)
        c.get_team_pace_stats()
        time.sleep(1.0)
        c.get_player_stats()
        time.sleep(1.0)
        if not args.skip_defense:
            try:
                c.get_defensive_matchups()
            except Exception as e:
                print(f"⚠️  defensive_matchups skipped: {e}")
            time.sleep(1.0)

    if args.skip_tracking_cache:
        print("\n✅ Raw CSV refresh complete (--skip-tracking-cache).")
        return 0

    quick = not args.full
    exit_code = 0
    for season in args.seasons:
        print("\n" + "=" * 70)
        print(f"Advanced / tracking cache: {season} ({'quick' if quick else 'full'})")
        print("=" * 70)
        ok, msg = refresh_player_advanced_tracking_cache(season, quick=quick)
        print(msg)
        if not ok:
            print(f"⚠️  Cache refresh reported failure for {season}", file=sys.stderr)
            exit_code = 1

    print("\n✅ Done. Restart Streamlit so @st.cache_resource picks up new CSV mtimes if needed.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
