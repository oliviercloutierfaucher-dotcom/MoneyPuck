"""NHL Elo rating system.

Implements the FiveThirtyEight-style Elo model adapted for hockey:
- K-factor of 6 (low, reflecting NHL's high variance)
- Margin-of-victory multiplier with autocorrelation dampening
- Home-ice advantage of 50 Elo points (~57% win rate for equal teams)
- 50% season-start regression toward 1500

References:
    - FiveThirtyEight: "How Our NHL Predictions Work"
    - Cole Anderson / CrowdScout Sports (K-factor formula variant)
    - Historical data: github.com/fivethirtyeight/data/tree/master/nhl-forecasts
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INITIAL_ELO = 1500
K_FACTOR = 6
HOME_ADVANTAGE = 50  # Elo points
SEASON_REGRESSION = 0.5  # Regress 50% toward mean at season start
MEAN_ELO = 1505  # Slightly above 1500 to account for league expansion


# ---------------------------------------------------------------------------
# Core Elo math
# ---------------------------------------------------------------------------

def win_probability(elo_a: float, elo_b: float) -> float:
    """Probability that team A beats team B given their Elo ratings."""
    return 1.0 / (1.0 + 10.0 ** (-(elo_a - elo_b) / 400.0))


def margin_of_victory_multiplier(goal_diff: int) -> float:
    """Multiplier that scales Elo update based on how convincing the win was.

    A 1-goal win gets ~0.80x, a 3-goal blowout gets ~1.54x.
    Logarithmic scaling provides diminishing returns.
    """
    if goal_diff <= 0:
        return 0.0
    return 0.6686 * math.log(goal_diff) + 0.8048


def autocorrelation_adjustment(winner_elo_diff: float) -> float:
    """Dampens Elo gain when a strong favorite wins (prevents runaway ratings).

    When an underdog wins, the adjustment amplifies the gain.
    """
    return 2.05 / (winner_elo_diff * 0.001 + 2.05)


# ---------------------------------------------------------------------------
# Elo tracker
# ---------------------------------------------------------------------------

class EloTracker:
    """Maintains and updates Elo ratings across a season."""

    def __init__(self, initial_ratings: dict[str, float] | None = None):
        self._ratings: dict[str, float] = defaultdict(lambda: INITIAL_ELO)
        if initial_ratings:
            self._ratings.update(initial_ratings)

    @property
    def ratings(self) -> dict[str, float]:
        return dict(self._ratings)

    def get(self, team: str) -> float:
        return self._ratings[team]

    def regress_to_mean(self) -> None:
        """Apply between-season regression (50% toward mean)."""
        for team in list(self._ratings):
            self._ratings[team] = (
                SEASON_REGRESSION * MEAN_ELO
                + (1 - SEASON_REGRESSION) * self._ratings[team]
            )

    def update(
        self,
        home_team: str,
        away_team: str,
        home_goals: int,
        away_goals: int,
    ) -> tuple[float, float]:
        """Update ratings after a game. Returns (new_home_elo, new_away_elo)."""
        home_elo = self._ratings[home_team]
        away_elo = self._ratings[away_team]

        # Predicted win probability (home gets advantage)
        expected_home = win_probability(home_elo + HOME_ADVANTAGE, away_elo)

        # Actual outcome (1 = home win, 0 = home loss)
        if home_goals > away_goals:
            actual_home = 1.0
        else:
            actual_home = 0.0

        # Goal differential and margin multiplier
        goal_diff = abs(home_goals - away_goals)
        mov = margin_of_victory_multiplier(goal_diff)

        # Autocorrelation: dampen when favorite wins as expected
        if home_goals > away_goals:
            winner_diff = home_elo + HOME_ADVANTAGE - away_elo
        else:
            winner_diff = away_elo - (home_elo + HOME_ADVANTAGE)
        auto = autocorrelation_adjustment(max(0, winner_diff))

        # Elo shift
        shift = K_FACTOR * mov * auto * (actual_home - expected_home)

        self._ratings[home_team] = home_elo + shift
        self._ratings[away_team] = away_elo - shift

        return (self._ratings[home_team], self._ratings[away_team])

    def predict(self, home_team: str, away_team: str) -> float:
        """Predict home win probability."""
        return win_probability(
            self._ratings[home_team] + HOME_ADVANTAGE,
            self._ratings[away_team],
        )


# ---------------------------------------------------------------------------
# Build Elo ratings from historical game data
# ---------------------------------------------------------------------------

def build_elo_ratings(
    games: list[dict[str, Any]],
    season: int | None = None,
) -> EloTracker:
    """Build Elo ratings from MoneyPuck game-by-game data.

    Parameters
    ----------
    games : list
        Game rows from MoneyPuck CSVs. Each must have:
        - playerTeam, opposingTeam (or homeTeamCode, awayTeamCode)
        - goalsFor, goalsAgainst (or home_goals, away_goals)
        - home_or_away (HOME/AWAY) for team-gbg format
        - gameDate or game_date
        - situation (filtered to 'all' for team-gbg)
    season : int, optional
        If provided, only processes games from this season.

    Returns
    -------
    EloTracker with updated ratings for all teams.
    """
    tracker = EloTracker()

    # Detect format
    is_team_gbg = bool(games and "playerTeam" in games[0])

    # Parse and deduplicate games
    seen_games: set[str] = set()
    parsed: list[tuple[str, str, str, int, int]] = []

    for row in games:
        if is_team_gbg:
            # Team game-by-game: only take HOME rows with situation=all
            if row.get("home_or_away", "") != "HOME":
                continue
            if row.get("situation", "") != "all":
                continue
            home = row.get("playerTeam", "")
            away = row.get("opposingTeam", "")
            home_goals = _safe_int(row.get("goalsFor", 0))
            away_goals = _safe_int(row.get("goalsAgainst", 0))
            raw_date = str(row.get("gameDate", ""))
        else:
            home = row.get("homeTeamCode", row.get("home_team", ""))
            away = row.get("awayTeamCode", row.get("away_team", ""))
            home_goals = _safe_int(row.get("home_goals", row.get("goalsFor", 0)))
            away_goals = _safe_int(row.get("away_goals", row.get("goalsAgainst", 0)))
            raw_date = str(row.get("gameDate", row.get("game_date", "")))

        if not home or not away:
            continue

        # Deduplicate
        game_key = f"{raw_date}-{home}-{away}"
        if game_key in seen_games:
            continue
        seen_games.add(game_key)

        parsed.append((raw_date, home, away, home_goals, away_goals))

    # Sort chronologically
    parsed.sort(key=lambda x: x[0])

    # Update ratings game by game
    for raw_date, home, away, home_goals, away_goals in parsed:
        if home_goals == away_goals:
            # Treat ties as 0 goal diff (OT games in MoneyPuck include OT/SO goals)
            continue
        tracker.update(home, away, home_goals, away_goals)

    return tracker


def _safe_int(val: Any) -> int:
    """Convert value to int, defaulting to 0."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0
