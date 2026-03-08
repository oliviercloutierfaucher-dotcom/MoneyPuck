# Phase 7: Dashboard Rebuild - Research

**Researched:** 2026-03-08
**Domain:** Frontend architecture (HTMX + Jinja2 + FastAPI server-side rendering)
**Confidence:** HIGH

## Summary

This phase transforms a 2252-line monolithic Jinja2 template that renders everything client-side via JavaScript into a tab-based SPA using HTMX for partial content swapping and server-side Jinja2 rendering. The core architectural shift is moving from "server sends JSON, JS builds DOM" to "server sends HTML fragments, HTMX swaps them in." The existing CSS variable system, dark/light theme, and Inter font stack are preserved and polished -- no CSS framework is introduced.

The key technical pattern is dual-mode route handlers: each tab endpoint checks for the `HX-Request` header. If present (HTMX request), it returns only the HTML partial. If absent (direct navigation/refresh), it returns the full `base.html` shell with the correct tab active and content pre-rendered. This ensures bookmarkable URLs work correctly.

**Primary recommendation:** Use HTMX 2.0 via CDN with `HX-Request` header detection in FastAPI to serve partials vs full pages, Chart.js 4.x via CDN for performance charts, and split the monolithic template into a shell + 5 partials + shared macros.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Tab-based SPA using HTMX -- NOT separate full HTML pages
- Single `base.html` shell with nav tabs that swap content via `hx-get` to partial endpoints
- Pages: Tonight's Games (default), Value Bets, Arbitrage, Performance, Player Props
- `hx-push-url` on tabs for bookmarkable URLs (e.g., `/value-bets`, `/arbs`)
- FastAPI serves both full page (GET `/value-bets`) and partial (GET `/partials/value-bets`)
- Full page requests render base.html with the correct tab active; partial requests return HTML fragment only
- Keep existing CSS variable system -- do NOT add Tailwind or DaisyUI
- Polish existing CSS: tighten spacing, improve card layouts, add missing breakpoints
- Add glassmorphism touches (subtle `backdrop-filter: blur`) on key panels
- Add micro-interactions: card hover lifts, smooth transitions, count-up animations
- HTMX via CDN -- no npm install
- Tab switching: `hx-get="/partials/games"` with `hx-target="#content"` and `hx-swap="innerHTML"`
- Auto-refresh: `hx-trigger="every 60s"` on active content panel
- No SSE -- HTMX polling at 60s
- Split base.html into shell + 5 partials + shared macros
- Each partial is a self-contained HTML fragment renderable independently
- Shared CSS stays in base.html `<style>` block
- Mobile breakpoints at 480px (phone), 768px (tablet), 1024px (desktop)
- Game cards: `minmax(300px, 1fr)` on mobile
- Nav tabs: horizontal scroll with overflow on mobile (no hamburger menu)
- Touch-friendly: minimum 44px tap targets
- No npm/build step -- all frontend assets via CDN or inline
- Must preserve CLI rendering path (presentation.py stays)
- Must preserve all existing API endpoints (no breaking changes)

### Claude's Discretion
- Exact CSS polish details (shadows, gradients, spacing values)
- How to handle the modal system across pages (global modal vs per-page)
- Chart library choice for performance page (Chart.js CDN vs lightweight alternative)
- Whether to add skeleton loading states during HTMX swaps
- Sort/filter interactions on value bets table
- Book chip filter state persistence across tab switches

