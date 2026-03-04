"""Comprehensive tests for the arbitrage detection algorithm in _detect_arbs()."""

from __future__ import annotations

import pytest

from app.web.web_preview import _detect_arbs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    home: str = "TOR",
    away: str = "MTL",
    books: list[dict] | None = None,
) -> dict:
    """Build a minimal game dict for _detect_arbs()."""
    return {
        "home": home,
        "away": away,
        "commence": "2026-03-03T19:00:00Z",
        "home_prob": 0.55,
        "away_prob": 0.45,
        "books": books or [],
    }


def _make_book(
    name: str,
    home_odds: int,
    away_odds: int,
    home_spread: float = -1.5,
    away_spread: float = 1.5,
    home_spread_odds: int = 0,
    away_spread_odds: int = 0,
    total_line: float = 5.5,
    over_odds: int = 0,
    under_odds: int = 0,
) -> dict:
    """Build a minimal book entry.

    American odds: positive = underdog, negative = favourite.
    """
    entry: dict = {
        "name": name,
        "key": name.lower().replace(" ", "_"),
        "home_odds": home_odds,
        "away_odds": away_odds,
        "home_implied": 0.0,
        "away_implied": 0.0,
        "home_edge": 0.0,
        "away_edge": 0.0,
    }
    if home_spread_odds:
        entry["home_spread"] = home_spread
        entry["away_spread"] = away_spread
        entry["home_spread_odds"] = home_spread_odds
        entry["away_spread_odds"] = away_spread_odds
    if over_odds:
        entry["total_line"] = total_line
        entry["over_odds"] = over_odds
        entry["under_odds"] = under_odds
    return entry


# ---------------------------------------------------------------------------
# a) Known arb scenario — hand-verified
# ---------------------------------------------------------------------------

