"""Reliability-scaled blend of our DARKO-based value with ESPN's projection.

How much we trust our own model vs. ESPN's consensus scales with how much data
DARKO actually has for the player:

    veteran (2+ seasons)  -> 0.70 ours / 0.30 ESPN
    sophomore (1 season)  -> 0.30 ours / 0.70 ESPN   (one noisy rookie year)
    rookie (no history)   -> 0.00 ours / 1.00 ESPN   (ESPN-only)

Both inputs are in the same unit — projected total fantasy points for the season
under the league's scoring — so the blend is a direct weighted average.

Rookies additionally get an ADP downward cap (the market fades raw prospects, so
ESPN's optimism is pulled toward consensus, never boosted) and a flat bust-risk
discount.
"""
from __future__ import annotations

VET_WEIGHT = 0.70
SOPH_WEIGHT = 0.30
ROOKIE_DISCOUNT = 0.90  # flat haircut: rookies bust more than projections say


def darko_weight(seasons_of_history: int) -> float:
    """DARKO's share of the blend given how many NBA seasons it has seen."""
    if seasons_of_history <= 0:
        return 0.0
    if seasons_of_history == 1:
        return SOPH_WEIGHT
    return VET_WEIGHT


def blend_value(darko_value: float, espn_total: float, weight: float) -> float:
    """Weighted average of our season value and ESPN's projected total."""
    return round(weight * darko_value + (1.0 - weight) * espn_total, 1)


def rookie_value(espn_total: float, espn_rank: int | None, adp_rank: int | None) -> float:
    """ESPN projection, capped downward toward market ADP, then discounted.

    If the market (ADP) drafts a rookie later than ESPN ranks him, that's ESPN
    over-hyping a raw prospect — scale down by espn_rank / adp_rank. The cap
    never boosts (factor <= 1). Then apply the flat rookie discount.
    """
    factor = 1.0
    if espn_rank and adp_rank:
        factor = min(1.0, espn_rank / adp_rank)
    return round(espn_total * factor * ROOKIE_DISCOUNT, 1)