### Deferred Ideas (OUT OF SCOPE)
- SSE real-time push -- defer to Phase 8 or later (HTMX polling sufficient for now)
- TradingView Lightweight Charts -- defer until line movement feature is more mature
- Component library / design system -- premature at this scale
- User preferences persistence (theme, default tab) -- Phase 10 with auth
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| R5.3 | Multi-page routing: Tonight's Games, Value Bets, Arbs, Performance, Props | HTMX tab navigation with `hx-push-url` + dual-mode route handlers (partial vs full page) |
| R5.4 | Tailwind CSS for professional styling (OVERRIDDEN: keep existing CSS) | Existing CSS variable system with Inter font, dark/light theme; polish with glassmorphism + micro-interactions |
| R5.5 | HTMX for dynamic partial updates | HTMX 2.0 via CDN, `hx-get` + `hx-target` + `hx-swap="innerHTML"`, `hx-trigger="every 60s"` for polling |
| R5.6 | Mobile-responsive layout | CSS breakpoints at 480/768/1024px, horizontal scroll nav, touch targets 44px+ |
| R5.7 | Real-time odds via SSE (DEFERRED: use HTMX polling) | `hx-trigger="every 60s"` replaces current JS `setInterval`, stop with HTTP 286 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| HTMX | 2.0.x | Partial HTML swaps, tab nav, polling | De facto standard for hypermedia-driven apps; CDN, no build step |
| Jinja2 | (bundled with FastAPI) | Server-side HTML rendering | Already used by FastAPI; `{% include %}` for partials, `{% macro %}` for reusable components |
| Chart.js | 4.5.x | Performance page charts (P&L, ROI) | Most popular charting lib, CDN-friendly, ~70KB gzipped, canvas-based |
| FastAPI | (existing) | Route handlers, template responses | Already in use; add partial endpoints alongside existing API routes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| htmx (head-support ext) | 2.0.x | Swap `<title>` on tab switch | Optional: include if you want browser tab title to update per page |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Chart.js | Inline SVG/CSS bars | Simpler but limited to bar charts; Chart.js needed for line charts on performance page |
| Chart.js | uPlot (~35KB) | Lighter but less documentation, fewer chart types |

**Installation:**
```html
<!-- In base.html <head> -->
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.js"></script>
```

No `pip install` or `npm install` needed. Both are CDN-only.

## Architecture Patterns

### Recommended Project Structure
```
app/web/
  app.py                     # FastAPI app + route handlers (existing + new partial routes)
  presentation.py            # CLI rendering (preserved, unchanged)
  deep_links.py              # Sportsbook URLs (preserved, unchanged)
  templates/
    base.html                # Shell: <head>, nav tabs, #content div, footer, CSS, HTMX script
    partials/
      games.html             # Tonight's Games tab content
      value_bets.html        # Value Bets tab content (table + plays cards)
      arbs.html              # Arbitrage tab content
      performance.html       # Performance tracker tab content (Chart.js)
      props.html             # Player Props tab content
    macros/
      cards.html             # Shared macros: game_card(), stat_pill(), badge(), etc.
```

### Pattern 1: Dual-Mode Route Handlers (Full Page vs Partial)
**What:** Each tab URL serves either the full page or just the partial, detected via `HX-Request` header.
**When to use:** Every tab route.
**Example:**
```python
# Source: HTMX docs (htmx.org/docs/) - HX-Request header
@app.get("/value-bets", response_class=HTMLResponse)
def value_bets_page(request: Request, demo: str = "0"):
    data = _get_dashboard_data(demo)
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        # HTMX tab click -> return partial only
        return templates.TemplateResponse(
            request=request,
            name="partials/value_bets.html",
            context={"data": data},
        )
    # Direct navigation / refresh -> return full page with tab active
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context={"data": data, "active_tab": "value-bets"},
    )
```

### Pattern 2: Tab Navigation with HTMX
**What:** Nav tabs use `hx-get` to fetch partials and swap into `#content`.
**When to use:** The navigation bar in `base.html`.
**Example:**
```html
<!-- Source: htmx.org/attributes/hx-push-url/ -->
<nav class="tab-nav">
  <a class="tab {% if active_tab == 'games' %}active{% endif %}"
     hx-get="/value-bets"
     hx-target="#content"
     hx-swap="innerHTML"
     hx-push-url="true">
    Tonight's Games
  </a>
  <!-- ... more tabs -->
</nav>
<div id="content">
  {% include "partials/games.html" %}
</div>
```

### Pattern 3: Auto-Refresh via HTMX Polling
**What:** Active content panel auto-refreshes every 60 seconds.
**When to use:** On the `#content` div or within each partial.
**Example:**
```html
<!-- Source: htmx.org/docs/ - polling -->
<!-- In each partial, wrap content with a polling trigger -->
<div hx-get="/games" hx-trigger="every 60s" hx-target="this" hx-swap="innerHTML">
  <!-- game cards here -->
</div>
```
Note: Polling can be stopped server-side by returning HTTP 286.

