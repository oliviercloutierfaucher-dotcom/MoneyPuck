"""Multi-season data loading and historical team code mapping.

Provides infrastructure for loading MoneyPuck data across multiple NHL seasons
(2015+), handling historical team code changes (ARI -> UTA, SEA expansion),
and gracefully skipping seasons where data is unavailable.
"""

from __future__ import annotations

from typing import Any

from app.data.data_sources import NHL_TEAMS, fetch_team_game_by_game
from app.logging_config import get_logger

log = get_logger("multi_season")


# ---------------------------------------------------------------------------
# Historical team code mapping
# ---------------------------------------------------------------------------

# Era boundaries for team code changes affecting 2015+ seasons:
# - Seattle Kraken (SEA) joined the NHL in the 2021-22 season (season=2021)
# - Arizona Coyotes (ARI) became Utah Hockey Club (UTA) in 2024-25 (season=2024)
# - Vegas Golden Knights (VGK) joined in 2017-18 (season=2017)
#   VGK is already in NHL_TEAMS; seasons before 2017 just won't have VGK data

HISTORICAL_TEAMS_BY_ERA: dict[str, dict[str, Any]] = {
    "sea_expansion": {
        "first_season": 2021,
        "team": "SEA",
        "note": "Seattle Kraken expansion team",
    },
    "ari_to_uta": {
        "last_season_as_ari": 2023,
        "old_code": "ARI",
        "new_code": "UTA",
        "note": "Arizona Coyotes relocated to Utah Hockey Club",
    },
    "vgk_expansion": {
        "first_season": 2017,
        "team": "VGK",
        "note": "Vegas Golden Knights expansion team",
    },
}


def get_teams_for_season(season: int) -> list[str]:
    """Return the correct list of NHL team codes for a given season.

    Handles historical changes:
    - Pre-2021: no SEA (Seattle Kraken hadn't joined yet)
    - Pre-2024: ARI instead of UTA (Arizona hadn't relocated yet)
    - Pre-2017: no VGK (Vegas hadn't joined yet)

    Parameters
    ----------
    season : int
        The season start year (e.g., 2024 for the 2024-25 season).

    Returns
    -------
    list[str]
        Sorted list of 3-letter team codes for that season.
    """
    teams = list(NHL_TEAMS)

    # Handle ARI <-> UTA
    if season < 2024:
        if "UTA" in teams:
            teams.remove("UTA")
        if "ARI" not in teams:
            teams.append("ARI")
    # For season >= 2024, UTA is already in NHL_TEAMS and ARI is not

    # Handle SEA expansion
    if season < 2021:
        if "SEA" in teams:
            teams.remove("SEA")

    # Handle VGK expansion
    if season < 2017:
        if "VGK" in teams:
            teams.remove("VGK")

    return sorted(teams)


def load_seasons(
    start_season: int = 2015,
    end_season: int = 2024,
) -> dict[int, list[dict[str, str]]]:
    """Load MoneyPuck game data for multiple seasons.

    For each season in the range [start_season, end_season], fetches per-team
    game-by-game data using the correct team codes for that era. Seasons that
    fail to load (404, network errors) are skipped gracefully.

    Parameters
    ----------
    start_season : int
        First season to load (inclusive).
    end_season : int
        Last season to load (inclusive).

    Returns
    -------
    dict[int, list[dict[str, str]]]
        Mapping of season year -> list of game rows.
    """
    seasons_data: dict[int, list[dict[str, str]]] = {}
    loaded: list[int] = []
    skipped: list[int] = []

    for season in range(start_season, end_season + 1):
        teams = get_teams_for_season(season)
        try:
            rows = fetch_team_game_by_game(season, teams=teams, fallback_to_bulk=False)
            if rows:
                seasons_data[season] = rows
                loaded.append(season)
                log.info("Season %d: loaded %d game rows", season, len(rows))
            else:
                skipped.append(season)
                log.warning("Season %d: no data returned, skipping", season)
        except Exception as exc:
            skipped.append(season)
            log.warning("Season %d: failed to load (%s), skipping", season, exc)

    log.info(
        "Loaded %d seasons: %s, skipped %d: %s",
        len(loaded), loaded, len(skipped), skipped,
    )
    return seasons_data
