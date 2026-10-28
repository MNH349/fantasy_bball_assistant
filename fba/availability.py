"""Availability / durability model.

H2H Points is won by *accumulating* points across a season and every week, so a
player who suits up 76 games at 34 FP/G is worth more than one who plays 52 at
38 FP/G — consistent availability beats a high per-game rate you only get in
bursts. This module estimates games played and lets the board rank by projected
*season* value rather than per-game ceiling.

Durability is a **career** trait, not a one-season readout: a perennial 70-game
player who lost time to a fluke injury last year is still durable. So we weight
several seasons of games played (recent seasons more, but the whole history
counts) rather than judging on the last year alone.
"""
from __future__ import annotations

import statistics
from typing import Sequence

FULL_SEASON = 82
PRIOR_MEAN = 66.0     # typical rotation-player games in a season
GAMES_FLOOR = 40.0
GAMES_CEIL = 80.0     # even iron-men rarely clear this
AGE_WEAR_START = 34   # decline in availability tends to show here

# Recency weights, most-recent season first. Truncated/renormalized to however
# many seasons a player actually has.
SEASON_WEIGHTS = (0.30, 0.24, 0.20, 0.14, 0.12)


def _weighted_career_gp(gp_history: Sequence[float]) -> float:
    """Recency-weighted average games played across a player's recent seasons.

    `gp_history` is games played per season, most recent first.
    """
    pairs = [(gp, w) for gp, w in zip(gp_history, SEASON_WEIGHTS) if gp is not None]
    if not pairs:
        return PRIOR_MEAN
    total_w = sum(w for _, w in pairs)
    return sum(gp * w for gp, w in pairs) / total_w


def projected_games(gp_history: Sequence[float], age: float | None) -> float:
    """Estimate games played next season from career history + age.

    A single lost season barely moves a long durable record; a repeated pattern
    of missed games does. Lightly regressed toward the league mean and penalized
    past the wear-and-tear age. Bounded to a sane range.
    """
    if not gp_history:
        base = 62.0  # rookie / no history
    else:
        # The career MEDIAN ignores a single fluke-injury year; recency captures
        # a genuine recent trend. Leaning on the median keeps durable players
        # (one bad year in five) high while a repeated pattern still drags a
        # player down, because then the median itself is low.
        recency = _weighted_career_gp(gp_history)
        median = statistics.median(gp_history)
        base = 0.6 * median + 0.4 * recency
        base = 0.9 * base + 0.1 * PRIOR_MEAN  # mild regression

    if age and age >= AGE_WEAR_START:
        base -= (age - (AGE_WEAR_START - 1)) * 2.0

    return round(max(GAMES_FLOOR, min(GAMES_CEIL, base)), 1)


def season_value(fpts_per_game: float, games: float) -> float:
    """Projected total fantasy points for the season (the ranking metric)."""
    return round(fpts_per_game * games, 1)
