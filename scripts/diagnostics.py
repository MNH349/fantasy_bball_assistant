"""Phase 1 acceptance test: connect to the league and print a snapshot.

Run:  python scripts/diagnostics.py
Needs ESPN_S2 / SWID in .env (a private league can't be read without them).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config, require_credentials  # noqa: E402
from fba import espn_client, scoring  # noqa: E402


def main() -> None:
    cfg = load_config()
    require_credentials(cfg)

    print(f"Connecting to league {cfg.league_id}, season {cfg.season} ...")
    league = espn_client.get_league(cfg)
    print(f"Connected: {getattr(league.settings, 'name', '(unnamed league)')}")

    formula = espn_client.fetch_scoring_formula(cfg)
    print("\n=== Scoring formula (per stat) ===")
    print(" ", scoring.format_scoring(formula))

    snap = espn_client.league_snapshot(league, cfg, formula)

    print("\n=== Teams ===")
    for t in snap["teams"]:
        print(f"  {t['name']:<28} {t['wins']}-{t['losses']}")

    print(f"\n=== My team: {snap['my_team'] or '(not auto-detected)'} ===")
    for r in snap["roster"]:
        print(f"  {r['name']:<24} {r['fpts_pg']:>6.1f} FP/G   {r['proTeam']}")

    print("\n=== Free-agent pool (top 15 by FP/G) ===")
    for r in espn_client.free_agent_pool(league, formula, size=50)[:15]:
        print(f"  {r['name']:<24} {r['fpts_pg']:>6.1f} FP/G   {r['proTeam']}")


if __name__ == "__main__":
    main()
