---
phase: 03-multi-season-validation
plan: 01
subsystem: testing
tags: [backtesting, elo, multi-season, moneypuck, historical-data]

# Dependency graph
requires:
  - phase: 02-ci-cd-pipeline
    provides: CI pipeline ensuring tests pass on commit
provides:
  - Multi-season data loader (load_seasons) with per-era team code handling
  - Historical team code mapping (ARI/UTA, SEA expansion, VGK expansion)
  - Elo carry-over support in backtest_season via optional elo_tracker parameter
  - Graceful 404/failure skipping for unavailable seasons
affects: [03-02-walk-forward-orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns: [era-based team code mapping, incremental Elo updates across seasons]

key-files:
  created:
    - app/core/multi_season.py
    - tests/core/test_multi_season.py
  modified:
    - app/data/data_sources.py
    - app/core/backtester.py

key-decisions:
  - "Historical team codes handled via era boundaries rather than full season-by-season mapping"
  - "fetch_team_game_by_game gets fallback_to_bulk kwarg to prevent 403s on old bulk CSV endpoint"
  - "External Elo tracker incrementally updated during backtest (not rebuilt each date)"

patterns-established:
  - "Era-based team code resolution: get_teams_for_season() centralizes historical NHL roster changes"
  - "Optional parameter extension: new keyword-only params with None defaults preserve backward compatibility"

requirements-completed: [R2.1, R2.2]

# Metrics
duration: 3min
completed: 2026-03-06
---

# Phase 3 Plan 1: Multi-Season Data Loading Summary

**Multi-season MoneyPuck data loader with historical team codes (ARI/UTA/SEA/VGK) and Elo carry-over support in backtester**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-06T23:29:47Z
- **Completed:** 2026-03-06T23:33:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Multi-season data loading infrastructure with graceful failure handling for unavailable seasons
- Historical team code mapping covering ARI->UTA (2024), SEA expansion (2021), VGK expansion (2017)
- Elo carry-over in backtest_season() via optional elo_tracker parameter with incremental updates
- 11 new tests covering data loading, team codes, Elo carry-over, and backward compatibility
- 477 total tests passing with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffolding for multi-season functionality** - `5c0c855` (test)
2. **Task 2: Build multi-season data loader and Elo carry-over** - `584c50f` (feat)

_TDD approach: tests written first (RED), then implementation (GREEN)_

## Files Created/Modified
- `app/core/multi_season.py` - Multi-season data loader with load_seasons() and get_teams_for_season()
- `app/data/data_sources.py` - Added fallback_to_bulk parameter to fetch_team_game_by_game()
- `app/core/backtester.py` - Added elo_tracker parameter to backtest_season() with incremental updates
- `tests/core/test_multi_season.py` - 11 tests for all multi-season functionality

## Decisions Made
- Historical team codes handled via era boundaries (season thresholds) rather than per-season lookup tables -- simpler and covers all known changes since 2015
- fetch_team_game_by_game gets a keyword-only `fallback_to_bulk` param (default True) to prevent hitting the dead bulk CSV endpoint when loading old seasons
- External Elo tracker is incrementally updated game-by-game during backtest rather than being rebuilt each prediction date -- preserves carry-over information and is more efficient

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TrackerConfig instantiation in tests**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** TrackerConfig requires odds_api_key positional argument, tests used keyword-only season=2024
- **Fix:** Added odds_api_key="" to all TrackerConfig instantiations in tests
- **Files modified:** tests/core/test_multi_season.py
- **Verification:** All 11 tests pass
- **Committed in:** 584c50f (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test fix, no scope change.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- load_seasons() ready for walk-forward orchestrator (Plan 02) to call
- get_teams_for_season() provides correct team lists per era
- backtest_season(elo_tracker=tracker) enables cross-season Elo carry-over
- EloTracker.regress_to_mean() available for between-season regression

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 03-multi-season-validation*
*Completed: 2026-03-06*
