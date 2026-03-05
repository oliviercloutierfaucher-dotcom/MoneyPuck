"""Tests for app.math.elo module."""

from __future__ import annotations

import pytest

from app.math.elo import (
    INITIAL_ELO,
    MEAN_ELO,
    autocorrelation_adjustment,
    build_elo_ratings,
    margin_of_victory_multiplier,
    win_probability,
    EloTracker,
)


# ------------------------------------------------------------------ #
# win_probability
# ------------------------------------------------------------------ #

class TestWinProbability:
    def test_equal_teams_fifty_percent(self):
        """Equal Elo ratings should give exactly 0.5."""
        assert win_probability(1500, 1500) == pytest.approx(0.5)

    def test_higher_elo_favored(self):
        """Higher-rated team should have >0.5 win probability."""
        assert win_probability(1600, 1500) > 0.5

    def test_lower_elo_underdog(self):
        """Lower-rated team should have <0.5 win probability."""
        assert win_probability(1400, 1500) < 0.5

    def test_symmetry(self):
        """P(A beats B) + P(B beats A) = 1."""
        p = win_probability(1600, 1450)
        q = win_probability(1450, 1600)
        assert p + q == pytest.approx(1.0)

    def test_400_point_gap(self):
        """A 400-point gap should yield ~0.909 for the stronger team."""
        p = win_probability(1900, 1500)
        assert p == pytest.approx(10.0 / 11.0, abs=0.001)

    def test_returns_between_zero_and_one(self):
        """Probability is always in (0, 1)."""
        for diff in [-1000, -200, 0, 200, 1000]:
            p = win_probability(1500 + diff, 1500)
            assert 0 < p < 1


# ------------------------------------------------------------------ #
# margin_of_victory_multiplier
# ------------------------------------------------------------------ #

class TestMarginOfVictoryMultiplier:
    def test_zero_diff_returns_zero(self):
        """0-goal difference (tie) should give 0 multiplier."""
        assert margin_of_victory_multiplier(0) == 0.0

    def test_negative_diff_returns_zero(self):
        """Negative goal diff should give 0 multiplier."""
        assert margin_of_victory_multiplier(-1) == 0.0

    def test_one_goal_approx_080(self):
        """1-goal win should give approximately 0.80."""
        m = margin_of_victory_multiplier(1)
        assert m == pytest.approx(0.8048, abs=0.01)

    def test_three_goals_approx_154(self):
        """3-goal blowout should give approximately 1.54."""
        m = margin_of_victory_multiplier(3)
        assert m == pytest.approx(1.54, abs=0.02)

    def test_monotonically_increasing(self):
        """Larger goal diffs should give larger multipliers."""
        vals = [margin_of_victory_multiplier(d) for d in range(1, 10)]
        for i in range(len(vals) - 1):
            assert vals[i] < vals[i + 1]

    def test_diminishing_returns(self):
        """Incremental gain should decrease as goal diff increases (log scaling)."""
        m1 = margin_of_victory_multiplier(1)
        m2 = margin_of_victory_multiplier(2)
        m3 = margin_of_victory_multiplier(3)
        m4 = margin_of_victory_multiplier(4)
        # Gain from 1->2 should exceed gain from 3->4
        assert (m2 - m1) > (m4 - m3)


# ------------------------------------------------------------------ #
# autocorrelation_adjustment
# ------------------------------------------------------------------ #

class TestAutocorrelationAdjustment:
    def test_always_positive(self):
        """Adjustment should always be positive."""
        for diff in [0, 50, 100, 200, 500]:
            assert autocorrelation_adjustment(diff) > 0

    def test_zero_diff_returns_one(self):
        """When winner_elo_diff is 0, adjustment should be 1.0."""
        assert autocorrelation_adjustment(0) == pytest.approx(1.0)

    def test_dampens_large_favorites(self):
        """Large positive diff (strong favorite won) should reduce gain (<1)."""
        adj = autocorrelation_adjustment(200)
        assert adj < 1.0

    def test_larger_diff_more_dampened(self):
        """Bigger elo diff should produce more dampening."""
        adj_small = autocorrelation_adjustment(100)
        adj_large = autocorrelation_adjustment(300)
        assert adj_large < adj_small

    def test_at_most_one_for_positive_diff(self):
        """For any positive diff the adjustment should be <= 1.0."""
        for diff in [1, 10, 100, 500, 1000]:
            assert autocorrelation_adjustment(diff) <= 1.0


