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
from app.math.elo import EloTracker, build_elo_ratings
from app.math.math_utils import (
    DEFAULT_METRIC_WEIGHTS,
    kelly_fraction as kelly_fraction_fn,
    logistic_win_probability,
    prediction_confidence,
)
from app.core.models import TrackerConfig

# Elo ensemble weight in backtester (matches EdgeScoringAgent.ELO_WEIGHT)
ELO_WEIGHT = 0.25


# League average save percentage (used as baseline)
LEAGUE_AVG_SAVE_PCT = 0.905

# ---------------------------------------------------------------------------
# Pass/fail thresholds for production readiness
# ---------------------------------------------------------------------------
BRIER_PASS = 0.24       # Must beat coin-flip (0.25) meaningfully
BRIER_GOOD = 0.22       # Strong calibration
ACCURACY_PASS = 0.52    # Must beat random
LOG_LOSS_PASS = 0.69    # Must beat coin-flip (ln(2) ≈ 0.693)
MIN_PREDICTIONS = 200   # Need enough data for statistical significance


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

    # Detect team-game-by-game format (has 'playerTeam') vs legacy (has 'homeTeamCode')
    is_team_gbg = bool(games_rows and "playerTeam" in games_rows[0])

    # Parse dates and sort games
    date_fmt = "%Y-%m-%d"
    games_with_dates: list[tuple[datetime, dict[str, str]]] = []
    for row in games_rows:
        raw_date = row.get("gameDate", "")[:10]
        try:
            # Support both YYYY-MM-DD and YYYYMMDD formats
            if len(raw_date) == 8 and "-" not in raw_date:
                dt = datetime.strptime(raw_date, "%Y%m%d")
            else:
                dt = datetime.strptime(raw_date, date_fmt)
        except ValueError:
            continue
        # For team-gbg format, only keep home-team "all" situation rows to avoid double-counting
        if is_team_gbg:
            if row.get("home_or_away", "") != "HOME" or row.get("situation", "") != "all":
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

        # Build Elo ratings from training data
        try:
            elo_tracker = build_elo_ratings(train_rows)
        except Exception:
            elo_tracker = None

        # Predict each game on this date
        for game_row in date_groups[test_date_str]:
            if is_team_gbg:
                home_team = game_row.get("playerTeam", "")
                away_team = game_row.get("opposingTeam", "")
            else:
                home_team = game_row["homeTeamCode"]
                away_team = game_row["awayTeamCode"]

            home_metrics = strength.get(home_team)
            away_metrics = strength.get(away_team)

            if home_metrics is None or away_metrics is None:
                continue

            home_z = home_metrics.home_strength
            away_z = away_metrics.away_strength

            logistic_home, _ = logistic_win_probability(
                home_z, away_z,
                home_advantage=home_advantage,
                k=logistic_k,
            )

            # Blend with Elo
            if elo_tracker is not None:
                elo_home = elo_tracker.predict(home_team, away_team)
                home_prob = (1 - ELO_WEIGHT) * logistic_home + ELO_WEIGHT * elo_home
            else:
                home_prob = logistic_home

            # Momentum adjustment from rolling windows
            if home_metrics.composite_5g != 0.0 or away_metrics.composite_5g != 0.0:
                momentum_adj = (home_metrics.momentum - away_metrics.momentum) * 0.02
                home_prob += momentum_adj

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


