"""3-tier goalie resolution: confirmed -> likely -> GP-leader fallback.

Resolves the starting goalie for each team using DailyFaceoff confirmation
data when available, falling back to the GP-leader heuristic when not.

All functions are resilient and never raise exceptions to the caller.
"""

from __future__ import annotations

from typing import Any

from app.data.nhl_api import infer_likely_starter
from app.logging_config import get_logger

log = get_logger("goalie_resolver")


def _match_goalie_name(
    df_name: str,
    goalie_stats: list[dict[str, Any]],
    team_code: str,
) -> dict[str, Any] | None:
    """Match a DailyFaceoff goalie name to a goalie_stats entry.

    Primary match: last name + team_code.  DailyFaceoff provides full names
    (e.g., "Jeremy Swayman"), goalie_stats also has full names.  We extract
    the last name and match against goalie_stats entries for the same team.

    Returns the matched goalie dict or None.
    """
    if not df_name or not goalie_stats:
        return None

    df_last = df_name.strip().split()[-1].lower()
    team_upper = team_code.upper()

    candidates = [
        g for g in goalie_stats
        if g.get("team_code", "").upper() == team_upper
    ]

    for g in candidates:
        player_name = g.get("player_name", "")
        if not player_name:
            continue
        stats_last = player_name.strip().split()[-1].lower()
        if stats_last == df_last:
            return g

    return None


def resolve_starter(
    team_code: str,
    df_starters: list[dict[str, Any]],
    goalie_stats: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """Resolve the starting goalie for a team with 3-tier fallback.

    Tier 1/2: DailyFaceoff confirmed or likely starter.
    Tier 3: GP-leader heuristic (existing ``infer_likely_starter``).

    Parameters
    ----------
    team_code : str
        NHL three-letter team abbreviation (e.g., "BOS").
    df_starters : list[dict]
        DailyFaceoff starter entries from ``fetch_dailyfaceoff_starters``.
    goalie_stats : list[dict]
        Season goalie stats from ``fetch_goalie_stats``.

    Returns
    -------
    tuple[dict | None, str]
        (goalie_dict, source) where source is one of:
        "confirmed", "likely", "gp_leader", "none".
    """
    team_upper = team_code.upper()

    # Tier 1 & 2: DailyFaceoff
    for entry in df_starters:
        # Check home side
        if entry.get("home_team", "").upper() == team_upper:
            status = entry.get("home_status", "unconfirmed")
            if status in ("confirmed", "likely"):
                goalie_name = entry.get("home_goalie")
                matched = _match_goalie_name(goalie_name, goalie_stats, team_code)
                if matched:
                    log.info(
                        "Resolved %s starter via DailyFaceoff (%s): %s",
                        team_code, status, goalie_name,
                    )
                    return matched, status

        # Check away side
        if entry.get("away_team", "").upper() == team_upper:
            status = entry.get("away_status", "unconfirmed")
            if status in ("confirmed", "likely"):
                goalie_name = entry.get("away_goalie")
                matched = _match_goalie_name(goalie_name, goalie_stats, team_code)
                if matched:
                    log.info(
                        "Resolved %s starter via DailyFaceoff (%s): %s",
                        team_code, status, goalie_name,
                    )
                    return matched, status

    # Tier 3: GP-leader heuristic
    starter = infer_likely_starter(team_code, goalie_stats)
    if starter:
        return starter, "gp_leader"

    return None, "none"


def resolve_all_starters(
    teams: list[str],
    df_starters: list[dict[str, Any]],
    goalie_stats: list[dict[str, Any]],
) -> dict[str, tuple[dict[str, Any] | None, str]]:
    """Resolve starting goalie for each team.

    Parameters
    ----------
    teams : list[str]
        List of NHL team abbreviations.
    df_starters : list[dict]
        DailyFaceoff starter entries.
    goalie_stats : list[dict]
        Season goalie stats.

    Returns
    -------
    dict[str, tuple[dict | None, str]]
        Dict keyed by team_code with (goalie_dict, source) tuples.
    """
    result: dict[str, tuple[dict[str, Any] | None, str]] = {}
    for team in teams:
        result[team] = resolve_starter(team, df_starters, goalie_stats)
    return result
