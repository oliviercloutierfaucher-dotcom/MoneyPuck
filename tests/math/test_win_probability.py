"""Phase 2: Win probability model tests."""

from app.core.agents import EdgeScoringAgent
from app.math.math_utils import (
    logistic_win_probability,
    prediction_confidence,
)
from app.core.models import TeamMetrics


def test_logistic_equal_strength_no_home_ice():
    home_p, away_p = logistic_win_probability(0.0, 0.0, home_advantage=0.0)
    assert abs(home_p - 0.5) < 0.001
    assert abs(away_p - 0.5) < 0.001


def test_logistic_equal_strength_with_home_ice():
    home_p, away_p = logistic_win_probability(0.0, 0.0, home_advantage=0.15)
    assert home_p > 0.5
    assert away_p < 0.5
    assert abs(home_p + away_p - 1.0) < 0.001


def test_logistic_strong_vs_weak():
    home_p, _ = logistic_win_probability(1.5, -1.0, home_advantage=0.15)
    assert home_p > 0.75  # strong home team should dominate
    assert home_p < 0.99  # but not 99%


def test_logistic_symmetry():
    h1, _ = logistic_win_probability(1.0, 0.0, home_advantage=0.0)
    _, a2 = logistic_win_probability(0.0, 1.0, home_advantage=0.0)
    assert abs(h1 - a2) < 0.001  # symmetric


def test_prediction_confidence_zero_games():
    conf = prediction_confidence(0, 0)
    assert conf == 0.05  # minimum floor prevents zero-confidence lockout


def test_prediction_confidence_many_games():
    conf = prediction_confidence(60, 60)
    assert conf > 0.75


def test_prediction_confidence_mixed():
    conf = prediction_confidence(5, 40)
    # avg = 22.5, confidence = 22.5 / (22.5 + 15) = 0.6
    assert 0.55 < conf < 0.65


def test_edge_scoring_with_team_metrics():
    strength = {
        "MTL": TeamMetrics(
            xg_share=0.55, home_strength=0.5, away_strength=0.3, games_played=40, composite=0.5,
        ),
        "TOR": TeamMetrics(
            xg_share=0.48, home_strength=0.1, away_strength=-0.2, games_played=40, composite=-0.1,
        ),
    }
    home_p, away_p, conf = EdgeScoringAgent._estimate_win_probability("MTL", "TOR", strength)
    assert home_p > 0.5  # MTL at home should be favored
    assert away_p < 0.5
    assert conf > 0.5  # Both teams have 40 games


def test_edge_scoring_unknown_team():
    strength = {
        "MTL": TeamMetrics(home_strength=0.5, away_strength=0.3, games_played=40),
    }
    home_p, away_p, conf = EdgeScoringAgent._estimate_win_probability("MTL", "UNKNOWN", strength)
    assert home_p == 0.5
    assert away_p == 0.5
    assert conf == 0.0
