# Phase 7: Dashboard Rebuild - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Professional multi-page dashboard with modern UI. Multi-page routing, HTMX partial updates, mobile-responsive layout, polished styling. Same data, better presentation. No new features — reorganize and polish what exists.

</domain>

<decisions>
## Implementation Decisions

### Page structure & navigation
- Tab-based SPA using HTMX — NOT separate full HTML pages
- Single `base.html` shell with nav tabs that swap content via `hx-get` to partial endpoints
- Pages: Tonight's Games (default), Value Bets, Arbitrage, Performance, Player Props
- `hx-push-url` on tabs for bookmarkable URLs (e.g., `/value-bets`, `/arbs`)
- FastAPI serves both full page (GET `/value-bets`) and partial (GET `/partials/value-bets`)
- Full page requests render base.html with the correct tab active; partial requests return HTML fragment only

### CSS framework approach
- Keep existing CSS variable system — do NOT add Tailwind or DaisyUI
- Current design already has Inter font, dark/light theme, proper color tokens, responsive base
- Polish existing CSS: tighten spacing, improve card layouts, add missing breakpoints
- Add glassmorphism touches (subtle `backdrop-filter: blur`) on key panels
- Add micro-interactions: card hover lifts, smooth transitions, count-up animations
- No build step, no npm, no PostCSS — pure CSS in templates

### HTMX integration
- HTMX via CDN (`<script src="htmx.org/...">`) — no npm install
- Tab switching: `hx-get="/partials/games"` with `hx-target="#content"` and `hx-swap="innerHTML"`
- Auto-refresh: `hx-trigger="every 60s"` on active content panel (replaces current JS `setInterval`)
- Loading indicators via `htmx:beforeRequest` / `htmx:afterRequest` CSS classes
- No SSE — HTMX polling at 60s matches current behavior, simpler to implement
- SSE deferred to Phase 8 or later if needed

### Template decomposition
- Split monolithic `base.html` (~2200 lines) into:
  - `base.html` — shell (head, nav, footer, CSS variables, HTMX script, shared JS)
  - `partials/games.html` — game cards grid + KPI strip + book chips
  - `partials/value_bets.html` — value bets table + plays cards
  - `partials/arbs.html` — arbitrage opportunities grid
  - `partials/performance.html` — performance dashboard (P&L, ROI, charts)
  - `partials/props.html` — player props display
  - `macros/cards.html` — shared Jinja2 macros for game cards, stat pills, badges
- Each partial is a self-contained HTML fragment renderable independently
- Shared CSS stays in `base.html` `<style>` block (no separate .css files)
- JS split: shared utilities in base.html, page-specific JS in each partial's `<script>` block

### Mobile responsiveness
- Add breakpoints at 480px (phone), 768px (tablet), 1024px (desktop)
- Game cards: `minmax(340px, 1fr)` → `minmax(300px, 1fr)` on mobile
- KPI strip: horizontal scroll or 2-column grid on mobile
- Nav tabs: horizontal scroll with overflow on mobile (no hamburger menu)
- Modal: near-full-screen on mobile with reduced padding
- Touch-friendly: minimum 44px tap targets

### Claude's Discretion
- Exact CSS polish details (shadows, gradients, spacing values)
- How to handle the modal system across pages (global modal vs per-page)
- Chart library choice for performance page (Chart.js CDN vs lightweight alternative)
- Whether to add skeleton loading states during HTMX swaps
- Sort/filter interactions on value bets table
- Book chip filter state persistence across tab switches

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/web/app.py` — FastAPI app with all routes, TTLCache, demo mode, security middleware
- `app/web/templates/base.html` — 2200-line monolithic Jinja2 template (CSS + HTML + JS)
- `app/web/presentation.py` — `to_serializable()`, `render_dashboard()` for CLI path
- `app/web/deep_links.py` — `build_sportsbook_url()` for sportsbook links
- CSS variable system with dark/light theme support already built
- Game card rendering, KPI strip, value bets table, arb cards, modals all exist in JS

### Established Patterns
- FastAPI routes: `@app.get("/")` serves HTML, `@router.get("/api/dashboard")` serves JSON
- Jinja2 template receives full data context and renders via JS client-side
- TTLCache with 90s TTL for odds responses
- Demo mode toggle via `?demo=1` query param
- Book chip filtering via client-side JS

### Integration Points
- `/api/dashboard` — returns full JSON payload (games, value_bets, arbs, summary, etc.)
- `/api/performance` — returns performance/settlement data
- `/api/opportunities` — returns opportunities JSON
- `/api/odds-history` — returns sparkline data
- `build_market_snapshot()` and `score_snapshot()` from service.py — data pipeline
- All existing tests in `tests/web/` use FastAPI TestClient

### Key Constraints
- No npm/build step — all frontend assets via CDN or inline
- Single Dockerfile deployment to Railway
- Must preserve CLI rendering path (`presentation.py` stays for `--tonight` output)
- Must preserve all existing API endpoints (no breaking changes)

</code_context>

<specifics>
## Specific Ideas

- Polymarket-inspired card design: large probability numbers, clean flat cards, minimal chrome
- Game cards should show probabilities as the dominant visual element
- Value indicator via green glow border rather than tag/badge
- Performance page with Chart.js CDN for P&L and ROI charts
- Tab navigation with active indicator (bottom border or background highlight)
- Smooth HTMX transitions using `htmx:afterSwap` to trigger entry animations

</specifics>

<deferred>
## Deferred Ideas

- SSE real-time push — defer to Phase 8 or later (HTMX polling sufficient for now)
- TradingView Lightweight Charts — defer until line movement feature is more mature
- Component library / design system — premature at this scale
- User preferences persistence (theme, default tab) — Phase 10 with auth

</deferred>

---

*Phase: 07-dashboard-rebuild*
*Context gathered: 2026-03-08*
