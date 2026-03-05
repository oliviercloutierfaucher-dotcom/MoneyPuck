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
from datetime import datetime

from app.logging_config import setup_logging, get_logger
from app.core.agents import TeamStrengthAgent, EdgeScoringAgent, RiskAgent
from app.math.math_utils import logistic_win_probability, goalie_matchup_adjustment
from app.core.models import TrackerConfig, TeamMetrics, ValueCandidate

log = get_logger("preview")


# ---------------------------------------------------------------------------
# Realistic demo data (based on 2024-25 NHL season trends)
# ---------------------------------------------------------------------------

def _build_demo_game_rows() -> list[dict[str, str]]:
    """Generate realistic game rows using MoneyPuck team GBG format.

    Uses all 16 metric columns so every metric lights up in the model.
    Stats are calibrated to approximate real 2024-25 NHL team performance.
    """
    random.seed(42)
    # team: (xg%, corsi%, hd_for, hd_against, gf, ga, sf, sa, fenwick%,
    #        fo%, takeaway_ratio, rebound_ctrl, dz_ga, sv%)
    teams_data = {
        "FLA": (0.560, 0.535, 12, 8,  3.5, 2.4, 33, 27, 0.540, 0.520, 0.55, 0.56, 3.2, 0.920),
        "EDM": (0.555, 0.540, 13, 9,  3.8, 2.8, 35, 28, 0.545, 0.505, 0.52, 0.54, 4.1, 0.912),
        "WPG": (0.545, 0.525, 11, 8,  3.3, 2.5, 32, 28, 0.530, 0.510, 0.53, 0.52, 3.8, 0.916),
        "DAL": (0.540, 0.530, 11, 9,  3.2, 2.6, 31, 27, 0.535, 0.515, 0.54, 0.53, 3.5, 0.914),
        "COL": (0.548, 0.520, 12, 9,  3.6, 2.9, 34, 30, 0.525, 0.490, 0.50, 0.55, 4.3, 0.908),
        "CAR": (0.535, 0.545, 10, 8,  3.1, 2.5, 32, 26, 0.548, 0.525, 0.56, 0.51, 3.0, 0.918),
        "TOR": (0.530, 0.515, 11, 9,  3.3, 2.8, 33, 29, 0.520, 0.500, 0.51, 0.52, 3.9, 0.910),
        "VGK": (0.528, 0.510, 10, 9,  3.2, 2.7, 31, 28, 0.515, 0.508, 0.52, 0.50, 3.7, 0.912),
        "NYR": (0.525, 0.530, 10, 9,  3.0, 2.6, 30, 27, 0.528, 0.495, 0.51, 0.53, 3.4, 0.922),
        "TBL": (0.520, 0.505, 11, 10, 3.4, 3.0, 33, 30, 0.508, 0.500, 0.49, 0.51, 4.0, 0.906),
        "BOS": (0.518, 0.520, 10, 9,  2.9, 2.6, 30, 28, 0.522, 0.520, 0.53, 0.50, 3.3, 0.915),
        "MIN": (0.515, 0.510, 10, 9,  2.8, 2.5, 29, 27, 0.512, 0.515, 0.54, 0.49, 3.1, 0.920),
        "NJD": (0.512, 0.505, 10, 9,  3.0, 2.8, 31, 29, 0.508, 0.498, 0.50, 0.51, 3.8, 0.910),
        "VAN": (0.510, 0.500, 10, 9,  3.1, 2.9, 32, 30, 0.505, 0.492, 0.49, 0.50, 4.2, 0.908),
        "LAK": (0.508, 0.508, 9, 9,   2.8, 2.7, 29, 28, 0.510, 0.505, 0.51, 0.49, 3.6, 0.912),
        "WSH": (0.505, 0.495, 10, 10, 3.2, 3.0, 31, 30, 0.498, 0.500, 0.48, 0.50, 4.0, 0.905),
        "OTT": (0.502, 0.498, 10, 10, 3.0, 2.9, 30, 29, 0.500, 0.495, 0.49, 0.48, 4.1, 0.907),
        "CGY": (0.498, 0.505, 9, 10,  2.7, 2.8, 28, 29, 0.502, 0.510, 0.52, 0.48, 3.5, 0.910),
        "STL": (0.495, 0.490, 9, 10,  2.8, 3.0, 29, 30, 0.492, 0.498, 0.48, 0.47, 4.3, 0.903),
        "DET": (0.492, 0.488, 9, 10,  2.7, 2.9, 28, 30, 0.490, 0.490, 0.47, 0.48, 4.5, 0.902),
        "SEA": (0.490, 0.485, 9, 10,  2.6, 2.8, 28, 30, 0.488, 0.495, 0.48, 0.47, 4.2, 0.906),
        "NYI": (0.488, 0.498, 9, 10,  2.5, 2.7, 27, 29, 0.496, 0.510, 0.50, 0.46, 3.8, 0.908),
        "PIT": (0.485, 0.480, 9, 10,  2.8, 3.1, 30, 32, 0.482, 0.488, 0.46, 0.49, 4.4, 0.900),
        "PHI": (0.482, 0.478, 9, 11,  2.6, 3.0, 28, 31, 0.480, 0.492, 0.47, 0.46, 4.6, 0.902),
        "BUF": (0.478, 0.475, 8, 10,  2.5, 3.0, 27, 31, 0.478, 0.485, 0.46, 0.47, 4.7, 0.899),
        "MTL": (0.475, 0.470, 8, 11,  2.4, 3.1, 27, 32, 0.472, 0.488, 0.45, 0.45, 4.8, 0.898),
        "ANA": (0.472, 0.465, 8, 11,  2.3, 3.0, 26, 31, 0.468, 0.480, 0.44, 0.46, 4.5, 0.901),
        "CBJ": (0.468, 0.460, 8, 11,  2.4, 3.2, 27, 33, 0.462, 0.482, 0.43, 0.44, 5.0, 0.897),
        "UTA": (0.465, 0.458, 8, 11,  2.3, 3.1, 26, 32, 0.460, 0.478, 0.44, 0.45, 5.1, 0.896),
        "NSH": (0.462, 0.470, 8, 11,  2.2, 3.0, 26, 31, 0.468, 0.500, 0.47, 0.44, 4.3, 0.904),
        "SJS": (0.440, 0.445, 7, 12,  2.0, 3.5, 24, 34, 0.448, 0.470, 0.42, 0.42, 5.5, 0.892),
        "CHI": (0.435, 0.440, 7, 12,  1.9, 3.4, 24, 35, 0.442, 0.465, 0.41, 0.43, 5.3, 0.890),
    }

    rows: list[dict[str, str]] = []
    team_list = list(teams_data.keys())
    dates = [f"2025-{m:02d}-{d:02d}" for m in range(10, 13) for d in range(1, 29, 3)]
    dates += [f"2026-{m:02d}-{d:02d}" for m in range(1, 3) for d in range(1, 29, 3)]

    for date in dates:
        random.shuffle(team_list)
        pairs = [(team_list[i], team_list[i+1]) for i in range(0, len(team_list) - 1, 2)]
        for home, away in pairs:
            d = teams_data[home]
            noise = lambda: random.gauss(0, 0.02)
            noise_small = lambda: random.gauss(0, 0.01)

            # Derived xG values for score-adj and flurry-adj
            xg_for = round(d[4] * 0.9 + random.gauss(0, 0.3), 2)
            xg_against = round(d[5] * 0.9 + random.gauss(0, 0.3), 2)
            score_adj_xg_for = round(xg_for * (1 + noise_small()), 2)
            score_adj_xg_against = round(xg_against * (1 + noise_small()), 2)
            flurry_adj_xg_for = round(xg_for * (0.95 + noise_small()), 2)
            flurry_adj_xg_against = round(xg_against * (0.95 + noise_small()), 2)
            hd_for = round(d[2] + random.gauss(0, 1))
            hd_against = round(d[3] + random.gauss(0, 1))
            hd_xg_for = round(hd_for * 0.12 + random.gauss(0, 0.05), 3)
            hd_xg_against = round(hd_against * 0.12 + random.gauss(0, 0.05), 3)
            md_xg_for = round(max(0, xg_for - hd_xg_for) * 0.6, 3)
            md_xg_against = round(max(0, xg_against - hd_xg_against) * 0.6, 3)
            rebound_xg_for = round(hd_xg_for * d[11] + noise_small(), 3)
            rebound_xg_against = round(hd_xg_against * (1 - d[11]) + noise_small(), 3)
            fo_total = round(55 + random.gauss(0, 5))
            fo_won = round(fo_total * (d[9] + noise_small()))
            ta_for = round(8 * d[10] + random.gauss(0, 1))
            ga_for = round(8 * (1 - d[10]) + random.gauss(0, 1))
            dz_ga = round(d[12] + random.gauss(0, 0.8), 1)

            # Use team GBG format so _extract_team_gbg() picks it up
            rows.append({
                "playerTeam": home,
                "home_or_away": "HOME",
                "situation": "all",
                "gameDate": date,
                "season": "2024",
                "xGoalsPercentage": str(round(d[0] + noise(), 4)),
                "corsiPercentage": str(round(d[1] + noise(), 4)),
                "fenwickPercentage": str(round(d[8] + noise(), 4)),
                "highDangerShotsFor": str(max(0, hd_for)),
                "highDangerShotsAgainst": str(max(0, hd_against)),
                "goalsFor": str(round(d[4] + random.gauss(0, 0.8))),
                "goalsAgainst": str(round(d[5] + random.gauss(0, 0.8))),
                "shotsOnGoalFor": str(round(d[6] + random.gauss(0, 2))),
                "shotsOnGoalAgainst": str(round(d[7] + random.gauss(0, 2))),
                "xGoalsFor": str(xg_for),
                "xGoalsAgainst": str(xg_against),
                "scoreVenueAdjustedxGoalsFor": str(score_adj_xg_for),
                "scoreVenueAdjustedxGoalsAgainst": str(score_adj_xg_against),
                "flurryAdjustedxGoalsFor": str(flurry_adj_xg_for),
                "flurryAdjustedxGoalsAgainst": str(flurry_adj_xg_against),
                "highDangerxGoalsFor": str(max(0, hd_xg_for)),
                "highDangerxGoalsAgainst": str(max(0, hd_xg_against)),
                "mediumDangerxGoalsFor": str(max(0, md_xg_for)),
                "mediumDangerxGoalsAgainst": str(max(0, md_xg_against)),
                "reboundxGoalsFor": str(max(0, rebound_xg_for)),
                "reboundxGoalsAgainst": str(max(0, rebound_xg_against)),
                "faceOffsWonFor": str(max(0, fo_won)),
                "faceOffsWonAgainst": str(max(0, fo_total - fo_won)),
                "takeawaysFor": str(max(0, ta_for)),
                "giveawaysFor": str(max(0, ga_for)),
                "dZoneGiveawaysFor": str(max(0, dz_ga)),
                "penaltiesFor": str(round(3 + random.gauss(0, 0.5))),
                "penaltiesAgainst": str(round(3 + random.gauss(0, 0.5))),
            })

            # Away team row
            ad = teams_data[away]
            a_xg_for = round(ad[4] * 0.9 + random.gauss(0, 0.3), 2)
            a_xg_against = round(ad[5] * 0.9 + random.gauss(0, 0.3), 2)
            a_hd_for = round(ad[2] + random.gauss(0, 1))
            a_hd_against = round(ad[3] + random.gauss(0, 1))
            rows.append({
                "playerTeam": away,
                "home_or_away": "AWAY",
                "situation": "all",
                "gameDate": date,
                "season": "2024",
                "xGoalsPercentage": str(round(ad[0] + noise(), 4)),
                "corsiPercentage": str(round(ad[1] + noise(), 4)),
                "fenwickPercentage": str(round(ad[8] + noise(), 4)),
                "highDangerShotsFor": str(max(0, a_hd_for)),
                "highDangerShotsAgainst": str(max(0, a_hd_against)),
                "goalsFor": str(round(ad[4] + random.gauss(0, 0.8))),
                "goalsAgainst": str(round(ad[5] + random.gauss(0, 0.8))),
                "shotsOnGoalFor": str(round(ad[6] + random.gauss(0, 2))),
                "shotsOnGoalAgainst": str(round(ad[7] + random.gauss(0, 2))),
                "xGoalsFor": str(a_xg_for),
                "xGoalsAgainst": str(a_xg_against),
                "scoreVenueAdjustedxGoalsFor": str(round(a_xg_for * (1 + noise_small()), 2)),
                "scoreVenueAdjustedxGoalsAgainst": str(round(a_xg_against * (1 + noise_small()), 2)),
                "flurryAdjustedxGoalsFor": str(round(a_xg_for * (0.95 + noise_small()), 2)),
                "flurryAdjustedxGoalsAgainst": str(round(a_xg_against * (0.95 + noise_small()), 2)),
                "highDangerxGoalsFor": str(max(0, round(a_hd_for * 0.12 + random.gauss(0, 0.05), 3))),
                "highDangerxGoalsAgainst": str(max(0, round(a_hd_against * 0.12 + random.gauss(0, 0.05), 3))),
                "mediumDangerxGoalsFor": str(max(0, round(a_xg_for * 0.35, 3))),
                "mediumDangerxGoalsAgainst": str(max(0, round(a_xg_against * 0.35, 3))),
                "reboundxGoalsFor": str(round(max(0, a_hd_for * 0.12 * ad[11]), 3)),
                "reboundxGoalsAgainst": str(round(max(0, a_hd_against * 0.12 * (1 - ad[11])), 3)),
                "faceOffsWonFor": str(round(55 * ad[9])),
                "faceOffsWonAgainst": str(round(55 * (1 - ad[9]))),
                "takeawaysFor": str(round(8 * ad[10])),
                "giveawaysFor": str(round(8 * (1 - ad[10]))),
                "dZoneGiveawaysFor": str(round(ad[12] + random.gauss(0, 0.5), 1)),
                "penaltiesFor": str(round(3 + random.gauss(0, 0.5))),
                "penaltiesAgainst": str(round(3 + random.gauss(0, 0.5))),
            })
    return rows


