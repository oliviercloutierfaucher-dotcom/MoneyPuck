---
created: 2026-03-05T03:21:22.342Z
title: Implement Elo rating system Phase 1
area: model
files:
  - app/math/elo.py
  - app/core/agents.py
  - app/core/backtester.py
  - tracker.py
---

## Problem

Current model uses a single logistic regression on z-scored team composites with exponential decay. Missing momentum/results-based signal that Elo captures. Professional models (gschwaeb, HarryShomer) all use Elo as an independent signal in their ensembles. FiveThirtyEight NHL Elo (K=6, MoV multiplier, autocorrelation adjustment) is well-documented and free historical data exists for validation.

## Solution

Build `app/math/elo.py` with:
- Running Elo per team (init 1500, K=6)
- Margin of victory multiplier: `0.6686 * ln(MOV) + 0.8048`
- Autocorrelation adjustment: `2.05 / (winner_elo_diff * 0.001 + 2.05)`
- Home-ice: +50 Elo points
- Season regression: 50% toward 1500
- Win probability: `1 / (10^(-diff/400) + 1)`
- Integrate as additional feature in TeamStrengthAgent
- Add to backtester for validation
