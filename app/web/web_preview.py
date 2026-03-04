from __future__ import annotations

import json
import math
import os
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.data.data_sources import get_books_for_region, QUEBEC_BOOKS, team_code, TEAM_NAME_TO_CODE
from app.data.polymarket import fetch_nhl_events, fetch_nhl_series_id, match_polymarket_to_games
from app.logging_config import get_logger, setup_logging
from app.math.math_utils import (
    american_to_decimal,
    american_to_implied_probability,
    goalie_matchup_adjustment,
    logistic_win_probability,
)
from app.core.models import TrackerConfig, ValueCandidate
from app.web.presentation import render_dashboard, render_html_preview, to_serializable
from app.core.service import build_market_snapshot, score_snapshot

log = get_logger("web_preview")

SUPPORTED_REGIONS = {"ca", "us", "qc", "on"}


def _float_param(params: dict[str, list[str]], name: str, default: float) -> float:
    try:
        value = params.get(name, [str(default)])[0]
        result = float(value)
        if not math.isfinite(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def _int_param(params: dict[str, list[str]], name: str, default: int) -> int:
    try:
        value = params.get(name, [str(default)])[0]
        return int(value)
    except (ValueError, TypeError):
        return default


def _build_config(params: dict[str, list[str]]) -> TrackerConfig:
    """Build a TrackerConfig from query parameters.

    API key is read ONLY from the environment variable for security.
    """
    api_key = os.getenv("ODDS_API_KEY", "")
    if not api_key:
        raise ValueError(
            "Missing Odds API key. Set the ODDS_API_KEY environment variable."
        )

    region = params.get("region", ["ca"])[0]
    # Map sub-regions to API region
    api_region = "ca" if region in {"qc", "on", "ca"} else region
    if api_region not in {"ca", "us"}:
        raise ValueError(f"Unsupported region '{region}'.")

    bankroll = _float_param(params, "bankroll", 1000.0)
    if bankroll <= 0:
        raise ValueError("Bankroll must be positive")

    # Get bookmaker filter for the region
    books = get_books_for_region(region)
    bookmaker_keys = ",".join(books.keys())

    return TrackerConfig(
        odds_api_key=api_key,
        region=api_region,
        bookmakers=bookmaker_keys,
        season=_int_param(params, "season", 2024),
        min_edge=max(0.0, _float_param(params, "min_edge", 2.0)),
        min_ev=max(0.0, _float_param(params, "min_ev", 0.02)),
        bankroll=bankroll,
        max_fraction_per_bet=min(1.0, max(0.0, _float_param(params, "max_fraction_per_bet", 0.03))),
    )


# ---------------------------------------------------------------------------
# Demo data builders (Quebec books)
# ---------------------------------------------------------------------------

DEMO_MATCHUPS = [
    ("TOR", "MTL", "2026-03-03T19:00:00Z"),
    ("FLA", "NYR", "2026-03-03T19:30:00Z"),
    ("EDM", "VAN", "2026-03-03T22:00:00Z"),
    ("WPG", "CHI", "2026-03-03T20:00:00Z"),
    ("DAL", "CBJ", "2026-03-03T19:00:00Z"),
    ("COL", "SJS", "2026-03-03T22:30:00Z"),
    ("CAR", "DET", "2026-03-03T19:00:00Z"),
    ("BOS", "BUF", "2026-03-03T19:00:00Z"),
]

DEMO_STRENGTH = {
    "FLA": 1.13, "WPG": 0.89, "EDM": 0.87, "CAR": 0.81, "DAL": 0.79,
    "COL": 0.66, "TOR": 0.51, "VGK": 0.47, "BOS": 0.46, "NYR": 0.40,
    "NJD": 0.37, "MIN": 0.33, "TBL": 0.30, "VAN": 0.19, "LAK": 0.14,
    "OTT": 0.03, "WSH": 0.02, "CGY": -0.01, "SEA": -0.09, "NYI": -0.14,
    "DET": -0.17, "STL": -0.19, "PHI": -0.32, "PIT": -0.35, "BUF": -0.51,
    "ANA": -0.70, "MTL": -0.74, "UTA": -0.76, "NSH": -0.78, "CBJ": -0.80,
    "SJS": -1.35, "CHI": -1.45,
}


def _build_demo_dashboard(params: dict[str, list[str]]) -> dict:
    """Build full demo dashboard data with Quebec books."""
    region = params.get("region", ["qc"])[0]
    books = get_books_for_region(region)
    book_names = list(books.values())
    bankroll = _float_param(params, "bankroll", 1000.0)
    min_edge = _float_param(params, "min_edge", 2.0)
    min_ev = _float_param(params, "min_ev", 0.02)

    games = []
    value_bets = []

    for home, away, commence in DEMO_MATCHUPS:
        random.seed(hash(home + away + "qc"))
        hs = DEMO_STRENGTH.get(home, 0)
        as_ = DEMO_STRENGTH.get(away, 0)

        # Model probability from strength differential
        diff = hs - as_ + 0.15  # home advantage
        home_prob = 1 / (1 + math.exp(-diff))
        away_prob = 1 - home_prob

        # Market consensus differs from model (creates edges)
        random.seed(hash(home + away + "market"))
        market_shift = random.gauss(0, 0.04)  # all books shifted same direction

        # Generate per-book odds
        game_books = []
        for bk_key, bk_name in books.items():
            random.seed(hash(home + away + bk_key))
            vig = random.uniform(0.03, 0.05)
            # All books agree on market consensus, small per-book noise
            h_implied = home_prob + market_shift + vig / 2 + random.gauss(0, 0.008)
            a_implied = away_prob - market_shift + vig / 2 + random.gauss(0, 0.008)
            h_implied = max(0.05, min(0.95, h_implied))
            a_implied = max(0.05, min(0.95, a_implied))
            h_odds = _implied_to_american(h_implied)
            a_odds = _implied_to_american(a_implied)

            # Edge = model prob - book implied
            h_edge = (home_prob - h_implied) * 100
            a_edge = (away_prob - a_implied) * 100

            # Spread odds (puck line -1.5 / +1.5) — correlated pair
            random.seed(hash(home + away + bk_key + "spread"))
            # Favorite gets + odds on spread, underdog gets - odds
            fav_spread = random.choice([+155, +165, +175, +185])
            dog_spread = round(-fav_spread * random.uniform(1.05, 1.20))
            if home_prob >= 0.5:
                spread_home, spread_away = fav_spread, dog_spread
            else:
                spread_home, spread_away = dog_spread, fav_spread

            # Total odds (over/under) — correlated pair
            random.seed(hash(home + away + bk_key + "total"))
            expected_total = 5.5 + (hs + abs(as_)) * 0.3 + random.gauss(0, 0.3)
            total_line = round(expected_total * 2) / 2  # round to nearest 0.5
            total_line = max(4.5, min(7.5, total_line))
            over_base = random.choice([-115, -110, -105])
            # Mirror: if over is -110, under is roughly -110 with small vig
            under_odds = round(-100 * (1 - 1 / american_to_decimal(over_base) + 0.045)
                               / (1 / american_to_decimal(over_base) - 0.045))
            under_odds = max(-130, min(-100, under_odds))
            over_odds = over_base

            game_books.append({
                "name": bk_name,
                "key": bk_key,
                "home_odds": h_odds,
                "away_odds": a_odds,
                "home_implied": round(h_implied, 4),
                "away_implied": round(a_implied, 4),
                "home_edge": round(h_edge, 2),
                "away_edge": round(a_edge, 2),
                "home_spread": -1.5,
                "away_spread": 1.5,
                "home_spread_odds": spread_home,
                "away_spread_odds": spread_away,
                "total_line": total_line,
                "over_odds": over_odds,
                "under_odds": under_odds,
            })

            # Check for value bets (moneyline)
            for side, model_p, impl_p, odds in [
                (home, home_prob, h_implied, h_odds),
                (away, away_prob, a_implied, a_odds),
            ]:
                edge_pp = (model_p - impl_p) * 100
                dec_odds = american_to_decimal(odds)
                ev = model_p * (dec_odds - 1) - (1 - model_p)
                if edge_pp >= min_edge and ev >= min_ev:
                    stake = min(bankroll * 0.03, bankroll * 0.15 / 5)
                    value_bets.append({
                        "commence_time_utc": commence,
                        "home_team": home,
                        "away_team": away,
                        "side": side,
                        "market": "ML",
                        "sportsbook": bk_name,
                        "american_odds": odds,
                        "decimal_odds": round(dec_odds, 2),
                        "implied_probability": round(impl_p, 4),
                        "model_probability": round(model_p, 4),
                        "edge_probability_points": round(edge_pp, 2),
                        "expected_value_per_dollar": round(ev, 4),
                        "kelly_fraction": round(max(0, (model_p * dec_odds - 1) / (dec_odds - 1)) * 0.5, 4),
                        "confidence": round(0.55 + random.uniform(0, 0.25), 2),
                        "recommended_stake": round(stake, 2),
                        "stake_fraction": round(stake / bankroll, 4),
                    })

        games.append({
            "home": home,
            "away": away,
            "commence": commence,
            "home_prob": round(home_prob, 4),
            "away_prob": round(away_prob, 4),
            "books": game_books,
        })

    # De-duplicate value bets: keep best per game+side
    best_bets: dict[str, dict] = {}
    for vb in value_bets:
        key = f"{vb['home_team']}-{vb['away_team']}-{vb['side']}-{vb['sportsbook']}"
        if key not in best_bets or vb["edge_probability_points"] > best_bets[key]["edge_probability_points"]:
            best_bets[key] = vb
    value_bets = sorted(best_bets.values(), key=lambda x: x["expected_value_per_dollar"], reverse=True)

    # Add Polymarket probabilities (simulated for demo — live fetches real data)
    for g in games:
        random.seed(hash(g["home"] + g["away"] + "poly"))
        # Polymarket crowd tends to be slightly off from model
        poly_shift = random.gauss(0, 0.04)
        g["poly_home_prob"] = round(max(0.02, min(0.98, g["home_prob"] + poly_shift)), 4)
        g["poly_away_prob"] = round(1 - g["poly_home_prob"], 4)

    # Seed a couple of arb opportunities for demo by tweaking odds on 2 games
    # Make book[0] favor home and book[1] favor away enough for an arb
    if len(games) >= 2 and len(games[1].get("books", [])) >= 2:
        # Game 2 (FLA vs NYR): force a total arb
        games[1]["books"][0]["over_odds"] = 105   # 2.05
        games[1]["books"][1]["under_odds"] = 100  # 2.00
        # Margin: 1/2.05 + 1/2.00 = 0.488 + 0.500 = 0.988 < 1 → arb
    if len(games) >= 4 and len(games[3].get("books", [])) >= 3:
        # Game 4 (WPG vs CHI): force a spread arb
        games[3]["books"][0]["home_spread_odds"] = 205   # 3.05
        games[3]["books"][2]["away_spread_odds"] = 110    # 2.10
        # Margin: 1/3.05 + 1/2.10 = 0.328 + 0.476 = 0.804 < 1 → arb

    arb_opportunities = _detect_arbs(games)

    total_stake = sum(b["recommended_stake"] for b in value_bets)
    avg_edge = sum(b["edge_probability_points"] for b in value_bets) / len(value_bets) if value_bets else 0

    return {
        "mode": "demo",
        "games": games,
        "value_bets": value_bets,
        "arb_opportunities": arb_opportunities,
        "books": book_names,
        "summary": {
            "total_bets": len(value_bets),
            "total_stake": round(total_stake, 2),
            "avg_edge": round(avg_edge, 2),
        },
        "config": {
            "region": region,
            "bankroll": bankroll,
            "min_edge": min_edge,
            "min_ev": min_ev,
        },
    }


def _detect_arbs(games: list[dict]) -> list[dict]:
    """Detect arbitrage opportunities across books for all markets.

    Limitations:
    - Only checks same-market arbs (e.g. ML vs ML, spread vs spread).
      Cross-market arbs (e.g. moneyline vs spread) are not detected.
    - Client-side book filtering in the dashboard does not recalculate
      arbs from the remaining books; it only hides arbs whose books
      are deselected.
    - Real-time execution risk: odds may change between detection and
      bet placement.  Arbs shown here are informational, not guarantees.
    """
    arbs = []
    for g in games:
        books = g.get("books", [])
        if len(books) < 2:
            continue
        home, away = g["home"], g["away"]

        # ML arb: best home decimal vs best away decimal across books
        ml_sides = []
        for b in books:
            h_dec = american_to_decimal(b["home_odds"])
            a_dec = american_to_decimal(b["away_odds"])
            ml_sides.append((b["name"], home, h_dec, away, a_dec))

        # Find best odds for each side
        best_home = max(ml_sides, key=lambda x: x[2])
        best_away = max(ml_sides, key=lambda x: x[4])
        margin = 1 / best_home[2] + 1 / best_away[4]
        if margin < 1.0:
            profit = (1 / margin - 1) * 100
            stake_a = (1 / best_home[2]) / (1 / best_home[2] + 1 / best_away[4]) * 100
            stake_b = 100 - stake_a
            arbs.append({
                "home_team": home,
                "away_team": away,
                "market": "Moneyline",
                "side_a": home,
                "side_a_book": best_home[0],
                "side_a_odds": round(best_home[2], 2),
                "side_b": away,
                "side_b_book": best_away[0],
                "side_b_odds": round(best_away[4], 2),
                "margin": round(margin, 4),
                "profit_pct": round(profit, 2),
                "stake_a_pct": round(stake_a, 2),
                "stake_b_pct": round(stake_b, 2),
            })

        # Spread arb — only compare books offering the SAME spread line
        spread_books = [(b["name"], b) for b in books if b.get("home_spread_odds")]
        if len(spread_books) >= 2:
            # Group books by their home spread value so we only compare
            # matching lines (e.g. -1.5 vs +1.5, not -1.5 vs -2.5)
            from collections import defaultdict
            spread_by_line: dict[float, list[tuple[str, dict]]] = defaultdict(list)
            for name, bdata in spread_books:
                line_val = bdata.get("home_spread", -1.5)
                spread_by_line[line_val].append((name, bdata))

            for spread_val, line_books in spread_by_line.items():
                if len(line_books) < 2:
                    continue
                best_hs = max(line_books, key=lambda x: american_to_decimal(x[1]["home_spread_odds"]))
                best_as = max(line_books, key=lambda x: american_to_decimal(x[1]["away_spread_odds"]))
                hs_dec = american_to_decimal(best_hs[1]["home_spread_odds"])
                as_dec = american_to_decimal(best_as[1]["away_spread_odds"])
                sp_margin = 1 / hs_dec + 1 / as_dec
                if sp_margin < 1.0:
                    profit = (1 / sp_margin - 1) * 100
                    sa = (1 / hs_dec) / (1 / hs_dec + 1 / as_dec) * 100
                    arbs.append({
                        "home_team": home, "away_team": away,
                        "market": f"Spread {spread_val}",
                        "side_a": f"{home} {spread_val}",
                        "side_a_book": best_hs[0],
                        "side_a_odds": round(hs_dec, 2),
                        "side_b": f"{away} {-spread_val}",
                        "side_b_book": best_as[0],
                        "side_b_odds": round(as_dec, 2),
                        "margin": round(sp_margin, 4),
                        "profit_pct": round(profit, 2),
                        "stake_a_pct": round(sa, 2),
                        "stake_b_pct": round(100 - sa, 2),
                    })

        # Total arb — only compare books offering the SAME total line
        total_books = [(b["name"], b) for b in books if b.get("over_odds")]
        if len(total_books) >= 2:
            from collections import defaultdict
            totals_by_line: dict[float, list[tuple[str, dict]]] = defaultdict(list)
            for name, bdata in total_books:
                line_val = bdata.get("total_line", 5.5)
                totals_by_line[line_val].append((name, bdata))

            for line, line_books in totals_by_line.items():
                if len(line_books) < 2:
                    continue
                best_over = max(line_books, key=lambda x: american_to_decimal(x[1]["over_odds"]))
                best_under = max(line_books, key=lambda x: american_to_decimal(x[1]["under_odds"]))
                o_dec = american_to_decimal(best_over[1]["over_odds"])
                u_dec = american_to_decimal(best_under[1]["under_odds"])
                t_margin = 1 / o_dec + 1 / u_dec
                if t_margin < 1.0:
                    profit = (1 / t_margin - 1) * 100
                    sa = (1 / o_dec) / (1 / o_dec + 1 / u_dec) * 100
                    arbs.append({
                        "home_team": home, "away_team": away,
                        "market": f"Total {line}",
                        "side_a": f"Over {line}",
                        "side_a_book": best_over[0],
                        "side_a_odds": round(o_dec, 2),
                        "side_b": f"Under {line}",
                        "side_b_book": best_under[0],
                        "side_b_odds": round(u_dec, 2),
                        "margin": round(t_margin, 4),
                        "profit_pct": round(profit, 2),
                        "stake_a_pct": round(sa, 2),
                        "stake_b_pct": round(100 - sa, 2),
                    })

    arbs.sort(key=lambda x: x["profit_pct"], reverse=True)
    return arbs


def _implied_to_american(p: float) -> int:
    """Convert implied probability to American odds."""
    if p >= 0.5:
        return round(-100 * p / (1 - p))
    else:
        return round(100 * (1 - p) / p)


def _build_live_dashboard(params: dict[str, list[str]]) -> dict:
    """Build dashboard from live API data.

    Uses live odds from The Odds API. When MoneyPuck data is unavailable
    (403 in cloud environments), falls back to calibrated demo strength
    ratings so the model still produces meaningful probabilities.
    """
    config = _build_config(params)
    region = params.get("region", ["qc"])[0]
    books_map = get_books_for_region(region)
    book_display_names = set(books_map.values())

    snapshot, games_rows = build_market_snapshot(config)
    recommendations = score_snapshot(snapshot, config, games_rows)
    strength = snapshot.team_strength

    # If MoneyPuck failed (0 teams), use demo strength ratings
    use_demo_strength = len(strength) < 10
    if use_demo_strength:
        log.info("Using demo strength ratings (MoneyPuck unavailable)")

    # Build per-game data with per-book odds
    games = []
    for event in snapshot.odds_events:
        home_raw = event.get("home_team", "")
        away_raw = event.get("away_team", "")
        commence = event.get("commence_time", "")

        # Map full names to 3-letter codes
        home = team_code(home_raw)
        away = team_code(away_raw)

        # Get strength — from model or demo fallback
        if use_demo_strength:
            hs = DEMO_STRENGTH.get(home, 0)
            as_ = DEMO_STRENGTH.get(away, 0)
            diff = hs - as_ + 0.15
            hp = 1 / (1 + math.exp(-diff))
            ap = 1 - hp
        else:
            home_m = strength.get(home)
            away_m = strength.get(away)
            if not home_m or not away_m:
                hp, ap = 0.5, 0.5
            else:
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

        game_books = []
        for bm in event.get("bookmakers", []):
            bm_title = bm.get("title", "")
            bm_key = bm.get("key", "")

            # Match book by key first, then by title
            display_name = books_map.get(bm_key, "")
            if not display_name and bm_title in book_display_names:
                display_name = bm_title
            if not display_name:
                display_name = bm_title or bm_key

            markets = {m.get("key"): m for m in bm.get("markets", [])}

            # Moneyline
            h2h = markets.get("h2h")
            if not h2h:
                continue
            h2h_out = {o["name"]: o.get("price", 0) for o in h2h.get("outcomes", [])}
            h_odds = h2h_out.get(home_raw, 0) or h2h_out.get(home, 0)
            a_odds = h2h_out.get(away_raw, 0) or h2h_out.get(away, 0)
            if not h_odds or not a_odds:
                continue
            h_imp = american_to_implied_probability(h_odds)
            a_imp = american_to_implied_probability(a_odds)

            book_entry = {
                "name": display_name,
                "home_odds": h_odds,
                "away_odds": a_odds,
                "home_implied": round(h_imp, 4),
                "away_implied": round(a_imp, 4),
                "home_edge": round((hp - h_imp) * 100, 2),
                "away_edge": round((ap - a_imp) * 100, 2),
            }

            # Spreads (puck line)
            spreads = markets.get("spreads")
            if spreads:
                for o in spreads.get("outcomes", []):
                    name = o.get("name", "")
                    if name == home_raw or name == home:
                        book_entry["home_spread"] = o.get("point", -1.5)
                        book_entry["home_spread_odds"] = o.get("price", 0)
                    elif name == away_raw or name == away:
                        book_entry["away_spread"] = o.get("point", 1.5)
                        book_entry["away_spread_odds"] = o.get("price", 0)

            # Totals (over/under)
            totals = markets.get("totals")
            if totals:
                for o in totals.get("outcomes", []):
                    name = o.get("name", "")
                    if name == "Over":
                        book_entry["total_line"] = o.get("point", 5.5)
                        book_entry["over_odds"] = o.get("price", 0)
                    elif name == "Under":
                        book_entry["under_odds"] = o.get("price", 0)

            game_books.append(book_entry)

        games.append({
            "home": home,
            "away": away,
            "commence": commence,
            "home_prob": round(hp, 4),
            "away_prob": round(ap, 4),
            "books": game_books,
        })

    # Rebuild value bets using demo strength if needed
    if use_demo_strength and games:
        value_bets = _extract_value_bets_from_games(games, config)
    else:
        value_bets = to_serializable(recommendations)

    # Fetch Polymarket data
    try:
        series_id = fetch_nhl_series_id()
        poly_events = fetch_nhl_events(series_id)
        poly_map = match_polymarket_to_games(poly_events, games)
        for g in games:
            key = f"{g['home']}-{g['away']}"
            if key in poly_map:
                g["poly_home_prob"] = poly_map[key]["poly_home_prob"]
                g["poly_away_prob"] = poly_map[key]["poly_away_prob"]
        log.info("Polymarket: matched %d/%d games", len(poly_map), len(games))
    except Exception:
        log.warning("Polymarket fetch failed — continuing without it")

    arb_opportunities = _detect_arbs(games)

    all_book_names = sorted({b["name"] for g in games for b in g.get("books", [])})
    total_stake = sum(b["recommended_stake"] for b in value_bets)
    avg_edge = sum(b["edge_probability_points"] for b in value_bets) / len(value_bets) if value_bets else 0

    return {
        "mode": "live" if not use_demo_strength else "live+demo-strength",
        "games": games,
        "value_bets": value_bets,
        "arb_opportunities": arb_opportunities,
        "books": all_book_names,
        "summary": {
            "total_bets": len(value_bets),
            "total_stake": round(total_stake, 2),
            "avg_edge": round(avg_edge, 2),
        },
        "config": {
            "region": region,
            "bankroll": config.bankroll,
            "min_edge": config.min_edge,
            "min_ev": config.min_ev,
        },
    }


def _extract_value_bets_from_games(
    games: list[dict], config: TrackerConfig,
) -> list[dict]:
    """Extract value bets from pre-computed game data with per-book edges."""
    bets = []
    for g in games:
        for b in g.get("books", []):
            for side, model_p, edge, odds in [
                (g["home"], g["home_prob"], b["home_edge"], b["home_odds"]),
                (g["away"], g["away_prob"], b["away_edge"], b["away_odds"]),
            ]:
                if edge < config.min_edge:
                    continue
                dec_odds = american_to_decimal(odds)
                implied = american_to_implied_probability(odds)
                ev = model_p * (dec_odds - 1) - (1 - model_p)
                if ev < config.min_ev:
                    continue
                kelly = max(0, (model_p * dec_odds - 1) / (dec_odds - 1)) * config.kelly_fraction
                stake = min(config.bankroll * kelly, config.bankroll * config.max_fraction_per_bet)
                bets.append({
                    "commence_time_utc": g["commence"],
                    "home_team": g["home"],
                    "away_team": g["away"],
                    "side": side,
                    "market": "ML",
                    "sportsbook": b["name"],
                    "american_odds": odds,
                    "decimal_odds": round(dec_odds, 2),
                    "implied_probability": round(implied, 4),
                    "model_probability": round(model_p, 4),
                    "edge_probability_points": round(edge, 2),
                    "expected_value_per_dollar": round(ev, 4),
                    "kelly_fraction": round(kelly, 4),
                    "confidence": round(min(0.8, 0.5 + edge / 40), 2),
                    "recommended_stake": round(stake, 2),
                    "stake_fraction": round(stake / config.bankroll, 4) if config.bankroll else 0,
                })
    # Best line per game+side
    best: dict[str, dict] = {}
    for bet in bets:
        key = f"{bet['home_team']}-{bet['away_team']}-{bet['side']}"
        if key not in best or bet["expected_value_per_dollar"] > best[key]["expected_value_per_dollar"]:
            best[key] = bet
    return sorted(best.values(), key=lambda x: x["expected_value_per_dollar"], reverse=True)


class PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        use_demo = params.get("demo", ["0"])[0] in {"1", "true", "yes"}

        # Force demo if no API key
        if not os.getenv("ODDS_API_KEY", ""):
            use_demo = True

        try:
            if parsed.path == "/api/dashboard" or parsed.path in {"/", "/index.html"}:
                if use_demo:
                    dashboard_data = _build_demo_dashboard(params)
                else:
                    dashboard_data = _build_live_dashboard(params)

                if parsed.path == "/api/dashboard":
                    body = json.dumps(dashboard_data, indent=2).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                # Render HTML dashboard
                body = render_dashboard(dashboard_data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return

            if parsed.path == "/api/opportunities":
                if use_demo:
                    data = _build_demo_dashboard(params)
                    body = json.dumps(data["value_bets"], indent=2).encode("utf-8")
                else:
                    config = _build_config(params)
                    from app.core.service import run_tracker
                    recommendations = run_tracker(config)
                    body = json.dumps(to_serializable(recommendations), indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))

        except ValueError as exc:
            log.warning("Bad request: %s", exc)
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
        except (OSError, TimeoutError) as exc:
            log.error("Network error: %s", exc)
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Upstream data source unavailable"}).encode("utf-8"))
        except Exception:
            log.exception("Unexpected error")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Internal server error"}).encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:
        log.info(format, *args)


def main() -> None:
    setup_logging()
    host = os.getenv("PREVIEW_HOST", "0.0.0.0")
    port = int(os.getenv("PREVIEW_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), PreviewHandler)
    log.info("Preview server starting on http://%s:%d", host, port)
    print(f"\n  MoneyPuck Edge Intelligence Dashboard")
    print(f"  http://localhost:{port}")
    print(f"  http://localhost:{port}?demo=1  (demo mode)\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
