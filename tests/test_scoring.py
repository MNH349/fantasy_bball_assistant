import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import scoring  # noqa: E402


def test_fantasy_points_known_line():
    formula = {"PTS": 1.0, "REB": 1.0, "AST": 2.0, "STL": 4.0, "BLK": 4.0, "TO": -2.0}
    line = {"PTS": 20, "REB": 10, "AST": 5, "STL": 2, "BLK": 1, "TO": 3}
    # 20 + 10 + 10 + 8 + 4 - 6 = 46
    assert scoring.fantasy_points(line, formula) == 46.0


def test_missing_keys_treated_as_zero():
    formula = {"PTS": 1.0, "3PM": 1.0, "BLK": 4.0}
    line = {"PTS": 15}  # no 3PM, no BLK
    assert scoring.fantasy_points(line, formula) == 15.0


def test_negative_weights_penalize():
    formula = {"FGA": -1.0, "FGM": 2.0}
    line = {"FGM": 8, "FGA": 18}
    # 16 - 18 = -2
    assert scoring.fantasy_points(line, formula) == -2.0


def test_default_scoring_has_all_core_stats():
    for key in ("PTS", "REB", "AST", "STL", "BLK", "TO"):
        assert key in scoring.DEFAULT_SCORING
