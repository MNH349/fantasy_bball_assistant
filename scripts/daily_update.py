"""Daily in-season update — the job the launchd schedule runs each morning.

Pipeline:
  1. Value every standard-contract player: fresh DARKO + this season's box
     scores + the NBA schedule (rest-of-season and current-week value).
  2. Tag each with ESPN ownership, positions, IR slot, injury and ESPN's own
     season average; project every night left in the matchup.
  3. Save today's snapshot, rank the universe (core 120 + watch list).
  4. Plan the week's streaming moves and find trade ideas.
  5. Write the daily report (and the top 100 on Mondays).

Run:  python scripts/daily_update.py
It is idempotent: re-running on the same day overwrites that day's results.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import REPORTS_DIR, UNTOUCHABLES_FILE, load_config, require_credentials  # noqa: E402
from fba import (  # noqa: E402
    contracts, espn_client, inseason, inseason_report, names, planner, projections,
    ranking, schedule, scoring, stats_nba, storage, tonight, trades,
)

# ESPN injury statuses that mean the player won't suit up this scoring period.
INACTIVE = {"OUT", "SUSPENSION", "INJURY_RESERVE"}
_ESPN_FIELDS = ("rostered_by", "is_mine", "injury", "positions", "lineup_slot", "espn_avg",
                "espn_games", "espn_proj_avg", "waiver_until")


def _resolve_scoring(cfg):
    if cfg.has_credentials:
        return espn_client.fetch_scoring_formula(cfg)
    return dict(scoring.DEFAULT_SCORING)


def _tag_ownership(rows: list[dict], status: dict) -> None:
    """Join ESPN ownership, positions, IR slot and injury onto rows by name."""
    matcher = names.Matcher({names.normalize(n): v for n, v in status["by_name"].items()})
    for r in rows:
        hit = matcher.get(r["name"]) or {}
        for field in _ESPN_FIELDS:
            r[field] = hit.get(field)
        r["is_mine"] = bool(r["is_mine"])


def _apply_injury_week(rows: list[dict]) -> None:
    """Zero the week value of anyone OUT — ROS stays (they return), but an
    inactive player scores nothing this period, keeping add/stream lists honest."""
    for r in rows:
        if r.get("injury") in INACTIVE:
            r["games_week"] = 0
            r["value_week"] = 0.0


def _value_players(cfg, formula, period_start: str) -> tuple[list[dict], dict, dict]:
    """Steps 1–2: valued, ESPN-tagged rows for standard-contract players."""
    print("Loading rosters, DARKO, box scores, schedule ...")
    standard = contracts.standard_roster(use_cache=False)
    darko = {i: d for i, d in projections.load_darko_preseason().items() if i in standard}
    if not darko:
        raise SystemExit("DARKO unavailable; cannot value players.")
    current = {r["player_id"]: r for r in stats_nba.fetch_player_stats(season="2026-27", use_cache=False)}
    prior_minutes = {r["player_id"]: r["line"].get("MIN", 0.0)
                     for r in stats_nba.fetch_player_stats(season="2025-26")}
    team_games = schedule.team_games()
    team_dates = {t: sorted(g) for t, g in team_games.items()}

    rows = inseason.value_board(
        darko, current, stats_nba.games_history(), prior_minutes, team_dates, formula,
        stats_nba.team_tricode_by_id(), roster_team={i: s["team"] for i, s in standard.items()},
    )

    print("Reading ESPN rosters, positions, injuries, adds used ...")
    status = espn_client.fetch_roster_status(cfg, period_start)
    standard_by_norm = {names.normalize(s["name"]): {"nba_id": i, "team": s["team"]}
                        for i, s in standard.items()}
    rows += inseason.espn_only_rows(status, rows, standard_by_norm, current, team_dates, formula)
    _tag_ownership(rows, status)
    _apply_injury_week(rows)
    rows.sort(key=lambda r: r["value_ros"], reverse=True)
    return rows, status, team_games


def main() -> None:
    cfg = load_config()
    require_credentials(cfg)
    today = date.today()
    today_iso = today.isoformat()
    period_start, period_end = schedule.current_period(today)
    days = [(today + timedelta(days=i)).isoformat()
            for i in range((date.fromisoformat(period_end) - today).days + 1)]
    formula = _resolve_scoring(cfg)

    rows, status, team_games = _value_players(cfg, formula, period_start)

    print("Projecting the rest of the matchup night by night ...")
    proj = tonight.nightly(rows, days, team_games, stats_nba.fetch_game_logs(use_cache=False),
                           formula, stats_nba.team_pace())

    storage.save_snapshot(rows, today_iso)
    rank, snap_day, prev_day = ranking.weekly_for(today_iso)
    universe = ranking.universe(rank)

    my_team = status["my_team_name"]
    mine = [r for r in rows if r["is_mine"]]
    free = [r for r in rows if r["rostered_by"] is None and r["name"] in universe]
    active_count = sum(1 for p in status["by_name"].values() if p["is_mine"] and p["lineup_slot"] != "IR")

    print("Planning streaming moves and finding trades ...")
    plan = planner.plan_week(mine, free, proj, days, status["adds_used"], active_count)
    ideas = trades.find(rows, my_team, universe, trades.load_untouchables(UNTOUCHABLES_FILE))

    relevant = {r["name"] for r in mine} | {r["name"] for r in free}
    storage.save_extras(today_iso, {
        "date": today_iso, "my_team": my_team, "period": [period_start, period_end],
        "plan": plan, "trades": ideas,
        "tonight": {n: p for n, p in proj.items() if n in relevant},
    })

    report = inseason_report.build_daily(today_iso, my_team, mine, free, plan, ideas, proj)
    path = inseason_report.write_daily_report(report, today_iso, REPORTS_DIR)
    if today.weekday() == 0 or not (REPORTS_DIR / "top100_latest.md").exists():
        inseason_report.write_top100(rank, snap_day, prev_day, REPORTS_DIR)

    todays = [m for m in plan["moves"] if m["day"] == today_iso]
    print(f"\nSnapshot saved for {today_iso} ({len(rows)} standard-contract players). Report: {path}")
    print(f"Adds left: {planner.ADDS_PER_MATCHUP - plan['adds_used']} of {planner.ADDS_PER_MATCHUP}. "
          f"Planned moves this week: {len(plan['moves'])}. Trade ideas: {len(ideas)}.")
    for name in plan["ir_moves"]:
        print(f"  Move {name} to IR.")
    for m in todays:
        print(f"  Today: add {m['add']} ({m['add_team']}), drop {m['drop'] or '(open spot)'}  +{m['gain']:.0f}")


if __name__ == "__main__":
    main()
