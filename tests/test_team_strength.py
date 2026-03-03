"""Phase 1: Multi-factor team strength model tests."""

from app.agents import TeamStrengthAgent
from app.math_utils import (
    composite_strength,
    exponential_decay_weight,
    regress_to_mean,
)


def test_exponential_decay_today_is_one():
    assert exponential_decay_weight(0) == 1.0


def test_exponential_decay_half_life():
    w = exponential_decay_weight(30, half_life=30)
    assert abs(w - 0.5) < 0.01


def test_exponential_decay_two_half_lives():
    w = exponential_decay_weight(60, half_life=30)
    assert abs(w - 0.25) < 0.01


def test_exponential_decay_negative_days():
    assert exponential_decay_weight(-5) == 0.0


def test_regress_to_mean_zero_games():
    assert regress_to_mean(0.6, n=0, k=20, prior=0.5) == 0.5


def test_regress_to_mean_equal_weight():
    result = regress_to_mean(0.6, n=20, k=20, prior=0.5)
    assert abs(result - 0.55) < 0.001


def test_regress_to_mean_many_games():
    result = regress_to_mean(0.6, n=80, k=20, prior=0.5)
    assert result >= 0.58  # mostly observed


def test_composite_strength_default_weights():
    metrics = {
        "xg_share": 1.0,
        "corsi_share": 1.0,
        "high_danger_share": 1.0,
        "shooting_pct": 1.0,
        "save_pct": 1.0,
        "pp_xg_per_60": 1.0,
        "pk_xg_against_per_60": 1.0,
    }
    result = composite_strength(metrics)
    # Only 7 of 16 default metrics supplied; full-weight normalization
    # pulls the result toward 0.0 instead of treating partial data as complete.
    # Available weight = 0.12+0.06+0.10+0.06+0.06+0.03+0.03 = 0.46
    # Result = 0.46 / 1.00 = 0.46
    assert abs(result - 0.46) < 0.001


def test_composite_strength_mixed():
    """Verify composite_strength with explicit weights produces expected result."""
    metrics = {
        "xg_share": 2.0,
        "corsi_share": -1.0,
        "high_danger_share": 0.0,
    }
    weights = {"xg_share": 0.35, "corsi_share": 0.15, "high_danger_share": 0.20}
    result = composite_strength(metrics, weights)
    # All weight keys are present in metrics, so full_w == available_w.
    # 0.35*2 + 0.15*(-1) + 0.20*0 = 0.55 / 0.70 = 0.7857
    expected = (0.35 * 2.0 + 0.15 * -1.0 + 0.20 * 0.0) / 0.70
    assert abs(result - expected) < 0.001


def test_composite_strength_missing_metrics_pulls_toward_zero():
    """Missing metrics should pull the composite toward 0.0 (league average).

    When only a fraction of the expected metrics are available, the result
    must be lower than if those same metrics were the only ones defined,
    because the full weight denominator includes the missing weights.
    """
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}

    # All metrics present -> weighted average is exact.
    all_present = composite_strength({"a": 1.0, "b": 1.0, "c": 1.0}, weights)
    assert abs(all_present - 1.0) < 0.001

    # Only metric "a" present -> strong z-score is diluted by missing data.
    sparse = composite_strength({"a": 1.0}, weights)
    # Expected: 0.5 * 1.0 / 1.0 = 0.5 (pulled toward 0.0)
    assert abs(sparse - 0.5) < 0.001
    assert sparse < all_present

    # No metrics present -> result is exactly 0.0 (league average).
    empty = composite_strength({}, weights)
    assert empty == 0.0


def _make_game_row(home, away, xg=0.5, corsi=0.5, hd_for=5, hd_against=5,
                   gf=3, ga=3, sf=30, sa=30, game_date="2026-01-15"):
    return {
        "homeTeamCode": home,
        "awayTeamCode": away,
        "xGoalsPercentage": str(xg),
        "corsiPercentage": str(corsi),
        "highDangerShotsFor": str(hd_for),
        "highDangerShotsAgainst": str(hd_against),
        "goalsFor": str(gf),
        "goalsAgainst": str(ga),
        "shotsOnGoalFor": str(sf),
        "shotsOnGoalAgainst": str(sa),
        "xGoalsFor": "2.5",
        "xGoalsAgainst": "2.0",
        "penaltiesFor": "3",
        "penaltiesAgainst": "4",
        "gameDate": game_date,
    }


def test_team_strength_agent_returns_team_metrics():
    rows = [
        _make_game_row("MTL", "TOR", xg=0.55, corsi=0.52, hd_for=8, hd_against=5),
        _make_game_row("TOR", "MTL", xg=0.48, corsi=0.49, hd_for=4, hd_against=6),
    ]
    result = TeamStrengthAgent().run(rows)
    assert "MTL" in result
    assert "TOR" in result
    # MTL should be stronger (higher xG in both games)
    assert result["MTL"].composite > result["TOR"].composite


def test_team_strength_agent_home_away_splits():
    rows = [
        _make_game_row("MTL", "TOR", xg=0.60, game_date="2026-01-10"),
        _make_game_row("TOR", "MTL", xg=0.55, game_date="2026-01-12"),
    ]
    result = TeamStrengthAgent().run(rows)
    # MTL home metrics from game 1 (xg=0.60) vs away from game 2
    assert result["MTL"].home_strength != result["MTL"].away_strength


def test_team_strength_agent_empty_input():
    result = TeamStrengthAgent().run([])
    assert result == {}


def test_team_strength_agent_games_played():
    rows = [
        _make_game_row("MTL", "TOR", game_date="2026-01-10"),
        _make_game_row("MTL", "BOS", game_date="2026-01-12"),
    ]
    result = TeamStrengthAgent().run(rows)
    assert result["MTL"].games_played == 2
    assert result["TOR"].games_played == 1
    assert result["BOS"].games_played == 1
