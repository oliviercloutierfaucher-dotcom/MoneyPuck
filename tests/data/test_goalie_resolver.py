"""Tests for 3-tier goalie resolution logic (app.data.goalie_resolver)."""
from __future__ import annotations

from app.data.goalie_resolver import resolve_starter, resolve_all_starters, _match_goalie_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GOALIE_STATS = [
    {
        "player_name": "Jeremy Swayman",
        "team_code": "BOS",
        "games_played": 40,
        "save_pct": 0.905,
        "gaa": 2.85,
        "wins": 23,
    },
    {
        "player_name": "Joonas Korpisalo",
        "team_code": "BOS",
        "games_played": 24,
        "save_pct": 0.893,
        "gaa": 3.20,
        "wins": 10,
    },
    {
        "player_name": "Igor Shesterkin",
        "team_code": "NYR",
        "games_played": 55,
        "save_pct": 0.921,
        "gaa": 2.30,
        "wins": 33,
    },
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

DF_STARTERS = [
    {
        "home_goalie": "Jeremy Swayman",
        "away_goalie": "Igor Shesterkin",
        "home_status": "confirmed",
        "away_status": "likely",
        "home_save_pct": 0.905,
        "away_save_pct": 0.921,
        "home_team": "BOS",
        "away_team": "NYR",
    },
]


# ---------------------------------------------------------------------------
# Tests: resolve_starter - Tier 1 (confirmed)
# ---------------------------------------------------------------------------


def test_resolve_confirmed():
    """Confirmed DailyFaceoff entry returns (goalie_dict, 'confirmed')."""
    goalie, source = resolve_starter("BOS", DF_STARTERS, GOALIE_STATS)

    assert source == "confirmed"
    assert goalie is not None
    assert goalie["player_name"] == "Jeremy Swayman"
    assert abs(goalie["save_pct"] - 0.905) < 1e-6


# ---------------------------------------------------------------------------
# Tests: resolve_starter - Tier 1 (likely)
# ---------------------------------------------------------------------------


def test_resolve_likely():
    """Likely DailyFaceoff entry returns (goalie_dict, 'likely')."""
    goalie, source = resolve_starter("NYR", DF_STARTERS, GOALIE_STATS)

    assert source == "likely"
    assert goalie is not None
    assert goalie["player_name"] == "Igor Shesterkin"


# ---------------------------------------------------------------------------
# Tests: resolve_starter - Tier 3 (gp_leader fallback)
# ---------------------------------------------------------------------------


def test_resolve_fallback_gp_leader_no_df_data():
    """No DailyFaceoff data for team -> falls back to GP-leader."""
    goalie, source = resolve_starter("MTL", DF_STARTERS, GOALIE_STATS)

    assert source == "gp_leader"
    assert goalie is not None
    assert goalie["player_name"] == "Samuel Montembeault"


def test_resolve_fallback_on_unconfirmed():
    """Unconfirmed DailyFaceoff entry -> falls back to GP-leader."""
    df_unconfirmed = [
        {
            "home_goalie": "Cayden Primeau",
            "away_goalie": "Igor Shesterkin",
            "home_status": "unconfirmed",
            "away_status": "likely",
            "home_save_pct": 0.898,
            "away_save_pct": 0.921,
            "home_team": "MTL",
            "away_team": "NYR",
        },
    ]

    goalie, source = resolve_starter("MTL", df_unconfirmed, GOALIE_STATS)

    assert source == "gp_leader"
    assert goalie is not None
    assert goalie["player_name"] == "Samuel Montembeault"


# ---------------------------------------------------------------------------
# Tests: resolve_starter - no data at all
# ---------------------------------------------------------------------------


def test_resolve_none_when_no_data():
    """No goalie data at all -> returns (None, 'none')."""
    goalie, source = resolve_starter("SEA", [], [])

    assert goalie is None
    assert source == "none"


def test_resolve_none_no_goalie_stats_for_team():
    """DailyFaceoff has no entry and goalie_stats has no team match."""
    goalie, source = resolve_starter("SEA", DF_STARTERS, GOALIE_STATS)

    assert goalie is None
    assert source == "none"


# ---------------------------------------------------------------------------
# Tests: _match_goalie_name
# ---------------------------------------------------------------------------


def test_match_goalie_name_full_name():
    """Full name match from DailyFaceoff to goalie_stats."""
    result = _match_goalie_name("Jeremy Swayman", GOALIE_STATS, "BOS")

    assert result is not None
    assert result["player_name"] == "Jeremy Swayman"


def test_match_goalie_name_last_name_only():
    """Last name + team_code match when first name differs."""
    # Simulate DailyFaceoff providing a slightly different first name
    result = _match_goalie_name("J. Swayman", GOALIE_STATS, "BOS")

    assert result is not None
    assert result["player_name"] == "Jeremy Swayman"


def test_match_goalie_name_no_match():
    """No matching goalie on team -> returns None."""
    result = _match_goalie_name("Connor Hellebuyck", GOALIE_STATS, "WPG")

    assert result is None


def test_match_goalie_name_wrong_team():
    """Goalie name exists but on wrong team -> returns None."""
    result = _match_goalie_name("Jeremy Swayman", GOALIE_STATS, "NYR")

    assert result is None


# ---------------------------------------------------------------------------
# Tests: resolve_all_starters
# ---------------------------------------------------------------------------


def test_resolve_all_starters():
    """resolve_all_starters returns dict keyed by team_code."""
    teams = ["BOS", "NYR", "MTL"]
    result = resolve_all_starters(teams, DF_STARTERS, GOALIE_STATS)

    assert isinstance(result, dict)
    assert len(result) == 3
    assert "BOS" in result
    assert "NYR" in result
    assert "MTL" in result

    goalie_bos, source_bos = result["BOS"]
    assert source_bos == "confirmed"
    assert goalie_bos["player_name"] == "Jeremy Swayman"

    goalie_nyr, source_nyr = result["NYR"]
    assert source_nyr == "likely"

    goalie_mtl, source_mtl = result["MTL"]
    assert source_mtl == "gp_leader"