def _build_demo_odds(matchups: list[tuple[str, str, str]]) -> list[dict]:
    """Build realistic odds events for given matchups with Quebec-legal books."""
    events = []
    # Quebec-legal sportsbooks
    books = [
        "Bet365", "Betway", "Bet99", "FanDuel", "DraftKings",
        "BetMGM", "Pinnacle", "Mise-o-jeu", "BetVictor", "PointsBet",
    ]
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

        bookmakers = []
        for book in books:
            # Each book has slightly different lines
            random.seed(hash(home + away + book))
            h_var = random.choice([-10, -5, 0, 0, 5, 10, 15])
            a_var = random.choice([-10, -5, 0, 0, 5, 10, 15])
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
    now = datetime.now()
    current_season = now.year if now.month >= 10 else now.year - 1
    parser.add_argument("--season", type=int, default=current_season)
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
            from app.data.data_sources import fetch_team_game_by_game
            games = fetch_team_game_by_game(args.season)
            print(f"  -> Loaded {len(games)} rows via team game-by-game (100+ columns)")
        except Exception:
            try:
                from app.data.data_sources import fetch_moneypuck_games
                games = fetch_moneypuck_games(args.season)
                print(f"  -> Loaded {len(games)} rows via bulk CSV (fallback)")
            except Exception:
                print("  -> Network unavailable, switching to demo mode")
                use_demo = True

    if not use_demo:
        print("\n[2/4] Fetching NHL goalie stats...")
        try:
            from app.data.nhl_api import fetch_goalie_stats
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
            from app.data.data_sources import fetch_odds
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
    python -m app.web.web_preview            # http://localhost:8080

  Model: 16-metric composite | Logistic win prob | Confidence-adj Kelly
  Data: MoneyPuck team GBG (100+ cols) + NHL API goalies + The Odds API
""")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