### Pattern 4: Server-Side Rendering with Jinja2 Macros
**What:** Reusable HTML components as Jinja2 macros instead of JS template literals.
**When to use:** Game cards, stat pills, badges, any repeated UI element.
**Example:**
```html
<!-- macros/cards.html -->
{% macro game_card(game) %}
<div class="game-card {% if game.has_value %}has-value{% endif %}">
  <div class="game-header">
    <div class="game-matchup">
      <span class="team-badge">{{ game.away }}</span>
      <span class="vs">@</span>
      <span class="team-badge">{{ game.home }}</span>
    </div>
    <span class="game-time">{{ game.time }}</span>
  </div>
  <div class="prob-buttons">
    <div class="prob-btn {% if game.away_prob > game.home_prob %}fav{% endif %}">
      <span class="prob-team">{{ game.away }}</span>
      <span class="prob-pct">{{ "%.0f"|format(game.away_prob * 100) }}%</span>
    </div>
    <div class="prob-btn {% if game.home_prob > game.away_prob %}fav{% endif %}">
      <span class="prob-team">{{ game.home }}</span>
      <span class="prob-pct">{{ "%.0f"|format(game.home_prob * 100) }}%</span>
    </div>
  </div>
</div>
{% endmacro %}
```

### Pattern 5: Loading States During HTMX Swaps
**What:** Show skeleton/spinner while HTMX fetches new content.
**When to use:** Tab switches.
**Example:**
```html
<style>
  .htmx-request #content { opacity: 0.5; transition: opacity 200ms; }
  .htmx-indicator { display: none; }
  .htmx-request .htmx-indicator { display: block; }
</style>
```

### Anti-Patterns to Avoid
- **Client-side JS rendering from JSON:** The current pattern. Move ALL rendering to Jinja2 server-side. The only JS should be for interactivity (sort, filter, modals, Chart.js init), not for building DOM.
- **Duplicating data fetching per partial:** Extract a shared `_get_dashboard_data(demo)` helper used by all routes, backed by the existing TTLCache.
- **Inline `<script>` in every partial:** Keep page-specific JS minimal. Chart.js init goes in performance partial; modal and sort/filter JS go in base.html since they are shared.
- **Breaking existing API endpoints:** All `/api/*` routes must remain unchanged. New partial routes are additive.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Partial vs full page detection | Custom middleware or decorator | Check `request.headers.get("HX-Request")` directly in handler | Simple one-liner, no abstraction needed |
| URL history management | Custom pushState JS | HTMX `hx-push-url="true"` | HTMX handles history snapshot/restore automatically |
| Polling / auto-refresh | JS `setInterval` + `fetch` + DOM rebuild | HTMX `hx-trigger="every 60s"` | Declarative, no JS needed, can stop with HTTP 286 |
| Loading indicators | Custom JS show/hide spinner | CSS `.htmx-request` class | HTMX adds class automatically during requests |
| Template components | JS template literals (current) | Jinja2 `{% macro %}` | Server-rendered, SEO-friendly, no JS needed |
| Charts (P&L, ROI) | Custom SVG/Canvas drawing | Chart.js via CDN | Battle-tested, responsive, dark theme support |

**Key insight:** The current codebase's biggest complexity is 800+ lines of JavaScript that build DOM from JSON. Moving to server-side Jinja2 rendering eliminates most of this JS. HTMX replaces the remaining client-side data fetching.

## Common Pitfalls

### Pitfall 1: Browser Refresh Returns Partial Instead of Full Page
**What goes wrong:** User navigates to `/value-bets` via HTMX (gets partial), then refreshes the page. The server must detect this is a full page request and return `base.html` with the correct tab active.
**Why it happens:** Forgetting to check `HX-Request` header, or returning partial for all requests.
**How to avoid:** Every tab route MUST check `request.headers.get("HX-Request")`. Non-HTMX requests get `base.html` with the partial `{% include %}`'d inside.
**Warning signs:** Refreshing a tab URL shows only a fragment of HTML with no CSS/nav.

