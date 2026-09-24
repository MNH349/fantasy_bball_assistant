"""Forward-looking projections and the growth model.

Phase 2 (draft): project each player's 26-27 per-game stat line.
  - Preferred source: DARKO's published talent sheet (per-100 rates + usage +
    efficiency + minutes). Its rate stats capture role/usage changes — a player
    who loses touches to a new teammate projects down automatically.
  - Minutes: DARKO's talent-sheet minutes are conservative (talent-regressed),
    which distorts per-game rankings, so we drive minutes from last season's
    actuals (nba_api) when available and fall back to DARKO's minutes otherwise.
  - Fallback: if DARKO can't be reached, a 25-26 baseline nudged by an age curve,
    so the draft board still runs.

Phase 3 (in-season): DARKO rest-of-season + next-game projections. Stubbed below.
"""
from __future__ import annotations

import csv
import io
from typing import Mapping

import requests

# DARKO's public workbook. The "current talent" tab (this gid) holds per-100
# box-score rates, usage, shooting %s, and minutes for every player.
DARKO_SHEET_ID = "1mhwOLqPu2F9026EQiVxFPIN1t9RGafGpl-dokaIsm9c"
DARKO_TALENT_GID = "284274620"
DARKO_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{DARKO_SHEET_ID}"
    f"/gviz/tq?tqx=out:csv&gid={DARKO_TALENT_GID}"
)


# --- Age curve (fallback path only) ---------------------------------------
PEAK_AGE = 27.0


def age_multiplier(age: float | None) -> float:
    if age is None:
        return 1.0
    if age <= PEAK_AGE:
        return 1.0 + min(0.08, (PEAK_AGE - age) * 0.015)
    return max(0.80, 1.0 - (age - PEAK_AGE) * 0.02)


def project_from_baseline(baseline_line: Mapping[str, float], age: float | None) -> dict[str, float]:
    """Naive fallback projection: scale each counting stat by the age curve."""
    mult = age_multiplier(age)
    return {k: round(v * mult, 3) for k, v in baseline_line.items()}


# --- DARKO ingest ----------------------------------------------------------
def _f(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def darko_line(rec: Mapping[str, float], minutes: float) -> dict[str, float]:
    """Build a canonical per-game stat line from DARKO per-100 rates + minutes.

    Possessions in `minutes` of play ≈ pace * minutes / 48 (pace is possessions
    per 48). Per-game counting stat = per-100 rate * possessions / 100. Makes are
    attempts * the matching shooting percentage.
    """
    poss_per_100 = rec["pace"] * minutes / 48.0 / 100.0
    fga = rec["fga_100"] * poss_per_100
    fta = rec["fta_100"] * poss_per_100
    fg3a = rec["fg3a_100"] * poss_per_100
    return {
        "MIN": round(minutes, 1),
        "PTS": round(rec["pts_100"] * poss_per_100, 2),
        "REB": round((rec["orb_100"] + rec["drb_100"]) * poss_per_100, 2),
        "AST": round(rec["ast_100"] * poss_per_100, 2),
        "STL": round(rec["stl_100"] * poss_per_100, 2),
        "BLK": round(rec["blk_100"] * poss_per_100, 2),
        "TO": round(rec["tov_100"] * poss_per_100, 2),
        "FGM": round(fga * rec["fg_pct"], 2),
        "FGA": round(fga, 2),
        "FTM": round(fta * rec["ft_pct"], 2),
        "FTA": round(fta, 2),
        "3PM": round(fg3a * rec["fg3_pct"], 2),
        "3PA": round(fg3a, 2),
    }


def load_darko_talent(url: str = DARKO_CSV_URL, timeout: int = 30) -> dict[int, dict]:
    """Fetch DARKO's talent sheet, keyed by nba_id.

    Each value: {name, age, position, darko_minutes, rates{...}} where `rates`
    holds pace + the per-100 and shooting fields `darko_line()` needs. Join on
    nba_id (stable across name-spelling differences). Returns {} on any failure
    so the draft board falls back to the age-curve baseline.
    """
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:  # noqa: BLE001
        print(f"[darko] fetch failed ({exc}); falling back to age-curve baseline.")
        return {}

    reader = csv.DictReader(io.StringIO(resp.text))
    rate_fields = (
        "pace", "usg_pct", "pts_100", "orb_100", "drb_100", "ast_100",
        "blk_100", "stl_100", "tov_100", "fta_100", "fga_100", "fg3a_100",
        "fg_pct", "ft_pct", "fg3_pct",
    )
    out: dict[int, dict] = {}
    for row in reader:
        nba_id = int(_f(row.get("nba_id", 0)))
        if not nba_id:
            continue
        out[nba_id] = {
            "name": row.get("player_name", "").strip(),
            "age": _f(row.get("age")),
            "position": row.get("position", ""),
            "darko_minutes": _f(row.get("minutes")),
            "rates": {k: _f(row.get(k)) for k in rate_fields},
        }
    return out


# Back-compat alias used by the draft-board script.
def load_darko_preseason(url: str = DARKO_CSV_URL) -> dict[int, dict]:
    return load_darko_talent(url)


# --- Phase 3: in-season (stubbed) -----------------------------------------
def rest_of_season_projection(player_record: dict) -> dict[str, float]:
    raise NotImplementedError(
        "Phase 3: ingest DARKO rest-of-season projections and blend with recent "
        "nba_api game logs."
    )


def next_week_projection(player_record: dict, games_next_week: int) -> dict[str, float]:
    raise NotImplementedError(
        "Phase 3: DARKO next-game projection x games-per-week from the NBA schedule."
    )
