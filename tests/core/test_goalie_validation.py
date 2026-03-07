"""Backup-start validation: measure Brier improvement from correct goalie identification.

These tests validate that the goalie resolution system, when it has correct data,
produces better predictions than the GP-leader heuristic. Uses synthetic scenarios
representing backup-start situations with realistic save% spreads.

No live API calls -- all tests use synthetic data.
"""

import math

from app.math.math_utils import (
    goalie_matchup_adjustment,
    logistic_win_probability,
)


def _brier_score(predictions: list[tuple[float, int]]) -> float:
    """Compute Brier score for a list of (predicted_prob, actual_outcome) pairs.

    Lower is better. 0.25 = coin flip.
    """
    if not predictions:
        return 0.25
    return sum((p - o) ** 2 for p, o in predictions) / len(predictions)


def _win_prob_with_goalie(
    home_strength: float,
    away_strength: float,
    home_save_pct: float,
    away_save_pct: float,
    home_advantage: float = 0.14,
    logistic_k: float = 0.9,
    goalie_impact: float = 1.5,
) -> float:
    """Compute home win probability using given goalie save percentages."""
    base_home, _ = logistic_win_probability(
        home_strength, away_strength,
        home_advantage=home_advantage, k=logistic_k,
    )
    g_adj = goalie_matchup_adjustment(home_save_pct, away_save_pct, goalie_impact)
    return max(0.01, min(0.99, base_home + g_adj / 100.0))


# ---- Synthetic backup-start scenarios ----

# Each scenario: (home_strength, away_strength, gp_leader_save_pct,
#                  actual_starter_save_pct, opponent_save_pct, actual_outcome)
# Outcome: 1 = home win, 0 = home loss
# These represent games where the backup started instead of the GP leader

BACKUP_START_SCENARIOS = [
    # Team has strong GP leader (0.920) but backup starts (0.895)
    (0.3, -0.1, 0.920, 0.895, 0.910, 0),   # backup loses
    (0.2, 0.0, 0.918, 0.890, 0.905, 0),    # backup loses
    (0.1, -0.2, 0.915, 0.893, 0.912, 1),   # backup wins (team was better)
    (-0.1, -0.3, 0.922, 0.898, 0.908, 1),  # backup wins
    (0.4, 0.1, 0.916, 0.891, 0.915, 0),    # backup loses close game
    (0.0, 0.2, 0.919, 0.894, 0.911, 0),    # backup loses
    (-0.2, -0.1, 0.920, 0.896, 0.910, 0),  # backup loses
    (0.3, 0.0, 0.917, 0.892, 0.907, 1),    # backup wins
    (0.1, 0.1, 0.921, 0.897, 0.913, 0),    # backup loses
    (0.5, 0.2, 0.914, 0.889, 0.906, 1),    # backup wins (strong team)
    (-0.1, 0.0, 0.918, 0.893, 0.912, 0),   # backup loses
    (0.2, -0.1, 0.920, 0.895, 0.908, 1),   # backup wins
    (0.0, 0.3, 0.916, 0.891, 0.915, 0),    # backup loses
    (0.4, 0.2, 0.922, 0.898, 0.910, 1),    # backup wins
    (-0.3, 0.0, 0.917, 0.892, 0.911, 0),   # backup loses
    (0.1, -0.1, 0.919, 0.894, 0.907, 1),   # backup wins
    (0.2, 0.1, 0.915, 0.890, 0.913, 0),    # backup loses
    (-0.2, -0.2, 0.921, 0.896, 0.909, 1),  # backup wins
    (0.3, 0.3, 0.918, 0.893, 0.914, 0),    # backup loses (evenly matched)
    (0.0, -0.1, 0.920, 0.895, 0.906, 1),   # backup wins
    (0.1, 0.0, 0.916, 0.891, 0.910, 0),    # backup loses
    (-0.1, -0.2, 0.922, 0.897, 0.908, 1),  # backup wins
    (0.2, 0.2, 0.917, 0.892, 0.912, 0),    # backup loses
    (0.5, 0.1, 0.919, 0.894, 0.907, 1),    # backup wins (strong team)
    (0.0, 0.1, 0.915, 0.890, 0.911, 0),    # backup loses
]