def simulate_betting_roi(
    predictions: list[dict[str, Any]],
    min_edge: float = 2.0,
    kelly_mult: float = 0.5,
    max_bet_frac: float = 0.03,
    vig: float = 0.04,
) -> dict[str, Any]:
    """Simulate ROI by treating the model's own predictions as bet decisions.

    Since backtest data doesn't include real betting lines, we synthesize
    market odds by adding vig to the true outcome rate. This tests whether
    the model's *calibration quality* would translate to profitable betting.

    For each prediction where the model claims an edge >= min_edge pp over
    a synthetic market line, we simulate placing a half-Kelly bet and
    settling it against the actual outcome.

    Parameters
    ----------
    predictions:
        Output from backtest_season(). Each dict has home_prob, actual_outcome.
    min_edge:
        Minimum edge in probability points to place a simulated bet.
    kelly_mult:
        Kelly fraction multiplier (0.5 = half-Kelly).
    max_bet_frac:
        Maximum fraction of bankroll per bet.
    vig:
        Simulated bookmaker vig added to fair odds (default 4%).

    Returns
    -------
    dict with:
        - total_bets: number of simulated bets placed
        - total_staked: sum of all stakes (starting bankroll = 1000)
        - final_bankroll: ending bankroll after all bets
        - roi_pct: (final - initial) / total_staked * 100
        - win_rate: fraction of bets won
        - avg_edge: average edge in pp on bets placed
        - max_drawdown_pct: worst peak-to-trough drawdown
        - bets_by_month: dict of YYYY-MM -> {bets, pnl}
    """
    bankroll = 1000.0
    initial_bankroll = bankroll
    peak_bankroll = bankroll
    max_drawdown = 0.0
    total_staked = 0.0
    wins = 0
    losses = 0
    edges: list[float] = []
    bets_by_month: dict[str, dict[str, float]] = defaultdict(lambda: {"bets": 0, "pnl": 0.0})

    for pred in predictions:
        model_p = pred["home_prob"]
        outcome = pred["actual_outcome"]
        game_date = pred.get("game_date", "")
        month_key = game_date[:7] if game_date else "unknown"

        # Simulate market line: true base rate + vig (making it harder to beat)
        # Use a noisy "market" that's roughly correct but with bookmaker margin
        # The "fair" implied probability is ~50% for average games + vig
        market_implied = min(0.95, max(0.05, (1 - model_p) * (1 - vig / 2) + vig / 2))
        # For the home side: model says home_prob, market says (1 - market_implied) for home
        home_market_implied = 1 - market_implied  # market's home win probability
        # Actually, let's be more realistic: the market is smart but not perfect
        # Use a blend: market = 0.7 * true_rate + 0.3 * model + vig
        # This means the market is closer to reality than the model on average
        true_rate = outcome  # hindsight
        # We can't use true_rate (that's cheating). Instead, simulate the market
        # as the complement of model_p with vig added (market disagrees by some margin)
        #
        # Simpler approach: market_implied_home = model_p - random noise + vig
        # Since we don't want randomness in a deterministic test, use:
        # market_implied_home = model_p * (1 - vig) = slightly worse than model
        # This means the model always has a small "edge" = vig amount
        # That's too easy. Instead:
        #
        # Fair approach: assume the market is ~50/50 for all games + home ice
        # adjustment. Model's edge comes from team strength differentiation.
        market_base = 0.537  # league-average home win rate (includes vig)
        # Add vig to make it harder
        if model_p > 0.5:
            # Model likes home team
            synthetic_implied = market_base + vig / 2
            model_side_p = model_p
            bet_side_won = outcome == 1
        else:
            # Model likes away team
            synthetic_implied = (1 - market_base) + vig / 2
            model_side_p = 1 - model_p
            bet_side_won = outcome == 0

        edge_pp = (model_side_p - synthetic_implied) * 100

        if edge_pp < min_edge:
            continue

        # Convert implied prob to decimal odds
        if synthetic_implied <= 0 or synthetic_implied >= 1:
            continue
        decimal_odds = 1.0 / synthetic_implied

        # Kelly sizing
        kelly = kelly_fraction_fn(model_side_p, decimal_odds) * kelly_mult
        stake = min(bankroll * kelly, bankroll * max_bet_frac)
        stake = max(0.0, stake)

        if stake < 1.0:  # minimum $1 bet
            continue

        total_staked += stake
        edges.append(edge_pp)
        bets_by_month[month_key]["bets"] += 1

        if bet_side_won:
            profit = stake * (decimal_odds - 1)
            bankroll += profit
            wins += 1
            bets_by_month[month_key]["pnl"] += profit
        else:
            bankroll -= stake
            losses += 1
            bets_by_month[month_key]["pnl"] -= stake

        # Track drawdown
        if bankroll > peak_bankroll:
            peak_bankroll = bankroll
        drawdown = (peak_bankroll - bankroll) / peak_bankroll * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    total_bets = wins + losses
    roi_pct = ((bankroll - initial_bankroll) / total_staked * 100) if total_staked > 0 else 0.0

    return {
        "total_bets": total_bets,
        "total_staked": round(total_staked, 2),
        "final_bankroll": round(bankroll, 2),
        "roi_pct": round(roi_pct, 2),
        "win_rate": round(wins / total_bets, 4) if total_bets else 0.0,
        "avg_edge": round(sum(edges) / len(edges), 2) if edges else 0.0,
        "max_drawdown_pct": round(max_drawdown, 2),
        "bets_by_month": dict(bets_by_month),
    }


