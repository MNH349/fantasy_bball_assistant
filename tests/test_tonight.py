import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import tonight  # noqa: E402

PACE = {"AAA": 100.0, "BBB": 104.0}


def _row(**kw):
    return {"name": "P", "nba_id": 1, "pro_team": "AAA", "value_fpg": 30.0, "minutes": 30.0,
            "positions": "PG,SG,G,UT", "injury": "ACTIVE", **kw}


def test_no_game_or_out_projects_zero():
    assert tonight.project(_row(), None, 0.0, PACE) == 0.0
    assert tonight.project(_row(injury="OUT"), "BBB", 0.0, PACE) == 0.0


def test_minutes_and_pace_adjustments():
    # 30 FP/G over 30 min; +3 inherited minutes = 33; game pace (100+104)/2 vs own 100.
    assert tonight.project(_row(), "BBB", 3.0, PACE) == round(33.0 * 1.02, 1)


def test_day_to_day_is_discounted():
    assert tonight.project(_row(injury="DAY_TO_DAY"), "AAA", 0.0, PACE) == 30.0 * tonight.DTD_FACTOR


def test_inherited_minutes_go_to_same_position_and_are_capped():
    logs = [{"player_id": 9, "team": "AAA", "game_id": f"g{i}", "game_date": f"2026-11-0{i}", "line": {}}
            for i in range(1, 6)]   # the injured starter played all 5 recent games
    rows = [
        {"name": "Hurt", "nba_id": 9, "pro_team": "AAA", "minutes": 34.0, "positions": "PG,G,UT", "injury": "OUT"},
        {"name": "Backup", "nba_id": 2, "pro_team": "AAA", "minutes": 20.0, "positions": "PG,SG,G,UT", "injury": "ACTIVE"},
        {"name": "Big", "nba_id": 3, "pro_team": "AAA", "minutes": 30.0, "positions": "C,UT", "injury": "ACTIVE"},
    ]
    extra = tonight.inherited_minutes(rows, logs)
    assert extra == {"Backup": tonight.MAX_EXTRA_MINUTES}   # half of 34 = 17 freed, capped; the C gets none


def test_only_half_of_the_minutes_move():
    logs = [{"player_id": 9, "team": "AAA", "game_id": f"g{i}", "game_date": f"2026-11-0{i}", "line": {}}
            for i in range(1, 6)]
    rows = [
        {"name": "Hurt", "nba_id": 9, "pro_team": "AAA", "minutes": 16.0, "positions": "PG,G,UT", "injury": "OUT"},
        {"name": "Backup", "nba_id": 2, "pro_team": "AAA", "minutes": 20.0, "positions": "PG,G,UT", "injury": "ACTIVE"},
    ]
    assert tonight.inherited_minutes(rows, logs) == {"Backup": 8.0}  # 16 x 0.5, under the cap
