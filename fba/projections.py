"""Forward-looking projections and the growth model.

Phase 2 (draft): project each player's 26-27 per-game stat line.
  - Preferred source: DARKO preseason projections (best free projector).
  - Fallback: 25-26 baseline adjusted by a simple age curve, so the draft board
    still runs if DARKO's 26-27 preseason board isn't posted yet.

Phase 3 (in-season): DARKO rest-of-season + next-game projections, weighted by
games-per-week. Stubbed below.
"""
from __future__ import annotations

from typing import Mapping

# --- Age curve -------------------------------------------------------------
# Rough, transparent heuristic: production peaks in the mid-20s, young players
# trend up, older players decline. Deliberately mild — it nudges, not dominates.
PEAK_AGE = 27.0


def age_multiplier(age: float | None) -> float:
    if age is None:
        return 1.0
    if age <= PEAK_AGE:
        # Up to +8% for the youngest rotation players approaching their peak.
        return 1.0 + min(0.08, (PEAK_AGE - age) * 0.015)
    # Decline after the peak, floored so veterans don't crater unrealistically.
    return max(0.80, 1.0 - (age - PEAK_AGE) * 0.02)


def project_from_baseline(baseline_line: Mapping[str, float], age: float | None) -> dict[str, float]:
    """Naive projection: scale every counting stat by the age multiplier."""
    mult = age_multiplier(age)
    return {k: round(v * mult, 3) for k, v in baseline_line.items()}


def projected_stat_line(player_record: dict, darko: Mapping[str, dict] | None = None) -> dict[str, float]:
    """Return the projected 26-27 per-game line for one player record.

    `player_record` is a row from stats_nba.fetch_player_stats().
    `darko` (optional) maps player name -> projected line; when present and the
    player is found, it takes precedence over the age-curve baseline.
    """
    if darko:
        hit = darko.get(player_record["name"])
        if hit:
            return dict(hit)
    return project_from_baseline(player_record["line"], player_record.get("age"))


def load_darko_preseason(path_or_url: str | None = None) -> dict[str, dict]:
    """Load DARKO preseason projections into {name: canonical_line}.

    TODO (build-time): wire the real DARKO source. DARKO publishes a Google
    Sheet; export it as CSV and map its columns to our canonical keys. DARKO
    omits STL and FG/FT makes — synthesize those from the player's 25-26
    per-minute rates x projected minutes before returning.

    Until that's wired, returns {} so the draft board falls back to the
    age-curve baseline (which is fully functional on its own).
    """
    return {}


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