# ------------------------------------------------------------------ #
# EloTracker.get
# ------------------------------------------------------------------ #

class TestEloTrackerGet:
    def test_unknown_team_returns_initial(self):
        """Unknown team should return INITIAL_ELO (1500)."""
        tracker = EloTracker()
        assert tracker.get("UnknownTeam") == INITIAL_ELO

    def test_initialized_team_returns_rating(self):
        """Team set via initial_ratings should return that value."""
        tracker = EloTracker(initial_ratings={"BOS": 1550})
        assert tracker.get("BOS") == 1550

    def test_multiple_unknowns_same_default(self):
        """All unknown teams start at the same default."""
        tracker = EloTracker()
        assert tracker.get("AAA") == tracker.get("BBB") == INITIAL_ELO


# ------------------------------------------------------------------ #
# EloTracker.update
# ------------------------------------------------------------------ #

class TestEloTrackerUpdate:
    def test_winner_gains_elo(self):
        """Home team winning should increase their Elo."""
        tracker = EloTracker()
        new_home, _ = tracker.update("HOME", "AWAY", 3, 1)
        assert new_home > INITIAL_ELO

    def test_loser_loses_elo(self):
        """Away team losing should decrease their Elo."""
        tracker = EloTracker()
        _, new_away = tracker.update("HOME", "AWAY", 3, 1)
        assert new_away < INITIAL_ELO

    def test_zero_sum(self):
        """Elo changes should be zero-sum: winner gain == loser loss."""
        tracker = EloTracker()
        new_home, new_away = tracker.update("HOME", "AWAY", 4, 2)
        home_change = new_home - INITIAL_ELO
        away_change = new_away - INITIAL_ELO
        assert home_change + away_change == pytest.approx(0.0)

    def test_away_win_updates_correctly(self):
        """Away team winning should increase away Elo and decrease home."""
        tracker = EloTracker()
        new_home, new_away = tracker.update("HOME", "AWAY", 1, 3)
        assert new_home < INITIAL_ELO
        assert new_away > INITIAL_ELO

    def test_larger_margin_bigger_shift(self):
        """A 5-1 win should produce a larger shift than a 2-1 win."""
        t1 = EloTracker()
        h1, _ = t1.update("H", "A", 2, 1)
        t2 = EloTracker()
        h2, _ = t2.update("H", "A", 5, 1)
        assert abs(h2 - INITIAL_ELO) > abs(h1 - INITIAL_ELO)

    def test_consecutive_updates_accumulate(self):
        """Multiple wins should accumulate Elo gains."""
        tracker = EloTracker()
        tracker.update("STRONG", "WEAK", 3, 1)
        tracker.update("STRONG", "WEAK", 2, 0)
        tracker.update("STRONG", "WEAK", 4, 2)
        assert tracker.get("STRONG") > INITIAL_ELO
        assert tracker.get("WEAK") < INITIAL_ELO


# ------------------------------------------------------------------ #
# EloTracker.predict
# ------------------------------------------------------------------ #

class TestEloTrackerPredict:
    def test_home_advantage_equal_teams(self):
        """Equal-rated teams: home should be predicted >50% due to HFA."""
        tracker = EloTracker()
        p = tracker.predict("HOME", "AWAY")
        assert p > 0.5

    def test_prediction_range(self):
        """Prediction should always be in (0, 1)."""
        tracker = EloTracker(initial_ratings={"A": 1300, "B": 1700})
        p = tracker.predict("A", "B")
        assert 0 < p < 1

    def test_stronger_home_team_higher_prob(self):
        """Stronger home team should have a higher win probability."""
        tracker = EloTracker(initial_ratings={"STRONG": 1600, "WEAK": 1400})
        p = tracker.predict("STRONG", "WEAK")
        assert p > 0.7  # 200-point gap + home advantage

    def test_weak_home_team_can_be_underdog(self):
        """A sufficiently weak home team should still be <50%."""
        tracker = EloTracker(initial_ratings={"WEAK": 1300, "STRONG": 1700})
        p = tracker.predict("WEAK", "STRONG")
        assert p < 0.5


# ------------------------------------------------------------------ #
# EloTracker.regress_to_mean
# ------------------------------------------------------------------ #

