"""Tests for bet settlement (Step 4), circuit breaker (Step 5), and overrides (Step 6)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.models import TeamMetrics, ValueCandidate
from app.data.database import TrackerDatabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_db() -> TrackerDatabase:
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test_tracker.db"
    return TrackerDatabase(db_path=db_path)


def _make_recommendation(
    side: str = "MTL",
    american_odds: int = 120,
    commence: str = "2026-03-10T19:00:00Z",
    home: str = "MTL",
    away: str = "TOR",
    stake: float = 25.0,
    model_prob: float = 0.55,
) -> dict:
    dec = 1 + american_odds / 100 if american_odds > 0 else 1 + 100 / abs(american_odds)
    candidate = ValueCandidate(
        commence_time_utc=commence,
        home_team=home,
        away_team=away,
        side=side,
        sportsbook="DraftKings",
        american_odds=american_odds,
        decimal_odds=dec,
        implied_probability=0.455,
        model_probability=model_prob,
        edge_probability_points=9.5,
        expected_value_per_dollar=0.18,
        kelly_fraction=0.09,
        confidence=0.85,
    )
    return {
        "candidate": candidate,
        "recommended_stake": stake,
        "stake_fraction": round(stake / 1000.0, 4),
    }


# ---------------------------------------------------------------------------
# Step 4: Settlement tests
# ---------------------------------------------------------------------------

def _patch_db(db):
    """Patch TrackerDatabase so that constructing it returns the given db."""
    mock_cls = lambda *a, **kw: db  # noqa: E731
    return patch("app.data.database.TrackerDatabase", side_effect=mock_cls)


def test_settle_outstanding_no_unsettled():
    """settle_outstanding with empty DB returns zero settled."""
    from app.core.service import settle_outstanding

    db = _tmp_db()
    with _patch_db(db):
        result = settle_outstanding()
    assert result["settled"] == 0
    assert result["total_pnl"] == 0.0
    db.close()


def test_settle_outstanding_win():
    """Settlement correctly identifies a win and computes P&L."""
    from app.core.service import settle_outstanding

    db = _tmp_db()
    rec = _make_recommendation(side="MTL", american_odds=120, stake=50.0)
    db.save_prediction(rec)

    # Mock: MTL won 4-2
    mock_scores = [{
        "game_id": 1,
        "home_team": "MTL",
        "away_team": "TOR",
        "home_score": 4,
        "away_score": 2,
        "game_state": "FINAL",
    }]

    with _patch_db(db), \
         patch("app.data.nhl_api.fetch_scores_for_date", return_value=mock_scores):
        result = settle_outstanding()

    assert result["settled"] == 1
    assert result["total_pnl"] > 0  # Win at +120
    db.close()


def test_settle_outstanding_loss():
    """Settlement correctly identifies a loss."""
    from app.core.service import settle_outstanding

    db = _tmp_db()
    rec = _make_recommendation(side="MTL", stake=50.0)
    db.save_prediction(rec)

    mock_scores = [{
        "game_id": 1,
        "home_team": "MTL",
        "away_team": "TOR",
        "home_score": 1,
        "away_score": 3,
        "game_state": "FINAL",
    }]

    with _patch_db(db), \
         patch("app.data.nhl_api.fetch_scores_for_date", return_value=mock_scores):
        result = settle_outstanding()

    assert result["settled"] == 1
    assert result["total_pnl"] == -50.0
    db.close()


def test_settle_outstanding_no_matching_score():
    """Predictions for games without scores remain unsettled."""
    from app.core.service import settle_outstanding

    db = _tmp_db()
    rec = _make_recommendation(side="MTL", stake=50.0)
    db.save_prediction(rec)

    # Different game — no match
    mock_scores = [{
        "game_id": 1,
        "home_team": "BOS",
        "away_team": "NYR",
        "home_score": 3,
        "away_score": 2,
        "game_state": "FINAL",
    }]

    with _patch_db(db), \
         patch("app.data.nhl_api.fetch_scores_for_date", return_value=mock_scores):
        result = settle_outstanding()

    assert result["settled"] == 0
    db.close()


# ---------------------------------------------------------------------------
# Step 5: Circuit breaker tests
# ---------------------------------------------------------------------------

def test_circuit_breaker_not_enough_data():
    """Circuit breaker does not trip with insufficient data."""
    from app.core.service import check_circuit_breaker

    db = _tmp_db()
    with _patch_db(db):
        tripped, msg = check_circuit_breaker()
    assert tripped is False
    assert "Not enough" in msg
    db.close()


def _make_unique_recommendation(i: int, model_prob: float = 0.6, stake: float = 10.0) -> dict:
    """Create a recommendation with unique commence_time to avoid UNIQUE constraint."""
    # Use unique hour+minute to avoid collisions
    hour = 18 + (i // 60)
    minute = i % 60
    return _make_recommendation(
        side="MTL",
        stake=stake,
        model_prob=model_prob,
        commence=f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}T{hour:02d}:{minute:02d}:00Z",
    )


def test_circuit_breaker_healthy_model():
    """Circuit breaker stays off with good predictions."""
    from app.core.service import check_circuit_breaker, CIRCUIT_BREAKER_WINDOW

    db = _tmp_db()
    # Create 50 well-calibrated predictions (60% model prob, 60% win rate)
    for i in range(CIRCUIT_BREAKER_WINDOW):
        rec = _make_unique_recommendation(i, model_prob=0.6)
        pred_id = db.save_prediction(rec)
        outcome = "win" if i < 30 else "loss"  # 60% win rate
        db.settle(pred_id, outcome=outcome, closing_odds=None,
                  profit_loss=10.0 if outcome == "win" else -10.0)

    with _patch_db(db):
        tripped, msg = check_circuit_breaker()
    assert tripped is False
    assert "healthy" in msg.lower() or "Brier" in msg
    db.close()


def test_circuit_breaker_trips_on_bad_model():
    """Circuit breaker trips when predictions are worse than coin flip."""
    from app.core.service import check_circuit_breaker, CIRCUIT_BREAKER_WINDOW

    db = _tmp_db()
    # Create 50 terrible predictions (90% model prob but only 20% win rate)
    for i in range(CIRCUIT_BREAKER_WINDOW):
        rec = _make_unique_recommendation(i, model_prob=0.9)
        pred_id = db.save_prediction(rec)
        outcome = "win" if i < 10 else "loss"  # 20% win rate with 90% confidence = terrible
        db.settle(pred_id, outcome=outcome, closing_odds=None,
                  profit_loss=10.0 if outcome == "win" else -10.0)

    with _patch_db(db):
        tripped, msg = check_circuit_breaker()
    assert tripped is True
    assert "CIRCUIT BREAKER" in msg
    db.close()


# ---------------------------------------------------------------------------
# Step 6: Override tests
# ---------------------------------------------------------------------------

def test_load_overrides_missing_file():
    """Missing overrides file returns empty dict."""
    from app.core.service import load_overrides

    with patch("app.core.service.OVERRIDES_PATH", "/nonexistent/overrides.json"):
        result = load_overrides()
    assert result == {}


def test_load_overrides_with_active_entries():
    """Active overrides (not expired) are loaded correctly."""
    from app.core.service import load_overrides

    overrides_data = {
        "TOR": {
            "strength_penalty": -0.3,
            "reason": "Matthews out",
            "expires": "2099-12-31",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(overrides_data, f)
        f.flush()
        with patch("app.core.service.OVERRIDES_PATH", f.name):
            result = load_overrides()

    assert "TOR" in result
    assert result["TOR"]["strength_penalty"] == -0.3


def test_load_overrides_expired_entries():
    """Expired overrides are filtered out."""
    from app.core.service import load_overrides

    overrides_data = {
        "TOR": {
            "strength_penalty": -0.3,
            "reason": "Matthews out",
            "expires": "2020-01-01",
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(overrides_data, f)
        f.flush()
        with patch("app.core.service.OVERRIDES_PATH", f.name):
            result = load_overrides()

    assert result == {}


def test_apply_overrides_adjusts_strength():
    """apply_overrides reduces composite/home/away strength by penalty."""
    from app.core.service import apply_overrides

    team_strength = {
        "TOR": TeamMetrics(
            home_strength=0.5, away_strength=0.3, composite=0.4, games_played=40,
        ),
        "MTL": TeamMetrics(
            home_strength=0.2, away_strength=0.1, composite=0.15, games_played=40,
        ),
    }
    overrides = {
        "TOR": {"strength_penalty": -0.3, "reason": "Matthews out"},
    }

    result = apply_overrides(team_strength, overrides)

    # TOR should be penalized
    assert abs(result["TOR"].composite - 0.1) < 1e-6
    assert abs(result["TOR"].home_strength - 0.2) < 1e-6
    assert abs(result["TOR"].away_strength - 0.0) < 1e-6
    # MTL should be unchanged
    assert result["MTL"].composite == 0.15


def test_get_excluded_teams():
    """get_excluded_teams returns teams with exclude=True."""
    from app.core.service import get_excluded_teams

    overrides = {
        "TOR": {"exclude": True, "reason": "uncertain lineup"},
        "MTL": {"strength_penalty": -0.1, "reason": "minor injury"},
    }
    excluded = get_excluded_teams(overrides)
    assert excluded == {"TOR"}


# ---------------------------------------------------------------------------
# Step 4: NHL API score fetching tests
# ---------------------------------------------------------------------------

@patch("app.data.nhl_api._fetch_json")
def test_fetch_game_score(mock_fetch):
    """fetch_game_score returns parsed score dict for a finished game."""
    from app.data.nhl_api import fetch_game_score

    mock_fetch.return_value = {
        "id": 2024020100,
        "gameState": "FINAL",
        "homeTeam": {"abbrev": "MTL", "score": 4},
        "awayTeam": {"abbrev": "TOR", "score": 2},
    }
    result = fetch_game_score(2024020100)
    assert result is not None
    assert result["home_team"] == "MTL"
    assert result["home_score"] == 4
    assert result["away_score"] == 2
    assert result["game_state"] == "FINAL"


@patch("app.data.nhl_api._fetch_json")
def test_fetch_game_score_api_failure(mock_fetch):
    """fetch_game_score returns None when API returns empty."""
    from app.data.nhl_api import fetch_game_score

    mock_fetch.return_value = {}
    result = fetch_game_score(9999999)
    assert result is None


@patch("app.data.nhl_api.fetch_game_score")
@patch("app.data.nhl_api.fetch_schedule")
def test_fetch_scores_for_date(mock_schedule, mock_score):
    """fetch_scores_for_date returns only completed games."""
    from app.data.nhl_api import fetch_scores_for_date

    mock_schedule.return_value = [
        {"game_id": 1, "game_state": "FINAL", "home_team": "MTL", "away_team": "TOR"},
        {"game_id": 2, "game_state": "FUT", "home_team": "BOS", "away_team": "NYR"},
    ]
    mock_score.return_value = {
        "game_id": 1, "home_team": "MTL", "away_team": "TOR",
        "home_score": 3, "away_score": 1, "game_state": "FINAL",
    }

    results = fetch_scores_for_date("2026-03-10")
    assert len(results) == 1
    assert results[0]["home_team"] == "MTL"
    # FUT game should be skipped
    mock_score.assert_called_once_with(1)
