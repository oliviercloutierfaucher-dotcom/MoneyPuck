"""Tests for ESPN injury fetcher and NHL club-stats player stats fetcher."""

from __future__ import annotations

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _make_espn_response(
    *,
    teams: list[dict] | None = None,
) -> dict:
    """Build a realistic ESPN injuries API JSON response."""
    if teams is None:
        teams = [
            {
                "team": {"abbreviation": "TOR"},
                "injuries": [
                    {
                        "athlete": {
                            "displayName": "Auston Matthews",
                            "position": {"abbreviation": "C"},
                        },
                        "status": "Day-To-Day",
                        "details": {
                            "type": "Upper Body",
                            "returnDate": "2026-03-15",
                        },
                    },
                    {
                        "athlete": {
                            "displayName": "Morgan Rielly",
                            "position": {"abbreviation": "D"},
                        },
                        "status": "Out",
                        "details": {
                            "type": "Knee",
                            "returnDate": "2026-04-01",
                        },
                    },
                ],
            },
            {
                "team": {"abbreviation": "EDM"},
                "injuries": [
                    {
                        "athlete": {
                            "displayName": "Evander Kane",
                            "position": {"abbreviation": "LW"},
                        },
                        "status": "Injured Reserve",
                        "details": {
                            "type": "Wrist",
                            "returnDate": "",
                        },
                    },
                ],
            },
        ]
    return {"injuries": teams}


def _make_nhl_club_stats_response() -> dict:
    """Build a realistic NHL club-stats API JSON response."""
    return {
        "skaters": [
            {
                "playerId": 8478483,
                "firstName": {"default": "Auston"},
                "lastName": {"default": "Matthews"},
                "positionCode": "C",
                "avgTimeOnIcePerGame": 1260.5,
                "gamesPlayed": 60,
                "points": 80,
            },
            {
                "playerId": 8477934,
                "firstName": {"default": "Mitch"},
                "lastName": {"default": "Marner"},
                "positionCode": "R",
                "avgTimeOnIcePerGame": 1200.0,
                "gamesPlayed": 70,
                "points": 75,
            },
            {
                "playerId": 8476853,
                "firstName": {"default": "Morgan"},
                "lastName": {"default": "Rielly"},
                "positionCode": "D",
                "avgTimeOnIcePerGame": 1400.0,
                "gamesPlayed": 55,
                "points": 40,
            },
        ],
        "goalies": [
            {
                "playerId": 8479361,
                "firstName": {"default": "Joseph"},
                "lastName": {"default": "Woll"},
                "gamesPlayed": 45,
                "gamesStarted": 42,
            },
        ],
    }


# ---------------------------------------------------------------------------
# fetch_injuries tests
# ---------------------------------------------------------------------------