class TestRegressToMean:
    def test_high_rating_moves_down(self):
        """A rating above MEAN_ELO should decrease after regression."""
        tracker = EloTracker(initial_ratings={"A": 1600})
        tracker.regress_to_mean()
        assert tracker.get("A") < 1600

    def test_low_rating_moves_up(self):
        """A rating below MEAN_ELO should increase after regression."""
        tracker = EloTracker(initial_ratings={"A": 1400})
        tracker.regress_to_mean()
        assert tracker.get("A") > 1400

    def test_moves_toward_mean(self):
        """After regression, rating should be closer to MEAN_ELO."""
        tracker = EloTracker(initial_ratings={"A": 1600})
        old_dist = abs(1600 - MEAN_ELO)
        tracker.regress_to_mean()
        new_dist = abs(tracker.get("A") - MEAN_ELO)
        assert new_dist < old_dist

    def test_50_percent_regression(self):
        """Rating should move exactly 50% toward MEAN_ELO."""
        tracker = EloTracker(initial_ratings={"A": 1600})
        tracker.regress_to_mean()
        expected = 0.5 * MEAN_ELO + 0.5 * 1600
        assert tracker.get("A") == pytest.approx(expected)

    def test_mean_rating_unchanged(self):
        """A team at MEAN_ELO should stay at MEAN_ELO after regression."""
        tracker = EloTracker(initial_ratings={"A": MEAN_ELO})
        tracker.regress_to_mean()
        assert tracker.get("A") == pytest.approx(MEAN_ELO)


# ------------------------------------------------------------------ #
# EloTracker.ratings property
# ------------------------------------------------------------------ #

class TestRatingsProperty:
    def test_returns_dict(self):
        tracker = EloTracker(initial_ratings={"A": 1500, "B": 1550})
        r = tracker.ratings
        assert isinstance(r, dict)
        assert "A" in r and "B" in r

    def test_returns_copy(self):
        """Mutating the returned dict should not affect internal state."""
        tracker = EloTracker(initial_ratings={"A": 1500})
        r = tracker.ratings
        r["A"] = 9999
        assert tracker.get("A") == 1500


# ------------------------------------------------------------------ #
# build_elo_ratings - team-gbg format
# ------------------------------------------------------------------ #

def _make_team_gbg_row(
    home: str,
    away: str,
    home_goals: int,
    away_goals: int,
    date: str = "2024-01-15",
    is_home: bool = True,
    situation: str = "all",
) -> dict:
    """Build a minimal MoneyPuck team-gbg row."""
    return {
        "playerTeam": home if is_home else away,
        "opposingTeam": away if is_home else home,
        "goalsFor": home_goals if is_home else away_goals,
        "goalsAgainst": away_goals if is_home else home_goals,
        "home_or_away": "HOME" if is_home else "AWAY",
        "situation": situation,
        "gameDate": date,
    }


class TestBuildEloRatingsTeamGBG:
    def test_processes_home_rows_only(self):
        """Only HOME rows with situation=all should be processed."""
        games = [
            _make_team_gbg_row("BOS", "TOR", 3, 1, is_home=True),
            _make_team_gbg_row("BOS", "TOR", 3, 1, is_home=False),  # AWAY duplicate
        ]
        tracker = build_elo_ratings(games)
        # Should have processed exactly one game
        assert tracker.get("BOS") > INITIAL_ELO
        assert tracker.get("TOR") < INITIAL_ELO

    def test_filters_situation_all(self):
        """Rows with situation != 'all' should be skipped."""
        games = [
            _make_team_gbg_row("BOS", "TOR", 3, 1, situation="5on5"),
        ]
        tracker = build_elo_ratings(games)
        # No games processed, both at initial
        assert tracker.get("BOS") == INITIAL_ELO
        assert tracker.get("TOR") == INITIAL_ELO

    def test_deduplicates_games(self):
        """Duplicate games (same date-home-away) should be processed once."""
        row = _make_team_gbg_row("BOS", "TOR", 4, 2, date="2024-01-15")
        games = [row, row.copy()]
        tracker = build_elo_ratings(games)
        # Process once: get the shift from a single game
        single_tracker = build_elo_ratings([row])
        assert tracker.get("BOS") == pytest.approx(single_tracker.get("BOS"))

    def test_chronological_ordering_matters(self):
        """Games should be processed in date order regardless of input order."""
        # Game 1: BOS beats TOR on Jan 10
        # Game 2: TOR beats BOS on Jan 20
        g1 = _make_team_gbg_row("BOS", "TOR", 3, 1, date="2024-01-10")
        g2 = _make_team_gbg_row("TOR", "BOS", 3, 1, date="2024-01-20")
        # Feed in reverse order
        tracker_reversed = build_elo_ratings([g2, g1])
        tracker_ordered = build_elo_ratings([g1, g2])
        assert tracker_reversed.get("BOS") == pytest.approx(tracker_ordered.get("BOS"))
        assert tracker_reversed.get("TOR") == pytest.approx(tracker_ordered.get("TOR"))

    def test_ties_skipped(self):
        """Tied games should be skipped (no Elo change)."""
        games = [_make_team_gbg_row("BOS", "TOR", 2, 2)]
        tracker = build_elo_ratings(games)
        assert tracker.get("BOS") == INITIAL_ELO
        assert tracker.get("TOR") == INITIAL_ELO

    def test_empty_games_list(self):
        """Empty input should return a fresh tracker."""
        tracker = build_elo_ratings([])
        assert isinstance(tracker, EloTracker)


