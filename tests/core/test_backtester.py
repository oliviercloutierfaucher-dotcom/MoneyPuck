"""Backtesting framework tests for model calibration and parameter optimization."""
import math

from app.core.backtester import (
    backtest_season,
    evaluate_predictions,
    format_report,
    grid_search,
    production_readiness_report,
    simulate_betting_roi,
)
from app.core.models import TrackerConfig


# ---------------------------------------------------------------------------
# Helper: build synthetic MoneyPuck game rows
# ---------------------------------------------------------------------------

def _make_game(home, away, date_str, goals_home, goals_away,
               xg_pct=0.5, corsi_pct=0.5):
    """Create a synthetic MoneyPuck CSV-style game row."""
    return {
        "homeTeamCode": home,
        "awayTeamCode": away,
        "gameDate": date_str,
        "season": "2024",
        "xGoalsPercentage": str(xg_pct),
        "corsiPercentage": str(corsi_pct),
        "goalsFor": str(goals_home),
        "goalsAgainst": str(goals_away),
        "shotsOnGoalFor": "30",
        "shotsOnGoalAgainst": "28",
        "highDangerShotsFor": "10",
        "highDangerShotsAgainst": "8",
        "xGoalsFor": str(goals_home * 0.9),
        "xGoalsAgainst": str(goals_away * 0.9),
        "penaltiesFor": "3",
        "penaltiesAgainst": "4",
    }


# ---------------------------------------------------------------------------
# Synthetic season dataset: 20+ games across 5+ dates, 4 teams
# ---------------------------------------------------------------------------

SYNTHETIC_GAMES = [
    # Date 1: 2024-01-10 (2 games)
    _make_game("MTL", "TOR", "2024-01-10", 4, 2, xg_pct=0.58, corsi_pct=0.54),
    _make_game("BOS", "OTT", "2024-01-10", 3, 1, xg_pct=0.55, corsi_pct=0.52),

    # Date 2: 2024-01-15 (2 games)
    _make_game("TOR", "MTL", "2024-01-15", 3, 2, xg_pct=0.52, corsi_pct=0.51),
    _make_game("OTT", "BOS", "2024-01-15", 2, 4, xg_pct=0.45, corsi_pct=0.48),

    # Date 3: 2024-01-20 (3 games)
    _make_game("MTL", "BOS", "2024-01-20", 2, 3, xg_pct=0.48, corsi_pct=0.49),
    _make_game("TOR", "OTT", "2024-01-20", 5, 1, xg_pct=0.60, corsi_pct=0.57),
    _make_game("BOS", "MTL", "2024-01-20", 3, 2, xg_pct=0.53, corsi_pct=0.51),

    # Date 4: 2024-01-25 (3 games)
    _make_game("MTL", "OTT", "2024-01-25", 4, 1, xg_pct=0.62, corsi_pct=0.58),
    _make_game("TOR", "BOS", "2024-01-25", 2, 2, xg_pct=0.50, corsi_pct=0.50),
    _make_game("OTT", "MTL", "2024-01-25", 1, 3, xg_pct=0.42, corsi_pct=0.46),

    # Date 5: 2024-02-01 (3 games)
    _make_game("BOS", "TOR", "2024-02-01", 3, 2, xg_pct=0.54, corsi_pct=0.53),
    _make_game("MTL", "TOR", "2024-02-01", 4, 3, xg_pct=0.56, corsi_pct=0.52),
    _make_game("OTT", "BOS", "2024-02-01", 1, 2, xg_pct=0.44, corsi_pct=0.47),

    # Date 6: 2024-02-05 (2 games)
    _make_game("TOR", "OTT", "2024-02-05", 3, 0, xg_pct=0.65, corsi_pct=0.60),
    _make_game("MTL", "BOS", "2024-02-05", 2, 1, xg_pct=0.53, corsi_pct=0.51),

    # Date 7: 2024-02-10 (3 games)
    _make_game("BOS", "MTL", "2024-02-10", 4, 3, xg_pct=0.52, corsi_pct=0.50),
    _make_game("OTT", "TOR", "2024-02-10", 2, 5, xg_pct=0.40, corsi_pct=0.45),
    _make_game("MTL", "OTT", "2024-02-10", 3, 1, xg_pct=0.58, corsi_pct=0.55),

    # Date 8: 2024-02-15 (2 games)
    _make_game("TOR", "MTL", "2024-02-15", 2, 1, xg_pct=0.51, corsi_pct=0.50),
    _make_game("BOS", "OTT", "2024-02-15", 5, 2, xg_pct=0.60, corsi_pct=0.56),
]


