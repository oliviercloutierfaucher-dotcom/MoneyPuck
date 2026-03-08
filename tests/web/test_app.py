"""FastAPI TestClient tests for the MoneyPuck Edge Intelligence dashboard."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.web.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

def test_dashboard_page_returns_html():
    resp = client.get("/?demo=1")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "MoneyPuck Edge Intelligence" in resp.text


def test_index_html_alias():
    resp = client.get("/index.html?demo=1")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# JSON API routes
# ---------------------------------------------------------------------------

def test_api_dashboard_returns_json():
    resp = client.get("/api/dashboard?demo=1")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("games", "value_bets", "books", "mode"):
        assert key in data


def test_api_dashboard_demo_has_games():
    resp = client.get("/api/dashboard?demo=1")
    data = resp.json()
    assert len(data["games"]) > 0
    game = data["games"][0]
    assert "home" in game
    assert "away" in game
    assert "books" in game


def test_api_dashboard_demo_has_quebec_books():
    resp = client.get("/api/dashboard?demo=1")
    data = resp.json()
    book_names = data["books"]
    for expected in ("Bet365", "Betway", "Bet99", "FanDuel", "Mise-o-jeu"):
        assert expected in book_names


def test_api_performance_returns_json():
    resp = client.get("/api/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_bets" in data


def test_api_opportunities_returns_json():
    resp = client.get("/api/opportunities?demo=1")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_api_odds_history_requires_game_id():
    resp = client.get("/api/odds-history")
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"] == "game_id parameter required"


def test_api_odds_history_demo_mode():
    resp = client.get("/api/odds-history?game_id=MTL-TOR-2026-01-01&demo=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshots" in data


# ---------------------------------------------------------------------------
# Security & error handling
# ---------------------------------------------------------------------------

def test_security_headers():
    resp = client.get("/?demo=1")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "DENY" in resp.headers.get("X-Frame-Options", "")
    assert resp.headers.get("Content-Security-Policy") is not None
    assert resp.headers.get("Referrer-Policy") is not None


def test_404_returns_json():
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