class TestFetchInjuries:
    """Tests for ESPN injury fetching and parsing."""

    @patch("app.data.injuries._fetch_json")
    def test_parses_espn_response(self, mock_fetch):
        from app.data.injuries import fetch_injuries

        mock_fetch.return_value = _make_espn_response()
        result = fetch_injuries()

        assert len(result) == 3
        tor_injuries = [i for i in result if i["team"] == "TOR"]
        assert len(tor_injuries) == 2

        matthews = next(i for i in result if i["player_name"] == "Auston Matthews")
        assert matthews["position"] == "C"
        assert matthews["status"] == "Day-To-Day"
        assert matthews["injury_type"] == "Upper Body"
        assert matthews["return_date"] == "2026-03-15"

    @patch("app.data.injuries._fetch_json")
    def test_position_normalization_lw(self, mock_fetch):
        """LW should be normalized to L."""
        from app.data.injuries import fetch_injuries

        mock_fetch.return_value = _make_espn_response()
        result = fetch_injuries()
        kane = next(i for i in result if i["player_name"] == "Evander Kane")
        assert kane["position"] == "L"

    @patch("app.data.injuries._fetch_json")
    def test_position_normalization_rw(self, mock_fetch):
        """RW should be normalized to R."""
        from app.data.injuries import fetch_injuries

        espn = _make_espn_response(teams=[
            {
                "team": {"abbreviation": "BOS"},
                "injuries": [
                    {
                        "athlete": {
                            "displayName": "David Pastrnak",
                            "position": {"abbreviation": "RW"},
                        },
                        "status": "Out",
                        "details": {"type": "Ankle", "returnDate": ""},
                    },
                ],
            },
        ])
        mock_fetch.return_value = espn
        result = fetch_injuries()
        assert result[0]["position"] == "R"

    @patch("app.data.injuries._fetch_json")
    def test_team_abbreviation_normalization(self, mock_fetch):
        """UTAH should be normalized to UTA."""
        from app.data.injuries import fetch_injuries

        espn = _make_espn_response(teams=[
            {
                "team": {"abbreviation": "UTAH"},
                "injuries": [
                    {
                        "athlete": {
                            "displayName": "Logan Cooley",
                            "position": {"abbreviation": "C"},
                        },
                        "status": "Out",
                        "details": {"type": "Shoulder", "returnDate": ""},
                    },
                ],
            },
        ])
        mock_fetch.return_value = espn
        result = fetch_injuries()
        assert result[0]["team"] == "UTA"

    @patch("app.data.injuries._fetch_json")
    def test_empty_response_returns_empty_list(self, mock_fetch):
        from app.data.injuries import fetch_injuries

        mock_fetch.return_value = {}
        result = fetch_injuries()
        assert result == []

    @patch("app.data.injuries._fetch_json")
    def test_malformed_response_returns_empty_list(self, mock_fetch):
        from app.data.injuries import fetch_injuries

        mock_fetch.return_value = {"injuries": [{"bad": "data"}]}
        result = fetch_injuries()
        assert result == []

    @patch("app.data.injuries._fetch_json")
    def test_api_failure_returns_empty_list(self, mock_fetch):
        """When _fetch_json returns empty dict (failure), we get empty list."""
        from app.data.injuries import fetch_injuries

        mock_fetch.return_value = {}
        result = fetch_injuries()
        assert result == []


# ---------------------------------------------------------------------------
# fetch_team_player_stats tests
# ---------------------------------------------------------------------------

class TestFetchTeamPlayerStats:
    """Tests for NHL club-stats player stats fetching."""

    @patch("app.data.injuries._fetch_json")
    def test_parses_skaters(self, mock_fetch):
        from app.data.injuries import fetch_team_player_stats

        mock_fetch.return_value = _make_nhl_club_stats_response()
        result = fetch_team_player_stats("TOR")

        skaters = [p for p in result if p["position"] != "G"]
        assert len(skaters) == 3

        matthews = next(p for p in result if "Matthews" in p["name"])
        assert matthews["position"] == "C"
        assert matthews["toi_per_game"] == 1260.5
        assert matthews["games_played"] == 60
        assert matthews["points"] == 80

    @patch("app.data.injuries._fetch_json")
    def test_parses_goalies(self, mock_fetch):
        from app.data.injuries import fetch_team_player_stats

        mock_fetch.return_value = _make_nhl_club_stats_response()
        result = fetch_team_player_stats("TOR")

        goalies = [p for p in result if p["position"] == "G"]
        assert len(goalies) == 1
        assert "Woll" in goalies[0]["name"]
        assert goalies[0]["games_played"] == 45
        assert goalies[0]["games_started"] == 42

    @patch("app.data.injuries._fetch_json")
    def test_correct_url_format(self, mock_fetch):
        from app.data.injuries import fetch_team_player_stats

        mock_fetch.return_value = {}
        fetch_team_player_stats("EDM")
        mock_fetch.assert_called_once()
        url = mock_fetch.call_args[0][0]
        assert "club-stats/EDM/now" in url

    @patch("app.data.injuries._fetch_json")
    def test_api_failure_returns_empty_list(self, mock_fetch):
        from app.data.injuries import fetch_team_player_stats

        mock_fetch.return_value = {}
        result = fetch_team_player_stats("TOR")
        assert result == []
