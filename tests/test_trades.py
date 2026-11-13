import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import trades  # noqa: E402

POS = "PG,SG,SF,PF,C,G,F,UT"


def _p(name, ros, espn_avg, owner, games_left=50.0, espn_games=10, **extra):
    return {"name": name, "value_ros": ros, "value_fpg": ros / games_left, "games_left": games_left,
            "espn_avg": espn_avg, "espn_games": espn_games, "rostered_by": owner, "positions": POS, **extra}


def test_espn_value_uses_projection_for_tiny_samples():
    hurt = _p("Hurt", 1500, -2.0, "T", espn_games=1, espn_proj_avg=30.0)
    assert trades.espn_value(hurt) == 30.0 * 50.0
    assert trades.espn_value(_p("Vet", 1500, 40.0, "T")) == 40.0 * 50.0


def test_open_spot_is_worth_the_lesser_of_free_agent_and_your_cut():
    mine = [_p("A", 2000, 40, "Me"), _p("B", 1800, 36, "Me"), _p("Weak", 900, 18, "Me")]
    theirs = [_p("Star", 3000, 55, "Them"), _p("Scrub", 500, 10, "Them")]
    free = [_p("BestFA", 1700, 30, None)]
    t = trades.assess(mine[:2], theirs[:1], mine, theirs, free)
    # Open spot credited at Weak (900), not BestFA (1700): 3000 + 900 vs 3800.
    assert t["my_get"] == 3900 and t["my_give"] == 3800
    assert t["their_drop"] == ["Scrub"]


def test_a_throw_in_you_would_cut_anyway_adds_nothing():
    mine = [_p("A", 2000, 40, "Me"), _p("Junk", 600, 12, "Me"), _p("Next", 1300, 25, "Me")]
    theirs = [_p("Star", 2100, 42, "Them"), _p("Bench", 900, 18, "Them")]
    free = [_p("BestFA", 1700, 30, None)]
    one = trades.assess(mine[:1], theirs[:1], mine, theirs, free)
    two = trades.assess(mine[:2], theirs[:1], mine, theirs, free)
    assert two["my_gain"] == one["my_gain"]


def test_find_keeps_bands_caps_and_untouchables():
    mine = [_p(f"M{i}", 1500 + 10 * i, 30, "Me") for i in range(10)]
    theirs = [_p("Target", 1600, 25, "Them")] + [_p(f"T{i}", 1000, 20, "Them") for i in range(9)]
    rows = mine + theirs
    found = trades.find(rows, "Me", universe={"Target"})
    assert found, "a 1-for-1 that ESPN rates higher for them should be found"
    for t in found:
        assert trades.MY_MIN <= t["my_pct"] <= trades.MY_MAX and t["their_pct"] >= trades.THEIR_MIN
    assert len({tuple(t["get"]) for t in found}) == len(found) <= trades.MAX_PER_TEAM
    blocked = trades.find(rows, "Me", {"Target"}, untouchables={f"M{i}" for i in range(10)})
    assert blocked == []
