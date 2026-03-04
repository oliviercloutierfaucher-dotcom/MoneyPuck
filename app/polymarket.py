"""Polymarket integration for NHL prediction markets.

Fetches NHL game markets from the Polymarket Gamma API and extracts
crowd-sourced win probabilities. No authentication required for reads.

The NHL has an official partnership with Polymarket (Oct 2025), so
game-level markets are available for most NHL matchups.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .data_sources import TEAM_NAME_TO_CODE, team_code
from .logging_config import get_logger

log = get_logger("polymarket")

GAMMA_API = "https://gamma-api.polymarket.com"
_TIMEOUT = 12  # seconds


def _get_json(url: str) -> Any:
    """Fetch JSON from a URL with error handling."""
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "MoneyPuck/1.0"})
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        log.warning("Polymarket API error: %s — %s", url, exc)
        return None


def fetch_nhl_series_id() -> int | None:
    """Discover the NHL series_id from the /sports endpoint."""
    data = _get_json(f"{GAMMA_API}/sports")
    if not data or not isinstance(data, list):
        return None
    for sport in data:
        name = (sport.get("sport") or "").lower()
        if "nhl" in name or "hockey" in name:
            # series field might be an ID or a string — try to extract
            series = sport.get("series")
            if isinstance(series, int):
                return series
            if isinstance(series, str):
                # Could be a JSON string or just an ID
                try:
                    return int(series)
                except ValueError:
                    pass
            # Also check for a series_id field
            sid = sport.get("series_id")
            if sid is not None:
                try:
                    return int(sid)
                except (ValueError, TypeError):
                    pass
    return None


def fetch_nhl_events(series_id: int | None = None) -> list[dict]:
    """Fetch active NHL events from Polymarket.

    Each event represents a game with markets (e.g., "Will TOR beat MTL?").
    Returns list of dicts with: home, away, polymarket_prob, question, slug.
    """
    # Strategy 1: Use series_id if available
    if series_id:
        url = f"{GAMMA_API}/events?series_id={series_id}&active=true&closed=false&limit=50&order=startDate&ascending=true"
        data = _get_json(url)
        if data and isinstance(data, list) and len(data) > 0:
            return _parse_events(data)

    # Strategy 2: Search by tag
    for tag in ["nhl", "hockey"]:
        url = f"{GAMMA_API}/events?tag={tag}&active=true&closed=false&limit=50"
        data = _get_json(url)
        if data and isinstance(data, list) and len(data) > 0:
            return _parse_events(data)

    # Strategy 3: Search by keyword
    url = f"{GAMMA_API}/events?title=NHL&active=true&closed=false&limit=50"
    data = _get_json(url)
    if data and isinstance(data, list):
        return _parse_events(data)

    return []


def _parse_events(events: list[dict]) -> list[dict]:
    """Parse Polymarket events into normalized game records."""
    results = []
    for event in events:
        title = event.get("title") or event.get("question") or ""
        markets = event.get("markets") or []

        for market in markets:
            parsed = _parse_game_market(market, title)
            if parsed:
                results.append(parsed)

    return results


# Patterns to extract team names from market questions
_VS_PATTERN = re.compile(
    r"(?:will\s+)?(.+?)\s+(?:vs?\.?|beat|defeat|win against|over)\s+(.+?)[\?\.]?\s*$",
    re.IGNORECASE,
)
_TEAM_PATTERN = re.compile(
    r"(.+?)\s+(?:to win|win|ML|moneyline)",
    re.IGNORECASE,
)


def _parse_game_market(market: dict, event_title: str) -> dict | None:
    """Parse a single market into a game record with probabilities.

    Returns dict with: home, away, poly_home_prob, poly_away_prob, question, slug
    or None if not a recognizable NHL game market.
    """
    question = market.get("question") or event_title or ""
    outcomes_raw = market.get("outcomes") or "[]"
    prices_raw = market.get("outcomePrices") or "[]"

    # Parse JSON strings if needed
    if isinstance(outcomes_raw, str):
        try:
            outcomes = json.loads(outcomes_raw)
        except json.JSONDecodeError:
            outcomes = []
    else:
        outcomes = outcomes_raw

    if isinstance(prices_raw, str):
        try:
            prices = [float(p) for p in json.loads(prices_raw)]
        except (json.JSONDecodeError, ValueError):
            prices = []
    else:
        prices = [float(p) for p in prices_raw] if prices_raw else []

    if len(outcomes) < 2 or len(prices) < 2:
        return None

    # Try to identify teams from outcomes or question
    team_a, team_b = None, None
    prob_a, prob_b = prices[0], prices[1]

    # Check if outcomes are team names
    code_a = _match_team(outcomes[0])
    code_b = _match_team(outcomes[1])

    if code_a and code_b:
        team_a, team_b = code_a, code_b
    else:
        # Try parsing from the question
        m = _VS_PATTERN.search(question)
        if m:
            team_a = _match_team(m.group(1).strip())
            team_b = _match_team(m.group(2).strip())

    if not team_a or not team_b:
        return None

    return {
        "home": team_b,  # Convention: second team listed is usually home
        "away": team_a,
        "poly_home_prob": round(prob_b, 4),
        "poly_away_prob": round(prob_a, 4),
        "question": question,
        "slug": market.get("slug") or "",
        "condition_id": market.get("conditionId") or market.get("condition_id") or "",
    }


def _match_team(name: str) -> str | None:
    """Try to match a string to an NHL team code."""
    name = name.strip()

    # Direct code match
    if name.upper() in TEAM_NAME_TO_CODE.values():
        return name.upper()

    # Full name match
    code = team_code(name)
    if code != name:  # team_code returns input if no match
        return code

    # Check if any team name is contained in the string
    name_lower = name.lower()
    for full_name, tc in TEAM_NAME_TO_CODE.items():
        # Match on city or team name
        parts = full_name.lower().split()
        if any(p in name_lower for p in parts if len(p) > 3):
            return tc

    return None


def match_polymarket_to_games(
    poly_events: list[dict], games: list[dict]
) -> dict[str, dict]:
    """Match Polymarket events to our game data by team codes.

    Returns a dict keyed by "HOME-AWAY" with the Polymarket data.
    """
    matched: dict[str, dict] = {}
    for pe in poly_events:
        h, a = pe.get("home", ""), pe.get("away", "")
        if not h or not a:
            continue
        # Try both orderings since home/away might be swapped
        key1 = f"{h}-{a}"
        key2 = f"{a}-{h}"
        for g in games:
            game_key = f"{g['home']}-{g['away']}"
            if game_key == key1:
                matched[game_key] = pe
                break
            elif game_key == key2:
                # Swap probabilities
                matched[game_key] = {
                    **pe,
                    "home": g["home"],
                    "away": g["away"],
                    "poly_home_prob": pe["poly_away_prob"],
                    "poly_away_prob": pe["poly_home_prob"],
                }
                break

    return matched
