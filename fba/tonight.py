"""Single-game projection: what a player should score on one specific night.

Season FP/G treats every night alike, but a role player's big nights are fairly
predictable. Three adjustments, in order of impact:
  1. Teammates out — an injured rotation player's minutes flow to healthy
     teammates at his position, in proportion to their own minutes. Scaled by
     how much he'd still been playing, so a long-term absence that's already in
     everyone's recent numbers isn't counted twice.
  2. Recent form — last-5-game FP/G blended into the season value.
  3. Opponent pace — a faster game means more possessions and more stats.
A player whose team doesn't play, or who is OUT, projects to zero. Today's
injury list is assumed to hold for the rest of the week; the daily refresh
corrects it.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from fba import scoring

FORM_GAMES = 5
MIN_FORM_GAMES = 3        # need this many recent games before form counts
FORM_WEIGHT = 0.3         # share of the projection taken from recent form
ROTATION_MINUTES = 15.0   # injured players below this free up no meaningful minutes
MAX_EXTRA_MINUTES = 8.0   # cap on minutes one player can inherit
DTD_FACTOR = 0.8          # day-to-day: discount for the chance he sits
INACTIVE = {"OUT", "SUSPENSION", "INJURY_RESERVE"}
POSITION_GROUP = {"PG": "guard", "SG": "guard", "SF": "wing", "PF": "big", "C": "big"}


def position_groups(positions: str | None) -> list[str]:
    """Position groups a player covers, primary first (from ESPN's slot list)."""
    groups = [POSITION_GROUP[p] for p in (positions or "").split(",") if p in POSITION_GROUP]
    return list(dict.fromkeys(groups))


def recent_form(logs: list[dict], formula: Mapping[str, float], n: int = FORM_GAMES) -> dict[int, dict]:
    """{nba_id: {fpg, games}} over each player's last `n` games."""
    by_player = defaultdict(list)
    for g in logs:
        by_player[g["player_id"]].append(g)
    form = {}
    for pid, games in by_player.items():
        last = sorted(games, key=lambda g: g["game_date"])[-n:]
        fpg = sum(scoring.fantasy_points(g["line"], formula) for g in last) / len(last)
        form[pid] = {"fpg": round(fpg, 2), "games": len(last)}
    return form


def _recent_share(logs: list[dict], n: int = FORM_GAMES) -> dict[int, float]:
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
            pots[(r.get("pro_team"), groups[0])] += r["minutes"] * share.get(r.get("nba_id"), 0.0)

    extra = defaultdict(float)
    for (team, group), freed in pots.items():
        takers = [r for r in rows if r.get("pro_team") == team and r.get("injury") not in INACTIVE
                  and group in position_groups(r.get("positions")) and (r.get("minutes") or 0) > 0]
        total = sum(r["minutes"] for r in takers)
        for r in takers:
            extra[r["name"]] += freed * r["minutes"] / total
    return {name: round(min(m, MAX_EXTRA_MINUTES), 1) for name, m in extra.items() if m > 0}


def project(row: dict, opponent: str | None, form: dict | None, extra_minutes: float,
            pace: Mapping[str, float]) -> float:
    """Projected fantasy points for one game (0 if no game or inactive)."""
    if opponent is None or row.get("injury") in INACTIVE:
        return 0.0
    base = row["value_fpg"]
    if form and form["games"] >= MIN_FORM_GAMES:
        base = (1 - FORM_WEIGHT) * base + FORM_WEIGHT * form["fpg"]
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
            logs: list[dict], formula: Mapping[str, float], pace: Mapping[str, float]) -> dict[str, dict[str, float]]:
    """{player name: {ISO date: projected FP}} for every row over `days`."""
    form = recent_form(logs, formula)
    extra = inherited_minutes(rows, logs)
    return {
        r["name"]: {
            d: project(r, team_games.get(r.get("pro_team"), {}).get(d), form.get(r.get("nba_id")),
                       extra.get(r["name"], 0.0), pace)
            for d in days
        }
        for r in rows
    }
