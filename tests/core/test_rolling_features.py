"""Tests for Phase 2: Multi-window rolling features (5g, 10g, momentum)."""
from __future__ import annotations

import pytest
from app.core.agents import TeamStrengthAgent
from app.core.models import TeamMetrics


# ---------------------------------------------------------------------------
# Helpers — build synthetic game entries as produced by _extract_team_gbg
# ---------------------------------------------------------------------------

def _make_game(team: str, game_date: str, xg: float = 0.5, **overrides) -> dict:
    """Build a single game entry dict matching TeamStrengthAgent extraction format."""
    base = {
        "weight": 1.0,
        "game_date": game_date,
        "xg_share": xg,
        "corsi_share": 0.5,
        "fenwick_share": 0.5,
        "high_danger_share": 0.5,
        "score_adj_xg_share": xg,
        "flurry_adj_xg_share": xg,
        "hd_xg_share": 0.5,
        "md_xg_share": 0.5,
        "rebound_control": 0.5,
        "faceoff_pct": 0.5,
        "takeaway_ratio": 0.5,
        "dzone_giveaway_rate": 0.0,
        "shooting_pct": 0.08,
        "save_pct": 0.91,
        "pp_xg_per_60": 0.0,
        "pk_xg_against_per_60": 0.0,
        "venue": "home",
    }
    base.update(overrides)
    return base


def _build_team_games(team: str, n_games: int, base_xg: float = 0.5,
                      trend: float = 0.0) -> list[dict]:
    """Build N games for a team with optional trend in xg_share.

    trend > 0: improving over time (most recent games have higher xG).
    """
    games = []
    for i in range(n_games):
        day = f"2025-01-{(i + 1):02d}"
        xg = base_xg + trend * i
        xg = max(0.0, min(1.0, xg))
        games.append(_make_game(team, day, xg=xg))
    return games


# ---------------------------------------------------------------------------
# Test _compute_rolling_composites directly
# ---------------------------------------------------------------------------

