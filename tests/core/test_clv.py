"""Tests for Closing Line Value (CLV) calculations and database persistence."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.core.clv import aggregate_clv, calculate_clv


# ---------------------------------------------------------------------------
# calculate_clv — unit tests
# ---------------------------------------------------------------------------


class TestCalculateClv:
    """Tests for the calculate_clv function."""

    def test_placed_better_than_close_positive_clv(self):
        """Placing at +150 when it closes at +130 should yield positive CLV.

        Implied prob of +150 = 100/250 = 40.0%
        Implied prob of +130 = 100/230 ≈ 43.48%
        CLV = 43.48 - 40.0 = +3.48 cents (positive → beat the close)
        """
        result = calculate_clv(placement_odds=150, closing_odds=130)
        assert result["clv_cents"] > 0, "Beat the close should yield positive CLV"
        assert abs(result["clv_cents"] - 3.48) < 0.1
        assert result["clv_pct"] > 0
        assert result["placement_implied"] == pytest.approx(0.4, abs=0.001)
        assert result["closing_implied"] == pytest.approx(0.4348, abs=0.001)

    def test_placed_worse_than_close_negative_clv(self):
        """Placing at +130 when it closes at +150 should yield negative CLV.

        You got worse odds than where the market ended up.
        """
        result = calculate_clv(placement_odds=130, closing_odds=150)
        assert result["clv_cents"] < 0, "Placed at worse odds → negative CLV"

    def test_same_odds_zero_clv(self):
        """Placing and closing at the same odds should give CLV = 0."""
        result = calculate_clv(placement_odds=110, closing_odds=110)
        assert result["clv_cents"] == pytest.approx(0.0, abs=1e-6)
        assert result["clv_pct"] == pytest.approx(0.0, abs=1e-6)

    def test_negative_american_odds_favorite(self):
        """Test CLV for a favorite: placed at -110, line moved to -130 (line sharpened against you)."""
        # -110 implied = 110/210 ≈ 52.38%
        # -130 implied = 130/230 ≈ 56.52%
        # Closing implied > placement implied → positive CLV (sharp money agreed with you)
        result = calculate_clv(placement_odds=-110, closing_odds=-130)
        assert result["clv_cents"] > 0
        assert result["placement_implied"] == pytest.approx(110 / 210, abs=0.001)
        assert result["closing_implied"] == pytest.approx(130 / 230, abs=0.001)

    def test_favorite_line_moves_away_negative_clv(self):
        """Placed a favorite at -130, line opens up to -110 → you paid too much."""
        result = calculate_clv(placement_odds=-130, closing_odds=-110)
        assert result["clv_cents"] < 0

    def test_extreme_underdog_odds(self):
        """Extreme underdog odds like +1000 should compute without errors."""
        result = calculate_clv(placement_odds=1000, closing_odds=800)
        assert "clv_cents" in result
        assert "placement_implied" in result
        assert result["placement_implied"] == pytest.approx(100 / 1100, abs=0.001)

    def test_return_keys_present(self):
        """Result dict should always contain all expected keys."""
        result = calculate_clv(placement_odds=200, closing_odds=180)
        assert set(result.keys()) == {"clv_cents", "clv_pct", "placement_implied", "closing_implied"}

    def test_clv_cents_is_100x_clv_pct(self):
        """clv_cents should equal clv_pct * 100 (within rounding)."""
        result = calculate_clv(placement_odds=120, closing_odds=110)
        assert result["clv_cents"] == pytest.approx(result["clv_pct"] * 100, abs=0.0001)


# ---------------------------------------------------------------------------
# aggregate_clv — unit tests
# ---------------------------------------------------------------------------


class TestAggregateClv:
    """Tests for the aggregate_clv function."""

    def test_empty_list_returns_zeros(self):
        result = aggregate_clv([])
        assert result["total_bets"] == 0
        assert result["avg_clv_cents"] == 0.0
        assert result["pct_beating_close"] == 0.0
        assert result["clv_by_book"] == {}

    def test_all_positive_clv(self):
        """All bets beating the close → 100% beating close, positive avg."""
        bets = [
            {"placement_odds": 150, "closing_odds": 130, "sportsbook": "DraftKings"},
            {"placement_odds": 200, "closing_odds": 170, "sportsbook": "DraftKings"},
        ]
        result = aggregate_clv(bets)
        assert result["pct_beating_close"] == 1.0
        assert result["avg_clv_cents"] > 0
        assert result["total_bets"] == 2

    def test_all_negative_clv(self):
        """All bets worse than close → 0% beating close, negative avg."""
        bets = [
            {"placement_odds": 130, "closing_odds": 150, "sportsbook": "FanDuel"},
            {"placement_odds": 120, "closing_odds": 140, "sportsbook": "FanDuel"},
        ]
        result = aggregate_clv(bets)
        assert result["pct_beating_close"] == 0.0
        assert result["avg_clv_cents"] < 0
        assert result["total_bets"] == 2

    def test_mixed_clv(self):
        """Mix of positive and negative CLV bets."""
        bets = [
            {"placement_odds": 150, "closing_odds": 130, "sportsbook": "BookA"},  # positive
            {"placement_odds": 130, "closing_odds": 150, "sportsbook": "BookB"},  # negative
            {"placement_odds": 110, "closing_odds": 110, "sportsbook": "BookA"},  # zero
        ]
        result = aggregate_clv(bets)
        assert result["total_bets"] == 3
        # 1 out of 3 strictly beats close
        assert result["pct_beating_close"] == pytest.approx(1 / 3, abs=0.01)

    def test_per_book_breakdown(self):
        """clv_by_book should contain entries for each distinct sportsbook."""
        bets = [
            {"placement_odds": 150, "closing_odds": 130, "sportsbook": "DraftKings"},
            {"placement_odds": 150, "closing_odds": 130, "sportsbook": "DraftKings"},
            {"placement_odds": 130, "closing_odds": 150, "sportsbook": "FanDuel"},
        ]
        result = aggregate_clv(bets)
        assert "DraftKings" in result["clv_by_book"]
        assert "FanDuel" in result["clv_by_book"]
        assert result["clv_by_book"]["DraftKings"]["total_bets"] == 2
        assert result["clv_by_book"]["FanDuel"]["total_bets"] == 1
        assert result["clv_by_book"]["DraftKings"]["avg_clv_cents"] > 0
        assert result["clv_by_book"]["FanDuel"]["avg_clv_cents"] < 0

    def test_bets_missing_odds_skipped(self):
        """Bets with None placement or closing odds should be silently skipped."""
        bets = [
            {"placement_odds": 150, "closing_odds": 130, "sportsbook": "Book"},
            {"placement_odds": None, "closing_odds": 130, "sportsbook": "Book"},
            {"placement_odds": 150, "closing_odds": None, "sportsbook": "Book"},
        ]
        result = aggregate_clv(bets)
        assert result["total_bets"] == 1

    def test_missing_sportsbook_defaults_to_unknown(self):
        """Bets without a sportsbook key should be grouped as 'unknown'."""
        bets = [
            {"placement_odds": 150, "closing_odds": 130},
        ]
        result = aggregate_clv(bets)
        assert "unknown" in result["clv_by_book"]


# ---------------------------------------------------------------------------
# Database integration tests
# ---------------------------------------------------------------------------


class TestClosingOddsDatabase:
    """Tests for save_closing_odds and get_closing_odds database methods."""

    def _make_db(self) -> "TrackerDatabase":
        from app.data.database import TrackerDatabase
        tmp = tempfile.mkdtemp()
        return TrackerDatabase(db_path=Path(tmp) / "test_clv.db")

    def test_save_and_retrieve_closing_odds(self):
        """Saved closing odds should be retrievable by game_id."""
        with self._make_db() as db:
            db.save_closing_odds(
                game_id="2026-01-01|TOR|MTL",
                home_team="TOR",
                away_team="MTL",
                sportsbook="DraftKings",
                home_odds=-130,
                away_odds=110,
                market="ML",
            )
            results = db.get_closing_odds("2026-01-01|TOR|MTL", market="ML")
            assert len(results) == 1
            row = results[0]
            assert row["home_team"] == "TOR"
            assert row["away_team"] == "MTL"
            assert row["sportsbook"] == "DraftKings"
            assert row["home_odds"] == -130
            assert row["away_odds"] == 110

    def test_multiple_books_same_game(self):
        """Multiple sportsbooks can be stored for the same game."""
        with self._make_db() as db:
            game_id = "2026-01-01|EDM|CGY"
            db.save_closing_odds(game_id, "EDM", "CGY", "DraftKings", -120, 100)
            db.save_closing_odds(game_id, "EDM", "CGY", "FanDuel", -115, 105)
            results = db.get_closing_odds(game_id)
            assert len(results) == 2
            books = {r["sportsbook"] for r in results}
            assert books == {"DraftKings", "FanDuel"}

    def test_upsert_replaces_existing(self):
        """Re-saving the same game_id+sportsbook+market combo should overwrite."""
        with self._make_db() as db:
            game_id = "2026-01-01|VAN|SEA"
            db.save_closing_odds(game_id, "VAN", "SEA", "BetMGM", -110, -110)
            db.save_closing_odds(game_id, "VAN", "SEA", "BetMGM", -130, 110)
            results = db.get_closing_odds(game_id)
            assert len(results) == 1
            assert results[0]["home_odds"] == -130  # updated value

    def test_get_closing_odds_empty_for_unknown_game(self):
        """Querying a non-existent game_id should return an empty list."""
        with self._make_db() as db:
            results = db.get_closing_odds("no-such-game")
            assert results == []

    def test_get_clv_summary_no_data(self):
        """CLV summary should return zero values when no settled predictions exist."""
        with self._make_db() as db:
            summary = db.get_clv_summary()
            assert summary["total_bets"] == 0
            assert summary["avg_clv_cents"] == 0.0
            assert summary["pct_beating_close"] == 0.0
            assert summary["clv_by_book"] == {}
