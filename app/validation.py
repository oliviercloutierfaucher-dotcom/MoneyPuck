"""Phase 4: Model quality validation metrics.

Pure functions — no database dependency.  All functions accept plain Python
types so they can be unit-tested without any database or network access.
"""
from __future__ import annotations

from typing import Any

from .math_utils import american_to_implied_probability


# ---------------------------------------------------------------------------
# Brier score
# ---------------------------------------------------------------------------


def brier_score(predictions: list[tuple[float, int]]) -> float:
    """Mean squared error between predicted probabilities and binary outcomes.

    Parameters
    ----------
    predictions:
        List of ``(model_probability, actual_outcome)`` tuples where
        ``actual_outcome`` is 1 (win) or 0 (loss/push).

    Returns
    -------
    float
        Brier score in [0, 1].  0.0 = perfect, 0.25 = coin-flip baseline,
        1.0 = perfectly wrong.

    Raises
    ------
    ValueError
        If *predictions* is empty.
    """
    if not predictions:
        raise ValueError("predictions list must not be empty")
    total = sum((prob - outcome) ** 2 for prob, outcome in predictions)
    return total / len(predictions)


# ---------------------------------------------------------------------------
# Closing Line Value
# ---------------------------------------------------------------------------


def closing_line_value(bet_odds: int, closing_odds: int) -> float:
    """Closing Line Value (CLV) in percentage points.

    CLV = implied_probability(closing_odds) - implied_probability(bet_odds)

    A *positive* value means we took a better price than the closing market,
    which is the primary indicator of a sharp bet.

    Parameters
    ----------
    bet_odds:
        American odds at which we placed the bet.
    closing_odds:
        American odds at market close (just before game start).

    Returns
    -------
    float
        CLV in percentage points.  Positive = our line was better than close.
    """
    bet_implied = american_to_implied_probability(bet_odds)
    close_implied = american_to_implied_probability(closing_odds)
    # Positive CLV: closing line is *harder* to beat (higher implied prob)
    # than the line we got (lower implied prob at time of bet).
    return (close_implied - bet_implied) * 100.0


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


def calibration_buckets(
    predictions: list[tuple[float, int]],
    n_buckets: int = 10,
) -> list[dict[str, Any]]:
    """Group predictions into equal-width probability buckets.

    Parameters
    ----------
    predictions:
        List of ``(model_probability, actual_outcome)`` tuples.
    n_buckets:
        Number of equal-width buckets between 0 and 1 (default 10).

    Returns
    -------
    list of dict
        Each dict has keys:
        - ``"predicted"`` — bucket midpoint (mean predicted probability)
        - ``"actual"`` — actual win rate within the bucket
        - ``"count"`` — number of predictions in the bucket

    Only buckets with at least one prediction are returned.
    """
    if n_buckets < 1:
        raise ValueError("n_buckets must be >= 1")

    bucket_width = 1.0 / n_buckets
    buckets: dict[int, list[tuple[float, int]]] = {}

    for prob, outcome in predictions:
        # Clamp to [0, n_buckets - 1] so prob=1.0 falls in the last bucket
        idx = min(int(prob / bucket_width), n_buckets - 1)
        buckets.setdefault(idx, []).append((prob, outcome))

    result: list[dict[str, Any]] = []
    for idx in sorted(buckets.keys()):
        bucket = buckets[idx]
        probs = [p for p, _ in bucket]
        outcomes = [o for _, o in bucket]
        result.append(
            {
                "predicted": sum(probs) / len(probs),
                "actual": sum(outcomes) / len(outcomes),
                "count": len(bucket),
            }
        )
    return result


# ---------------------------------------------------------------------------
# ROI summary
# ---------------------------------------------------------------------------


def roi_summary(settled: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute return-on-investment statistics from a list of settled predictions.

    Parameters
    ----------
    settled:
        List of dicts, each containing at least:
        - ``"recommended_stake"`` (float) — amount wagered
        - ``"profit_loss"`` (float) — net P&L (positive = profit)
        - ``"outcome"`` (str) — ``"win"``, ``"loss"``, or ``"push"``

    Returns
    -------
    dict with keys:
        - ``"total_staked"`` — sum of all stakes
        - ``"total_pnl"`` — sum of all profit/loss
        - ``"roi_pct"`` — 100 * total_pnl / total_staked (0.0 if no stake)
        - ``"n_bets"`` — number of settled predictions
        - ``"win_rate"`` — fraction of bets that were wins (0.0 if no bets)
    """
    if not settled:
        return {
            "total_staked": 0.0,
            "total_pnl": 0.0,
            "roi_pct": 0.0,
            "n_bets": 0,
            "win_rate": 0.0,
        }

    total_staked = sum(float(s["recommended_stake"]) for s in settled)
    total_pnl = sum(float(s["profit_loss"]) for s in settled)
    n_bets = len(settled)
    n_wins = sum(1 for s in settled if s.get("outcome") == "win")

    roi_pct = (total_pnl / total_staked * 100.0) if total_staked else 0.0
    win_rate = n_wins / n_bets if n_bets else 0.0

    return {
        "total_staked": round(total_staked, 4),
        "total_pnl": round(total_pnl, 4),
        "roi_pct": round(roi_pct, 4),
        "n_bets": n_bets,
        "win_rate": round(win_rate, 4),
    }


# ---------------------------------------------------------------------------
# Comprehensive health report
# ---------------------------------------------------------------------------


def model_health_report(settled: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce a comprehensive model-quality report suitable for JSON output.

    Combines Brier score, average CLV, ROI summary, and calibration data.

    Parameters
    ----------
    settled:
        List of settled prediction dicts.  Each dict must have all fields
        required by :func:`roi_summary`.  For Brier score and calibration
        the dict additionally needs ``"model_probability"`` and the numeric
        outcome implied by ``"outcome"`` (``"win"`` → 1, otherwise → 0).
        For CLV the dict needs ``"american_odds"`` and ``"closing_odds"``
        (the latter may be ``None``).

    Returns
    -------
    dict with keys:
        - ``"n_settled"`` — total settled bets
        - ``"brier_score"`` — Brier score (``None`` if no data)
        - ``"avg_clv_pp"`` — average CLV in percentage points (``None`` if no closing odds)
        - ``"roi"`` — dict from :func:`roi_summary`
        - ``"calibration"`` — list from :func:`calibration_buckets`
    """
    report: dict[str, Any] = {
        "n_settled": len(settled),
        "brier_score": None,
        "avg_clv_pp": None,
        "roi": roi_summary(settled),
        "calibration": [],
    }

    # Brier score & calibration — need model_probability + binary outcome
    prob_outcome_pairs: list[tuple[float, int]] = []
    for s in settled:
        if "model_probability" not in s:
            continue
        binary = 1 if s.get("outcome") == "win" else 0
        prob_outcome_pairs.append((float(s["model_probability"]), binary))

    if prob_outcome_pairs:
        report["brier_score"] = round(brier_score(prob_outcome_pairs), 6)
        report["calibration"] = calibration_buckets(prob_outcome_pairs)

    # Average CLV — only predictions that have both bet odds and closing odds
    clv_values: list[float] = []
    for s in settled:
        closing = s.get("closing_odds")
        bet = s.get("american_odds")
        if closing is not None and bet is not None:
            try:
                clv_values.append(closing_line_value(int(bet), int(closing)))
            except (ValueError, ZeroDivisionError):
                pass

    if clv_values:
        report["avg_clv_pp"] = round(sum(clv_values) / len(clv_values), 4)

    return report
