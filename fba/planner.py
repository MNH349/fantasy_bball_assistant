"""Weekly streaming planner: how to spend the matchup's 7 adds.

Two facts drive it:
  - A streamer only scores on nights he plays AND an open starting slot he's
    eligible for exists; on a crowded night he sits on your bench for nothing.
  - One add can cover several open nights.
So the planner maps your starting lineup night by night, then greedily picks the
pickup — a free agent into one of your 2 streamer spots — that adds the most
starting-lineup points over the rest of the week, and repeats while adds remain
and each move clears the swap threshold. Core players are never dropped; an OUT
core player goes to IR first when an IR spot is open, which frees a roster spot
without spending a drop.
"""
from __future__ import annotations

from typing import Iterable, Mapping

LINEUP_SLOTS = ("PG", "SG", "SF", "PF", "C", "G", "F", "UT", "UT", "UT")
ACTIVE_ROSTER = 13
IR_SLOTS = 2
STREAMER_SPOTS = 2
ADDS_PER_MATCHUP = 7
SWAP_THRESHOLD = 8.0      # projected points a move must add to be worth an add
CANDIDATE_POOL = 30       # free agents considered, by projected points this week
INACTIVE = {"OUT", "SUSPENSION", "INJURY_RESERVE"}


def eligible(positions: str | None) -> frozenset[str]:
    """Lineup slots a player can fill, from ESPN's comma-separated slot list."""
    return frozenset(s for s in (positions or "").split(",") if s)


def best_lineup(players: Iterable[tuple[float, frozenset[str]]]) -> tuple[float, int]:
    """(points, starters) of the best legal starting lineup.

    Greedy by points, keeping a player only if the starters can still be matched
    to distinct slots (checked with augmenting paths). For slot-eligibility
    problems like this, greedy-with-matching is exactly optimal.
    """
    owner: list[int | None] = [None] * len(LINEUP_SLOTS)
    chosen = [p for p in sorted(players, key=lambda p: p[0], reverse=True) if p[0] > 0]

    def place(i: int, seen: set[int]) -> bool:
        for s, slot in enumerate(LINEUP_SLOTS):
            if slot in chosen[i][1] and s not in seen:
                seen.add(s)
                if owner[s] is None or place(owner[s], seen):
                    owner[s] = i
                    return True
        return False

    total, starters = 0.0, 0
    for i, (pts, _) in enumerate(chosen):
        if place(i, set()):
            total, starters = total + pts, starters + 1
    return round(total, 1), starters


def fillable_slots(eligibilities: Iterable[frozenset[str]]) -> int:
    """How many of the 10 starting slots this group of players can fill."""
    return best_lineup((1.0, e) for e in eligibilities)[1]


def _segment(row: list, k: int) -> list[int]:
    """Day indexes from `k` onward while the same player holds this spot."""
    seg = [k]
    while seg[-1] + 1 < len(row) and row[seg[-1] + 1] == row[k]:
        seg.append(seg[-1] + 1)
    return seg


def streamer_spots(active: list[dict], n: int = STREAMER_SPOTS) -> list[str]:
    """The `n` players with the lowest average rank across FP/G and ROS value."""
    def ranks(key):
        return {r["name"]: i for i, r in enumerate(sorted(active, key=lambda r: r[key]), start=1)}
    by_fpg, by_ros = ranks("value_fpg"), ranks("value_ros")
    worst = sorted(active, key=lambda r: ((by_fpg[r["name"]] + by_ros[r["name"]]) / 2, r["value_ros"]))
    return [r["name"] for r in worst[:n]]


