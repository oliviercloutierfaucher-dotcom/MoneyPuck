"""Line movement tracking — records odds snapshots over time and exposes
consensus history for sparkline charts in the dashboard.

In-memory store keyed by game_id.  Optional SQLite persistence via the
existing TrackerDatabase-style schema (odds_history table).
"""
from __future__ import annotations

import random
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.logging_config import get_logger

log = get_logger("odds_history")

# ---------------------------------------------------------------------------
# In-memory store  (module-level singleton)
# ---------------------------------------------------------------------------

# game_id -> list of OddsSnapshot, ordered by insertion time
_store: dict[str, list["OddsSnapshot"]] = defaultdict(list)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class OddsSnapshot:
    """A single point-in-time snapshot of odds for one sportsbook on one game."""

    game_id: str
    home_team: str
    away_team: str
    sportsbook: str
    home_odds: int          # American odds
    away_odds: int          # American odds
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Derived convenience properties
    @property
    def home_implied(self) -> float:
        """Implied probability for home team (no vig removal)."""
        return _american_to_implied(self.home_odds)

    @property
    def away_implied(self) -> float:
        """Implied probability for away team (no vig removal)."""
        return _american_to_implied(self.away_odds)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _american_to_implied(odds: int) -> float:
    """Convert American odds integer to raw implied probability."""
    if odds == 0:
        return 0.5
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def make_game_id(home_team: str, away_team: str, commence_time: str) -> str:
    """Create a canonical game_id string.

    Example: ``"TOR-MTL-2026-03-05T19:00:00Z"``
    """
    # Normalise the timestamp portion — keep only the date+time, drop microseconds
    ts = commence_time.split(".")[0] if "." in commence_time else commence_time
    return f"{home_team}-{away_team}-{ts}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_snapshot(snapshot: OddsSnapshot) -> None:
    """Append *snapshot* to the in-memory store for its game_id."""
    _store[snapshot.game_id].append(snapshot)
    log.debug(
        "Recorded snapshot: %s | %s | H:%s A:%s @ %s",
        snapshot.game_id,
        snapshot.sportsbook,
        snapshot.home_odds,
        snapshot.away_odds,
        snapshot.timestamp.isoformat(),
    )


def get_history(game_id: str) -> list[OddsSnapshot]:
    """Return all recorded snapshots for *game_id*, sorted oldest → newest."""
    return sorted(_store.get(game_id, []), key=lambda s: s.timestamp)


def get_consensus_history(game_id: str) -> list[dict[str, Any]]:
    """Return average implied probability across all books at each timestamp.

    Snapshots from the same second (same truncated timestamp) are averaged.
    Returns a list of dicts:
      ``{"time": "HH:MM", "home_implied": float, "away_implied": float,
         "books": {bookname: {"home": int, "away": int}}}``
    """
    history = get_history(game_id)
    if not history:
        return []

    # Group by minute-truncated timestamp so we collapse same-refresh snapshots
    buckets: dict[str, list[OddsSnapshot]] = defaultdict(list)
    for snap in history:
        key = snap.timestamp.strftime("%Y-%m-%dT%H:%M")
        buckets[key].append(snap)

    result: list[dict[str, Any]] = []
    for ts_key in sorted(buckets):
        snaps = buckets[ts_key]
        avg_h = sum(s.home_implied for s in snaps) / len(snaps)
        avg_a = sum(s.away_implied for s in snaps) / len(snaps)
        books_detail = {
            s.sportsbook: {"home": s.home_odds, "away": s.away_odds}
            for s in snaps
        }
        # Format display time as HH:MM
        display_time = ts_key[11:]  # "HH:MM"
        result.append({
            "time": display_time,
            "home_implied": round(avg_h, 4),
            "away_implied": round(avg_a, 4),
            "books": books_detail,
        })

    return result


def build_history_response(game_id: str) -> dict[str, Any]:
    """Build the full JSON response for ``/api/odds-history?game_id=...``.

    Includes opening odds, current odds, and net movement.
    """
    consensus = get_consensus_history(game_id)
    if not consensus:
        return {
            "game_id": game_id,
            "snapshots": [],
            "opening": None,
            "current": None,
            "movement": None,
        }

    opening = consensus[0]
    current = consensus[-1]
    return {
        "game_id": game_id,
        "snapshots": consensus,
        "opening": {
            "home_implied": opening["home_implied"],
            "away_implied": opening["away_implied"],
        },
        "current": {
            "home_implied": current["home_implied"],
            "away_implied": current["away_implied"],
        },
        "movement": {
            "home_shift": round(current["home_implied"] - opening["home_implied"], 4),
            "away_shift": round(current["away_implied"] - opening["away_implied"], 4),
        },
    }


def clear_history(game_id: str | None = None) -> None:
    """Clear history for a specific game, or all games if *game_id* is None."""
    if game_id is None:
        _store.clear()
    else:
        _store.pop(game_id, None)


