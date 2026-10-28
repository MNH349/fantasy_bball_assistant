"""2025-26 historical stats from nba_api — the draft-board baseline.

Pulls league-wide per-game player stats once and caches them to disk so we don't
hammer stats.nba.com. Everything is returned as canonical stat lines.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from config import DATA_CACHE_DIR

# nba_api season strings are "YYYY-YY". The 2025-26 season is "2025-26".
BASELINE_SEASON = "2025-26"

# Recent seasons (most recent first) used to judge career durability.
CAREER_SEASONS = ["2025-26", "2024-25", "2023-24", "2022-23", "2021-22"]

# nba_api LeagueDashPlayerStats column -> our canonical key.
NBA_COL_TO_KEY = {
    "PTS": "PTS", "REB": "REB", "AST": "AST", "STL": "STL", "BLK": "BLK",
    "TOV": "TO", "FGM": "FGM", "FGA": "FGA", "FTM": "FTM", "FTA": "FTA",
    "FG3M": "3PM", "FG3A": "3PA", "MIN": "MIN", "GP": "GP",
}


def _cache_path(season: str) -> Path:
    return DATA_CACHE_DIR / f"nba_player_stats_{season}.json"


def fetch_player_stats(season: str = BASELINE_SEASON, use_cache: bool = True) -> list[dict]:
    """Return a list of player records: name, age, and a canonical stat line.

    Per-game mode. Cached to disk; delete the cache file to force a refresh.
    """
    DATA_CACHE_DIR.mkdir(exist_ok=True)
    cache = _cache_path(season)
    if use_cache and cache.exists():
        return json.loads(cache.read_text())

    from nba_api.stats.endpoints import leaguedashplayerstats

    resp = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        per_mode_detailed="PerGame",
    )
    frames = resp.get_data_frames()
    df = frames[0]

    records = []
    for _, row in df.iterrows():
        line = {key: float(row[col]) for col, key in NBA_COL_TO_KEY.items() if col in row}
        records.append(
            {
                "player_id": int(row["PLAYER_ID"]),
                "name": row["PLAYER_NAME"],
                "age": float(row["AGE"]) if "AGE" in row else None,
                "gp": int(row["GP"]) if "GP" in row else 0,
                "line": line,
            }
        )

    cache.write_text(json.dumps(records, indent=2))
    # Be polite to the endpoint if a caller loops over seasons.
    time.sleep(0.6)
    return records


def games_history(seasons: list[str] = CAREER_SEASONS) -> dict[int, list[int]]:
    """Return {player_id: [games_played, ...]} across seasons, most recent first.

    Missing seasons (player not in the league yet) are simply absent, so the
    list length reflects how much career history exists. Cached per season.
    """
    history: dict[int, list[int]] = {}
    for season in seasons:
        for rec in fetch_player_stats(season=season):
            history.setdefault(rec["player_id"], []).append(rec.get("gp", 0))
    return history
