"""Injury tier classification and win probability adjustment calculation.

Classifies injured NHL players into impact tiers based on TOI ranking
within their team/position group, then calculates a net win probability
adjustment from the home team's perspective.

Key design decisions:
- Goalie injuries are detected for display but NOT applied as adjustments
  (Phase 4 already handles goalie impact via backup save%).
- GTD (Game-Time Decision) players receive half the adjustment.
- Per-team penalty capped at 8pp to prevent runaway adjustments.
- Net adjustment is symmetrical: equal injuries on both teams cancel out.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.logging_config import get_logger

log = get_logger("injury_impact")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIER_IMPACT: dict[str, float] = {
    "starting_g": 4.0,    # Display only -- NOT applied (Phase 4 handles)
    "top6_f": 2.0,        # pp midpoint of 1.5-2.5 range
    "top4_d": 1.5,        # pp midpoint of 1-2 range
    "bottom6_f": 0.75,    # pp midpoint of 0.5-1 range
    "bottom_d": 0.75,     # pp midpoint of 0.5-1 range
}

GTD_MULTIPLIER = 0.5
MAX_INJURY_ADJ = 8.0  # pp cap per team

FORWARD_POSITIONS = {"C", "L", "R", "LW", "RW", "F"}
DEFENSE_POSITIONS = {"D"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InjuredPlayer:
    """Represents an injured player with tier classification and impact."""

    team: str
    player_name: str
    position: str
    status: str
    tier: str
    impact_pp: float


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------

def classify_player_tier(
    player_name: str,
    position: str,
    team_players: list[dict],
) -> str:
    """Classify a player into an impact tier based on TOI rank within team.

    Matches by last name within the team roster (same pattern as Phase 4
    goalie resolver). Falls back to bottom tier if player not found.

    Parameters
    ----------
    player_name : str
        Full display name (e.g. "Connor McDavid").
    position : str
        Position code (C, L, R, D, G).
    team_players : list[dict]
        Team roster from fetch_team_player_stats().

    Returns
    -------
    str
        One of: "starting_g", "top6_f", "top4_d", "bottom6_f", "bottom_d".
    """
    if position == "G":
        return "starting_g"

    # Determine positional group
    is_forward = position in FORWARD_POSITIONS
    is_defense = position in DEFENSE_POSITIONS

    if is_forward:
        group = sorted(
            [p for p in team_players if p.get("position", "") in ("C", "L", "R")],
            key=lambda p: p.get("toi_per_game", 0),
            reverse=True,
        )
        # Match by last name
        last_name = player_name.split()[-1] if player_name else ""
        rank = _find_rank(last_name, group)
        if rank is None:
            return "bottom6_f"  # fallback
        return "top6_f" if rank < 6 else "bottom6_f"

    if is_defense:
        group = sorted(
            [p for p in team_players if p.get("position", "") == "D"],
            key=lambda p: p.get("toi_per_game", 0),
            reverse=True,
        )
        last_name = player_name.split()[-1] if player_name else ""
        rank = _find_rank(last_name, group)
        if rank is None:
            return "bottom_d"  # fallback
        return "top4_d" if rank < 4 else "bottom_d"

    # Unknown position -> bottom forward
    return "bottom6_f"


def _find_rank(last_name: str, sorted_players: list[dict]) -> int | None:
    """Find a player's rank index by last name in a sorted list."""
    last_name_lower = last_name.lower()
    for i, p in enumerate(sorted_players):
        p_name = p.get("name", "")
        p_last = p_name.split()[-1].lower() if p_name else ""
        if p_last == last_name_lower:
            return i
    return None


# ---------------------------------------------------------------------------
# Build tiers (batch operation)
# ---------------------------------------------------------------------------

def build_player_tiers(
    injuries: list[dict],
    fetch_stats_fn=None,
) -> dict[tuple[str, str], str]:
    """Build (team, player_name) -> tier mapping for all injured players.

    Only fetches player stats for teams that have injuries (lazy).
    Caches per-team results within a single call.

    Parameters
    ----------
    injuries : list[dict]
        Output from fetch_injuries().
    fetch_stats_fn : callable, optional
        Function(team_code) -> list[dict]. Defaults to fetch_team_player_stats.

    Returns
    -------
    dict[tuple[str, str], str]
        Mapping of (team_code, player_name) -> tier string.
    """
    if fetch_stats_fn is None:
        from app.data.injuries import fetch_team_player_stats
        fetch_stats_fn = fetch_team_player_stats

    # Group injuries by team
    teams_with_injuries: dict[str, list[dict]] = {}
    for inj in injuries:
        team = inj.get("team", "")
        if team:
            teams_with_injuries.setdefault(team, []).append(inj)

    # Fetch stats per team (cached within this call)
    team_rosters: dict[str, list[dict]] = {}
    tiers: dict[tuple[str, str], str] = {}

    for team, team_injuries in teams_with_injuries.items():
        if team not in team_rosters:
            team_rosters[team] = fetch_stats_fn(team)

        roster = team_rosters[team]
        for inj in team_injuries:
            player_name = inj.get("player_name", "")
            position = inj.get("position", "")
            tier = classify_player_tier(player_name, position, roster)
            tiers[(team, player_name)] = tier

    return tiers


# ---------------------------------------------------------------------------
# Adjustment calculation
# ---------------------------------------------------------------------------

def calculate_injury_adjustment(
    home_team: str,
    away_team: str,
    injuries: list[dict],
    player_tiers: dict[tuple[str, str], str],
) -> tuple[float, list[InjuredPlayer]]:
    """Calculate net injury adjustment from home team's perspective.

    Positive result means home team benefits (away team more depleted).

    Parameters
    ----------
    home_team : str
        Home team abbreviation.
    away_team : str
        Away team abbreviation.
    injuries : list[dict]
        Output from fetch_injuries().
    player_tiers : dict[tuple[str, str], str]
        Output from build_player_tiers().

    Returns
    -------
    tuple[float, list[InjuredPlayer]]
        (net_adjustment_probability, injured_player_list)
        net_adjustment is in probability units (pp / 100).
        injured_player_list includes ALL injuries (including goalies) for display.
    """
    if not injuries:
        return 0.0, []

    injured_players: list[InjuredPlayer] = []

    def team_penalty(team: str) -> float:
        team_injuries = [i for i in injuries if i.get("team", "") == team]
        total = 0.0

        for inj in team_injuries:
            player_name = inj.get("player_name", "")
            position = inj.get("position", "")
            status = inj.get("status", "")
            tier = player_tiers.get((team, player_name), "bottom6_f")

            impact = TIER_IMPACT.get(tier, 0.75)

            # GTD: half impact
            is_gtd = "Day-To-Day" in status or "DTD" in status.upper()
            if is_gtd:
                impact *= GTD_MULTIPLIER

            # Build display record (all players including goalies)
            injured_players.append(InjuredPlayer(
                team=team,
                player_name=player_name,
                position=position,
                status=status,
                tier=tier,
                impact_pp=impact,
            ))

            # Skip goalie injuries in adjustment calculation
            if tier == "starting_g":
                continue

            total += impact

        if total > MAX_INJURY_ADJ:
            log.info(
                "Injury cap reached for %s: %.1f capped to %.1f",
                team, total, MAX_INJURY_ADJ,
            )
            total = MAX_INJURY_ADJ

        return total

    home_penalty = team_penalty(home_team)
    away_penalty = team_penalty(away_team)

    # Net: positive = home benefits (away more hurt)
    net_adj = (away_penalty - home_penalty) / 100.0

    return net_adj, injured_players
