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

from app.logging_config import get_logger

log = get_logger("data_sources")

ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds"
MONEYPUCK_BASE = "https://moneypuck.com/moneypuck/playerData/games.csv"
MONEYPUCK_TEAM_GAME_BASE = "https://moneypuck.com/moneypuck/playerData/teamGameByGame"

# ---------------------------------------------------------------------------
# Quebec & Canadian sportsbook configuration
# Maps The Odds API bookmaker keys to display names
# ---------------------------------------------------------------------------

QUEBEC_BOOKS: dict[str, str] = {
    "bet365": "Bet365",
    "betway": "Betway",
    "bet99": "Bet99",
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "pinnacle": "Pinnacle",
    "betvictor": "BetVictor",
    "pointsbetus": "PointsBet",
    "betrivers": "BetRivers",
    "betano": "Betano",
    "northstar": "NorthStar",
    "espacejeuxca": "Mise-o-jeu",
}

ONTARIO_BOOKS: dict[str, str] = {
    **QUEBEC_BOOKS,
    "williamhill": "William Hill",
    "unibet": "Unibet",
    "theScore": "theScore Bet",
    "coolbet": "Coolbet",
    "888sport": "888sport",
}

US_BOOKS: dict[str, str] = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "pointsbetus": "PointsBet",
    "betrivers": "BetRivers",
    "unibet": "Unibet",
    "williamhill": "William Hill",
    "wynnbet": "WynnBET",
    "twinspires": "TwinSpires",
}

REGION_BOOK_PRESETS: dict[str, dict[str, str]] = {
    "qc": QUEBEC_BOOKS,
    "on": ONTARIO_BOOKS,
    "ca": QUEBEC_BOOKS,  # Default Canadian to QC books
    "us": US_BOOKS,
}


def get_books_for_region(region: str) -> dict[str, str]:
    """Return bookmaker key -> display name mapping for a region."""
    return REGION_BOOK_PRESETS.get(region, QUEBEC_BOOKS)


# ---------------------------------------------------------------------------
# Odds API full team name → 3-letter code mapping
# ---------------------------------------------------------------------------

TEAM_NAME_TO_CODE: dict[str, str] = {
    "Anaheim Ducks": "ANA",
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN",
    "Montreal Canadiens": "MTL",
    "Montréal Canadiens": "MTL",
    "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St Louis Blues": "STL",
    "St. Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Utah Hockey Club": "UTA",
    "Utah Mammoth": "UTA",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}

TEAM_CODE_TO_NAME: dict[str, str] = {v: k for k, v in TEAM_NAME_TO_CODE.items()}


def team_code(name_or_code: str) -> str:
    """Convert a full team name or 3-letter code to a 3-letter code."""
    if len(name_or_code) <= 3:
        return name_or_code.upper()
    return TEAM_NAME_TO_CODE.get(name_or_code, name_or_code)


# All 32 NHL teams (2024-25 onward, UTA replaced ARI)
NHL_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL",
    "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NJD",
    "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA", "SJS",
    "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH",
]

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
            from urllib.request import Request
            req = Request(url, headers={"User-Agent": "MoneyPuck/1.0"})
            with urlopen(req, timeout=timeout) as response:  # nosec B310
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
        "markets": "h2h,spreads,totals",
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


# ---------------------------------------------------------------------------
# Polymarket integration
# ---------------------------------------------------------------------------

POLYMARKET_GAMMA_BASE = "https://gamma-api.polymarket.com"
POLYMARKET_NHL_SERIES_ID = "10346"

# Polymarket uses short team names — map to 3-letter NHL codes
_POLYMARKET_NAME_TO_CODE: dict[str, str] = {
    "Ducks": "ANA",
    "Bruins": "BOS",
    "Sabres": "BUF",
    "Flames": "CGY",
    "Hurricanes": "CAR",
    "Blackhawks": "CHI",
    "Avalanche": "COL",
    "Blue Jackets": "CBJ",
    "Stars": "DAL",
    "Red Wings": "DET",
    "Oilers": "EDM",
    "Panthers": "FLA",
    "Kings": "LAK",
    "Wild": "MIN",
    "Canadiens": "MTL",
    "Predators": "NSH",
    "Devils": "NJD",
    "Islanders": "NYI",
    "Rangers": "NYR",
    "Senators": "OTT",
    "Flyers": "PHI",
    "Penguins": "PIT",
    "Sharks": "SJS",
    "Kraken": "SEA",
    "Blues": "STL",
    "Lightning": "TBL",
    "Maple Leafs": "TOR",
    "Utah": "UTA",
    "Canucks": "VAN",
    "Golden Knights": "VGK",
    "Capitals": "WSH",
    "Jets": "WPG",
}


def _probability_to_american(prob: float) -> int:
    """Convert 0-1 probability to American odds."""
    if prob <= 0.0 or prob >= 1.0:
        return 0
    if prob >= 0.5:
        return int(round(-(prob / (1.0 - prob)) * 100))
    return int(round(((1.0 - prob) / prob) * 100))


