"""Markdown/CSV reports: the daily in-season report and the weekly top 100.

The daily report leads with what to do today (streaming move, IR moves, adds
left), then the rest of the week's plan, core ROS upgrades, trade ideas, and the
roster. Core upgrades are deliberately conservative: drop candidates are ranked
on rest-of-season value, so a hurt star (whose ROS stays high) never surfaces as
droppable, only genuine deadweight does.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

# How far below the best free agent a rostered player must sit before we call
# him droppable, as a fraction of that value (a small cushion against noise).
DROP_MARGIN = 0.97


def _fmt(row: dict) -> str:
    inj = row.get("injury") or ""
    return row["name"] + ("" if inj in ("", "ACTIVE") else f" _{inj}_")


def _table(header: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    return out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]


def _day(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%a %m/%d")


def _base_positions(row: dict) -> str:
    return "/".join(p for p in (row.get("positions") or "").split(",") if p in ("PG", "SG", "SF", "PF", "C"))


def droppable(mine: list[dict], replacement_ros: float) -> list[dict]:
    """My players below replacement value, weakest first (drop candidates).

    Ranking on rest-of-season value (not current production) is what protects a
    hurt star: his ROS value stays high, so he sits above replacement and never
    surfaces here — only genuine deadweight does.
    """
    pool = [r for r in mine if r["value_ros"] < replacement_ros * DROP_MARGIN]
    return sorted(pool, key=lambda r: r["value_ros"])


def core_upgrades(core: list[dict], free: list[dict], limit: int = 6) -> list[tuple[dict, dict]]:
    """(add, drop) pairs where a free agent beats a core player on ROS value."""
    upgrades = sorted(free, key=lambda r: r["value_ros"], reverse=True)[:limit]
    best_fa = upgrades[0]["value_ros"] if upgrades else 0.0
    drops = droppable(core, best_fa)
    return [(add, drop) for add, drop in zip(upgrades, drops) if add["value_ros"] > drop["value_ros"]]


def _plan_section(plan: dict, today: str) -> list[str]:
    todays = [m for m in plan["moves"] if m["day"] == today]
    lines = ["## Today", "",
             f"**Adds left this matchup: {7 - plan['adds_used']} of 7** "
             f"({len(plan['moves'])} planned below).", ""]
    for name in plan["ir_moves"]:
        lines.append(f"- 🏥 **Move {name} to IR** — he's OUT; that frees a roster spot without a drop.")
    for m in todays:
        drop = f"drop **{m['drop']}**" if m["drop"] else "no drop needed (open spot)"
        lines.append(f"- ➕ **Add {m['add']}** ({m['add_team']}), {drop} — "
                     f"+{m['gain']:.0f} projected lineup points this week.")
    if not todays and not plan["ir_moves"]:
        lines.append("- No move today — nothing clears the +8 point bar.")
    lines += ["", f"Open starting slots tonight: **{plan['open_slots_after'].get(today, 0)}**.", "",
              "## This week's streaming plan", ""]
    if plan["moves"]:
        lines += _table(["Day", "Add", "Tm", "Drop", "Projected games", "Gain"], [
            [_day(m["day"]), m["add"], m["add_team"] or "", m["drop"] or "(open spot)",
             ", ".join(f"{_day(d)[:3]} {fp:.0f}" for d, fp in m["games"].items()), f"+{m['gain']:.0f}"]
            for m in plan["moves"]])
    else:
        lines.append("_No pickups planned — your lineup is full on the nights that matter._")
    lines += ["", "Open starting slots by night (before → after the plan): " + ", ".join(
        f"{_day(d)[:3]} {plan['open_slots_before'][d]}→{plan['open_slots_after'][d]}" for d in plan["days"]),
        "", f"Projected lineup points through Sunday: {plan['points_before']:.0f} → "
            f"**{plan['points_after']:.0f}**.", f"Streamer spots: {', '.join(plan['streamers'])}."]
    return lines


def _trade_section(trades: list[dict]) -> list[str]:
    lines = ["", "## Trade ideas", "",
             "_You gain 3–15% on our ROS value; it looks even or better to them on ESPN's numbers._", ""]
    if not trades:
        return lines + ["_No trades fit both bands today._"]
    rows = []
    for t in trades:
        extras = ([f"+ add {n}" for n in t["my_fill"]] + [f"they drop {n}" for n in t["their_drop"]])
        rows.append([t["team"], " + ".join(t["give"]), " + ".join(t["get"]), "; ".join(extras) or "—",
                     f"{t['my_pct']:+.0%}", f"{t['their_pct']:+.0%}"])
    return lines + _table(["Team", "You give", "You get", "Roster spot", "You (ours)", "Them (ESPN)"], rows)


def build_daily(today: str, my_team_name: str, mine: list[dict], free: list[dict],
                plan: dict, trades: list[dict], proj: dict) -> str:
    """Render the daily report as a Markdown string."""
    core = [r for r in mine if r["name"] not in plan["streamers"] and r.get("lineup_slot") != "IR"]
    lines = [
        f"# In-Season Report — {today}", "",
        "Projections blend DARKO with this season's production. **Tonight** adjusts "
        "for teammates out and opponent pace. **ROS** = FP/G × games left.", "",
    ]
    lines += _plan_section(plan, today)

    lines += ["", "## Core upgrades — rest of season", ""]
    pairs = core_upgrades(core, free)
    lines += (_table(["Add", "Tm", "ROS", "Drop", "ROS", "Δ"], [
        [_fmt(a), a.get("pro_team") or "", f"{a['value_ros']:.0f}", _fmt(d), f"{d['value_ros']:.0f}",
         f"+{a['value_ros'] - d['value_ros']:.0f}"] for a, d in pairs])
        if pairs else ["_No free agent beats a core player on rest-of-season value._"])

    lines += _trade_section(trades)

    def role(r):
        return "IR" if r.get("lineup_slot") == "IR" else "streamer" if r["name"] in plan["streamers"] else "core"
    lines += ["", f"## {my_team_name}", ""]
    lines += _table(["Player", "Tm", "Pos", "Role", "FP/G", "ESPN avg", "ROS", "Tonight"], [
        [_fmt(r), r.get("pro_team") or "", _base_positions(r), role(r), f"{r['value_fpg']:.1f}",
         f"{r.get('espn_avg') or 0:.1f}", f"{r['value_ros']:.0f}", f"{proj.get(r['name'], {}).get(today, 0):.0f}"]
        for r in sorted(mine, key=lambda r: r["value_ros"], reverse=True)])
    return "\n".join(lines) + "\n"


def write_daily_report(text: str, today: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"inseason_{today}.md"
    path.write_text(text)
    (out_dir / "inseason_latest.md").write_text(text)
    return path


# --- Weekly top 100 -------------------------------------------------------
def _move(r: dict) -> str:
    if r["rank_change"] is None:
        return "new"
    return "—" if r["rank_change"] == 0 else f"{'▲' if r['rank_change'] > 0 else '▼'}{abs(r['rank_change'])}"


def _rank_line(r: dict) -> list:
    return [r["rank"], _move(r), _fmt(r), r.get("pro_team") or "", _base_positions(r),
            f"{r['value_fpg']:.1f}", f"{r.get('espn_avg') or 0:.1f}", f"{r['games_left']:.0f}",
            f"{r['value_ros']:.0f}", r.get("rostered_by") or "FA", r.get("tag", "")]


_RANK_COLS = ["Rk", "Move", "Player", "Tm", "Pos", "FP/G", "ESPN avg", "GL", "ROS", "Owner", "Tag"]


def build_top100(ranking: dict, snap_day: str, prev_day: str | None) -> str:
    vs = f"vs {prev_day}" if prev_day else "no earlier snapshot to compare"
    lines = [f"# Top 100 — week of {snap_day}", "",
             f"Standard-contract players ranked by rest-of-season value ({vs}). ▲/▼ = spots moved.", ""]
    lines += _table(_RANK_COLS, [_rank_line(r) for r in ranking["top"]])
    lines += ["", "## Watch list — ranks 121–160 climbing fast", "",
              "_Up 15+ spots or +4 MPG in the last week._", ""]
    lines += (_table(_RANK_COLS + ["ΔMPG"], [_rank_line(r) + [f"{r['minutes_change'] or 0:+.1f}"]
                                           for r in ranking["watch"]])
              if ranking["watch"] else ["_Nobody below the core is climbing fast this week._"])
    lines += ["", "## Fallers — core players down 15+ spots", ""]
    lines += (_table(_RANK_COLS, [_rank_line(r) for r in ranking["fallers"]])
              if ranking["fallers"] else ["_No big fallers this week._"])
    return "\n".join(lines) + "\n"


def write_top100(ranking: dict, snap_day: str, prev_day: str | None, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    text = build_top100(ranking, snap_day, prev_day)
    path = out_dir / f"top100_{snap_day}.md"
    path.write_text(text)
    (out_dir / "top100_latest.md").write_text(text)
    fields = ["rank", "rank_change", "name", "pro_team", "positions", "value_fpg", "espn_avg",
              "games_left", "value_ros", "rostered_by", "tag"]
    with (out_dir / "top100_latest.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ranking["top"])
    return path
