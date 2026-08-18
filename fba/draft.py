"""Draft board: rank players by projected 26-27 fantasy points.

Position-agnostic best-available board — works for any draft slot. Reuses the
league's Points scoring formula so the ranking reflects *your* league, not a
generic one.
"""
from __future__ import annotations

from typing import Mapping

from fba import projections, scoring

# Tier cutoffs by overall rank. Simple and readable; refine once we see the
# real distribution of projected fantasy points.
TIER_BOUNDS = [(1, 12, "T1 Elite"), (13, 30, "T2 Core"), (31, 60, "T3 Starter"),
               (61, 100, "T4 Rotation"), (101, 10_000, "T5 Deep")]


def _tier(rank: int) -> str:
    for lo, hi, label in TIER_BOUNDS:
        if lo <= rank <= hi:
            return label
    return "T5 Deep"


def build_board(
    player_records: list[dict],
    scoring_formula: Mapping[str, float],
    darko: Mapping[str, dict] | None = None,
    min_games: int = 20,
) -> list[dict]:
    """Return a ranked draft board.

    Each row: rank, name, age, positions(if available), projected fantasy
    pts/game, 25-26 baseline fantasy pts/game, growth delta, tier.

    `min_games` filters out tiny-sample players from the 25-26 baseline.
    """
    rows = []
    for rec in player_records:
        if rec.get("gp", 0) < min_games:
            continue
        baseline_line = rec["line"]
        proj_line = projections.projected_stat_line(rec, darko=darko)
        baseline_fpts = scoring.fantasy_points(baseline_line, scoring_formula)
        proj_fpts = scoring.fantasy_points(proj_line, scoring_formula)
        rows.append(
            {
                "name": rec["name"],
                "age": rec.get("age"),
                "proj_fpts_pg": proj_fpts,
                "baseline_fpts_pg": baseline_fpts,
                "growth": round(proj_fpts - baseline_fpts, 2),
            }
        )

    rows.sort(key=lambda r: r["proj_fpts_pg"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
        row["tier"] = _tier(i)
    return rows
