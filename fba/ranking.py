"""Weekly top-100 ranking, with a watch list and fallers.

The league only rosters about 104 players (8 teams x 13 active), so the useful
universe is the top 120 by rest-of-season value (the core), the band just below
it for players climbing fast enough to matter soon (the watch list), and core
players sliding hard (fallers). Movement is measured against the snapshot a
week earlier, re-ranked over today's player universe so a released two-way or a
new signing doesn't shift everyone else's number.
"""
from __future__ import annotations

from datetime import date, timedelta

from fba import storage

TOP_N = 100
CORE_SIZE = 120
WATCH_DEPTH = 160      # watch list = ranks 121..160 that are climbing
RANK_MOVE = 15         # spots gained (watch) or lost (falling) in a week
MINUTES_JUMP = 4.0     # MPG gained in a week that also qualifies for the watch list
WINDOW_DAYS = 7
# The weekly ranking never uses a snapshot valued by an older model: when the
# model changes mid-week, it ranks off the first snapshot taken after the change.
# Bump this whenever the valuation model changes.
MODEL_DATE = "2026-11-12"   # K=5, durability at half strength
# Shown as of the latest snapshot even when ranking off an earlier one, so the
# weekly list always reflects today's owners, injuries and contract status.
LIVE_FIELDS = ("pro_team", "rostered_by", "injury", "positions", "lineup_slot", "espn_avg", "espn_games")


def rank_rows(rows: list[dict]) -> list[dict]:
    """Copies of `rows` sorted by ROS value with a 1-based `rank`."""
    ordered = sorted(rows, key=lambda r: r["value_ros"], reverse=True)
    return [{**r, "rank": i} for i, r in enumerate(ordered, start=1)]


def _is_climbing(r: dict) -> bool:
    return (r["rank_change"] or 0) >= RANK_MOVE or (r["minutes_change"] or 0) >= MINUTES_JUMP


def weekly(current: list[dict], previous: list[dict]) -> dict:
    """Rank `current`, compare with `previous`, split into top/core/watch/fallers.

    Each ranked row gains `prev_rank`, `rank_change` (+ = climbed, None = new to
    the universe), `minutes_change`, and a `tag` of "core" or "falling".
    """
    now_names = {r["name"] for r in current}
    prev = {r["name"]: r for r in rank_rows([r for r in previous if r["name"] in now_names])}

    ranked = []
    for r in rank_rows(current):
        p = prev.get(r["name"])
        ranked.append({
            **r,
            "prev_rank": p["rank"] if p else None,
            "rank_change": p["rank"] - r["rank"] if p else None,
            "minutes_change": round((r["minutes"] or 0) - (p["minutes"] or 0), 1) if p else None,
        })

    core = [{**r, "tag": "falling" if (r["rank_change"] or 0) <= -RANK_MOVE else "core"}
            for r in ranked[:CORE_SIZE]]
    return {
        "top": core[:TOP_N],
        "core": core,
        "watch": [r for r in ranked[CORE_SIZE:WATCH_DEPTH] if _is_climbing(r)],
        "fallers": [r for r in core if r["tag"] == "falling"],
    }


def universe(ranking: dict) -> set[str]:
    """Names the streaming planner and trade finder may draw from: core + watch."""
    return {r["name"] for r in ranking["core"]} | {r["name"] for r in ranking["watch"]}


def last_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_for(day: str) -> tuple[dict, str | None, str | None]:
    """Ranking from the snapshot on/before `day` vs. the one a week earlier.

    Values come from that snapshot (so the weekly list holds steady all week);
    owner, injury, positions and ESPN average come from the latest snapshot, and
    only players in the latest snapshot (today's standard contracts) are ranked.
    Returns (ranking, snapshot_date, compared_to_date). Before a full week of
    history exists, compares with the oldest snapshot instead. Snapshots from
    before MODEL_DATE are skipped as the ranking base (see above).
    """
    snap_day = storage.snapshot_on_or_before(day)
    if snap_day is None:
        return weekly([], []), None, None
    if snap_day < MODEL_DATE:
        snap_day = min((d for d in storage.snapshot_dates() if d >= MODEL_DATE), default=snap_day)
    latest = {r["name"]: r for r in storage.load_snapshot()}
    current = [{**r, **{f: latest[r["name"]].get(f) for f in LIVE_FIELDS}}
               for r in storage.load_snapshot(snap_day) if r["name"] in latest]

    week_ago = (date.fromisoformat(snap_day) - timedelta(days=WINDOW_DAYS)).isoformat()
    dates = storage.snapshot_dates()
    prev_day = storage.snapshot_on_or_before(week_ago) or (dates[0] if dates[0] < snap_day else None)
    previous = storage.load_snapshot(prev_day) if prev_day else []
    return weekly(current, previous), snap_day, prev_day
