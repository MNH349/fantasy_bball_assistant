import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import team_context  # noqa: E402


def _rec(name, team, usg, minutes, pts, reb):
    return {
        "name": name,
        "team": team,
        "usg": usg,
        "proj_line": {"PTS": pts, "REB": reb, "MIN": minutes},
    }


def test_crowded_team_is_faded():
    # Six ball-dominant stars: usage demand = 6 * 0.30 * 38 / 48 = 1.43 (>1).
    records = [_rec(f"Star{i}", "PHL", 0.30, 38, 25, 8) for i in range(6)]
    before = records[0]["proj_line"]["PTS"]
    team_context.adjust(records)
    assert records[0]["proj_line"]["PTS"] < before  # ball stat compressed
    assert records[0]["usg_factor"] < 1.0


def test_minutes_over_subscription_compresses():
    # 7 players * 36 min = 252 > 240 -> minutes compress.
    records = [_rec(f"P{i}", "BOS", 0.15, 36, 10, 5) for i in range(7)]
    team_context.adjust(records)
    assert records[0]["min_factor"] < 1.0
    assert records[0]["proj_line"]["REB"] < 5  # rebounds follow minutes


def test_normal_team_untouched():
    # Balanced: 5 players * 30 min = 150 min, usage sums modestly -> no compression.
    records = [_rec(f"P{i}", "SAC", 0.16, 30, 12, 5) for i in range(5)]
    team_context.adjust(records)
    assert records[0]["proj_line"]["PTS"] == 12
    assert records[0]["min_factor"] == 1.0


def test_ball_stats_faded_more_than_rebounds():
    # Oversubscribed on both axes; PTS (ball) should drop by more than REB (minutes only).
    records = [_rec(f"S{i}", "LAL", 0.32, 38, 20, 10) for i in range(5)]
    team_context.adjust(records)
    r = records[0]
    pts_ratio = r["proj_line"]["PTS"] / 20
    reb_ratio = r["proj_line"]["REB"] / 10
    assert pts_ratio < reb_ratio


def test_single_player_team_not_adjusted():
    records = [_rec("Solo", "UTA", 0.35, 40, 28, 9)]
    team_context.adjust(records)
    assert records[0]["proj_line"]["PTS"] == 28


def test_player_without_team_ignored():
    records = [_rec("NoTeam", None, 0.30, 36, 25, 8), _rec("A", "MIA", 0.3, 36, 25, 8)]
    team_context.adjust(records)
    assert records[0]["proj_line"]["PTS"] == 25  # untouched
