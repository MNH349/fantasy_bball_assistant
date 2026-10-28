"""In-season valuation: blend DARKO talent with this season's production.

Preseason, value came from last year. In-season we have a growing sample of
*this* year, but early-season fantasy numbers are mostly noise. So value is a
confidence-weighted blend:

    value_fpg = (1 - w) * darko_fpg + w * actual_fpg,   w = gp / (gp + K)

DARKO (re-pulled daily, so it already reflects recent form) anchors the estimate
while the sample is small; actual production earns weight as games accumulate. K
is the prior strength in games. DARKO's *rates* are driven by each player's
season-to-date minutes, so a role change (more/less court time) flows through
immediately, before the nudge even kicks in.

Two values come out, because H2H Points needs both horizons:
  - ROS : value_fpg x games left this season (durability x team games remaining)
  - WEEK: value_fpg x games in the current Mon-Sun scoring period
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping, Sequence

from fba import availability, names, projections, schedule, scoring

NUDGE_PRIOR_GAMES = 20   # K: games played at which actuals and DARKO weigh equally
FULL_SEASON = 82
ESPN_ONLY_MIN_AVG = 18.0  # ignore deep-bench ESPN projections (fantasy pts/game)
# Default availability for a player with no NBA history (true rookie).
ROOKIE_DURABILITY = availability.projected_games([], None) / FULL_SEASON


def nudge_weight(games_played: int, k: int = NUDGE_PRIOR_GAMES) -> float:
    """Weight on season-to-date actuals vs. DARKO; ramps 0 -> 1 with sample."""
    if games_played <= 0:
        return 0.0
    return games_played / (games_played + k)


def project_player(
    rates: Mapping[str, float],
    role_minutes: float,
    cur_line: Mapping[str, float],
    games_played: int,
    gp_history: Sequence[float],
    age: float | None,
    formula: Mapping[str, float],
    games_week: int,
    team_games_left: int,
) -> dict:
    """Blend DARKO and actuals for one player; return per-game + ROS + week values."""
    darko_fpg = scoring.fantasy_points(projections.darko_line(rates, role_minutes), formula)
    actual_fpg = scoring.fantasy_points(cur_line, formula) if games_played > 0 else darko_fpg
    w = nudge_weight(games_played)
    value_fpg = (1 - w) * darko_fpg + w * actual_fpg

    durability = availability.projected_games(gp_history, age) / FULL_SEASON
    games_left = round(durability * team_games_left, 1)

    return {
        "darko_fpg": round(darko_fpg, 2),
        "actual_fpg": round(actual_fpg, 2),
        "value_fpg": round(value_fpg, 2),
        "games_left": games_left,
        "value_ros": round(value_fpg * games_left, 1),
        "games_week": games_week,
        "value_week": round(value_fpg * games_week, 1),
    }


def _mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def league_average_counts(team_dates: Mapping[str, list], today: date | None = None) -> tuple[int, int]:
    """(avg games this period, avg games remaining) across teams — the fallback
    when a player's team can't be resolved."""
    start, end = schedule.current_period(today)
    as_of = (today or date.today()).isoformat()
    aw = round(_mean(schedule.games_in_period(team_dates, t, start, end) for t in team_dates))
    al = round(_mean(schedule.games_remaining(team_dates, t, as_of) for t in team_dates))
    return aw, al


def team_counts(team_dates: Mapping[str, list], team: str | None,
                avg_week: int, avg_left: int, today: date | None = None) -> tuple[int, int]:
    """Games this period and games remaining for `team`, averaged if unknown."""
    if team not in team_dates:
        return avg_week, avg_left
    start, end = schedule.current_period(today)
    as_of = (today or date.today()).isoformat()
    return (schedule.games_in_period(team_dates, team, start, end),
            schedule.games_remaining(team_dates, team, as_of))


def value_board(
    darko: Mapping[int, dict],
    current_stats: Mapping[int, dict],
    gp_history: Mapping[int, list],
    prior_minutes: Mapping[int, float],
    team_dates: Mapping[str, list],
    formula: Mapping[str, float],
    tricode_by_id: Mapping[int, str],
    today: date | None = None,
) -> list[dict]:
    """Value every DARKO player off current-season role + production.

    `current_stats` is {nba_id: record} from stats_nba for THIS season;
    `gp_history` is {nba_id: [gp, ...]} over PRIOR seasons (durability only);
    `prior_minutes` is {nba_id: last-season MPG}, the stable minutes prior a
    tiny current-season sample regresses toward (DARKO's own minutes are
    talent-regressed and run low, so they make a poor prior);
    `tricode_by_id` maps a DARKO tm_id to an NBA tricode so players who have not
    yet appeared in a box score still get their team's schedule.
    """
    avg_week, avg_left = league_average_counts(team_dates, today)

    rows = []
    for nba_id, d in darko.items():
        cur = current_stats.get(nba_id)
        gp = cur["gp"] if cur else 0
        # Blend role minutes the same way as production: a one-game minutes
        # fluke shouldn't inflate a deep player, so regress toward last season's
        # minutes until the sample grows (DARKO's minutes as a last resort).
        w_min = nudge_weight(gp)
        prior_min = prior_minutes.get(nba_id) or d["darko_minutes"]
        season_min = cur["line"].get("MIN", 0.0) if (cur and gp > 0) else None
        role_minutes = prior_min if season_min is None else (1 - w_min) * prior_min + w_min * season_min
        team = cur["team"] if (cur and cur.get("team")) else tricode_by_id.get(d.get("tm_id"))

        gw, gl = team_counts(team_dates, team, avg_week, avg_left, today)

        vals = project_player(
            d["rates"], role_minutes, cur["line"] if cur else {}, gp,
            gp_history.get(nba_id, []), d.get("age"), formula, gw, gl,
        )
        rows.append(
            {
                "name": d["name"],
                "nba_id": nba_id,
                "pro_team": team,
                "dpm": round(d.get("dpm", 0.0), 2),
                "minutes": round(role_minutes, 1),
                "usg": round(d["rates"].get("usg_pct", 0.0), 3),
                **vals,
            }
        )
    rows.sort(key=lambda r: r["value_ros"], reverse=True)
    return rows


def espn_only_rows(
    status: dict,
    darko_rows: list[dict],
    nba_team_by_norm: Mapping[str, str],
    team_dates: Mapping[str, list],
    today: date | None = None,
) -> list[dict]:
    """Rows for ESPN players DARKO never covered — true rookies, mainly.

    DARKO has no projection for a first-year player, so we fall back to ESPN's
    own per-game projection (already in league scoring units) times a rookie
    durability estimate. Skips anyone a DARKO row already covers (so no one is
    double-counted) and deep-bench noise below a minutes-worth projection.
    """
    covered = names.Matcher({names.normalize(r["name"]): r for r in darko_rows})
    avg_week, avg_left = league_average_counts(team_dates, today)
    rows = []
    for name_, p in status["by_name"].items():
        if covered.get(name_) is not None:
            continue
        avg = p.get("espn_avg") or 0.0
        if avg < ESPN_ONLY_MIN_AVG:
            continue
        team = nba_team_by_norm.get(names.normalize(name_)) or p.get("pro_team")
        gw, gl = team_counts(team_dates, team, avg_week, avg_left, today)
        games_left = round(ROOKIE_DURABILITY * gl, 1)
        rows.append(
            {
                "name": name_, "nba_id": None, "pro_team": team,
                "dpm": 0.0, "minutes": 0.0, "usg": 0.0,
                "darko_fpg": 0.0, "actual_fpg": round(avg, 2), "value_fpg": round(avg, 2),
                "games_left": games_left, "value_ros": round(avg * games_left, 1),
                "games_week": gw, "value_week": round(avg * gw, 1),
                "rostered_by": p["rostered_by"], "is_mine": p["is_mine"], "injury": p["injury"],
            }
        )
    return rows
