"""
Derived per-player advanced-style rates from traditional box columns (no extra API).

These complement **team** context (pace, def rating, shot zones): performance is both
how the player operates individually (efficiency, shot mix, foul pressure) and the
environment (opponent, scheme, pace).
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def player_derived_advanced_rates(player_row: Any) -> Dict[str, float]:
    """
    Compute TS%, eFG%, 3-point attempt rate, FT rate, rebound activity from season row.

    Expects keys like FGM, FGA, FG3M, FG3A, FTM, FTA, PTS, OREB, DREB, MIN (per-game).
    Returns neutral defaults if volume too low.
    """
    out: Dict[str, float] = {
        "ts_pct": 0.56,
        "efg_pct": 0.52,
        "three_point_ar": 0.38,
        "ft_rate": 0.22,
        "oreb_pct_activity": 0.0,
        "dreb_pct_activity": 0.0,
    }
    def _num(key: str, default: float = 0.0) -> float:
        # float(nan) is truthy, so `nan or 0` does NOT fall back — guard explicitly
        try:
            v = float(player_row.get(key, default))
            return default if not np.isfinite(v) else v
        except (TypeError, ValueError):
            return default

    try:
        fgm = _num("FGM")
        fga = _num("FGA")
        fg3m = _num("FG3M")
        fg3a = _num("FG3A")
        ftm = _num("FTM")
        fta = _num("FTA")
        pts = _num("PTS")
        oreb = _num("OREB")
        dreb = _num("DREB")
        mn = _num("MIN")

        if fga < 2.0 or mn < 5.0:
            return out

        # eFG% = (FGM + 0.5 * 3PM) / FGA
        efg = (fgm + 0.5 * fg3m) / max(fga, 1e-6)
        # TS% = PTS / (2 * (FGA + 0.44 * FTA))
        ts_denom = 2.0 * (fga + 0.44 * max(fta, 0.0))
        ts = pts / max(ts_denom, 1e-6)
        three_ar = fg3a / max(fga, 1e-6)
        ftr = fta / max(fga, 1e-6)

        out["ts_pct"] = float(np.clip(ts, 0.35, 0.75))
        out["efg_pct"] = float(np.clip(efg, 0.35, 0.75))
        out["three_point_ar"] = float(np.clip(three_ar, 0.05, 0.85))
        out["ft_rate"] = float(np.clip(ftr, 0.0, 1.2))
        # Activity proxies (not true REB% — need team rebounds); useful for big vs guard tilt
        out["oreb_pct_activity"] = float(np.clip(oreb / max(mn, 1e-6) * 36.0, 0.0, 8.0))
        out["dreb_pct_activity"] = float(np.clip(dreb / max(mn, 1e-6) * 36.0, 0.0, 18.0))
    except Exception:
        pass
    return out


def efficiency_volatility_nudge(ts_pct: float, league_ts: float = 0.56) -> float:
    """
    Tiny multiplier (≈0.98–1.02): slightly more trust in projection for above-avg efficiency.

    Does not replace matchup or pace — only nudges the blended scoring_context path.
    """
    try:
        delta = float(ts_pct) - float(league_ts)
        return float(np.clip(1.0 + 0.12 * delta, 0.985, 1.02))
    except Exception:
        return 1.0
