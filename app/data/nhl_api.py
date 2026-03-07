"""NHL public API client for live schedule, goalie, and standings data.

This module provides best-effort enrichment data from the NHL's public API
(https://api-web.nhle.com). All functions are resilient -- they return empty
collections or None on failure and never propagate exceptions.

Phase 6 addition to the MoneyPuck betting model pipeline.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.request import Request, urlopen

from app.logging_config import get_logger

log = get_logger("nhl_api")

NHL_API_BASE = "https://api-web.nhle.com/v1"


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _fetch_json(url: str, timeout: int = 15, retries: int = 2) -> dict:
    """Fetch *url* and return parsed JSON as a dict.

    Retries up to *retries* times with 3-second backoff on failure.
    Returns an empty dict on **any** error so callers never need to handle
    exceptions -- this is a best-effort enrichment layer.
    """
    import time

    for attempt in range(1, retries + 2):  # 1-indexed, total = retries + 1
        try:
            req = Request(url, headers={"User-Agent": "MoneyPuck/1.0"})
            with urlopen(req, timeout=timeout) as resp:  # nosec B310
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            if attempt <= retries:
                log.debug("NHL API attempt %d/%d failed for %s: %s", attempt, retries + 1, url, exc)
                time.sleep(3)
            else:
                log.warning("NHL API request failed after %d attempts for %s: %s", attempt, url, exc)
    return {}


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def fetch_schedule(date: str | None = None) -> list[dict[str, Any]]:
    """Fetch the NHL schedule for a given date (YYYY-MM-DD).

    If *date* is ``None`` the current UTC date is used.

    Returns a list of game dicts, each containing at minimum:
        - game_id   (int)
        - home_team (str -- three-letter abbreviation)
        - away_team (str -- three-letter abbreviation)
        - start_time (str -- UTC ISO-8601)
        - game_state (str)
    """
    if date is None:
        from datetime import date as _date
        date = _date.today().isoformat()

    url = f"{NHL_API_BASE}/schedule/{date}"
    data = _fetch_json(url)

    games: list[dict[str, Any]] = []

    for week_entry in data.get("gameWeek", []):
        for game in week_entry.get("games", []):
            home = game.get("homeTeam", {})
            away = game.get("awayTeam", {})
            games.append({
                "game_id": game.get("id", 0),
                "home_team": home.get("abbrev", ""),
                "away_team": away.get("abbrev", ""),
                "start_time": game.get("startTimeUTC", ""),
                "game_state": game.get("gameState", ""),
            })

    return games


def fetch_team_schedule(
    team_code: str,
    season: str = "20242025",
) -> list[dict[str, Any]]:
    """Fetch a team's full season schedule.

    Useful for back-to-back detection with actual NHL data rather than
    inferring from MoneyPuck game dates.

    Returns a list of raw game dicts from the NHL API.  Each dict is
    normalised to include at minimum ``game_id``, ``game_date``,
    ``home_team``, ``away_team``, and ``game_state``.

    Endpoint: ``/v1/club-schedule-season/{team_code}/{season}``
    """
    url = f"{NHL_API_BASE}/club-schedule-season/{team_code}/{season}"
    data = _fetch_json(url)

    games: list[dict[str, Any]] = []
    for game in data.get("games", []):
        home = game.get("homeTeam", {})
        away = game.get("awayTeam", {})
        games.append({
            "game_id": game.get("id", 0),
            "game_date": game.get("gameDate", ""),
            "home_team": home.get("abbrev", ""),
            "away_team": away.get("abbrev", ""),
            "start_time": game.get("startTimeUTC", ""),
            "game_state": game.get("gameState", ""),
        })

    return games


# ---------------------------------------------------------------------------
# Goalie helpers
# ---------------------------------------------------------------------------

def fetch_goalie_stats(season: str = "20242025") -> list[dict[str, Any]]:
    """Fetch goalie statistics for the season.

    Returns a list of goalie dicts, each containing:
        - player_name   (str)
        - team_code     (str)
        - games_played  (int)
        - save_pct      (float)
        - gaa           (float)
        - wins          (int)

    The NHL API exposes several leader-category endpoints.  We query the
    ``savePercentage`` category with a large enough limit to capture all
    rostered goalies, then enrich with wins from a second call.
    """
    # Primary: save-percentage leaders (gives us save_pct, gaa, GP)
    url = (
        f"{NHL_API_BASE}/goalie-stats-leaders/current"
        f"?categories=savePctg&limit=200"
    )
    data = _fetch_json(url)

    # Build a lookup keyed on player name so we can merge wins in later.
    goalies_by_name: dict[str, dict[str, Any]] = {}

    for category in data.get("categories", []):
        for entry in category.get("leaders", []):
            player = entry.get("player", {})
            first = player.get("firstName", {})
            last = player.get("lastName", {})
            first_name = first.get("default", "") if isinstance(first, dict) else str(first)
            last_name = last.get("default", "") if isinstance(last, dict) else str(last)
            name = f"{first_name} {last_name}".strip()

            team = entry.get("teamAbbrev", "")
            if isinstance(team, dict):
                team = team.get("default", "")

            goalies_by_name[name] = {
                "player_name": name,
                "team_code": str(team),
                "games_played": int(entry.get("gamesPlayed", 0)),
                "save_pct": float(entry.get("value", 0.0)),
                "gaa": float(entry.get("goalsAgainstAverage", 0.0)),
                "wins": int(entry.get("wins", 0)),
            }

    # Secondary: wins leaders -- merge win counts we may have missed.
    wins_url = (
        f"{NHL_API_BASE}/goalie-stats-leaders/current"
        f"?categories=wins&limit=200"
    )
    wins_data = _fetch_json(wins_url)

    for category in wins_data.get("categories", []):
        for entry in category.get("leaders", []):
            player = entry.get("player", {})
            first = player.get("firstName", {})
            last = player.get("lastName", {})
            first_name = first.get("default", "") if isinstance(first, dict) else str(first)
            last_name = last.get("default", "") if isinstance(last, dict) else str(last)
            name = f"{first_name} {last_name}".strip()

            if name in goalies_by_name:
                goalies_by_name[name]["wins"] = int(entry.get("value", goalies_by_name[name]["wins"]))
            else:
                team = entry.get("teamAbbrev", "")
                if isinstance(team, dict):
                    team = team.get("default", "")

                goalies_by_name[name] = {
                    "player_name": name,
                    "team_code": str(team),
                    "games_played": int(entry.get("gamesPlayed", 0)),
                    "save_pct": 0.0,
                    "gaa": 0.0,
                    "wins": int(entry.get("value", 0)),
                }

    log.info("Fetched stats for %d goalies", len(goalies_by_name))
    return list(goalies_by_name.values())


def fetch_game_goalies(game_id: int) -> dict[str, list[dict[str, Any]]]:
    """Fetch goalie data for a specific game from NHL API gamecenter.

    Uses the ``/v1/gamecenter/{game_id}/landing`` endpoint to extract
    goalie comparison data (both teams' goalies with season stats).

    Parameters
    ----------
    game_id : int
        NHL game ID (e.g. 2025020990).

    Returns
    -------
    dict[str, list[dict]]
        Dict keyed by team abbreviation, each value is a list of goalie
        dicts with keys: player_id, name, games_played, save_pct, gaa.
        Returns ``{}`` on any failure.
    """
    data = _fetch_json(f"{NHL_API_BASE}/gamecenter/{game_id}/landing")
    if not data:
        return {}

    matchup = data.get("matchup", {})
    comparison = matchup.get("goalieComparison", {})

    result: dict[str, list[dict[str, Any]]] = {}
    for side in ("homeTeam", "awayTeam"):
        team_abbrev = data.get(side, {}).get("abbrev", "")
        leaders = comparison.get(side, {}).get("leaders", [])
        result[team_abbrev] = [
            {
                "player_id": g.get("playerId"),
                "name": g.get("name", {}).get("default", ""),
                "games_played": g.get("gamesPlayed", 0),
                "save_pct": g.get("savePctg", 0.0),
                "gaa": g.get("gaa", 0.0),
            }
            for g in leaders
        ]

    return result


def infer_likely_starter(
    team_code: str,
    goalie_stats: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Infer the likely starting goalie for *team_code*.

    Heuristic: the goalie on the given team with the most games played is
    assumed to be the starter.  Returns ``None`` when no goalie matches.

    KNOWN LIMITATION (Agent 5 audit):
    This heuristic is a POOR proxy for "who starts tonight."
    - Always returns the season GP leader, even on backup-start nights.
    - Has no access to daily lineup confirmations, morning skate
      reports, or official starting goalie announcements.
    - In tandem situations (e.g. 40/40 GP splits), accuracy drops
      to near coin-flip.
    - Injured starters continue to be selected until the backup
      overtakes them in total GP.
    - The downstream goalie_matchup_adjustment() may apply a +/- 1-3pp
      error on backup-start nights.

    Improvement path: consume a confirmed-starter feed (DailyFaceoff,
    LeftWingLock) or the NHL API /gamecenter/{id}/landing preview,
    which typically includes confirmed starters 1-2 hours before puck drop.
    """
    candidates = [
        g for g in goalie_stats
        if g.get("team_code", "").upper() == team_code.upper()
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda g: g.get("games_played", 0))


def fetch_game_goalies(game_id: int) -> dict[str, list[dict[str, Any]]]:
    """Fetch goalie data for a specific game from the NHL API.

    Uses the ``/v1/gamecenter/{game_id}/landing`` endpoint to extract
    goalie comparison data with per-goalie season stats.

    Parameters
    ----------
    game_id : int
        NHL game ID (e.g., 2025020990).

    Returns
    -------
    dict[str, list[dict]]
        Dict keyed by team abbreviation, each containing a list of goalie
        dicts with keys: player_id, name, games_played, save_pct, gaa.
        Returns empty dict on any failure.
    """
    data = _fetch_json(f"{NHL_API_BASE}/gamecenter/{game_id}/landing")
    if not data:
        return {}

    matchup = data.get("matchup", {})
    comparison = matchup.get("goalieComparison", {})

    result: dict[str, list[dict[str, Any]]] = {}
    for side in ("homeTeam", "awayTeam"):
        team_abbrev = data.get(side, {}).get("abbrev", "")
        if not team_abbrev:
            continue
        leaders = comparison.get(side, {}).get("leaders", [])
        result[team_abbrev] = [
            {
                "player_id": g.get("playerId"),
                "name": g.get("name", {}).get("default", ""),
                "games_played": g.get("gamesPlayed", 0),
                "save_pct": g.get("savePctg", 0.0),
                "gaa": g.get("gaa", 0.0),
            }
            for g in leaders
        ]
    return result


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def fetch_game_score(game_id: int) -> dict[str, Any] | None:
    """Fetch final score for a specific game by NHL game ID.

    Returns a dict with keys: game_id, home_team, away_team, home_score,
    away_score, game_state.  Returns None if the game is not found or
    the API call fails.

    game_state values: "OFF" or "FINAL" = game is over.
    """
    url = f"{NHL_API_BASE}/gamecenter/{game_id}/landing"
    data = _fetch_json(url)
    if not data:
        return None

    home = data.get("homeTeam", {})
    away = data.get("awayTeam", {})
    return {
        "game_id": data.get("id", game_id),
        "home_team": home.get("abbrev", ""),
        "away_team": away.get("abbrev", ""),
        "home_score": int(home.get("score", 0)),
        "away_score": int(away.get("score", 0)),
        "game_state": data.get("gameState", ""),
    }


def fetch_scores_for_date(date_str: str | None = None) -> list[dict[str, Any]]:
    """Fetch final scores for all games on a given date.

    Combines fetch_schedule + fetch_game_score for finished games.
    Only returns games where game_state indicates completion (OFF/FINAL).
    """
    schedule = fetch_schedule(date_str)
    results: list[dict[str, Any]] = []

    for game in schedule:
        state = game.get("game_state", "")
        if state not in ("OFF", "FINAL"):
            continue
        score = fetch_game_score(game["game_id"])
        if score:
            results.append(score)

    return results


def fetch_standings() -> list[dict[str, Any]]:
    """Fetch current NHL standings.

    Returns a list of team dicts, each containing:
        - team_code    (str)
        - wins         (int)
        - losses       (int)
        - ot_losses    (int)
        - points       (int)
        - games_played (int)
        - goal_diff    (int)
    """
    url = f"{NHL_API_BASE}/standings/now"
    data = _fetch_json(url)

    standings: list[dict[str, Any]] = []

    for team_entry in data.get("standings", []):
        abbrev = team_entry.get("teamAbbrev", {})
        if isinstance(abbrev, dict):
            code = abbrev.get("default", "")
        else:
            code = str(abbrev)

        goals_for = int(team_entry.get("goalFor", 0))
        goals_against = int(team_entry.get("goalAgainst", 0))

        standings.append({
            "team_code": code,
            "wins": int(team_entry.get("wins", 0)),
            "losses": int(team_entry.get("losses", 0)),
            "ot_losses": int(team_entry.get("otLosses", 0)),
            "points": int(team_entry.get("points", 0)),
            "games_played": int(team_entry.get("gamesPlayed", 0)),
            "goal_diff": goals_for - goals_against,
        })

    return standings
