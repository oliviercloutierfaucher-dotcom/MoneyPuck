---
phase: 05-injury-impact-system
plan: 02
subsystem: model, dashboard
tags: [injury-adjustment, pipeline-integration, parallel-fetch, dashboard-display]

# Dependency graph
requires:
  - phase: 05-injury-impact-system
    provides: "ESPN injury fetcher, tier classification, adjustment calculation (Plan 01)"
  - phase: 04-starting-goalies
    provides: "Goalie resolution pipeline (goalie impact handled separately)"
provides:
  - "Pipeline-integrated injury fetch (parallel 6th worker in ThreadPoolExecutor)"
  - "EdgeScoringAgent injury_adj parameter alongside sit_adj and goalie_adj"
  - "Dashboard game cards with key injured players and significant swing flags"
  - "score_snapshot with injury-aware edge scoring"
affects: [dashboard-ui, model-accuracy, web-preview]

# Tech tracking
tech-stack:
  added: []
  patterns: [parallel-injury-fetch, injury-adj-pipeline-wiring, game-card-injury-display]

key-files:
  created: []
  modified:
    - app/core/agents.py
    - app/core/service.py
    - app/web/web_preview.py
    - app/web/presentation.py
    - tests/core/test_agents.py

key-decisions:
  - "injury_adj added as probability-unit parameter (already divided by 100), unlike goalie_adj which is in pp"
  - "Injury data stored on event dict as _injuries key to avoid modifying frozen ValueCandidate dataclass"
  - "Dashboard shows only top-tier injuries (top6_f, top4_d, starting_g) to avoid clutter"
  - "Significant swing threshold set at >2pp per plan user decision"
  - "build_market_snapshot returns 3-tuple (snapshot, games_rows, injuries) for pipeline transparency"

patterns-established:
  - "Injury fetch as 6th parallel worker in build_market_snapshot ThreadPoolExecutor"
  - "Game card enrichment pattern: compute per-game data before games.append() in live dashboard"
  - "renderInjurySection() JS helper for card-level injury display"

requirements-completed: [R4.3, R4.4]

# Metrics
duration: 5min
completed: 2026-03-07
---

# Phase 5 Plan 02: Pipeline Integration & Dashboard Display Summary

**Injury adjustment wired into EdgeScoringAgent pipeline with parallel fetch, score_snapshot integration, and dashboard game cards showing key injured players with >2pp swing flags**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-07T23:12:28Z
- **Completed:** 2026-03-07T23:17:57Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- EdgeScoringAgent._estimate_win_probability() now accepts injury_adj parameter alongside sit_adj and goalie_adj
- Pipeline fetches injuries in parallel as 6th worker in ThreadPoolExecutor (fail-soft, no slowdown)
- score_snapshot() builds player tiers and passes injuries + tiers to edge agent per game
- Dashboard game cards display key injured players (top-tier only) below team names with significant swing badges
- Manual overrides (apply_overrides) still run first and are unchanged; injury adjustment is separate and additive

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire injury_adj into EdgeScoringAgent + pipeline (TDD)** - `fed05bd` (test), `56e3918` (feat)
2. **Task 2: Dashboard injury display on game cards** - `491d2db` (feat)

## Files Created/Modified
- `app/core/agents.py` - Added injury_adj to _estimate_win_probability(), injuries/player_tiers to run()
- `app/core/service.py` - _fetch_injuries_safe(), 6-worker ThreadPoolExecutor, 3-tuple return, injury-aware score_snapshot
- `app/web/web_preview.py` - Injury enrichment per game, cache updated for 4-tuple, build_player_tiers import
- `app/web/presentation.py` - CSS for injury display, renderInjurySection() JS helper, card template integration
- `tests/core/test_agents.py` - 3 new tests for injury adjustment in EdgeScoringAgent

## Decisions Made
- injury_adj is in probability units (pp/100), consistent with calculate_injury_adjustment output, unlike goalie_adj which is in pp
- Used event["_injuries"] for passing injury data to presentation layer (avoids modifying frozen ValueCandidate)
- Only top-tier injuries displayed on cards (top6_f, top4_d, starting_g) per user decision to avoid clutter
- build_market_snapshot returns 3-tuple for pipeline transparency rather than mutating snapshot

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Full injury impact system complete (data fetch + tier classification + adjustment math + pipeline + dashboard)
- 564 tests passing (3 new + 561 existing)
- Ready for Phase 6 (FastAPI migration or next planned phase)

---
*Phase: 05-injury-impact-system*
*Completed: 2026-03-07*
