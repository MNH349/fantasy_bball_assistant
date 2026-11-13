import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import tonight  # noqa: E402

PACE = {"AAA": 100.0, "BBB": 104.0}


def _row(**kw):
    return {"name": "P", "nba_id": 1, "pro_team": "AAA", "value_fpg": 30.0, "minutes": 30.0,
            "positions": "PG,SG,G,UT", "injury": "ACTIVE", **kw}


def test_no_game_or_out_projects_zero():
    assert tonight.project(_row(), None, None, 0.0, PACE) == 0.0
    assert tonight.project(_row(injury="OUT"), "BBB", None, 0.0, PACE) == 0.0


def test_form_minutes_and_pace_adjustments():
    form = {"fpg": 40.0, "games": 5}
    # 0.7*30 + 0.3*40 = 33; +3 inherited minutes at 1.1 FP/min = 36.3; pace 102/100.
    assert tonight.project(_row(), "BBB", form, 3.0, PACE) == round(36.3 * 1.02, 1)


def test_day_to_day_is_discounted():
    assert tonight.project(_row(injury="DAY_TO_DAY"), "AAA", None, 0.0, PACE) == 24.0


def test_inherited_minutes_go_to_same_position_and_are_capped():
    logs = [{"player_id": 9, "team": "AAA", "game_id": f"g{i}", "game_date": f"2026-11-0{i}", "line": {}}
            for i in range(1, 6)]   # the injured starter played all 5 recent games
    rows = [
        {"name": "Hurt", "nba_id": 9, "pro_team": "AAA", "minutes": 34.0, "positions": "PG,G,UT", "injury": "OUT"},
        {"name": "Backup", "nba_id": 2, "pro_team": "AAA", "minutes": 20.0, "positions": "PG,SG,G,UT", "injury": "ACTIVE"},
        {"name": "Big", "nba_id": 3, "pro_team": "AAA", "minutes": 30.0, "positions": "C,UT", "injury": "ACTIVE"},
    ]
    extra = tonight.inherited_minutes(rows, logs)
    assert extra == {"Backup": tonight.MAX_EXTRA_MINUTES}   # 34 freed, capped; the C gets none