# ---------------------------------------------------------------------------
# Demo sparkline data generation
# ---------------------------------------------------------------------------

def generate_demo_sparkline(
    game_id: str,
    home_team: str,
    away_team: str,
    current_home_prob: float,
    n_points: int = 5,
) -> list[dict[str, Any]]:
    """Generate fake sparkline data for demo mode.

    Produces *n_points* data points with a slight random walk ending at
    *current_home_prob*.  Uses the game_id as the random seed so the result
    is deterministic across page refreshes.
    """
    rng = random.Random(hash(game_id + "sparkline"))
    # Walk backward from current to generate opening
    points: list[float] = [current_home_prob]
    for _ in range(n_points - 1):
        step = rng.gauss(0, 0.012)
        prev = max(0.05, min(0.95, points[0] - step))
        points.insert(0, prev)

    # Build fake hourly timestamps
    result: list[dict[str, Any]] = []
    for i, prob in enumerate(points):
        hour = 10 + i * 2  # 10:00, 12:00, 14:00, 16:00, 18:00
        result.append({
            "time": f"{hour:02d}:00",
            "home_implied": round(prob, 4),
            "away_implied": round(1.0 - prob, 4),
            "books": {},
        })
    return result


def record_snapshots_from_dashboard(
    games: list[dict[str, Any]],
) -> None:
    """Record one OddsSnapshot per book per game from the dashboard data dict.

    Called each time ``/api/dashboard`` is fetched in live mode.  Each game
    dict should have keys: ``home``, ``away``, ``commence``, ``books`` (list).
    """
    for g in games:
        home = g.get("home", "")
        away = g.get("away", "")
        commence = g.get("commence", "")
        if not home or not away:
            continue
        gid = make_game_id(home, away, commence)
        for book in g.get("books", []):
            h_odds = book.get("home_odds", 0)
            a_odds = book.get("away_odds", 0)
            if not h_odds or not a_odds:
                continue
            snap = OddsSnapshot(
                game_id=gid,
                home_team=home,
                away_team=away,
                sportsbook=book.get("name", "Unknown"),
                home_odds=int(h_odds),
                away_odds=int(a_odds),
            )
            record_snapshot(snap)


# ---------------------------------------------------------------------------
# Optional SQLite persistence
# ---------------------------------------------------------------------------

_ODDS_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS odds_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     TEXT    NOT NULL,
    home_team   TEXT    NOT NULL,
    away_team   TEXT    NOT NULL,
    sportsbook  TEXT    NOT NULL,
    home_odds   INTEGER NOT NULL,
    away_odds   INTEGER NOT NULL,
    recorded_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_odds_history_game
    ON odds_history (game_id, recorded_at);
"""


def init_odds_history_table(conn: sqlite3.Connection) -> None:
    """Create the odds_history table in an existing SQLite connection."""
    conn.executescript(_ODDS_HISTORY_SCHEMA)
    conn.commit()


def persist_snapshot(conn: sqlite3.Connection, snapshot: OddsSnapshot) -> None:
    """Write a single OddsSnapshot to the SQLite odds_history table."""
    conn.execute(
        """
        INSERT INTO odds_history
            (game_id, home_team, away_team, sportsbook, home_odds, away_odds, recorded_at)
        VALUES
            (:game_id, :home_team, :away_team, :sportsbook, :home_odds, :away_odds, :recorded_at)
        """,
        {
            "game_id": snapshot.game_id,
            "home_team": snapshot.home_team,
            "away_team": snapshot.away_team,
            "sportsbook": snapshot.sportsbook,
            "home_odds": snapshot.home_odds,
            "away_odds": snapshot.away_odds,
            "recorded_at": snapshot.timestamp.isoformat(),
        },
    )
    conn.commit()


def load_history_from_db(
    conn: sqlite3.Connection, game_id: str
) -> list[OddsSnapshot]:
    """Load snapshots for *game_id* from SQLite into the in-memory store."""
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM odds_history WHERE game_id = ? ORDER BY recorded_at",
        (game_id,),
    )
    snapshots: list[OddsSnapshot] = []
    for row in cur.fetchall():
        ts_str = row["recorded_at"]
        # Parse ISO timestamp — handle both with and without timezone
        try:
            if ts_str.endswith("Z"):
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            elif "+" in ts_str or ts_str.endswith("00:00"):
                ts = datetime.fromisoformat(ts_str)
            else:
                ts = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        snap = OddsSnapshot(
            game_id=row["game_id"],
            home_team=row["home_team"],
            away_team=row["away_team"],
            sportsbook=row["sportsbook"],
            home_odds=row["home_odds"],
            away_odds=row["away_odds"],
            timestamp=ts,
        )
        snapshots.append(snap)
        # Also populate the in-memory store
        _store[game_id].append(snap)
    return snapshots
