"""
Fetch and cache league-wide **player** advanced + scoring + hustle + tracking (NBA stats API).

Writes one merged parquet-friendly CSV under data/cache/ for fast loads during predictions.
Requires `nba_api` and network when refreshing; load-only path is used in MatchupFeatureBuilder.

Refresh (CLI or UI):
    python -m src.data_collection.player_advanced_tracking_cache 2025-26 --quick   # fast: 2 calls
    python -m src.data_collection.player_advanced_tracking_cache 2025-26 --full    # hustle + PT (slow)
    python -m src.data_collection.player_advanced_tracking_cache 2025-26 --no-fallback
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import pandas as pd

from src.config.nba_seasons import ADV_TRACKING_FALLBACK_SEASON, PRIMARY_NBA_SEASON

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Tighter defaults so Streamlit doesn’t “hang” for 10+ minutes; override via env if needed.
DELAY_S = _env_float("NBA_ADV_TRACKING_STAGGER", 0.35)
MAX_RETRIES = max(1, min(5, _env_int("NBA_ADV_TRACKING_RETRIES", 2)))
RETRY_BASE_DELAY_S = _env_float("NBA_ADV_TRACKING_RETRY_DELAY", 1.25)
FETCH_TIMEOUT = max(15, _env_int("NBA_ADV_TRACKING_TIMEOUT", 50))

logger = logging.getLogger(__name__)


def _season_api(season: str) -> str:
    return season.strip()


def _with_retries(
    label: str,
    fetch_fn: Callable[[], pd.DataFrame],
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Run fetch with retries; return (df, None) or (None, error summary)."""
    last_err: Optional[str] = None
    for attempt in range(MAX_RETRIES):
        try:
            df = fetch_fn()
            if df is not None and len(df) > 0 and "PLAYER_ID" in df.columns:
                return df, None
            last_err = "empty DataFrame or missing PLAYER_ID column"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            logger.warning("NBA fetch %s attempt %s/%s failed: %s", label, attempt + 1, MAX_RETRIES, last_err)
        if attempt + 1 < MAX_RETRIES:
            time.sleep(RETRY_BASE_DELAY_S * (attempt + 1))
    return None, f"{label}: {last_err}"


