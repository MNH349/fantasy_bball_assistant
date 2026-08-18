"""Phase 2 acceptance test: build the 2026-27 draft board.

Run:  python scripts/draft_board.py
Uses 2025-26 nba_api stats (cached) + projected growth. If DARKO preseason
projections aren't wired/available yet, falls back to the age-curve baseline.

Scoring formula: pulled live from the league if ESPN_S2/SWID are set; otherwise
uses DEFAULT_SCORING so the board still builds without credentials.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import REPORTS_DIR, load_config  # noqa: E402
from fba import draft, espn_client, projections, report, scoring, stats_nba  # noqa: E402


def resolve_scoring(cfg) -> dict:
    if cfg.has_credentials:
        try:
            league = espn_client.get_league(cfg)
            print("Using live league scoring formula.")
            return scoring.scoring_from_league(league)
        except Exception as exc:  # noqa: BLE001
            print(f"Could not read live league ({exc}); using DEFAULT_SCORING.")
    else:
        print("No credentials set; using DEFAULT_SCORING (edit later once connected).")
    return dict(scoring.DEFAULT_SCORING)


def main() -> None:
    cfg = load_config()
    formula = resolve_scoring(cfg)

    print(f"Loading 2025-26 player stats ({stats_nba.BASELINE_SEASON}) ...")
    records = stats_nba.fetch_player_stats()
    print(f"  {len(records)} players loaded.")

    darko = projections.load_darko_preseason()  # {} until wired -> age-curve fallback
    if not darko:
        print("DARKO preseason not wired yet; using age-curve growth baseline.")

    board = draft.build_board(records, formula, darko=darko)
    csv_path, md_path = report.write_draft_board(board, REPORTS_DIR)
    print(f"\nDraft board written:\n  {csv_path}\n  {md_path}")
    print("\nTop 15:")
    for r in board[:15]:
        print(f"  {r['rank']:>3}. {r['name']:<24} {r['proj_fpts_pg']:>6.1f} FP/G "
              f"({r['growth']:+.1f})  {r['tier']}")


if __name__ == "__main__":
    main()
