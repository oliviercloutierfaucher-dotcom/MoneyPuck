"""Tests for app.math.arbitrage module."""

from __future__ import annotations

import pytest

from app.math.arbitrage import find_arbitrages, find_near_arbs


def _make_event(
    home: str = "Team A",
    away: str = "Team B",
    bookmakers: list | None = None,
) -> dict:
    """Build a minimal Odds API-format event."""
    return {
        "home_team": home,
        "away_team": away,
        "commence_time": "2025-01-15T00:00:00Z",
        "bookmakers": bookmakers or [],
    }


def _make_bookmaker(key: str, title: str, markets: list) -> dict:
    return {"key": key, "title": title, "markets": markets}


def _h2h_market(outcomes: list[tuple[str, int]]) -> dict:
    return {
        "key": "h2h",
        "outcomes": [{"name": n, "price": p} for n, p in outcomes],
    }


def _spread_market(outcomes: list[tuple[str, int, float]]) -> dict:
    return {
        "key": "spreads",
        "outcomes": [{"name": n, "price": p, "point": pt} for n, p, pt in outcomes],
    }


def _total_market(outcomes: list[tuple[str, int, float]]) -> dict:
    return {
        "key": "totals",
        "outcomes": [{"name": n, "price": p, "point": pt} for n, p, pt in outcomes],
    }


# ------------------------------------------------------------------ #
# Moneyline arbs
# ------------------------------------------------------------------ #

class TestMoneylineArbs:
    def test_known_arb(self):
        """Book A offers +120 on home, Book B offers +120 on away → arb."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "Book A", [_h2h_market([("Team A", 120), ("Team B", -200)])]),
            _make_bookmaker("b", "Book B", [_h2h_market([("Team A", -200), ("Team B", 120)])]),
        ])
        arbs = find_arbitrages([event])
        assert len(arbs) == 1
        assert arbs[0]["market"] == "Moneyline"
        assert arbs[0]["profit_pct"] > 0
        assert arbs[0]["margin"] < 1.0
        assert arbs[0]["side_a_book"] == "Book A"
        assert arbs[0]["side_b_book"] == "Book B"

    def test_no_arb_standard_vig(self):
        """Both books at -110 → no arb (standard vig)."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "Book A", [_h2h_market([("Team A", -110), ("Team B", -110)])]),
            _make_bookmaker("b", "Book B", [_h2h_market([("Team A", -110), ("Team B", -110)])]),
        ])
        arbs = find_arbitrages([event])
        assert len(arbs) == 0

    def test_single_bookmaker_no_arb(self):
        """Single bookmaker can't produce cross-book arb."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "Book A", [_h2h_market([("Team A", 200), ("Team B", 200)])]),
        ])
        arbs = find_arbitrages([event])
        assert len(arbs) == 0

    def test_empty_bookmakers(self):
        arbs = find_arbitrages([_make_event(bookmakers=[])])
        assert arbs == []

    def test_same_book_ml_rejected(self):
        """Both sides from same book → no arb even if margin < 1."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "Book A", [_h2h_market([("Team A", 200), ("Team B", 200)])]),
            _make_bookmaker("a", "Book A", [_h2h_market([("Team A", 200), ("Team B", 200)])]),
        ])
        arbs = find_arbitrages([event])
        assert len(arbs) == 0

    def test_same_book_near_arb_rejected(self):
        """Near-arb on same book rejected too."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "Book A", [_h2h_market([("Team A", 105), ("Team B", 105)])]),
            _make_bookmaker("a", "Book A", [_h2h_market([("Team A", 105), ("Team B", 105)])]),
        ])
        near = find_near_arbs([event])
        assert len(near) == 0

    def test_arb_sorted_by_profit(self):
        """Multiple events, results sorted by profit descending."""
        event1 = _make_event(home="A", away="B", bookmakers=[
            _make_bookmaker("x", "X", [_h2h_market([("A", 150), ("B", -300)])]),
            _make_bookmaker("y", "Y", [_h2h_market([("A", -300), ("B", 150)])]),
        ])
        event2 = _make_event(home="C", away="D", bookmakers=[
            _make_bookmaker("x", "X", [_h2h_market([("C", 120), ("D", -250)])]),
            _make_bookmaker("y", "Y", [_h2h_market([("C", -250), ("D", 120)])]),
        ])
        arbs = find_arbitrages([event1, event2])
        assert len(arbs) == 2
        assert arbs[0]["profit_pct"] >= arbs[1]["profit_pct"]

    def test_stake_split_sums_to_100(self):
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "A", [_h2h_market([("Team A", 130), ("Team B", -300)])]),
            _make_bookmaker("b", "B", [_h2h_market([("Team A", -300), ("Team B", 130)])]),
        ])
        arbs = find_arbitrages([event])
        if arbs:
            total = arbs[0]["stake_a_pct"] + arbs[0]["stake_b_pct"]
            assert abs(total - 100.0) < 0.5


# ------------------------------------------------------------------ #
# Spread arbs
# ------------------------------------------------------------------ #

class TestSpreadArbs:
    def test_spread_arb_same_line(self):
        """Arb on matching spread lines across books."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "A", [_spread_market([
                ("Team A", 130, -1.5), ("Team B", -200, 1.5),
            ])]),
            _make_bookmaker("b", "B", [_spread_market([
                ("Team A", -200, -1.5), ("Team B", 130, 1.5),
            ])]),
        ])
        arbs = find_arbitrages([event])
        spread_arbs = [a for a in arbs if "Spread" in a["market"]]
        assert len(spread_arbs) == 1
        assert spread_arbs[0]["profit_pct"] > 0

    def test_no_spread_arb_standard_vig(self):
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "A", [_spread_market([
                ("Team A", -110, -1.5), ("Team B", -110, 1.5),
            ])]),
            _make_bookmaker("b", "B", [_spread_market([
                ("Team A", -110, -1.5), ("Team B", -110, 1.5),
            ])]),
        ])
        arbs = find_arbitrages([event])
        spread_arbs = [a for a in arbs if "Spread" in a["market"]]
        assert len(spread_arbs) == 0


