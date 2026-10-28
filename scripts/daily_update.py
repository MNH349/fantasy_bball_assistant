"""Daily in-season update — the job the launchd schedule runs each morning.

Pipeline: pull fresh DARKO + this season's nba_api box scores + the NBA schedule
-> value every player (DARKO blended with season-to-date production, split into
rest-of-season and current-week) -> tag each with ESPN fantasy ownership and
injury status -> append today's snapshot to SQLite -> write the daily report.

Run:  python scripts/daily_update.py
It is idempotent: re-running on the same day overwrites that day's snapshot.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import REPORTS_DIR, load_config, require_credentials  # noqa: E402
from fba import (  # noqa: E402
    espn_client, inseason, inseason_report, names, projections, scoring,
    storage, stats_nba, schedule,
)


def _resolve_scoring(cfg):
    if cfg.has_credentials:
        return espn_client.fetch_scoring_formula(cfg)
    return dict(scoring.DEFAULT_SCORING)


# ESPN injury statuses that mean the player won't suit up this scoring period.
INACTIVE = {"OUT", "SUSPENSION", "INJURY_RESERVE"}


def _tag_ownership(rows: list[dict], status: dict) -> None:
    """Join ESPN ownership + injury onto DARKO-valued rows, matched by name."""
    by_norm = {names.normalize(n): v for n, v in status["by_name"].items()}
    matcher = names.Matcher(by_norm)
    for r in rows:
        hit = matcher.get(r["name"])
        r["rostered_by"] = hit["rostered_by"] if hit else None
        r["is_mine"] = bool(hit and hit["is_mine"])
        r["injury"] = hit["injury"] if hit else None


def _apply_injury_week(rows: list[dict]) -> None:
    """Zero the week value of anyone OUT — ROS stays (they return), but an
    inactive player scores nothing this period, keeping add/stream lists honest."""
    for r in rows:
        if r.get("injury") in INACTIVE:
            r["games_week"] = 0
            r["value_week"] = 0.0


def _previous_snapshot_date(today: str) -> str | None:
    earlier = [d for d in storage.snapshot_dates() if d < today]
    return earlier[-1] if earlier else None


def main() -> None:
    cfg = load_config()
    require_credentials(cfg)
    today = date.today().isoformat()
    formula = _resolve_scoring(cfg)

    print("Loading DARKO, this-season box scores, schedule ...")
    darko = projections.load_darko_preseason()
    current = {r["player_id"]: r for r in stats_nba.fetch_player_stats(season="2026-27", use_cache=False)}
    gp_history = stats_nba.games_history()
    prior_minutes = {r["player_id"]: r["line"].get("MIN", 0.0)
                     for r in stats_nba.fetch_player_stats(season="2025-26")}
    team_dates = schedule.team_game_dates()
    tricodes = stats_nba.team_tricode_by_id()
    if not darko:
        raise SystemExit("DARKO unavailable; cannot value players.")

    rows = inseason.value_board(darko, current, gp_history, prior_minutes, team_dates, formula, tricodes)

    print("Reading ESPN rosters + injuries ...")
    status = espn_client.fetch_roster_status(cfg)
    _tag_ownership(rows, status)

    # Add ESPN-only players (true rookies DARKO doesn't cover) so they show up on
    # rosters and in trades, then zero out this week for anyone inactive.
    nba_team_by_norm = {names.normalize(r["name"]): r.get("team") for r in current.values()}
    rows += inseason.espn_only_rows(status, rows, nba_team_by_norm, team_dates)
    _apply_injury_week(rows)
    rows.sort(key=lambda r: r["value_ros"], reverse=True)

    free = [r for r in rows if r["rostered_by"] is None]
    best_fa_ros = max((r["value_ros"] for r in free), default=0.0)

    prev_date = _previous_snapshot_date(today)
    prev_by_name = {r["name"]: r["value_ros"] for r in storage.load_snapshot(prev_date)} if prev_date else {}

    storage.save_snapshot(rows, today)
    path = inseason_report.write_daily_report(
        rows, prev_by_name, best_fa_ros, today, status["my_team_name"], REPORTS_DIR
    )

    mine = sorted((r for r in rows if r["is_mine"]), key=lambda r: r["value_ros"], reverse=True)
    print(f"\nSnapshot saved for {today} ({len(rows)} players). Report: {path}")
    print(f"Replacement (best FA ROS): {best_fa_ros:.0f}"
          + (f"   (trends vs {prev_date})" if prev_date else "   (first snapshot — no trends yet)"))
    print(f"\n{status['my_team_name']} — top of roster by ROS value:")
    for r in mine[:5]:
        print(f"  {r['name']:<24} {r.get('pro_team') or '':<4} ROS {r['value_ros']:>6.0f}  "
              f"wk {r['value_week']:>4.0f} ({r['games_week']}g)")


if __name__ == "__main__":
    main()
