#!/usr/bin/env python3
"""Live model preview — fetches real MoneyPuck data and shows team power rankings
plus edge analysis.

Usage:
    python live_preview.py                              # demo mode (no network)
    python live_preview.py --odds-api-key YOUR_KEY      # with real odds
"""
from __future__ import annotations

import argparse
import os
import random
import sys

from app.logging_config import setup_logging, get_logger
from app.agents import TeamStrengthAgent, EdgeScoringAgent, RiskAgent
from app.math_utils import logistic_win_probability, goalie_matchup_adjustment
from app.models import TrackerConfig, TeamMetrics, ValueCandidate

log = get_logger("preview")


# ---------------------------------------------------------------------------
# Realistic demo data (based on 2024-25 NHL season trends)
# ---------------------------------------------------------------------------

def _build_demo_game_rows() -> list[dict[str, str]]:
    """Generate realistic game rows using legacy bulk CSV format.

    Stats are calibrated to approximate real 2024-25 NHL team performance.
    """
    random.seed(42)
    teams_data = {
        # team: (xg_pct, corsi_pct, hd_for, hd_against, gf, ga, sf, sa, fenwick)
        "FLA": (0.560, 0.535, 12, 8,  3.5, 2.4, 33, 27, 0.540),
        "EDM": (0.555, 0.540, 13, 9,  3.8, 2.8, 35, 28, 0.545),
        "WPG": (0.545, 0.525, 11, 8,  3.3, 2.5, 32, 28, 0.530),
        "DAL": (0.540, 0.530, 11, 9,  3.2, 2.6, 31, 27, 0.535),
        "COL": (0.548, 0.520, 12, 9,  3.6, 2.9, 34, 30, 0.525),
        "CAR": (0.535, 0.545, 10, 8,  3.1, 2.5, 32, 26, 0.548),
        "TOR": (0.530, 0.515, 11, 9,  3.3, 2.8, 33, 29, 0.520),
        "VGK": (0.528, 0.510, 10, 9,  3.2, 2.7, 31, 28, 0.515),
        "NYR": (0.525, 0.530, 10, 9,  3.0, 2.6, 30, 27, 0.528),
        "TBL": (0.520, 0.505, 11, 10, 3.4, 3.0, 33, 30, 0.508),
        "BOS": (0.518, 0.520, 10, 9,  2.9, 2.6, 30, 28, 0.522),
        "MIN": (0.515, 0.510, 10, 9,  2.8, 2.5, 29, 27, 0.512),
        "NJD": (0.512, 0.505, 10, 9,  3.0, 2.8, 31, 29, 0.508),
        "VAN": (0.510, 0.500, 10, 9,  3.1, 2.9, 32, 30, 0.505),
        "LAK": (0.508, 0.508, 9, 9,   2.8, 2.7, 29, 28, 0.510),
        "WSH": (0.505, 0.495, 10, 10, 3.2, 3.0, 31, 30, 0.498),
        "OTT": (0.502, 0.498, 10, 10, 3.0, 2.9, 30, 29, 0.500),
        "CGY": (0.498, 0.505, 9, 10,  2.7, 2.8, 28, 29, 0.502),
        "STL": (0.495, 0.490, 9, 10,  2.8, 3.0, 29, 30, 0.492),
        "DET": (0.492, 0.488, 9, 10,  2.7, 2.9, 28, 30, 0.490),
        "SEA": (0.490, 0.485, 9, 10,  2.6, 2.8, 28, 30, 0.488),
        "NYI": (0.488, 0.498, 9, 10,  2.5, 2.7, 27, 29, 0.496),
        "PIT": (0.485, 0.480, 9, 10,  2.8, 3.1, 30, 32, 0.482),
        "PHI": (0.482, 0.478, 9, 11,  2.6, 3.0, 28, 31, 0.480),
        "BUF": (0.478, 0.475, 8, 10,  2.5, 3.0, 27, 31, 0.478),
        "MTL": (0.475, 0.470, 8, 11,  2.4, 3.1, 27, 32, 0.472),
        "ANA": (0.472, 0.465, 8, 11,  2.3, 3.0, 26, 31, 0.468),
        "CBJ": (0.468, 0.460, 8, 11,  2.4, 3.2, 27, 33, 0.462),
        "UTA": (0.465, 0.458, 8, 11,  2.3, 3.1, 26, 32, 0.460),
        "NSH": (0.462, 0.470, 8, 11,  2.2, 3.0, 26, 31, 0.468),
        "SJS": (0.440, 0.445, 7, 12,  2.0, 3.5, 24, 34, 0.448),
        "CHI": (0.435, 0.440, 7, 12,  1.9, 3.4, 24, 35, 0.442),
    }

    rows: list[dict[str, str]] = []
    team_list = list(teams_data.keys())
    dates = [f"2025-{m:02d}-{d:02d}" for m in range(10, 13) for d in range(1, 29, 3)]
    dates += [f"2026-{m:02d}-{d:02d}" for m in range(1, 3) for d in range(1, 29, 3)]

    for date in dates:
        random.shuffle(team_list)
        pairs = [(team_list[i], team_list[i+1]) for i in range(0, len(team_list) - 1, 2)]
        for home, away in pairs:
            hd = teams_data[home]
            ad = teams_data[away]

            noise = lambda: random.gauss(0, 0.02)
            rows.append({
                "homeTeamCode": home,
                "awayTeamCode": away,
                "gameDate": date,
                "season": "2024",
                "xGoalsPercentage": str(round(hd[0] + noise(), 4)),
                "corsiPercentage": str(round(hd[1] + noise(), 4)),
                "fenwickPercentage": str(round(hd[8] + noise(), 4)),
                "highDangerShotsFor": str(round(hd[2] + random.gauss(0, 1))),
                "highDangerShotsAgainst": str(round(hd[3] + random.gauss(0, 1))),
                "goalsFor": str(round(hd[4] + random.gauss(0, 0.8))),
                "goalsAgainst": str(round(hd[5] + random.gauss(0, 0.8))),
                "shotsOnGoalFor": str(round(hd[6] + random.gauss(0, 2))),
                "shotsOnGoalAgainst": str(round(hd[7] + random.gauss(0, 2))),
                "xGoalsFor": str(round(hd[4] * 0.9 + random.gauss(0, 0.3), 2)),
                "xGoalsAgainst": str(round(hd[5] * 0.9 + random.gauss(0, 0.3), 2)),
                "penaltiesFor": str(round(3 + random.gauss(0, 0.5))),
                "penaltiesAgainst": str(round(3 + random.gauss(0, 0.5))),
            })
    return rows


