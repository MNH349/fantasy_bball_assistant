import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import draft, projections  # noqa: E402


def _rec(name, age, pts, reb, ast, minutes=30.0, baseline=True):
    line = {"PTS": pts, "REB": reb, "AST": ast, "MIN": minutes}
    return {
        "name": name,
        "age": age,
        "proj_line": line,
        "baseline_line": dict(line) if baseline else None,
    }


def test_board_orders_by_projected_points():
    formula = {"PTS": 1.0, "REB": 1.0, "AST": 2.0}
    records = [
        _rec("Star", 25, 28, 8, 8),
        _rec("Role", 29, 9, 4, 2),
        _rec("Mid", 27, 18, 6, 4),
    ]
    board = draft.build_board(records, formula)
    assert [r["name"] for r in board] == ["Star", "Mid", "Role"]
    assert board[0]["rank"] == 1
    assert board[0]["tier"] == "T1 Elite"


def test_min_minutes_filter_excludes_bench():
    formula = {"PTS": 1.0}
    records = [
        _rec("Starter", 26, 20, 0, 0, minutes=32),
        _rec("Benchwarmer", 24, 30, 0, 0, minutes=6),  # big rate, tiny minutes -> out
    ]
    board = draft.build_board(records, formula, min_minutes=12.0)
    assert [r["name"] for r in board] == ["Starter"]


def test_growth_none_when_no_baseline():
    formula = {"PTS": 1.0}
    board = draft.build_board([_rec("Rookie", 20, 15, 3, 3, baseline=False)], formula)
    assert board[0]["growth"] is None
    assert board[0]["baseline_fpts_pg"] is None


def test_darko_line_conversion():
    # 100 possessions worth of pace/minutes -> per-100 rates pass through cleanly.
    rates = {
        "pace": 100.0, "usg_pct": 0.25,
        "pts_100": 30.0, "orb_100": 3.0, "drb_100": 7.0, "ast_100": 5.0,
        "blk_100": 1.0, "stl_100": 2.0, "tov_100": 3.0,
        "fta_100": 6.0, "fga_100": 20.0, "fg3a_100": 8.0,
        "fg_pct": 0.5, "ft_pct": 0.8, "fg3_pct": 0.4,
    }
    line = projections.darko_line(rates, minutes=48.0)  # 48 min @ pace 100 -> 100 poss
    assert round(line["PTS"]) == 30
    assert round(line["REB"]) == 10
    assert round(line["FGM"]) == 10  # 20 attempts * 0.5
    assert round(line["3PM"]) == 3   # 8 attempts * 0.4


def test_age_curve_growth_sign():
    assert projections.age_multiplier(22) > 1.0
    assert projections.age_multiplier(35) < 1.0