def fetch_polymarket_odds() -> list[dict[str, Any]]:
    """Fetch NHL moneyline odds from Polymarket's Gamma API.

    Returns data in the same format as fetch_odds() (Odds API format)
    so it plugs directly into the EdgeScoringAgent pipeline.

    No auth required — Polymarket's read API is fully public.
    """
    url = (
        f"{POLYMARKET_GAMMA_BASE}/events"
        f"?series_id={POLYMARKET_NHL_SERIES_ID}"
        f"&active=true&closed=false&limit=50"
    )
    try:
        data = _fetch_with_retry(url, label="Polymarket", timeout=15)
        events_raw = json.loads(data.decode("utf-8"))
    except Exception as exc:
        log.warning("Polymarket fetch failed: %s", exc)
        return []

    if not isinstance(events_raw, list):
        log.warning("Polymarket returned unexpected type: %s", type(events_raw).__name__)
        return []

    odds_events: list[dict[str, Any]] = []

    for event in events_raw:
        title = event.get("title", "")
        # Title format: "Away vs. Home" — parse team names
        if " vs. " not in title:
            continue

        markets = event.get("markets", [])

        # Find the moneyline market
        moneyline = None
        for m in markets:
            if m.get("sportsMarketType") == "moneyline":
                moneyline = m
                break

        if moneyline is None:
            continue

        try:
            outcomes = json.loads(moneyline.get("outcomes", "[]"))
            prices = json.loads(moneyline.get("outcomePrices", "[]"))
        except (json.JSONDecodeError, TypeError):
            continue

        if len(outcomes) != 2 or len(prices) != 2:
            continue

        # Map short names to NHL codes
        code_0 = _POLYMARKET_NAME_TO_CODE.get(outcomes[0])
        code_1 = _POLYMARKET_NAME_TO_CODE.get(outcomes[1])
        if not code_0 or not code_1:
            log.debug("Polymarket: unmapped team in %s", title)
            continue

        # Determine home/away from title ("Away vs. Home")
        parts = title.split(" vs. ")
        away_name = parts[0].strip()
        home_name = parts[1].strip()
        home_code = _POLYMARKET_NAME_TO_CODE.get(home_name)
        away_code = _POLYMARKET_NAME_TO_CODE.get(away_name)
        if not home_code or not away_code:
            continue

        # Build outcome prices as American odds
        prob_0 = float(prices[0])
        prob_1 = float(prices[1])

        american_0 = _probability_to_american(prob_0)
        american_1 = _probability_to_american(prob_1)
        if american_0 == 0 or american_1 == 0:
            continue

        # Use gameStartTime or endDate as commence_time
        commence = moneyline.get("gameStartTime", "")
        if not commence:
            commence = moneyline.get("endDate", "")

        # Convert Polymarket event to Odds API format
        odds_event: dict[str, Any] = {
            "id": f"polymarket_{event.get('id', '')}",
            "sport_key": "icehockey_nhl",
            "commence_time": commence,
            "home_team": home_code,
            "away_team": away_code,
            "bookmakers": [
                {
                    "key": "polymarket",
                    "title": "Polymarket",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": home_code, "price": american_0 if code_0 == home_code else american_1},
                                {"name": away_code, "price": american_0 if code_0 == away_code else american_1},
                            ],
                        }
                    ],
                }
            ],
        }
        odds_events.append(odds_event)

    log.info("Fetched %d NHL events from Polymarket", len(odds_events))
    return odds_events


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


def fetch_team_game_by_game(
    season: int,
    teams: list[str] | None = None,
    *,
    fallback_to_bulk: bool = True,
) -> list[dict[str, str]]:
    """Fetch per-team game-by-game data from MoneyPuck with 100+ advanced metrics.

    This endpoint provides score-adjusted xG, flurry-adjusted xG, danger-zone
    breakdowns, rebound control, faceoffs, giveaways/takeaways, and more.

    Falls back to the bulk games.csv if per-team fetches fail (unless
    fallback_to_bulk is False, which is useful for multi-season loading
    where we want to skip unavailable seasons rather than hitting a 403).
    """
    target_teams = teams or NHL_TEAMS
    # MoneyPuck directory year matches the season start year
    # (e.g., 2025 directory = 2025-26 season starting Oct 2025)
    mp_year = season

    all_rows: list[dict[str, str]] = []
    failed_teams: list[str] = []

    for team in target_teams:
        url = f"{MONEYPUCK_TEAM_GAME_BASE}/{mp_year}/regular/{team}.csv"
        try:
            data = _fetch_with_retry(url, label=f"MoneyPuck {team}", timeout=20)
            text = data.decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(text)))
            all_rows.extend(rows)
            log.debug("Fetched %d game rows for %s", len(rows), team)
        except Exception as exc:
            log.warning("Failed to fetch team game data for %s: %s", team, exc)
            failed_teams.append(team)

    if failed_teams:
        log.warning(
            "Failed to fetch %d/%d teams: %s",
            len(failed_teams), len(target_teams), failed_teams,
        )

    if not all_rows:
        if fallback_to_bulk:
            log.warning("No team game-by-game data fetched, falling back to bulk CSV")
            return fetch_moneypuck_games(season)
        else:
            log.warning("No team game-by-game data fetched for season %d (no bulk fallback)", season)
            return []

    log.info(
        "Loaded %d team-game rows across %d teams (season %d)",
        len(all_rows), len(target_teams) - len(failed_teams), season,
    )
    return all_rows
