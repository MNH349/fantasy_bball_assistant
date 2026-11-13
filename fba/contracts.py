"""Who is on a standard NBA contract right now.

An 8-team league only ever rosters real rotation players, so anyone without a
standard deal — two-way, 10-day, G-League, or simply unsigned — is noise in every
list. NBA.com team rosters flag non-standard deals in SUPPLEMENTAL_STATUS; a
blank status means a standard contract. Players on no roster at all (unsigned,
overseas, G-League) never appear. Fetched from all 30 rosters about once a day.
"""
from __future__ import annotations

import json
import time

from config import DATA_CACHE_DIR

SEASON = "2026-27"
_CACHE = DATA_CACHE_DIR / f"standard_rosters_{SEASON}.json"
_CACHE_TTL_HOURS = 20


def _fetch() -> dict[int, dict]:
    from nba_api.stats.endpoints import commonteamroster
    from nba_api.stats.static import teams

    out: dict[int, dict] = {}
    for team in teams.get_teams():
        df = commonteamroster.CommonTeamRoster(
            team_id=team["id"], season=SEASON, timeout=45
        ).get_data_frames()[0]
        for _, row in df.iterrows():
            if not row["SUPPLEMENTAL_STATUS"]:  # blank = standard contract
                out[int(row["PLAYER_ID"])] = {"name": row["PLAYER"], "team": team["abbreviation"]}
        time.sleep(0.6)  # be polite: 30 requests in a row
    return out


def standard_roster(use_cache: bool = True) -> dict[int, dict]:
    """{nba_id: {name, team}} for every player on a standard NBA contract.

    `team` is the player's current NBA tricode, straight from the roster, so it
    also catches trades before they show up in box-score data.
    """
    if use_cache and _CACHE.exists():
        age_h = (time.time() - _CACHE.stat().st_mtime) / 3600
        if age_h < _CACHE_TTL_HOURS:
            return {int(k): v for k, v in json.loads(_CACHE.read_text()).items()}

    roster = _fetch()
    DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(roster))
    return roster