# ------------------------------------------------------------------ #
# Total arbs
# ------------------------------------------------------------------ #

class TestTotalArbs:
    def test_total_arb(self):
        """Over/under arb across books on same line."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "A", [_total_market([
                ("Over", 130, 5.5), ("Under", -200, 5.5),
            ])]),
            _make_bookmaker("b", "B", [_total_market([
                ("Over", -200, 5.5), ("Under", 130, 5.5),
            ])]),
        ])
        arbs = find_arbitrages([event])
        total_arbs = [a for a in arbs if "Total" in a["market"]]
        assert len(total_arbs) == 1
        assert "5.5" in total_arbs[0]["market"]

    def test_no_total_arb(self):
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "A", [_total_market([
                ("Over", -110, 5.5), ("Under", -110, 5.5),
            ])]),
            _make_bookmaker("b", "B", [_total_market([
                ("Over", -110, 5.5), ("Under", -110, 5.5),
            ])]),
        ])
        arbs = find_arbitrages([event])
        total_arbs = [a for a in arbs if "Total" in a["market"]]
        assert len(total_arbs) == 0


# ------------------------------------------------------------------ #
# Near-arbs
# ------------------------------------------------------------------ #

class TestNearArbs:
    def test_near_arb_detected(self):
        """Low-vig market just above break-even detected as near-arb."""
        # -105 on both sides → margin ≈ 1.024 → within default 0.02 threshold? No.
        # Use -102 on both sides → margin ≈ 1.0196 → within 0.02
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "A", [_h2h_market([("Team A", -102), ("Team B", -200)])]),
            _make_bookmaker("b", "B", [_h2h_market([("Team A", -200), ("Team B", -102)])]),
        ])
        near = find_near_arbs([event], threshold=0.03)
        assert len(near) >= 1
        assert near[0]["margin"] >= 1.0

    def test_true_arb_excluded_from_near(self):
        """True arbs (margin < 1) should NOT appear in near-arbs."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "A", [_h2h_market([("Team A", 120), ("Team B", -200)])]),
            _make_bookmaker("b", "B", [_h2h_market([("Team A", -200), ("Team B", 120)])]),
        ])
        near = find_near_arbs([event])
        assert len(near) == 0

    def test_high_vig_excluded(self):
        """High-vig markets are NOT near-arbs."""
        event = _make_event(bookmakers=[
            _make_bookmaker("a", "A", [_h2h_market([("Team A", -150), ("Team B", -150)])]),
            _make_bookmaker("b", "B", [_h2h_market([("Team A", -150), ("Team B", -150)])]),
        ])
        near = find_near_arbs([event], threshold=0.02)
        assert len(near) == 0

    def test_near_arbs_sorted_by_margin(self):
        """Near-arbs sorted by margin ascending (closest to arb first)."""
        e1 = _make_event(home="A", away="B", bookmakers=[
            _make_bookmaker("x", "X", [_h2h_market([("A", -101), ("B", -200)])]),
            _make_bookmaker("y", "Y", [_h2h_market([("A", -200), ("B", -101)])]),
        ])
        e2 = _make_event(home="C", away="D", bookmakers=[
            _make_bookmaker("x", "X", [_h2h_market([("C", -103), ("D", -200)])]),
            _make_bookmaker("y", "Y", [_h2h_market([("C", -200), ("D", -103)])]),
        ])
        near = find_near_arbs([e1, e2], threshold=0.03)
        if len(near) >= 2:
            assert near[0]["margin"] <= near[1]["margin"]


# ------------------------------------------------------------------ #
# Cross-source arb (Polymarket + sportsbook)
# ------------------------------------------------------------------ #

class TestCrossSourceArb:
    def test_polymarket_sportsbook_arb(self):
        """Polymarket as a bookmaker with divergent odds creates arb."""
        event = _make_event(home="Toronto Maple Leafs", away="Montreal Canadiens", bookmakers=[
            _make_bookmaker("fanduel", "FanDuel", [
                _h2h_market([("Toronto Maple Leafs", -150), ("Montreal Canadiens", 130)]),
            ]),
            _make_bookmaker("polymarket", "Polymarket", [
                _h2h_market([("Toronto Maple Leafs", 140), ("Montreal Canadiens", -160)]),
            ]),
        ])
        arbs = find_arbitrages([event])
        assert len(arbs) == 1
        # One leg from each source
        books = {arbs[0]["side_a_book"], arbs[0]["side_b_book"]}
        assert "Polymarket" in books
        assert "FanDuel" in books
