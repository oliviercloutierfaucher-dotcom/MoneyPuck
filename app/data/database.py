"""Phase 4: SQLite persistence layer for prediction tracking."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from app.logging_config import get_logger

log = get_logger("database")

def _resolve_db_path() -> Path:
    """Resolve database path with 3-tier priority.

    1. RAILWAY_VOLUME_MOUNT_PATH (auto-set by Railway when volume attached)
    2. MONEYPUCK_DB_PATH (explicit override)
    3. ~/.moneypuck/tracker.db (local dev fallback)
    """
    railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_mount:
        path = Path(railway_mount) / "tracker.db"
        log.info("Using Railway volume: %s", path)
        return path

    explicit = os.getenv("MONEYPUCK_DB_PATH")
    if explicit:
        return Path(explicit)

    return Path.home() / ".moneypuck" / "tracker.db"


DB_PATH = _resolve_db_path()

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS closing_odds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     TEXT    NOT NULL,
    home_team   TEXT    NOT NULL,
    away_team   TEXT    NOT NULL,
    sportsbook  TEXT    NOT NULL,
    market      TEXT    DEFAULT 'ML',
    home_odds   INTEGER,
    away_odds   INTEGER,
    captured_at TEXT    NOT NULL,
    UNIQUE(game_id, sportsbook, market)
);

CREATE INDEX IF NOT EXISTS idx_closing_odds_game
    ON closing_odds (game_id);

CREATE TABLE IF NOT EXISTS predictions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at          TEXT    DEFAULT (datetime('now')),
    game_id             TEXT,
    commence_time       TEXT,
    home_team           TEXT,
    away_team           TEXT,
    side                TEXT,
    sportsbook          TEXT,
    american_odds       INTEGER,
    decimal_odds        REAL,
    implied_probability REAL,
    model_probability   REAL,
    model_confidence    REAL,
    edge_pp             REAL,
    ev_per_dollar       REAL,
    kelly_fraction      REAL,
    recommended_stake   REAL,
    profile             TEXT    DEFAULT 'default',
    outcome             TEXT,
    closing_odds        INTEGER,
    profit_loss         REAL,
    settled_at          TEXT
);

CREATE TABLE IF NOT EXISTS model_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at            TEXT    DEFAULT (datetime('now')),
    profile           TEXT,
    config_json       TEXT,
    total_candidates  INTEGER,
    total_stake       REAL,
    avg_edge          REAL,
    avg_ev            REAL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_unique
    ON predictions (commence_time, home_team, away_team, side, sportsbook, profile);

CREATE INDEX IF NOT EXISTS idx_predictions_game
    ON predictions (commence_time, home_team, away_team);

CREATE INDEX IF NOT EXISTS idx_predictions_outcome
    ON predictions (outcome);

CREATE INDEX IF NOT EXISTS idx_predictions_profile
    ON predictions (profile);
"""


