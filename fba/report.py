"""Render board/recommendation data to CSV and Markdown.

Draft-board rendering is implemented (Phase 2). In-season report rendering is
stubbed for Phase 4.
"""
from __future__ import annotations

import csv
from pathlib import Path


def write_draft_board(rows: list[dict], out_dir: Path) -> tuple[Path, Path]:
    """Write the ranked draft board as CSV + a readable Markdown cheat sheet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "draft_board.csv"
    md_path = out_dir / "draft_board.md"

    fields = ["rank", "tier", "cls", "name", "positions", "team", "fpg",
              "games", "value", "espn_rank", "adp_rank"]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# 2026-27 Draft Board",
        "",
        "Ranked by projected **season value** (FP/G × games) for your H2H Points "
        "league. Value blends our DARKO+crowding+availability model with ESPN's "
        "projection, weighted by data reliability — **V**eterans 0.7 ours, "
        "**S**ophomores 0.3 ours, **R**ookies ESPN-only (with an ADP downward cap "
        "and a bust discount). **ESPN Rk** and **ADP** are consensus references; "
        "big gaps from our rank are where to apply judgment.",
        "",
        "| Rank | Tier | Cls | Player | Pos | Team | FP/G | G | Value | ESPN Rk | ADP |",
        "|-----:|------|:---:|--------|-----|------|-----:|--:|------:|--------:|----:|",
    ]
    for r in rows:
        erk = f"#{r['espn_rank']}" if r.get("espn_rank") else "—"
        adp = f"#{r['adp_rank']}" if r.get("adp_rank") else "—"
        lines.append(
            f"| {r['rank']} | {r['tier']} | {r['cls']} | {r['name']} | "
            f"{r.get('positions') or ''} | {r.get('team') or ''} | "
            f"{r['fpg']:.1f} | {r['games']:.0f} | {r['value']:.0f} | {erk} | {adp} |"
        )
    md_path.write_text("\n".join(lines) + "\n")
    return csv_path, md_path


def write_weekly_report(*args, **kwargs):
    raise NotImplementedError(
        "Phase 4: render pickups / drops / trade targets to Markdown + CSV."
    )
