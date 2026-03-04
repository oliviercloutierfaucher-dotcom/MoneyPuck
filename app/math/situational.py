"""Phase 5 -- Situational Factors.

Pure functions (no external API calls) that detect and quantify
situational factors affecting NHL game outcomes.  All inputs come from
MoneyPuck CSV rows (``dict[str, str]`` with fields such as *gameDate*,
*homeTeamCode*, *awayTeamCode*, etc.).

Every adjustment value is expressed as a probability delta from the
**home team's perspective** -- positive means the home team benefits,
negative means the away team benefits.
"""

from __future__ import annotations

from datetime import date, datetime

# ---------------------------------------------------------------------------
# Timezone offsets from Eastern (ET = 0) for all 32 NHL teams
# ---------------------------------------------------------------------------

TEAM_TIMEZONE: dict[str, int] = {
    # Atlantic Division
    "BOS": 0,   # Boston Bruins
    "BUF": 0,   # Buffalo Sabres
    "DET": 0,   # Detroit Red Wings
    "FLA": 0,   # Florida Panthers
    "MTL": 0,   # Montreal Canadiens
    "OTT": 0,   # Ottawa Senators
    "T.B": 0,   # Tampa Bay Lightning
    "TOR": 0,   # Toronto Maple Leafs
    # Metropolitan Division
    "CAR": 0,   # Carolina Hurricanes
    "CBJ": 0,   # Columbus Blue Jackets
    "N.J": 0,   # New Jersey Devils
    "NYI": 0,   # New York Islanders
    "NYR": 0,   # New York Rangers
    "PHI": 0,   # Philadelphia Flyers
    "PIT": 0,   # Pittsburgh Penguins
    "WSH": 0,   # Washington Capitals
    # Central Division
    "CHI": -1,  # Chicago Blackhawks
    "COL": -2,  # Colorado Avalanche
    "DAL": -1,  # Dallas Stars
    "MIN": -1,  # Minnesota Wild
    "NSH": -1,  # Nashville Predators
    "STL": -1,  # St. Louis Blues
    "UTA": -2,  # Utah Hockey Club (formerly Arizona)
    "WPG": -1,  # Winnipeg Jets
    # Pacific Division
    "ANA": -3,  # Anaheim Ducks
    "CGY": -2,  # Calgary Flames
    "EDM": -2,  # Edmonton Oilers
    "L.A": -3,  # Los Angeles Kings
    "S.J": -3,  # San Jose Sharks
    "SEA": -3,  # Seattle Kraken
    "VAN": -3,  # Vancouver Canucks
    "VGK": -3,  # Vegas Golden Knights
}


# ---------------------------------------------------------------------------
# Rest-day detection
# ---------------------------------------------------------------------------

def _parse_date(iso: str | date) -> date:
    """Parse the first 10 characters of an ISO-format date string.

    Also accepts ``datetime.date`` objects directly.
    """
    if isinstance(iso, date):
        return iso
    return datetime.strptime(str(iso)[:10], "%Y-%m-%d").date()


def detect_rest_days(
    team: str,
    game_date: str,
    games_rows: list[dict[str, str]],
) -> int:
    """Return the number of rest days before *game_date* for *team*.

    Scans *games_rows* for the most recent game where *team* appeared as
    either the home or away team **before** *game_date* and returns the
    calendar-day difference minus one (i.e. 0 means back-to-back).

    Returns ``99`` when no prior game is found (e.g. season opener).
    """
    try:
        target = _parse_date(game_date)
    except (ValueError, TypeError):
        return 99

    most_recent: date | None = None

    for row in games_rows:
        if row.get("homeTeamCode") != team and row.get("awayTeamCode") != team:
            continue
        row_date_str = row.get("gameDate", "")
        if not row_date_str:
            continue
        try:
            row_date = _parse_date(row_date_str)
        except (ValueError, TypeError):
            continue
        if row_date >= target:
            continue
        if most_recent is None or row_date > most_recent:
            most_recent = row_date

    if most_recent is None:
        return 99

    return (target - most_recent).days - 1


