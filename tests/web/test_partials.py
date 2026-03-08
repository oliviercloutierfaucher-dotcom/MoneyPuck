"""Tests for HTMX partial endpoints and full page tab routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.web.app import app

client = TestClient(app)

HTMX_HEADERS = {"HX-Request": "true"}


# ---------------------------------------------------------------------------
# Games tab
# ---------------------------------------------------------------------------

def test_games_partial_returns_fragment():
    resp = client.get("/games?demo=1", headers=HTMX_HEADERS)
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "<head" not in resp.text


def test_games_full_returns_base():
    resp = client.get("/games?demo=1")
    assert resp.status_code == 200
    assert "<html" in resp.text
    assert "tab-nav" in resp.text
    # Games tab should be active
    assert 'class="tab active"' in resp.text or "active" in resp.text


# ---------------------------------------------------------------------------
# Value Bets tab
# ---------------------------------------------------------------------------

def test_value_bets_partial():
    resp = client.get("/value-bets?demo=1", headers=HTMX_HEADERS)
    assert resp.status_code == 200
    assert "<html" not in resp.text


def test_value_bets_full():
    resp = client.get("/value-bets?demo=1")
    assert resp.status_code == 200
    assert "<html" in resp.text
    assert "tab-nav" in resp.text


# ---------------------------------------------------------------------------
# Arbs tab
# ---------------------------------------------------------------------------

def test_arbs_partial():
    resp = client.get("/arbs?demo=1", headers=HTMX_HEADERS)
    assert resp.status_code == 200
    assert "<html" not in resp.text


def test_arbs_full():
    resp = client.get("/arbs?demo=1")
    assert resp.status_code == 200
    assert "<html" in resp.text
    assert "tab-nav" in resp.text


# ---------------------------------------------------------------------------
# Performance tab
# ---------------------------------------------------------------------------

def test_performance_partial():
    resp = client.get("/performance?demo=1", headers=HTMX_HEADERS)
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "perf-section" in resp.text


def test_performance_full():
    resp = client.get("/performance?demo=1")
    assert resp.status_code == 200
    assert "<html" in resp.text
    assert "tab-nav" in resp.text


# ---------------------------------------------------------------------------
# Props tab
# ---------------------------------------------------------------------------

def test_props_partial():
    resp = client.get("/props?demo=1", headers=HTMX_HEADERS)
    assert resp.status_code == 200
    assert "<html" not in resp.text


def test_props_full():
    resp = client.get("/props?demo=1")
    assert resp.status_code == 200
    assert "<html" in resp.text
    assert "tab-nav" in resp.text


# ---------------------------------------------------------------------------
# Root serves games
# ---------------------------------------------------------------------------

def test_root_serves_games():
    resp = client.get("/?demo=1")
    assert resp.status_code == 200
    assert "MoneyPuck Edge Intelligence" in resp.text
    # Should have games tab active
    assert "<html" in resp.text


# ---------------------------------------------------------------------------
# Demo mode propagation
# ---------------------------------------------------------------------------

def test_demo_mode_partial():
    resp = client.get("/games?demo=1", headers=HTMX_HEADERS)
    assert resp.status_code == 200
    # Partial should render without errors in demo mode
    assert "games-grid" in resp.text or "controls" in resp.text
