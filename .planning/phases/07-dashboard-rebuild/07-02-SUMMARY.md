---
phase: 07-dashboard-rebuild
plan: 02
subsystem: ui
tags: [jinja2, server-side-rendering, macros, mobile-responsive, glassmorphism]

# Dependency graph
requires:
  - phase: 07-dashboard-rebuild
    provides: HTMX tab shell with 5 partials, dual-mode route handlers
provides:
  - Server-side Jinja2 macros (game_card, value_bet_row, arb_card, stat_pill, badge)
  - Server-rendered games partial with KPI strip, plays, arbs, value bets table
  - Server-rendered value bets partial with sortable table
  - Server-rendered arbs partial with arb cards
  - Mobile-responsive CSS at 480px, 768px, 1024px breakpoints
  - Glassmorphism and micro-interaction effects on game cards
affects: [07-dashboard-rebuild]

# Tech tracking
tech-stack:
  added: []
  patterns: [jinja2-server-rendering, css-mobile-breakpoints, glassmorphism-backdrop-filter]

key-files:
  created: []
  modified:
    - app/web/templates/macros/cards.html
    - app/web/templates/partials/games.html
    - app/web/templates/partials/value_bets.html
    - app/web/templates/partials/arbs.html
    - app/web/templates/base.html

key-decisions:
  - "Game cards, plays, arbs, value bets table all rendered server-side via Jinja2 macros from data dict"
  - "Modal content still built via JS (complex interactive DOM requiring data lookups)"
  - "Sparklines rendered client-side via data attributes (data-sparkline JSON) for SVG generation"
  - "Book chip filter toggles via JS but chips rendered server-side"
  - "Value bets table sort uses client-side DOM reordering (no server round-trip for <50 rows)"
  - "Three CSS breakpoints: 1024px (desktop), 768px (tablet), 480px (phone)"

patterns-established:
  - "Jinja2 macro pattern: game_card(game, idx, value_bets) receives game dict and index"
  - "Server-side KPI computation using Jinja2 filters (map, sum, max, length)"
  - "data-dec attribute pattern for client-side American-to-decimal odds conversion"
  - "data-commence attribute pattern for client-side timezone-aware time formatting"

requirements-completed: [R5.4, R5.6]

# Metrics
duration: 10min
completed: 2026-03-08
---

# Phase 7 Plan 2: Server-Side Rendering and Mobile CSS Summary

**Jinja2 macros replace ~600 lines of JS DOM building for games, value bets, and arbs with server-side rendering plus mobile-responsive breakpoints at 480px/768px/1024px**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-08T00:58:51Z
- **Completed:** 2026-03-08T01:09:27Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Built 5 reusable Jinja2 macros (game_card, value_bet_row, arb_card, stat_pill, badge) replacing JS template literals
- Converted games, value bets, and arbs partials from client-side JS DOM building to server-side Jinja2 rendering
- Added comprehensive mobile-responsive CSS with 3 breakpoints, touch-friendly 44px targets, and horizontal-scroll tab nav
- Added glassmorphism (backdrop-filter: blur) and card hover lift effects per CONTEXT.md design spec
- 607 total tests passing (full suite green, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Build Jinja2 macros and convert games partial** - `7ca97f2` (feat)
2. **Task 2: Convert value bets and arbs partials** - `6a907ff` (feat)
3. **Task 3: Add mobile-responsive CSS breakpoints** - `0af9f43` (feat)

## Files Created/Modified
- `app/web/templates/macros/cards.html` - Full Jinja2 macros: game_card, value_bet_row, arb_card, stat_pill, badge
- `app/web/templates/partials/games.html` - Server-rendered games tab (KPI, plays, arbs, game cards, value table)
- `app/web/templates/partials/value_bets.html` - Server-rendered value bets with KPI summary and sortable table
- `app/web/templates/partials/arbs.html` - Server-rendered arb cards with KPI summary
- `app/web/templates/base.html` - Mobile breakpoints, touch targets, glassmorphism, hover effects

## Decisions Made
- Game modal still uses JS DOM building (complex interactive content with data lookups across games/books/arbs)
- Sparklines use data-sparkline attribute with JSON for client-side SVG generation (server can't do client-side SVG animation)
- Book chip filter rendered server-side but toggle behavior remains JS (client-side show/hide)
- Value bets table sort implemented as client-side DOM reordering rather than server round-trip (data set is <50 rows)
- Refresh navigates via full page reload instead of AJAX+DOM rebuild (simpler with server-rendering)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three main tab partials (games, value bets, arbs) now server-rendered
- Mobile-responsive layout complete at all breakpoints
- Ready for Plan 03 (performance/props partials, remaining polish)
- Template structure stable for further UI improvements

## Self-Check: PASSED

All 5 modified files verified present. All 3 task commits (7ca97f2, 6a907ff, 0af9f43) verified in git log.

---
*Phase: 07-dashboard-rebuild*
*Completed: 2026-03-08*
