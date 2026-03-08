---
phase: 07-dashboard-rebuild
plan: 01
subsystem: ui
tags: [htmx, jinja2, fastapi, spa, tab-navigation, partials]

# Dependency graph
requires:
  - phase: 06-fastapi-migration
    provides: FastAPI app with Jinja2 templates, all routes migrated
provides:
  - Shell template with HTMX tab navigation and CSS variable system
  - 5 tab partials (games, value_bets, arbs, performance, props)
  - Shared Jinja2 macros (game_card, stat_pill, badge)
  - Dual-mode route handlers (full page vs HTMX partial)
  - Tab routing with bookmarkable URLs
affects: [07-dashboard-rebuild]

# Tech tracking
tech-stack:
  added: [htmx-2.0.8]
  patterns: [dual-mode-route-handlers, htmx-partial-swap, template-decomposition]

key-files:
  created:
    - app/web/templates/partials/games.html
    - app/web/templates/partials/value_bets.html
    - app/web/templates/partials/arbs.html
    - app/web/templates/partials/performance.html
    - app/web/templates/partials/props.html
    - app/web/templates/macros/cards.html
    - tests/web/test_partials.py
    - tests/web/test_tab_routes.py
  modified:
    - app/web/templates/base.html
    - app/web/app.py

key-decisions:
  - "HTMX via CDN (no npm/build step) for tab navigation with hx-push-url for bookmarkable URLs"
  - "Games partial contains all existing client-side JS rendering for backward compatibility"
  - "Shared JS utilities (esc, bookLink, dec, pct, n) in base.html, page-specific JS in partials"
  - "Stub partials for value-bets, arbs, props tabs -- full content migration deferred to Plans 02-03"
  - "HX-Request header detection pattern: _tab_response() helper reduces route handler duplication"
  - "CSP updated to allow cdn.jsdelivr.net for HTMX script loading"

patterns-established:
  - "Dual-mode route pattern: check HX-Request header, return partial or full page"
  - "Template include pattern: base.html uses {% include partials/active_tab.html %}"
  - "Partial self-containment: each partial has own <script> block with page-specific JS"
  - "Global data via window.__MP_DATA for cross-partial access to dashboard JSON"

requirements-completed: [R5.3, R5.5]

# Metrics
duration: 10min
completed: 2026-03-08
---

# Phase 7 Plan 1: HTMX Tab Shell Summary

**Split 2252-line monolithic base.html into shell + 5 tab partials + macros with HTMX tab navigation and dual-mode FastAPI route handlers**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-08T00:45:04Z
- **Completed:** 2026-03-08T00:55:34Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Split monolithic 2252-line base.html into shell template (~850 lines CSS/nav/shared JS) + 5 tab partials + macros
- Added HTMX CDN script and tab navigation bar with 5 tabs and bookmarkable URLs
- Created dual-mode route handlers that serve full pages or HTMX partials based on HX-Request header
- 32 new tests covering partial endpoints, full page routing, and API backward compatibility
- 607 total tests passing (full suite green, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create base shell, macros, stub partials, and HTMX tab navigation** - `cc5e25f` (feat)
2. **Task 2: Add dual-mode route handlers and write routing tests** - `79a7b8d` (feat)

## Files Created/Modified
- `app/web/templates/base.html` - Shell template with CSS, header, HTMX nav tabs, footer, modal, shared JS
- `app/web/templates/partials/games.html` - Games tab with controls, KPI strip, game cards, all client-side JS
- `app/web/templates/partials/value_bets.html` - Value bets stub partial
- `app/web/templates/partials/arbs.html` - Arbitrage stub partial
- `app/web/templates/partials/performance.html` - Performance tracker with full JS rendering
- `app/web/templates/partials/props.html` - Player props stub partial
- `app/web/templates/macros/cards.html` - Placeholder macros (game_card, stat_pill, badge)
- `app/web/app.py` - 5 dual-mode route handlers, _tab_response() helper, CSP update
- `tests/web/test_partials.py` - 12 tests for partial/full page endpoints
- `tests/web/test_tab_routes.py` - 20 tests for tab routing, backward compat, API integrity

## Decisions Made
- HTMX via CDN -- no build step, consistent with project's no-npm constraint
- Games partial carries ALL existing client-side JS for identical rendering (Plans 02-03 will migrate to server-side Jinja2)
- Stub partials for value-bets, arbs, props -- these tabs point users to Games tab for now
- Performance partial is fully functional (has its own JS that lazy-loads /api/performance)
- CSP header updated to allow cdn.jsdelivr.net for HTMX script
- _tab_response() helper centralizes HX-Request detection to avoid duplication across 5 routes
- window.__MP_DATA provides global data access for partials (replaces the old `D` variable)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added active_tab to existing dashboard_page context**
- **Found during:** Task 1
- **Issue:** New base.html template requires `active_tab` context variable for `{% include %}` directive, but existing `dashboard_page` route didn't provide it
- **Fix:** Added `"active_tab": "games"` to the template context in the existing route handler
- **Files modified:** app/web/app.py
- **Verification:** All 11 existing tests pass unchanged
- **Committed in:** cc5e25f (Task 1 commit)

**2. [Rule 2 - Missing Critical] Updated CSP header for HTMX CDN**
- **Found during:** Task 1
- **Issue:** Content-Security-Policy header blocked scripts from cdn.jsdelivr.net, which would prevent HTMX from loading
- **Fix:** Added `https://cdn.jsdelivr.net` to script-src directive
- **Files modified:** app/web/app.py
- **Verification:** CSP test updated expectation, HTMX script would load correctly
- **Committed in:** cc5e25f (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical)
**Impact on plan:** Both fixes were necessary for the template split to work. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Shell + partials structure ready for Plans 02-03 (content migration to server-side Jinja2)
- Tab navigation works; clicking tabs will swap content via HTMX once full partials are built
- All API endpoints preserved for client-side JS that still runs in the games partial

## Self-Check: PASSED

All 9 created files verified present. Both task commits (cc5e25f, 79a7b8d) verified in git log.

---
*Phase: 07-dashboard-rebuild*
*Completed: 2026-03-08*
