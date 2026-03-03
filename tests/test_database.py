"""Phase 4: Tests for the SQLite persistence layer (TrackerDatabase)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.database import TrackerDatabase
from app.models import ValueCandidate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _tmp_db() -> TrackerDatabase:
    """Return a TrackerDatabase backed by a temporary file."""
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "test_tracker.db"
    return TrackerDatabase(db_path=db_path)


def _make_recommendation(
    side: str = "MTL",
    sportsbook: str = "DraftKings",
    american_odds: int = 120,
    commence: str = "2026-03-10T19:00:00Z",
    home: str = "MTL",
    away: str = "TOR",
    stake: float = 25.0,
    confidence: float = 0.85,
) -> dict:
    """Build a minimal recommendation dict as RiskAgent would produce."""
    dec = 1 + american_odds / 100 if american_odds > 0 else 1 + 100 / abs(american_odds)
    candidate = ValueCandidate(
        commence_time_utc=commence,
        home_team=home,
        away_team=away,
        side=side,
        sportsbook=sportsbook,
        american_odds=american_odds,
        decimal_odds=dec,
        implied_probability=0.455,
        model_probability=0.55,
        edge_probability_points=9.5,
        expected_value_per_dollar=0.18,
        kelly_fraction=0.09,
        confidence=confidence,
    )
    return {
        "candidate": candidate,
        "recommended_stake": stake,
        "stake_fraction": round(stake / 1000.0, 4),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_database_round_trip():
    """Save a prediction and retrieve it; verify core fields survive the trip."""
    with _tmp_db() as db:
        rec = _make_recommendation(stake=30.0)
        pred_id = db.save_prediction(rec, profile="aggressive")

        assert isinstance(pred_id, int)
        assert pred_id >= 1

        rows = db.get_predictions(profile="aggressive")
        assert len(rows) == 1

        row = rows[0]
        assert row["id"] == pred_id
        assert row["profile"] == "aggressive"
        assert row["home_team"] == "MTL"
        assert row["away_team"] == "TOR"
        assert row["side"] == "MTL"
        assert row["sportsbook"] == "DraftKings"
        assert row["american_odds"] == 120
        assert abs(row["model_probability"] - 0.55) < 1e-6
        assert abs(row["recommended_stake"] - 30.0) < 1e-6
        # outcome must be NULL until settled
        assert row["outcome"] is None
        assert row["profit_loss"] is None


def test_settle_prediction():
    """Save a prediction, settle it as a win, and verify P&L is stored."""
    with _tmp_db() as db:
        rec = _make_recommendation(stake=50.0, american_odds=110)
        pred_id = db.save_prediction(rec)

        # Win: stake $50 at +110 → profit = $55
        pnl = 55.0
        db.settle(pred_id, outcome="win", closing_odds=105, profit_loss=pnl)

        rows = db.get_predictions()
        assert len(rows) == 1
        row = rows[0]

        assert row["outcome"] == "win"
        assert row["closing_odds"] == 105
        assert abs(row["profit_loss"] - pnl) < 1e-6
        assert row["settled_at"] is not None


def test_get_unsettled():
    """Save two predictions, settle one, confirm only one unsettled remains."""
    with _tmp_db() as db:
        rec_a = _make_recommendation(side="MTL", sportsbook="BookA", stake=20.0)
        rec_b = _make_recommendation(side="TOR", sportsbook="BookB", stake=15.0,
                                     american_odds=-120)

        id_a = db.save_prediction(rec_a)
        id_b = db.save_prediction(rec_b)

        # Settle the first one
        db.settle(id_a, outcome="loss", closing_odds=125, profit_loss=-20.0)

        unsettled = db.get_unsettled()
        assert len(unsettled) == 1
        assert unsettled[0]["id"] == id_b
        assert unsettled[0]["outcome"] is None
