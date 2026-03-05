"""Tests for app.data.player_props — PropLine, compare_props, find_prop_edges."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.data.player_props import (
    PropLine,
    _american_to_implied,
    _parse_props_response,
    build_demo_props,
    compare_props,
    fetch_player_props,
    find_prop_edges,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prop(
    player: str = "Connor McDavid",
    market: str = "player_goals",
    line: float = 0.5,
    over_odds: int = -120,
    under_odds: int = -110,
    sportsbook: str = "FanDuel",
    sportsbook_key: str = "fanduel",
) -> PropLine:
    return PropLine(
        player_name=player,
        market=market,
        line=line,
        over_odds=over_odds,
        under_odds=under_odds,
        sportsbook=sportsbook,
        sportsbook_key=sportsbook_key,
    )


# ---------------------------------------------------------------------------
# Test 1 — PropLine dataclass creation
# ---------------------------------------------------------------------------


def test_propline_dataclass_creation():
    """PropLine holds all fields correctly."""
    p = PropLine(
        player_name="Auston Matthews",
        market="player_goals",
        line=0.5,
        over_odds=-130,
        under_odds=+110,
        sportsbook="BetMGM",
        sportsbook_key="betmgm",
    )
    assert p.player_name == "Auston Matthews"
    assert p.market == "player_goals"
    assert p.line == 0.5
    assert p.over_odds == -130
    assert p.under_odds == 110
    assert p.sportsbook == "BetMGM"
    assert p.sportsbook_key == "betmgm"


# ---------------------------------------------------------------------------
# Test 2 — compare_props: finds best odds across books
# ---------------------------------------------------------------------------


def test_compare_props_finds_best_odds():
    """compare_props returns the best over/under across books for each player+market."""
    props = [
        _make_prop("McDavid", "player_goals", 0.5, over_odds=-130, under_odds=-110, sportsbook="FanDuel", sportsbook_key="fanduel"),
        _make_prop("McDavid", "player_goals", 0.5, over_odds=-115, under_odds=-120, sportsbook="DraftKings", sportsbook_key="draftkings"),
        _make_prop("McDavid", "player_goals", 0.5, over_odds=-125, under_odds=-105, sportsbook="BetMGM", sportsbook_key="betmgm"),
    ]
    results = compare_props(props)
    assert len(results) == 1

    r = results[0]
    assert r["player_name"] == "McDavid"
    assert r["market"] == "player_goals"
    assert r["line"] == 0.5
    # Best over = highest American odds = -115 (DraftKings)
    assert r["best_over_odds"] == -115
    assert r["best_over_book"] == "DraftKings"
    # Best under = highest American odds = -105 (BetMGM)
    assert r["best_under_odds"] == -105
    assert r["best_under_book"] == "BetMGM"
    # book_spread must be non-negative
    assert r["book_spread"] >= 0.0


def test_compare_props_multiple_players_sorted_by_spread():
    """compare_props groups by player+market and sorts by book_spread ascending."""
    # Player A: tight market (low spread) — -110/-110
    # Player B: wide market (high spread) — -200/-200
    props = [
        _make_prop("Player A", "player_shots_on_goal", 3.5, over_odds=-110, under_odds=-110, sportsbook="FD", sportsbook_key="fanduel"),
        _make_prop("Player B", "player_shots_on_goal", 3.5, over_odds=-200, under_odds=-200, sportsbook="FD", sportsbook_key="fanduel"),
    ]
    results = compare_props(props)
    assert len(results) == 2
    # Tighter market first
    assert results[0]["player_name"] == "Player A"
    assert results[1]["player_name"] == "Player B"
    # Spread of Player B > Player A
    assert results[1]["book_spread"] > results[0]["book_spread"]


def test_compare_props_empty_returns_empty():
    """compare_props with empty input returns empty list."""
    assert compare_props([]) == []


# ---------------------------------------------------------------------------
# Test 3 — find_prop_edges: identifies outlier lines
# ---------------------------------------------------------------------------


def test_find_prop_edges_detects_outlier_line():
    """find_prop_edges flags a book with a line 0.5+ away from consensus."""
    # Consensus is 0.5 across 3 books; one book offers 1.5
    props = [
        _make_prop("Pastrnak", "player_goals", line=0.5, sportsbook="FD", sportsbook_key="fanduel"),
        _make_prop("Pastrnak", "player_goals", line=0.5, sportsbook="DK", sportsbook_key="draftkings"),
        _make_prop("Pastrnak", "player_goals", line=1.5, sportsbook="BetMGM", sportsbook_key="betmgm"),
    ]
    edges = find_prop_edges(props)
    assert len(edges) >= 1

    # BetMGM's higher line means the under is more generous → under_value
    betmgm_edge = next((e for e in edges if e["sportsbook"] == "BetMGM"), None)
    assert betmgm_edge is not None
    assert betmgm_edge["direction"] == "under_value"
    assert betmgm_edge["deviation"] == pytest.approx(1.0, abs=0.01)
    assert betmgm_edge["player_name"] == "Pastrnak"


def test_find_prop_edges_over_value_direction():
    """A book with a lower-than-consensus line is flagged as over_value."""
    props = [
        _make_prop("Draisaitl", "player_shots_on_goal", line=4.5, sportsbook="FD", sportsbook_key="fanduel"),
        _make_prop("Draisaitl", "player_shots_on_goal", line=4.5, sportsbook="DK", sportsbook_key="draftkings"),
        _make_prop("Draisaitl", "player_shots_on_goal", line=3.5, sportsbook="BetMGM", sportsbook_key="betmgm"),
    ]
    edges = find_prop_edges(props)
    betmgm_edge = next((e for e in edges if e["sportsbook"] == "BetMGM"), None)
    assert betmgm_edge is not None
    assert betmgm_edge["direction"] == "over_value"


def test_find_prop_edges_no_outliers_returns_empty():
    """find_prop_edges returns empty when all lines agree."""
    props = [
        _make_prop("Matthews", "player_goals", line=0.5, sportsbook="FD", sportsbook_key="fanduel"),
        _make_prop("Matthews", "player_goals", line=0.5, sportsbook="DK", sportsbook_key="draftkings"),
    ]
    edges = find_prop_edges(props)
    assert edges == []


def test_find_prop_edges_empty_returns_empty():
    """find_prop_edges with empty input returns empty list."""
    assert find_prop_edges([]) == []


# ---------------------------------------------------------------------------
# Test 4 — build_demo_props
# ---------------------------------------------------------------------------


def test_build_demo_props_returns_prop_lines():
    """build_demo_props returns non-empty list of PropLine objects."""
    props = build_demo_props("TOR", "MTL")
    assert len(props) > 0
    for p in props:
        assert isinstance(p, PropLine)
        assert p.player_name
        assert p.market
        assert p.line > 0
        assert isinstance(p.over_odds, int)
        assert isinstance(p.under_odds, int)


def test_build_demo_props_different_games_differ():
    """Demo props vary by game matchup (seeded per game)."""
    props_a = build_demo_props("TOR", "MTL")
    props_b = build_demo_props("EDM", "VAN")
    # Not necessarily different players, but markets and odds should vary
    assert props_a != props_b


def test_build_demo_props_deterministic():
    """build_demo_props is deterministic for the same matchup."""
    p1 = build_demo_props("BOS", "BUF")
    p2 = build_demo_props("BOS", "BUF")
    assert len(p1) == len(p2)
    for a, b in zip(p1, p2):
        assert a.player_name == b.player_name
        assert a.market == b.market
        assert a.line == b.line
        assert a.over_odds == b.over_odds
        assert a.under_odds == b.under_odds


# ---------------------------------------------------------------------------
# Test 5 — _parse_props_response
# ---------------------------------------------------------------------------


def test_parse_props_response_parses_correctly():
    """_parse_props_response extracts PropLine objects from raw API dict."""
    raw = {
        "bookmakers": [
            {
                "key": "fanduel",
                "title": "FanDuel",
                "markets": [
                    {
                        "key": "player_goals",
                        "outcomes": [
                            {"name": "Over", "description": "Connor McDavid", "price": -120, "point": 0.5},
                            {"name": "Under", "description": "Connor McDavid", "price": -110, "point": 0.5},
                        ],
                    }
                ],
            }
        ]
    }
    props = _parse_props_response(raw)
    assert len(props) == 1
    p = props[0]
    assert p.player_name == "Connor McDavid"
    assert p.market == "player_goals"
    assert p.line == 0.5
    assert p.over_odds == -120
    assert p.under_odds == -110
    assert p.sportsbook == "FanDuel"
    assert p.sportsbook_key == "fanduel"


def test_parse_props_response_skips_incomplete_sides():
    """Outcomes missing over or under are skipped."""
    raw = {
        "bookmakers": [
            {
                "key": "fanduel",
                "title": "FanDuel",
                "markets": [
                    {
                        "key": "player_goals",
                        "outcomes": [
                            # Only Over, no Under
                            {"name": "Over", "description": "Sidney Crosby", "price": -115, "point": 0.5},
                        ],
                    }
                ],
            }
        ]
    }
    props = _parse_props_response(raw)
    assert props == []


def test_parse_props_response_multiple_books():
    """Props from multiple books are all captured."""
    raw = {
        "bookmakers": [
            {
                "key": "fanduel",
                "title": "FanDuel",
                "markets": [
                    {
                        "key": "player_shots_on_goal",
                        "outcomes": [
                            {"name": "Over", "description": "Leon Draisaitl", "price": -115, "point": 3.5},
                            {"name": "Under", "description": "Leon Draisaitl", "price": -115, "point": 3.5},
                        ],
                    }
                ],
            },
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {
                        "key": "player_shots_on_goal",
                        "outcomes": [
                            {"name": "Over", "description": "Leon Draisaitl", "price": -110, "point": 3.5},
                            {"name": "Under", "description": "Leon Draisaitl", "price": -120, "point": 3.5},
                        ],
                    }
                ],
            },
        ]
    }
    props = _parse_props_response(raw)
    assert len(props) == 2
    books = {p.sportsbook_key for p in props}
    assert books == {"fanduel", "draftkings"}


# ---------------------------------------------------------------------------
# Test 6 — fetch_player_props: error handling
# ---------------------------------------------------------------------------


def test_fetch_player_props_raises_on_empty_api_key():
    """ValueError raised when api_key is empty."""
    with pytest.raises(ValueError, match="[Aa][Pp][Ii]"):
        fetch_player_props("", "event123")


def test_fetch_player_props_raises_on_empty_event_id():
    """ValueError raised when event_id is empty."""
    with pytest.raises(ValueError, match="event_id"):
        fetch_player_props("valid_key", "")


def test_fetch_player_props_returns_empty_on_network_error():
    """fetch_player_props returns [] gracefully on network failure."""
    from urllib.error import URLError

    with patch("app.data.player_props._fetch_with_retry", side_effect=URLError("timeout")):
        result = fetch_player_props("valid_key", "event123")
    assert result == []


def test_fetch_player_props_returns_empty_on_bad_json():
    """fetch_player_props returns [] gracefully when response is not valid JSON."""
    with patch("app.data.player_props._fetch_with_retry", return_value=b"not json"):
        result = fetch_player_props("valid_key", "event123")
    assert result == []


def test_fetch_player_props_full_round_trip():
    """fetch_player_props parses a full API response correctly via mock."""
    api_response = {
        "id": "event123",
        "bookmakers": [
            {
                "key": "betmgm",
                "title": "BetMGM",
                "markets": [
                    {
                        "key": "player_saves",
                        "outcomes": [
                            {"name": "Over", "description": "Joseph Woll", "price": -115, "point": 25.5},
                            {"name": "Under", "description": "Joseph Woll", "price": -115, "point": 25.5},
                        ],
                    }
                ],
            }
        ],
    }
    raw_bytes = json.dumps(api_response).encode("utf-8")

    with patch("app.data.player_props._fetch_with_retry", return_value=raw_bytes):
        props = fetch_player_props("valid_key", "event123")

    assert len(props) == 1
    assert props[0].player_name == "Joseph Woll"
    assert props[0].market == "player_saves"
    assert props[0].line == 25.5
    assert props[0].sportsbook == "BetMGM"


# ---------------------------------------------------------------------------
# Test 7 — _american_to_implied helper
# ---------------------------------------------------------------------------


def test_american_to_implied_positive_odds():
    """Positive American odds convert correctly (+200 = 33.3%)."""
    assert _american_to_implied(200) == pytest.approx(1 / 3, abs=0.001)


def test_american_to_implied_negative_odds():
    """-110 odds convert to ~52.4% implied probability."""
    assert _american_to_implied(-110) == pytest.approx(110 / 210, abs=0.001)


def test_american_to_implied_even_money():
    """-100/+100 both convert to 50%."""
    assert _american_to_implied(-100) == pytest.approx(0.5, abs=0.001)
    assert _american_to_implied(100) == pytest.approx(0.5, abs=0.001)


# ---------------------------------------------------------------------------
# Test 8 — compare_props: market_label populated
# ---------------------------------------------------------------------------


def test_compare_props_market_label():
    """compare_props includes a human-readable market_label."""
    props = [
        _make_prop("Matthews", "player_shots_on_goal", line=3.5, sportsbook="FD", sportsbook_key="fanduel"),
    ]
    results = compare_props(props)
    assert results[0]["market_label"] == "Shots"


def test_compare_props_goals_label():
    props = [_make_prop("Matthews", "player_goals", line=0.5, sportsbook="FD", sportsbook_key="fanduel")]
    results = compare_props(props)
    assert results[0]["market_label"] == "Goals"