def _build_demo_odds(matchups: list[tuple[str, str, str]]) -> list[dict]:
    """Build realistic odds events for given matchups."""
    events = []
    for home, away, commence in matchups:
        # Generate realistic American odds
        random.seed(hash(home + away))
        home_fav = random.random() > 0.45
        if home_fav:
            home_odds = random.choice([-130, -140, -150, -160, -170, -180, -200])
            away_odds = random.choice([+110, +120, +130, +140, +150, +160, +175])
        else:
            home_odds = random.choice([+110, +115, +120, +130, +140, +150])
            away_odds = random.choice([-120, -130, -140, -150, -160])

        books = ["DraftKings", "FanDuel", "BetMGM", "Caesars"]
        bookmakers = []
        for book in books:
            # Slight variation per book
            h_var = random.choice([-5, 0, 0, 5, 10])
            a_var = random.choice([-5, 0, 0, 5, 10])
            bookmakers.append({
                "title": book,
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": home, "price": home_odds + h_var},
                        {"name": away, "price": away_odds + a_var},
                    ]
                }]
            })

        events.append({
            "home_team": home,
            "away_team": away,
            "commence_time": commence,
            "bookmakers": bookmakers,
        })
    return events


def _print_section(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Live MoneyPuck model preview")
    parser.add_argument("--odds-api-key", default=os.getenv("ODDS_API_KEY", ""))
    parser.add_argument("--region", default="ca")
    parser.add_argument("--season", type=int, default=2024)
    parser.add_argument("--log-level", default="WARNING")
    parser.add_argument("--demo", action="store_true",
                        help="Use demo data (no network required)")
    args = parser.parse_args()

    setup_logging(args.log_level)

    _print_section("MONEYPUCK EDGE MODEL v2 — LIVE PREVIEW")

    # ---- Determine data source ----
    use_demo = args.demo
    games = None
    goalie_stats: list[dict] = []

    if not use_demo:
        print("\n[1/4] Fetching MoneyPuck team game-by-game data...")
        try:
            from app.data_sources import fetch_team_game_by_game
            games = fetch_team_game_by_game(args.season)
            print(f"  -> Loaded {len(games)} rows via team game-by-game (100+ columns)")
        except Exception:
            try:
                from app.data_sources import fetch_moneypuck_games
                games = fetch_moneypuck_games(args.season)
                print(f"  -> Loaded {len(games)} rows via bulk CSV (fallback)")
            except Exception:
                print("  -> Network unavailable, switching to demo mode")
                use_demo = True

    if not use_demo:
        print("\n[2/4] Fetching NHL goalie stats...")
        try:
            from app.nhl_api import fetch_goalie_stats
            goalie_stats = fetch_goalie_stats()
            print(f"  -> Loaded {len(goalie_stats)} goalies")
        except Exception:
            print("  -> Goalie fetch failed (non-critical)")

    if use_demo or games is None:
        print("\n[1/4] Building demo data (calibrated to 2024-25 NHL season)...")
        games = _build_demo_game_rows()
        print(f"  -> Generated {len(games)} game rows for 32 teams")
        print("\n[2/4] Goalie data: skipped (demo mode)")

    # ---- Build team strength ----
    print("\n[3/4] Building team strength ratings (16-metric composite)...")
    config = TrackerConfig(
        odds_api_key=args.odds_api_key or "demo",
        season=args.season,
        region=args.region,
        min_edge=1.5,
        min_ev=0.01,
    )
    agent = TeamStrengthAgent()
    strength = agent.run(games, config, goalie_stats or None)
    print(f"  -> Computed strength for {len(strength)} teams")

    # ---- Power Rankings ----
    _print_section("TEAM POWER RANKINGS (composite z-score)")
    ranked = sorted(strength.items(), key=lambda x: x[1].composite, reverse=True)

    print(f"\n{'Rank':<5} {'Team':<5} {'Composite':>10} {'Home':>8} {'Away':>8} "
          f"{'xG%':>6} {'Corsi%':>7} {'HD%':>6} {'SV%':>6} {'GP':>4}")
    print("-" * 72)
    for i, (team, m) in enumerate(ranked, 1):
        bar = "+" * max(0, int(m.composite * 10)) if m.composite > 0 else "-" * max(0, int(-m.composite * 10))
        print(
            f"{i:<5} {team:<5} {m.composite:>+10.3f} {m.home_strength:>+8.3f} "
            f"{m.away_strength:>+8.3f} {m.xg_share:>5.1%} {m.corsi_share:>6.1%} "
            f"{m.high_danger_share:>5.1%} {m.save_pct:>5.3f} {m.games_played:>4}  {bar}"
        )

    # ---- Top 5 detail ----
    _print_section("TOP 5 TEAMS — FULL 16-METRIC PROFILE")
    for i, (team, m) in enumerate(ranked[:5], 1):
        print(f"\n  #{i} {team} (composite: {m.composite:+.3f})")
        print(f"    Core:    xG% {m.xg_share:.3f}  |  Score-adj {m.score_adj_xg_share:.3f}  |  Flurry-adj {m.flurry_adj_xg_share:.3f}")
        print(f"    Shots:   Corsi% {m.corsi_share:.3f}  |  Fenwick% {m.fenwick_share:.3f}  |  HD share {m.high_danger_share:.3f}")
        print(f"    Danger:  HD xG% {m.hd_xg_share:.3f}  |  MD xG% {m.md_xg_share:.3f}  |  Rebound {m.rebound_control:.3f}")
        print(f"    Exec:    Sh% {m.shooting_pct:.3f}  |  SV% {m.save_pct:.3f}  |  FO% {m.faceoff_pct:.3f}")
        print(f"    Puck:    Takeaway {m.takeaway_ratio:.3f}  |  DZ giveaways {m.dzone_giveaway_rate:.1f}")
        print(f"    Venue:   Home {m.home_strength:+.3f}  |  Away {m.away_strength:+.3f}  |  Games {m.games_played}")

    # ---- Edge analysis ----
    print("\n[4/4] Running edge detection & risk management...")
    matchups = [
        ("TOR", "MTL", "2026-03-03T19:00:00Z"),
        ("FLA", "NYR", "2026-03-03T19:30:00Z"),
        ("EDM", "VAN", "2026-03-03T22:00:00Z"),
        ("WPG", "CHI", "2026-03-03T20:00:00Z"),
        ("DAL", "CBJ", "2026-03-03T19:00:00Z"),
        ("COL", "SJS", "2026-03-03T22:30:00Z"),
        ("CAR", "DET", "2026-03-03T19:00:00Z"),
        ("BOS", "BUF", "2026-03-03T19:00:00Z"),
    ]

    if args.odds_api_key and not use_demo:
        try:
            from app.data_sources import fetch_odds
            odds_events = fetch_odds(args.odds_api_key, args.region, None)
            source_label = "LIVE ODDS"
        except Exception:
            odds_events = _build_demo_odds(matchups)
            source_label = "DEMO ODDS (API unavailable)"
    else:
        odds_events = _build_demo_odds(matchups)
        source_label = "DEMO ODDS (set ODDS_API_KEY for live)"

    _print_section(f"TONIGHT'S GAMES — {source_label}")

    # Model probabilities for each game
    print(f"\n  {'Game':<20} {'Home Win':>9} {'Away Win':>9} {'Spread':<12} {'Call'}")
    print("  " + "-" * 65)
    for event in odds_events:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        home_m = strength.get(home)
        away_m = strength.get(away)
        if home_m and away_m:
            hp, ap = logistic_win_probability(
                home_m.home_strength, away_m.away_strength
            )
            diff = abs(hp - ap) * 100
            if diff > 15:
                call = "STRONG"
            elif diff > 8:
                call = "LEAN"
            else:
                call = "TOSS-UP"
            fav = home if hp > ap else away
            matchup = f"{away} @ {home}"
            print(f"  {matchup:<20} {hp:>8.1%} {ap:>9.1%} {fav} by {diff:.0f}pp  {call}")

    # Edge detection
    edge_agent = EdgeScoringAgent()
    risk_agent = RiskAgent()
    candidates = edge_agent.run(odds_events, strength, config, games)
    recommendations = risk_agent.run(candidates, config)

    _print_section("VALUE BETS DETECTED")

    if not recommendations:
        print("\n  No value bets found at current thresholds")
        print(f"  (min_edge={config.min_edge}pp, min_ev={config.min_ev})")
    else:
        print(f"\n  {len(recommendations)} value bet(s) found! Bankroll: ${config.bankroll:,.0f}\n")
        print(f"  {'Game':<22} {'Pick':<6} {'Book':<12} {'Odds':>6} "
              f"{'Market':>7} {'Model':>7} {'Edge':>7} {'EV/$':>6} {'Stake':>8} {'Conf':>5}")
        print("  " + "-" * 100)
        total_stake = 0.0
        for rec in recommendations:
            c = rec["candidate"]
            game = f"{c.away_team} @ {c.home_team}"
            total_stake += rec["recommended_stake"]
            print(
                f"  {game:<22} {c.side:<6} {c.sportsbook:<12} "
                f"{c.american_odds:>+6} "
                f"{c.implied_probability:>6.1%} {c.model_probability:>6.1%} "
                f"{c.edge_probability_points:>+6.1f}pp "
                f"{c.expected_value_per_dollar:>5.3f} ${rec['recommended_stake']:>7.2f} "
                f"{c.confidence:>4.0%}"
            )

        print(f"\n  Total stake tonight: ${total_stake:,.2f} "
              f"({total_stake/config.bankroll:.1%} of bankroll)")
        print(f"  Exposure cap: {config.max_nightly_exposure:.0%} = ${config.bankroll * config.max_nightly_exposure:,.0f}")

    # ---- Deployment instructions ----
    _print_section("DEPLOYMENT")
    mode = "DEMO" if use_demo else "LIVE"
    print(f"""
  Current mode: {mode}

  To run with LIVE data:
    export ODDS_API_KEY="your_key_here"    # https://the-odds-api.com (free tier)
    python live_preview.py                  # auto-fetches from MoneyPuck + Odds API

  To run the full tracker:
    python tracker.py --region ca --bankroll 5000

  To run army mode (5 strategy profiles):
    python tracker.py --army --json

  To start the web dashboard:
    python -m app.web_preview               # http://localhost:8080

  Model: 16-metric composite | Logistic win prob | Confidence-adj Kelly
  Data: MoneyPuck team GBG (100+ cols) + NHL API goalies + The Odds API
""")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
