import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import availability  # noqa: E402


def test_durable_beats_injury_prone():
    durable = availability.projected_games([78, 76, 74, 79, 77], age=27)
    injured = availability.projected_games([48, 52, 45, 55, 50], age=27)
    assert durable > injured
    assert durable > 70
    assert injured < 65


def test_one_fluke_season_barely_moves_durable_career():
    # A career iron-man who lost last year to a fluke should stay durable.
    steady = availability.projected_games([73, 71, 74, 70, 72], age=30)
    fluke = availability.projected_games([40, 71, 74, 70, 72], age=30)
    assert steady - fluke < 12  # dented, not tanked
    assert fluke > 60


def test_age_penalty_applied():
    young = availability.projected_games([70, 70, 70], age=25)
    old = availability.projected_games([70, 70, 70], age=38)
    assert old < young


def test_bounds_respected():
    assert availability.projected_games([82, 82, 82], age=24) <= availability.GAMES_CEIL
    assert availability.projected_games([5, 3, 4], age=40) >= availability.GAMES_FLOOR


def test_missing_history_uses_default():
    g = availability.projected_games([], age=None)
    assert availability.GAMES_FLOOR <= g <= availability.GAMES_CEIL


def test_season_value_rewards_availability():
    # A durable 34 FP/G player beats a fragile 38 FP/G one on season total.
    durable = availability.season_value(34.0, 78)
    fragile = availability.season_value(38.0, 50)
    assert durable > fragile
