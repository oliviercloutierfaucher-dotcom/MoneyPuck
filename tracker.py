#!/usr/bin/env python3
"""Production-oriented NHL value-bet tracker CLI."""

from __future__ import annotations

import argparse
import json
import os

from app.army import run_agent_army
from app.models import TrackerConfig
from app.presentation import to_serializable
from app.service import run_tracker

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
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    parser.add_argument("--army", action="store_true", help="Run all betting-agent profiles in parallel")
    return parser.parse_args()


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
    if not args.odds_api_key:
        print("Missing Odds API key. Set ODDS_API_KEY or pass --odds-api-key.")
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
    )

    try:
        if args.army:
            army_results = run_agent_army(config)
            print(json.dumps(army_results, indent=2))
            return 0

        recommendations = run_tracker(config)
    except Exception as exc:
        print(f"Tracker run failed: {exc}")
        return 2

    if args.json:
        print(json.dumps(to_serializable(recommendations), indent=2))
    else:
        _print_human(recommendations)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
