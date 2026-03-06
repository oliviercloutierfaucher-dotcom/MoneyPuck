"""Tests for multi-season data loading and Elo carry-over functionality."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from app.math.elo import EloTracker


def make_game_row(
    home: str,
    away: str,
    home_goals: int,
    away_goals: int,
    date_str: str,
) -> dict[str, str]:
    """Create a synthetic team-gbg format game row."""
    return {
        "playerTeam": home,
        "opposingTeam": away,
        "goalsFor": str(home_goals),
        "goalsAgainst": str(away_goals),
        "gameDate": date_str,
        "home_or_away": "HOME",
        "situation": "all",
        "xGoalsPercentage": "0.50",
        "corsiPercentage": "0.50",
        "fenwickPercentage": "0.50",
        "shotsOnGoalFor": "30",
        "shotsOnGoalAgainst": "28",
        "xGoalsFor": "2.5",
        "xGoalsAgainst": "2.3",
        "highDangerShotsFor": "10",
        "highDangerShotsAgainst": "8",
        "penaltiesFor": "3",
        "penaltiesAgainst": "4",
        "iceTime": "3600",
        "season": "2024",
    }


def _make_season_rows(season_year: int, num_games: int = 5) -> list[dict[str, str]]:
    """Create a set of synthetic game rows for a given season."""
    teams = ["BOS", "TOR", "MTL", "OTT", "DET"]
    rows = []
    for i in range(num_games):
        home = teams[i % len(teams)]
        away = teams[(i + 1) % len(teams)]
        date_str = f"{season_year}10{10 + i:02d}"
        row = make_game_row(home, away, 3, 2, date_str)
        row["season"] = str(season_year)
        rows.append(row)
    return rows


class TestLoadMultipleSeasons(unittest.TestCase):
    """load_seasons() with mocked fetch returns data for multiple seasons, skips 404s."""

    @patch("app.core.multi_season.fetch_team_game_by_game")
    def test_load_multiple_seasons(self, mock_fetch):
        from app.core.multi_season import load_seasons

        # Mock fetch returns data for 2022 and 2023, raises for 2021
        def side_effect(season, teams=None, fallback_to_bulk=False):
            if season == 2021:
                raise HTTPError(
                    url="http://example.com",
                    code=404,
                    msg="Not Found",
                    hdrs=MagicMock(),
                    fp=None,
                )
            return _make_season_rows(season)

        mock_fetch.side_effect = side_effect

        result = load_seasons(start_season=2021, end_season=2023)
        # Should have 2022 and 2023, not 2021
        self.assertIn(2022, result)
        self.assertIn(2023, result)
        self.assertNotIn(2021, result)
        self.assertEqual(len(result[2022]), 5)
        self.assertEqual(len(result[2023]), 5)


class TestGracefulSeasonFallback(unittest.TestCase):
    """load_seasons() handles HTTPError/404 gracefully, returns partial data."""

    @patch("app.core.multi_season.fetch_team_game_by_game")
    def test_graceful_season_fallback(self, mock_fetch):
        from app.core.multi_season import load_seasons

        # All seasons fail except one
        def side_effect(season, teams=None, fallback_to_bulk=False):
            if season == 2020:
                return _make_season_rows(2020, num_games=3)
            raise HTTPError(
                url="http://example.com",
                code=404,
                msg="Not Found",
                hdrs=MagicMock(),
                fp=None,
            )

        mock_fetch.side_effect = side_effect

        result = load_seasons(start_season=2018, end_season=2022)
        # Only 2020 should be present
        self.assertEqual(list(result.keys()), [2020])
        self.assertEqual(len(result[2020]), 3)

    @patch("app.core.multi_season.fetch_team_game_by_game")
    def test_all_seasons_fail_returns_empty(self, mock_fetch):
        from app.core.multi_season import load_seasons

        mock_fetch.side_effect = HTTPError(
            url="http://example.com",
            code=404,
            msg="Not Found",
            hdrs=MagicMock(),
            fp=None,
        )
        result = load_seasons(start_season=2015, end_season=2016)
        self.assertEqual(result, {})


class TestHistoricalTeamCodes(unittest.TestCase):
    """get_teams_for_season() returns correct team lists per era."""

    def test_pre_2024_has_ari_not_uta(self):
        from app.core.multi_season import get_teams_for_season

        teams_2020 = get_teams_for_season(2020)
        self.assertIn("ARI", teams_2020)
        self.assertNotIn("UTA", teams_2020)

    def test_2024_has_uta_not_ari(self):
        from app.core.multi_season import get_teams_for_season

        teams_2024 = get_teams_for_season(2024)
        self.assertIn("UTA", teams_2024)
        self.assertNotIn("ARI", teams_2024)

    def test_pre_2021_excludes_sea(self):
        from app.core.multi_season import get_teams_for_season

        teams_2020 = get_teams_for_season(2020)
        self.assertNotIn("SEA", teams_2020)

    def test_2021_includes_sea(self):
        from app.core.multi_season import get_teams_for_season

        teams_2021 = get_teams_for_season(2021)
        self.assertIn("SEA", teams_2021)

    def test_current_season_matches_nhl_teams(self):
        from app.core.multi_season import get_teams_for_season
        from app.data.data_sources import NHL_TEAMS

        teams_2024 = get_teams_for_season(2024)
        self.assertEqual(sorted(teams_2024), sorted(NHL_TEAMS))


class TestEloCarryOver(unittest.TestCase):
    """backtest_season() with pre-built EloTracker uses those ratings."""

    def test_elo_carry_over(self):
        from app.core.backtester import backtest_season
        from app.core.models import TrackerConfig

        # Create synthetic season data with enough games for training + test
        rows = []
        teams = ["BOS", "TOR", "MTL", "OTT", "DET", "BUF"]
        # Training games (dates early in season)
        for i in range(20):
            home = teams[i % len(teams)]
            away = teams[(i + 1) % len(teams)]
            day = 10 + (i // 3)
            month = 10 + (i // 15)
            date_str = f"2024{month:02d}{day:02d}"
            rows.append(make_game_row(home, away, 3 + (i % 2), 2, date_str))

        # Test games (later dates)
        for i in range(5):
            home = teams[i % len(teams)]
            away = teams[(i + 2) % len(teams)]
            date_str = f"20250115"
            rows.append(make_game_row(home, away, 2 + (i % 3), 1, date_str))

        config = TrackerConfig(odds_api_key="", season=2024)

        # Pre-built tracker with non-default ratings
        pre_built = EloTracker({"BOS": 1600, "TOR": 1550, "MTL": 1450})

        # With elo_tracker, should use those ratings
        preds_with = backtest_season(rows, config, elo_tracker=pre_built)
        # Without elo_tracker, builds fresh
        preds_without = backtest_season(rows, config)

        # Both should produce predictions, but they may differ
        self.assertGreater(len(preds_with), 0)
        self.assertGreater(len(preds_without), 0)

        # If we have matching predictions, the probabilities should differ
        # because the pre-built tracker has non-default ratings
        if preds_with and preds_without:
            # At least some predictions should have different home_prob
            probs_with = [p["home_prob"] for p in preds_with]
            probs_without = [p["home_prob"] for p in preds_without]
            # They should differ (pre-built ratings are non-default)
            if len(probs_with) == len(probs_without):
                diffs = [abs(a - b) for a, b in zip(probs_with, probs_without)]
                self.assertGreater(max(diffs), 0.001,
                    "Pre-built Elo should produce different predictions than fresh Elo")


class TestEloCarryOverRegression(unittest.TestCase):
    """EloTracker.regress_to_mean() brings ratings closer to 1505."""

    def test_elo_regression(self):
        tracker = EloTracker({"BOS": 1600, "TOR": 1400})
        tracker.regress_to_mean()
        ratings = tracker.ratings
        # BOS should be closer to 1505 (was 1600, now ~1552.5)
        self.assertLess(ratings["BOS"], 1600)
        self.assertGreater(ratings["BOS"], 1505)
        # TOR should be closer to 1505 (was 1400, now ~1452.5)
        self.assertGreater(ratings["TOR"], 1400)
        self.assertLess(ratings["TOR"], 1505)


class TestBacktestSeasonBackwardCompatible(unittest.TestCase):
    """backtest_season() without elo_tracker param works as before."""

    def test_backward_compatible(self):
        from app.core.backtester import backtest_season
        from app.core.models import TrackerConfig

        # Create minimal synthetic data
        rows = []
        teams = ["BOS", "TOR", "MTL", "OTT"]
        for i in range(15):
            home = teams[i % len(teams)]
            away = teams[(i + 1) % len(teams)]
            day = 10 + (i // 3)
            month = 10 + (i // 10)
            date_str = f"2024{month:02d}{day:02d}"
            rows.append(make_game_row(home, away, 3, 2, date_str))

        config = TrackerConfig(odds_api_key="", season=2024)

        # Call without elo_tracker -- must work without error
        preds = backtest_season(rows, config)
        self.assertIsInstance(preds, list)


if __name__ == "__main__":
    unittest.main()
