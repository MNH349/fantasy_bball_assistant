import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import ranking  # noqa: E402


def _rows(values, minutes=None):
    return [{"name": f"P{i}", "value_ros": v, "minutes": (minutes or {}).get(f"P{i}", 30.0)}
            for i, v in enumerate(values)]


def test_watch_list_and_fallers():
    # P_i is ranked i+1 last week (values 3000, 2990, ...).
    previous = _rows([3000 - 10 * i for i in range(170)])
    current = _rows([3000 - 10 * i for i in range(170)])
    current[165]["value_ros"] = 1605   # rank 166 -> 141: +25, inside the watch band
    current[10]["value_ros"] = 2700    # rank 11 -> 30: -19, still core, so a faller
    rk = ranking.weekly(current, previous)
    assert [r["name"] for r in rk["watch"]] == ["P165"]
    assert [r["name"] for r in rk["fallers"]] == ["P10"]
    assert rk["fallers"][0]["rank"] == 30 and rk["fallers"][0]["tag"] == "falling"
    assert len(rk["top"]) == ranking.TOP_N and len(rk["core"]) == ranking.CORE_SIZE


def test_minutes_jump_also_qualifies():
    previous = _rows([3000 - 10 * i for i in range(170)])
    current = _rows([3000 - 10 * i for i in range(170)], minutes={"P130": 35.0})
    assert "P130" in {r["name"] for r in ranking.weekly(current, previous)["watch"]}


def test_new_players_have_no_move():
    rk = ranking.weekly(_rows([100, 90]), [])
    assert rk["top"][0]["rank_change"] is None
