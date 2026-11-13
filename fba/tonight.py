"""Single-game projection: what a player should score on one specific night.

Season FP/G treats every night alike, but a role player's big nights are fairly
predictable. Two adjustments on top of the blended FP/G:
  1. Teammates out — half of an injured rotation player's minutes flow to
     healthy teammates at his position, in proportion to their own minutes.
     Scaled by how much he'd still been playing, so a long-term absence that's
     already in everyone's recent numbers isn't counted twice.
  2. Opponent pace — a faster game means more possessions and more stats.
A player whose team doesn't play, or who is OUT, projects to zero. Today's
injury list is assumed to hold for the rest of the week; the daily refresh
corrects it.

Backtested on 1,540 player-games (10/28-11/11), each rebuilt from that morning's
data: half-strength injury minutes beat both none and full strength (full
over-projected by ~1.8 FP); pace helped slightly. A last-5-game form blend made
things worse at every weight, since the base FP/G already leans on recent games
(K=5), so it was dropped. Day-to-day players suited up 75% of the time.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping

RECENT_GAMES = 5          # window for judging how much an injured player had been playing
ROTATION_MINUTES = 15.0   # injured players below this free up no meaningful minutes
INJURY_MINUTES_SHARE = 0.5  # share of his minutes that go to same-position teammates
MAX_EXTRA_MINUTES = 8.0   # cap on minutes one player can inherit
DTD_FACTOR = 0.75         # day-to-day: share of the time they actually played
INACTIVE = {"OUT", "SUSPENSION", "INJURY_RESERVE"}
POSITION_GROUP = {"PG": "guard", "SG": "guard", "SF": "wing", "PF": "big", "C": "big"}


def position_groups(positions: str | None) -> list[str]:
    """Position groups a player covers, primary first (from ESPN's slot list)."""
    groups = [POSITION_GROUP[p] for p in (positions or "").split(",") if p in POSITION_GROUP]
    return list(dict.fromkeys(groups))


def _recent_share(logs: list[dict], n: int = RECENT_GAMES) -> dict[int, float]:
    """{nba_id: fraction of his team's last `n` games he appeared in}."""
    team_games = defaultdict(dict)
    for g in logs:
        team_games[g["team"]][g["game_id"]] = g["game_date"]
    last_games = {t: set(sorted(gs, key=gs.get)[-n:]) for t, gs in team_games.items()}
    appeared = defaultdict(set)
    for g in logs:
        if g["game_id"] in last_games.get(g["team"], ()):
            appeared[g["player_id"]].add(g["game_id"])
    return {pid: len(ids) / n for pid, ids in appeared.items()}


def inherited_minutes(rows: list[dict], logs: list[dict]) -> dict[str, float]:
    """{player name: extra minutes} from injured rotation teammates."""
    share = _recent_share(logs)
    pots = defaultdict(float)  # (team, group) -> minutes freed up
    for r in rows:
        groups = position_groups(r.get("positions"))
        if r.get("injury") in INACTIVE and (r.get("minutes") or 0) >= ROTATION_MINUTES and groups:
            pots[(r.get("pro_team"), groups[0])] += (r["minutes"] * share.get(r.get("nba_id"), 0.0)
                                                      * INJURY_MINUTES_SHARE)

    extra = defaultdict(float)
    for (team, group), freed in pots.items():
        takers = [r for r in rows if r.get("pro_team") == team and r.get("injury") not in INACTIVE
                  and group in position_groups(r.get("positions")) and (r.get("minutes") or 0) > 0]
        total = sum(r["minutes"] for r in takers)
        for r in takers:
            extra[r["name"]] += freed * r["minutes"] / total
    return {name: round(min(m, MAX_EXTRA_MINUTES), 1) for name, m in extra.items() if m > 0}


def project(row: dict, opponent: str | None, extra_minutes: float, pace: Mapping[str, float]) -> float:
    """Projected fantasy points for one game (0 if no game or inactive)."""
    if opponent is None or row.get("injury") in INACTIVE:
        return 0.0
    base = row["value_fpg"]
    minutes = row.get("minutes") or 0
    if minutes:
        base += base / minutes * extra_minutes
    own, opp = pace.get(row.get("pro_team")), pace.get(opponent)
    if own and opp:
        base *= (own + opp) / 2 / own
    if row.get("injury") == "DAY_TO_DAY":
        base *= DTD_FACTOR
    return round(base, 1)


def nightly(rows: list[dict], days: list[str], team_games: Mapping[str, Mapping[str, str]],
            logs: list[dict], pace: Mapping[str, float]) -> dict[str, dict[str, float]]:
    """{player name: {ISO date: projected FP}} for every row over `days`."""
    extra = inherited_minutes(rows, logs)
    return {
        r["name"]: {
            d: project(r, team_games.get(r.get("pro_team"), {}).get(d), extra.get(r["name"], 0.0), pace)
            for d in days
        }
        for r in rows
    }
