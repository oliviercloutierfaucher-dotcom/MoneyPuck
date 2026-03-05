"""Player props fetching and analysis for NHL games.

Fetches player prop markets from The Odds API's per-event endpoint:
  GET /v4/sports/icehockey_nhl/events/{event_id}/odds
      ?markets=player_points,player_assists,player_goals,
               player_shots_on_goal,player_saves
      &oddsFormat=american

The API charges one request per event per call, so props are fetched
on demand rather than in bulk. Use `fetch_player_props` per game.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from app.data.data_sources import _fetch_with_retry
from app.logging_config import get_logger

log = get_logger("player_props")

ODDS_API_EVENTS_BASE = (
    "https://api.the-odds-api.com/v4/sports/icehockey_nhl/events"
)

# All prop market keys we request
PROP_MARKETS = [
    "player_points",
    "player_assists",
    "player_goals",
    "player_shots_on_goal",
    "player_saves",
]

# Human-readable label for each market key
MARKET_LABELS: dict[str, str] = {
    "player_points": "Points",
    "player_assists": "Assists",
    "player_goals": "Goals",
    "player_shots_on_goal": "Shots",
    "player_saves": "Saves",
}


@dataclass
class PropLine:
    """A single player prop line from one sportsbook."""

    player_name: str
    market: str           # e.g. "player_goals"
    line: float           # the over/under line
    over_odds: int        # American odds for the over
    under_odds: int       # American odds for the under
    sportsbook: str       # display name, e.g. "FanDuel"
    sportsbook_key: str   # API key, e.g. "fanduel"


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def fetch_player_props(
    api_key: str,
    event_id: str,
    regions: str = "ca",
    bookmakers: str = "",
) -> list[PropLine]:
    """Fetch player props from The Odds API for a single game event.

    Parameters
    ----------
    api_key:
        The Odds API key.
    event_id:
        The Odds API event ``id`` field (e.g. ``"abc123def456..."``)
    regions:
        API region parameter (``"ca"`` or ``"us"``).
    bookmakers:
        Comma-separated bookmaker keys to filter. Empty = all.

    Returns
    -------
    list[PropLine]
        One entry per player / market / sportsbook combination.
        Returns an empty list when the event has no props or on error.
    """
    if not api_key or not api_key.strip():
        raise ValueError("Odds API key must not be empty")
    if not event_id or not event_id.strip():
        raise ValueError("event_id must not be empty")

    params: dict[str, str] = {
        "apiKey": api_key,
        "regions": regions,
        "markets": ",".join(PROP_MARKETS),
        "oddsFormat": "american",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers

    url = f"{ODDS_API_EVENTS_BASE}/{event_id}/odds?{urlencode(params)}"
    log.info("Fetching player props for event_id=%s", event_id)

    try:
        data = _fetch_with_retry(url, label=f"PlayerProps({event_id})")
    except Exception as exc:
        log.warning("Failed to fetch player props for %s: %s", event_id, exc)
        return []

    try:
        raw = json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        log.warning("Failed to parse player props response for %s: %s", event_id, exc)
        return []

    return _parse_props_response(raw)


def _parse_props_response(raw: dict[str, Any]) -> list[PropLine]:
    """Extract PropLine objects from a raw Odds API event-odds response."""
    props: list[PropLine] = []

    bookmakers = raw.get("bookmakers", [])
    if not isinstance(bookmakers, list):
        return props

    for bm in bookmakers:
        bm_key = bm.get("key", "")
        bm_title = bm.get("title", bm_key)

        for market in bm.get("markets", []):
            market_key = market.get("key", "")
            if market_key not in PROP_MARKETS:
                continue

            # Each outcome is one player's over or under
            # Group by player description (The Odds API puts player name
            # as ``description`` on each outcome)
            player_sides: dict[str, dict[str, Any]] = {}
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")       # "Over" or "Under"
                desc = outcome.get("description", "") # player name
                price = outcome.get("price", 0)
                point = outcome.get("point", 0.5)
                if not desc:
                    continue
                if desc not in player_sides:
                    player_sides[desc] = {"line": float(point)}
                if name == "Over":
                    player_sides[desc]["over_odds"] = int(price)
                elif name == "Under":
                    player_sides[desc]["under_odds"] = int(price)

            for player, sides in player_sides.items():
                over_odds = sides.get("over_odds")
                under_odds = sides.get("under_odds")
                if over_odds is None or under_odds is None:
                    continue  # need both sides
                props.append(
                    PropLine(
                        player_name=player,
                        market=market_key,
                        line=sides["line"],
                        over_odds=over_odds,
                        under_odds=under_odds,
                        sportsbook=bm_title,
                        sportsbook_key=bm_key,
                    )
                )

    log.debug("Parsed %d prop lines for event", len(props))
    return props


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def compare_props(props: list[PropLine]) -> list[dict[str, Any]]:
    """Find the best over and under odds for each player + market combination.

    Groups props by (player_name, market, line) and returns one record per
    group with the best over odds and best under odds across all books.

    Returns
    -------
    list[dict]
        Sorted by book_spread ascending (tightest markets first).
        Each dict contains:
          - player_name, market, market_label, line
          - best_over_odds, best_over_book, best_over_key
          - best_under_odds, best_under_book, best_under_key
          - book_spread  (diff between best over implied % and best under implied %)
    """
    if not props:
        return []

    # Group by (player, market, line)
    groups: dict[tuple[str, str, float], list[PropLine]] = {}
    for p in props:
        key = (p.player_name, p.market, p.line)
        groups.setdefault(key, []).append(p)

    results = []
    for (player, market, line), lines in groups.items():
        # Best over = highest American odds (most favourable to bettor)
        best_over = max(lines, key=lambda x: x.over_odds)
        # Best under = highest American odds for the under
        best_under = max(lines, key=lambda x: x.under_odds)

        over_imp = _american_to_implied(best_over.over_odds)
        under_imp = _american_to_implied(best_under.under_odds)
        # Book spread = sum of implied probs minus 1 (the vig / juice)
        # Lower = tighter market = more liquid
        book_spread = round(over_imp + under_imp - 1.0, 4)

        results.append({
            "player_name": player,
            "market": market,
            "market_label": MARKET_LABELS.get(market, market),
            "line": line,
            "best_over_odds": best_over.over_odds,
            "best_over_book": best_over.sportsbook,
            "best_over_key": best_over.sportsbook_key,
            "best_under_odds": best_under.under_odds,
            "best_under_book": best_under.sportsbook,
            "best_under_key": best_under.sportsbook_key,
            "book_spread": book_spread,
        })

    results.sort(key=lambda x: x["book_spread"])
    return results


def find_prop_edges(props: list[PropLine]) -> list[dict[str, Any]]:
    """Identify props where one book's line differs from consensus.

    For each (player, market) combination, computes the consensus line
    across all books (median) and flags any book whose line deviates by
    more than 0.5 goals/points/shots from consensus.

    A book offering a notably higher line on the over (same or better odds)
    or a notably lower line (more generous under) is flagged as a potential
    edge.

    Returns
    -------
    list[dict]
        Sorted by deviation descending. Each dict:
          - player_name, market, market_label
          - consensus_line, outlier_line, deviation
          - sportsbook, sportsbook_key
          - direction  ("over_value" | "under_value")
          - over_odds, under_odds
    """
    if not props:
        return []

    # Group by (player, market) — lines may differ across books
    groups: dict[tuple[str, str], list[PropLine]] = {}
    for p in props:
        key = (p.player_name, p.market)
        groups.setdefault(key, []).append(p)

    edges = []
    for (player, market), lines in groups.items():
        if len(lines) < 2:
            continue

        all_lines = sorted(p.line for p in lines)
        n = len(all_lines)
        consensus = all_lines[n // 2] if n % 2 else (all_lines[n // 2 - 1] + all_lines[n // 2]) / 2

        for p in lines:
            deviation = abs(p.line - consensus)
            if deviation < 0.5:
                continue

            # Book has an outlier line
            if p.line > consensus:
                # Higher line = easier over (you need more), but more
                # generous under (easier to stay under)
                direction = "under_value"
            else:
                # Lower line = easier over (need fewer)
                direction = "over_value"

            edges.append({
                "player_name": player,
                "market": market,
                "market_label": MARKET_LABELS.get(market, market),
                "consensus_line": consensus,
                "outlier_line": p.line,
                "deviation": round(deviation, 1),
                "sportsbook": p.sportsbook,
                "sportsbook_key": p.sportsbook_key,
                "direction": direction,
                "over_odds": p.over_odds,
                "under_odds": p.under_odds,
            })

    edges.sort(key=lambda x: x["deviation"], reverse=True)
    return edges


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

_DEMO_PLAYERS = {
    "player_goals": [
        ("Auston Matthews", 0.5),
        ("David Pastrnak", 0.5),
        ("Connor McDavid", 0.5),
    ],
    "player_shots_on_goal": [
        ("Auston Matthews", 3.5),
        ("David Pastrnak", 3.5),
        ("Connor McDavid", 4.5),
    ],
    "player_saves": [
        ("Joseph Woll", 25.5),
        ("Jeremy Swayman", 26.5),
        ("Stuart Skinner", 27.5),
    ],
    "player_points": [
        ("Connor McDavid", 1.5),
        ("Auston Matthews", 0.5),
    ],
    "player_assists": [
        ("Connor McDavid", 0.5),
        ("Leon Draisaitl", 0.5),
    ],
}

_DEMO_BOOKS = [
    ("FanDuel", "fanduel"),
    ("DraftKings", "draftkings"),
    ("BetMGM", "betmgm"),
]


def build_demo_props(home_team: str, away_team: str) -> list[PropLine]:
    """Generate realistic-looking demo prop lines for a game.

    Produces 2-3 players per market across 3 books with slight line/odds
    variation to illustrate the comparison features.
    """
    import random

    seed_str = home_team + away_team + "props"
    rng = random.Random(hash(seed_str))

    props: list[PropLine] = []

    # Pick 3 markets for demo
    markets_to_use = rng.sample(list(_DEMO_PLAYERS.keys()), k=3)

    for market in markets_to_use:
        players = _DEMO_PLAYERS[market]
        # Pick 2-3 players
        n_players = rng.randint(2, min(3, len(players)))
        selected = rng.sample(players, k=n_players)

        for player_name, base_line in selected:
            for book_name, book_key in _DEMO_BOOKS:
                # Slight line variation per book (0 or +0.5 shift)
                line_shift = rng.choice([0.0, 0.0, 0.5])
                line = base_line + line_shift

                # Odds near -115 to -125 with small per-book variance
                over_base = rng.randint(-125, -105)
                under_base = rng.randint(-125, -105)

                props.append(
                    PropLine(
                        player_name=player_name,
                        market=market,
                        line=line,
                        over_odds=over_base,
                        under_odds=under_base,
                        sportsbook=book_name,
                        sportsbook_key=book_key,
                    )
                )

    return props


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _american_to_implied(odds: int) -> float:
    """Convert American odds to implied probability (no vig removal)."""
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)
