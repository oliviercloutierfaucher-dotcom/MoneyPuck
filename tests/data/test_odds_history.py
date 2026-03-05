"""Tests for app.data.odds_history — line movement tracking."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.data.odds_history import (
    OddsSnapshot,
    _american_to_implied,
    build_history_response,
    clear_history,
    generate_demo_sparkline,
    get_consensus_history,
    get_history,
    init_odds_history_table,
    load_history_from_db,
    make_game_id,
    persist_snapshot,
    record_snapshot,
    record_snapshots_from_dashboard,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_store():
    """Wipe the global in-memory store before each test."""
    clear_history()
    yield
    clear_history()


def _snap(game_id="TOR-MTL-2026-03-05T19:00:00", sportsbook="Bet365",
          home_odds=-150, away_odds=130,
          ts: datetime | None = None) -> OddsSnapshot:
    return OddsSnapshot(
        game_id=game_id,
        home_team="TOR",
        away_team="MTL",
        sportsbook=sportsbook,
        home_odds=home_odds,
        away_odds=away_odds,
        timestamp=ts or datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. make_game_id
# ---------------------------------------------------------------------------

class TestMakeGameId:
    def test_basic_format(self):
        gid = make_game_id("TOR", "MTL", "2026-03-05T19:00:00Z")
        assert gid == "TOR-MTL-2026-03-05T19:00:00Z"

    def test_strips_microseconds(self):
        gid = make_game_id("EDM", "VAN", "2026-03-05T22:00:00.000000Z")
        # The dot-split strips the fractional seconds; the trailing Z is part
        # of the fraction suffix, so the result won't have it — that's fine,
        # the important thing is no fractional seconds remain.
        assert ".000000" not in gid
        assert gid.startswith("EDM-VAN-2026-03-05T22:00:00")

    def test_no_dot_unchanged(self):
        gid = make_game_id("BOS", "BUF", "2026-03-05T19:00:00Z")
        assert "." not in gid


# ---------------------------------------------------------------------------
# 2. record_snapshot + get_history
# ---------------------------------------------------------------------------

class TestRecordAndRetrieve:
    def test_empty_history_returns_empty_list(self):
        result = get_history("nonexistent-game-id")
        assert result == []

    def test_single_snapshot_stored(self):
        snap = _snap()
        record_snapshot(snap)
        history = get_history(snap.game_id)
        assert len(history) == 1
        assert history[0].sportsbook == "Bet365"

    def test_multiple_snapshots_sorted_by_time(self):
        t1 = datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 5, 16, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 3, 5, 18, 0, 0, tzinfo=timezone.utc)
        # Insert out of order
        record_snapshot(_snap(ts=t3))
        record_snapshot(_snap(ts=t1))
        record_snapshot(_snap(ts=t2))
        history = get_history("TOR-MTL-2026-03-05T19:00:00")
        timestamps = [s.timestamp for s in history]
        assert timestamps == sorted(timestamps)

    def test_separate_games_isolated(self):
        snap_a = _snap(game_id="TOR-MTL-2026-03-05T19:00:00")
        snap_b = OddsSnapshot(
            game_id="EDM-VAN-2026-03-05T22:00:00",
            home_team="EDM", away_team="VAN",
            sportsbook="Bet365", home_odds=-120, away_odds=100,
            timestamp=datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
        )
        record_snapshot(snap_a)
        record_snapshot(snap_b)
        assert len(get_history("TOR-MTL-2026-03-05T19:00:00")) == 1
        assert len(get_history("EDM-VAN-2026-03-05T22:00:00")) == 1


# ---------------------------------------------------------------------------
# 3. OddsSnapshot implied properties
# ---------------------------------------------------------------------------

class TestOddsSnapshotImplied:
    def test_negative_american_to_implied(self):
        snap = _snap(home_odds=-150)
        assert abs(snap.home_implied - (150 / 250)) < 0.0001

    def test_positive_american_to_implied(self):
        snap = _snap(away_odds=130)
        assert abs(snap.away_implied - (100 / 230)) < 0.0001

    def test_helper_zero_returns_half(self):
        assert _american_to_implied(0) == 0.5


# ---------------------------------------------------------------------------
# 4. get_consensus_history
# ---------------------------------------------------------------------------

class TestConsensusHistory:
    def test_empty_game_returns_empty(self):
        result = get_consensus_history("no-such-game")
        assert result == []

    def test_single_book_single_time(self):
        t = datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc)
        record_snapshot(_snap(home_odds=-150, away_odds=130, ts=t))
        consensus = get_consensus_history("TOR-MTL-2026-03-05T19:00:00")
        assert len(consensus) == 1
        row = consensus[0]
        assert "time" in row
        assert "home_implied" in row
        assert "away_implied" in row
        assert "books" in row
        assert row["time"] == "14:00"

    def test_multiple_books_averaged(self):
        """Two books at the same minute should be averaged."""
        t = datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc)
        # Book A: home -150 → 0.6
        record_snapshot(_snap(sportsbook="BookA", home_odds=-150, away_odds=130, ts=t))
        # Book B: home -130 → ~0.565
        record_snapshot(_snap(sportsbook="BookB", home_odds=-130, away_odds=110, ts=t))
        consensus = get_consensus_history("TOR-MTL-2026-03-05T19:00:00")
        assert len(consensus) == 1
        # Average should be between the two
        exp_a = 150 / 250
        exp_b = 130 / 230
        expected_avg = (exp_a + exp_b) / 2
        assert abs(consensus[0]["home_implied"] - round(expected_avg, 4)) < 0.001

    def test_multiple_timestamps_create_multiple_buckets(self):
        t1 = datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 5, 16, 30, 0, tzinfo=timezone.utc)
        record_snapshot(_snap(ts=t1))
        record_snapshot(_snap(ts=t2))
        consensus = get_consensus_history("TOR-MTL-2026-03-05T19:00:00")
        assert len(consensus) == 2
        # Times should be chronological
        assert consensus[0]["time"] == "14:00"
        assert consensus[1]["time"] == "16:30"

    def test_books_detail_included(self):
        t = datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc)
        record_snapshot(_snap(sportsbook="Bet365", home_odds=-150, away_odds=130, ts=t))
        consensus = get_consensus_history("TOR-MTL-2026-03-05T19:00:00")
        assert "Bet365" in consensus[0]["books"]
        assert "home" in consensus[0]["books"]["Bet365"]
        assert "away" in consensus[0]["books"]["Bet365"]


# ---------------------------------------------------------------------------
# 5. build_history_response
# ---------------------------------------------------------------------------

class TestBuildHistoryResponse:
    def test_no_history_returns_null_fields(self):
        resp = build_history_response("empty-game")
        assert resp["game_id"] == "empty-game"
        assert resp["snapshots"] == []
        assert resp["opening"] is None
        assert resp["current"] is None
        assert resp["movement"] is None

    def test_with_two_snapshots_calculates_movement(self):
        t1 = datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 5, 16, 0, 0, tzinfo=timezone.utc)
        # Opening: home -150 (implied ~0.6)
        record_snapshot(_snap(home_odds=-150, away_odds=130, ts=t1))
        # Current: home -170 (implied ~0.63) — line moved toward home
        record_snapshot(_snap(home_odds=-170, away_odds=150, ts=t2))
        resp = build_history_response("TOR-MTL-2026-03-05T19:00:00")
        assert resp["opening"]["home_implied"] < resp["current"]["home_implied"]
        assert resp["movement"]["home_shift"] > 0
        assert resp["movement"]["away_shift"] < 0
        assert len(resp["snapshots"]) == 2


# ---------------------------------------------------------------------------
# 6. generate_demo_sparkline
# ---------------------------------------------------------------------------

class TestGenerateDemoSparkline:
    def test_returns_n_points(self):
        result = generate_demo_sparkline("TOR-MTL-abc", "TOR", "MTL", 0.58, n_points=5)
        assert len(result) == 5

    def test_last_point_near_current_prob(self):
        current = 0.62
        result = generate_demo_sparkline("TOR-MTL-abc", "TOR", "MTL", current, n_points=4)
        assert abs(result[-1]["home_implied"] - current) < 0.001

    def test_all_points_have_required_keys(self):
        result = generate_demo_sparkline("EDM-VAN-xyz", "EDM", "VAN", 0.55, n_points=3)
        for pt in result:
            assert "time" in pt
            assert "home_implied" in pt
            assert "away_implied" in pt
            assert "books" in pt

    def test_home_away_sum_to_one(self):
        result = generate_demo_sparkline("BOS-BUF-test", "BOS", "BUF", 0.50, n_points=5)
        for pt in result:
            total = pt["home_implied"] + pt["away_implied"]
            assert abs(total - 1.0) < 0.001

    def test_probs_within_valid_range(self):
        result = generate_demo_sparkline("FLA-NYR-test", "FLA", "NYR", 0.70, n_points=10)
        for pt in result:
            assert 0.0 < pt["home_implied"] < 1.0
            assert 0.0 < pt["away_implied"] < 1.0

    def test_deterministic_with_same_seed(self):
        r1 = generate_demo_sparkline("TOR-MTL-seed", "TOR", "MTL", 0.58)
        r2 = generate_demo_sparkline("TOR-MTL-seed", "TOR", "MTL", 0.58)
        assert r1 == r2

    def test_different_games_differ(self):
        r1 = generate_demo_sparkline("TOR-MTL-aaa", "TOR", "MTL", 0.58)
        r2 = generate_demo_sparkline("EDM-VAN-bbb", "EDM", "VAN", 0.58)
        # Same current prob but different seeds — at least one intermediate point should differ
        any_different = any(
            r1[i]["home_implied"] != r2[i]["home_implied"]
            for i in range(len(r1))
        )
        assert any_different

    def test_default_five_points(self):
        result = generate_demo_sparkline("WPG-CHI-default", "WPG", "CHI", 0.65)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# 7. record_snapshots_from_dashboard
# ---------------------------------------------------------------------------

class TestRecordSnapshotsFromDashboard:
    def test_records_all_books(self):
        games = [{
            "home": "TOR", "away": "MTL",
            "commence": "2026-03-05T19:00:00Z",
            "books": [
                {"name": "Bet365", "home_odds": -150, "away_odds": 130},
                {"name": "Betway", "home_odds": -145, "away_odds": 125},
            ],
        }]
        record_snapshots_from_dashboard(games)
        gid = make_game_id("TOR", "MTL", "2026-03-05T19:00:00Z")
        history = get_history(gid)
        assert len(history) == 2
        books = {s.sportsbook for s in history}
        assert "Bet365" in books
        assert "Betway" in books

    def test_skips_missing_odds(self):
        games = [{
            "home": "EDM", "away": "VAN",
            "commence": "2026-03-05T22:00:00Z",
            "books": [
                {"name": "BookA", "home_odds": 0, "away_odds": 110},
                {"name": "BookB", "home_odds": -120, "away_odds": 0},
            ],
        }]
        record_snapshots_from_dashboard(games)
        gid = make_game_id("EDM", "VAN", "2026-03-05T22:00:00Z")
        # Both should be skipped (missing one side)
        assert get_history(gid) == []

    def test_skips_games_without_books(self):
        games = [{"home": "BOS", "away": "BUF", "commence": "2026-03-05T19:00:00Z", "books": []}]
        record_snapshots_from_dashboard(games)
        assert get_history(make_game_id("BOS", "BUF", "2026-03-05T19:00:00Z")) == []


# ---------------------------------------------------------------------------
# 8. SQLite persistence
# ---------------------------------------------------------------------------

class TestSQLitePersistence:
    def test_init_creates_table(self):
        conn = sqlite3.connect(":memory:")
        init_odds_history_table(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='odds_history'"
        )
        assert cur.fetchone() is not None
        conn.close()

    def test_persist_and_load(self):
        conn = sqlite3.connect(":memory:")
        init_odds_history_table(conn)
        snap = _snap()
        persist_snapshot(conn, snap)

        loaded = load_history_from_db(conn, snap.game_id)
        assert len(loaded) == 1
        s = loaded[0]
        assert s.game_id == snap.game_id
        assert s.home_team == snap.home_team
        assert s.away_team == snap.away_team
        assert s.sportsbook == snap.sportsbook
        assert s.home_odds == snap.home_odds
        assert s.away_odds == snap.away_odds
        conn.close()

    def test_load_populates_in_memory_store(self):
        conn = sqlite3.connect(":memory:")
        init_odds_history_table(conn)
        snap = _snap(game_id="TEST-GAME-2026-03-05T19:00:00")
        persist_snapshot(conn, snap)

        # In-memory store is cleared by the autouse fixture
        assert get_history(snap.game_id) == []

        load_history_from_db(conn, snap.game_id)
        # Now the in-memory store should have the loaded snap
        assert len(get_history(snap.game_id)) == 1
        conn.close()

    def test_persist_multiple_snapshots(self):
        conn = sqlite3.connect(":memory:")
        init_odds_history_table(conn)
        for book in ["Bet365", "Betway", "Pinnacle"]:
            snap = _snap(sportsbook=book)
            persist_snapshot(conn, snap)
        cur = conn.execute("SELECT COUNT(*) FROM odds_history")
        assert cur.fetchone()[0] == 3
        conn.close()
