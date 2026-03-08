"""Tests for tab URL routing, backward compatibility, and API route integrity."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.web.app import app

client = TestClient(app)

TAB_URLS = ["/games", "/value-bets", "/arbs", "/performance", "/props"]


# ---------------------------------------------------------------------------
# All tab URLs return 200
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", TAB_URLS)
def test_all_tab_urls_return_200(url):
    resp = client.get(f"{url}?demo=1")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Direct navigation has nav tabs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", TAB_URLS)
def test_direct_navigation_has_nav_tabs(url):
    resp = client.get(f"{url}?demo=1")
    assert "tab-nav" in resp.text
    assert "Tonight's Games" in resp.text
    assert "Value Bets" in resp.text
    assert "Arbitrage" in resp.text
    assert "Performance" in resp.text
    assert "Player Props" in resp.text


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

def test_index_html_still_works():
    resp = client.get("/index.html?demo=1")
    assert resp.status_code == 200
    assert "MoneyPuck Edge Intelligence" in resp.text


# ---------------------------------------------------------------------------
# API routes unchanged
# ---------------------------------------------------------------------------

def test_api_dashboard_still_json():
    resp = client.get("/api/dashboard?demo=1")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert "games" in data
    assert "value_bets" in data


def test_api_performance_still_json():
    resp = client.get("/api/performance")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    data = resp.json()
    assert "total_bets" in data


# ---------------------------------------------------------------------------
# HTMX partial returns fragment (no full HTML wrapper)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", TAB_URLS)
def test_htmx_request_returns_fragment(url):
    resp = client.get(f"{url}?demo=1", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "<html" not in resp.text
    assert "<!doctype" not in resp.text.lower()


# ---------------------------------------------------------------------------
# Full page requests have correct active tab
# ---------------------------------------------------------------------------

def test_games_tab_active_on_root():
    resp = client.get("/?demo=1")
    # The games tab link should have 'active' class
    assert 'active' in resp.text


def test_value_bets_tab_active():
    resp = client.get("/value-bets?demo=1")
    # Check that the response contains the value-bets active indicator
    assert 'Value Bets' in resp.text
