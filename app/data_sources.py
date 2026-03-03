from __future__ import annotations

import csv
import io
import json
import math
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .logging_config import get_logger

log = get_logger("data_sources")

ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds"
MONEYPUCK_BASE = "https://moneypuck.com/moneypuck/playerData/games.csv"

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds


def _fetch_with_retry(url: str, timeout: int = 30, label: str = "API") -> bytes:
    """Fetch URL content with retry logic and exponential backoff.

    Retries on transient network errors and HTTP 429/5xx responses.
    Raises the final exception after all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.debug("Fetching %s (attempt %d/%d)", label, attempt, MAX_RETRIES)
            with urlopen(url, timeout=timeout) as response:  # nosec B310
                data = response.read()
                log.debug("%s fetch succeeded (%d bytes)", label, len(data))
                return data
        except HTTPError as exc:
            last_exc = exc
            if exc.code == 429:
                wait = RETRY_BACKOFF_BASE ** attempt
                log.warning(
                    "%s rate-limited (429), retrying in %ds (attempt %d/%d)",
                    label, wait, attempt, MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            if exc.code >= 500:
                wait = RETRY_BACKOFF_BASE ** attempt
                log.warning(
                    "%s server error (%d), retrying in %ds (attempt %d/%d)",
                    label, exc.code, wait, attempt, MAX_RETRIES,
                )
                time.sleep(wait)
                continue
            # Client errors (400, 401, 403, etc.) are not retryable
            log.error("%s HTTP error %d: %s", label, exc.code, exc.reason)
            raise
        except (URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE ** attempt
                log.warning(
                    "%s network error: %s, retrying in %ds (attempt %d/%d)",
                    label, exc, wait, attempt, MAX_RETRIES,
                )
                time.sleep(wait)
            else:
                log.error("%s failed after %d attempts: %s", label, MAX_RETRIES, exc)

    raise last_exc  # type: ignore[misc]


def fetch_odds(api_key: str, region: str, bookmakers: str | None) -> list[dict[str, Any]]:
    """Fetch live moneyline odds from The Odds API."""
    if not api_key or not api_key.strip():
        raise ValueError("Odds API key must not be empty")

    params = {
        "apiKey": api_key,
        "regions": region,
        "markets": "h2h",
        "oddsFormat": "american",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers

    url = f"{ODDS_API_BASE}?{urlencode(params)}"
    log.info("Fetching odds for region=%s, bookmakers=%s", region, bookmakers or "all")
    data = _fetch_with_retry(url, label="Odds API")
    events = json.loads(data.decode("utf-8"))

    if not isinstance(events, list):
        log.error("Odds API returned unexpected type: %s", type(events).__name__)
        raise ValueError("Odds API returned unexpected response format")

    log.info("Received %d events from Odds API", len(events))
    return events


REQUIRED_COLUMNS = {
    "season",
    "homeTeamCode",
    "awayTeamCode",
    "xGoalsPercentage",
}

DESIRED_COLUMNS = REQUIRED_COLUMNS | {
    "gameDate",
    "gameId",
    "home_or_away",
    "situation",
    "iceTime",
    "corsiPercentage",
    "fenwickPercentage",
    "highDangerShotsFor",
    "highDangerShotsAgainst",
    "goalsFor",
    "goalsAgainst",
    "shotsOnGoalFor",
    "shotsOnGoalAgainst",
    "xGoalsFor",
    "xGoalsAgainst",
    "penaltiesFor",
    "penaltiesAgainst",
}


def safe_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    """Extract a float from a CSV row with safe fallback."""
    try:
        val = float(row[key])
        if not math.isfinite(val):
            return default
        return val
    except (KeyError, ValueError, TypeError):
        return default


def _safe_int(value: str, default: int) -> int:
    """Safely convert a string to int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def fetch_moneypuck_games(season: int) -> list[dict[str, str]]:
    """Fetch game-level xG data from MoneyPuck CSV."""
    log.info("Fetching MoneyPuck games for season %d", season)
    data = _fetch_with_retry(MONEYPUCK_BASE, label="MoneyPuck CSV")
    text = data.decode("utf-8")

    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        log.warning("MoneyPuck CSV returned 0 rows")
        return []

    available = set(rows[0].keys())
    missing = REQUIRED_COLUMNS - available
    if missing:
        raise ValueError(f"MoneyPuck schema missing required columns: {sorted(missing)}")

    filtered = [row for row in rows if _safe_int(row.get("season", ""), 0) == season]
    log.info("Loaded %d games for season %d (from %d total rows)", len(filtered), season, len(rows))
    return filtered
