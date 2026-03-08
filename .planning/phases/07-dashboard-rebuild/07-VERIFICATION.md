---
phase: 07-dashboard-rebuild
verified: 2026-03-08T02:00:00Z
status: gaps_found
score: 12/14 must-haves verified
gaps:
  - truth: "Active tab content auto-refreshes every 60 seconds via HTMX polling"
    status: partial
    reason: "Games partial still uses JS setInterval for auto-refresh instead of HTMX hx-trigger polling. The other 4 partials (value_bets, arbs, performance, props) correctly use hx-trigger='every 60s'."
    artifacts:
      - path: "app/web/templates/partials/games.html"
        issue: "Missing hx-trigger='every 60s' wrapper div. Still has setInterval at line 656."
    missing:
      - "Add hx-get/hx-trigger='every 60s' wrapper div to games.html partial, same pattern as other 4 partials"
      - "Remove setInterval-based startAutoRefresh() function from games.html"
  - truth: "HTMX polling replaces the current JS setInterval refresh mechanism"
    status: failed
    reason: "setInterval still present in app/web/templates/partials/games.html line 656. Plan 03 claimed 'JS setInterval removed from all templates' but games.html was not converted."
    artifacts:
      - path: "app/web/templates/partials/games.html"
        issue: "startAutoRefresh() function with setInterval still present at lines 651-671"
    missing:
      - "Remove startAutoRefresh() and autoRefreshInterval/autoRefreshCountdown variables from games.html"
      - "Add HTMX polling wrapper div with hx-trigger='every 60s' to games.html"
---

# Phase 7: Dashboard Rebuild Verification Report

**Phase Goal:** Professional multi-page dashboard with modern UI. Multi-page routing, HTMX partial updates, mobile-responsive layout, polished styling. Same data, better presentation. No new features -- reorganize and polish what exists.
**Verified:** 2026-03-08T02:00:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Navigating to /games, /value-bets, /arbs, /performance, /props returns full HTML page with correct tab active | VERIFIED | All 5 dual-mode route handlers exist in app.py (lines 1223-1291). Each calls `_tab_response()` with correct `active_tab` value. base.html tab nav uses `{% if active_tab == 'games' %}active{% endif %}` pattern. 32 tests confirm. |
| 2 | HTMX requests (HX-Request header) to same URLs return only the partial HTML fragment | VERIFIED | `_tab_response()` helper (line 1196) checks `request.headers.get("HX-Request") == "true"` and returns partial template. Tests in test_partials.py validate fragments lack `<html>` tag. |
| 3 | Tab navigation via HTMX swaps content without full page reload | VERIFIED | base.html nav tabs (lines 975-991) use `hx-get`, `hx-target="#content"`, `hx-swap="innerHTML"`, and `hx-push-url`. HTMX CDN loaded at line 10. |
| 4 | Direct browser refresh on any tab URL renders the full page with that tab selected | VERIFIED | Route handlers serve `base.html` with correct `active_tab` for non-HTMX requests. Tests verify active class on correct tab. |
| 5 | All existing /api/* endpoints remain unchanged and functional | VERIFIED | API router preserved. test_tab_routes.py includes API backward-compat tests. |
| 6 | Game cards render server-side via Jinja2 macros without client-side JS DOM building | VERIFIED | macros/cards.html has `game_card` macro (115 lines). games.html uses `{% for game in games %}{{ game_card(game, loop.index0, value_bets) }}{% endfor %}`. No JS `renderGameCard` function. |
| 7 | Value bets table renders server-side with sortable columns | VERIFIED | value_bets.html uses `{% for bet in value_bets %}{{ value_bet_row(bet, loop.index) }}{% endfor %}`. Sort is client-side DOM reorder (appropriate for <50 rows). |
| 8 | Arb cards render server-side via Jinja2 | VERIFIED | arbs.html uses `{% for arb in arb_opportunities %}{{ arb_card(arb) }}{% endfor %}`. |
| 9 | Dashboard is mobile-responsive at 480px, 768px, and 1024px breakpoints | VERIFIED | base.html has `@media (max-width: 1024px)` at line 891, `@media (max-width: 768px)` at line 897, `@media (max-width: 480px)` at line 930. |
| 10 | Performance page shows P&L bar chart rendered by Chart.js | VERIFIED | performance.html has `<canvas id="pl-chart">` with `new Chart(ctx, {type: 'bar', ...})` IIFE at lines 54-88. Chart.js CDN in base.html line 11. |
| 11 | Performance page shows KPIs server-side | VERIFIED | performance.html renders win_rate, roi_pct, net_profit, total_bets from `perf_data` dict via Jinja2. |
| 12 | Player props page renders server-side via Jinja2 | VERIFIED | props.html iterates `data.games` to collect props, renders table with player, game, market, line, over/under odds, spread. |
| 13 | Active tab content auto-refreshes every 60 seconds via HTMX polling | PARTIAL | value_bets.html, arbs.html, performance.html, and props.html all have `hx-trigger="every 60s"` wrapper divs. **Games partial does NOT have HTMX polling** -- it uses JS setInterval instead. |
| 14 | HTMX polling replaces the current JS setInterval refresh mechanism | FAILED | setInterval still present in games.html at line 656 (`startAutoRefresh` function). Plan 03 Summary claimed all setInterval was removed, but games.html was not converted. |

**Score:** 12/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/web/templates/base.html` | Shell template with nav tabs, HTMX script, #content div, CSS variables | VERIFIED | ~1060 lines. Contains CSS vars, HTMX CDN, Chart.js CDN, tab nav, #content div, modal, theme toggle, shared JS. |
| `app/web/templates/partials/games.html` | Games tab partial fragment | VERIFIED | 741 lines. Server-rendered game cards, KPI strip, plays, arbs, value table, controls, hedge calc. |
| `app/web/templates/partials/value_bets.html` | Value bets tab partial fragment | VERIFIED | 119 lines. Server-rendered with HTMX polling, KPI summary, plays cards, sortable table. |
| `app/web/templates/partials/arbs.html` | Arbitrage tab partial fragment | VERIFIED | 39 lines. Server-rendered with HTMX polling, KPI summary, arb cards via macro. |
| `app/web/templates/partials/performance.html` | Performance tab with Chart.js | VERIFIED | 149 lines. Server-rendered KPIs, Chart.js bar chart, by-book table, recent bets, HTMX polling. |
| `app/web/templates/partials/props.html` | Props tab partial | VERIFIED | 65 lines. Server-rendered player props table from game data, HTMX polling. |
| `app/web/templates/macros/cards.html` | Shared Jinja2 macros | VERIFIED | 172 lines. Contains game_card, stat_pill, value_bet_row, arb_card, badge macros. |
| `app/web/app.py` | Dual-mode route handlers for all 5 tabs | VERIFIED | 5 routes (/, /games, /value-bets, /arbs, /performance, /props) with _tab_response() helper. HX-Request detection. |
| `tests/web/test_partials.py` | Tests for partial endpoints | VERIFIED | 123 lines. |
| `tests/web/test_tab_routes.py` | Tests for full page tab routes | VERIFIED | 95 lines. 32 total tests across both files. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| base.html | app.py route handlers | hx-get URLs matching routes | WIRED | Tab links use hx-get="/games", "/value-bets", "/arbs", "/performance", "/props" -- all match route decorators. |
| app.py | partials/*.html | TemplateResponse with HX-Request detection | WIRED | _tab_response() returns partial name for HTMX requests, base.html for full requests. |
| partials/games.html | macros/cards.html | Jinja2 import | WIRED | `{% from "macros/cards.html" import game_card, stat_pill, value_bet_row, arb_card %}` at line 4. |
| partials/value_bets.html | macros/cards.html | Jinja2 import | WIRED | `{% from "macros/cards.html" import value_bet_row, stat_pill %}` at line 3. |
| partials/arbs.html | macros/cards.html | Jinja2 import | WIRED | `{% from "macros/cards.html" import arb_card %}` at line 3. |
| performance.html | Chart.js CDN | canvas + Chart constructor | WIRED | `new Chart(ctx, {...})` IIFE in script block. Chart.js CDN in base.html head. |
| value_bets.html | /value-bets route | hx-trigger every 60s | WIRED | `hx-get="/value-bets?demo={{ data.mode }}" hx-trigger="every 60s"` |
| arbs.html | /arbs route | hx-trigger every 60s | WIRED | `hx-get="/arbs?demo={{ data.mode }}" hx-trigger="every 60s"` |
| performance.html | /performance route | hx-trigger every 60s | WIRED | `hx-get="/performance?demo={{ data.mode|default('demo') }}" hx-trigger="every 60s"` |
| props.html | /props route | hx-trigger every 60s | WIRED | `hx-get="/props?demo={{ data.mode }}" hx-trigger="every 60s"` |
| games.html | /games route | hx-trigger every 60s | NOT WIRED | Games partial lacks HTMX polling. Uses setInterval JS instead. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| R5.3 | 07-01 | Multi-page routing: Tonight's Games, Value Bets, Arbs, Performance, Props | SATISFIED | All 5 tabs implemented with dual-mode route handlers and bookmarkable URLs. |
| R5.4 | 07-02, 07-03 | Professional styling (CSS, no build step) | SATISFIED | Existing CSS variable system polished with glassmorphism, hover effects, mobile breakpoints. No Tailwind added per CONTEXT.md decision. Note: R5.4 originally said "Tailwind CSS" but CONTEXT.md explicitly decided against it. |
| R5.5 | 07-01 | HTMX for dynamic partial updates | SATISFIED | HTMX tab switching works. 4/5 partials have HTMX polling. Games partial has JS-based refresh (functional but not HTMX). |
| R5.6 | 07-02 | Mobile-responsive layout | SATISFIED | Three breakpoints (480px, 768px, 1024px). Touch targets 44px. Horizontal scrolling tabs on mobile. |
| R5.7 | 07-03 | Real-time odds updates via SSE (replace 60s polling) | NOT APPLICABLE | CONTEXT.md explicitly deferred SSE to Phase 8+. HTMX 60s polling is the intended mechanism for this phase. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| partials/games.html | 656 | `setInterval` auto-refresh still present | Warning | Should be replaced by HTMX polling per phase goal. Functionally works but contradicts the architectural decision to use HTMX polling exclusively. |
| partials/games.html | 651 | `autoRefreshInterval`, `autoRefreshCountdown` variables | Info | Dead weight if HTMX polling is added; creates dual refresh mechanism if both coexist. |

### Human Verification Required

### 1. Visual Quality Check
**Test:** Open `http://localhost:8080/?demo=1` in browser. Navigate all 5 tabs.
**Expected:** Professional appearance comparable to BetQL/Betstamp. Game cards show probabilities as dominant visual element. Glassmorphism blur on cards. Green glow on value cards.
**Why human:** Visual quality is subjective and cannot be verified by code inspection.

### 2. Mobile Responsiveness
**Test:** Open browser dev tools, toggle device toolbar to 375px width. Navigate all tabs.
**Expected:** Tabs scroll horizontally, game cards stack vertically, no horizontal overflow, all targets tappable.
**Why human:** CSS media queries exist but actual rendering behavior needs visual confirmation.

### 3. Theme Toggle
**Test:** Click theme toggle button in header. Verify dark/light switch on all tabs.
**Expected:** All elements respect theme. No unstyled or hard-coded colors showing through.
**Why human:** CSS variable overrides need visual confirmation across all components.

### 4. Chart.js Rendering
**Test:** Navigate to Performance tab with `?demo=1`. Check bar chart renders.
**Expected:** Monthly P&L bar chart with green/red bars. Responsive to container size.
**Why human:** Canvas rendering cannot be verified via code inspection.

### 5. HTMX Tab Switching
**Test:** Open Network tab. Click between tabs.
**Expected:** Only partial HTML fragments loaded (no full page). URL updates in address bar.
**Why human:** HTMX runtime behavior needs browser verification.

### Gaps Summary

Two related gaps were found, both stemming from the same root cause: **the games partial was not converted to HTMX polling in Plan 03**.

The games.html partial (the largest at 741 lines) still uses a JS `setInterval`-based `startAutoRefresh()` function (lines 651-671) for auto-refresh, while the other 4 partials correctly use `hx-trigger="every 60s"` HTMX polling wrappers. Plan 03's Summary claimed "JS setInterval removed from all templates" and "HTMX polling (hx-trigger='every 60s') on all 5 tab partials" but this was not done for the games partial.

This is a minor gap -- the dashboard is fully functional. The games tab still refreshes, just via a different mechanism. The fix is straightforward: add an HTMX polling wrapper div and remove the setInterval code.

---

_Verified: 2026-03-08T02:00:00Z_
_Verifier: Claude (gsd-verifier)_
