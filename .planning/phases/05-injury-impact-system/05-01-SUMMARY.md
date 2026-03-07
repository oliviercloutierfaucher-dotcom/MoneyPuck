---
phase: 05-injury-impact-system
plan: 01
subsystem: data, model
tags: [espn-api, nhl-api, injuries, tier-classification, win-probability]

# Dependency graph
requires:
  - phase: 04-starting-goalies
    provides: "Goalie resolution pipeline (Phase 4 handles goalie impact separately)"
provides:
  - "ESPN injury fetcher (fetch_injuries) for all 32 NHL teams"
  - "NHL club-stats player stats fetcher (fetch_team_player_stats) for TOI-based tier classification"
  - "Player tier classification (classify_player_tier) by TOI rank within positional group"
  - "Injury adjustment calculation (calculate_injury_adjustment) with GTD, cap, symmetry, goalie exclusion"
  - "InjuredPlayer frozen dataclass for pipeline/display use"
affects: [05-02-pipeline-integration, dashboard-injury-display]

# Tech tracking
tech-stack:
  added: []
  patterns: [espn-api-fetcher, toi-based-tier-classification, injury-adjustment-math]

key-files:
  created:
    - app/data/injuries.py
    - app/core/injury_impact.py
    - tests/data/test_injuries.py
    - tests/core/test_injury_impact.py
  modified: []

key-decisions:
  - "ESPN injuries API as primary injury data source (free, structured JSON, no auth required)"
  - "Last-name matching for player lookup between ESPN and NHL API data (same pattern as Phase 4 goalie resolver)"
  - "Goalie injuries excluded from adjustment calculation (Phase 4 handles goalie impact via backup save%)"
  - "Position normalization: LW->L, RW->R to match project conventions"

patterns-established:
  - "ESPN API fetcher pattern: _fetch_json reuse with fail-soft empty list return"
  - "Tier classification by TOI rank within positional group (top-6 F, top-4 D)"
  - "Injectable fetch function (fetch_stats_fn) for testability without mocking"

requirements-completed: [R4.1, R4.2, R4.3, R4.4]

# Metrics
duration: 3min
completed: 2026-03-07
---

# Phase 5 Plan 01: Injury Data & Impact Calculation Summary

**ESPN injury fetcher + NHL club-stats tier classification + adjustment math with GTD half-impact, 8pp cap, and goalie exclusion**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-07T22:56:05Z
- **Completed:** 2026-03-07T22:59:30Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- ESPN injury API fetcher with position normalization (LW->L, RW->R) and team abbreviation normalization (UTAH->UTA)
- NHL club-stats API fetcher for per-player TOI/position data enabling automated tier classification
- Tier classification engine ranking players by TOI within their positional group (top-6 F, top-4 D, bottom-6 F, bottom-pair D)
- Adjustment calculation with GTD half-impact, 8pp per-team cap, symmetrical net, and goalie exclusion
- 33 unit tests covering all parsing, classification, and adjustment edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: ESPN injury fetcher + NHL player stats fetcher** - `faa65b8` (test)
2. **Task 2: Tier classification + injury adjustment calculation** - `c3391df` (feat)

## Files Created/Modified
- `app/data/injuries.py` - ESPN injury fetcher + NHL club-stats player stats fetcher
- `app/core/injury_impact.py` - Tier classification, InjuredPlayer dataclass, adjustment calculation
- `tests/data/test_injuries.py` - 11 tests for injury data fetching and parsing
- `tests/core/test_injury_impact.py` - 22 tests for tier classification and adjustment math

## Decisions Made
- Used ESPN injuries API (free, structured JSON, no auth) as primary injury data source
- Last-name matching between ESPN display names and NHL API roster (Phase 4 goalie resolver pattern)
- Goalie injuries detected for display but NOT applied as adjustments (Phase 4 handles via backup save%)
- Injectable fetch_stats_fn parameter in build_player_tiers for clean testing without mock patches
- Position normalization at fetch layer (LW->L, RW->R) so downstream code uses consistent codes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Data layer and calculation engine ready for Plan 02 pipeline integration
- fetch_injuries() and calculate_injury_adjustment() are fully tested standalone modules
- EdgeScoringAgent integration point identified (injury_adj parameter alongside sit_adj and goalie_adj)
- build_market_snapshot() thread pool ready for injury_future parallel fetch

## Self-Check: PASSED

All 4 created files verified on disk. Both task commits (faa65b8, c3391df) verified in git log. 561 tests passing (33 new + 528 existing).

---
*Phase: 05-injury-impact-system*
*Completed: 2026-03-07*