### Pitfall 2: Stale Data After Tab Switch
**What goes wrong:** User switches tabs but sees cached/old data because the polling timer from the previous tab is still running.
**Why it happens:** HTMX swaps innerHTML but old `hx-trigger="every 60s"` elements were in the previous DOM and are now gone. This actually works correctly -- HTMX stops polling when elements are removed from DOM.
**How to avoid:** Put the `hx-trigger="every 60s"` on a div INSIDE each partial (not on #content). When the partial is swapped out, the polling trigger goes with it.
**Warning signs:** Network tab shows requests to the wrong partial endpoint.

### Pitfall 3: Game Card Modal Breaks After Tab Switch
**What goes wrong:** Modal is defined in base.html but the JS that opens it references elements inside a partial that may not be loaded.
**Why it happens:** The modal click handler was registered on elements that got swapped out.
**How to avoid:** Use event delegation on `#content` or the `<body>` for modal triggers. Define the modal overlay in `base.html` (outside `#content`). Use `htmx:afterSwap` event to re-bind if needed.
**Warning signs:** Clicking a game card does nothing after switching tabs.

### Pitfall 4: CSS Transition Jank on HTMX Swaps
**What goes wrong:** Content appears with no transition, causing a visual "jump."
**Why it happens:** HTMX `innerHTML` swap is instant by default.
**How to avoid:** Use `hx-swap="innerHTML transition:true"` or add CSS transitions on `.htmx-settling` class. Or use the `htmx:afterSwap` event to trigger entry animations.
**Warning signs:** Tab content appears abruptly.

### Pitfall 5: Book Filter State Lost on Tab Switch
**What goes wrong:** User selects specific book filters, switches to Arbs tab, switches back, and all filters are reset.
**Why it happens:** HTMX replaces the entire `#content` div, destroying the filter state.
**How to avoid:** Either (a) keep book filters in `base.html` shell (outside `#content`) so they persist, or (b) pass active filters as query params in the `hx-get` URL, or (c) store in `sessionStorage` and restore via `htmx:afterSwap`.
**Warning signs:** Users have to re-select book filters every time they switch tabs.

### Pitfall 6: Demo Mode Not Propagated to Partial Requests
**What goes wrong:** Full page loads with `?demo=1` but HTMX partial requests don't include the demo param, causing live API calls.
**Why it happens:** HTMX `hx-get` URL doesn't include query params from the original page load.
**How to avoid:** Pass demo/region/bankroll params via `hx-vals` attribute or include them in the `hx-get` URL dynamically. Alternatively, store mode in a server-side session or cookie.
**Warning signs:** Demo mode works on initial load but breaks when switching tabs.

## Code Examples

### HTMX Tab Navigation (base.html shell)
```html
<!-- Source: htmx.org/docs/ -->
<nav class="tab-nav" id="tab-nav">
  <a class="tab {% if active_tab == 'games' %}active{% endif %}"
     hx-get="/games"
     hx-target="#content"
     hx-swap="innerHTML"
     hx-push-url="/games"
     hx-indicator="#loading"
     onclick="setActiveTab(this)">
    Tonight's Games
  </a>
  <a class="tab {% if active_tab == 'value-bets' %}active{% endif %}"
     hx-get="/value-bets"
     hx-target="#content"
     hx-swap="innerHTML"
     hx-push-url="/value-bets"
     hx-indicator="#loading"
     onclick="setActiveTab(this)">
    Value Bets
  </a>
  <!-- ... arbs, performance, props -->
</nav>
<div id="loading" class="htmx-indicator">Loading...</div>
<div id="content">
  {% include "partials/" + active_tab|replace("-", "_") + ".html" %}
</div>
```

### FastAPI Route Handler with HX-Request Detection
```python
# Source: htmx.org/docs/ - Request Headers
@app.get("/games", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
def games_page(request: Request, demo: str = "0", region: str = "qc",
               bankroll: float = 1000.0, min_edge: float = 2.0, min_ev: float = 0.02):
    params = _make_params(region=region, bankroll=bankroll, min_edge=min_edge, min_ev=min_ev)
    data = _build_demo_dashboard(params) if _is_demo(demo) else _build_live_dashboard(params)

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request=request,
            name="partials/games.html",
            context={"data": data},
        )
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context={"data": data, "active_tab": "games"},
    )
```

### Chart.js Integration (in performance.html partial)
```html
<!-- Source: chartjs.org/docs/latest/getting-started/ -->
<canvas id="pl-chart" height="200"></canvas>
<script>
document.addEventListener('htmx:afterSwap', function(evt) {
  if (!document.getElementById('pl-chart')) return;
  const ctx = document.getElementById('pl-chart').getContext('2d');
  const months = JSON.parse('{{ months_json|safe }}');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: months.map(m => m.month),
      datasets: [{
        data: months.map(m => m.profit),
        backgroundColor: months.map(m => m.profit >= 0
          ? 'rgba(16,185,129,0.7)' : 'rgba(239,68,68,0.7)'),
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        y: { grid: { color: 'rgba(51,65,85,0.3)' } },
        x: { grid: { display: false } }
      }
    }
  });
});
</script>
```

### Mobile-Responsive Tab Navigation
```css
/* Source: Project CSS conventions */
.tab-nav {
  display: flex;
  gap: 2px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  padding-bottom: 2px;
}
.tab-nav::-webkit-scrollbar { display: none; }
.tab {
  white-space: nowrap;
  padding: 10px 20px;
  min-height: 44px; /* touch target */
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
  cursor: pointer;
  text-decoration: none;
}
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
@media (max-width: 480px) {
  .tab { padding: 10px 14px; font-size: 12px; }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Client-side JS renders DOM from JSON | Server-side Jinja2 renders HTML fragments | This phase | Eliminates ~800 lines of JS template code |
| Full page refresh / setInterval polling | HTMX partial swaps + declarative polling | This phase | Smoother UX, less bandwidth, no flash of empty content |
| Single monolithic page | Tab-based SPA with bookmarkable URLs | This phase | Better navigation, shareable deep links |
| HTMX 1.x | HTMX 2.0.x | 2024-06 | Improved defaults, smaller bundle, better browser support |

**Deprecated/outdated:**
- HTMX 1.x: Still works but 2.0 is current stable. Use 2.0.x.
- Chart.js 3.x: Use 4.x (tree-shaking, better defaults).

## Discretion Recommendations

### Modal System: Global Modal in base.html
**Recommendation:** Keep a single modal overlay in `base.html` (outside `#content`). Use event delegation on `document.body` to handle clicks on game cards in any partial. The modal content can be populated via a small HTMX request (`hx-get="/partials/game-modal?game_id=X"`) or via JS from data attributes on the card.
**Rationale:** Avoids duplicating modal markup in every partial. Survives tab switches.

### Chart Library: Chart.js 4.x via CDN
**Recommendation:** Use Chart.js. It is the standard choice for CDN-based charting without a build step. ~70KB gzipped is acceptable for a dashboard. The performance page needs bar charts (monthly P&L) and potentially line charts (cumulative ROI). Chart.js handles both well.
**Rationale:** uPlot is lighter but has less documentation and fewer chart types. The existing app already renders bar charts via JS, so the migration to Chart.js is straightforward.

### Skeleton Loading States: Yes, Add Them
**Recommendation:** Use CSS-only skeleton states via the `.htmx-request` class. Fade the content area to 50% opacity during swaps, with a subtle loading indicator. No JS needed.
**Rationale:** Tab switches may take 100-500ms (especially if fetching live data). A visual loading state prevents the UI from feeling broken.

### Sort/Filter on Value Bets Table: Keep Client-Side JS
**Recommendation:** Keep sort/filter as client-side JS within the `value_bets.html` partial. The data is already rendered in the table; sorting/filtering rows in JS is simpler than round-tripping to the server.
**Rationale:** The data set is small (typically <50 rows). Server-side sort adds latency for no benefit.

### Book Chip Filter State: Query Params
**Recommendation:** Pass active book filters as query params in `hx-get` URLs. When a user clicks a book chip, update the `hx-get` URL on all tab links to include `?books=bet365,betway`. This way tab switches preserve the filter.
**Rationale:** SessionStorage works but is invisible to the server. Query params are transparent and bookmarkable.

## Open Questions

1. **Demo mode propagation across tab switches**
   - What we know: Current demo mode is via `?demo=1` query param
   - What's unclear: Best way to propagate this to all HTMX partial requests
   - Recommendation: Inject demo flag into `hx-vals` on tab links from the Jinja2 template context, or use a JS helper that reads the current URL params and appends them to `hx-get` URLs

2. **Existing test coverage for new routes**
   - What we know: `tests/web/test_app.py` tests `GET /?demo=1` and API routes
   - What's unclear: How many tests need updating vs. new tests for partial routes
   - Recommendation: Add tests for each new route (both with and without `HX-Request` header), keep existing API tests unchanged

3. **Sparkline rendering in Jinja2**
   - What we know: Current sparklines are rendered via JS (`buildSparkPolyline` function generating SVG)
   - What's unclear: Whether to move sparkline generation to server-side (Python SVG) or keep as client-side JS
   - Recommendation: Keep sparkline rendering as inline JS in the games partial -- SVG generation from data points is simpler in JS, and the data is already available in the template context

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pytest.ini or pyproject.toml (existing) |
| Quick run command | `pytest tests/web/ -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R5.3 | Tab routes return full HTML or partial based on HX-Request header | integration | `pytest tests/web/test_app.py -x -k "partial or tab"` | Needs new tests |
| R5.3 | Direct navigation to /value-bets returns full page | integration | `pytest tests/web/test_app.py -x -k "full_page"` | Needs new tests |
| R5.4 | CSS variables and theme support preserved | smoke | `pytest tests/web/test_app.py -x -k "css or theme"` | Needs new tests |
| R5.5 | HTMX partial endpoints return HTML fragments (not full page) | integration | `pytest tests/web/test_app.py -x -k "partial"` | Needs new tests |
| R5.5 | Polling endpoint responds correctly | integration | `pytest tests/web/test_app.py -x -k "poll"` | Needs new tests |
| R5.6 | Template renders without errors at all breakpoint scenarios | unit | `pytest tests/web/test_app.py -x -k "responsive"` | manual-only (visual) |
| R5.7 | 60s polling replaces setInterval (no JS setInterval in output) | unit | `pytest tests/web/test_app.py -x -k "no_setinterval"` | Needs new tests |

### Sampling Rate
- **Per task commit:** `pytest tests/web/ -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/web/test_partials.py` -- tests for all 5 partial routes (HX-Request header detection)
- [ ] `tests/web/test_tab_routes.py` -- tests for full page routes returning base.html with correct active tab
- [ ] Update `tests/web/test_app.py` -- existing dashboard route tests may need updating if `/` route changes

## Sources

### Primary (HIGH confidence)
- [HTMX Official Docs](https://htmx.org/docs/) - HX-Request header, polling, CSS classes, hx-push-url, hx-swap
- [HTMX hx-push-url Attribute](https://htmx.org/attributes/hx-push-url/) - URL history management, DOM snapshot/restore
- [Chart.js Official Docs](https://www.chartjs.org/docs/latest/getting-started/) - CDN installation, chart types, responsive config

### Secondary (MEDIUM confidence)
- [FastAPI as Hypermedia App with HTMX](https://medium.com/@strasbourgwebsolutions/fastapi-as-a-hypermedia-driven-application-w-htmx-jinja2templates-644c3bfa51d1) - Dual-mode handler pattern
- [TestDriven.io FastAPI + HTMX](https://testdriven.io/blog/fastapi-htmx/) - Integration patterns
- [HTMX GitHub Discussions #1700](https://github.com/bigskysoftware/htmx/discussions/1700) - Back/forward button with hx-push-url

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - HTMX 2.0 and Chart.js 4.x are well-documented, CDN-available, and widely used
- Architecture: HIGH - Dual-mode handler pattern (HX-Request detection) is the canonical HTMX approach, documented officially
- Pitfalls: HIGH - Based on known HTMX behavior (header detection, DOM swap lifecycle) and project-specific analysis of current codebase
- CSS/responsive: MEDIUM - Existing CSS system is solid; specific polish values are discretionary

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (HTMX 2.0 and Chart.js 4.x are stable releases)
