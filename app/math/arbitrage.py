"""Arbitrage detection across multiple bookmakers and prediction markets.

Finds guaranteed-profit opportunities where the combined implied probability
across the best odds from different sources sums to less than 100%.

Works on raw Odds API-format events (the same structure produced by
``build_market_snapshot``), so it plugs into both the CLI and web dashboard.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.math.math_utils import american_to_decimal


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ArbOpportunity = dict[str, Any]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _margin(dec_a: float, dec_b: float) -> float:
    """Combined implied probability (margin) for two sides."""
    return 1.0 / dec_a + 1.0 / dec_b


def _profit_pct(margin: float) -> float:
    """Guaranteed profit percentage for a given margin < 1."""
    return (1.0 / margin - 1.0) * 100


def _stake_split(dec_a: float, dec_b: float) -> tuple[float, float]:
    """Optimal stake split (%) to guarantee equal payout on both sides."""
    inv_a = 1.0 / dec_a
    inv_b = 1.0 / dec_b
    total = inv_a + inv_b
    return (inv_a / total * 100, inv_b / total * 100)


# ---------------------------------------------------------------------------
# Core: extract best odds per side from an event
# ---------------------------------------------------------------------------

def _extract_moneyline_sides(
    event: dict[str, Any],
) -> list[tuple[str, str, float, str]]:
    """Extract (book_name, side_name, decimal_odds, book_key) for each h2h outcome."""
    sides: list[tuple[str, str, float, str]] = []
    for bm in event.get("bookmakers", []):
        bm_name = bm.get("title", bm.get("key", "unknown"))
        bm_key = bm.get("key", "")
        for market in bm.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price", 0)
                if not name or not price:
                    continue
                try:
                    dec = american_to_decimal(int(price))
                except (ValueError, TypeError):
                    continue
                sides.append((bm_name, name, dec, bm_key))
    return sides


def _extract_spread_sides(
    event: dict[str, Any],
) -> dict[float, list[tuple[str, str, float, float]]]:
    """Extract spread outcomes grouped by line value.

    Returns {line: [(book_name, side_name, decimal_odds, point)]}.
    """
    by_line: dict[float, list[tuple[str, str, float, float]]] = defaultdict(list)
    for bm in event.get("bookmakers", []):
        bm_name = bm.get("title", bm.get("key", "unknown"))
        for market in bm.get("markets", []):
            if market.get("key") != "spreads":
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price", 0)
                point = outcome.get("point", 0)
                if not name or not price:
                    continue
                try:
                    dec = american_to_decimal(int(price))
                except (ValueError, TypeError):
                    continue
                by_line[abs(point)].append((bm_name, name, dec, point))
    return dict(by_line)


def _extract_total_sides(
    event: dict[str, Any],
) -> dict[float, list[tuple[str, str, float]]]:
    """Extract total (over/under) outcomes grouped by line value.

    Returns {line: [(book_name, side_name, decimal_odds)]}.
    """
    by_line: dict[float, list[tuple[str, str, float]]] = defaultdict(list)
    for bm in event.get("bookmakers", []):
        bm_name = bm.get("title", bm.get("key", "unknown"))
        for market in bm.get("markets", []):
            if market.get("key") != "totals":
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price", 0)
                point = outcome.get("point", 0)
                if not name or not price:
                    continue
                try:
                    dec = american_to_decimal(int(price))
                except (ValueError, TypeError):
                    continue
                by_line[point].append((bm_name, name, dec))
    return dict(by_line)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_arbitrages(odds_events: list[dict[str, Any]]) -> list[ArbOpportunity]:
    """Find guaranteed arbitrage opportunities across bookmakers.

    Scans moneyline, spread, and total markets for each event.
    Returns opportunities sorted by profit % descending.

    Parameters
    ----------
    odds_events : list
        Events in Odds API format with nested ``bookmakers[].markets[].outcomes[]``.

    Returns
    -------
    list of dicts, each containing:
        - home_team, away_team, commence_time
        - market (str): "Moneyline", "Spread -1.5", "Total 5.5"
        - side_a, side_a_book, side_a_odds (decimal)
        - side_b, side_b_book, side_b_odds (decimal)
        - margin (float < 1.0)
        - profit_pct (float > 0)
        - stake_a_pct, stake_b_pct (optimal stake split)
    """
    arbs: list[ArbOpportunity] = []

    for event in odds_events:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        commence = event.get("commence_time", "")

        if len(event.get("bookmakers", [])) < 2:
            continue

        # --- Moneyline ---
        ml_sides = _extract_moneyline_sides(event)
        home_sides = [(bm, dec) for bm, name, dec, _ in ml_sides if name == home]
        away_sides = [(bm, dec) for bm, name, dec, _ in ml_sides if name == away]

        if home_sides and away_sides:
            best_home = max(home_sides, key=lambda x: x[1])
            best_away = max(away_sides, key=lambda x: x[1])
            m = _margin(best_home[1], best_away[1])
            if m < 1.0 and best_home[0] != best_away[0]:
                sa, sb = _stake_split(best_home[1], best_away[1])
                arbs.append({
                    "home_team": home, "away_team": away,
                    "commence_time": commence,
                    "market": "Moneyline",
                    "side_a": home, "side_a_book": best_home[0],
                    "side_a_odds": round(best_home[1], 3),
                    "side_b": away, "side_b_book": best_away[0],
                    "side_b_odds": round(best_away[1], 3),
                    "margin": round(m, 4),
                    "profit_pct": round(_profit_pct(m), 2),
                    "stake_a_pct": round(sa, 1),
                    "stake_b_pct": round(sb, 1),
                })

        # --- Spreads ---
        spread_groups = _extract_spread_sides(event)
        for line_val, entries in spread_groups.items():
            # Need at least 2 books with this spread line
            # Group by side (positive point = underdog, negative = favorite)
            fav = [(bm, dec) for bm, name, dec, pt in entries if pt < 0]
            dog = [(bm, dec) for bm, name, dec, pt in entries if pt > 0]
            if fav and dog:
                best_fav = max(fav, key=lambda x: x[1])
                best_dog = max(dog, key=lambda x: x[1])
                m = _margin(best_fav[1], best_dog[1])
                if m < 1.0 and best_fav[0] != best_dog[0]:
                    sa, sb = _stake_split(best_fav[1], best_dog[1])
                    arbs.append({
                        "home_team": home, "away_team": away,
                        "commence_time": commence,
                        "market": f"Spread {line_val}",
                        "side_a": f"Favorite -{line_val}",
                        "side_a_book": best_fav[0],
                        "side_a_odds": round(best_fav[1], 3),
                        "side_b": f"Underdog +{line_val}",
                        "side_b_book": best_dog[0],
                        "side_b_odds": round(best_dog[1], 3),
                        "margin": round(m, 4),
                        "profit_pct": round(_profit_pct(m), 2),
                        "stake_a_pct": round(sa, 1),
                        "stake_b_pct": round(sb, 1),
                    })

        # --- Totals ---
        total_groups = _extract_total_sides(event)
        for line_val, entries in total_groups.items():
            overs = [(bm, dec) for bm, name, dec in entries if name == "Over"]
            unders = [(bm, dec) for bm, name, dec in entries if name == "Under"]
            if overs and unders:
                best_over = max(overs, key=lambda x: x[1])
                best_under = max(unders, key=lambda x: x[1])
                m = _margin(best_over[1], best_under[1])
                if m < 1.0 and best_over[0] != best_under[0]:
                    sa, sb = _stake_split(best_over[1], best_under[1])
                    arbs.append({
                        "home_team": home, "away_team": away,
                        "commence_time": commence,
                        "market": f"Total {line_val}",
                        "side_a": f"Over {line_val}",
                        "side_a_book": best_over[0],
                        "side_a_odds": round(best_over[1], 3),
                        "side_b": f"Under {line_val}",
                        "side_b_book": best_under[0],
                        "side_b_odds": round(best_under[1], 3),
                        "margin": round(m, 4),
                        "profit_pct": round(_profit_pct(m), 2),
                        "stake_a_pct": round(sa, 1),
                        "stake_b_pct": round(sb, 1),
                    })

    arbs.sort(key=lambda x: x["profit_pct"], reverse=True)
    return arbs


def find_near_arbs(
    odds_events: list[dict[str, Any]],
    threshold: float = 0.02,
) -> list[ArbOpportunity]:
    """Find near-arbitrage opportunities (low-vig markets).

    Returns markets where the combined margin is below ``1 + threshold``
    but above 1.0 (not a true arb). These represent low-juice markets
    where a slight line movement could create an arb.

    Same return format as ``find_arbitrages`` but ``profit_pct`` will be
    negative (representing the remaining vig, not guaranteed profit).
    """
    near: list[ArbOpportunity] = []

    for event in odds_events:
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        commence = event.get("commence_time", "")

        if len(event.get("bookmakers", [])) < 2:
            continue

        # --- Moneyline only for near-arbs (most actionable) ---
        ml_sides = _extract_moneyline_sides(event)
        home_sides = [(bm, dec) for bm, name, dec, _ in ml_sides if name == home]
        away_sides = [(bm, dec) for bm, name, dec, _ in ml_sides if name == away]

        if home_sides and away_sides:
            best_home = max(home_sides, key=lambda x: x[1])
            best_away = max(away_sides, key=lambda x: x[1])
            m = _margin(best_home[1], best_away[1])
            if 1.0 <= m < 1.0 + threshold and best_home[0] != best_away[0]:
                sa, sb = _stake_split(best_home[1], best_away[1])
                vig_pct = (m - 1.0) * 100
                near.append({
                    "home_team": home, "away_team": away,
                    "commence_time": commence,
                    "market": "Moneyline",
                    "side_a": home, "side_a_book": best_home[0],
                    "side_a_odds": round(best_home[1], 3),
                    "side_b": away, "side_b_book": best_away[0],
                    "side_b_odds": round(best_away[1], 3),
                    "margin": round(m, 4),
                    "vig_pct": round(vig_pct, 2),
                    "stake_a_pct": round(sa, 1),
                    "stake_b_pct": round(sb, 1),
                })

    near.sort(key=lambda x: x["margin"])
    return near
