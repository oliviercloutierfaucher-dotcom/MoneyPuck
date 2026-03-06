# Phase 3: Multi-Season Validation - Research

**Researched:** 2026-03-06
**Domain:** Backtesting, walk-forward validation, parameter stability analysis
**Confidence:** HIGH

## Summary

This phase extends the existing single-season backtester to validate the model across multiple NHL seasons. The existing infrastructure (`backtest_season()`, `evaluate_predictions()`, `simulate_betting_roi()`, `grid_search()`) is well-built and covers all needed metrics. The primary work is: (1) a multi-season data loader with graceful fallback, (2) a walk-forward orchestrator that runs fixed-param and per-season-grid-search modes, (3) Elo carry-over between seasons, and (4) a parameter stability report with an explicit VERDICT.

MoneyPuck team game-by-game CSVs are confirmed available from 2008 onward (verified 2008 and 2015 via direct fetch). The existing `fetch_team_game_by_game(season)` function works for any season year. The COVID 2020-21 season (56 games) is included but must be flagged in output.

**Primary recommendation:** Build a `multi_season_validator` module that orchestrates existing backtester functions across seasons, adds Elo carry-over with `regress_to_mean()`, and produces a structured report ending with a parameter drift verdict.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Fetch as many seasons as MoneyPuck per-team CSVs support (try from ~2015 onward)
- Graceful fallback when a season's data doesn't exist (404 -> skip, don't crash)
- 2020-21 COVID season: include in results but flag it separately in output (abnormal: 56 games, no fans, compressed schedule)
- COVID season IS included in pass/fail -- if the model can't handle it, that's a real weakness
- Two validation modes run in sequence:
  1. Fixed params test: Use current production params (home_advantage=0.14, logistic_k=0.9) on every season
  2. Per-season grid search: Find optimal params for each season independently, report drift
- Test both accuracy (Brier, win rate) AND profitability (ROI with Kelly sizing)
- Minimum >55% win rate on every held-out season (strict -- from REQUIREMENTS.md)
- Any single season failing = overall validation fails
- COVID season included in this strict rule (no exemptions)
- Positive ROI also required per season (tests full pipeline including Kelly)
- Report ends with explicit verdict: "VERDICT: Parameters are stable/overfit" based on drift analysis

### Claude's Discretion
- CLI flag design (new --validate vs extending --backtest)
- Report detail level (summary vs full diagnostic)
- Output destination (CLI only vs saved report file)
- Training window approach (single prior season vs cumulative)
- Elo carry-over strategy between seasons
- Season data caching strategy
- Season auto-discovery vs hardcoded list
- Parameter drift threshold definition

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| R2.1 | Backtester supports 2022-23, 2023-24, and 2024-25 seasons | MoneyPuck data confirmed available 2008+. Existing `fetch_team_game_by_game(season)` works per-team. Need multi-season loader with fallback. |
| R2.2 | Walk-forward validation: train on season N, test on N+1 | Existing `backtest_season()` replays a season with rolling window. Need orchestrator to chain seasons and carry Elo forward. |
| R2.3 | Parameter stability report: do optimal params hold across seasons? | Existing `grid_search()` finds optimal params per season. Need cross-season comparison and drift detection. |
| R2.4 | Brier score, ROI, win rate reported per season | Existing `evaluate_predictions()` + `simulate_betting_roi()` already compute all metrics. Need per-season aggregation. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.x | All implementation | No new dependencies needed |
| pytest | 9.0.2 | Testing | Already installed and configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses | stdlib | Report structures | For typed return values |
| statistics | stdlib | Param drift analysis | Mean, stdev for parameter stability |
| json | stdlib | Report serialization | For --json output mode |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib statistics | numpy/scipy | Overkill; only need mean/stdev for drift analysis |
| Custom report format | pandas DataFrame | Would add dependency; dict-based approach matches existing pattern |

**Installation:**
```bash
# No new packages needed -- all stdlib + existing deps
```

## Architecture Patterns

### Recommended Project Structure
```
app/core/
    backtester.py          # Existing -- keep untouched
    multi_season.py        # NEW: multi-season validation orchestrator
app/data/
    data_sources.py        # Minor: add graceful 404 handling in fetch_team_game_by_game
app/math/
    elo.py                 # Existing -- already has regress_to_mean()
tracker.py                 # Add --validate-seasons CLI flag
tests/core/
    test_multi_season.py   # NEW: multi-season validation tests
```

### Pattern 1: Multi-Season Orchestrator
**What:** A module that fetches data for multiple seasons, runs backtests in sequence, carries Elo forward, and aggregates results.
**When to use:** This is the core of the phase.
**Key design:**
```python
def validate_multi_season(
    seasons: list[int],
    config: TrackerConfig,
    mode: str = "fixed",  # "fixed" or "grid_search"
) -> MultiSeasonReport:
    """Run walk-forward validation across seasons.

    For each season:
    1. Fetch MoneyPuck data (skip on 404)
    2. Run backtest_season() with Elo carried from prior season
    3. Evaluate predictions + simulate ROI
    4. Optionally run grid_search for per-season optimal params

    Returns aggregated report with per-season breakdowns.
    """
```

### Pattern 2: Elo Carry-Over Between Seasons
**What:** Carry Elo ratings from one season to the next with regression to mean.
**When to use:** Between every season boundary.
**Best practice from FiveThirtyEight (Neil Paine):**
- Retain 70% of previous season's rating, regress 30% toward 1505
- The existing code uses 50% regression (SEASON_REGRESSION = 0.5) -- this is MORE aggressive than FiveThirtyEight recommends
- **Recommendation:** Keep the existing 50% regression for now (it was tuned for this model). The per-season grid search results will reveal if adjusting this helps.
- For multi-season validation, carry the EloTracker instance across seasons, calling `regress_to_mean()` at each season boundary.

**Implementation approach:**
```python
elo_tracker = EloTracker()
for season in seasons:
    games = fetch_season_data(season)
    if not games:
        continue  # graceful 404 skip
    if prior_season_played:
        elo_tracker.regress_to_mean()  # Apply between-season regression
    preds = backtest_season_with_elo(games, config, elo_tracker)
    # ... evaluate and collect results
```

### Pattern 3: Graceful Season Discovery
**What:** Try fetching from 2015 onward, skip seasons that 404.
**When to use:** Data loading phase.
**Approach:** Attempt to fetch one team's CSV per season as a probe. If 404, skip entire season. If success, fetch all 32 teams.

### Pattern 4: Training Window Approach
**Recommendation: Cumulative training (all prior seasons' data).**
- Single prior season limits training data unnecessarily
- The model's `train_window_days=60` parameter already handles recency via rolling window
- The key benefit of cumulative is Elo ratings: they need many games to converge
- This matches FiveThirtyEight's approach where Elo ratings are lifetime cumulative

### Anti-Patterns to Avoid
- **Modifying backtest_season() directly:** The existing function works well for single seasons. Wrap it rather than changing its signature.
- **Parallel season fetching:** MoneyPuck may rate-limit; fetch sequentially with short delays.
- **Comparing raw Brier scores across seasons without context:** COVID season has fewer games, so Brier has higher variance. Flag it, but don't normalize it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Single-season backtest | New backtest logic | Existing `backtest_season()` | Already handles format detection, rolling windows, Elo blending |
| Metric evaluation | New metric calculators | Existing `evaluate_predictions()` | Brier, log loss, accuracy, calibration all implemented |
| ROI simulation | New betting simulator | Existing `simulate_betting_roi()` | Kelly sizing, drawdown, monthly breakdown all implemented |
| Parameter search | New optimizer | Existing `grid_search()` | 1050-combination grid already defined |
| Elo regression | Custom regression math | Existing `EloTracker.regress_to_mean()` | Already implements season boundary regression |

**Key insight:** This phase is primarily an ORCHESTRATION task. Almost all computational building blocks exist. The new code wraps existing functions across multiple seasons and aggregates results.

## Common Pitfalls

### Pitfall 1: MoneyPuck Team Code Changes (ARI -> UTA)
**What goes wrong:** Arizona Coyotes (ARI) became Utah Hockey Club (UTA) in 2024-25. Older seasons use ARI; current code's NHL_TEAMS list only has UTA.
**Why it happens:** Team relocations change codes across seasons.
**How to avoid:** When fetching older seasons, include ARI in the team list. Map ARI -> UTA (or keep separate) for Elo continuity.
**Warning signs:** Missing team data for 31 of 32 teams in older seasons.

### Pitfall 2: Seattle Kraken Didn't Exist Before 2021-22
**What goes wrong:** Fetching SEA for 2020 or earlier seasons returns 404.
**Why it happens:** Expansion team joined in 2021-22.
**How to avoid:** Per-team 404s are already handled in `fetch_team_game_by_game()` (logs warning, continues). Just ensure the overall flow handles teams that don't exist in older seasons.

### Pitfall 3: COVID Season Data Shape
**What goes wrong:** 2020-21 had 56 games (not 82), compressed schedule, games in hub cities (no true home ice).
**Why it happens:** Pandemic.
**How to avoid:** Flag it in output. The user explicitly decided it counts toward pass/fail.
**Warning signs:** If home advantage drops significantly in 2020-21 grid search, that's expected (hub city = no real home ice).

### Pitfall 4: Grid Search Runtime Explosion
**What goes wrong:** Default grid is 1050 combinations. Across 10 seasons, that's 10,500 grid search runs, each processing ~1200 games. Could take hours.
**Why it happens:** Combinatorial explosion.
**How to avoid:** Two strategies: (a) Use a smaller grid for multi-season (e.g., 3x3x3x3 = 81 combos), or (b) only run full grid on the 3 required seasons (2022-25). For parameter stability, a coarser grid that identifies the approximate optimal region is sufficient.
**Warning signs:** Runtime exceeding 30 minutes for multi-season validation.

### Pitfall 5: Backtest Season Requires Elo Integration Refactor
**What goes wrong:** Current `backtest_season()` builds Elo from scratch internally using `build_elo_ratings(train_rows)`. This means Elo doesn't carry over between seasons.
**Why it happens:** It was designed for single-season use.
**How to avoid:** Either (a) modify `backtest_season()` to accept an optional pre-built EloTracker, or (b) build a `backtest_season_with_elo()` wrapper that passes an existing tracker through. Option (a) is cleaner -- add an `elo_tracker: EloTracker | None = None` parameter with backward-compatible default.
**Warning signs:** If Elo predictions at the start of each season look identical (all ~0.5), the tracker isn't carrying over.

### Pitfall 6: fetch_team_game_by_game Falls Back to Bulk CSV on Failure
**What goes wrong:** If enough individual team fetches fail, the function falls back to `fetch_moneypuck_games(season)` which hits the bulk `games.csv` endpoint that returns 403.
**Why it happens:** The fallback was designed when bulk CSV worked.
**How to avoid:** The fallback to bulk CSV should be disabled or wrapped in try/except for older seasons. Better: if most teams succeed, just proceed with partial data.

## Code Examples

### Multi-Season Data Loading with Graceful Fallback
```python
# Pattern for loading multiple seasons
def load_seasons(start_season: int = 2015, end_season: int = 2024) -> dict[int, list[dict]]:
    """Load MoneyPuck data for multiple seasons, skipping unavailable ones."""
    from app.data.data_sources import fetch_team_game_by_game

    season_data = {}
    for season in range(start_season, end_season + 1):
        try:
            games = fetch_team_game_by_game(season)
            if games:
                season_data[season] = games
                # Log: loaded N games for season YYYY
            else:
                # Log: no data for season YYYY, skipping
                pass
        except Exception:
            # Log: failed to fetch season YYYY, skipping
            continue
    return season_data
```

### Parameter Stability Analysis
```python
def analyze_parameter_stability(
    per_season_optimal: dict[int, dict[str, float]],
) -> dict[str, Any]:
    """Analyze whether optimal parameters are stable across seasons."""
    from statistics import mean, stdev

    params = ["half_life", "regression_k", "home_advantage", "logistic_k"]
    stability = {}

    for param in params:
        values = [opt[param] for opt in per_season_optimal.values()]
        stability[param] = {
            "mean": mean(values),
            "stdev": stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
            "values_by_season": {s: opt[param] for s, opt in per_season_optimal.items()},
        }

    return stability
```

### Verdict Logic
```python
def determine_verdict(
    season_results: dict[int, dict],
    param_stability: dict[str, Any],
) -> str:
    """Determine VERDICT: Parameters are stable/overfit."""
    # Check 1: Every season must pass >55% win rate and positive ROI
    all_pass = all(
        r["accuracy"] >= 0.55 and r["roi_pct"] > 0.0
        for r in season_results.values()
    )

    # Check 2: Parameter drift -- if optimal params vary wildly, likely overfit
    # e.g., if home_advantage ranges from 0.05 to 0.25 across seasons
    high_drift = any(
        s["stdev"] / s["mean"] > 0.3  # coefficient of variation > 30%
        for s in param_stability.values()
        if s["mean"] != 0
    )

    if all_pass and not high_drift:
        return "VERDICT: Parameters are STABLE across seasons"
    elif all_pass and high_drift:
        return "VERDICT: Model performs well but parameters show DRIFT — current params may be season-specific"
    else:
        return "VERDICT: Parameters are OVERFIT — model fails on held-out seasons"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Validate on single season | Walk-forward multi-season | Standard practice | Exposes overfitting |
| In-sample grid search | Out-of-sample validation | Standard practice | Honest performance assessment |
| Fresh Elo each season | Carry-over with regression | FiveThirtyEight standard | Better early-season predictions |
| 50% Elo regression (current code) | 30% regression (FiveThirtyEight) | Neil Paine's recommendation | Less aggressive regression retains more signal |

**Note on Elo regression:** The existing code uses `SEASON_REGRESSION = 0.5` (50% regression to mean). FiveThirtyEight/Neil Paine recommends 30% regression (retain 70%). The multi-season validation will reveal which works better for this model. Consider testing both values in the grid search or as a separate comparison.

## Open Questions

1. **How many seasons to fetch?**
   - What we know: MoneyPuck data confirmed available from 2008+. User wants "as many as possible from ~2015 onward."
   - What's unclear: How many seasons of per-team CSV data exist without issues. Some older seasons may have different team codes or missing columns.
   - Recommendation: Start from 2015, probe each season, report what's available. Minimum required: 2022, 2023, 2024 per R2.1.

2. **Grid search runtime for multi-season**
   - What we know: 1050 combinations x 10 seasons = very slow (potentially hours).
   - What's unclear: Exact runtime per season on this hardware.
   - Recommendation: Use a reduced grid (e.g., 3-4 values per param = ~100 combos) for multi-season mode. Full 1050 grid only for the current production season.

3. **Elo regression parameter (50% vs 30%)**
   - What we know: Current code = 50%, FiveThirtyEight = 30%.
   - What's unclear: Which is optimal for this specific model ensemble.
   - Recommendation: This is a perfect thing to test during multi-season validation. Run both and report which performs better.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pytest discovery (no explicit config file) |
| Quick run command | `python -m pytest tests/core/test_multi_season.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R2.1 | Load multiple seasons of MoneyPuck data | unit | `python -m pytest tests/core/test_multi_season.py::test_load_multiple_seasons -x` | Wave 0 |
| R2.1 | Graceful 404 handling for missing seasons | unit | `python -m pytest tests/core/test_multi_season.py::test_graceful_season_fallback -x` | Wave 0 |
| R2.2 | Walk-forward: train on N, test on N+1 | unit | `python -m pytest tests/core/test_multi_season.py::test_walk_forward_validation -x` | Wave 0 |
| R2.2 | Elo carry-over between seasons | unit | `python -m pytest tests/core/test_multi_season.py::test_elo_carry_over -x` | Wave 0 |
| R2.3 | Per-season grid search + drift report | unit | `python -m pytest tests/core/test_multi_season.py::test_parameter_stability -x` | Wave 0 |
| R2.3 | Verdict generation (stable/overfit) | unit | `python -m pytest tests/core/test_multi_season.py::test_verdict_logic -x` | Wave 0 |
| R2.4 | Brier, ROI, win rate per season | unit | `python -m pytest tests/core/test_multi_season.py::test_per_season_metrics -x` | Wave 0 |
| R2.4 | COVID season flagged in output | unit | `python -m pytest tests/core/test_multi_season.py::test_covid_season_flag -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/core/test_multi_season.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/test_multi_season.py` -- covers R2.1, R2.2, R2.3, R2.4
- [ ] Tests must use synthetic data (not live MoneyPuck fetches) for speed and reliability

## Sources

### Primary (HIGH confidence)
- MoneyPuck team game-by-game CSV endpoints -- verified working for 2008 and 2015 via direct HTTP fetch
- Existing codebase: `app/core/backtester.py`, `app/data/data_sources.py`, `app/math/elo.py` -- read in full

### Secondary (MEDIUM confidence)
- [Neil Paine - How My NHL Elo Ratings and Forecast Works](https://neilpaine.substack.com/p/how-my-nhl-elo-ratings-and-forecast) -- K=6, 30% regression, 1505 mean
- [FiveThirtyEight NHL Methodology](https://fivethirtyeight.com/methodology/how-our-nhl-predictions-work/)
- [Machine learning for sports betting: model selection](https://arxiv.org/abs/2303.06021) -- calibration > accuracy, walk-forward validation

### Tertiary (LOW confidence)
- Runtime estimates for grid search across 10 seasons -- extrapolated from single-season behavior, not measured

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries needed, all existing code verified
- Architecture: HIGH -- clear orchestration pattern, existing building blocks verified
- Pitfalls: HIGH -- team code changes (ARI->UTA), COVID season, grid search runtime all documented from codebase inspection
- Elo regression value: MEDIUM -- 50% vs 30% needs empirical testing during this phase

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain, MoneyPuck data is static for past seasons)
