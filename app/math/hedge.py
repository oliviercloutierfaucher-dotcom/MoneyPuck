"""Hedge calculator for managing open betting positions.

Provides tools to calculate hedge stakes for locking in guaranteed profit
or minimising worst-case losses on existing bets, plus fair cashout valuation
based on current market odds.

All odds are in **decimal** format (e.g. 2.50 = +150 American).
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_decimal(odds: float) -> float:
    """Validate and return decimal odds (must be > 1.0)."""
    if odds <= 1.0:
        raise ValueError(f"Decimal odds must be > 1.0, got {odds}")
    return odds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_hedge(
    original_odds: float,
    original_stake: float,
    hedge_odds: float,
    mode: str = "lock_profit",
) -> dict:
    """Calculate the optimal hedge stake for an open position.

    Parameters
    ----------
    original_odds:
        Decimal odds of the original bet (e.g. 2.50).
    original_stake:
        Dollar amount wagered on the original bet.
    hedge_odds:
        Decimal odds available on the opposite side.
    mode:
        ``"lock_profit"`` — size the hedge to guarantee equal payout on
        both outcomes (classic guaranteed-profit hedge).
        ``"minimize_loss"`` — if no profit is achievable, find the hedge
        stake that minimises worst-case loss; falls back to lock_profit
        when a guaranteed profit exists.

    Returns
    -------
    dict with keys:
        hedge_stake          – Recommended dollar amount to bet on the hedge.
        profit_if_original_wins  – Net P&L when the original bet wins.
        profit_if_hedge_wins     – Net P&L when the hedge bet wins.
        guaranteed_profit    – Minimum of the two profit figures.
        roi_pct              – Guaranteed profit / total outlay * 100.
    """
    original_odds = _to_decimal(original_odds)
    hedge_odds = _to_decimal(hedge_odds)

    if original_stake <= 0:
        raise ValueError(f"original_stake must be positive, got {original_stake}")

    original_payout = original_odds * original_stake  # gross payout if original wins

    if mode == "lock_profit":
        # Solve: original_payout - original_stake - h = h * (hedge_odds - 1)
        # i.e. both sides net the same profit.
        # If original wins  : original_payout - original_stake - h
        # If hedge wins     : h * (hedge_odds - 1) - original_stake
        # Set equal → h = original_payout / hedge_odds
        hedge_stake = original_payout / hedge_odds

    elif mode == "minimize_loss":
        # First check if a guaranteed profit exists (margin < 1).
        margin = 1.0 / original_odds + 1.0 / hedge_odds
        if margin < 1.0:
            # Guaranteed profit exists — use lock_profit sizing.
            hedge_stake = original_payout / hedge_odds
        else:
            # No guaranteed profit.  Find h that minimises the worst-case loss:
            # loss_if_original_wins = original_stake + h - original_payout
            # loss_if_hedge_wins    = original_stake - h * (hedge_odds - 1)
            # Minimise max(loss_A, loss_B) → set loss_A = loss_B and solve.
            # original_stake + h - original_payout = original_stake - h*(hedge_odds-1)
            # h + h*(hedge_odds-1) = original_payout
            # h * hedge_odds = original_payout  ← same formula as lock_profit
            hedge_stake = original_payout / hedge_odds
    else:
        raise ValueError(f"Unknown mode '{mode}'. Expected 'lock_profit' or 'minimize_loss'.")

    hedge_stake = round(hedge_stake, 2)
    total_outlay = original_stake + hedge_stake

    profit_if_original_wins = round(
        original_payout - original_stake - hedge_stake, 2
    )
    profit_if_hedge_wins = round(
        hedge_stake * hedge_odds - total_outlay, 2
    )
    guaranteed_profit = round(min(profit_if_original_wins, profit_if_hedge_wins), 2)
    roi_pct = round(guaranteed_profit / total_outlay * 100, 2) if total_outlay > 0 else 0.0

    return {
        "hedge_stake": hedge_stake,
        "profit_if_original_wins": profit_if_original_wins,
        "profit_if_hedge_wins": profit_if_hedge_wins,
        "guaranteed_profit": guaranteed_profit,
        "roi_pct": roi_pct,
    }


def calculate_cashout_value(
    original_odds: float,
    original_stake: float,
    current_odds: float,
) -> dict:
    """Calculate the fair cashout value of an open bet.

    The *fair* cashout value is what a risk-neutral bookmaker would pay
    you to close the position based purely on the current implied
    probability — i.e. the current market probability times the original
    potential profit.

    Parameters
    ----------
    original_odds:
        Decimal odds at which the original bet was placed.
    original_stake:
        Dollar amount originally wagered.
    current_odds:
        Current decimal odds available on the same selection.

    Returns
    -------
    dict with keys:
        fair_value       – The stake-inclusive cashout amount that gives zero EV.
        profit_if_cashout – Net P&L if you accept fair_value (= fair_value - original_stake).
        ev_if_hold       – Expected value of holding the open bet at current odds
                           (from the bettor's perspective, based on the original win
                           probability implied by current_odds).
    """
    original_odds = _to_decimal(original_odds)
    current_odds = _to_decimal(current_odds)

    if original_stake <= 0:
        raise ValueError(f"original_stake must be positive, got {original_stake}")

    original_payout = original_odds * original_stake

    # Current implied probability of winning
    current_implied_prob = 1.0 / current_odds

    # Fair cashout = current win probability × original gross payout
    fair_value = round(current_implied_prob * original_payout, 2)
    profit_if_cashout = round(fair_value - original_stake, 2)

    # EV of holding = prob_win * net_win + prob_lose * (-stake)
    # Using current_implied_prob as our best estimate of P(win)
    ev_if_hold = round(
        current_implied_prob * (original_payout - original_stake)
        - (1.0 - current_implied_prob) * original_stake,
        2,
    )

    return {
        "fair_value": fair_value,
        "profit_if_cashout": profit_if_cashout,
        "ev_if_hold": ev_if_hold,
    }
