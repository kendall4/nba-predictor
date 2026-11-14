"""
Opponent-aware adjustments on top of base matchup features.

- Rebounds: opponent glass (DREB%/OREB%) + their shooting efficiency (more misses → more events).
- Scoring: match player interior vs perimeter tendency to overall defensive weakness (def_factor).
- Shot zones (optional): when ``data/cache/{season}_shot_zones_*.csv`` exists (from NBA shot locations),
  align **team** rim/3pt volume + **opponent** allowed rim/3pt profile with player paint/perimeter tilt.

Shot charts are optional because they require a one-time cache fetch (see ``team_shot_matchup.refresh_shot_zone_cache``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def compute_league_baselines_from_pace(pace_df: pd.DataFrame) -> Dict[str, float]:
    """League means from blended team pace table."""
    out: Dict[str, float] = {
        "dreb_pct": 0.73,
        "oreb_pct": 0.27,
        "efg_pct": 0.54,
        "fg3a_rate": 0.42,
    }
    if pace_df is None or len(pace_df) == 0:
        return out
    try:
        if "DREB_PCT" in pace_df.columns:
            out["dreb_pct"] = float(pace_df["DREB_PCT"].astype(float).mean())
        if "OREB_PCT" in pace_df.columns:
            out["oreb_pct"] = float(pace_df["OREB_PCT"].astype(float).mean())
        if "EFG_PCT" in pace_df.columns:
            out["efg_pct"] = float(pace_df["EFG_PCT"].astype(float).mean())
    except Exception:
        pass
    return out


def compute_league_fg3_share_from_players(players_df: pd.DataFrame) -> float:
    """Mean FG3A / FGA among players with meaningful volume (for perimeter index)."""
    if players_df is None or len(players_df) == 0:
        return 0.38
    try:
        fga = pd.to_numeric(players_df.get("FGA"), errors="coerce")
        fg3a = pd.to_numeric(players_df.get("FG3A"), errors="coerce")
        m = (fga > 5) & (fg3a.notna()) & (fga.notna())
        if m.sum() < 50:
            return 0.38
        return float((fg3a[m] / fga[m]).clip(0.05, 0.85).mean())
    except Exception:
        return 0.38


def rebound_opponent_multiplier(opp_row: pd.Series, baselines: Dict[str, float]) -> float:
    """
    >1 when opponent is weaker on the defensive glass and/or misses more (lower eFG).
    <1 when they crash OREB hard (fewer DREB for us) or are elite DREB%.
    """
    mult = 1.0
    try:
        ld = float(baselines.get("dreb_pct", 0.73))
        lo = float(baselines.get("oreb_pct", 0.27))
        lefg = float(baselines.get("efg_pct", 0.54))

        od = float(opp_row.get("DREB_PCT", ld))
        oo = float(opp_row.get("OREB_PCT", lo))
        oefg = float(opp_row.get("EFG_PCT", lefg))

        if ld > 1e-6:
            # Lower opponent DREB% → worse at securing misses → more board chances for us
            mult += 0.22 * (ld - od) / ld
        if lo > 1e-6:
            # Higher opponent OREB% → they own their misses → fewer DREB for us
            mult -= 0.14 * (oo - lo) / lo
        if lefg > 1e-6:
            # Lower opponent eFG (their offense) → more misses when they shoot → more DREB chances
            mult += 0.12 * (lefg - oefg) / lefg
    except Exception:
        return 1.0
    return float(np.clip(mult, 0.93, 1.10))


def player_paint_and_perimeter_index(player_row: pd.Series, league_fg3_share: float) -> tuple[float, float]:
    """
    Returns (paint_index, perimeter_index) roughly in [-1, 1].
    paint: 2PT volume + foul drawing proxy
    perimeter: 3PA rate vs league
    """
    def _num(key: str, default: float = 0.0) -> float:
        try:
            v = float(player_row.get(key, default))
            return default if not np.isfinite(v) else v
        except (TypeError, ValueError):
            return default

    try:
        fga = _num("FGA")
        fg3a = _num("FG3A")
        fta = _num("FTA")
        if fga < 3:
            return 0.0, 0.0
        two_share = (fga - fg3a) / fga
        # League typical two_share ~ 0.55–0.62; normalize around 0.58
        paint_raw = (two_share - 0.58) / 0.22
        ft_rate = fta / fga
        # ~0.25 FTA/FGA is high drive pressure
        ft_raw = (ft_rate - 0.22) / 0.18
        paint_index = float(np.clip(0.62 * np.clip(paint_raw, -1, 1) + 0.38 * np.clip(ft_raw, -1, 1), -1, 1))

        three_share = fg3a / fga
        perim_raw = (three_share - league_fg3_share) / max(0.12, league_fg3_share)
        perimeter_index = float(np.clip(perim_raw, -1, 1))
        return paint_index, perimeter_index
    except Exception:
        return 0.0, 0.0


def scoring_profile_multiplier(
    player_row: pd.Series,
    _opp_row: pd.Series,
    def_factor: float,
    _baselines: Dict[str, float],
    league_fg3_share: float,
) -> float:
    """
    Small tilt: interior-heavy scorers get a bit more vs weak D; perimeter-heavy scorers
    get a bit more when opponent is soft overall (def_factor > 1). Capped.
    """
    try:
        paint_i, perim_i = player_paint_and_perimeter_index(player_row, league_fg3_share)
        # def_factor > 1 → opponent allows more than avg (weak D relative to 112 baseline)
        d_tail = float(def_factor) - 1.0
        # Typical d_tail in [-0.06, 0.08]
        scale = 0.45  # dampen
        interior_term = scale * paint_i * d_tail
        # Perimeter specialists still benefit from weak D, but less tied to "paint"
        perimeter_term = 0.28 * perim_i * d_tail
        mult = 1.0 + interior_term + perimeter_term
        # Optional: opponent allows more threes context — use their defensive EFG proxy via TS/EFG
        # If opponent has very high eFG it's their offense quality, not our matchup; skip extra.

        return float(np.clip(mult, 0.965, 1.055))
    except Exception:
        return 1.0


def shot_zone_context_multipliers(
    player_team: str,
    opponent_team: str,
    paint_profile_index: float,
    perimeter_profile_index: float,
    offense_df: Optional[pd.DataFrame],
    defense_df: Optional[pd.DataFrame],
) -> tuple[float, float, Dict[str, Any]]:
    """
    Team shot-location alignment: player's team offensive mix vs what opponents allow vs this defense.

    Defense CSV (measure=opponent): rim_fga_pct / 3pt shares = what **opponents** shoot vs this team
    (higher rim_fga_pct ⇒ more rim attempts allowed ⇒ leaky paint). Offense CSV: this team's attempt mix.

    Returns (points_mult, threes_mult, meta) — multipliers near 1.0 if data missing.
    """
    meta: Dict[str, Any] = {"shot_zones_active": False}
    if offense_df is None or defense_df is None:
        return 1.0, 1.0, meta
    if len(offense_df) == 0 or len(defense_df) == 0:
        return 1.0, 1.0, meta
    need = {
        "TEAM_ABBREVIATION",
        "rim_fga_pct",
        "corner3_fga_pct",
        "above_break3_fga_pct",
        "rim_fg_pct",
    }
    if not need.issubset(set(offense_df.columns)) or not need.issubset(set(defense_df.columns)):
        meta["reason"] = "missing_columns"
        return 1.0, 1.0, meta

    pt = str(player_team).strip().upper()
    ot = str(opponent_team).strip().upper()
    try:
        o = offense_df.set_index("TEAM_ABBREVIATION")
        d = defense_df.set_index("TEAM_ABBREVIATION")
        if pt not in o.index or ot not in d.index:
            meta["reason"] = "team_not_in_shot_cache"
            return 1.0, 1.0, meta

        league_rim_allow = float(d["rim_fga_pct"].astype(float).mean())
        league_3_allow = float(
            (d["corner3_fga_pct"].astype(float) + d["above_break3_fga_pct"].astype(float)).mean()
        )
        league_rim_off = float(o["rim_fga_pct"].astype(float).mean())
        league_3_off = float(
            (o["corner3_fga_pct"].astype(float) + o["above_break3_fga_pct"].astype(float)).mean()
        )
        league_rim_fg_allowed = float(d["rim_fg_pct"].astype(float).mean())

        opp_rim_allow = float(d.loc[ot, "rim_fga_pct"])
        opp_3_allow = float(d.loc[ot, "corner3_fga_pct"] + d.loc[ot, "above_break3_fga_pct"])
        opp_rim_fg_allowed = float(d.loc[ot, "rim_fg_pct"])

        team_rim = float(o.loc[pt, "rim_fga_pct"])
        team_3 = float(o.loc[pt, "corner3_fga_pct"] + o.loc[pt, "above_break3_fga_pct"])

        rim_allow_z = (opp_rim_allow - league_rim_allow) / max(league_rim_allow * 0.12, 1.0)
        rim_team_z = (team_rim - league_rim_off) / max(league_rim_off * 0.12, 1.0)
        rim_vol_signal = rim_allow_z * rim_team_z

        rim_soft = (opp_rim_fg_allowed - league_rim_fg_allowed) / max(8.0, 0.01)

        paint_w = float(np.clip(0.15 + 0.85 * (paint_profile_index + 1.0) / 2.0, 0.0, 1.0))
        vol_pts = 0.038 * rim_vol_signal * paint_w
        # Soft rim D (high opp FG% allowed at rim) helps finishers; paint_w keeps it player-relevant
        eff_pts = 0.022 * rim_soft * paint_w
        pts_mult = float(np.clip(1.0 + vol_pts + eff_pts, 0.965, 1.065))

        three_allow_z = (opp_3_allow - league_3_allow) / max(league_3_allow * 0.12, 1.0)
        three_team_z = (team_3 - league_3_off) / max(league_3_off * 0.12, 1.0)
        three_signal = three_allow_z * three_team_z
        perim_w = float(np.clip(0.15 + 0.85 * (perimeter_profile_index + 1.0) / 2.0, 0.0, 1.0))
        thr_mult = float(np.clip(1.0 + 0.045 * three_signal * perim_w, 0.94, 1.09))

        meta = {
            "shot_zones_active": True,
            "rim_vol_signal": round(rim_vol_signal, 4),
            "three_vol_signal": round(three_signal, 4),
            "rim_fg_allowed_vs_lg": round(rim_soft, 4),
        }
        return pts_mult, thr_mult, meta
    except Exception as e:
        meta["reason"] = str(e)[:120]
        return 1.0, 1.0, meta


def threes_opponent_multiplier(opp_row: pd.Series, perimeter_index: float) -> float:
    """Slight bump to predicted threes for shooters vs teams that play faster / weaker D."""
    if abs(perimeter_index) < 0.15:
        return 1.0
    try:
        pace = float(opp_row.get("PACE", 98))
        p_mult = 1.0 + 0.04 * max(0, perimeter_index) * ((pace - 98.0) / 98.0)
        return float(np.clip(p_mult, 0.97, 1.06))
    except Exception:
        return 1.0
