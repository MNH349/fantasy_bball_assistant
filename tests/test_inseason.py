import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import inseason, inseason_report  # noqa: E402

# Minimal DARKO rates that make darko_line produce PTS only: at 48 minutes and
# pace 100, poss_per_100 = 1.0, so PTS = pts_100.
RATES = {
    "pace": 100.0, "usg_pct": 0.0, "pts_100": 30.0, "orb_100": 0.0, "drb_100": 0.0,
    "ast_100": 0.0, "blk_100": 0.0, "stl_100": 0.0, "tov_100": 0.0,
    "fta_100": 0.0, "fga_100": 0.0, "fg3a_100": 0.0,
    "fg_pct": 0.0, "ft_pct": 0.0, "fg3_pct": 0.0,
}
PTS_ONLY = {"PTS": 1.0}


def test_nudge_weight_ramps_with_sample():
    assert inseason.nudge_weight(0) == 0.0
    assert inseason.nudge_weight(20, k=20) == 0.5     # 50/50 at K games
    assert inseason.nudge_weight(60, k=20) > inseason.nudge_weight(20, k=20)


def test_project_player_blends_darko_and_actuals():
    # darko_fpg = 30 (rates), actual = 40; at gp=20,K=20 -> w=0.5 -> value 35.
    out = inseason.project_player(
        RATES, role_minutes=48.0, cur_line={"PTS": 40.0}, games_played=20,
        gp_history=[], age=None, formula=PTS_ONLY, games_week=3, team_games_left=70,
    )
    assert out["darko_fpg"] == 30.0
    assert out["actual_fpg"] == 40.0
    assert out["value_fpg"] == 35.0
    assert out["value_week"] == 35.0 * 3           # value_fpg x games_week
    assert out["games_week"] == 3


def test_project_player_no_games_is_pure_darko():
    out = inseason.project_player(
        RATES, role_minutes=48.0, cur_line={}, games_played=0,
        gp_history=[], age=None, formula=PTS_ONLY, games_week=4, team_games_left=70,
    )
    assert out["value_fpg"] == out["darko_fpg"] == 30.0


def test_team_counts_falls_back_to_average_when_unknown():
    team_dates = {"AAA": ["2026-10-26"]}
    assert inseason.team_counts(team_dates, "ZZZ", avg_week=3, avg_left=40) == (3, 40)


def test_droppable_protects_high_ros_players():
    mine = [
        {"name": "Star", "value_ros": 3000.0},
        {"name": "HurtStud", "value_ros": 2400.0, "injury": "OUT"},  # ROS stays high
        {"name": "Deadweight", "value_ros": 500.0},
    ]
    drops = inseason_report.droppable(mine, replacement_ros=1000.0)
    assert [r["name"] for r in drops] == ["Deadweight"]  # hurt stud is shielded