def _fetch_league_dash_players(season: str, measure_type: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
        from nba_api.stats.library.parameters import (
            LeagueIDNullable,
            PerModeDetailed,
            SeasonTypeAllStar,
        )
    except ImportError as e:
        return None, f"nba_api import failed: {e}"

    def _call() -> pd.DataFrame:
        r = leaguedashplayerstats.LeagueDashPlayerStats(
            season=_season_api(season),
            season_type_all_star=SeasonTypeAllStar.regular,
            measure_type_detailed_defense=measure_type,
            per_mode_detailed=PerModeDetailed.per_game,
            league_id_nullable=LeagueIDNullable.default,
            timeout=FETCH_TIMEOUT,
        )
        return r.league_dash_player_stats.get_data_frame()

    return _with_retries(f"LeagueDashPlayerStats({measure_type!r})", _call)


def _fetch_hustle(season: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        from nba_api.stats.endpoints import leaguehustlestatsplayer
        from nba_api.stats.library.parameters import PerModeTime, SeasonTypeAllStar
    except ImportError as e:
        return None, f"nba_api import failed: {e}"

    def _call() -> pd.DataFrame:
        r = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=_season_api(season),
            season_type_all_star=SeasonTypeAllStar.regular,
            per_mode_time=PerModeTime.per_game,
            timeout=FETCH_TIMEOUT,
        )
        return r.hustle_stats_player.get_data_frame()

    return _with_retries("LeagueHustleStatsPlayer", _call)


def _fetch_pt_measure(season: str, pt_measure: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        from nba_api.stats.endpoints import leaguedashptstats
        from nba_api.stats.library.parameters import PlayerOrTeam, PerModeSimple, SeasonTypeAllStar
    except ImportError as e:
        return None, f"nba_api import failed: {e}"

    def _call() -> pd.DataFrame:
        r = leaguedashptstats.LeagueDashPtStats(
            season=_season_api(season),
            season_type_all_star=SeasonTypeAllStar.regular,
            pt_measure_type=pt_measure,
            player_or_team=PlayerOrTeam.player,
            per_mode_simple=PerModeSimple.per_game,
            timeout=FETCH_TIMEOUT,
        )
        return r.league_dash_pt_stats.get_data_frame()

    return _with_retries(f"LeagueDashPtStats({pt_measure!r})", _call)


def _numeric_suffix_merge(
    base: pd.DataFrame,
    add: pd.DataFrame,
    suffix: str,
    key: str = "PLAYER_ID",
) -> pd.DataFrame:
    if add is None or len(add) == 0 or key not in add.columns:
        return base
    if key not in base.columns:
        return base
    drop = [c for c in add.columns if c in base.columns and c != key]
    sub = add.drop(columns=drop, errors="ignore").copy()
    id_like = {"PLAYER_NAME", "NICKNAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE", "GP", "G"}
    rename_map = {}
    for c in sub.columns:
        if c == key or c in id_like:
            continue
        if pd.api.types.is_numeric_dtype(sub[c]) or sub[c].dtype == object:
            try:
                sub[c] = pd.to_numeric(sub[c], errors="coerce")
            except Exception:
                pass
        if c not in id_like:
            rename_map[c] = f"{c}{suffix}"
    sub = sub.rename(columns=rename_map)
    keep = [key] + [rename_map[k] for k in rename_map]
    keep = [c for c in keep if c in sub.columns]
    return base.merge(sub[keep], on=key, how="left")


def _refresh_one_season(season: str, quick: bool = False) -> Tuple[Optional[pd.DataFrame], List[str]]:
    """
    Fetch and merge tables for a single season.

    ``quick=True`` (default for in-app): **Advanced + Scoring only** (~2 NBA.com calls).
    ``quick=False``: adds hustle + 4 player-tracking tables (~8 calls) — use **terminal** if possible;
    Streamlit blocks the UI for the whole run.
    """
    try:
        from nba_api.stats.library.parameters import MeasureTypeDetailedDefense
    except ImportError:
        return None, ["nba_api not installed or broken import"]

    errors: List[str] = []
    parts: List[Tuple[str, Optional[pd.DataFrame]]] = []

    time.sleep(DELAY_S)
    adv, err = _fetch_league_dash_players(season, MeasureTypeDetailedDefense.advanced)
    if err:
        errors.append(err)
    parts.append(("adv", adv))

    time.sleep(DELAY_S)
    scr, err = _fetch_league_dash_players(season, MeasureTypeDetailedDefense.scoring)
    if err:
        errors.append(err)
    parts.append(("scr", scr))

    if not quick:
        time.sleep(DELAY_S)
        hus, err = _fetch_hustle(season)
        if err:
            errors.append(err)
        parts.append(("hstl", hus))

        for pt_label in ("CatchShoot", "PullUpShot", "PaintTouch", "SpeedDistance"):
            time.sleep(DELAY_S)
            pt, err = _fetch_pt_measure(season, pt_label)
            if err:
                errors.append(err)
            parts.append((f"pt_{pt_label}", pt))

    base = None
    for label, df in parts:
        if df is None or len(df) == 0 or "PLAYER_ID" not in df.columns:
            continue
        df = df.drop_duplicates(subset=["PLAYER_ID"], keep="last")
        if base is None:
            base = df.copy()
            continue
        base = _numeric_suffix_merge(base, df, suffix=f"__{label}")

    if base is None or len(base) == 0:
        return None, errors
    return base, errors


def refresh_player_advanced_tracking_cache(
    season: str = PRIMARY_NBA_SEASON,
    fallback_seasons: Optional[List[str]] = None,
    *,
    quick: bool = True,
) -> Tuple[bool, str]:
    """
    Pull league player tables and merge on ``PLAYER_ID``.

    ``quick=True`` (default): **Advanced + Scoring** only — enough for TS%, USG%, most rates; ~2 API calls.
    ``quick=False``: adds hustle + player tracking — ~8 calls; **prefer running in a terminal** for reliability.

    **Always tries the requested ``season`` first** (default: :data:`~src.config.nba_seasons.PRIMARY_NBA_SEASON`).

    If the primary season returns no rows, tries ``fallback_seasons``. When that argument is omitted,
    the default fallback is :data:`~src.config.nba_seasons.ADV_TRACKING_FALLBACK_SEASON` only if
    ``season`` equals the primary season constant (so custom seasons are not auto-fallback unless
    you pass ``fallback_seasons=[...]``).

    Pass ``fallback_seasons=[]`` to disable any fallback.
    """
    primary = _season_api(season)
    if fallback_seasons is not None:
        fallbacks = list(fallback_seasons)
    else:
        fallbacks = []
        if primary == PRIMARY_NBA_SEASON:
            fallbacks.append(ADV_TRACKING_FALLBACK_SEASON)

    tried: List[str] = []
    last_detail = ""

    for s in [primary] + [x for x in fallbacks if x and _season_api(x) != primary]:
        s = _season_api(s)
        tried.append(s)
        base, errs = _refresh_one_season(s, quick=quick)
        if base is not None and len(base) > 0:
            path = CACHE_DIR / f"player_advanced_tracking_{s.replace('-', '_')}.csv"
            try:
                base.to_csv(path, index=False)
            except Exception as e:
                return False, str(e)
            note = ""
            if s != primary:
                note = f" (used fallback season **{s}** — update app season / re-fetch for {primary} when API has data)"
            qnote = " (**quick:** Advanced+Scoring only)" if quick else " (**full:** incl. hustle + PT)"
            ok_msg = f"Saved {len(base)} players × {len(base.columns)} cols → `{path}`{qnote}{note}"
            if errs:
                ok_msg += f"\n\n⚠️ Some optional tables failed (partial merge): " + "; ".join(errs[:6])
                if len(errs) > 6:
                    ok_msg += f" … +{len(errs) - 6} more"
            return True, ok_msg
        last_detail = "; ".join(errs) if errs else "all endpoints returned empty"

    tips = (
        "Tips: run from **project root**; `nba_api` in same venv. "
        "For **full** hustle+PT fetch use a **terminal** (Streamlit freezes until HTTP finishes): "
        "`python -m src.data_collection.player_advanced_tracking_cache 2025-26 --full`. "
        "Quick refresh: add `--quick`. stats.nba.com may rate-limit — retry or change network."
    )
    return (
        False,
        f"No player rows after trying seasons: {', '.join(tried)}. Last errors: {last_detail}\n\n{tips}",
    )


def load_player_advanced_tracking(
    season: Optional[str] = None,
    *,
    fallback_season: Optional[str] = None,
    allow_fallback: bool = True,
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Load merged cache only (no API).

    **Order:** primary ``season`` (default: PRIMARY_NBA_SEASON), then optional fallback file.

    Returns:
        ``(dataframe, resolved_season)`` where ``resolved_season`` is which season's file was loaded
        (e.g. ``\"2025-26\"`` or ``\"2024-25\"``), or ``(None, None)`` if nothing on disk.
    """
    primary = _season_api(season) if season else PRIMARY_NBA_SEASON
    fb = ADV_TRACKING_FALLBACK_SEASON if fallback_season is None else fallback_season

    to_try: List[str] = [primary]
    if allow_fallback and fb and _season_api(fb) != primary:
        to_try.append(_season_api(fb))

    for s in to_try:
        path = CACHE_DIR / f"player_advanced_tracking_{s.replace('-', '_')}.csv"
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
            if len(df) > 0 and "PLAYER_ID" in df.columns:
                df["PLAYER_ID"] = pd.to_numeric(df["PLAYER_ID"], errors="coerce").astype("Int64")
                return df, s
        except Exception:
            continue
    return None, None


def row_for_player_id(df: Optional[pd.DataFrame], player_id: Optional[int]) -> Optional[pd.Series]:
    if df is None or len(df) == 0:
        return None
    try:
        pid = int(player_id)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    m = df["PLAYER_ID"] == pid
    if not m.any():
        return None
    return df.loc[m].iloc[0]


def tracking_features_from_row(row: pd.Series) -> dict:
    """
    Flatten a subset of API columns into prediction feature keys (prefix api_*).
    Safe when row is None. Merged columns may be suffixed (e.g. DEFLECTIONS__hstl).
    """
    if row is None or len(row) == 0:
        return {"api_adv_tracking_loaded": False}

    def g(*names: str) -> Optional[float]:
        for n in names:
            if n in row.index and pd.notna(row[n]):
                try:
                    return float(row[n])
                except (TypeError, ValueError):
                    continue
        for n in names:
            for col in row.index:
                sc = str(col)
                if sc.startswith(f"{n}__") and pd.notna(row[col]):
                    try:
                        return float(row[col])
                    except (TypeError, ValueError):
                        continue
        return None

    out = {
        "api_adv_tracking_loaded": True,
        "api_ts_pct": g("TS_PCT"),
        "api_usg_pct": g("USG_PCT"),
        "api_oreb_pct": g("OREB_PCT"),
        "api_dreb_pct": g("DREB_PCT"),
        "api_reb_pct": g("REB_PCT"),
        "api_ast_pct": g("AST_PCT"),
        "api_tov_pct": g("TOV_PCT"),
        "api_efg_pct": g("EFG_PCT"),
        "api_off_rating": g("OFF_RATING"),
        "api_def_rating": g("DEF_RATING"),
        "api_net_rating": g("NET_RATING"),
        "api_pie": g("PIE"),
        "api_pace": g("PACE"),
        "api_pct_pts_paint": g("PCT_PTS_PAINT"),
        "api_pct_fga_2pt": g("PCT_FGA_2PT"),
        "api_pct_fga_3pt": g("PCT_FGA_3PT"),
        "api_pct_pts_2pt": g("PCT_PTS_2PT"),
        "api_pct_pts_3pt": g("PCT_PTS_3PT"),
        "api_deflections": g("DEFLECTIONS"),
        "api_contested_shots": g("CONTESTED_SHOTS"),
        "api_screen_assists": g("SCREEN_ASSISTS"),
        "api_loose_balls_rec": g("LOOSE_BALLS_RECOVERED"),
    }
    # Merged tracking columns (suffix __pt_*)
    for col in row.index:
        if not isinstance(col, str):
            continue
        cu = col.upper().replace(" ", "_")
        if out.get("api_catch_shoot_fga") is None and "CATCH" in cu and "FGA" in cu:
            v = g(col)
            if v is not None:
                out["api_catch_shoot_fga"] = v
        if out.get("api_pullup_fga") is None and "PULL" in cu and "FGA" in cu:
            v = g(col)
            if v is not None:
                out["api_pullup_fga"] = v
        if out.get("api_paint_touches") is None and "PAINT" in cu and "TOUCH" in cu:
            v = g(col)
            if v is not None:
                out["api_paint_touches"] = v
        if out.get("api_speed_metric") is None and (
            cu in ("DIST_MILES", "DIST_FEET", "AVG_SPEED", "AVG_SPD") or "SPEED" in cu
        ):
            v = g(col)
            if v is not None:
                out["api_speed_metric"] = v
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Refresh NBA player advanced + hustle + tracking cache")
    ap.add_argument("season", nargs="?", default=PRIMARY_NBA_SEASON)
    ap.add_argument("--force", "-f", action="store_true", help="Reserved for future skip-if-fresh behavior")
    ap.add_argument(
        "--no-fallback",
        action="store_true",
        help=f"Only fetch the given season; do not try {ADV_TRACKING_FALLBACK_SEASON} if it fails",
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--quick",
        action="store_true",
        help="Advanced + Scoring only (~2 calls, default)",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help="Include hustle + player tracking (~8 calls)",
    )
    args = ap.parse_args()
    fb: Optional[List[str]] = [] if args.no_fallback else None
    quick = not args.full  # default quick unless --full (--quick is explicit alias of default)
    ok, msg = refresh_player_advanced_tracking_cache(
        args.season, fallback_seasons=fb, quick=quick
    )
    print(msg)
    raise SystemExit(0 if ok else 1)
