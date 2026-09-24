"""Phase 2 acceptance test: build the 2026-27 draft board.

Run:  python scripts/draft_board.py

Projection source: DARKO's talent sheet (per-100 rates + usage + efficiency),
with per-game minutes driven by last season's nba_api actuals and joined on
nba_id. Falls back to a 25-26 age-curve baseline if DARKO can't be reached.

Scoring formula: pulled live from the league if ESPN_S2/SWID are set; otherwise
DEFAULT_SCORING, so the board still builds without credentials.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import REPORTS_DIR, load_config  # noqa: E402
from fba import draft, espn_client, projections, report, scoring, stats_nba  # noqa: E402


def resolve_scoring(cfg) -> dict:
    if cfg.has_credentials:
        print("Reading live league scoring formula ...")
        return espn_client.fetch_scoring_formula(cfg)
    print("No credentials set; using DEFAULT_SCORING (connect to use your league's).")
    return dict(scoring.DEFAULT_SCORING)


def build_records(baseline: list[dict], darko: dict[int, dict]) -> list[dict]:
    """Join DARKO projections to last-season baselines on nba_id.

    Minutes come from last season's actuals when available (DARKO's talent-sheet
    minutes are conservative and skew per-game rankings); DARKO minutes are the
    fallback for players without a 25-26 line (rookies, long-injured).
    """
    baseline_by_id = {rec["player_id"]: rec for rec in baseline}
    records = []
    for nba_id, d in darko.items():
        base = baseline_by_id.get(nba_id)
        minutes = base["line"].get("MIN", 0.0) if base else 0.0
        if not minutes:
            minutes = d["darko_minutes"]
        records.append(
            {
                "name": d["name"],
                "age": d["age"],
                "proj_line": projections.darko_line(d["rates"], minutes),
                "baseline_line": base["line"] if base else None,
            }
        )
    return records


def build_records_fallback(baseline: list[dict]) -> list[dict]:
    """Age-curve fallback when DARKO is unavailable."""
    records = []
    for rec in baseline:
        if rec.get("gp", 0) < 20:
            continue
        records.append(
            {
                "name": rec["name"],
                "age": rec.get("age"),
                "proj_line": projections.project_from_baseline(rec["line"], rec.get("age")),
                "baseline_line": rec["line"],
            }
        )
    return records


def main() -> None:
    cfg = load_config()
    formula = resolve_scoring(cfg)

    print(f"Loading 2025-26 player stats ({stats_nba.BASELINE_SEASON}) ...")
    baseline = stats_nba.fetch_player_stats()
    print(f"  {len(baseline)} players loaded.")

    print("Fetching DARKO talent projections ...")
    darko = projections.load_darko_preseason()
    if darko:
        print(f"  {len(darko)} DARKO players; minutes from last-season actuals.")
        records = build_records(baseline, darko)
    else:
        print("  DARKO unavailable; using age-curve growth baseline.")
        records = build_records_fallback(baseline)

    board = draft.build_board(records, formula)
    csv_path, md_path = report.write_draft_board(board, REPORTS_DIR)
    print(f"\nDraft board written:\n  {csv_path}\n  {md_path}")
    print("\nTop 20:")
    for r in board[:20]:
        growth = "—" if r["growth"] is None else f"{r['growth']:+.1f}"
        print(f"  {r['rank']:>3}. {r['name']:<24} {r['proj_fpts_pg']:>6.1f} FP/G "
              f"({growth})  {r['tier']}")


if __name__ == "__main__":
    main()