class TestRollingComposites:
    """Unit tests for TeamStrengthAgent._compute_rolling_composites."""

    def test_basic_5_and_10_game_windows(self):
        """With 15 games, 5g and 10g windows should use last 5/10 games."""
        team_games = {
            "TOR": _build_team_games("TOR", 15, base_xg=0.55),
            "MTL": _build_team_games("MTL", 15, base_xg=0.45),
        }
        teams = ["MTL", "TOR"]
        result = TeamStrengthAgent._compute_rolling_composites(team_games, teams, 20)

        # TOR (xg=0.55) should be positive, MTL (xg=0.45) should be negative
        assert result["TOR"]["composite_5g"] > 0
        assert result["MTL"]["composite_5g"] < 0
        assert result["TOR"]["composite_10g"] > 0
        assert result["MTL"]["composite_10g"] < 0

    def test_fewer_than_5_games(self):
        """Teams with < 5 games should still get composites (from available games)."""
        team_games = {
            "TOR": _build_team_games("TOR", 3, base_xg=0.55),
            "MTL": _build_team_games("MTL", 3, base_xg=0.45),
        }
        teams = ["MTL", "TOR"]
        result = TeamStrengthAgent._compute_rolling_composites(team_games, teams, 20)

        # Should not crash; composites computed from 3 games
        assert "composite_5g" in result["TOR"]
        assert "composite_10g" in result["TOR"]
        assert "momentum" in result["TOR"]

    def test_empty_games(self):
        """Team with no games gets zero composites."""
        team_games = {
            "TOR": [],
            "MTL": _build_team_games("MTL", 10, base_xg=0.5),
        }
        teams = ["MTL", "TOR"]
        result = TeamStrengthAgent._compute_rolling_composites(team_games, teams, 20)
        # With z-scoring across 2 teams, one at 0.5 raw → should be near zero
        assert isinstance(result["TOR"]["composite_5g"], float)

    def test_momentum_positive_when_improving(self):
        """Team trending UP should have positive momentum."""
        # Last 5 games have higher xg than games 6-10
        games = []
        # Older games (games 1-10): xg = 0.45
        for i in range(10):
            games.append(_make_game("TOR", f"2025-01-{(i+1):02d}", xg=0.45))
        # Recent games (games 11-15): xg = 0.60
        for i in range(5):
            games.append(_make_game("TOR", f"2025-01-{(i+11):02d}", xg=0.60))

        # Need a second team for z-scoring
        mtl_games = _build_team_games("MTL", 15, base_xg=0.50)

        team_games = {"TOR": games, "MTL": mtl_games}
        teams = ["MTL", "TOR"]
        result = TeamStrengthAgent._compute_rolling_composites(team_games, teams, 20)

        # TOR's 5g composite (xg=0.60) should exceed 10g composite (avg of 0.45 and 0.60)
        assert result["TOR"]["momentum"] > 0, (
            f"Expected positive momentum, got {result['TOR']['momentum']}"
        )

    def test_momentum_negative_when_declining(self):
        """Team trending DOWN should have negative momentum."""
        games = []
        # Older games: xg = 0.60
        for i in range(10):
            games.append(_make_game("TOR", f"2025-01-{(i+1):02d}", xg=0.60))
        # Recent games: xg = 0.40
        for i in range(5):
            games.append(_make_game("TOR", f"2025-01-{(i+11):02d}", xg=0.40))

        mtl_games = _build_team_games("MTL", 15, base_xg=0.50)
        team_games = {"TOR": games, "MTL": mtl_games}
        teams = ["MTL", "TOR"]
        result = TeamStrengthAgent._compute_rolling_composites(team_games, teams, 20)

        assert result["TOR"]["momentum"] < 0

    def test_rolling_uses_most_recent_games(self):
        """5g window should use the 5 most recent games by date, not first 5."""
        games = []
        # 10 games total, deliberately out of order
        for i in [5, 3, 8, 1, 10, 2, 7, 4, 9, 6]:
            xg = 0.60 if i > 5 else 0.40  # Recent games better
            games.append(_make_game("TOR", f"2025-01-{i:02d}", xg=xg))

        mtl_games = _build_team_games("MTL", 10, base_xg=0.50)
        team_games = {"TOR": games, "MTL": mtl_games}
        teams = ["MTL", "TOR"]
        result = TeamStrengthAgent._compute_rolling_composites(team_games, teams, 20)

        # 5g should reflect games 6-10 (xg=0.60), so TOR should be positive
        assert result["TOR"]["composite_5g"] > 0

    def test_all_keys_present(self):
        """Result dict should have all three keys."""
        team_games = {
            "TOR": _build_team_games("TOR", 10),
            "MTL": _build_team_games("MTL", 10),
        }
        teams = ["MTL", "TOR"]
        result = TeamStrengthAgent._compute_rolling_composites(team_games, teams, 20)
        for team in teams:
            assert set(result[team].keys()) == {"composite_5g", "composite_10g", "momentum"}


# ---------------------------------------------------------------------------
# Integration: rolling features flow through to TeamMetrics
# ---------------------------------------------------------------------------

