"""Draft board assembly: per-player value, then final ranking.

The board mixes three player types with different data, so it's built in two
stages: `compute_darko_rows` turns DARKO+availability records into season values,
the script blends those with ESPN (and appends ESPN-only rookies), and
`finalize` ranks whatever it's handed by final value. Ranking is by projected
SEASON value (per-game × games), so availability counts.
"""
from __future__ import annotations

from typing import Mapping

from fba import availability, scoring

TIER_BOUNDS = [(1, 12, "T1 Elite"), (13, 30, "T2 Core"), (31, 60, "T3 Starter"),
               (61, 100, "T4 Rotation"), (101, 10_000, "T5 Deep")]


def _tier(rank: int) -> str:
    for lo, hi, label in TIER_BOUNDS:
        if lo <= rank <= hi:
            return label
    return "T5 Deep"


def compute_darko_rows(
    records: list[dict],
    scoring_formula: Mapping[str, float],
    min_minutes: float = 12.0,
) -> list[dict]:
    """Turn DARKO projection records into per-player season values.

    Produces per-game FP, projected games, the DARKO season value, and how many
    seasons of history DARKO has (which sets the blend weight downstream). Does
    not rank — the script blends with ESPN first.
    """
    rows = []
    for rec in records:
        proj_line = rec["proj_line"]
        if proj_line.get("MIN", 0.0) < min_minutes:
            continue
        fpg = scoring.fantasy_points(proj_line, scoring_formula)
        games = availability.projected_games(rec.get("gp_history") or [], rec.get("age"))
        rows.append(
            {
                "name": rec["name"],
                "team": rec.get("team"),
                "age": rec.get("age"),
                "darko_fpg": fpg,
                "games": games,
                "darko_value": availability.season_value(fpg, games),
                "seasons": len(rec.get("gp_history") or []),
            }
        )
    return rows


def finalize(rows: list[dict]) -> list[dict]:
    """Sort by final `value` (projected season total) and assign rank + tier."""
    rows.sort(key=lambda r: r["value"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
        row["tier"] = _tier(i)
    return rows
