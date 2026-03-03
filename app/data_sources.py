from __future__ import annotations

import csv
import io
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds"
MONEYPUCK_BASE = "https://moneypuck.com/moneypuck/playerData/games.csv"


def fetch_odds(api_key: str, region: str, bookmakers: str | None) -> list[dict[str, Any]]:
    params = {
        "apiKey": api_key,
        "regions": region,
        "markets": "h2h",
        "oddsFormat": "american",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers

    url = f"{ODDS_API_BASE}?{urlencode(params)}"
    with urlopen(url, timeout=30) as response:  # nosec B310
        return json.loads(response.read().decode("utf-8"))


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
        return float(row[key])
    except (KeyError, ValueError, TypeError):
        return default


def fetch_moneypuck_games(season: int) -> list[dict[str, str]]:
    with urlopen(MONEYPUCK_BASE, timeout=30) as response:  # nosec B310
        text = response.read().decode("utf-8")

    rows = list(csv.DictReader(io.StringIO(text)))
    available = set(rows[0].keys()) if rows else set()
    missing = REQUIRED_COLUMNS - available
    if missing:
        raise ValueError(f"MoneyPuck schema missing required columns: {sorted(missing)}")

    return [row for row in rows if int(row["season"]) == season]
