"""In-season recommendations — Phase 4 (stubbed).

Given the league state (rosters + free agents) and projections, produce:
  - pickups:  free agents whose projected fantasy pts beat weak rostered players
  - drops:    rostered players underperforming vs. the free-agent pool
  - trades:   buy-low (recent slump, projection says rebound) / sell-high targets

All three reduce to comparing projected fantasy points over a window, using the
same scoring formula as the draft board.
"""
from __future__ import annotations


def waiver_pickups(*args, **kwargs):
    raise NotImplementedError(
        "Phase 4: rank free agents by projected fantasy pts (short-term = next "
        "week weighted by games; long-term = rest-of-season) vs. current roster."
    )


def drop_candidates(*args, **kwargs):
    raise NotImplementedError(
        "Phase 4: flag rostered players projected below the best available "
        "free agents at their position."
    )


def trade_targets(*args, **kwargs):
    raise NotImplementedError(
        "Phase 4: buy-low (baseline > recent form, projection rebounds) and "
        "sell-high (recent form > projection) candidates across other rosters."
    )
