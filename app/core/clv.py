"""Closing Line Value (CLV) calculations for MoneyPuck NHL betting tracker.

CLV measures whether a bet was placed at better odds than the closing line —
the market's final price just before a game starts.  Consistently beating the
closing line is the strongest long-run indicator of real edge, because it means
the sharp money agreed with your position *after* you placed the bet.

Formula
-------
For each bet we convert both the placement odds and the closing odds to
implied probability (removing the vig is not done here — we compare raw
implied probabilities which is the standard "raw CLV" approach).

    clv_cents = implied_prob(closing_odds) - implied_prob(placement_odds)

A **positive** value means you got a better price than where the line closed:
    - You placed at +150 (40.0% implied) and it closed at +130 (43.5%)
      → clv_cents = 43.5 - 40.0 = +3.5 cents  (you beat the close)

A **negative** value means you paid more juice than the market settled at:
    - You placed at -130 (56.5% implied) and it closed at -150 (60.0%)
      → clv_cents = 60.0 - 56.5 = +3.5 cents  (still beats close for the -side)

Note: "cents" here means percentage-point cents in implied probability space,
i.e. the raw difference multiplied by 100 for human readability.
"""

from __future__ import annotations

from app.math.math_utils import american_to_implied_probability


def calculate_clv(placement_odds: int, closing_odds: int) -> dict:
    """Calculate Closing Line Value for a single bet.

    Parameters
    ----------
    placement_odds:
        American odds at the time the bet was placed (e.g. +150 or -110).
    closing_odds:
        American odds at the market close, same side as the bet.

    Returns
    -------
    dict with:
    - ``clv_cents`` (float): difference in implied probability × 100.
      Positive means you beat the close.
    - ``clv_pct`` (float): the same value expressed as a fraction (not ×100).
      Positive means you beat the close.
    - ``placement_implied`` (float): implied probability of placement odds.
    - ``closing_implied`` (float): implied probability of closing odds.

    Examples
    --------
    >>> calculate_clv(150, 130)   # placed +150, closed +130
    {'clv_cents': 3.497..., 'clv_pct': 0.03497..., ...}

    >>> calculate_clv(-110, -130)  # placed -110, closed -130 (line moved in your favour)
    {'clv_cents': 5.128..., ...}   # closing implied went UP → you beat the close
    """
    placement_implied = american_to_implied_probability(placement_odds)
    closing_implied = american_to_implied_probability(closing_odds)

    # Positive CLV = closing implied is HIGHER than placement implied
    # (the market thinks this side is more likely than when you bet → your
    # price was better than the market's final verdict).
    clv_pct = closing_implied - placement_implied
    clv_cents = clv_pct * 100

    return {
        "clv_cents": round(clv_cents, 4),
        "clv_pct": round(clv_pct, 6),
        "placement_implied": round(placement_implied, 6),
        "closing_implied": round(closing_implied, 6),
    }


def aggregate_clv(bets: list[dict]) -> dict:
    """Compute aggregate CLV statistics over a list of bets.

    Each bet dict must contain:
    - ``placement_odds`` (int): American odds when the bet was placed.
    - ``closing_odds`` (int): American odds at market close.
    - ``sportsbook`` (str, optional): book name for per-book breakdown.

    Returns
    -------
    dict with:
    - ``avg_clv_cents`` (float): mean CLV in probability-point cents.
    - ``pct_beating_close`` (float): fraction [0, 1] of bets with CLV > 0.
    - ``total_bets`` (int): number of bets in the sample.
    - ``clv_by_book`` (dict[str, dict]): per-sportsbook breakdown with the
      same keys as the top-level summary.
    """
    if not bets:
        return {
            "avg_clv_cents": 0.0,
            "pct_beating_close": 0.0,
            "total_bets": 0,
            "clv_by_book": {},
        }

    clv_values: list[float] = []
    by_book: dict[str, list[float]] = {}

    for bet in bets:
        placement = bet.get("placement_odds")
        closing = bet.get("closing_odds")
        book = bet.get("sportsbook", "unknown")

        if placement is None or closing is None:
            continue
        if placement == 0 or closing == 0:
            continue

        result = calculate_clv(int(placement), int(closing))
        c = result["clv_cents"]
        clv_values.append(c)
        by_book.setdefault(book, []).append(c)

    if not clv_values:
        return {
            "avg_clv_cents": 0.0,
            "pct_beating_close": 0.0,
            "total_bets": 0,
            "clv_by_book": {},
        }

    total = len(clv_values)
    avg_clv = sum(clv_values) / total
    pct_positive = sum(1 for c in clv_values if c > 0) / total

    clv_by_book: dict[str, dict] = {}
    for book, values in by_book.items():
        book_total = len(values)
        clv_by_book[book] = {
            "avg_clv_cents": round(sum(values) / book_total, 4),
            "pct_beating_close": round(sum(1 for v in values if v > 0) / book_total, 4),
            "total_bets": book_total,
        }

    return {
        "avg_clv_cents": round(avg_clv, 4),
        "pct_beating_close": round(pct_positive, 4),
        "total_bets": total,
        "clv_by_book": clv_by_book,
    }
