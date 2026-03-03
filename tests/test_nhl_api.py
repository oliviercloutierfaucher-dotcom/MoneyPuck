"""Phase 6: Tests for the NHL API client module (app.nhl_api)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from app import nhl_api


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_urlopen_response(data: dict) -> MagicMock:
    """Build a mock that behaves like the object returned by urlopen().

    The mock supports both `.read()` and context-manager usage
    (``with urlopen(...) as resp``).
    """
    raw = json.dumps(data).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = raw
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Realistic NHL API response fragments
# ---------------------------------------------------------------------------

SCHEDULE_RESPONSE = {
    "gameWeek": [
        {
            "date": "2025-03-10",
            "games": [
                {
                    "id": 2024020100,
                    "startTimeUTC": "2025-03-10T23:00:00Z",
                    "gameState": "FUT",
                    "homeTeam": {"abbrev": "MTL", "score": 0},
                    "awayTeam": {"abbrev": "TOR", "score": 0},
                },
                {
                    "id": 2024020101,
                    "startTimeUTC": "2025-03-10T23:30:00Z",
                    "gameState": "FUT",
                    "homeTeam": {"abbrev": "BOS", "score": 0},
                    "awayTeam": {"abbrev": "NYR", "score": 0},
                },
            ],
        }
    ]
}

EMPTY_SCHEDULE_RESPONSE = {
    "gameWeek": [
        {
            "date": "2025-07-15",
            "games": [],
        }
    ]
}

STANDINGS_RESPONSE = {
    "standings": [
        {
            "teamAbbrev": {"default": "MTL"},
            "gamesPlayed": 65,
            "wins": 35,
            "losses": 22,
            "otLosses": 8,
            "points": 78,
            "goalFor": 210,
            "goalAgainst": 195,
        },
        {
            "teamAbbrev": {"default": "TOR"},
            "gamesPlayed": 65,
            "wins": 40,
            "losses": 18,
            "otLosses": 7,
            "points": 87,
            "goalFor": 230,
            "goalAgainst": 185,
        },
    ]
}

GOALIE_LEADERS_SAVE_PCT = {
    "categories": [
        {
            "categoryName": "savePctg",
            "leaders": [
                {
                    "player": {
                        "firstName": {"default": "Samuel"},
                        "lastName": {"default": "Montembeault"},
                    },
                    "teamAbbrev": "MTL",
                    "gamesPlayed": 45,
                    "value": 0.912,
                    "goalsAgainstAverage": 2.85,
                    "wins": 22,
                },
                {
                    "player": {
                        "firstName": {"default": "Joseph"},
                        "lastName": {"default": "Woll"},
                    },
                    "teamAbbrev": "TOR",
                    "gamesPlayed": 40,
                    "value": 0.918,
                    "goalsAgainstAverage": 2.50,
                    "wins": 25,
                },
            ],
        }
    ]
}

GOALIE_LEADERS_WINS = {
    "categories": [
        {
            "categoryName": "wins",
            "leaders": [
                {
                    "player": {
                        "firstName": {"default": "Joseph"},
                        "lastName": {"default": "Woll"},
                    },
                    "teamAbbrev": "TOR",
                    "gamesPlayed": 40,
                    "value": 25,
                },
                {
                    "player": {
                        "firstName": {"default": "Samuel"},
                        "lastName": {"default": "Montembeault"},
                    },
                    "teamAbbrev": "MTL",
                    "gamesPlayed": 45,
                    "value": 22,
                },
            ],
        }
    ]
}


# ---------------------------------------------------------------------------
# Tests: _fetch_json
# ---------------------------------------------------------------------------


@patch("app.nhl_api.urlopen")
def test_fetch_json_success(mock_urlopen):
    """urlopen returns valid JSON bytes -> _fetch_json parses correctly."""
    payload = {"key": "value", "count": 42}
    mock_urlopen.return_value = _mock_urlopen_response(payload)

    result = nhl_api._fetch_json("https://example.com/api")

    assert result == payload
    mock_urlopen.assert_called_once()


@patch("app.nhl_api.urlopen")
def test_fetch_json_failure(mock_urlopen):
    """urlopen raises URLError -> _fetch_json returns empty dict."""
    mock_urlopen.side_effect = URLError("DNS lookup failed")

    result = nhl_api._fetch_json("https://example.com/api")

    assert result == {}


# ---------------------------------------------------------------------------
# Tests: fetch_schedule
# ---------------------------------------------------------------------------


@patch("app.nhl_api._fetch_json")
def test_fetch_schedule_parses_games(mock_fetch):
    """Realistic schedule structure -> fetch_schedule returns game dicts."""
    mock_fetch.return_value = SCHEDULE_RESPONSE

    games = nhl_api.fetch_schedule(date="2025-03-10")

    assert isinstance(games, list)
    assert len(games) == 2

    g0 = games[0]
    assert g0["home_team"] == "MTL"
    assert g0["away_team"] == "TOR"
    assert g0["game_id"] == 2024020100

    g1 = games[1]
    assert g1["home_team"] == "BOS"
    assert g1["away_team"] == "NYR"


@patch("app.nhl_api._fetch_json")
def test_fetch_schedule_empty(mock_fetch):
    """Empty games list in schedule -> returns empty list."""
    mock_fetch.return_value = EMPTY_SCHEDULE_RESPONSE

    games = nhl_api.fetch_schedule(date="2025-07-15")

    assert games == []


# ---------------------------------------------------------------------------
# Tests: fetch_standings
# ---------------------------------------------------------------------------


@patch("app.nhl_api._fetch_json")
def test_fetch_standings_parses(mock_fetch):
    """Standings response -> fetch_standings returns team dicts."""
    mock_fetch.return_value = STANDINGS_RESPONSE

    standings = nhl_api.fetch_standings()

    assert isinstance(standings, list)
    assert len(standings) == 2

    mtl = standings[0]
    assert mtl["team_code"] == "MTL"
    assert mtl["points"] == 78
    assert mtl["wins"] == 35
    assert mtl["goal_diff"] == 15  # 210 - 195

    tor = standings[1]
    assert tor["team_code"] == "TOR"
    assert tor["points"] == 87
    assert tor["goal_diff"] == 45  # 230 - 185


# ---------------------------------------------------------------------------
# Tests: fetch_goalie_stats
# ---------------------------------------------------------------------------


@patch("app.nhl_api._fetch_json")
def test_fetch_goalie_stats_parses(mock_fetch):
    """Goalie stats response -> parsed into list of goalie dicts."""
    # Two calls: first for savePctg, second for wins
    mock_fetch.side_effect = [GOALIE_LEADERS_SAVE_PCT, GOALIE_LEADERS_WINS]

    goalies = nhl_api.fetch_goalie_stats()

    assert isinstance(goalies, list)
    assert len(goalies) == 2

    names = {g["player_name"] for g in goalies}
    assert "Samuel Montembeault" in names
    assert "Joseph Woll" in names

    monty = next(g for g in goalies if g["player_name"] == "Samuel Montembeault")
    assert monty["team_code"] == "MTL"
    assert monty["games_played"] == 45
    assert abs(monty["save_pct"] - 0.912) < 1e-6
    assert monty["wins"] == 22


# ---------------------------------------------------------------------------
# Tests: infer_likely_starter
# ---------------------------------------------------------------------------


def test_infer_likely_starter_picks_most_games():
    """Given two goalies on the same team, picks the one with more GP."""
    goalie_stats = [
        {
            "player_name": "Samuel Montembeault",
            "team_code": "MTL",
            "games_played": 45,
            "save_pct": 0.912,
            "gaa": 2.85,
            "wins": 22,
        },
        {
            "player_name": "Cayden Primeau",
            "team_code": "MTL",
            "games_played": 18,
            "save_pct": 0.898,
            "gaa": 3.20,
            "wins": 8,
        },
    ]

    starter = nhl_api.infer_likely_starter("MTL", goalie_stats)

    assert starter is not None
    assert starter["player_name"] == "Samuel Montembeault"
    assert starter["games_played"] == 45


def test_infer_likely_starter_no_match():
    """Team code not found in goalie stats -> returns None."""
    goalie_stats = [
        {
            "player_name": "Joseph Woll",
            "team_code": "TOR",
            "games_played": 40,
            "save_pct": 0.918,
            "gaa": 2.50,
            "wins": 25,
        },
    ]

    result = nhl_api.infer_likely_starter("SEA", goalie_stats)

    assert result is None
