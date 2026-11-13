"""Trade assessment and the trade finder.

Every trade is judged two ways:
  - Mine, by our rest-of-season value: the finder wants a 3-15% gain. Less isn't
    worth the hassle; more and the other manager likely says no (and that's when
    our model is most likely the one that's wrong).
  - Theirs, by what they see in the ESPN app — season-average FP/G x games left
    (ESPN's projection while the average rests on under 5 games): no worse
    than -2%, so it looks even-or-better to them.
Good trades live where our model and ESPN disagree: a hot start DARKO doesn't
believe (sell it) or a slow start it expects to recover (buy it).

Uneven trades count the roster spots they open or force. Whoever ends up over
drops their lowest player. Whoever ends up short gains an open spot — but the
best free agent could be added anyway by cutting the weakest player, so the spot
is only worth the lesser of the two (crediting the whole free agent would make
every consolidation trade look like a win). Both teams must still be able to
fill at least as many starting slots with healthy players as before.
"""
from __future__ import annotations

from itertools import combinations
from typing import Iterable

from fba.planner import INACTIVE, eligible, fillable_slots

MY_MIN, MY_MAX = 0.03, 0.15
THEIR_MIN = -0.02
MAX_SUGGESTIONS = 10
MAX_PER_TEAM = 3
ESPN_MIN_GAMES = 5   # below this, managers lean on ESPN's projection, not the average


def ros(r: dict) -> float:
    return r["value_ros"]


def espn_value(r: dict) -> float:
    """What other managers see: ESPN season average x games left."""
    if (r.get("espn_games") or 0) >= ESPN_MIN_GAMES and r.get("espn_avg"):
        fpg = r["espn_avg"]
    else:
        fpg = r.get("espn_proj_avg") or r["value_fpg"]
    return fpg * r["games_left"]


def _total(players: Iterable[dict], key) -> float:
    return round(sum(key(p) for p in players), 1)


def _pct(gain: float, give: float, get: float) -> float:
    return gain / max(give, get, 1.0)


def _healthy_slots(players: Iterable[dict]) -> int:
    return fillable_slots(eligible(p.get("positions")) for p in players if p.get("injury") not in INACTIVE)


def _lowest(players: list[dict], n: int, key) -> list[dict]:
    """The `n` lowest-valued non-IR players (who'd be dropped)."""
    return sorted((p for p in players if p.get("lineup_slot") != "IR"), key=key)[:max(0, n)]


def _spot_credit(fills: list[dict], could_cut: list[dict], key) -> float:
    """Value of open roster spots: each adds a free agent without a cut, so it's
    worth the lesser of that free agent and whoever you'd otherwise cut for him.

    `could_cut` is the whole current roster, traded players included — so a
    throw-in who'd have been your cut anyway adds nothing to the deal."""
    cuts = sorted((p for p in could_cut if p.get("lineup_slot") != "IR"), key=key)
    return sum(min(key(f), key(cuts[i])) if i < len(cuts) else key(f) for i, f in enumerate(fills))


def _names(players: Iterable[dict]) -> list[str]:
    return [p["name"] for p in players]


def assess(give: list[dict], get: list[dict], mine: list[dict], theirs: list[dict], free: list[dict]) -> dict:
    """Both views of a trade, including the roster spots it opens or forces."""
    give_n, get_n = set(_names(give)), set(_names(get))
    extra = len(give) - len(get)   # > 0: I open spots and they must drop

    healthy_free = [p for p in free if p.get("injury") not in INACTIVE]
    my_fill = sorted(healthy_free, key=ros, reverse=True)[:max(0, extra)]
    my_drop = _lowest([p for p in mine if p["name"] not in give_n], -extra, ros)
    their_drop = _lowest([p for p in theirs if p["name"] not in get_n] + give, extra, espn_value)
    their_fill = sorted(healthy_free, key=espn_value, reverse=True)[:max(0, -extra)]

    my_kept = [p for p in mine if p["name"] not in give_n]
    their_kept = [p for p in theirs if p["name"] not in get_n] + give
    my_give_v = _total(give + my_drop, ros)
    my_get_v = round(_total(get, ros) + _spot_credit(my_fill, mine, ros), 1)
    their_give_v = _total(get + their_drop, espn_value)
    their_get_v = round(_total(give, espn_value) + _spot_credit(their_fill, theirs, espn_value), 1)

    my_after = [p for p in my_kept if p not in my_drop] + get + my_fill
    their_after = [p for p in their_kept if p not in their_drop] + their_fill

    return {
        "give": _names(give), "get": _names(get),
        "my_fill": _names(my_fill), "my_drop": _names(my_drop),
        "their_drop": _names(their_drop), "their_fill": _names(their_fill),
        "my_give": my_give_v, "my_get": my_get_v,
        "my_gain": round(my_get_v - my_give_v, 1), "my_pct": _pct(my_get_v - my_give_v, my_give_v, my_get_v),
        "their_give": their_give_v, "their_get": their_get_v,
        "their_gain": round(their_get_v - their_give_v, 1),
        "their_pct": _pct(their_get_v - their_give_v, their_give_v, their_get_v),
        "my_lineup_ok": _healthy_slots(my_after) >= _healthy_slots(mine),
        "their_lineup_ok": _healthy_slots(their_after) >= _healthy_slots(theirs),
    }


