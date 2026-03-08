---
phase: 07-dashboard-rebuild
plan: 03
subsystem: ui
tags: [chart.js, htmx-polling, performance-page, props, auto-refresh]

# Dependency graph
requires:
  - phase: 07-dashboard-rebuild
    provides: HTMX tab shell, server-rendered games/value-bets/arbs partials
provides:
  - Server-rendered performance page with Chart.js P&L bar chart
  - Server-rendered player props page
  - HTMX polling (every 60s) on all 5 tab partials replacing JS setInterval
  - Theme toggle fix (data-theme attribute on html tag)
affects: [07-dashboard-rebuild]

# Tech tracking
tech-stack:
  added: [chart.js-4.5.1]
  patterns: [htmx-polling-auto-refresh, chart-js-bar-chart, iife-script-pattern]

key-files:
  created: []
  modified:
    - app/web/templates/partials/performance.html
    - app/web/templates/partials/props.html
    - app/web/templates/partials/games.html
    - app/web/templates/partials/value_bets.html
    - app/web/templates/partials/arbs.html
    - app/web/templates/base.html

key-decisions:
  - "Chart.js bar chart for monthly P&L with green/red bars based on profit sign"
  - "Chart.js scripts use IIFE pattern so they work both on initial load and HTMX swap"
  - "HTMX polling via hx-trigger='every 60s' on inner div in each partial"
  - "Polling stops automatically when tab is switched (partial DOM replaced)"
  - "Polling URLs propagate demo mode and relevant query params"
  - "JS setInterval removed from all templates — HTMX polling is sole refresh mechanism"

patterns-established:
  - "IIFE script pattern in partials for Chart.js compatibility with HTMX swaps"
  - "HTMX polling div wraps partial content for automatic lifecycle management"

requirements-completed: [R5.4, R5.7]

# Metrics
duration: 10min
completed: 2026-03-08
---

# Phase 7 Plan 3: Performance Charts, Props, and HTMX Polling Summary

**Server-rendered performance page with Chart.js P&L chart, props page, and HTMX 60s auto-refresh polling replacing JS setInterval across all 5 tabs**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-08T01:00:00Z
- **Completed:** 2026-03-08T01:10:55Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Converted performance partial to server-side Jinja2 with Chart.js P&L bar chart, KPIs, by-book table, recent bets
- Converted props partial to server-side Jinja2 with player props comparison table
- Added HTMX polling (hx-trigger="every 60s") to all 5 tab partials
- Removed all JS setInterval auto-refresh mechanisms
- Fixed theme toggle (added data-theme="dark" to html tag)
- 607 total tests passing (full suite green, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert performance and props partials to server-side rendering** - `32a9d1e` (feat)
2. **Task 2: Add HTMX polling to all 5 partials and remove JS setInterval** - `7d9a482` (feat)
3. **Task 3: Visual verification checkpoint** - `e600775` (fix: theme toggle)

## Files Created/Modified
- `app/web/templates/partials/performance.html` - Server-rendered KPIs, Chart.js P&L bar chart, by-book table, recent bets, HTMX polling
- `app/web/templates/partials/props.html` - Server-rendered player props comparison table, HTMX polling
- `app/web/templates/partials/games.html` - Added HTMX polling wrapper div
- `app/web/templates/partials/value_bets.html` - Added HTMX polling wrapper div
- `app/web/templates/partials/arbs.html` - Added HTMX polling wrapper div
- `app/web/templates/base.html` - Added data-theme="dark" to html tag for theme toggle

## Decisions Made
- Chart.js bar chart uses green/red coloring based on monthly profit sign
- IIFE pattern for Chart.js scripts ensures compatibility with HTMX partial swaps
- Polling inner div pattern: hx-trigger on div inside partial, auto-stops on tab switch
- Performance route passes data directly (no separate /api/performance fetch needed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Theme toggle data-theme attribute**
- **Found during:** Task 3 visual checkpoint
- **Issue:** Theme toggle button clicked but CSS variables didn't switch — `<html>` tag missing `data-theme="dark"` attribute
- **Fix:** Added `data-theme="dark"` to `<html lang="en">` in base.html
- **Files modified:** app/web/templates/base.html
- **Verification:** Theme toggle works in both directions
- **Committed in:** e600775

---

**Total deviations:** 1 auto-fixed (missing critical)
**Impact on plan:** Necessary fix for theme system to work. No scope creep.

## Issues Encountered
None beyond the theme toggle fix.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 7 Dashboard Rebuild complete
- All 5 tab pages fully server-rendered via Jinja2
- HTMX tab navigation and 60s polling operational
- Mobile-responsive layout at 3 breakpoints
- Ready for Phase 8 (whatever comes next in roadmap)

## Self-Check: PASSED

All 6 modified files verified present. All 3 task commits (32a9d1e, 7d9a482, e600775) verified in git log.

---
*Phase: 07-dashboard-rebuild*
*Completed: 2026-03-08*
