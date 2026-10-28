"""NBA schedule: how many games each team plays, and when.

Weekly H2H Points is partly a game-count game — a merely-good player with four
games in a scoring period can out-earn a better one with two. This module pulls
the regular-season schedule once a day and answers the two questions the engine
needs: games left this season (for ROS value) and games inside the current
scoring period (for next-week value). Team keys are NBA tricodes (e.g. "CLE").
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta

from config import DATA_CACHE_DIR

SEASON = "2026-27"
_CACHE = DATA_CACHE_DIR / f"schedule_{SEASON}.json"
_CACHE_TTL_HOURS = 20  # refetch roughly once a day


def _is_regular_season(game_id: str) -> bool:
    """Regular-season game ids have '2' as their third character."""
    return len(game_id) > 2 and game_id[2] == "2"


def _fetch_raw() -> dict:
    from nba_api.stats.endpoints import scheduleleaguev2

    return scheduleleaguev2.ScheduleLeagueV2(
        league_id="00", season=SEASON, timeout=45
    ).get_dict()


def team_game_dates(use_cache: bool = True) -> dict[str, list[str]]:
    """Map NBA tricode -> sorted ISO dates it plays a regular-season game.

    Each game contributes a date to both the home and away team. Cached to
    data_cache/ and refetched about once a day so the daily job stays cheap.
    """
    if use_cache and _CACHE.exists():
        age_h = (time.time() - _CACHE.stat().st_mtime) / 3600
        if age_h < _CACHE_TTL_HOURS:
            return json.loads(_CACHE.read_text())

    raw = _fetch_raw()
    dates: dict[str, list[str]] = {}
    for day in raw["leagueSchedule"]["gameDates"]:
        for g in day["games"]:
            if not _is_regular_season(g["gameId"]):
                continue
            iso = g["gameDateEst"][:10]
            for side in ("homeTeam", "awayTeam"):
                tri = g[side].get("teamTricode")
                if tri:
                    dates.setdefault(tri, []).append(iso)

    dates = {tri: sorted(ds) for tri, ds in dates.items()}
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(dates))
    return dates


def current_period(today: date | None = None) -> tuple[str, str]:
    """ISO (start, end) of the Monday–Sunday scoring period containing `today`.

    ESPN fantasy basketball scoring periods run Monday through Sunday by default.
    """
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def games_in_period(team_dates: dict[str, list[str]], team: str, start: str, end: str) -> int:
    """How many games `team` plays in the inclusive ISO date window [start, end]."""
    return sum(1 for d in team_dates.get(team, []) if start <= d <= end)


def games_remaining(team_dates: dict[str, list[str]], team: str, as_of: str | None = None) -> int:
    """How many regular-season games `team` has on/after `as_of` (default today)."""
    as_of = as_of or date.today().isoformat()
    return sum(1 for d in team_dates.get(team, []) if d >= as_of)
