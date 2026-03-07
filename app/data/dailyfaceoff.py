"""DailyFaceoff starting goalie scraper.

Fetches confirmed starting goalie data from DailyFaceoff's starting-goalies
page by extracting the embedded __NEXT_DATA__ JSON. This provides pre-game
confirmation status (Confirmed/Likely/Unconfirmed) that the NHL API does not.

All functions are resilient -- they return empty collections on failure and
never propagate exceptions.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.request import Request, urlopen

from app.logging_config import get_logger

log = get_logger("dailyfaceoff")

# DailyFaceoff team slugs to NHL three-letter abbreviations
SLUG_TO_ABBREV: dict[str, str] = {
    "anaheim-ducks": "ANA",
    "boston-bruins": "BOS",
    "buffalo-sabres": "BUF",
    "calgary-flames": "CGY",
    "carolina-hurricanes": "CAR",
    "chicago-blackhawks": "CHI",
    "colorado-avalanche": "COL",
    "columbus-blue-jackets": "CBJ",
    "dallas-stars": "DAL",
    "detroit-red-wings": "DET",
    "edmonton-oilers": "EDM",
    "florida-panthers": "FLA",
    "los-angeles-kings": "LAK",
    "minnesota-wild": "MIN",
    "montreal-canadiens": "MTL",
    "nashville-predators": "NSH",
    "new-jersey-devils": "NJD",
    "new-york-islanders": "NYI",
    "new-york-rangers": "NYR",
    "ottawa-senators": "OTT",
    "philadelphia-flyers": "PHI",
    "pittsburgh-penguins": "PIT",
    "san-jose-sharks": "SJS",
    "seattle-kraken": "SEA",
    "st-louis-blues": "STL",
    "tampa-bay-lightning": "TBL",
    "toronto-maple-leafs": "TOR",
    "utah-hockey-club": "UTA",
    "vancouver-canucks": "VAN",
    "vegas-golden-knights": "VGK",
    "washington-capitals": "WSH",
    "winnipeg-jets": "WPG",
}


def _status_label(strength_name: str | None) -> str:
    """Map DailyFaceoff confirmation status to normalized label."""
    if strength_name == "Confirmed":
        return "confirmed"
    elif strength_name == "Likely":
        return "likely"
    return "unconfirmed"


def fetch_dailyfaceoff_starters(date_str: str) -> list[dict[str, Any]]:
    """Fetch confirmed starters from DailyFaceoff for a given date.

    Parameters
    ----------
    date_str : str
        Date in YYYY-MM-DD format.

    Returns
    -------
    list[dict]
        List of dicts with keys: home_goalie, away_goalie, home_status,
        away_status, home_save_pct, away_save_pct, home_team, away_team.
        Returns empty list on any failure.
    """
    url = f"https://www.dailyfaceoff.com/starting-goalies/{date_str}"
    try:
        req = Request(url, headers={"User-Agent": "MoneyPuck/1.0"})
        with urlopen(req, timeout=15) as resp:  # nosec B310
            html = resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        log.warning("DailyFaceoff fetch failed: %s", exc)
        return []

    # Extract __NEXT_DATA__ JSON
    match = re.search(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        log.warning("DailyFaceoff: __NEXT_DATA__ not found in page")
        return []

    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("DailyFaceoff: failed to parse __NEXT_DATA__ JSON: %s", exc)
        return []

    games = data.get("props", {}).get("pageProps", {}).get("data", [])
    if not isinstance(games, list):
        log.warning("DailyFaceoff: unexpected data structure (not a list)")
        return []

    starters: list[dict[str, Any]] = []
    for game in games:
        if not isinstance(game, dict):
            continue
        home_slug = game.get("homeTeamSlug", "")
        away_slug = game.get("awayTeamSlug", "")
        home_team = SLUG_TO_ABBREV.get(home_slug, home_slug)
        away_team = SLUG_TO_ABBREV.get(away_slug, away_slug)

        starters.append({
            "home_goalie": game.get("homeGoalieName"),
            "away_goalie": game.get("awayGoalieName"),
            "home_status": _status_label(game.get("homeNewsStrengthName")),
            "away_status": _status_label(game.get("awayNewsStrengthName")),
            "home_save_pct": game.get("homeGoalieSavePercentage"),
            "away_save_pct": game.get("awayGoalieSavePercentage"),
            "home_team": home_team,
            "away_team": away_team,
        })

    log.info("DailyFaceoff: parsed %d games for %s", len(starters), date_str)
    return starters
