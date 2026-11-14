"""
Teammate absence adjustments
============================
When teammates are OUT, remaining players split extra minutes and box-score load. We **do not**
have true on/off or lineup-stint data in this project: that requires play-by-play / lineup endpoints
(Cleaning the Glass, Second Spectrum, or heavy `nba_api` league dash lineups), extra storage, and
join logic we never shipped — see ``lineup_effects_analyzer`` stub. Here we use injury status +
**season per-game rates** to approximate *who* was lost (PTS/AST/REB/MIN) and allocate a **fraction**
of that loss across **active** teammates by their **existing shares** of team scoring / playmaking /
glass (multiple players absorb the vacuum differently per stat).

This is still a heuristic, not a replacement for on/off.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

# Caps on mild multipliers (per stat)
_CAP_PTS = 0.065
_CAP_REB = 0.045
_CAP_AST = 0.055
_CAP_MIN = 0.045

# Fraction of “lost” box-score we assume stays on the team (rest = defense, pace, opponent)
_RETAIN_PTS = 0.28
_RETAIN_AST = 0.36
_RETAIN_REB = 0.30
_RETAIN_MIN = 0.40

# Denominators normalize “typical” star loss so multipliers stay bounded
_NORM_LOST_PTS = 17.0
_NORM_LOST_AST = 6.0
_NORM_LOST_REB = 8.0
_NORM_LOST_MIN = 30.0

# Fallback when we cannot compute shares (missing roster row): count-based vacuum
_MILD_PTS_STAR = 0.017
_MILD_PTS_OTHER = 0.006
_MILD_REB_STAR = 0.011
_MILD_REB_OTHER = 0.004
_MILD_AST_STAR = 0.014
_MILD_AST_OTHER = 0.005
_MILD_MIN_STAR = 0.010
_MILD_MIN_OTHER = 0.003

_EMPHASIS_SCALE = 2.1
_EMPH_CAP_PTS = 0.12


def _normalize_name(name: str) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    s = str(name).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^\w\s]", "", s)
    s = s.replace(" iii", "").replace(" ii", "").replace(" jr", "").replace(" sr", "")
    return " ".join(s.split())


def _status_is_out(status: Optional[str]) -> bool:
    if status is None or (isinstance(status, float) and pd.isna(status)):
        return False
    t = str(status).lower()
    if "out" in t or "doubtful" in t:
        return True
    return False


def _team_top_scorers(
    roster: pd.DataFrame, team: str, min_min: float = 10.0, n: int = 2
) -> Set[str]:
    sub = roster[(roster["TEAM_ABBREVIATION"] == team) & (roster["MIN"] >= min_min)].copy()
    if sub.empty:
        return set()
    sub = sub.sort_values("PTS", ascending=False).head(n)
    return {_normalize_name(x) for x in sub["PLAYER_NAME"].tolist()}


def _top_n_names_by_pts(roster: pd.DataFrame, team: str, n: int = 4, min_min: float = 10.0) -> Set[str]:
    sub = roster[(roster["TEAM_ABBREVIATION"] == team) & (roster["MIN"] >= min_min)]
    if sub.empty:
        return set()
    return set(sub.nlargest(n, "PTS")["PLAYER_NAME"].tolist())


def build_slate_teammate_absence_index(
    slate_teams: Set[str],
    roster_df: pd.DataFrame,
) -> Dict[str, Dict]:
    """
    Per team:
      - outs, star_outs (top-2 PPG)
      - key_rotation_outs: star OR top-4 PPG (MIN>=10) OR MIN>=22 — “starter / key rotation”
      - lost_pts / lost_ast / lost_reb / lost_minutes: weighted sum for what left the floor
    """
    empty: Dict[str, Dict] = {t: _empty_team_index() for t in slate_teams}
    need = {"PLAYER_NAME", "TEAM_ABBREVIATION", "PTS", "MIN", "AST", "REB"}
    if not need.issubset(roster_df.columns):
        return empty

    slate_roster = roster_df[roster_df["TEAM_ABBREVIATION"].isin(slate_teams)].copy()
    if slate_roster.empty:
        return empty

    names = slate_roster["PLAYER_NAME"].drop_duplicates().tolist()
    try:
        from src.services.injury_tracker import InjuryTracker

        tracker = InjuryTracker()
        st = tracker.get_multiple_statuses(names, use_cache=True)
    except Exception:
        return empty

    if st is None or len(st) == 0:
        return empty

    out: Dict[str, Dict] = {t: _empty_team_index() for t in slate_teams}

    st = st.rename(columns={"player": "PLAYER_NAME"})
    m = slate_roster[["PLAYER_NAME", "TEAM_ABBREVIATION", "PTS", "MIN", "AST", "REB"]].drop_duplicates(
        subset=["PLAYER_NAME"], keep="first"
    ).merge(st, on="PLAYER_NAME", how="left")
    m["is_out"] = m["status"].apply(_status_is_out)

    for team in slate_teams:
        top2 = _team_top_scorers(roster_df, team)
        top4_names = _top_n_names_by_pts(roster_df, team, n=4, min_min=10.0)
        team_roster = roster_df[roster_df["TEAM_ABBREVIATION"] == team]
        team_out = m[(m["TEAM_ABBREVIATION"] == team) & m["is_out"]]
        outs_raw = team_out["PLAYER_NAME"].dropna().unique().tolist()
        out[team]["outs"] = list(outs_raw)

        star_names: List[str] = []
        key_rotation: List[str] = []
        for nm in outs_raw:
            rows = team_roster[team_roster["PLAYER_NAME"] == nm]
            if rows.empty:
                continue
            r0 = rows.iloc[0]
            pts, ast, reb, mn = float(r0["PTS"]), float(r0["AST"]), float(r0["REB"]), float(r0["MIN"])
            is_star = _normalize_name(nm) in top2
            in_top4 = nm in top4_names
            heavy_min = mn >= 22.0
            is_key = is_star or in_top4 or heavy_min
            if is_star:
                star_names.append(nm)
            if is_key:
                key_rotation.append(nm)
                w = 1.0
            else:
                w = 0.42
            out[team]["lost_pts"] += pts * w
            out[team]["lost_ast"] += ast * w
            out[team]["lost_reb"] += reb * w
            out[team]["lost_minutes"] += mn * w

        out[team]["star_outs"] = star_names
        out[team]["key_rotation_outs"] = key_rotation

    return out


def _empty_team_index() -> Dict:
    return {
        "outs": [],
        "star_outs": [],
        "key_rotation_outs": [],
        "lost_pts": 0.0,
        "lost_ast": 0.0,
        "lost_reb": 0.0,
        "lost_minutes": 0.0,
    }


def _vacuum_mults_count(star_n: int, other_n: int) -> Tuple[float, float, float, float, float, float, float, float]:
    """Fallback: mild_pts, mild_reb, mild_ast, mild_min, emph_pts, emph_reb, emph_ast, emph_min."""
    mild_pts = 1.0 + min(_CAP_PTS, _MILD_PTS_STAR * star_n + _MILD_PTS_OTHER * other_n)
    mild_reb = 1.0 + min(_CAP_REB, _MILD_REB_STAR * star_n + _MILD_REB_OTHER * other_n)
    mild_ast = 1.0 + min(_CAP_AST, _MILD_AST_STAR * star_n + _MILD_AST_OTHER * other_n)
    mild_min = 1.0 + min(_CAP_MIN, _MILD_MIN_STAR * star_n + _MILD_MIN_OTHER * other_n)

    def _emph(mild: float, cap: float) -> float:
        d = mild - 1.0
        return 1.0 + min(cap, d * _EMPHASIS_SCALE)

    emph_pts = _emph(mild_pts, _EMPH_CAP_PTS)
    emph_reb = _emph(mild_reb, _CAP_REB * 1.8)
    emph_ast = _emph(mild_ast, _CAP_AST * 1.8)
    emph_min = _emph(mild_min, _CAP_MIN * 1.8)
    return mild_pts, mild_reb, mild_ast, mild_min, emph_pts, emph_reb, emph_ast, emph_min


def _redistribution_mults(
    team: str,
    n_self: str,
    index_team: Dict,
    roster_df: pd.DataFrame,
    star_n: int,
    other_n: int,
) -> Tuple[float, float, float, float, float, float, float, float]:
    """
    Allocate lost PTS/AST/REB/MIN across active teammates by season share on the team.
    Falls back to count-based _vacuum_mults_count if roster lookup fails.
    """
    outs = index_team.get("outs") or []
    outs_norm = {_normalize_name(x) for x in outs}

    active = roster_df[
        (roster_df["TEAM_ABBREVIATION"] == team)
        & ~roster_df["PLAYER_NAME"].apply(lambda x: _normalize_name(x) in outs_norm)
    ]
    if active.empty:
        return _vacuum_mults_count(star_n, other_n)

    pr = active[active["PLAYER_NAME"].apply(lambda x: _normalize_name(x) == n_self)]
    if pr.empty:
        return _vacuum_mults_count(star_n, other_n)

    pj = pr.iloc[0]
    s_pts = float(active["PTS"].sum())
    s_ast = float(active["AST"].sum())
    s_reb = float(active["REB"].sum())
    s_min = float(active["MIN"].sum())

    lost_pts = float(index_team.get("lost_pts") or 0.0)
    lost_ast = float(index_team.get("lost_ast") or 0.0)
    lost_reb = float(index_team.get("lost_reb") or 0.0)
    lost_min = float(index_team.get("lost_minutes") or 0.0)

    if lost_pts + lost_ast + lost_reb < 0.25 and (star_n + other_n) > 0:
        return _vacuum_mults_count(star_n, other_n)

    share_p = float(pj["PTS"]) / max(s_pts, 22.0)
    share_a = float(pj["AST"]) / max(s_ast, 8.0)
    share_r = float(pj["REB"]) / max(s_reb, 18.0)
    share_m = float(pj["MIN"]) / max(s_min, 100.0)

    d_pts = min(
        _CAP_PTS,
        _RETAIN_PTS * lost_pts * share_p / _NORM_LOST_PTS,
    )
    d_ast = min(
        _CAP_AST,
        _RETAIN_AST * lost_ast * share_a / _NORM_LOST_AST,
    )
    d_reb = min(
        _CAP_REB,
        _RETAIN_REB * lost_reb * share_r / _NORM_LOST_REB,
    )
    d_min = min(
        _CAP_MIN,
        _RETAIN_MIN * lost_min * share_m / _NORM_LOST_MIN,
    )

    mild_pts, mild_reb, mild_ast, mild_min = (
        1.0 + d_pts,
        1.0 + d_reb,
        1.0 + d_ast,
        1.0 + d_min,
    )

    def _emph(mild: float, cap: float) -> float:
        d = mild - 1.0
        return 1.0 + min(cap, d * _EMPHASIS_SCALE)

    emph_pts = _emph(mild_pts, _EMPH_CAP_PTS)
    emph_reb = _emph(mild_reb, _CAP_REB * 1.8)
    emph_ast = _emph(mild_ast, _CAP_AST * 1.8)
    emph_min = _emph(mild_min, _CAP_MIN * 1.8)
    return mild_pts, mild_reb, mild_ast, mild_min, emph_pts, emph_reb, emph_ast, emph_min


def _summary_labels(
    star_outs: List[str],
    key_rotation: List[str],
    other_outs: List[str],
    max_len: int = 140,
) -> str:
    parts = []
    seen = set()
    for p in star_outs[:4]:
        if p not in seen:
            parts.append(f"{p} (star OUT)")
            seen.add(p)
    for p in key_rotation[:5]:
        if p in seen:
            continue
        if _normalize_name(p) not in {_normalize_name(s) for s in star_outs}:
            parts.append(f"{p} (rotation OUT)")
            seen.add(p)
    for p in other_outs[:2]:
        if p not in seen:
            parts.append(f"{p} (OUT)")
            seen.add(p)
    s = "; ".join(parts)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def apply_teammate_absence_to_matchup_df(
    df: pd.DataFrame,
    index: Dict[str, Dict],
    *,
    roster_df: Optional[pd.DataFrame] = None,
    enabled: bool = True,
) -> pd.DataFrame:
    """
    Apply share-based vacuum to predictions; add emphasis columns and labels.
    """
    if df is None or len(df) == 0:
        return df
    if not enabled:
        return df

    df = df.copy()
    if "player_name" not in df.columns or "team" not in df.columns:
        return df

    keys_out: List[str] = []
    keys_mult: List[float] = []
    keys_star_n: List[int] = []
    emph_pts: List[float] = []
    emph_reb: List[float] = []
    emph_ast: List[float] = []

    for idx, row in df.iterrows():
        team = row.get("team")
        pname = row.get("player_name")
        if team not in index:
            keys_out.append("")
            keys_mult.append(1.0)
            keys_star_n.append(0)
            emph_pts.append(float(row.get("predicted_points", 0) or 0))
            emph_reb.append(float(row.get("predicted_rebounds", 0) or 0))
            emph_ast.append(float(row.get("predicted_assists", 0) or 0))
            continue

        it = index[team]
        outs = it.get("outs") or []
        star_outs = it.get("star_outs") or []
        key_rot = it.get("key_rotation_outs") or []
        n_self = _normalize_name(pname)
        outs_set = {_normalize_name(x) for x in outs}
        self_listed_out = n_self in outs_set

        star_ex = [x for x in star_outs if _normalize_name(x) != n_self]
        outs_ex = [x for x in outs if _normalize_name(x) != n_self]
        topn = {_normalize_name(x) for x in star_outs}
        other_ex = [x for x in outs_ex if _normalize_name(x) not in topn]

        star_n = len(star_ex)
        other_n = len(other_ex)

        if self_listed_out or (star_n == 0 and other_n == 0):
            kr_set = set(key_rot)
            bench_outs = [x for x in outs if x not in kr_set]
            keys_out.append(_summary_labels(star_outs, key_rot, bench_outs))
            keys_mult.append(1.0)
            keys_star_n.append(len([x for x in star_outs if _normalize_name(x) != n_self]))
            emph_pts.append(float(row.get("predicted_points", 0) or 0))
            emph_reb.append(float(row.get("predicted_rebounds", 0) or 0))
            emph_ast.append(float(row.get("predicted_assists", 0) or 0))
            continue

        if roster_df is not None and len(roster_df) > 0:
            mpts, mreb, mast, mmin, epts, ereb, east, _ = _redistribution_mults(
                team, n_self, it, roster_df, star_n, other_n
            )
        else:
            mpts, mreb, mast, mmin, epts, ereb, east, _ = _vacuum_mults_count(star_n, other_n)

        keys_out.append(_summary_labels(star_ex, [k for k in key_rot if _normalize_name(k) != n_self], other_ex))
        keys_mult.append(round(mpts, 4))
        keys_star_n.append(star_n)

        base_pts = float(row.get("predicted_points", 0) or 0)
        base_reb = float(row.get("predicted_rebounds", 0) or 0)
        base_ast = float(row.get("predicted_assists", 0) or 0)

        if "predicted_points" in df.columns:
            df.at[idx, "predicted_points"] = base_pts * mpts
        if "predicted_rebounds" in df.columns:
            df.at[idx, "predicted_rebounds"] = base_reb * mreb
        if "predicted_assists" in df.columns:
            df.at[idx, "predicted_assists"] = base_ast * mast
        if "minutes" in df.columns:
            df.at[idx, "minutes"] = float(row["minutes"]) * mmin

        if "predicted_threes" in df.columns:
            df.at[idx, "predicted_threes"] = float(row.get("predicted_threes") or 0) * (1.0 + (mpts - 1.0) * 0.85)
        if "predicted_turnovers" in df.columns:
            df.at[idx, "predicted_turnovers"] = float(row.get("predicted_turnovers") or 0) * (
                1.0 + (mpts - 1.0) * 0.5 + (mast - 1.0) * 0.35
            )

        emph_pts.append(base_pts * epts)
        emph_reb.append(base_reb * ereb)
        emph_ast.append(base_ast * east)

    df["key_teammates_out"] = keys_out
    df["teammate_absence_pts_mult"] = keys_mult
    df["star_teammates_out_count"] = keys_star_n
    df["pred_points_absence_emphasis"] = emph_pts
    df["pred_rebounds_absence_emphasis"] = emph_reb
    df["pred_assists_absence_emphasis"] = emph_ast

    return df