class TrackerDatabase:
    """SQLite-backed store for predictions and model run summaries."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        log.debug("Opening database at %s", self._db_path)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "TrackerDatabase":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_schema(self) -> None:
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_prediction(
        self, recommendation: dict[str, Any], profile: str = "default"
    ) -> int:
        """Persist a recommendation dict produced by RiskAgent.

        The dict must contain:
        - ``"candidate"``: a ``ValueCandidate`` instance
        - ``"recommended_stake"``: float
        - ``"stake_fraction"``: float (used as kelly_fraction column value)
        """
        candidate = recommendation["candidate"]
        stake = recommendation["recommended_stake"]
        stake_fraction = recommendation["stake_fraction"]

        # Build a synthetic game_id from commence_time + teams so that
        # unsettlement queries can group by game without an external ID.
        game_id = (
            f"{candidate.commence_time_utc}|"
            f"{candidate.home_team}|"
            f"{candidate.away_team}"
        )

        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO predictions (
                game_id, commence_time, home_team, away_team,
                side, sportsbook,
                american_odds, decimal_odds,
                implied_probability, model_probability, model_confidence,
                edge_pp, ev_per_dollar, kelly_fraction,
                recommended_stake, profile
            ) VALUES (
                :game_id, :commence_time, :home_team, :away_team,
                :side, :sportsbook,
                :american_odds, :decimal_odds,
                :implied_probability, :model_probability, :model_confidence,
                :edge_pp, :ev_per_dollar, :kelly_fraction,
                :recommended_stake, :profile
            )
            """,
            {
                "game_id": game_id,
                "commence_time": candidate.commence_time_utc,
                "home_team": candidate.home_team,
                "away_team": candidate.away_team,
                "side": candidate.side,
                "sportsbook": candidate.sportsbook,
                "american_odds": candidate.american_odds,
                "decimal_odds": candidate.decimal_odds,
                "implied_probability": candidate.implied_probability,
                "model_probability": candidate.model_probability,
                "model_confidence": candidate.confidence,
                "edge_pp": candidate.edge_probability_points,
                "ev_per_dollar": candidate.expected_value_per_dollar,
                "kelly_fraction": stake_fraction,
                "recommended_stake": stake,
                "profile": profile,
            },
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def save_run(
        self,
        profile: str,
        config_json: str,
        total_candidates: int,
        total_stake: float,
        avg_edge: float,
        avg_ev: float,
    ) -> int:
        """Persist a model-run summary row."""
        cur = self._conn.execute(
            """
            INSERT INTO model_runs
                (profile, config_json, total_candidates, total_stake, avg_edge, avg_ev)
            VALUES
                (:profile, :config_json, :total_candidates, :total_stake, :avg_edge, :avg_ev)
            """,
            {
                "profile": profile,
                "config_json": config_json,
                "total_candidates": total_candidates,
                "total_stake": total_stake,
                "avg_edge": avg_edge,
                "avg_ev": avg_ev,
            },
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_unsettled(self) -> list[dict[str, Any]]:
        """Return all predictions that have not yet been settled."""
        cur = self._conn.execute(
            "SELECT * FROM predictions WHERE outcome IS NULL ORDER BY commence_time"
        )
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def settle(
        self,
        prediction_id: int,
        outcome: str,
        closing_odds: int | None,
        profit_loss: float,
        auto_commit: bool = True,
    ) -> None:
        """Mark a prediction as settled with its outcome and P&L.

        Set *auto_commit* to ``False`` when calling inside an explicit
        transaction (the caller is responsible for commit/rollback).
        """
        if outcome not in {"win", "loss", "push", "void"}:
            raise ValueError(f"Invalid outcome '{outcome}'. Must be 'win', 'loss', 'push', or 'void'.")
        self._conn.execute(
            """
            UPDATE predictions
            SET outcome    = :outcome,
                closing_odds = :closing_odds,
                profit_loss  = :profit_loss,
                settled_at   = datetime('now')
            WHERE id = :id
            """,
            {
                "id": prediction_id,
                "outcome": outcome,
                "closing_odds": closing_odds,
                "profit_loss": profit_loss,
            },
        )
        if auto_commit:
            self._conn.commit()

    def get_predictions(
        self,
        profile: str | None = None,
        days_back: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return predictions, optionally filtered by profile and recency."""
        clauses: list[str] = []
        params: dict[str, Any] = {}

        if profile is not None:
            clauses.append("profile = :profile")
            params["profile"] = profile

        if days_back is not None:
            clauses.append(
                "created_at >= datetime('now', :days_offset)"
            )
            params["days_offset"] = f"-{days_back} days"

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cur = self._conn.execute(
            f"SELECT * FROM predictions {where} ORDER BY created_at DESC",
            params,
        )
        return [self._row_to_dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Closing odds
    # ------------------------------------------------------------------

    def save_closing_odds(
        self,
        game_id: str,
        home_team: str,
        away_team: str,
        sportsbook: str,
        home_odds: int | None,
        away_odds: int | None,
        market: str = "ML",
    ) -> None:
        """Persist closing-line odds for a game.

        Uses INSERT OR REPLACE so repeated captures (e.g. multiple settlement
        passes) always keep the most recent snapshot.
        """
        self._conn.execute(
            """
            INSERT OR REPLACE INTO closing_odds
                (game_id, home_team, away_team, sportsbook, market,
                 home_odds, away_odds, captured_at)
            VALUES
                (:game_id, :home_team, :away_team, :sportsbook, :market,
                 :home_odds, :away_odds, datetime('now'))
            """,
            {
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "sportsbook": sportsbook,
                "market": market,
                "home_odds": home_odds,
                "away_odds": away_odds,
            },
        )
        self._conn.commit()

    def get_closing_odds(
        self, game_id: str, market: str = "ML"
    ) -> list[dict[str, Any]]:
        """Return all bookmakers' closing odds for a given game and market."""
        cur = self._conn.execute(
            "SELECT * FROM closing_odds WHERE game_id = :game_id AND market = :market",
            {"game_id": game_id, "market": market},
        )
        return [self._row_to_dict(r) for r in cur.fetchall()]

    def get_clv_summary(self) -> dict[str, Any]:
        """Aggregate CLV stats across all settled predictions that have closing odds.

        A prediction must have both ``american_odds`` (placement odds) and
        ``closing_odds`` (the column on the predictions table) to be included.

        Returns a dict with:
        - ``avg_clv_cents``: mean CLV in probability-point cents
        - ``pct_beating_close``: fraction of bets that beat the closing line
        - ``total_bets``: number of bets with CLV data
        - ``clv_by_book``: per-sportsbook breakdown
        """
        from app.core.clv import aggregate_clv

        cur = self._conn.execute(
            """
            SELECT sportsbook, american_odds, closing_odds
            FROM predictions
            WHERE american_odds IS NOT NULL
              AND closing_odds IS NOT NULL
              AND outcome IS NOT NULL
            """
        )
        rows = [self._row_to_dict(r) for r in cur.fetchall()]
        if not rows:
            return {
                "avg_clv_cents": 0.0,
                "pct_beating_close": 0.0,
                "total_bets": 0,
                "clv_by_book": {},
            }
        bets = [
            {
                "sportsbook": r["sportsbook"],
                "placement_odds": r["american_odds"],
                "closing_odds": r["closing_odds"],
            }
            for r in rows
        ]
        return aggregate_clv(bets)

    def close(self) -> None:
        """Close the underlying database connection."""
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass
