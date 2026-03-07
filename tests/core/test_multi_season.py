"""Tests for multi-season data loading, walk-forward validation, and verdict logic.

Uses synthetic data and mocks throughout -- no network calls.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from app.math.elo import EloTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_season_rows(season_year: int, num_games: int = 20) -> list[dict[str, str]]:
    """Create a set of synthetic game rows for a given season."""
    teams = ["BOS", "TOR", "MTL", "OTT", "DET"]
    rows = []
    for i in range(num_games):
        home = teams[i % len(teams)]
        away = teams[(i + 1) % len(teams)]
        day = 10 + (i % 20)
        month = 10 + (i // 20)
        date_str = f"{season_year}{month:02d}{day:02d}"
        row = make_game_row(home, away, 3 + (i % 2), 2, date_str)
        row["season"] = str(season_year)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Controlled mock return values for walk-forward tests
# ---------------------------------------------------------------------------

def _mock_eval_predictions(predictions):
    """Return controlled evaluation metrics."""
    return {
        "brier_score": 0.240,
        "log_loss": 0.68,
        "accuracy": 0.58,
        "calibration": [],
        "n_predictions": len(predictions) if predictions else 20,
        "home_bias": 0.01,
    }


def _mock_simulate_roi(predictions, **kwargs):
    """Return controlled ROI metrics."""
    return {
        "total_bets": 50,
        "total_staked": 500.0,
        "final_bankroll": 1100.0,
        "roi_pct": 5.2,
        "win_rate": 0.58,
        "avg_edge": 3.1,
        "max_drawdown_pct": 8.0,
        "bets_by_month": {},
    }


# ===================================================================
# Plan 01 Tests: Data loading, team codes, Elo carry-over
# ===================================================================

class TestLoadMultipleSeasons(unittest.TestCase):
    """load_seasons() with mocked fetch returns data for multiple seasons, skips 404s."""

    @patch("app.core.multi_season.fetch_team_game_by_game")
    def test_load_multiple_seasons(self, mock_fetch):
        from app.core.multi_season import load_seasons

        def side_effect(season, teams=None, fallback_to_bulk=False):
            if season == 2021:
                raise HTTPError(
                    url="http://example.com", code=404, msg="Not Found",
                    hdrs=MagicMock(), fp=None,
                )
            return _make_season_rows(season)

        mock_fetch.side_effect = side_effect

        result = load_seasons(start_season=2021, end_season=2023)
        self.assertIn(2022, result)
        self.assertIn(2023, result)
        self.assertNotIn(2021, result)
        self.assertEqual(len(result[2022]), 20)
        self.assertEqual(len(result[2023]), 20)


class TestGracefulSeasonFallback(unittest.TestCase):
    """load_seasons() handles HTTPError/404 gracefully, returns partial data."""

    @patch("app.core.multi_season.fetch_team_game_by_game")
    def test_graceful_season_fallback(self, mock_fetch):
        from app.core.multi_season import load_seasons

        def side_effect(season, teams=None, fallback_to_bulk=False):
            if season == 2020:
                return _make_season_rows(2020, num_games=3)
            raise HTTPError(
                url="http://example.com", code=404, msg="Not Found",
                hdrs=MagicMock(), fp=None,
            )

        mock_fetch.side_effect = side_effect

        result = load_seasons(start_season=2018, end_season=2022)
        self.assertEqual(list(result.keys()), [2020])
        self.assertEqual(len(result[2020]), 3)

    @patch("app.core.multi_season.fetch_team_game_by_game")
    def test_all_seasons_fail_returns_empty(self, mock_fetch):
        from app.core.multi_season import load_seasons

        mock_fetch.side_effect = HTTPError(
            url="http://example.com", code=404, msg="Not Found",
            hdrs=MagicMock(), fp=None,
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

        rows = []
        teams = ["BOS", "TOR", "MTL", "OTT", "DET", "BUF"]
        for i in range(20):
            home = teams[i % len(teams)]
            away = teams[(i + 1) % len(teams)]
            day = 10 + (i // 3)
            month = 10 + (i // 15)
            date_str = f"2024{month:02d}{day:02d}"
            rows.append(make_game_row(home, away, 3 + (i % 2), 2, date_str))

        for i in range(5):
            home = teams[i % len(teams)]
            away = teams[(i + 2) % len(teams)]
            date_str = "20250115"
            rows.append(make_game_row(home, away, 2 + (i % 3), 1, date_str))

        config = TrackerConfig(odds_api_key="", season=2024)
        pre_built = EloTracker({"BOS": 1600, "TOR": 1550, "MTL": 1450})

        preds_with = backtest_season(rows, config, elo_tracker=pre_built)
        preds_without = backtest_season(rows, config)

        self.assertGreater(len(preds_with), 0)
        self.assertGreater(len(preds_without), 0)

        if preds_with and preds_without and len(preds_with) == len(preds_without):
            probs_with = [p["home_prob"] for p in preds_with]
            probs_without = [p["home_prob"] for p in preds_without]
            diffs = [abs(a - b) for a, b in zip(probs_with, probs_without)]
            self.assertGreater(max(diffs), 0.001,
                "Pre-built Elo should produce different predictions than fresh Elo")


class TestEloCarryOverRegression(unittest.TestCase):
    """EloTracker.regress_to_mean() brings ratings closer to 1505."""

    def test_elo_regression(self):
        tracker = EloTracker({"BOS": 1600, "TOR": 1400})
        tracker.regress_to_mean()
        ratings = tracker.ratings
        self.assertLess(ratings["BOS"], 1600)
        self.assertGreater(ratings["BOS"], 1505)
        self.assertGreater(ratings["TOR"], 1400)
        self.assertLess(ratings["TOR"], 1505)


class TestBacktestSeasonBackwardCompatible(unittest.TestCase):
    """backtest_season() without elo_tracker param works as before."""

    def test_backward_compatible(self):
        from app.core.backtester import backtest_season
        from app.core.models import TrackerConfig

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
        preds = backtest_season(rows, config)
        self.assertIsInstance(preds, list)


# ===================================================================
# Plan 02 Tests: Walk-forward orchestrator, stability, verdict
# ===================================================================

class TestWalkForwardFixedParams(unittest.TestCase):

    @patch("app.core.multi_season.simulate_betting_roi", side_effect=_mock_simulate_roi)
    @patch("app.core.multi_season.evaluate_predictions", side_effect=_mock_eval_predictions)
    @patch("app.core.multi_season.backtest_season")
    @patch("app.core.multi_season.load_seasons")
    def test_walk_forward_fixed_params(self, mock_load, mock_bt, mock_eval, mock_roi):
        from app.core.multi_season import validate_multi_season

        mock_load.return_value = {
            2022: _make_season_rows(2022),
            2023: _make_season_rows(2023),
            2024: _make_season_rows(2024),
        }
        mock_bt.return_value = [{"home_prob": 0.6, "actual_outcome": 1}] * 20

        config = MagicMock()
        result = validate_multi_season(config=config, mode="fixed",
                                        start_season=2022, end_season=2024)

        self.assertEqual(result["mode"], "fixed")
        self.assertEqual(len(result["season_results"]), 3)
        self.assertTrue(result["overall_pass"])


class TestWalkForwardEloCarryOver(unittest.TestCase):

    @patch("app.core.multi_season.simulate_betting_roi", side_effect=_mock_simulate_roi)
    @patch("app.core.multi_season.evaluate_predictions", side_effect=_mock_eval_predictions)
    @patch("app.core.multi_season.backtest_season")
    @patch("app.core.multi_season.load_seasons")
    def test_walk_forward_elo_carry_over(self, mock_load, mock_bt, mock_eval, mock_roi):
        """Elo tracker is carried between seasons with regress_to_mean()."""
        from app.core.multi_season import validate_multi_season

        mock_load.return_value = {
            2022: _make_season_rows(2022),
            2023: _make_season_rows(2023),
        }
        mock_bt.return_value = [{"home_prob": 0.6, "actual_outcome": 1}] * 20

        config = MagicMock()
        result = validate_multi_season(config=config, mode="fixed",
                                        start_season=2022, end_season=2023)

        for call in mock_bt.call_args_list:
            self.assertIn("elo_tracker", call.kwargs)


class TestWalkForwardGridSearch(unittest.TestCase):

    @patch("app.core.multi_season.grid_search")
    @patch("app.core.multi_season.simulate_betting_roi", side_effect=_mock_simulate_roi)
    @patch("app.core.multi_season.evaluate_predictions", side_effect=_mock_eval_predictions)
    @patch("app.core.multi_season.backtest_season")
    @patch("app.core.multi_season.load_seasons")
    def test_walk_forward_grid_search(self, mock_load, mock_bt, mock_eval, mock_roi, mock_gs):
        from app.core.multi_season import validate_multi_season

        mock_load.return_value = {
            2022: _make_season_rows(2022),
            2023: _make_season_rows(2023),
        }
        mock_bt.return_value = [{"home_prob": 0.6, "actual_outcome": 1}] * 20
        mock_gs.return_value = [{
            "params": {"half_life": 30, "regression_k": 20,
                       "home_advantage": 0.14, "logistic_k": 0.9},
            "brier_score": 0.240,
        }]

        config = MagicMock()
        result = validate_multi_season(config=config, mode="grid_search",
                                        start_season=2022, end_season=2023)

        self.assertEqual(result["mode"], "grid_search")
        self.assertIn("param_stability", result)
        self.assertIn("verdict", result)
        mock_gs.assert_called()


class TestParameterStability(unittest.TestCase):

    def test_parameter_stability_uniform(self):
        from app.core.multi_season import analyze_parameter_stability

        per_season_optimal = {
            2022: {"half_life": 30, "regression_k": 20,
                   "home_advantage": 0.14, "logistic_k": 0.9},
            2023: {"half_life": 30, "regression_k": 20,
                   "home_advantage": 0.14, "logistic_k": 0.9},
            2024: {"half_life": 30, "regression_k": 20,
                   "home_advantage": 0.14, "logistic_k": 0.9},
        }
        stability = analyze_parameter_stability(per_season_optimal)

        self.assertIn("half_life", stability)
        self.assertIn("mean", stability["half_life"])
        self.assertIn("stdev", stability["half_life"])
        self.assertIn("min", stability["half_life"])
        self.assertIn("max", stability["half_life"])
        self.assertIn("coefficient_of_variation", stability["half_life"])
        self.assertAlmostEqual(stability["half_life"]["mean"], 30.0)
        self.assertAlmostEqual(stability["half_life"]["coefficient_of_variation"], 0.0)

    def test_parameter_stability_varying(self):
        from app.core.multi_season import analyze_parameter_stability

        per_season_optimal = {
            2022: {"half_life": 21, "regression_k": 15,
                   "home_advantage": 0.10, "logistic_k": 0.7},
            2023: {"half_life": 45, "regression_k": 25,
                   "home_advantage": 0.20, "logistic_k": 1.2},
        }
        stability = analyze_parameter_stability(per_season_optimal)
        self.assertGreater(stability["half_life"]["coefficient_of_variation"], 0.1)


class TestVerdict(unittest.TestCase):

    def test_verdict_stable(self):
        from app.core.multi_season import determine_verdict

        results = [
            {"season": 2022, "accuracy": 0.58, "roi_pct": 5.0},
            {"season": 2023, "accuracy": 0.56, "roi_pct": 3.0},
        ]
        stability = {
            "half_life": {"coefficient_of_variation": 0.05},
            "regression_k": {"coefficient_of_variation": 0.05},
            "home_advantage": {"coefficient_of_variation": 0.05},
            "logistic_k": {"coefficient_of_variation": 0.05},
        }
        verdict = determine_verdict(results, stability)
        self.assertIn("STABLE", verdict)

    def test_verdict_overfit(self):
        from app.core.multi_season import determine_verdict

        results = [
            {"season": 2022, "accuracy": 0.58, "roi_pct": 5.0},
            {"season": 2023, "accuracy": 0.50, "roi_pct": -2.0},
        ]
        verdict = determine_verdict(results)
        self.assertIn("OVERFIT", verdict)

    def test_verdict_drift(self):
        from app.core.multi_season import determine_verdict

        results = [
            {"season": 2022, "accuracy": 0.58, "roi_pct": 5.0},
            {"season": 2023, "accuracy": 0.57, "roi_pct": 4.0},
        ]
        stability = {
            "half_life": {"coefficient_of_variation": 0.40},
            "regression_k": {"coefficient_of_variation": 0.05},
            "home_advantage": {"coefficient_of_variation": 0.05},
            "logistic_k": {"coefficient_of_variation": 0.05},
        }
        verdict = determine_verdict(results, stability)
        self.assertIn("DRIFT", verdict)


class TestCovidSeasonFlag(unittest.TestCase):

    @patch("app.core.multi_season.simulate_betting_roi", side_effect=_mock_simulate_roi)
    @patch("app.core.multi_season.evaluate_predictions", side_effect=_mock_eval_predictions)
    @patch("app.core.multi_season.backtest_season")
    @patch("app.core.multi_season.load_seasons")
    def test_covid_season_flag(self, mock_load, mock_bt, mock_eval, mock_roi):
        from app.core.multi_season import validate_multi_season

        mock_load.return_value = {
            2019: _make_season_rows(2019),
            2020: _make_season_rows(2020),
            2021: _make_season_rows(2021),
        }
        mock_bt.return_value = [{"home_prob": 0.6, "actual_outcome": 1}] * 20

        config = MagicMock()
        result = validate_multi_season(config=config, mode="fixed",
                                        start_season=2019, end_season=2021)

        covid_result = [r for r in result["season_results"]
                        if r["season"] == 2020][0]
        self.assertTrue(covid_result["is_covid"])

        non_covid = [r for r in result["season_results"]
                     if r["season"] != 2020]
        for r in non_covid:
            self.assertFalse(r["is_covid"])


class TestPerSeasonMetrics(unittest.TestCase):

    @patch("app.core.multi_season.simulate_betting_roi", side_effect=_mock_simulate_roi)
    @patch("app.core.multi_season.evaluate_predictions", side_effect=_mock_eval_predictions)
    @patch("app.core.multi_season.backtest_season")
    @patch("app.core.multi_season.load_seasons")
    def test_per_season_metrics(self, mock_load, mock_bt, mock_eval, mock_roi):
        from app.core.multi_season import validate_multi_season

        mock_load.return_value = {2023: _make_season_rows(2023)}
        mock_bt.return_value = [{"home_prob": 0.6, "actual_outcome": 1}] * 20

        config = MagicMock()
        result = validate_multi_season(config=config, mode="fixed",
                                        start_season=2023, end_season=2023)

        sr = result["season_results"][0]
        self.assertIn("brier_score", sr)
        self.assertIn("accuracy", sr)
        self.assertIn("roi_pct", sr)
        self.assertIn("n_predictions", sr)
        self.assertIn("win_rate", sr)


class TestStrictPassFail(unittest.TestCase):

    @patch("app.core.multi_season.simulate_betting_roi")
    @patch("app.core.multi_season.evaluate_predictions")
    @patch("app.core.multi_season.backtest_season")
    @patch("app.core.multi_season.load_seasons")
    def test_negative_roi_fails(self, mock_load, mock_bt, mock_eval, mock_roi):
        from app.core.multi_season import validate_multi_season

        mock_load.return_value = {
            2022: _make_season_rows(2022),
            2023: _make_season_rows(2023),
        }
        mock_bt.return_value = [{"home_prob": 0.6, "actual_outcome": 1}] * 20
        mock_eval.side_effect = [
            {"brier_score": 0.24, "accuracy": 0.58, "n_predictions": 20,
             "log_loss": 0.68, "calibration": [], "home_bias": 0.01},
            {"brier_score": 0.24, "accuracy": 0.58, "n_predictions": 20,
             "log_loss": 0.68, "calibration": [], "home_bias": 0.01},
        ]
        mock_roi.side_effect = [
            {"total_bets": 50, "roi_pct": 5.0, "win_rate": 0.58,
             "total_staked": 500, "final_bankroll": 1100,
             "avg_edge": 3.0, "max_drawdown_pct": 8.0, "bets_by_month": {}},
            {"total_bets": 50, "roi_pct": -3.0, "win_rate": 0.48,
             "total_staked": 500, "final_bankroll": 900,
             "avg_edge": 1.0, "max_drawdown_pct": 15.0, "bets_by_month": {}},
        ]

        config = MagicMock()
        result = validate_multi_season(config=config, mode="fixed",
                                        start_season=2022, end_season=2023)
        self.assertFalse(result["overall_pass"])

    @patch("app.core.multi_season.simulate_betting_roi")
    @patch("app.core.multi_season.evaluate_predictions")
    @patch("app.core.multi_season.backtest_season")
    @patch("app.core.multi_season.load_seasons")
    def test_low_win_rate_fails(self, mock_load, mock_bt, mock_eval, mock_roi):
        from app.core.multi_season import validate_multi_season

        mock_load.return_value = {2022: _make_season_rows(2022)}
        mock_bt.return_value = [{"home_prob": 0.6, "actual_outcome": 1}] * 20
        mock_eval.return_value = {
            "brier_score": 0.24, "accuracy": 0.50, "n_predictions": 20,
            "log_loss": 0.68, "calibration": [], "home_bias": 0.01,
        }
        mock_roi.return_value = {
            "total_bets": 50, "roi_pct": 5.0, "win_rate": 0.50,
            "total_staked": 500, "final_bankroll": 1100,
            "avg_edge": 3.0, "max_drawdown_pct": 8.0, "bets_by_month": {},
        }

        config = MagicMock()
        result = validate_multi_season(config=config, mode="fixed",
                                        start_season=2022, end_season=2022)
        self.assertFalse(result["overall_pass"])


class TestFormatMultiSeasonReport(unittest.TestCase):
    """format_multi_season_report() produces readable output."""

    def test_report_contains_verdict(self):
        from app.core.multi_season import format_multi_season_report

        results = {
            "mode": "grid_search",
            "config_used": {
                "half_life": 30, "regression_k": 20,
                "home_advantage": 0.14, "logistic_k": 0.9,
            },
            "season_results": [
                {"season": 2022, "n_predictions": 400, "accuracy": 0.58,
                 "brier_score": 0.240, "roi_pct": 5.2, "win_rate": 0.58,
                 "is_covid": False},
            ],
            "overall_pass": True,
            "param_stability": {
                "half_life": {"mean": 30, "stdev": 0, "min": 30,
                              "max": 30, "coefficient_of_variation": 0.0},
            },
            "verdict": "VERDICT: Parameters are STABLE across seasons",
        }
        report = format_multi_season_report(results)
        self.assertIn("VERDICT:", report)
        self.assertIn("STABLE", report)
        self.assertIn("2022", report)
        self.assertIn("MULTI-SEASON VALIDATION REPORT", report)

    def test_report_covid_flag(self):
        from app.core.multi_season import format_multi_season_report

        results = {
            "mode": "fixed",
            "config_used": {"half_life": 30, "regression_k": 20,
                           "home_advantage": 0.14, "logistic_k": 0.9},
            "season_results": [
                {"season": 2020, "n_predictions": 200, "accuracy": 0.56,
                 "brier_score": 0.245, "roi_pct": 2.0, "win_rate": 0.56,
                 "is_covid": True},
            ],
            "overall_pass": True,
        }
        report = format_multi_season_report(results)
        self.assertIn("COVID", report)

    def test_report_per_season_rows(self):
        from app.core.multi_season import format_multi_season_report

        results = {
            "mode": "fixed",
            "config_used": {"half_life": 30, "regression_k": 20,
                           "home_advantage": 0.14, "logistic_k": 0.9},
            "season_results": [
                {"season": 2022, "n_predictions": 400, "accuracy": 0.58,
                 "brier_score": 0.240, "roi_pct": 5.2, "win_rate": 0.58,
                 "is_covid": False},
                {"season": 2023, "n_predictions": 410, "accuracy": 0.57,
                 "brier_score": 0.241, "roi_pct": 4.0, "win_rate": 0.57,
                 "is_covid": False},
            ],
            "overall_pass": True,
        }
        report = format_multi_season_report(results)
        self.assertIn("2022", report)
        self.assertIn("2023", report)
        self.assertIn("PASS", report)


class TestCLIArgParsing(unittest.TestCase):
    """--validate-seasons CLI flag is recognized."""

    def test_validate_seasons_flag(self):
        from tracker import parse_args
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["tracker.py", "--validate-seasons",
                        "--odds-api-key", "test"]
            args = parse_args()
            self.assertTrue(args.validate_seasons)
        finally:
            sys.argv = original_argv

    def test_validate_seasons_with_json(self):
        from tracker import parse_args
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["tracker.py", "--validate-seasons", "--json",
                        "--odds-api-key", "test"]
            args = parse_args()
            self.assertTrue(args.validate_seasons)
            self.assertTrue(args.json)
        finally:
            sys.argv = original_argv


if __name__ == "__main__":
    unittest.main()