class TestRollingIntegration:
    """Test that rolling features are populated in TeamMetrics via run()."""

    def _make_gbg_rows(self, n_games: int = 15) -> list[dict]:
        """Build MoneyPuck team-game-by-game rows for 2 teams."""
        rows = []
        for i in range(n_games):
            day = f"2025010{(i + 1):d}" if i < 9 else f"202501{(i + 1):d}"
            # TOR home game
            rows.append({
                "playerTeam": "TOR", "opposingTeam": "MTL",
                "home_or_away": "HOME", "situation": "all",
                "gameDate": day,
                "xGoalsPercentage": "0.58",
                "corsiPercentage": "0.52",
                "fenwickPercentage": "0.51",
                "highDangerShotsFor": "5", "highDangerShotsAgainst": "4",
                "goalsFor": "3", "goalsAgainst": "2",
                "shotsOnGoalFor": "30", "shotsOnGoalAgainst": "28",
                "scoreVenueAdjustedxGoalsFor": "2.5",
                "scoreVenueAdjustedxGoalsAgainst": "2.0",
                "flurryAdjustedxGoalsFor": "2.3",
                "flurryAdjustedxGoalsAgainst": "1.9",
                "highDangerxGoalsFor": "1.5", "highDangerxGoalsAgainst": "1.2",
                "mediumDangerxGoalsFor": "0.8", "mediumDangerxGoalsAgainst": "0.7",
                "reboundxGoalsFor": "0.3", "reboundxGoalsAgainst": "0.2",
                "faceOffsWonFor": "28", "faceOffsWonAgainst": "25",
                "takeawaysFor": "5", "giveawaysFor": "4",
                "dZoneGiveawaysFor": "2",
                "xGoalsFor": "2.8", "xGoalsAgainst": "2.2",
            })
            # MTL away game (same matchup, away perspective)
            rows.append({
                "playerTeam": "MTL", "opposingTeam": "TOR",
                "home_or_away": "AWAY", "situation": "all",
                "gameDate": day,
                "xGoalsPercentage": "0.42",
                "corsiPercentage": "0.48",
                "fenwickPercentage": "0.49",
                "highDangerShotsFor": "4", "highDangerShotsAgainst": "5",
                "goalsFor": "2", "goalsAgainst": "3",
                "shotsOnGoalFor": "28", "shotsOnGoalAgainst": "30",
                "scoreVenueAdjustedxGoalsFor": "2.0",
                "scoreVenueAdjustedxGoalsAgainst": "2.5",
                "flurryAdjustedxGoalsFor": "1.9",
                "flurryAdjustedxGoalsAgainst": "2.3",
                "highDangerxGoalsFor": "1.2", "highDangerxGoalsAgainst": "1.5",
                "mediumDangerxGoalsFor": "0.7", "mediumDangerxGoalsAgainst": "0.8",
                "reboundxGoalsFor": "0.2", "reboundxGoalsAgainst": "0.3",
                "faceOffsWonFor": "25", "faceOffsWonAgainst": "28",
                "takeawaysFor": "4", "giveawaysFor": "5",
                "dZoneGiveawaysFor": "3",
                "xGoalsFor": "2.2", "xGoalsAgainst": "2.8",
            })
        return rows

    def test_team_metrics_has_rolling_fields(self):
        """TeamMetrics should have composite_5g, composite_10g, momentum."""
        agent = TeamStrengthAgent()
        rows = self._make_gbg_rows(15)
        result = agent.run(rows)

        for team in ["TOR", "MTL"]:
            m = result[team]
            assert hasattr(m, "composite_5g")
            assert hasattr(m, "composite_10g")
            assert hasattr(m, "momentum")
            assert isinstance(m.composite_5g, float)
            assert isinstance(m.composite_10g, float)
            assert isinstance(m.momentum, float)

    def test_stronger_team_positive_rolling(self):
        """TOR (xg=0.58) should have positive rolling composite vs MTL (xg=0.42)."""
        agent = TeamStrengthAgent()
        rows = self._make_gbg_rows(15)
        result = agent.run(rows)

        assert result["TOR"].composite_5g > result["MTL"].composite_5g
        assert result["TOR"].composite_10g > result["MTL"].composite_10g

    def test_momentum_is_difference(self):
        """momentum should equal composite_5g - composite_10g."""
        agent = TeamStrengthAgent()
        rows = self._make_gbg_rows(15)
        result = agent.run(rows)

        for team in ["TOR", "MTL"]:
            m = result[team]
            expected = m.composite_5g - m.composite_10g
            assert abs(m.momentum - expected) < 1e-10


# ---------------------------------------------------------------------------
# TeamMetrics dataclass field tests
# ---------------------------------------------------------------------------

class TestTeamMetricsRollingFields:
    """Test the new fields on the TeamMetrics dataclass."""

    def test_defaults_are_zero(self):
        m = TeamMetrics()
        assert m.composite_5g == 0.0
        assert m.composite_10g == 0.0
        assert m.momentum == 0.0

    def test_custom_values(self):
        m = TeamMetrics(composite_5g=0.5, composite_10g=0.3, momentum=0.2)
        assert m.composite_5g == 0.5
        assert m.composite_10g == 0.3
        assert m.momentum == 0.2

    def test_frozen(self):
        m = TeamMetrics(composite_5g=0.5)
        with pytest.raises(AttributeError):
            m.composite_5g = 1.0  # type: ignore[misc]
