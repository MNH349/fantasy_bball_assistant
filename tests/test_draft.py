import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import draft  # noqa: E402


def _rec(name, pts, minutes=30.0, gp_history=(70, 70), age=27):
    return {
        "name": name,
        "age": age,
        "gp_history": list(gp_history),
        "proj_line": {"PTS": pts, "MIN": minutes},
    }


def test_compute_rows_makes_season_value():
    formula = {"PTS": 1.0}
    rows = draft.compute_darko_rows([_rec("A", 20, minutes=30)], formula)
    assert rows[0]["darko_fpg"] == 20.0
    assert rows[0]["darko_value"] == 20.0 * rows[0]["games"]
    assert rows[0]["seasons"] == 2


def test_min_minutes_filter():
    formula = {"PTS": 1.0}
    rows = draft.compute_darko_rows(
        [_rec("Bench", 30, minutes=6)], formula, min_minutes=12.0
    )
    assert rows == []


def test_seasons_counts_history_length():
    formula = {"PTS": 1.0}
    soph = draft.compute_darko_rows([_rec("Soph", 18, gp_history=(70,))], formula)
    assert soph[0]["seasons"] == 1


def test_finalize_ranks_by_value():
    rows = [
        {"name": "Low", "value": 1000},
        {"name": "High", "value": 3000},
        {"name": "Mid", "value": 2000},
    ]
    ranked = draft.finalize(rows)
    assert [r["name"] for r in ranked] == ["High", "Mid", "Low"]
    assert ranked[0]["rank"] == 1 and ranked[0]["tier"] == "T1 Elite"
