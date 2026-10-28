import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import schedule  # noqa: E402

TEAM_DATES = {"AAA": ["2026-10-26", "2026-10-28", "2026-11-02", "2026-11-05"]}


def test_current_period_is_monday_to_sunday():
    # 2026-10-27 is a Tuesday; the period is Mon 10-26 .. Sun 11-01.
    assert schedule.current_period(date(2026, 10, 27)) == ("2026-10-26", "2026-11-01")


def test_games_in_period_counts_inclusive_window():
    start, end = schedule.current_period(date(2026, 10, 27))
    assert schedule.games_in_period(TEAM_DATES, "AAA", start, end) == 2  # 10-26, 10-28


def test_games_remaining_counts_on_or_after():
    assert schedule.games_remaining(TEAM_DATES, "AAA", "2026-10-28") == 3  # 28, 11-02, 11-05


def test_unknown_team_is_zero():
    assert schedule.games_remaining(TEAM_DATES, "ZZZ", "2026-10-01") == 0


def test_regular_season_filter():
    assert schedule._is_regular_season("0022600001")   # '2' third char
    assert not schedule._is_regular_season("0012600001")  # preseason