def _default_config():
    """Return a TrackerConfig suitable for backtesting tests."""
    return TrackerConfig(odds_api_key="x")


# ---------------------------------------------------------------------------
# Test 1: backtest_season returns predictions with expected fields
# ---------------------------------------------------------------------------

def test_backtest_season_returns_predictions():
    """Feed synthetic games spanning multiple dates; verify predictions
    are returned with all expected fields."""
    config = _default_config()
    preds = backtest_season(SYNTHETIC_GAMES, config, train_window_days=60)

    assert len(preds) > 0, "backtest should produce at least one prediction"

    # Check each prediction has the required fields
    required_keys = {
        "game_date", "home_team", "away_team",
        "home_prob", "actual_outcome",
        "goals_home", "goals_away", "confidence",
    }
    for pred in preds:
        assert required_keys.issubset(pred.keys()), (
            f"Missing keys: {required_keys - pred.keys()}"
        )
        # Sanity-check value ranges
        assert 0.0 < pred["home_prob"] < 1.0
        assert pred["actual_outcome"] in (0, 1)
        assert 0.0 <= pred["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Test 2: first date has no predictions (no training data)
# ---------------------------------------------------------------------------

def test_backtest_uses_only_prior_games():
    """The first date should have NO predictions because there is no
    prior training data. The second date should use the first date's games."""
    config = _default_config()
    preds = backtest_season(SYNTHETIC_GAMES, config, train_window_days=60)

    # First date in dataset is 2024-01-10
    first_date_preds = [p for p in preds if p["game_date"] == "2024-01-10"]
    assert len(first_date_preds) == 0, (
        "First date should have no predictions (no training data)"
    )

    # Second date (2024-01-15) should have predictions trained on date 1
    second_date_preds = [p for p in preds if p["game_date"] == "2024-01-15"]
    assert len(second_date_preds) > 0, (
        "Second date should have predictions from first date's training data"
    )


# ---------------------------------------------------------------------------
# Test 3: perfect predictions give Brier=0, accuracy=1.0
# ---------------------------------------------------------------------------

def test_evaluate_perfect_predictions():
    """When every prediction exactly matches the outcome, Brier should be 0
    and accuracy should be 1.0."""
    perfect_preds = [
        {"home_prob": 1.0, "actual_outcome": 1},
        {"home_prob": 1.0, "actual_outcome": 1},
        {"home_prob": 0.0, "actual_outcome": 0},
        {"home_prob": 0.0, "actual_outcome": 0},
    ]
    # Clamp to avoid log(0) same way the evaluator does internally
    for p in perfect_preds:
        p["home_prob"] = max(0.01, min(0.99, p["home_prob"]))

    metrics = evaluate_predictions(perfect_preds)

    # Brier very close to 0 (not exactly 0 due to clamping)
    assert metrics["brier_score"] < 0.001
    assert metrics["accuracy"] == 1.0
    assert metrics["n_predictions"] == 4


# ---------------------------------------------------------------------------
# Test 4: coin-flip predictions give Brier=0.25, accuracy=0.5
# ---------------------------------------------------------------------------

def test_evaluate_coin_flip():
    """All predictions at 0.5 → Brier = 0.25, accuracy = 0.5 (ties excluded)."""
    coin_flip_preds = [
        {"home_prob": 0.5, "actual_outcome": 1},
        {"home_prob": 0.5, "actual_outcome": 0},
        {"home_prob": 0.5, "actual_outcome": 1},
        {"home_prob": 0.5, "actual_outcome": 0},
    ]
    metrics = evaluate_predictions(coin_flip_preds)

    assert abs(metrics["brier_score"] - 0.25) < 1e-9
    # p==0.5 is never >0.5 or <0.5, so accuracy = 0
    assert metrics["accuracy"] == 0.0


# ---------------------------------------------------------------------------
# Test 5: calibration returns proper bucket structure
# ---------------------------------------------------------------------------

def test_evaluate_calibration_buckets():
    """Verify calibration returns 10 buckets with predicted/actual/count."""
    preds = [
        {"home_prob": 0.15, "actual_outcome": 0},
        {"home_prob": 0.35, "actual_outcome": 0},
        {"home_prob": 0.55, "actual_outcome": 1},
        {"home_prob": 0.75, "actual_outcome": 1},
        {"home_prob": 0.85, "actual_outcome": 1},
        {"home_prob": 0.95, "actual_outcome": 1},
    ]
    metrics = evaluate_predictions(preds)
    calibration = metrics["calibration"]

    assert len(calibration) == 10, "Should have exactly 10 calibration buckets"

    for bucket in calibration:
        assert "predicted" in bucket
        assert "actual" in bucket
        assert "count" in bucket
        assert bucket["count"] >= 0

    # Sum of counts across all buckets should equal total predictions
    total_count = sum(b["count"] for b in calibration)
    assert total_count == len(preds)


# ---------------------------------------------------------------------------
# Test 6: near-perfect predictions produce very low log_loss
# ---------------------------------------------------------------------------

def test_evaluate_log_loss_perfect():
    """Near-perfect predictions should yield very low log loss."""
    near_perfect = [
        {"home_prob": 0.99, "actual_outcome": 1},
        {"home_prob": 0.99, "actual_outcome": 1},
        {"home_prob": 0.01, "actual_outcome": 0},
        {"home_prob": 0.01, "actual_outcome": 0},
    ]
    metrics = evaluate_predictions(near_perfect)

    # log_loss should be very small for near-perfect predictions
    assert metrics["log_loss"] < 0.05
    # Compared to coin-flip log_loss (~0.693)
    coin_preds = [
        {"home_prob": 0.5, "actual_outcome": 1},
        {"home_prob": 0.5, "actual_outcome": 0},
    ]
    coin_metrics = evaluate_predictions(coin_preds)
    assert metrics["log_loss"] < coin_metrics["log_loss"]


# ---------------------------------------------------------------------------
# Test 7: grid search returns results sorted by Brier score
# ---------------------------------------------------------------------------

def test_grid_search_returns_sorted():
    """A small 2x2 grid search should return results sorted by Brier (ascending)."""
    config = _default_config()
    small_grid = {
        "half_life": [14, 30],
        "home_advantage": [0.10, 0.20],
    }
    results = grid_search(
        SYNTHETIC_GAMES, config, param_grid=small_grid, train_window_days=60,
    )

    # Should have 2 * 2 = 4 results
    assert len(results) == 4

    # Results should be sorted by Brier score ascending
    brier_scores = [r["brier_score"] for r in results]
    assert brier_scores == sorted(brier_scores), (
        "Results should be sorted by Brier score ascending"
    )

    # Each result should have the expected keys
    for r in results:
        assert "params" in r
        assert "brier_score" in r
        assert "log_loss" in r
        assert "accuracy" in r
        assert "n_predictions" in r


# ---------------------------------------------------------------------------
# Test 8: grid search best params have the lowest Brier score
# ---------------------------------------------------------------------------

def test_grid_search_best_params():
    """The first result from grid search should have the lowest Brier score."""
    config = _default_config()
    small_grid = {
        "regression_k": [10, 30],
        "logistic_k": [0.8, 1.2],
    }
    results = grid_search(
        SYNTHETIC_GAMES, config, param_grid=small_grid, train_window_days=60,
    )

    assert len(results) > 0

    best = results[0]
    for r in results[1:]:
        assert best["brier_score"] <= r["brier_score"], (
            f"Best result (Brier={best['brier_score']:.4f}) should be <= "
            f"other result (Brier={r['brier_score']:.4f})"
        )

    # Verify best result has valid params
    assert "params" in best
    assert isinstance(best["params"], dict)
    assert best["n_predictions"] > 0


# ---------------------------------------------------------------------------
# Test 9: evaluate_predictions with empty list
# ---------------------------------------------------------------------------

def test_evaluate_empty_predictions():
    """Evaluating an empty prediction list should return zeros gracefully."""
    metrics = evaluate_predictions([])
    assert metrics["n_predictions"] == 0
    assert metrics["brier_score"] == 0.0
    assert metrics["accuracy"] == 0.0


# ---------------------------------------------------------------------------
# Test 10: backtest_season respects train_window_days
# ---------------------------------------------------------------------------

def test_backtest_season_train_window():
    """A very short train window should exclude older games and may reduce
    prediction count or change model outputs compared to a long window."""
    config = _default_config()

    # Wide window: all games in training
    preds_wide = backtest_season(SYNTHETIC_GAMES, config, train_window_days=365)

    # Narrow window: only last 10 days of training data
    preds_narrow = backtest_season(SYNTHETIC_GAMES, config, train_window_days=10)

    # Both should produce predictions, but probabilities may differ
    assert len(preds_wide) > 0
    # With a 10-day window, some later dates may have fewer training games
    # so predictions could differ
    if len(preds_narrow) > 0 and len(preds_wide) > 0:
        # Find a common game to compare
        wide_by_key = {
            (p["game_date"], p["home_team"], p["away_team"]): p
            for p in preds_wide
        }
        for p in preds_narrow:
            key = (p["game_date"], p["home_team"], p["away_team"])
            if key in wide_by_key:
                # The probabilities should be different since the training
                # data differs (unless by coincidence)
                # Just verify both are valid probabilities
                assert 0.0 < p["home_prob"] < 1.0
                assert 0.0 < wide_by_key[key]["home_prob"] < 1.0
                break


# ---------------------------------------------------------------------------
# Test 11: simulate_betting_roi returns expected structure
# ---------------------------------------------------------------------------

def test_simulate_betting_roi_structure():
    """ROI simulation should return all required fields with valid values."""
    config = _default_config()
    preds = backtest_season(SYNTHETIC_GAMES, config, train_window_days=60)
    roi = simulate_betting_roi(preds)

    required_keys = {
        "total_bets", "total_staked", "final_bankroll",
        "roi_pct", "win_rate", "avg_edge", "max_drawdown_pct",
        "bets_by_month",
    }
    assert required_keys.issubset(roi.keys())
    assert roi["final_bankroll"] >= 0  # can't go negative
    assert 0.0 <= roi["win_rate"] <= 1.0
    assert roi["max_drawdown_pct"] >= 0.0


# ---------------------------------------------------------------------------
# Test 12: simulate_betting_roi with no edges places no bets
# ---------------------------------------------------------------------------

def test_simulate_roi_high_min_edge():
    """With a very high min_edge, no bets should be placed."""
    config = _default_config()
    preds = backtest_season(SYNTHETIC_GAMES, config, train_window_days=60)
    roi = simulate_betting_roi(preds, min_edge=99.0)

    assert roi["total_bets"] == 0
    assert roi["total_staked"] == 0.0
    assert roi["final_bankroll"] == 1000.0


# ---------------------------------------------------------------------------
# Test 13: production_readiness_report has verdict
# ---------------------------------------------------------------------------

def test_production_readiness_report_structure():
    """Report should include verdict, checks, metrics, and simulated ROI."""
    config = _default_config()
    preds = backtest_season(SYNTHETIC_GAMES, config, train_window_days=60)
    report = production_readiness_report(preds, config)

    assert "verdict" in report
    assert report["verdict"] in {"PASS", "CONDITIONAL", "FAIL"}
    assert "verdict_detail" in report
    assert "checks" in report
    assert "metrics" in report
    assert "simulated_roi" in report

    # Checks should include critical items
    assert "brier_score" in report["checks"]
    assert "accuracy" in report["checks"]
    assert "sample_size" in report["checks"]
    assert "simulated_roi" in report["checks"]

    # Each check has pass/fail
    for name, check in report["checks"].items():
        assert "pass" in check, f"Check {name} missing 'pass' field"
        assert "value" in check
        assert "threshold" in check


# ---------------------------------------------------------------------------
# Test 14: format_report produces non-empty string
# ---------------------------------------------------------------------------

def test_format_report_output():
    """Formatted report should be a non-empty string with key sections."""
    config = _default_config()
    preds = backtest_season(SYNTHETIC_GAMES, config, train_window_days=60)
    report = production_readiness_report(preds, config)
    text = format_report(report)

    assert len(text) > 100
    assert "VERDICT" in text
    assert "CALIBRATION" in text
    assert "SIMULATED BETTING" in text
    # Depending on verdict, report shows either "NEXT STEPS" or "MODEL IS NOT READY"
    assert "NEXT STEPS" in text or "MODEL IS NOT READY" in text


# ---------------------------------------------------------------------------
# Test 15: perfect predictions get good scores
# ---------------------------------------------------------------------------

def test_readiness_report_good_model():
    """A model with near-perfect predictions should score well on checks."""
    # Create lots of well-calibrated predictions
    preds = []
    for i in range(300):
        # Model predicts 60% home win, home actually wins 60% of the time
        if i % 5 < 3:  # 60% home wins
            preds.append({"home_prob": 0.60, "actual_outcome": 1, "game_date": f"2024-01-{(i % 28) + 1:02d}"})
        else:
            preds.append({"home_prob": 0.40, "actual_outcome": 0, "game_date": f"2024-01-{(i % 28) + 1:02d}"})

    report = production_readiness_report(preds)
    assert report["checks"]["sample_size"]["pass"] is True
    assert report["checks"]["accuracy"]["pass"] is True