def production_readiness_report(
    predictions: list[dict[str, Any]],
    config: TrackerConfig | None = None,
) -> dict[str, Any]:
    """Comprehensive backtest report with clear pass/fail verdict.

    Combines calibration metrics, simulated ROI, and threshold checks
    to produce a single go/no-go assessment for production betting.
    """
    metrics = evaluate_predictions(predictions)
    roi = simulate_betting_roi(
        predictions,
        min_edge=config.min_edge if config else 2.0,
        kelly_mult=config.kelly_fraction if config else 0.5,
        max_bet_frac=config.max_fraction_per_bet if config else 0.03,
    )

    # Pass/fail checks
    checks: dict[str, dict[str, Any]] = {}

    n = metrics["n_predictions"]
    checks["sample_size"] = {
        "value": n,
        "threshold": MIN_PREDICTIONS,
        "pass": n >= MIN_PREDICTIONS,
        "detail": f"{n} predictions (need >= {MIN_PREDICTIONS})",
    }

    brier = metrics["brier_score"]
    checks["brier_score"] = {
        "value": round(brier, 4),
        "threshold": BRIER_PASS,
        "pass": brier <= BRIER_PASS,
        "grade": "EXCELLENT" if brier <= BRIER_GOOD else ("PASS" if brier <= BRIER_PASS else "FAIL"),
        "detail": f"Brier {brier:.4f} vs coin-flip 0.2500 (lower is better)",
    }

    acc = metrics["accuracy"]
    checks["accuracy"] = {
        "value": round(acc, 4),
        "threshold": ACCURACY_PASS,
        "pass": acc >= ACCURACY_PASS,
        "detail": f"Accuracy {acc:.1%} (need > {ACCURACY_PASS:.0%})",
    }

    ll = metrics["log_loss"]
    checks["log_loss"] = {
        "value": round(ll, 4),
        "threshold": LOG_LOSS_PASS,
        "pass": ll <= LOG_LOSS_PASS,
        "detail": f"Log loss {ll:.4f} vs coin-flip 0.6931",
    }

    bias = abs(metrics["home_bias"])
    checks["home_bias"] = {
        "value": round(metrics["home_bias"], 4),
        "threshold": 0.03,
        "pass": bias <= 0.03,
        "detail": f"Home bias {metrics['home_bias']:+.4f} (should be near 0)",
    }

    # Calibration quality: max deviation across buckets
    cal = metrics["calibration"]
    max_cal_error = 0.0
    for bucket in cal:
        if bucket["count"] >= 10:  # only check buckets with enough data
            max_cal_error = max(max_cal_error, abs(bucket["predicted"] - bucket["actual"]))
    checks["calibration"] = {
        "value": round(max_cal_error, 4),
        "threshold": 0.08,
        "pass": max_cal_error <= 0.08,
        "detail": f"Max calibration error {max_cal_error:.1%} across populated buckets",
    }

    # ROI check
    checks["simulated_roi"] = {
        "value": roi["roi_pct"],
        "threshold": 0.0,
        "pass": roi["roi_pct"] > 0.0,
        "detail": f"Simulated ROI {roi['roi_pct']:+.1f}% on {roi['total_bets']} bets",
    }

    checks["max_drawdown"] = {
        "value": roi["max_drawdown_pct"],
        "threshold": 30.0,
        "pass": roi["max_drawdown_pct"] <= 30.0,
        "detail": f"Max drawdown {roi['max_drawdown_pct']:.1f}% (limit 30%)",
    }

    # Overall verdict
    critical_checks = ["brier_score", "accuracy", "sample_size"]
    critical_pass = all(checks[c]["pass"] for c in critical_checks)
    all_pass = all(c["pass"] for c in checks.values())

    if all_pass:
        verdict = "PASS"
        verdict_detail = "All checks passed. Model is ready for paper trading."
    elif critical_pass:
        verdict = "CONDITIONAL"
        failed = [k for k, v in checks.items() if not v["pass"]]
        verdict_detail = f"Critical checks passed but warnings on: {', '.join(failed)}"
    else:
        verdict = "FAIL"
        failed = [k for k, v in checks.items() if not v["pass"]]
        verdict_detail = f"Failed checks: {', '.join(failed)}. Do NOT bet real money."

    return {
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "checks": checks,
        "metrics": metrics,
        "simulated_roi": roi,
    }