def plan_week(
    mine: list[dict],
    free: list[dict],
    proj: Mapping[str, Mapping[str, float]],
    days: list[str],
    adds_used: int,
    active_count: int | None = None,
) -> dict:
    """Plan this matchup's pickups from `days[0]` (today) through Sunday.

    `mine`/`free` are valued rows with `positions`, `lineup_slot`, `injury` and
    (for free agents) `waiver_until`; `proj` is {name: {day: projected FP}};
    `active_count` is how many non-IR players ESPN shows on my roster (defaults
    to the non-IR rows in `mine`).
    """
    on_ir = [r for r in mine if r.get("lineup_slot") == "IR"]
    active = [r for r in mine if r.get("lineup_slot") != "IR"]
    streamers = streamer_spots(active)
    core = [r for r in active if r["name"] not in streamers]
    ir_moves = sorted((r for r in core if r.get("injury") in INACTIVE),
                      key=lambda r: r["value_ros"], reverse=True)[:max(0, IR_SLOTS - len(on_ir))]
    core = [r for r in core if r not in ir_moves]

    empty = max(0, ACTIVE_ROSTER - (active_count if active_count is not None else len(active)))
    spots = streamers + [None] * (len(ir_moves) + empty)
    holders = [[h] * len(days) for h in spots]   # holders[spot][day index]

    elig = {r["name"]: eligible(r.get("positions")) for r in mine + free}
    core_names = [r["name"] for r in core]
    memo: dict = {}

    def lineup(k: int, names: tuple[str, ...]) -> tuple[float, int]:
        key = (k, names)
        if key not in memo:
            memo[key] = best_lineup((proj.get(n, {}).get(days[k], 0.0), elig.get(n, frozenset())) for n in names)
        return memo[key]

    def roster_on(k: int, swap: tuple[int, str] | None = None) -> tuple[str, ...]:
        on = [swap[1] if swap and s == swap[0] else holders[s][k] for s in range(len(spots))]
        return tuple(sorted(core_names + [n for n in on if n]))

    before = [lineup(k, roster_on(k)) for k in range(len(days))]
    base = [pts for pts, _ in before]

    pool = sorted(
        (r for r in free if r.get("injury") not in INACTIVE),
        key=lambda r: sum(proj.get(r["name"], {}).get(d, 0.0) for d in days), reverse=True,
    )[:CANDIDATE_POOL]

    moves, used, adds_left = [], set(), max(0, ADDS_PER_MATCHUP - adds_used)
    while adds_left > 0:
        best = None
        for s in range(len(spots)):
            for k in range(len(days)):
                seg = _segment(holders[s], k)
                for fa in pool:
                    name = fa["name"]
                    if name in used or (fa.get("waiver_until") or "") > days[k]:
                        continue
                    if not any(proj.get(name, {}).get(days[j], 0.0) for j in seg):
                        continue
                    gain = sum(lineup(j, roster_on(j, (s, name)))[0] - base[j] for j in seg)
                    if best is None or gain > best[0]:
                        best = (gain, s, k, seg, fa)
        if best is None or best[0] < SWAP_THRESHOLD:
            break
        gain, s, k, seg, fa = best
        dropped = holders[s][k]
        for j in seg:
            holders[s][j] = fa["name"]
            base[j] = lineup(j, roster_on(j))[0]
        used.add(fa["name"])
        adds_left -= 1
        moves.append({"spot": s, "day": days[k], "add": fa["name"], "add_team": fa.get("pro_team"),
                      "drop": dropped, "gain": round(gain, 1)})

    # A later move can cut short an earlier pickup's stay, so list each pickup's
    # projected games from the final plan.
    for m in moves:
        held = [j for j in range(len(days)) if holders[m["spot"]][j] == m["add"]]
        m["games"] = {days[j]: proj.get(m["add"], {}).get(days[j], 0.0)
                      for j in held if proj.get(m["add"], {}).get(days[j], 0.0)}

    after = [lineup(k, roster_on(k)) for k in range(len(days))]
    return {
        "days": days,
        "streamers": streamers,
        "ir_moves": [r["name"] for r in ir_moves],
        "adds_used": adds_used,
        "adds_left": adds_left,
        "moves": sorted(moves, key=lambda m: m["day"]),
        "open_slots_before": {d: len(LINEUP_SLOTS) - before[k][1] for k, d in enumerate(days)},
        "open_slots_after": {d: len(LINEUP_SLOTS) - after[k][1] for k, d in enumerate(days)},
        "points_before": round(sum(p for p, _ in before), 1),
        "points_after": round(sum(p for p, _ in after), 1),
    }
