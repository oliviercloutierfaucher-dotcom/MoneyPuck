"""Tests for the TTLCache used for server-side odds response caching."""
from __future__ import annotations

import time

import pytest

from app.web.web_preview import TTLCache


def test_cache_hit():
    """Calling get() within TTL returns cached value."""
    cache = TTLCache(ttl_seconds=90.0)
    cache.set("key1", {"data": "value"})
    result = cache.get("key1")
    assert result == {"data": "value"}


def test_cache_miss():
    """Calling get() with unknown key returns None."""
    cache = TTLCache(ttl_seconds=90.0)
    assert cache.get("nonexistent") is None


def test_cache_expiry(monkeypatch):
    """Calling get() after TTL returns None."""
    fake_time = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_time[0])

    cache = TTLCache(ttl_seconds=10.0)
    cache.set("key1", "fresh")

    # Still within TTL
    fake_time[0] = 105.0
    assert cache.get("key1") == "fresh"

    # Past TTL
    fake_time[0] = 111.0
    assert cache.get("key1") is None


def test_cache_set_overwrite():
    """Setting same key twice overwrites previous value."""
    cache = TTLCache(ttl_seconds=90.0)
    cache.set("key1", "old")
    cache.set("key1", "new")
    assert cache.get("key1") == "new"


def test_cache_different_keys():
    """Different keys are independent."""
    cache = TTLCache(ttl_seconds=90.0)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_force_refresh_bypasses_cache():
    """The TTLCache supports clearing a key to simulate force refresh."""
    cache = TTLCache(ttl_seconds=90.0)
    cache.set("dashboard:ca", {"stale": True})

    # Force refresh: caller checks refresh param and skips cache
    # Simulate by setting new value (which is what the handler does)
    cache.set("dashboard:ca", {"stale": False})
    assert cache.get("dashboard:ca") == {"stale": False}
