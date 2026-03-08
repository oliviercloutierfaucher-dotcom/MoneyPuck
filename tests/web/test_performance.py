"""Tests for the /api/performance endpoint and its data helpers."""
from __future__ import annotations

import json
import pathlib
import sqlite3
import tempfile

import pytest

from app.web.app import _aggregate_performance, _demo_performance_data, _build_performance_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prediction(
    *,
    outcome: str | None = "win",
    stake: float = 30.0,
    profit_loss: float = 25.0,
    sportsbook: str = "Bet365",
    home_team: str = "TOR",
    away_team: str = "MTL",
    commence_time: str = "2025-01-15T19:00:00Z",
    decimal_odds: float = 1.85,
    settled_at: str | None = "2025-01-15 22:30:00",
    created_at: str = "2025-01-15 12:00:00",
) -> dict:
    return {
        "id": 1,
        "created_at": created_at,
        "game_id": f"{commence_time}|{home_team}|{away_team}",
        "commence_time": commence_time,
        "home_team": home_team,
        "away_team": away_team,
        "side": home_team,
        "sportsbook": sportsbook,
        "american_odds": -118,
        "decimal_odds": decimal_odds,
        "implied_probability": 0.541,
        "model_probability": 0.60,
        "model_confidence": 0.65,
        "edge_pp": 5.9,
        "ev_per_dollar": 0.059,
        "kelly_fraction": 0.05,
        "recommended_stake": stake,
        "profile": "default",
        "outcome": outcome,
        "closing_odds": -115,
        "profit_loss": profit_loss,
        "settled_at": settled_at,
    }


# ---------------------------------------------------------------------------
# 1. Demo data structure
# ---------------------------------------------------------------------------

class TestDemoPerformanceData:
    def test_returns_required_top_level_keys(self):
        d = _demo_performance_data()
        required = {
            "total_bets", "settled_bets", "pending_bets",
            "wins", "losses", "win_rate",
            "total_staked", "total_returned", "net_profit", "roi_pct",
            "by_month", "by_book", "recent_bets",
        }
        assert required.issubset(d.keys())

    def test_numeric_sanity(self):
        d = _demo_performance_data()
        assert d["total_bets"] > 0
        assert d["wins"] + d["losses"] == d["settled_bets"]
        assert 0.0 <= d["win_rate"] <= 1.0
        assert d["total_staked"] > 0
        assert isinstance(d["roi_pct"], float)

    def test_by_month_shape(self):
        d = _demo_performance_data()
        assert len(d["by_month"]) > 0
        month = d["by_month"][0]
        assert "month" in month
        assert "bets" in month
        assert "profit" in month
        assert "roi" in month

    def test_by_book_sorted_descending(self):
        d = _demo_performance_data()
        rois = [b["roi"] for b in d["by_book"]]
        assert rois == sorted(rois, reverse=True)

    def test_recent_bets_shape(self):
        d = _demo_performance_data()
        assert len(d["recent_bets"]) > 0
        bet = d["recent_bets"][0]
        for key in ("date", "game", "side", "odds", "stake", "result", "profit"):
            assert key in bet

    def test_demo_flag_present(self):
        d = _demo_performance_data()
        assert d.get("_demo") is True


# ---------------------------------------------------------------------------
# 2. Aggregation logic
# ---------------------------------------------------------------------------