class TestKnownArb:
    """Home at 2.50 (Book A) and Away at 2.00 (Book B).

    Hand calculation:
      margin  = 1/2.50 + 1/2.00 = 0.40 + 0.50 = 0.90
      profit  = (1/0.90 - 1) * 100 = 11.11%
      stake_a = 0.40 / 0.90 * 100 = 44.44
      stake_b = 100 - 44.44 = 55.56
      Return either way = $111.11 on $100 wagered
    """

    def test_detects_moneyline_arb(self):
        # +150 = 2.50 decimal, +100 = 2.00 decimal
        books = [
            _make_book("BookA", home_odds=150, away_odds=-200),
            _make_book("BookB", home_odds=-150, away_odds=100),
        ]
        game = _make_game(books=books)
        arbs = _detect_arbs([game])

        assert len(arbs) == 1
        arb = arbs[0]
        assert arb["market"] == "Moneyline"
        assert arb["side_a"] == "TOR"
        assert arb["side_b"] == "MTL"
        assert arb["side_a_book"] == "BookA"
        assert arb["side_b_book"] == "BookB"

    def test_profit_percentage(self):
        books = [
            _make_book("BookA", home_odds=150, away_odds=-200),
            _make_book("BookB", home_odds=-150, away_odds=100),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        arb = arbs[0]

        # 1/2.50 + 1/2.00 = 0.90
        assert arb["margin"] == pytest.approx(0.90, abs=0.01)
        # profit = (1/0.90 - 1) * 100 = 11.11%
        assert arb["profit_pct"] == pytest.approx(11.11, abs=0.02)

    def test_stake_split(self):
        books = [
            _make_book("BookA", home_odds=150, away_odds=-200),
            _make_book("BookB", home_odds=-150, away_odds=100),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        arb = arbs[0]

        # stake_a = 0.40 / 0.90 * 100 = 44.44
        assert arb["stake_a_pct"] == pytest.approx(44.44, abs=0.02)
        assert arb["stake_b_pct"] == pytest.approx(55.56, abs=0.02)
        # They must sum to 100
        assert arb["stake_a_pct"] + arb["stake_b_pct"] == pytest.approx(100.0, abs=0.01)

    def test_return_consistency(self):
        """Either outcome should yield the same total return."""
        books = [
            _make_book("BookA", home_odds=150, away_odds=-200),
            _make_book("BookB", home_odds=-150, away_odds=100),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        arb = arbs[0]

        return_a = arb["stake_a_pct"] * arb["side_a_odds"]  # bet on home wins
        return_b = arb["stake_b_pct"] * arb["side_b_odds"]  # bet on away wins
        assert return_a == pytest.approx(return_b, rel=0.01)
        # Both should equal ~111.11
        assert return_a == pytest.approx(111.11, abs=0.2)


# ---------------------------------------------------------------------------
# b) No arb scenario — tight odds (margin > 1.0)
# ---------------------------------------------------------------------------

class TestNoArb:
    def test_tight_odds_no_arb(self):
        """Both books have standard vig — no arb possible."""
        # -110 = 1.909 decimal → 1/1.909 = 0.5238
        # margin = 0.5238 + 0.5238 = 1.0476 > 1
        books = [
            _make_book("BookA", home_odds=-110, away_odds=-110),
            _make_book("BookB", home_odds=-115, away_odds=-105),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        assert arbs == []


# ---------------------------------------------------------------------------
# c) Exactly 1.0 margin — should NOT be displayed
# ---------------------------------------------------------------------------

class TestExactlyOneMargin:
    def test_margin_exactly_one(self):
        """Margin of exactly 1.0 means zero profit — should not flag as arb."""
        # +100 = 2.00 decimal → 1/2.00 = 0.50
        # margin = 0.50 + 0.50 = 1.00
        books = [
            _make_book("BookA", home_odds=100, away_odds=-200),
            _make_book("BookB", home_odds=-200, away_odds=100),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        assert arbs == []


# ---------------------------------------------------------------------------
# d) Single bookmaker — can't arb against yourself
# ---------------------------------------------------------------------------

class TestSingleBook:
    def test_single_book_returns_empty(self):
        books = [_make_book("BookA", home_odds=200, away_odds=200)]
        arbs = _detect_arbs([_make_game(books=books)])
        assert arbs == []


# ---------------------------------------------------------------------------
# e) Mismatched spread lines — should NOT detect arb
# ---------------------------------------------------------------------------

class TestMismatchedSpreadLines:
    def test_different_spread_values_no_arb(self):
        """Book A has -1.5, Book B has -2.5 — not comparable."""
        books = [
            _make_book(
                "BookA", home_odds=-110, away_odds=-110,
                home_spread=-1.5, away_spread=1.5,
                home_spread_odds=200, away_spread_odds=-250,
            ),
            _make_book(
                "BookB", home_odds=-110, away_odds=-110,
                home_spread=-2.5, away_spread=2.5,
                home_spread_odds=300, away_spread_odds=-400,
            ),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        # Filter to only spread arbs
        spread_arbs = [a for a in arbs if "Spread" in a["market"]]
        assert spread_arbs == []


# ---------------------------------------------------------------------------
# f) Mismatched total lines — should NOT detect arb
# ---------------------------------------------------------------------------

class TestMismatchedTotalLines:
    def test_different_total_lines_no_arb(self):
        """Over 5.5 vs Under 6.5 are NOT the same market."""
        books = [
            _make_book(
                "BookA", home_odds=-110, away_odds=-110,
                total_line=5.5, over_odds=150, under_odds=-200,
            ),
            _make_book(
                "BookB", home_odds=-110, away_odds=-110,
                total_line=6.5, over_odds=-200, under_odds=150,
            ),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        total_arbs = [a for a in arbs if "Total" in a["market"]]
        assert total_arbs == []


# ---------------------------------------------------------------------------
# g) Same spread lines — valid comparison
# ---------------------------------------------------------------------------

class TestSameSpreadLines:
    def test_same_spread_arb_detected(self):
        """Both books offer -1.5/+1.5 with exploitable odds gap."""
        # BookA: home spread odds +200 = 3.00 decimal → 1/3.00 = 0.333
        # BookB: away spread odds +110 = 2.10 decimal → 1/2.10 = 0.476
        # margin = 0.333 + 0.476 = 0.810 < 1.0 → arb
        books = [
            _make_book(
                "BookA", home_odds=-110, away_odds=-110,
                home_spread=-1.5, away_spread=1.5,
                home_spread_odds=200, away_spread_odds=-250,
            ),
            _make_book(
                "BookB", home_odds=-110, away_odds=-110,
                home_spread=-1.5, away_spread=1.5,
                home_spread_odds=-200, away_spread_odds=110,
            ),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        spread_arbs = [a for a in arbs if "Spread" in a["market"]]
        assert len(spread_arbs) == 1
        arb = spread_arbs[0]
        assert arb["market"] == "Spread -1.5"
        assert arb["margin"] == pytest.approx(0.81, abs=0.01)

    def test_same_total_arb_detected(self):
        """Both books offer 5.5 total with exploitable over/under gap."""
        # BookA: over +105 = 2.05 → 1/2.05 = 0.4878
        # BookB: under +100 = 2.00 → 1/2.00 = 0.5000
        # margin = 0.4878 + 0.5000 = 0.9878 < 1.0 → arb
        books = [
            _make_book(
                "BookA", home_odds=-110, away_odds=-110,
                total_line=5.5, over_odds=105, under_odds=-130,
            ),
            _make_book(
                "BookB", home_odds=-110, away_odds=-110,
                total_line=5.5, over_odds=-125, under_odds=100,
            ),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        total_arbs = [a for a in arbs if "Total" in a["market"]]
        assert len(total_arbs) == 1
        arb = total_arbs[0]
        assert arb["market"] == "Total 5.5"
        assert arb["margin"] < 1.0


# ---------------------------------------------------------------------------
# h) Multiple books — verify best odds selected
# ---------------------------------------------------------------------------

class TestMultipleBooks:
    def test_three_books_selects_best_odds(self):
        """With 3 books, the best home and best away odds should be picked."""
        # BookA: home +160 = 2.60 (best home)
        # BookB: home +120 = 2.20, away +110 = 2.10 (best away)
        # BookC: home +130 = 2.30, away +100 = 2.00
        # Best arb: home from BookA (2.60) + away from BookB (2.10)
        # margin = 1/2.60 + 1/2.10 = 0.3846 + 0.4762 = 0.8608 < 1 → arb
        books = [
            _make_book("BookA", home_odds=160, away_odds=-180),
            _make_book("BookB", home_odds=120, away_odds=110),
            _make_book("BookC", home_odds=130, away_odds=100),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        ml_arbs = [a for a in arbs if a["market"] == "Moneyline"]
        assert len(ml_arbs) == 1
        arb = ml_arbs[0]
        assert arb["side_a_book"] == "BookA"  # best home odds
        assert arb["side_b_book"] == "BookB"  # best away odds
        assert arb["side_a_odds"] == pytest.approx(2.60, abs=0.01)
        assert arb["side_b_odds"] == pytest.approx(2.10, abs=0.01)

    def test_four_books_spread_best_on_same_line(self):
        """4 books, 2 on -1.5 and 2 on -2.5 — arb only within same line group."""
        books = [
            # Line -1.5 group: no arb (tight odds)
            _make_book(
                "BookA", home_odds=-110, away_odds=-110,
                home_spread=-1.5, away_spread=1.5,
                home_spread_odds=150, away_spread_odds=-180,
            ),
            _make_book(
                "BookB", home_odds=-110, away_odds=-110,
                home_spread=-1.5, away_spread=1.5,
                home_spread_odds=140, away_spread_odds=-170,
            ),
            # Line -2.5 group: arb exists
            _make_book(
                "BookC", home_odds=-110, away_odds=-110,
                home_spread=-2.5, away_spread=2.5,
                home_spread_odds=300, away_spread_odds=-400,
            ),
            _make_book(
                "BookD", home_odds=-110, away_odds=-110,
                home_spread=-2.5, away_spread=2.5,
                home_spread_odds=-350, away_spread_odds=250,
            ),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        spread_arbs = [a for a in arbs if "Spread" in a["market"]]
        # Only the -2.5 group should produce an arb
        assert len(spread_arbs) == 1
        assert spread_arbs[0]["market"] == "Spread -2.5"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_games_list(self):
        assert _detect_arbs([]) == []

    def test_game_with_no_books(self):
        game = _make_game(books=[])
        assert _detect_arbs([game]) == []

    def test_multiple_games_arbs_sorted_by_profit(self):
        """Arbs from different games should be sorted by profit_pct descending."""
        game1 = _make_game(
            home="TOR", away="MTL",
            books=[
                _make_book("BookA", home_odds=150, away_odds=-180),
                _make_book("BookB", home_odds=-180, away_odds=100),
            ],
        )
        game2 = _make_game(
            home="EDM", away="VAN",
            books=[
                _make_book("BookA", home_odds=200, away_odds=-250),
                _make_book("BookB", home_odds=-250, away_odds=200),
            ],
        )
        arbs = _detect_arbs([game1, game2])
        assert len(arbs) >= 1
        # If multiple arbs, they should be in descending profit order
        for i in range(len(arbs) - 1):
            assert arbs[i]["profit_pct"] >= arbs[i + 1]["profit_pct"]

    def test_arb_output_has_all_required_fields(self):
        books = [
            _make_book("BookA", home_odds=150, away_odds=-200),
            _make_book("BookB", home_odds=-200, away_odds=100),
        ]
        arbs = _detect_arbs([_make_game(books=books)])
        assert len(arbs) == 1
        arb = arbs[0]
        required = {
            "home_team", "away_team", "market",
            "side_a", "side_a_book", "side_a_odds",
            "side_b", "side_b_book", "side_b_odds",
            "margin", "profit_pct", "stake_a_pct", "stake_b_pct",
        }
        assert required.issubset(arb.keys())