def find(rows: list[dict], my_team: str, universe: set[str], untouchables: set[str] = frozenset()) -> list[dict]:
    """Up to 10 trades (max 3 per team) that slightly favor me and look fair to them.

    1-for-1 and 2-for-1 (I consolidate). The player I get must be in the core or
    watch list; untouchables are never offered. Sorted by how good the deal
    looks to them, then by my gain; only the best package per target is kept.
    """
    by_team: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("rostered_by"):
            by_team.setdefault(r["rostered_by"], []).append(r)
    mine = by_team.get(my_team, [])
    free = [r for r in rows if not r.get("rostered_by")]
    offer = [r for r in mine if r["name"] not in untouchables]
    packages = [[m] for m in offer] + [list(pair) for pair in combinations(offer, 2)]

    found = []
    for team, theirs in by_team.items():
        if team == my_team:
            continue
        for target in (p for p in theirs if p["name"] in universe):
            for give in packages:
                t = assess(give, [target], mine, theirs, free)
                if (MY_MIN <= t["my_pct"] <= MY_MAX and t["their_pct"] >= THEIR_MIN
                        and t["my_lineup_ok"] and t["their_lineup_ok"]):
                    found.append({**t, "team": team})

    found.sort(key=lambda t: (t["their_pct"], t["my_pct"]), reverse=True)
    picked, per_team, targets = [], {}, set()
    for t in found:
        target = (t["team"], t["get"][0])  # best package per target, not near-duplicates
        if target not in targets and per_team.get(t["team"], 0) < MAX_PER_TEAM:
            targets.add(target)
            picked.append(t)
            per_team[t["team"]] = per_team.get(t["team"], 0) + 1
        if len(picked) == MAX_SUGGESTIONS:
            break
    return picked


def load_untouchables(path) -> set[str]:
    """Names from the untouchables file (one per line, # comments), if it exists."""
    if not path.exists():
        return set()
    lines = (line.strip() for line in path.read_text().splitlines())
    return {line for line in lines if line and not line.startswith("#")}


FAIR_BAND = 0.05     # within 5% either way on our value = roughly even
CLEAR_BAND = 0.15    # beyond 15% = a clear win or loss


def evaluate_named(rows: list[dict], my_team: str, give_names: list[str], get_names: list[str]) -> dict:
    """assess() a trade typed as player names, finding both rosters and free agents.

    Returns the assessment plus `team`, or {"error": ...} if a name doesn't match
    or the players don't come from my team / a single other team.
    """
    from fba import names

    matcher = names.Matcher({names.normalize(r["name"]): r for r in rows})
    give = [matcher.get(n) for n in give_names]
    get = [matcher.get(n) for n in get_names]
    missing = [n for n, r in zip(give_names + get_names, give + get) if r is None]
    if missing:
        return {"error": f"No standard-contract player matches: {', '.join(missing)}"}
    if not give or not get:
        return {"error": "Need at least one player on each side."}
    if any(r.get("rostered_by") != my_team for r in give):
        return {"error": f"Everyone you give must be on {my_team}."}
    owners = {r.get("rostered_by") for r in get}
    if len(owners) != 1 or None in owners or my_team in owners:
        return {"error": "Everyone you get must come from one other team."}
    team = owners.pop()
    mine = [r for r in rows if r.get("rostered_by") == my_team]
    theirs = [r for r in rows if r.get("rostered_by") == team]
    free = [r for r in rows if not r.get("rostered_by")]
    return {**assess(give, get, mine, theirs, free), "team": team}


def verdict(t: dict) -> str:
    """One-line call on a trade, from my side's value change."""
    pct = t["my_pct"]
    if pct > CLEAR_BAND:
        call = "ACCEPT — a clear rest-of-season value gain."
    elif pct > FAIR_BAND:
        call = "LEAN ACCEPT — a modest value gain."
    elif pct >= -FAIR_BAND:
        call = "ROUGHLY EVEN on value — decide on fit and need."
    elif pct >= -CLEAR_BAND:
        call = "LEAN DECLINE — you give up modest value."
    else:
        call = "DECLINE — you give up clear rest-of-season value."
    if not t["my_lineup_ok"]:
        call += " Warning: you couldn't fill as many starting slots afterwards."
    return call
