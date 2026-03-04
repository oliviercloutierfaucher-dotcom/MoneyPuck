"""Historical backtesting framework for model calibration and parameter optimization."""
from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from app.core.agents import TeamStrengthAgent
from app.math.math_utils import (
    DEFAULT_METRIC_WEIGHTS,
    logistic_win_probability,
    prediction_confidence,
)
from app.core.models import TrackerConfig


# League average save percentage (used as baseline)
LEAGUE_AVG_SAVE_PCT = 0.905


def backtest_season(
    games_rows: list[dict[str, str]],
    config: TrackerConfig,
    train_window_days: int = 60,
) -> list[dict[str, Any]]:
    """Replay a season of MoneyPuck data to evaluate model predictions.

    For each game date, uses only games BEFORE that date (rolling window)
    to build team strength, then predicts outcomes for that date's games.
    Compares predictions against actual outcomes (goalsFor/goalsAgainst).

    Parameters
    ----------
    games_rows:
        Full season of MoneyPuck CSV rows with gameDate, homeTeamCode,
        awayTeamCode, goalsFor, goalsAgainst, etc.
    config:
        TrackerConfig for model parameters.
    train_window_days:
        Only use games from the last N days for training (default 60).
        Earlier games are excluded entirely (not just down-weighted).

    Returns a list of prediction dicts, each containing:
        - game_date, home_team, away_team
        - home_prob (model prediction)
        - actual_outcome: 1 if home won, 0 if away won
        - goals_home, goals_away
        - confidence
    """
    # Read config params with safe defaults
    half_life = getattr(config, "half_life", 30.0)
    regression_k = getattr(config, "regression_k", 20)
    home_advantage = getattr(config, "home_advantage", 0.15)
    logistic_k = getattr(config, "logistic_k", 1.0)

    # Parse dates and sort games
    date_fmt = "%Y-%m-%d"
    games_with_dates: list[tuple[datetime, dict[str, str]]] = []
    for row in games_rows:
        raw_date = row.get("gameDate", "")[:10]
        try:
            dt = datetime.strptime(raw_date, date_fmt)
        except ValueError:
            continue
        games_with_dates.append((dt, row))

    games_with_dates.sort(key=lambda x: x[0])

    # Group by date
    date_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for dt, row in games_with_dates:
        date_groups[dt.strftime(date_fmt)].append(row)

    sorted_dates = sorted(date_groups.keys())

    predictions: list[dict[str, Any]] = []

    for i, test_date_str in enumerate(sorted_dates):
        test_dt = datetime.strptime(test_date_str, date_fmt)

        # Collect training rows: all games BEFORE this date
        train_rows: list[dict[str, str]] = []
        cutoff_dt = test_dt - timedelta(days=train_window_days)
        for dt, row in games_with_dates:
            if dt >= test_dt:
                break
            if dt >= cutoff_dt:
                train_rows.append(row)

        # Need some training data to make predictions
        if not train_rows:
            continue

        # Build team strength from training data
        agent = TeamStrengthAgent()
        agent.HALF_LIFE = half_life
        agent.REGRESSION_K = regression_k
        strength = agent.run(train_rows)

        # Predict each game on this date
        for game_row in date_groups[test_date_str]:
            home_team = game_row["homeTeamCode"]
            away_team = game_row["awayTeamCode"]

            home_metrics = strength.get(home_team)
            away_metrics = strength.get(away_team)

            if home_metrics is None or away_metrics is None:
                continue

            home_z = home_metrics.home_strength
            away_z = away_metrics.away_strength

            home_prob, _ = logistic_win_probability(
                home_z, away_z,
                home_advantage=home_advantage,
                k=logistic_k,
            )

            # Clamp to avoid log(0)
            home_prob = max(0.01, min(0.99, home_prob))

            conf = prediction_confidence(
                home_metrics.games_played, away_metrics.games_played,
            )

            # Actual outcome
            try:
                goals_home = int(float(game_row.get("goalsFor", "0")))
                goals_away = int(float(game_row.get("goalsAgainst", "0")))
            except (ValueError, TypeError):
                goals_home = 0
                goals_away = 0

            actual_outcome = 1 if goals_home > goals_away else 0

            predictions.append({
                "game_date": test_date_str,
                "home_team": home_team,
                "away_team": away_team,
                "home_prob": home_prob,
                "actual_outcome": actual_outcome,
                "goals_home": goals_home,
                "goals_away": goals_away,
                "confidence": conf,
            })

    return predictions


