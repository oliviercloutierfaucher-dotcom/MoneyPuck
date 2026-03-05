#!/usr/bin/env python3
"""Production-oriented NHL value-bet tracker CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime

from app.core.army import run_agent_army
from app.logging_config import get_logger, setup_logging
from app.core.models import TrackerConfig
from app.web.presentation import to_serializable
from app.core.service import run_tracker

log = get_logger("cli")

SUPPORTED_REGIONS = {"ca", "us"}


def _current_nhl_season() -> int:
    """Return the current NHL season start year (e.g. 2025 for the 2025-26 season).

    The NHL season runs roughly October to June, so before October we're
    still in the previous season.
    """
    now = datetime.now()
    return now.year if now.month >= 10 else now.year - 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NHL edge tracker (MoneyPuck vs market)")
    parser.add_argument("--odds-api-key", default=os.getenv("ODDS_API_KEY"), help="The Odds API key")
    parser.add_argument("--region", default="ca", choices=sorted(SUPPORTED_REGIONS))
    parser.add_argument("--bookmakers", default="", help="Optional comma-separated bookmaker keys")
    parser.add_argument("--season", type=int, default=_current_nhl_season())
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
    parser.add_argument("--tonight", action="store_true", help="Show tonight's games with model probabilities and value bets")
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


def _print_human(recommendations: list[dict[str, object]], config: TrackerConfig | None = None) -> None:
    if not recommendations:
        print("No value bets found with current thresholds.")
        return

    print(f"\nFound {len(recommendations)} value bet(s)")
    bankroll = config.bankroll if config else 1000.0
    print(f"Bankroll: ${bankroll:,.0f}\n")
    print(f"{'Game':<22} {'Pick':<6} {'Book':<12} {'Odds':>6} "
          f"{'Market':>7} {'Model':>7} {'Edge':>7} {'EV/$':>6} {'Stake':>8} {'Conf':>5}")
    print("-" * 100)
    total_stake = 0.0
    for item in recommendations:
        c = item["candidate"]
        game = f"{c.away_team} @ {c.home_team}"
        total_stake += item["recommended_stake"]
        print(
            f"{game:<22} {c.side:<6} {c.sportsbook:<12} "
            f"{c.american_odds:>+6} "
            f"{c.implied_probability:>6.1%} {c.model_probability:>6.1%} "
            f"{c.edge_probability_points:>+6.1f}pp "
            f"{c.expected_value_per_dollar:>5.3f} ${item['recommended_stake']:>7.2f} "
            f"{c.confidence:>4.0%}"
        )
    print()
    print(f"Total stake: ${total_stake:,.2f} ({total_stake/bankroll:.1%} of bankroll)")


def _print_tonight(recommendations: list[dict[str, object]], snapshot, config: TrackerConfig) -> None:
    """Rich output for --tonight mode with game matchups + value bets."""
    from app.math.math_utils import logistic_win_probability, goalie_matchup_adjustment

    today_str = date.today().isoformat()
    strength = snapshot.team_strength

    print(f"\n{'=' * 72}")
    print(f"  TONIGHT'S GAMES — {today_str}")
    print(f"{'=' * 72}")

    # Show all games with model probabilities
    today_events = [
        e for e in snapshot.odds_events
        if e.get("commence_time", "")[:10] == today_str
    ]
    if not today_events:
        today_events = snapshot.odds_events  # show all if date filter yields nothing

    if today_events:
        print(f"\n  {'Game':<20} {'Home Win':>9} {'Away Win':>9} {'Spread':<12} {'Call'}")
        print("  " + "-" * 65)
        for event in today_events:
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            home_m = strength.get(home)
            away_m = strength.get(away)
            if home_m and away_m:
                hp, ap = logistic_win_probability(
                    home_m.home_strength, away_m.away_strength,
                    home_advantage=config.home_advantage, k=config.logistic_k,
                )
                if home_m.starter_save_pct and away_m.starter_save_pct:
                    g_adj = goalie_matchup_adjustment(
                        home_m.starter_save_pct, away_m.starter_save_pct,
                        config.goalie_impact,
                    )
                    hp = max(0.01, min(0.99, hp + g_adj))
                    ap = 1.0 - hp
                diff = abs(hp - ap) * 100
                fav = home if hp > ap else away
                call = "STRONG" if diff > 15 else ("LEAN" if diff > 8 else "TOSS-UP")
                matchup = f"{away} @ {home}"
                print(f"  {matchup:<20} {hp:>8.1%} {ap:>9.1%} {fav} by {diff:.0f}pp  {call}")
    else:
        print("\n  No games found for today")

    # Value bets section
    print(f"\n{'=' * 72}")
    if recommendations:
        print(f"  VALUE BETS ({len(recommendations)})")
        print(f"{'=' * 72}\n")
        _print_human(recommendations, config)
    else:
        print(f"  NO VALUE BETS at current thresholds")
        print(f"  (min_edge={config.min_edge}pp, min_ev={config.min_ev})")
        print(f"{'=' * 72}")

    print()


def _load_dotenv() -> None:
    """Load .env file from project root if it exists."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
    except FileNotFoundError:
        pass


