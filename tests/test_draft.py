import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import draft, projections  # noqa: E402


def _rec(name, age, gp, pts, reb, ast):
    return {
        "player_id": hash(name) % 100000,
        "name": name,
        "age": age,
        "gp": gp,
        "line": {"PTS": pts, "REB": reb, "AST": ast},
    }


def test_board_orders_by_projected_points():
    formula = {"PTS": 1.0, "REB": 1.0, "AST": 2.0}
    records = [
        _rec("Star", 25, 70, 28, 8, 8),      # high
        _rec("Role", 29, 70, 9, 4, 2),       # low
        _rec("Mid", 27, 70, 18, 6, 4),       # middle
    ]
    board = draft.build_board(records, formula)
    names_in_order = [r["name"] for r in board]
    assert names_in_order == ["Star", "Mid", "Role"]
    assert board[0]["rank"] == 1
    assert board[0]["tier"] == "T1 Elite"


def test_min_games_filter_excludes_small_sample():
    formula = {"PTS": 1.0}
    records = [
        _rec("Regular", 26, 65, 20, 0, 0),
        _rec("CupOfCoffee", 24, 5, 30, 0, 0),  # huge stats, tiny sample -> excluded
    ]
    board = draft.build_board(records, formula, min_games=20)
    assert [r["name"] for r in board] == ["Regular"]


def test_age_curve_growth_sign():
    # Young player projected up, old player projected down vs. baseline.
    young = projections.age_multiplier(22)
    old = projections.age_multiplier(35)
    assert young > 1.0
    assert old < 1.0