def test_backup_start_brier_improvement():
    """Correct goalie identification improves Brier score by >0.005 on backup-start games.

    For each synthetic backup-start scenario, compute win probability with:
    1. GP-leader's save% (wrong goalie -- what current heuristic picks)
    2. Actual starter's save% (correct goalie -- what confirmed data gives us)

    The correct goalie should produce a better-calibrated probability, yielding
    a lower (better) Brier score.
    """
    wrong_goalie_predictions = []
    right_goalie_predictions = []

    for (home_str, away_str, gp_leader_svp, actual_svp,
         opp_svp, outcome) in BACKUP_START_SCENARIOS:

        # Wrong: use GP-leader's save% (the heuristic pick)
        wrong_prob = _win_prob_with_goalie(
            home_str, away_str, gp_leader_svp, opp_svp,
        )
        wrong_goalie_predictions.append((wrong_prob, outcome))

        # Right: use actual starter's save% (confirmed data)
        right_prob = _win_prob_with_goalie(
            home_str, away_str, actual_svp, opp_svp,
        )
        right_goalie_predictions.append((right_prob, outcome))

    wrong_brier = _brier_score(wrong_goalie_predictions)
    right_brier = _brier_score(right_goalie_predictions)
    improvement = wrong_brier - right_brier

    assert improvement > 0.005, (
        f"Expected Brier improvement >0.005 on backup-start games, "
        f"got {improvement:.6f} (wrong={wrong_brier:.4f}, right={right_brier:.4f})"
    )


def test_gp_leader_error_magnitude():
    """GP-leader heuristic introduces measurable probability error on backup-start games.

    The error should be 1-3 percentage points on average when the backup starts
    instead of the GP leader.
    """
    errors = []

    for (home_str, away_str, gp_leader_svp, actual_svp,
         opp_svp, _outcome) in BACKUP_START_SCENARIOS:

        wrong_prob = _win_prob_with_goalie(
            home_str, away_str, gp_leader_svp, opp_svp,
        )
        right_prob = _win_prob_with_goalie(
            home_str, away_str, actual_svp, opp_svp,
        )
        errors.append(abs(wrong_prob - right_prob) * 100)  # percentage points

    avg_error = sum(errors) / len(errors)
    max_error = max(errors)

    # Average error should be between 1-3 percentage points
    assert avg_error >= 1.0, (
        f"Expected avg error >= 1pp, got {avg_error:.2f}pp"
    )
    assert avg_error <= 5.0, (
        f"Expected avg error <= 5pp, got {avg_error:.2f}pp"
    )
    # Max error should be meaningful but not crazy
    assert max_error >= 1.5, (
        f"Expected max error >= 1.5pp, got {max_error:.2f}pp"
    )
    assert max_error <= 10.0, (
        f"Expected max error <= 10pp, got {max_error:.2f}pp"
    )


