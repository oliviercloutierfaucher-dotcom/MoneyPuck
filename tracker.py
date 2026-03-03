#!/usr/bin/env python3
"""Production-oriented NHL value-bet tracker CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys

from app.army import run_agent_army
from app.logging_config import get_logger, setup_logging
from app.models import TrackerConfig
from app.presentation import to_serializable
from app.service import run_tracker

log = get_logger("cli")

SUPPORTED_REGIONS = {"ca", "us"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NHL edge tracker (MoneyPuck vs market)")
    parser.add_argument("--odds-api-key", default=os.getenv("ODDS_API_KEY"), help="The Odds API key")
    parser.add_argument("--region", default="ca", choices=sorted(SUPPORTED_REGIONS))
    parser.add_argument("--bookmakers", default="", help="Optional comma-separated bookmaker keys")
    parser.add_argument("--season", type=int, default=2024)
    parser.add_argument("--min-edge", type=float, default=2.0)
    parser.add_argument("--min-ev", type=float, default=0.02)
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--max-fraction-per-bet", type=float, default=0.03)
    parser.add_argument("--kelly-fraction", type=float, default=0.5, help="Kelly multiplier (0.5 = half-Kelly)")
    parser.add_argument("--max-nightly-exposure", type=float, default=0.15, help="Max total stake per night as fraction of bankroll")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    parser.add_argument("--army", action="store_true", help="Run all betting-agent profiles in parallel")
    parser.add_argument("--persist", action="store_true", help="Save predictions to SQLite database")
    parser.add_argument("--validate", action="store_true", help="Print model health report from stored predictions")
    # Tunable model parameters
    parser.add_argument("--half-life", type=float, default=30.0, help="Decay half-life in days for game weighting")
    parser.add_argument("--regression-k", type=int, default=20, help="Bayesian regression-to-mean sample size")
    parser.add_argument("--home-advantage", type=float, default=0.15, help="Home ice advantage in z-score space")
    parser.add_argument("--logistic-k", type=float, default=1.0, help="Logistic scaling constant")
    parser.add_argument("--goalie-impact", type=float, default=1.5, help="Goalie save%% impact scaling factor")
    parser.add_argument("--backtest", action="store_true", help="Run backtesting against historical data")
    parser.add_argument("--log-level", default=None, help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    return parser.parse_args()


def _validate_args(args: argparse.Namespace) -> str | None:
    """Validate CLI arguments. Returns error message or None if valid."""
    if not args.odds_api_key:
        return "Missing Odds API key. Set ODDS_API_KEY or pass --odds-api-key."
    if args.bankroll <= 0:
        return "Bankroll must be positive."
    if args.kelly_fraction <= 0 or args.kelly_fraction > 1.0:
        return "Kelly fraction must be between 0 (exclusive) and 1.0 (inclusive)."
    if args.max_fraction_per_bet <= 0 or args.max_fraction_per_bet > 1.0:
        return "Max fraction per bet must be between 0 (exclusive) and 1.0 (inclusive)."
    if args.max_nightly_exposure <= 0 or args.max_nightly_exposure > 1.0:
        return "Max nightly exposure must be between 0 (exclusive) and 1.0 (inclusive)."
    if args.half_life <= 0:
        return "Half-life must be positive."
    if args.logistic_k <= 0:
        return "Logistic scaling constant must be positive."
    return None


def _print_human(recommendations: list[dict[str, object]]) -> None:
    if not recommendations:
        print("No value bets found with current thresholds.")
        return

    print(f"Found {len(recommendations)} opportunities\n")
    for item in recommendations:
        c = item["candidate"]
        print(
            f"[{c.commence_time_utc}] {c.away_team} @ {c.home_team} | "
            f"Bet {c.side} ({c.american_odds:+}) at {c.sportsbook} | "
            f"Edge {c.edge_probability_points:.2f}pp | EV/$ {c.expected_value_per_dollar:.3f} | "
            f"Stake ${item['recommended_stake']} ({item['stake_fraction'] * 100:.2f}% BR)"
        )


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)

    error = _validate_args(args)
    if error:
        log.error(error)
        print(error, file=sys.stderr)
        return 1

    config = TrackerConfig(
        odds_api_key=args.odds_api_key,
        region=args.region,
        bookmakers=args.bookmakers,
        season=args.season,
        min_edge=args.min_edge,
        min_ev=args.min_ev,
        bankroll=args.bankroll,
        max_fraction_per_bet=args.max_fraction_per_bet,
        kelly_fraction=args.kelly_fraction,
        max_nightly_exposure=args.max_nightly_exposure,
        persist=args.persist,
        half_life=args.half_life,
        regression_k=args.regression_k,
        home_advantage=args.home_advantage,
        logistic_k=args.logistic_k,
        goalie_impact=args.goalie_impact,
    )

    try:
        # Phase 4: model health report from stored predictions
        if args.validate:
            from app.database import TrackerDatabase
            from app.validation import model_health_report
            with TrackerDatabase() as db:
                settled = db.get_predictions()
                settled = [s for s in settled if s.get("outcome") is not None]
            report = model_health_report(settled)
            print(json.dumps(report, indent=2))
            return 0

        if args.backtest:
            from app.backtester import backtest_season, evaluate_predictions
            from app.data_sources import fetch_moneypuck_games
            log.info("Starting backtest for season %d", config.season)
            games = fetch_moneypuck_games(config.season)
            log.info("Backtesting %d games", len(games))
            preds = backtest_season(games, config)
            report = evaluate_predictions(preds)
            report["n_predictions"] = len(preds)
            print(json.dumps(report, indent=2))
            return 0

        if args.army:
            army_results = run_agent_army(config)
            print(json.dumps(army_results, indent=2))
            return 0

        recommendations = run_tracker(config)
    except ValueError as exc:
        log.error("Configuration error: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (OSError, TimeoutError) as exc:
        log.error("Network error: %s", exc)
        print(f"Network error: {exc}", file=sys.stderr)
        return 2
    except Exception:
        log.exception("Unexpected error during tracker run")
        print("Tracker run failed unexpectedly. Check logs for details.", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(to_serializable(recommendations), indent=2))
    else:
        _print_human(recommendations)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