class TestAggregatePerformance:
    def test_basic_win_loss_counts(self):
        predictions = [
            _make_prediction(outcome="win", profit_loss=25.0, stake=30.0),
            _make_prediction(outcome="loss", profit_loss=-30.0, stake=30.0),
            _make_prediction(outcome="win", profit_loss=20.0, stake=30.0),
        ]
        result = _aggregate_performance(predictions)
        assert result["wins"] == 2
        assert result["losses"] == 1
        assert result["settled_bets"] == 3
        assert result["pending_bets"] == 0

    def test_pending_bets_counted(self):
        predictions = [
            _make_prediction(outcome="win", profit_loss=25.0, stake=30.0),
            _make_prediction(outcome=None, profit_loss=None, stake=30.0),
        ]
        result = _aggregate_performance(predictions)
        assert result["pending_bets"] == 1
        assert result["settled_bets"] == 1

    def test_win_rate_calculation(self):
        predictions = [
            _make_prediction(outcome="win", profit_loss=20.0, stake=30.0),
            _make_prediction(outcome="win", profit_loss=20.0, stake=30.0),
            _make_prediction(outcome="loss", profit_loss=-30.0, stake=30.0),
        ]
        result = _aggregate_performance(predictions)
        # win_rate is rounded to 4 decimal places
        assert abs(result["win_rate"] - (2 / 3)) < 1e-4

    def test_net_profit_and_roi(self):
        stake = 100.0
        profit = 20.0
        predictions = [
            _make_prediction(outcome="win", profit_loss=profit, stake=stake),
        ]
        result = _aggregate_performance(predictions)
        assert result["total_staked"] == pytest.approx(stake)
        assert result["net_profit"] == pytest.approx(profit)
        assert result["roi_pct"] == pytest.approx(profit / stake * 100, abs=0.01)

    def test_monthly_aggregation(self):
        predictions = [
            _make_prediction(
                outcome="win", profit_loss=25.0, stake=30.0,
                settled_at="2025-01-15 22:00:00",
            ),
            _make_prediction(
                outcome="loss", profit_loss=-30.0, stake=30.0,
                settled_at="2025-02-10 22:00:00",
            ),
        ]
        result = _aggregate_performance(predictions)
        months = {m["month"]: m for m in result["by_month"]}
        assert "2025-01" in months
        assert "2025-02" in months
        assert months["2025-01"]["bets"] == 1
        assert months["2025-01"]["profit"] == pytest.approx(25.0)
        assert months["2025-02"]["bets"] == 1
        assert months["2025-02"]["profit"] == pytest.approx(-30.0)

    def test_by_book_aggregation_and_sorting(self):
        predictions = [
            _make_prediction(outcome="win", profit_loss=40.0, stake=30.0, sportsbook="BetMGM"),
            _make_prediction(outcome="loss", profit_loss=-30.0, stake=30.0, sportsbook="Bet365"),
            _make_prediction(outcome="win", profit_loss=35.0, stake=30.0, sportsbook="BetMGM"),
        ]
        result = _aggregate_performance(predictions)
        books = {b["book"]: b for b in result["by_book"]}
        assert books["BetMGM"]["bets"] == 2
        assert books["BetMGM"]["profit"] == pytest.approx(75.0)
        assert books["Bet365"]["profit"] == pytest.approx(-30.0)
        # BetMGM has higher ROI — should come first
        assert result["by_book"][0]["book"] == "BetMGM"

    def test_recent_bets_structure(self):
        preds = [
            _make_prediction(
                outcome="win", profit_loss=20.0, stake=30.0,
                home_team="EDM", away_team="VAN",
                decimal_odds=1.90,
            )
        ]
        result = _aggregate_performance(preds)
        assert len(result["recent_bets"]) == 1
        bet = result["recent_bets"][0]
        assert bet["game"] == "VAN @ EDM"
        assert bet["side"] == "EDM"
        assert bet["result"] == "win"
        assert bet["profit"] == pytest.approx(20.0)
        assert bet["odds"] == pytest.approx(1.90)

    def test_empty_predictions_no_crash(self):
        result = _aggregate_performance([])
        assert result["total_bets"] == 0
        assert result["win_rate"] == 0.0
        assert result["roi_pct"] == 0.0
        assert result["by_month"] == []
        assert result["by_book"] == []
        assert result["recent_bets"] == []


# ---------------------------------------------------------------------------
# 3. Build performance data — fallback to demo when no DB
# ---------------------------------------------------------------------------

class TestBuildPerformanceData:
    def test_falls_back_to_demo_when_db_missing(self, monkeypatch, tmp_path):
        """If DB_PATH does not exist, returns demo data."""
        import app.web.app as wp
        monkeypatch.setattr(
            "app.data.database.DB_PATH",
            tmp_path / "nonexistent.db",
        )
        result = _build_performance_data()
        # Must have all required keys
        assert "total_bets" in result
        assert "by_month" in result
        assert "recent_bets" in result

    def test_returns_valid_json_serialisable_dict(self):
        result = _build_performance_data()
        # Must be JSON-serialisable
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert "total_bets" in parsed

    def test_win_rate_bounded(self):
        result = _build_performance_data()
        assert 0.0 <= result["win_rate"] <= 1.0

    def test_by_month_list(self):
        result = _build_performance_data()
        assert isinstance(result["by_month"], list)

    def test_by_book_sorted(self):
        result = _build_performance_data()
        rois = [b["roi"] for b in result["by_book"]]
        assert rois == sorted(rois, reverse=True)

    def test_recent_bets_at_most_ten(self):
        result = _build_performance_data()
        assert len(result["recent_bets"]) <= 10