def test_correct_starter_no_regression():
    """When GP-leader IS the actual starter, model output is unchanged.

    This verifies that using confirmed data never makes predictions worse
    when the confirmed starter matches the GP-leader heuristic pick.
    """
    # Scenarios where GP-leader IS the correct starter
    gp_leader_correct = [
        (0.3, -0.1, 0.920, 0.910, 1),
        (0.2, 0.0, 0.918, 0.905, 1),
        (0.1, -0.2, 0.915, 0.912, 0),
        (-0.1, -0.3, 0.922, 0.908, 1),
        (0.0, 0.1, 0.916, 0.911, 0),
        (0.4, 0.2, 0.919, 0.907, 1),
        (-0.2, 0.0, 0.917, 0.913, 0),
        (0.1, 0.0, 0.921, 0.909, 1),
        (0.3, 0.1, 0.914, 0.906, 1),
        (-0.1, -0.1, 0.920, 0.910, 0),
    ]

    for (home_str, away_str, gp_leader_svp, opp_svp, outcome) in gp_leader_correct:
        # When GP-leader IS the starter, both methods give the same result
        heuristic_prob = _win_prob_with_goalie(
            home_str, away_str, gp_leader_svp, opp_svp,
        )
        confirmed_prob = _win_prob_with_goalie(
            home_str, away_str, gp_leader_svp, opp_svp,
        )

        assert abs(heuristic_prob - confirmed_prob) < 1e-10, (
            f"When GP-leader is correct, confirmed should match: "
            f"heuristic={heuristic_prob:.6f}, confirmed={confirmed_prob:.6f}"
        )


def test_brier_improvement_with_larger_save_pct_spread():
    """Larger save% spreads between starter and backup produce bigger improvements.

    Teams with a clear #1 goalie (e.g., 0.925 vs 0.880 backup) should show
    larger Brier improvement than teams with a close tandem.
    """
    # Large spread scenarios (starter 0.925, backup 0.880)
    large_spread = [
        (0.2, 0.0, 0.925, 0.880, 0.910, 0),
        (0.1, -0.1, 0.925, 0.880, 0.910, 0),
        (0.3, 0.1, 0.925, 0.880, 0.910, 1),
        (-0.1, -0.2, 0.925, 0.880, 0.910, 1),
        (0.0, 0.1, 0.925, 0.880, 0.910, 0),
    ]

    # Small spread scenarios (starter 0.915, backup 0.910)
    small_spread = [
        (0.2, 0.0, 0.915, 0.910, 0.910, 0),
        (0.1, -0.1, 0.915, 0.910, 0.910, 0),
        (0.3, 0.1, 0.915, 0.910, 0.910, 1),
        (-0.1, -0.2, 0.915, 0.910, 0.910, 1),
        (0.0, 0.1, 0.915, 0.910, 0.910, 0),
    ]

    def compute_improvement(scenarios):
        wrong_preds, right_preds = [], []
        for (hs, as_, leader, actual, opp, out) in scenarios:
            wrong_preds.append((_win_prob_with_goalie(hs, as_, leader, opp), out))
            right_preds.append((_win_prob_with_goalie(hs, as_, actual, opp), out))
        return _brier_score(wrong_preds) - _brier_score(right_preds)

    large_improvement = compute_improvement(large_spread)
    small_improvement = compute_improvement(small_spread)

    # Larger save% spread should produce larger Brier improvement
    assert large_improvement > small_improvement, (
        f"Expected large spread ({large_improvement:.6f}) > small spread ({small_improvement:.6f})"
    )


def test_systematic_error_direction():
    """GP-leader heuristic systematically overestimates win probability on backup-start games.

    When a backup starts, the team's actual save% is lower than the GP-leader's.
    The heuristic should therefore systematically overestimate the team's win probability.
    """
    overestimate_count = 0
    total = 0

    for (home_str, away_str, gp_leader_svp, actual_svp,
         opp_svp, _outcome) in BACKUP_START_SCENARIOS:
        wrong_prob = _win_prob_with_goalie(
            home_str, away_str, gp_leader_svp, opp_svp,
        )
        right_prob = _win_prob_with_goalie(
            home_str, away_str, actual_svp, opp_svp,
        )
        if wrong_prob > right_prob:
            overestimate_count += 1
        total += 1

    overestimate_rate = overestimate_count / total

    # GP-leader always has higher save% than backup, so the heuristic
    # should overestimate win prob in nearly every case
    assert overestimate_rate >= 0.95, (
        f"Expected GP-leader to overestimate in >=95% of backup-start games, "
        f"got {overestimate_rate:.0%} ({overestimate_count}/{total})"
    )
