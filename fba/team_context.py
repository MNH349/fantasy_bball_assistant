"""Team-context adjustment: fade players on crowded rosters.

DARKO projects a player's *individual* talent (per-100 rates), and we drive
minutes from last season — neither knows the player's new teammates. So four
stars traded onto one team all keep their old usage and minutes, which is
impossible. This layer corrects that using two conservation facts:

  * Minutes: a team has 5 * 48 = 240 player-minutes per game to hand out.
  * Usage:  the five on-court players' usage rates sum to ~100%, so across a
            rotation  sum(usg_i * min_i) = 48  in equilibrium.

For each team we measure how oversubscribed it is on each axis and scale its
players down proportionally. Ball-dominant stats take both the minutes and the
usage haircut; the rest (rebounds, steals, blocks) only follow minutes. We only
ever *compress* (never inflate), because our player pool is incomplete and a
thin roster would otherwise get a spurious boost.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

# Stats tied to having the ball — these absorb the usage haircut on top of the
# minutes haircut. Rebounds, steals and blocks scale with minutes only.
BALL_STATS = {"PTS", "AST", "FGA", "FGM", "FTA", "FTM", "3PM", "3PA", "TO"}

TEAM_MINUTES = 240.0   # 5 players * 48 minutes
USAGE_BUDGET = 48.0    # sum(usg * minutes) in a balanced rotation
ROTATION_SIZE = 9      # a real rotation is ~9 players; ignore the deep bench
FACTOR_FLOOR = 0.78    # most any single axis can compress a team
COMBINED_FLOOR = 0.65  # most the two axes together can compress one stat

# Not real franchises — players here share no minutes/usage, so never group them.
NON_TEAMS = {None, "", "FA", "None"}


def _clamped(ratio: float) -> float:
    """A compress-only factor in [FACTOR_FLOOR, 1.0] (never inflates)."""
    return max(FACTOR_FLOOR, min(1.0, ratio))


def adjust(records: Iterable[dict]) -> list[dict]:
    """Scale each record's `proj_line` for roster crowding, in place.

    Records must carry `team` (current pro team) and `usg` (projected usage
    fraction). Records without a team are left untouched. Also annotates each
    adjusted record with `min_factor` / `usg_factor` for transparency.
    """
    records = list(records)
    by_team: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        if rec.get("team") not in NON_TEAMS:
            by_team[rec["team"]].append(rec)

    for players in by_team.values():
        if len(players) < 2:
            continue
        # Crowding is a property of the rotation, not the 15-man roster, so
        # measure demand over the top players by projected minutes.
        rotation = sorted(
            players, key=lambda p: p["proj_line"].get("MIN", 0.0), reverse=True
        )[:ROTATION_SIZE]
        total_min = sum(p["proj_line"].get("MIN", 0.0) for p in rotation)
        usage_demand = sum(
            p.get("usg", 0.0) * p["proj_line"].get("MIN", 0.0) for p in rotation
        ) / USAGE_BUDGET

        min_factor = _clamped(TEAM_MINUTES / total_min) if total_min > TEAM_MINUTES else 1.0
        usg_factor = _clamped(1.0 / usage_demand) if usage_demand > 1.0 else 1.0

        for p in players:
            line = p["proj_line"]
            adjusted = {}
            for stat, value in line.items():
                if stat == "MIN":
                    adjusted[stat] = round(value * min_factor, 1)
                elif stat in BALL_STATS:
                    adjusted[stat] = round(value * max(COMBINED_FLOOR, min_factor * usg_factor), 2)
                else:
                    adjusted[stat] = round(value * min_factor, 2)
            p["proj_line"] = adjusted
            p["min_factor"] = round(min_factor, 3)
            p["usg_factor"] = round(usg_factor, 3)

    return records