def format_report(report: dict[str, Any]) -> str:
    """Format a production_readiness_report into human-readable output."""
    lines: list[str] = []
    w = 72

    lines.append("=" * w)
    lines.append("  MONEYPUCK EDGE — BACKTEST VALIDATION REPORT")
    lines.append("=" * w)

    # Verdict banner
    verdict = report["verdict"]
    if verdict == "PASS":
        symbol = "[PASS]"
    elif verdict == "CONDITIONAL":
        symbol = "[WARN]"
    else:
        symbol = "[FAIL]"
    lines.append(f"\n  VERDICT: {symbol} {report['verdict_detail']}")

    # Checks table
    lines.append(f"\n{'  Check':<25} {'Value':>10} {'Threshold':>12} {'Status':>8}")
    lines.append("  " + "-" * 58)
    for name, check in report["checks"].items():
        status = "PASS" if check["pass"] else "FAIL"
        val = check["value"]
        thr = check["threshold"]
        if isinstance(val, float):
            val_str = f"{val:.4f}"
        else:
            val_str = str(val)
        if isinstance(thr, float):
            thr_str = f"{thr:.4f}"
        else:
            thr_str = str(thr)
        lines.append(f"  {name:<23} {val_str:>10} {thr_str:>12} {status:>8}")

    # Calibration curve
    cal = report["metrics"]["calibration"]
    populated = [b for b in cal if b["count"] > 0]
    if populated:
        lines.append(f"\n  CALIBRATION CURVE (predicted vs actual win rate)")
        lines.append(f"  {'Predicted':>10} {'Actual':>10} {'Count':>8} {'Error':>8}")
        lines.append("  " + "-" * 40)
        for b in populated:
            err = b["predicted"] - b["actual"]
            lines.append(
                f"  {b['predicted']:>9.1%} {b['actual']:>9.1%} {b['count']:>8} {err:>+7.1%}"
            )

    # ROI simulation
    roi = report["simulated_roi"]
    lines.append(f"\n  SIMULATED BETTING PERFORMANCE")
    lines.append("  " + "-" * 40)
    lines.append(f"  Bets placed:      {roi['total_bets']}")
    lines.append(f"  Total staked:     ${roi['total_staked']:,.2f}")
    lines.append(f"  Final bankroll:   ${roi['final_bankroll']:,.2f} (started $1,000)")
    lines.append(f"  ROI:              {roi['roi_pct']:+.1f}%")
    lines.append(f"  Win rate:         {roi['win_rate']:.1%}")
    lines.append(f"  Avg edge:         {roi['avg_edge']:.1f}pp")
    lines.append(f"  Max drawdown:     {roi['max_drawdown_pct']:.1f}%")

    if roi.get("bets_by_month"):
        lines.append(f"\n  MONTHLY BREAKDOWN")
        lines.append(f"  {'Month':<12} {'Bets':>6} {'P&L':>10}")
        lines.append("  " + "-" * 30)
        for month in sorted(roi["bets_by_month"]):
            m = roi["bets_by_month"][month]
            lines.append(f"  {month:<12} {m['bets']:>6} ${m['pnl']:>+9.2f}")

    # Recommendations
    lines.append(f"\n{'=' * w}")
    if verdict == "PASS":
        lines.append("  NEXT STEPS:")
        lines.append("  1. Start paper trading (--tonight --json) for 2+ weeks")
        lines.append("  2. Track CLV (closing line value) to verify edge quality")
        lines.append("  3. Begin with quarter-Kelly (--kelly-fraction 0.25)")
    elif verdict == "CONDITIONAL":
        lines.append("  NEXT STEPS:")
        lines.append("  1. Investigate failed checks above")
        lines.append("  2. Run grid search to optimize parameters")
        lines.append("  3. Paper trade only — do NOT use real money yet")
    else:
        lines.append("  MODEL IS NOT READY FOR BETTING.")
        lines.append("  1. Run: python tracker.py --backtest (grid search)")
        lines.append("  2. Review calibration curve for systematic bias")
        lines.append("  3. Consider parameter tuning with --half-life, --logistic-k")
    lines.append("=" * w)

    return "\n".join(lines)


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
