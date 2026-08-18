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

    fields = ["rank", "tier", "name", "age", "proj_fpts_pg", "baseline_fpts_pg", "growth"]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# 2026-27 Draft Board",
        "",
        "Ranked by projected per-game fantasy points in your H2H Points league. "
        "Position-agnostic (best available for any draft slot).",
        "",
        "| Rank | Tier | Player | Age | Proj FP/G | 25-26 FP/G | Growth |",
        "|-----:|------|--------|----:|----------:|-----------:|-------:|",
    ]
    for r in rows:
        age = "" if r.get("age") is None else f"{r['age']:.0f}"
        lines.append(
            f"| {r['rank']} | {r['tier']} | {r['name']} | {age} | "
            f"{r['proj_fpts_pg']:.1f} | {r['baseline_fpts_pg']:.1f} | {r['growth']:+.1f} |"
        )
    md_path.write_text("\n".join(lines) + "\n")
    return csv_path, md_path


def write_weekly_report(*args, **kwargs):
    raise NotImplementedError(
        "Phase 4: render pickups / drops / trade targets to Markdown + CSV."
    )
