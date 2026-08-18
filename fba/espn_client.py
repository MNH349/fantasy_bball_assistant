"""Thin wrapper around the espn_api basketball League.

Isolates every ESPN-specific detail (auth, object shapes) behind a few helpers
so the rest of the codebase deals in plain dicts.
"""
from __future__ import annotations

from typing import Any

from config import Config
from fba import scoring


def get_league(cfg: Config):
    """Return a connected espn_api basketball League for the configured season."""
    from espn_api.basketball import League  # imported lazily so tests don't need the dep

    return League(
        league_id=cfg.league_id,
        year=cfg.season,
        espn_s2=cfg.espn_s2,
        swid=cfg.swid,
    )


def player_stat_line(player) -> dict[str, float]:
    """Extract a per-game canonical stat line from an espn_api Player.

    espn_api stores stats in `player.stats`, keyed by scoring period, each with
    'avg'/'total' breakdown dicts. Structure varies by library version, so we
    probe defensively and return what we can (missing keys -> handled downstream).
    NOTE: confirm the exact shape against live data in diagnostics before trusting.
    """
    stats: dict[str, Any] = getattr(player, "stats", {}) or {}
    # Prefer the season aggregate (period '0' or the '00YYYY' total key).
    season_block = None
    for key, block in stats.items():
        if str(key) in ("0", "0000") or "avg" in (block or {}):
            season_block = block
            break
    if season_block is None and stats:
        season_block = next(iter(stats.values()))

    avg = (season_block or {}).get("avg", {}) if season_block else {}
    # ESPN uses its own abbreviations; map the ones we care about.
    src_to_key = {
        "PTS": "PTS", "REB": "REB", "AST": "AST", "STL": "STL", "BLK": "BLK",
        "TO": "TO", "FGM": "FGM", "FGA": "FGA", "FTM": "FTM", "FTA": "FTA",
        "3PTM": "3PM", "3PM": "3PM", "3PTA": "3PA", "3PA": "3PA",
    }
    return {dst: float(avg.get(src, 0.0)) for src, dst in src_to_key.items() if src in avg}


def my_team(league, cfg: Config):
    """Best-effort lookup of the user's own team (by SWID owner match)."""
    for team in league.teams:
        owners = getattr(team, "owners", []) or []
        owner_ids = [o.get("id") if isinstance(o, dict) else o for o in owners]
        if cfg.swid and cfg.swid in owner_ids:
            return team
    return None


def league_snapshot(league, cfg: Config, scoring_formula: dict[str, float]) -> dict:
    """Compact, print-friendly summary of the league's current state."""
    teams = [
        {"name": t.team_name, "wins": t.wins, "losses": t.losses}
        for t in league.teams
    ]
    mine = my_team(league, cfg)
    roster = []
    if mine is not None:
        for p in mine.roster:
            line = player_stat_line(p)
            roster.append(
                {
                    "name": p.name,
                    "positions": getattr(p, "eligibleSlots", None) or getattr(p, "position", ""),
                    "proTeam": getattr(p, "proTeam", ""),
                    "fpts_pg": scoring.fantasy_points(line, scoring_formula),
                }
            )
        roster.sort(key=lambda r: r["fpts_pg"], reverse=True)
    return {"teams": teams, "my_team": getattr(mine, "team_name", None), "roster": roster}


def free_agent_pool(league, scoring_formula: dict[str, float], size: int = 50) -> list[dict]:
    """Ranked free-agent pool by per-game fantasy points."""
    fas = league.free_agents(size=size)
    rows = []
    for p in fas:
        line = player_stat_line(p)
        rows.append(
            {
                "name": p.name,
                "positions": getattr(p, "eligibleSlots", None) or getattr(p, "position", ""),
                "proTeam": getattr(p, "proTeam", ""),
                "fpts_pg": scoring.fantasy_points(line, scoring_formula),
            }
        )
    rows.sort(key=lambda r: r["fpts_pg"], reverse=True)
    return rows
