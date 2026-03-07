"""ESPN injury fetcher and NHL club-stats player stats fetcher.

Provides two data-fetching functions:
- fetch_injuries(): Current NHL injuries from ESPN's public API
- fetch_team_player_stats(): Per-player TOI/stats from NHL club-stats API

Both are fail-soft -- they return empty lists on any error, consistent with
the project's best-effort enrichment pattern.
"""

from __future__ import annotations

from app.data.nhl_api import _fetch_json
from app.logging_config import get_logger

log = get_logger("injuries")

# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

ESPN_INJURIES_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"
)
NHL_CLUB_STATS_URL = "https://api-web.nhle.com/v1/club-stats/{team}/now"

# ---------------------------------------------------------------------------
# Team abbreviation normalization (ESPN -> NHL conventions)
# ---------------------------------------------------------------------------

TEAM_ABBREV_MAP: dict[str, str] = {
    "UTAH": "UTA",
    "PHX": "ARI",
}

# Position normalization (ESPN -> project conventions)
POSITION_MAP: dict[str, str] = {
    "LW": "L",
    "RW": "R",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_injuries() -> list[dict]:
    """Fetch current NHL injuries from ESPN API.

    Returns a list of dicts, each with keys:
        team, player_name, position, status, injury_type, return_date

    Returns empty list on any error (fail-soft).
    """
    try:
        data = _fetch_json(ESPN_INJURIES_URL)
        if not data:
            return []

        injuries: list[dict] = []
        for team_entry in data.get("injuries", []):
            team_info = team_entry.get("team", {})
            if not isinstance(team_info, dict):
                continue
            raw_abbrev = team_info.get("abbreviation", "")
            if not raw_abbrev:
                continue
            team_abbrev = TEAM_ABBREV_MAP.get(raw_abbrev, raw_abbrev)

            for inj in team_entry.get("injuries", []):
                athlete = inj.get("athlete", {})
                if not isinstance(athlete, dict):
                    continue
                player_name = athlete.get("displayName", "")
                if not player_name:
                    continue

                pos_info = athlete.get("position", {})
                raw_pos = pos_info.get("abbreviation", "") if isinstance(pos_info, dict) else ""
                position = POSITION_MAP.get(raw_pos, raw_pos)

                details = inj.get("details", {})
                if not isinstance(details, dict):
                    details = {}

                injuries.append({
                    "team": team_abbrev,
                    "player_name": player_name,
                    "position": position,
                    "status": inj.get("status", ""),
                    "injury_type": details.get("type", ""),
                    "return_date": details.get("returnDate", ""),
                })

        log.info("Fetched %d injuries across NHL teams", len(injuries))
        return injuries

    except Exception:
        log.warning("Failed to fetch ESPN injuries", exc_info=True)
        return []


def fetch_team_player_stats(team_code: str) -> list[dict]:
    """Fetch per-player stats from NHL club-stats API for tier classification.

    Returns a list of dicts, each with keys:
        player_id, name, position, toi_per_game, games_played, points
    Goalies also include: games_started

    Returns empty list on any error (fail-soft).
    """
    try:
        url = NHL_CLUB_STATS_URL.format(team=team_code)
        data = _fetch_json(url)
        if not data:
            return []

        players: list[dict] = []

        for skater in data.get("skaters", []):
            first = skater.get("firstName", {})
            last = skater.get("lastName", {})
            first_name = first.get("default", "") if isinstance(first, dict) else str(first)
            last_name = last.get("default", "") if isinstance(last, dict) else str(last)

            players.append({
                "player_id": skater.get("playerId"),
                "name": f"{first_name} {last_name}".strip(),
                "position": skater.get("positionCode", ""),
                "toi_per_game": skater.get("avgTimeOnIcePerGame", 0),
                "games_played": skater.get("gamesPlayed", 0),
                "points": skater.get("points", 0),
            })

        for goalie in data.get("goalies", []):
            first = goalie.get("firstName", {})
            last = goalie.get("lastName", {})
            first_name = first.get("default", "") if isinstance(first, dict) else str(first)
            last_name = last.get("default", "") if isinstance(last, dict) else str(last)

            players.append({
                "player_id": goalie.get("playerId"),
                "name": f"{first_name} {last_name}".strip(),
                "position": "G",
                "toi_per_game": 0,
                "games_played": goalie.get("gamesPlayed", 0),
                "games_started": goalie.get("gamesStarted", 0),
                "points": 0,
            })

        log.info("Fetched stats for %d players on %s", len(players), team_code)
        return players

    except Exception:
        log.warning("Failed to fetch player stats for %s", team_code, exc_info=True)
        return []
