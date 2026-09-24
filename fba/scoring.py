"""H2H Points scoring engine — the backbone of the whole tool.

A *stat line* is a plain dict of canonical stat keys -> values (per game or per
season). A *scoring formula* maps each canonical stat key -> points awarded per
unit of that stat. `fantasy_points()` reduces a stat line to a single number.

The same formula drives the draft board and every in-season recommendation, so
this module deliberately knows nothing about ESPN, nba_api, or DARKO — it just
does arithmetic on dicts, which makes it trivially unit-testable.
"""
from __future__ import annotations

from typing import Mapping

# Canonical stat keys used everywhere in this project. Data adapters
# (espn_client, stats_nba, projections) translate their sources into these.
STAT_KEYS = (
    "PTS", "REB", "AST", "STL", "BLK", "TO",
    "FGM", "FGA", "FTM", "FTA", "3PM", "3PA",
)

# Fallback formula used only when the live league settings can't be read.
# ESPN "Points" leagues vary — the real values are pulled from league.settings
# by `scoring_from_league()`. This default is a common ESPN points setup and is
# clearly labelled so it never silently masquerades as the league's real rules.
DEFAULT_SCORING: dict[str, float] = {
    "PTS": 1.0,
    "REB": 1.0,
    "AST": 2.0,
    "STL": 4.0,
    "BLK": 4.0,
    "TO": -2.0,
    "FGM": 2.0,
    "FGA": -1.0,
    "FTM": 1.0,
    "FTA": -1.0,
    "3PM": 1.0,
}


def fantasy_points(stat_line: Mapping[str, float], scoring: Mapping[str, float]) -> float:
    """Sum stat values weighted by the league's points-per-stat formula.

    Missing keys count as zero, so partial stat lines are safe.
    """
    return round(
        sum(float(stat_line.get(key, 0.0)) * weight for key, weight in scoring.items()),
        2,
    )


# ESPN's internal stat ids -> our canonical keys. ESPN identifies scoring items
# by a numeric statId; this maps the ones relevant to a Points league.
# NOTE: verify/extend this against the real league.settings output on first
# connect (see scripts/diagnostics.py) — ESPN occasionally reuses ids.
ESPN_STAT_ID_TO_KEY: dict[int, str] = {
    0: "PTS",
    1: "BLK",
    2: "STL",
    3: "AST",
    6: "REB",
    11: "TO",
    13: "FGM",
    14: "FGA",
    15: "FTM",
    16: "FTA",
    17: "3PM",
    18: "3PA",
    38: "TD",  # triple-double bonus (per-game event; not derivable from averages)
    39: "QD",  # quadruple-double bonus (vanishingly rare)
}


def scoring_from_league(league) -> dict[str, float]:
    """Extract the league's real Points formula from an espn_api League object.

    espn_api exposes scoring items on `league.settings`. The exact attribute has
    shifted across library versions, so we probe a couple of shapes and fall
    back to DEFAULT_SCORING (with a warning) if nothing usable is found.
    """
    settings = getattr(league, "settings", None)
    raw = None
    for attr in ("scoring_format", "scoring_settings", "scoring"):
        raw = getattr(settings, attr, None)
        if raw:
            break

    if not raw:
        print(
            "[scoring] WARNING: could not read league scoring settings; "
            "falling back to DEFAULT_SCORING. Verify with diagnostics."
        )
        return dict(DEFAULT_SCORING)

    formula: dict[str, float] = {}
    for item in raw:
        # Items may be dicts like {'abbr': 'PTS', 'points': 1.0, 'id': 0} or
        # {'statId': 0, 'points': 1.0}. Handle both.
        abbr = item.get("abbr") if isinstance(item, dict) else None
        stat_id = item.get("id", item.get("statId")) if isinstance(item, dict) else None
        points = item.get("points", item.get("pointsOverrides")) if isinstance(item, dict) else None
        if points is None:
            continue
        key = abbr if abbr in STAT_KEYS else ESPN_STAT_ID_TO_KEY.get(stat_id)
        if key:
            formula[key] = float(points)

    if not formula:
        print(
            "[scoring] WARNING: league scoring settings present but unrecognized; "
            "falling back to DEFAULT_SCORING. Inspect raw settings in diagnostics."
        )
        return dict(DEFAULT_SCORING)
    return formula


def format_scoring(scoring: Mapping[str, float]) -> str:
    """Human-readable one-liner of a scoring formula, for reports/diagnostics."""
    return "  ".join(f"{k}:{v:+g}" for k, v in scoring.items())
