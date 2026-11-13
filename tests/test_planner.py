import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import planner  # noqa: E402

GUARD = planner.eligible("PG,SG,G,UT")
CENTER = planner.eligible("C,UT")


def test_best_lineup_respects_slots():
    # Five centers: only C + 3 UT can hold them, so just 4 start.
    pts, starters = planner.best_lineup([(30.0, CENTER)] * 5)
    assert starters == 4 and pts == 120.0


def test_best_lineup_reassigns_to_fit_a_specialist():
    # The flexible big grabs C first; the C-only big still starts because the
    # flexible one gets moved to UT (plain greedy would bench him).
    players = [(45.0, planner.eligible("C,UT")), (40.0, planner.eligible("C"))]
    assert planner.best_lineup(players) == (85.0, 2)


def test_players_without_a_game_never_start():
    assert planner.best_lineup([(0.0, GUARD), (25.0, GUARD)]) == (25.0, 1)


def test_streamer_spots_use_average_rank():
    active = [
        {"name": "A", "value_fpg": 40, "value_ros": 2400},
        {"name": "B", "value_fpg": 20, "value_ros": 1500},   # low on both
        {"name": "C", "value_fpg": 35, "value_ros": 1000},   # low ROS only
        {"name": "D", "value_fpg": 22, "value_ros": 1900},   # low FP/G only
    ]
    assert planner.streamer_spots(active, n=1) == ["B"]


def _row(name, fpg, ros, positions="PG,SG,SF,PF,C,G,F,UT", **extra):
    return {"name": name, "value_fpg": fpg, "value_ros": ros, "positions": positions, **extra}


def test_plan_fills_an_open_night_and_respects_the_threshold():
    days = ["2026-11-13", "2026-11-14"]
    mine = [_row(f"Core{i}", 30, 2000) for i in range(11)] + [_row("S1", 15, 900), _row("S2", 16, 950)]
    # Only 8 of mine play on the 13th, so 2 slots are open; S1/S2 don't play.
    proj = {f"Core{i}": {days[0]: 30.0 if i < 8 else 0.0, days[1]: 30.0} for i in range(11)}
    free = [_row("Hot", 25, 1200), _row("Meh", 10, 800)]
    proj.update({"Hot": {days[0]: 30.0, days[1]: 30.0}, "Meh": {days[0]: 5.0, days[1]: 0.0}})

    plan = planner.plan_week(mine, free, proj, days, adds_used=5)
    assert [m["add"] for m in plan["moves"]] == ["Hot"]     # Meh's +5 is under the bar
    assert plan["moves"][0]["drop"] in ("S1", "S2")
    assert plan["adds_left"] == 1
    assert plan["open_slots_before"][days[0]] == 2 and plan["open_slots_after"][days[0]] == 1


def test_plan_waits_for_waivers_and_stops_at_zero_adds():
    days = ["2026-11-13", "2026-11-14"]
    mine = [_row(f"Core{i}", 30, 2000) for i in range(9)] + [_row("S1", 15, 900), _row("S2", 16, 950)]
    proj = {f"Core{i}": {d: 30.0 for d in days} for i in range(9)}
    free = [_row("Claimed", 30, 1500, waiver_until=days[1])]
    proj["Claimed"] = {d: 30.0 for d in days}

    plan = planner.plan_week(mine, free, proj, days, adds_used=6)
    assert plan["moves"][0]["day"] == days[1]               # can't add before waivers clear
    assert planner.plan_week(mine, free, proj, days, adds_used=7)["moves"] == []


def test_out_core_player_goes_to_ir_first():
    days = ["2026-11-13"]
    mine = [_row(f"Core{i}", 30, 2000) for i in range(11)] + [_row("S1", 15, 900), _row("S2", 16, 950)]
    mine[0]["injury"] = "OUT"
    plan = planner.plan_week(mine, [], {}, days, adds_used=0)
    assert plan["ir_moves"] == ["Core0"]