def evaluate_predictions(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute comprehensive evaluation metrics from backtest predictions.

    Returns dict with:
        - brier_score: mean squared error of probabilities
        - log_loss: logarithmic loss
        - accuracy: percentage of correct favorite picks
        - calibration: list of {predicted, actual, count} buckets
        - n_predictions: total predictions evaluated
        - home_bias: average (predicted_home - actual_home_win_rate)
    """
    n = len(predictions)
    if n == 0:
        return {
            "brier_score": 0.0,
            "log_loss": 0.0,
            "accuracy": 0.0,
            "calibration": [],
            "n_predictions": 0,
            "home_bias": 0.0,
        }

    # Extract probabilities and outcomes
    probs = [p["home_prob"] for p in predictions]
    outcomes = [p["actual_outcome"] for p in predictions]

    # Brier score: mean((p - y)^2)
    brier_score = sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / n

    # Log loss: -mean(y*log(p) + (1-y)*log(1-p))
    eps = 1e-15  # avoid log(0)
    log_loss = -sum(
        y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps))
        for p, y in zip(probs, outcomes)
    ) / n

    # Accuracy: fraction where (p>0.5 and y==1) or (p<0.5 and y==0)
    correct = sum(
        1 for p, y in zip(probs, outcomes)
        if (p > 0.5 and y == 1) or (p < 0.5 and y == 0)
    )
    accuracy = correct / n

    # Calibration: 10 buckets (0.0-0.1, 0.1-0.2, ..., 0.9-1.0)
    bucket_sums: dict[int, float] = defaultdict(float)
    bucket_counts: dict[int, int] = defaultdict(int)
    bucket_outcomes: dict[int, float] = defaultdict(float)

    for p, y in zip(probs, outcomes):
        bucket_idx = min(int(p * 10), 9)  # 0-9
        bucket_sums[bucket_idx] += p
        bucket_counts[bucket_idx] += 1
        bucket_outcomes[bucket_idx] += y

    calibration = []
    for b in range(10):
        count = bucket_counts[b]
        if count > 0:
            calibration.append({
                "predicted": bucket_sums[b] / count,
                "actual": bucket_outcomes[b] / count,
                "count": count,
            })
        else:
            calibration.append({
                "predicted": (b + 0.5) / 10,
                "actual": 0.0,
                "count": 0,
            })

    # Home bias: average(predicted_home - actual_home_win_rate)
    avg_predicted = sum(probs) / n
    avg_actual = sum(outcomes) / n
    home_bias = avg_predicted - avg_actual

    return {
        "brier_score": brier_score,
        "log_loss": log_loss,
        "accuracy": accuracy,
        "calibration": calibration,
        "n_predictions": n,
        "home_bias": home_bias,
    }


def grid_search(
    games_rows: list[dict[str, str]],
    base_config: TrackerConfig,
    param_grid: dict[str, list[Any]] | None = None,
    train_window_days: int = 60,
) -> list[dict[str, Any]]:
    """Grid search over model parameters to find optimal configuration.

    Parameters
    ----------
    param_grid:
        Dict mapping parameter names to lists of values to try.
        Default grid searches over (expanded per Agent 5 audit):
        - half_life: [14, 21, 30, 45, 60]
        - regression_k: [10, 15, 20, 25, 30]
        - home_advantage: [0.05, 0.10, 0.15, 0.18, 0.20, 0.25]
        - logistic_k: [0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5]

        Total default combinations: 5 * 5 * 6 * 7 = 1050.

    Returns a list of result dicts sorted by Brier score (best first), each containing:
        - params: dict of parameter values used
        - brier_score, log_loss, accuracy
        - n_predictions

    Usage guidance
    --------------
    1. Run with at least one full season of MoneyPuck CSV data.
    2. Examine the top-5 results for parameter clustering — if the
       best results all share, e.g., half_life=30 and logistic_k=0.8,
       those values are likely robust.
    3. Check calibration curves (evaluate_predictions) for the best
       config to verify the model isn't systematically over- or
       under-confident.
    4. Be wary of overfitting: the best grid config on one season
       may not generalize.  Validate on a hold-out season.
    """
    if param_grid is None:
        # Default grid expanded per Agent 5 audit.  Wider ranges test
        # sensitivity to each parameter and help identify calibration
        # sweet spots.  Total combinations: 5 * 5 * 6 * 7 = 1050.
        #
        # home_advantage: 0.05 (minimal) through 0.25 (aggressive).
        #   0.18-0.20 may better match observed ~54-55% NHL home win rate.
        # logistic_k: 0.5-0.7 test flatter curves (more parity), which
        #   may better fit the NHL's competitive balance.
        # half_life: 60 added for a less reactive, smoother model.
        # regression_k: 10-30 tests the speed of trusting observed data.
        param_grid = {
            "half_life": [14, 21, 30, 45, 60],
            "regression_k": [10, 15, 20, 25, 30],
            "home_advantage": [0.05, 0.10, 0.15, 0.18, 0.20, 0.25],
            "logistic_k": [0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5],
        }

    # Build list of param names and value lists in consistent order
    param_names = sorted(param_grid.keys())
    value_lists = [param_grid[name] for name in param_names]

    results: list[dict[str, Any]] = []

    for combination in itertools.product(*value_lists):
        params = dict(zip(param_names, combination))

        # Create modified config using dataclasses.replace for known fields,
        # but since these fields may not exist on TrackerConfig, we build a
        # lightweight wrapper approach: store params and pass to backtest.
        # We attempt replace() for any fields that exist on the dataclass.
        try:
            config = replace(base_config, **params)
        except TypeError:
            # Fields don't exist on TrackerConfig yet; use base config and
            # inject params via a simple namespace wrapper.
            config = _ConfigOverlay(base_config, params)

        preds = backtest_season(games_rows, config, train_window_days)
        metrics = evaluate_predictions(preds)

        results.append({
            "params": params,
            "brier_score": metrics["brier_score"],
            "log_loss": metrics["log_loss"],
            "accuracy": metrics["accuracy"],
            "n_predictions": metrics["n_predictions"],
        })

    # Sort by Brier score ascending (lower is better)
    results.sort(key=lambda r: r["brier_score"])
    return results


class _ConfigOverlay:
    """Thin overlay that delegates attribute access to an underlying config
    but allows overriding specific parameters.

    This lets the backtester work even when TrackerConfig hasn't been updated
    with the new tuning fields (half_life, regression_k, etc.).
    """

    def __init__(self, base: TrackerConfig, overrides: dict[str, Any]) -> None:
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)
