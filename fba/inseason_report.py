"""Daily in-season report: my team, waiver upgrades, streamers, risers/fallers.

Consumes valued rows (from fba.inseason) already tagged with fantasy ownership
and injury status, plus the previous snapshot for day-over-day trends. Writes one
dated Markdown file. The add/drop logic is deliberately conservative: drop
candidates are ranked by rest-of-season value, not current production, and
anything above replacement level is shielded — so a hurt star (whose ROS value
stays high) never surfaces as droppable, only genuine deadweight does.
"""
from __future__ import annotations

from pathlib import Path

# How far below replacement a rostered player must sit before we call him
# droppable, as a fraction of replacement value (a small cushion against noise).
DROP_MARGIN = 0.97


def _fmt(row: dict) -> str:
    inj = row.get("injury") or ""
    tag = "" if inj in ("", "ACTIVE", None) else f" _{inj}_"
    return f"{row['name']}{tag}"


def _table(header: list[str], rows: list[list]) -> list[str]:
    sep = ["---"] * len(header)
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return out


def _board_line(r: dict) -> list:
    return [_fmt(r), r.get("pro_team") or "", f"{r['value_fpg']:.1f}",
            f"{r['games_left']:.0f}", f"{r['value_ros']:.0f}",
            r["games_week"], f"{r['value_week']:.0f}", f"{r['dpm']:+.1f}"]


_BOARD_COLS = ["Player", "Tm", "FP/G", "GL", "ROS", "GW", "Week", "DPM"]


def droppable(mine: list[dict], replacement_ros: float) -> list[dict]:
    """My players below replacement value, weakest first (drop candidates).

    Ranking on rest-of-season value (not current production) is what protects a
    hurt star: his ROS value stays high, so he sits above replacement and never
    surfaces here — only genuine deadweight does.
    """
    pool = [r for r in mine if r["value_ros"] < replacement_ros * DROP_MARGIN]
    return sorted(pool, key=lambda r: r["value_ros"])


def _risers_fallers(rows, prev_by_name, limit=8):
    """Biggest day-over-day ROS-value swings among rostered/notable players."""
    deltas = []
    for r in rows:
        prev = prev_by_name.get(r["name"])
        if prev is None:
            continue
        deltas.append((round(r["value_ros"] - prev, 0), r))
    deltas.sort(key=lambda d: d[0], reverse=True)
    risers = [(d, r) for d, r in deltas if d > 0][:limit]
    fallers = [(d, r) for d, r in deltas if d < 0][-limit:]
    return risers, fallers


def build(rows: list[dict], prev_by_name: dict, replacement_ros: float,
          today: str, my_team_name: str | None) -> str:
    """Render the full daily report as a Markdown string."""
    mine = [r for r in rows if r.get("is_mine")]
    free = [r for r in rows if r.get("rostered_by") is None]
    mine_ros = sorted(mine, key=lambda r: r["value_ros"], reverse=True)

    lines = [
        f"# In-Season Report — {today}",
        "",
        "Value blends DARKO talent with season-to-date production (weight on "
        "actuals ramps with games played, K=20). **ROS** = per-game × games left "
        "(durability × team games remaining); **Week** = per-game × games in the "
        "current Mon–Sun period. **DPM** is DARKO's impact rating — a *trend* "
        "signal only, it does not drive value.",
        "",
        f"## {my_team_name or 'My team'} — rest of season",
        "",
    ]
    lines += _table(_BOARD_COLS, [_board_line(r) for r in mine_ros])

    # --- Waiver upgrades (ROS), each paired with a protected drop ----------
    drop_pool = droppable(mine_ros, replacement_ros)
    upgrades = sorted(free, key=lambda r: r["value_ros"], reverse=True)[:10]

    lines += ["", "## Waiver upgrades — rest of season", ""]
    if not drop_pool:
        lines += ["_No droppable deadweight: every rostered player is above "
                  "replacement. Only make a move for a clear ROS upgrade._", ""]
    pair_rows = []
    for i, add in enumerate(upgrades):
        drop = drop_pool[i] if i < len(drop_pool) else None
        if drop is None or add["value_ros"] <= drop["value_ros"]:
            continue
        pair_rows.append([
            _fmt(add), add.get("pro_team") or "", f"{add['value_ros']:.0f}",
            "→", _fmt(drop), f"{drop['value_ros']:.0f}",
            f"+{add['value_ros'] - drop['value_ros']:.0f}",
        ])
    if pair_rows:
        lines += _table(["Add", "Tm", "ROS", "", "Drop", "ROS", "Δ"], pair_rows)
    else:
        lines += ["_No free agent beats a droppable player on ROS value right now._"]

    # --- Streaming this week (schedule-driven) -----------------------------
    streamers = sorted(free, key=lambda r: r["value_week"], reverse=True)[:12]
    lines += ["", "## Streaming this week — most fantasy points left in the period", ""]
    lines += _table(["Player", "Tm", "GW", "Week", "FP/G", "ROS"],
                    [[_fmt(r), r.get("pro_team") or "", r["games_week"],
                      f"{r['value_week']:.0f}", f"{r['value_fpg']:.1f}",
                      f"{r['value_ros']:.0f}"] for r in streamers])

    # --- Risers / fallers (needs yesterday) --------------------------------
    lines += ["", "## Risers & fallers (vs. last snapshot)", ""]
    if not prev_by_name:
        lines += ["_No prior snapshot yet — trends appear once the daily job has "
                  "run on two different days._"]
    else:
        risers, fallers = _risers_fallers(rows, prev_by_name)
        lines += ["**Risers**", ""]
        lines += _table(["Player", "Tm", "ΔROS", "ROS", "DPM"],
                        [[_fmt(r), r.get("pro_team") or "", f"+{d:.0f}",
                          f"{r['value_ros']:.0f}", f"{r['dpm']:+.1f}"] for d, r in risers] or [["—", "", "", "", ""]])
        lines += ["", "**Fallers**", ""]
        lines += _table(["Player", "Tm", "ΔROS", "ROS", "DPM"],
                        [[_fmt(r), r.get("pro_team") or "", f"{d:.0f}",
                          f"{r['value_ros']:.0f}", f"{r['dpm']:+.1f}"] for d, r in fallers] or [["—", "", "", "", ""]])

    # --- Top overall board -------------------------------------------------
    lines += ["", "## Top 25 overall — rest of season", ""]
    lines += _table(_BOARD_COLS, [_board_line(r) for r in rows[:25]])

    return "\n".join(lines) + "\n"


def write_daily_report(rows, prev_by_name, replacement_ros, today, my_team_name,
                       out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    text = build(rows, prev_by_name, replacement_ros, today, my_team_name)
    path = out_dir / f"inseason_{today}.md"
    path.write_text(text)
    (out_dir / "inseason_latest.md").write_text(text)
    return path