# ------------------------------------------------------------------ #
# build_elo_ratings - alternative format
# ------------------------------------------------------------------ #

class TestBuildEloRatingsAltFormat:
    def test_alt_format_keys(self):
        """Should process homeTeamCode / awayTeamCode format."""
        games = [
            {
                "homeTeamCode": "BOS",
                "awayTeamCode": "TOR",
                "home_goals": 4,
                "away_goals": 1,
                "gameDate": "2024-02-01",
            },
        ]
        tracker = build_elo_ratings(games)
        assert tracker.get("BOS") > INITIAL_ELO
        assert tracker.get("TOR") < INITIAL_ELO


# ------------------------------------------------------------------ #
# Integration: strong teams rise over many games
# ------------------------------------------------------------------ #

class TestIntegration:
    def test_strong_team_rises(self):
        """A team that consistently wins should have higher Elo than losers."""
        games = []
        for i in range(15):
            date = f"2024-01-{i + 1:02d}"
            games.append(_make_team_gbg_row("STRONG", "WEAK", 4, 1, date=date))
        tracker = build_elo_ratings(games)
        assert tracker.get("STRONG") > tracker.get("WEAK")
        assert tracker.get("STRONG") > INITIAL_ELO
        assert tracker.get("WEAK") < INITIAL_ELO

    def test_multiple_teams_ordering(self):
        """After many games, team rankings should reflect win records."""
        games = []
        # BEST beats MID, MID beats WORST
        for i in range(10):
            d = f"2024-02-{i + 1:02d}"
            games.append(_make_team_gbg_row("BEST", "MID", 3, 1, date=d))
        for i in range(10):
            d = f"2024-03-{i + 1:02d}"
            games.append(_make_team_gbg_row("MID", "WORST", 3, 1, date=d))
        tracker = build_elo_ratings(games)
        assert tracker.get("BEST") > tracker.get("MID")
        assert tracker.get("MID") > tracker.get("WORST")

    def test_zero_sum_across_league(self):
        """Total Elo across all teams should equal num_teams * INITIAL_ELO."""
        games = []
        teams = ["A", "B", "C", "D"]
        matchups = [("A", "B", 3, 1), ("C", "D", 2, 0), ("A", "C", 1, 0), ("B", "D", 4, 2)]
        for i, (h, a, hg, ag) in enumerate(matchups):
            games.append(_make_team_gbg_row(h, a, hg, ag, date=f"2024-01-{i + 1:02d}"))
        tracker = build_elo_ratings(games)
        total = sum(tracker.get(t) for t in teams)
        assert total == pytest.approx(len(teams) * INITIAL_ELO)

    def test_regress_then_continue(self):
        """Regression between seasons followed by more games should work."""
        games_s1 = []
        for i in range(5):
            games_s1.append(_make_team_gbg_row("A", "B", 3, 1, date=f"2024-01-{i + 1:02d}"))
        tracker = build_elo_ratings(games_s1)
        elo_before = tracker.get("A")
        tracker.regress_to_mean()
        elo_after_regress = tracker.get("A")
        # After regression the rating should be closer to mean
        assert abs(elo_after_regress - MEAN_ELO) < abs(elo_before - MEAN_ELO)
        # Can still update after regression
        tracker.update("A", "B", 4, 0)
        assert tracker.get("A") > elo_after_regress
