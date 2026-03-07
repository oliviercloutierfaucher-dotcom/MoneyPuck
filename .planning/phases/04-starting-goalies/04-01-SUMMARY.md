---
phase: 04-starting-goalies
plan: 01
subsystem: data
tags: [dailyfaceoff, nhl-api, goalie-resolution, scraping, fallback]

# Dependency graph
requires:
  - phase: 01-persistent-storage
    provides: database and data pipeline foundation
provides:
  - DailyFaceoff __NEXT_DATA__ JSON scraper with 32-team slug mapping
  - NHL API gamecenter goalie comparison enrichment (fetch_game_goalies)
  - 3-tier goalie resolution (confirmed > likely > gp_leader > none)
  - Goalie name matching (last name + team_code)
affects: [04-02, pipeline-integration, agents]

# Tech tracking
tech-stack:
  added: []
  patterns: [__NEXT_DATA__ JSON extraction, 3-tier fallback resolution, last-name goalie matching]

key-files:
  created:
    - app/data/dailyfaceoff.py
    - app/data/goalie_resolver.py
    - tests/data/test_dailyfaceoff.py
    - tests/data/test_goalie_resolver.py
  modified:
    - app/data/nhl_api.py
    - tests/data/test_nhl_api.py

key-decisions:
  - "DailyFaceoff __NEXT_DATA__ JSON extraction over DOM scraping for stability"
  - "Last-name + team_code matching handles abbreviated first names (J. Swayman vs Jeremy Swayman)"
  - "Unconfirmed status treated same as missing -- falls back to gp_leader"

patterns-established:
  - "__NEXT_DATA__ JSON extraction: regex for script tag, defensive .get() access"
  - "3-tier fallback: confirmed > likely > gp_leader > none with source tracking"
  - "SLUG_TO_ABBREV static mapping for DailyFaceoff team slugs to NHL abbreviations"

requirements-completed: [R3.1, R3.3]

# Metrics
duration: 4min
completed: 2026-03-07
---

# Phase 4 Plan 1: Goalie Data Layer Summary

**DailyFaceoff scraper with __NEXT_DATA__ JSON extraction, NHL API gamecenter goalie enrichment, and 3-tier resolution (confirmed > likely > gp_leader) with last-name matching**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T16:43:15Z
- **Completed:** 2026-03-07T16:47:16Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- DailyFaceoff scraper parses __NEXT_DATA__ JSON for goalie confirmations with full 32-team slug mapping
- NHL API fetch_game_goalies extracts per-goalie season stats from gamecenter/landing endpoint
- 3-tier goalie resolution correctly picks confirmed > likely > gp_leader with graceful fallback
- 30 data layer tests passing, 523 total suite tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: DailyFaceoff scraper and NHL API gamecenter goalie enrichment**
   - `f4f9c86` (test: add failing tests for DailyFaceoff scraper and fetch_game_goalies)
   - `c10b7c9` (feat: add goalie data layer - DailyFaceoff scraper, resolver, NHL API enrichment)
   - `b1623c4` (feat: implement DailyFaceoff scraper and fetch_game_goalies)

2. **Task 2: 3-tier goalie resolution logic**
   - `a31cff2` (test: add goalie resolver unit tests)

_Note: Implementation code for both tasks was committed together in c10b7c9 from a prior session. Tests were added in this session._

## Files Created/Modified
- `app/data/dailyfaceoff.py` - DailyFaceoff __NEXT_DATA__ scraper with SLUG_TO_ABBREV mapping
- `app/data/goalie_resolver.py` - 3-tier goalie resolution with name matching
- `app/data/nhl_api.py` - Added fetch_game_goalies() for gamecenter goalie comparison
- `tests/data/test_dailyfaceoff.py` - 10 tests for DailyFaceoff scraper
- `tests/data/test_goalie_resolver.py` - 11 tests for goalie resolver
- `tests/data/test_nhl_api.py` - 2 new tests for fetch_game_goalies

## Decisions Made
- DailyFaceoff __NEXT_DATA__ JSON extraction chosen over DOM scraping for stability (React/Next.js page)
- Last-name + team_code matching handles abbreviated first names gracefully
- Unconfirmed status treated as missing data -- triggers gp_leader fallback
- No new dependencies required -- uses stdlib urllib, json, re

## Deviations from Plan

None - plan executed as written. Implementation code existed from a prior session; this execution added comprehensive test coverage and committed atomically.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Goalie data layer complete with all three modules (dailyfaceoff.py, goalie_resolver.py, nhl_api.py extension)
- Ready for Plan 2: pipeline integration (agents.py, service.py modifications)
- resolve_starter() and resolve_all_starters() are the public API for downstream consumption

## Self-Check: PASSED

All 6 files verified present. All 4 commits verified in git log.

---
*Phase: 04-starting-goalies*
*Completed: 2026-03-07*