def is_back_to_back(rest_days: int) -> bool:
    """Return ``True`` when a team played the previous day (0 rest days)."""
    return rest_days == 0


# ---------------------------------------------------------------------------
# Rest adjustment (home-team perspective)
# ---------------------------------------------------------------------------

def rest_adjustment(rest_days_home: int, rest_days_away: int) -> float:
    """Probability adjustment based on the rest differential.

    Returned value is from the **home team's perspective**:
    * negative means the home team is disadvantaged
    * positive means the home team benefits

    Scale
    -----
    - B2B vs 2+ rest  : -0.04
    - B2B vs 1 rest   : -0.02
    - B2B vs B2B      :  0.00
    - 1 rest vs 2+    : -0.01
    - 3+ rest (rust)  : -0.01
    - Otherwise       :  0.00

    When the **away** team is the tired side the sign flips (home benefits).
    """
    home_b2b = is_back_to_back(rest_days_home)
    away_b2b = is_back_to_back(rest_days_away)

    # Both on a back-to-back -- cancels out
    if home_b2b and away_b2b:
        return 0.0

    # Home team on a B2B
    if home_b2b:
        if rest_days_away >= 2:
            return -0.04
        # away has 1 rest day
        return -0.02

    # Away team on a B2B
    if away_b2b:
        if rest_days_home >= 2:
            return 0.04
        # home has 1 rest day
        return 0.02

    # Neither is B2B -- check moderate fatigue / rust
    # Home has 1 rest vs away 2+
    if rest_days_home == 1 and rest_days_away >= 2:
        return -0.01

    # Away has 1 rest vs home 2+
    if rest_days_away == 1 and rest_days_home >= 2:
        return 0.01

    # Rust factor: either team with 3+ rest days
    if rest_days_home >= 3 and rest_days_away < 3:
        return -0.01
    if rest_days_away >= 3 and rest_days_home < 3:
        return 0.01

    return 0.0


# ---------------------------------------------------------------------------
# Travel / timezone adjustment
# ---------------------------------------------------------------------------

def travel_adjustment(home_team: str, away_team: str) -> float:
    """Probability adjustment for timezone-distance travel.

    For every timezone the away team crosses beyond the first, the home
    team receives a +0.01 bonus, capped at +0.03.

    Returns the adjustment from the home team's perspective (always >= 0).
    """
    home_tz = TEAM_TIMEZONE.get(home_team, 0)
    away_tz = TEAM_TIMEZONE.get(away_team, 0)
    tz_diff = abs(home_tz - away_tz)

    if tz_diff < 2:
        return 0.0

    # +0.01 for each timezone crossed beyond 1, capped at 0.03
    return min((tz_diff - 1) * 0.01, 0.03)


# ---------------------------------------------------------------------------
# Master function
# ---------------------------------------------------------------------------

def situational_adjustments(
    home_team: str,
    away_team: str,
    game_date: str,
    games_rows: list[dict[str, str]],
) -> dict[str, float | int | bool]:
    """Combine all situational factors into a single dict.

    Returns
    -------
    dict with keys:
        home_rest_days : int
        away_rest_days : int
        home_b2b       : bool
        away_b2b       : bool
        rest_adj       : float   (home perspective)
        travel_adj     : float   (home perspective)
        total_adj      : float   (rest_adj + travel_adj)
    """
    home_rest = detect_rest_days(home_team, game_date, games_rows)
    away_rest = detect_rest_days(away_team, game_date, games_rows)

    r_adj = rest_adjustment(home_rest, away_rest)
    t_adj = travel_adjustment(home_team, away_team)

    return {
        "home_rest_days": home_rest,
        "away_rest_days": away_rest,
        "home_b2b": is_back_to_back(home_rest),
        "away_b2b": is_back_to_back(away_rest),
        "rest_adj": r_adj,
        "travel_adj": t_adj,
        "total_adj": round(r_adj + t_adj, 4),
    }
