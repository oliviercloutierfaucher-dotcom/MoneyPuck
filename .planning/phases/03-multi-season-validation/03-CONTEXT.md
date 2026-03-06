# Phase 3: Multi-Season Validation - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the model works across multiple NHL seasons, not just 2024-25. Extend the backtester to load historical MoneyPuck data, run walk-forward validation, report parameter stability, and produce a clear overfit verdict. No model changes — this is validation of what exists.

</domain>

<decisions>
## Implementation Decisions

### Season scope
- Fetch as many seasons as MoneyPuck per-team CSVs support (try from ~2015 onward)
- Graceful fallback when a season's data doesn't exist (404 → skip, don't crash)
- 2020-21 COVID season: include in results but flag it separately in output (abnormal: 56 games, no fans, compressed schedule)
- COVID season IS included in pass/fail — if the model can't handle it, that's a real weakness

### Walk-forward design
- Two validation modes run in sequence:
  1. **Fixed params test:** Use current production params (home_advantage=0.14, logistic_k=0.9) on every season
  2. **Per-season grid search:** Find optimal params for each season independently, report drift
- Training data approach: Claude's discretion (prior season only vs cumulative)
- Elo ratings between seasons: Claude's discretion (carry-over with regression vs reset — follow FiveThirtyEight best practices)
- Test both accuracy (Brier, win rate) AND profitability (ROI with Kelly sizing)

### Success threshold
- Minimum >55% win rate on every held-out season (strict — from REQUIREMENTS.md)
- Any single season failing = overall validation fails
- COVID season included in this strict rule (no exemptions)
- Positive ROI also required per season (tests full pipeline including Kelly)

### Output format
- Report ends with explicit verdict: "VERDICT: Parameters are stable/overfit" based on drift analysis
- CLI invocation and report detail level: Claude's discretion
- Parameter stability: Claude decides whether to define drift limits or just report

### Claude's Discretion
- CLI flag design (new --validate vs extending --backtest)
- Report detail level (summary vs full diagnostic)
- Output destination (CLI only vs saved report file)
- Training window approach (single prior season vs cumulative)
- Elo carry-over strategy between seasons
- Season data caching strategy
- Season auto-discovery vs hardcoded list
- Parameter drift threshold definition

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core/backtester.py`: `backtest_season()` — replays a single season, returns prediction dicts
- `app/core/backtester.py`: `grid_search()` — parameter optimization over a season
- `app/core/backtester.py`: `evaluate_predictions()` — Brier, accuracy, log loss
- `app/core/backtester.py`: `simulate_betting_roi()` — Kelly sizing simulation
- `app/core/backtester.py`: `production_readiness_report()` + `format_report()` — existing report generation
- `app/data/data_sources.py`: `fetch_moneypuck_team_game_data(season)` — per-team CSV fetcher
- `app/math/elo.py`: `EloTracker`, `build_elo_ratings()` — Elo system already built

### Established Patterns
- Season mapping: `mp_year = season` (MoneyPuck directory year = season start year)
- Team-game-by-game format detection: checks for `playerTeam` key
- Pass/fail thresholds already defined: `BRIER_PASS=0.24`, `ACCURACY_PASS=0.52`
- Grid search iterates over `TrackerConfig` overrides

### Integration Points
- `tracker.py` CLI: `--backtest` flag already exists — multi-season extends this
- `app/core/models.py`: `TrackerConfig` holds all model parameters
- `app/data/data_sources.py:454`: `fetch_moneypuck_team_game_data(season)` — needs to support older seasons

</code_context>

<specifics>
## Specific Ideas

- The user cares about proving this isn't overfit — the verdict must be clear and honest
- If params are overfit, say so plainly rather than burying it in numbers
- Full pipeline test (including Kelly ROI) not just accuracy — the model needs to make money

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-multi-season-validation*
*Context gathered: 2026-03-06*
