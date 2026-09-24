"""Draft board: rank players by projected 26-27 fantasy points.

Position-agnostic best-available board — works for any draft slot. Reuses the
league's Points scoring formula so the ranking reflects *your* league.

Input is a list of unified projection records (source-agnostic), each with:
    {"name", "age", "proj_line": {...}, "baseline_line": {...} | None}
The caller (scripts/draft_board.py) builds these from DARKO or, as a fallback,
from the age-curve baseline.
"""
from __future__ import annotations

from typing import Mapping

from fba import scoring

TIER_BOUNDS = [(1, 12, "T1 Elite"), (13, 30, "T2 Core"), (31, 60, "T3 Starter"),
               (61, 100, "T4 Rotation"), (101, 10_000, "T5 Deep")]


def _tier(rank: int) -> str:
    for lo, hi, label in TIER_BOUNDS:
        if lo <= rank <= hi:
            return label
    return "T5 Deep"


def build_board(
    records: list[dict],
    scoring_formula: Mapping[str, float],
    min_minutes: float = 12.0,
) -> list[dict]:
    """Rank projection records by projected per-game fantasy points.

    `min_minutes` drops players projected for fewer than that many minutes
    (deep-bench noise). Growth is projected minus last-season fantasy points,
    or None when no baseline is available (e.g. a rookie).
    """
    rows = []
    for rec in records:
        proj_line = rec["proj_line"]
        if proj_line.get("MIN", 0.0) < min_minutes:
            continue
        proj_fpts = scoring.fantasy_points(proj_line, scoring_formula)
        baseline = rec.get("baseline_line")
        baseline_fpts = scoring.fantasy_points(baseline, scoring_formula) if baseline else None
        rows.append(
            {
                "name": rec["name"],
                "age": rec.get("age"),
                "proj_fpts_pg": proj_fpts,
                "baseline_fpts_pg": baseline_fpts,
                "growth": None if baseline_fpts is None else round(proj_fpts - baseline_fpts, 2),
            }
        )

    rows.sort(key=lambda r: r["proj_fpts_pg"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
        row["tier"] = _tier(i)
    return rows