def main() -> int:
    _load_dotenv()
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
            from app.data.database import TrackerDatabase
            from app.math.validation import model_health_report
            with TrackerDatabase() as db:
                settled = db.get_predictions()
                settled = [s for s in settled if s.get("outcome") is not None]
            report = model_health_report(settled)
            print(json.dumps(report, indent=2))
            return 0

        if args.backtest:
            from app.core.backtester import backtest_season, evaluate_predictions
            from app.data.data_sources import fetch_moneypuck_games
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

        if args.tonight:
            from app.core.service import build_market_snapshot, score_snapshot
            snapshot, games_rows = build_market_snapshot(config)
            recommendations = score_snapshot(snapshot, config, games_rows)

            if config.persist and recommendations:
                from app.core.service import _persist_recommendations
                _persist_recommendations(recommendations, config)

            if args.json:
                output = {
                    "date": date.today().isoformat(),
                    "model": "moneypuck-edge-v2",
                    "config": {
                        "bankroll": config.bankroll,
                        "min_edge": config.min_edge,
                        "min_ev": config.min_ev,
                        "kelly_fraction": config.kelly_fraction,
                        "region": config.region,
                    },
                    "games": [],
                    "bets": to_serializable(recommendations),
                    "summary": {
                        "total_bets": len(recommendations),
                        "total_stake": sum(float(r["recommended_stake"]) for r in recommendations),
                        "avg_edge": (
                            sum(r["candidate"].edge_probability_points for r in recommendations) / len(recommendations)
                            if recommendations else 0.0
                        ),
                        "avg_ev": (
                            sum(r["candidate"].expected_value_per_dollar for r in recommendations) / len(recommendations)
                            if recommendations else 0.0
                        ),
                    },
                }
                # Add game-level model probabilities
                from app.math.math_utils import logistic_win_probability, goalie_matchup_adjustment
                for event in snapshot.odds_events:
                    home = event.get("home_team", "")
                    away = event.get("away_team", "")
                    hm = snapshot.team_strength.get(home)
                    am = snapshot.team_strength.get(away)
                    if hm and am:
                        hp, ap = logistic_win_probability(
                            hm.home_strength, am.away_strength,
                            home_advantage=config.home_advantage, k=config.logistic_k,
                        )
                        if hm.starter_save_pct and am.starter_save_pct:
                            g_adj = goalie_matchup_adjustment(
                                hm.starter_save_pct, am.starter_save_pct,
                                config.goalie_impact,
                            )
                            hp = max(0.01, min(0.99, hp + g_adj))
                            ap = 1.0 - hp
                        output["games"].append({
                            "home": home,
                            "away": away,
                            "home_win_pct": round(hp, 4),
                            "away_win_pct": round(ap, 4),
                            "favourite": home if hp > ap else away,
                            "commence": event.get("commence_time", ""),
                        })
                print(json.dumps(output, indent=2))
            else:
                _print_tonight(recommendations, snapshot, config)
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
        _print_human(recommendations, config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
