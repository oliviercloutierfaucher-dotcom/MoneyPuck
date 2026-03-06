# Web Frontend Research: Professional UI for MoneyPuck

**Researched:** 2026-03-06
**Mode:** Ecosystem
**Overall confidence:** HIGH

---

## 1. Backend + Frontend Architecture: Recommendation

### Verdict: FastAPI + HTMX + Jinja2 (Option B/C hybrid)

**Why not the other options:**

| Option | Verdict | Why |
|--------|---------|-----|
| A: Stdlib + React SPA | Overkill | Adds Node.js build toolchain, npm dependency tree, separate dev servers. You're one developer building a betting tool, not a SaaS team. React's state management complexity is wasted when your data comes from server-side Python anyway. |
| B: FastAPI + templates | **Winner** | FastAPI is 3 lines of change from your current stdlib server. Serves Jinja2 templates natively. Built-in SSE support. Auto-generates API docs. Async by default. Already the Python web standard. |
| C: Stdlib + Jinja2 | Second best | Avoids adding FastAPI dependency but you manually reimplement routing, static file serving, error handling, SSE -- all things FastAPI gives you free. |
| D: Static site generator | Wrong tool | SSGs are for content sites, not interactive dashboards with live data. |

### Why FastAPI + HTMX specifically

The current codebase is a 2261-line `presentation.py` generating HTML via f-strings with double-brace escaping. This is unmaintainable. The fix is Jinja2 templates (proper HTML files with `{{ variables }}`), served by FastAPI, with HTMX for dynamic updates.

**HTMX advantage over React/Vue:** No JavaScript build step. No npm. No node_modules. No webpack/vite config. You add a single `<script src="htmx.org">` tag and write HTML attributes like `hx-get="/api/games" hx-trigger="every 30s"` to get auto-refreshing sections. The server returns HTML fragments, not JSON.

**Performance data (HIGH confidence):**
- FastAPI + HTMX: First Contentful Paint 300-500ms vs React's 1500-3000ms
- Total page weight: 50-100KB vs React's 1.5-3MB
- HTMX library size: ~14KB gzipped
- No build step means no CI/CD complexity

### Migration path from current codebase

```
Current:  ThreadingHTTPServer + f-string HTML (presentation.py)
Step 1:   FastAPI + Jinja2 templates (extract HTML from f-strings into .html files)
Step 2:   Add HTMX for dynamic sections (replace 60s full-page refresh with partial updates)
Step 3:   Add SSE for live odds (replace polling with server push)
```

The current API endpoints (`/api/dashboard`, `/api/performance`, `/api/opportunities`, `/api/odds-history`) map directly to FastAPI routes. The `do_GET` handler becomes multiple `@app.get()` decorators.

### Required changes to Dockerfile

```dockerfile
# Only change: add uvicorn to requirements
# CMD changes from:
CMD ["python", "-m", "app.web.web_preview"]
# to:
CMD ["uvicorn", "app.web.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### New dependencies

```
fastapi>=0.115
uvicorn[standard]>=0.32
jinja2>=3.1
```

Total addition: 3 packages. No Node.js. No npm. Stays pure Python.

**Confidence: HIGH** -- FastAPI + Jinja2 + HTMX is a well-documented, production-proven pattern with extensive guides and community adoption.

---

## 2. Professional Betting Dashboard UI Patterns

Based on analysis of OddsJam, Action Network, Unabated, and BetQL.

### Universal layout pattern (every pro betting dashboard follows this)

```
+--------------------------------------------------+
| HEADER: Logo | Nav tabs | Region selector | Theme|
+--------------------------------------------------+
| SUMMARY BAR: Total edges | Bankroll | ROI | P&L  |
+--------------------------------------------------+
|                                                    |
|  MAIN CONTENT (tabbed):                           |
|                                                    |
|  [Today's Games] [Value Bets] [Arbs] [Tracker]   |
|                                                    |
|  +----------------------------------------------+ |
|  | GAME CARD (one per matchup)                   | |
|  | Away @ Home  |  7:00 PM ET                    | |
|  | Model: 58.2% |  Best line: -125 (FanDuel)     | |
|  |                                                | |
|  | Book1  Book2  Book3  Book4  Book5 (odds grid) | |
|  | -130   -125   -135   -128   -132              | |
|  | +110   +105   +115   +108   +112              | |
|  |                                                | |
|  | [Edge badge: +3.2%] [EV badge: +$0.04]        | |
|  +----------------------------------------------+ |
|                                                    |
+--------------------------------------------------+
| SIDEBAR (desktop) or BOTTOM SHEET (mobile):       |
| - Power Rankings                                  |
| - Line Movement chart                             |
| - Quick filters                                   |
+--------------------------------------------------+
```

### Key UI elements that make it look "professional"

1. **Odds grid** -- Multi-book comparison in a compact table. Best odds highlighted in green. This is the #1 feature users expect.

2. **Color-coded edges** -- Green for positive EV, amber for marginal, no color for negative. Gradient intensity shows edge magnitude.

3. **Star/badge rating system** -- BetQL uses 1-5 stars. OddsJam uses percentage badges. Quick visual scan of bet quality.

4. **Real-time latency indicator** -- Unabated shows a small dot per book indicating data freshness. Builds trust.

5. **Sticky header with summary stats** -- Bankroll, daily P&L, active bets count. Always visible.

6. **Game cards, not just tables** -- Each matchup is a visual card with team logos/colors, not a spreadsheet row. Cards expand to show details.

7. **Dark mode default** -- Every pro betting tool defaults to dark mode. Your current dark theme is correct. Add a light mode toggle.

8. **Sportsbook logos** -- Visual recognition is faster than reading "FanDuel". Use book icons/colors in the odds grid.

### Features MoneyPuck already has (keep these)

- Dark theme with cyan/green accent colors (matches industry standard)
- Multi-book odds comparison grid
- Value bet highlighting with edge percentages
- Performance tracking section
- Deep links to sportsbooks
- Auto-refresh (60s polling)

### Features to add for professional tier

| Feature | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| Tabbed navigation (Games/Bets/Arbs/Tracker/Rankings) | P0 | Low | Currently one long scroll page |
| Game cards instead of table rows | P0 | Medium | Visual upgrade, each game expandable |
| Responsive mobile layout | P0 | Medium | Current layout breaks on mobile |
| Line movement sparklines | P1 | Medium | Already have sparkline data in odds_history |
| Bet slip / calculator sidebar | P1 | Medium | Kelly calc is backend-ready |
| Filter bar (sport, book, min edge) | P1 | Low | Query params already support this |
| Team logos/colors | P2 | Low | Static assets, NHL team color map |
| Notification badges for new edges | P2 | Low | SSE-powered |
| User accounts / saved preferences | P3 | High | Needs auth, database |

---

## 3. Mobile-Responsive Patterns for Data-Heavy Betting Apps

### Core approach: Cards on mobile, tables on desktop

```css
/* Desktop: odds grid as table */
@media (min-width: 768px) {
  .odds-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(80px, 1fr)); }
}

/* Mobile: stack vertically, show best line prominently */
@media (max-width: 767px) {
  .odds-grid { display: none; } /* Hide full grid */
  .best-line { display: block; } /* Show only best odds */
  .game-card { /* Swipe to expand for full grid */ }
}
```

### Mobile-specific patterns from pro apps

1. **Progressive disclosure** -- Show game + best line on mobile. Tap to expand full book comparison. Don't try to fit 8 sportsbook columns on a phone.

2. **Bottom tab navigation** -- Not a hamburger menu. Tabs for: Games, Bets, Arbs, Profile. Thumb-reachable.

3. **Swipeable game cards** -- Swipe left for quick bet action, swipe right to dismiss/save.

4. **Pull-to-refresh** -- Standard mobile pattern. Replace the current 60s auto-refresh with pull-to-refresh on mobile.

5. **Sticky filters** -- Sport/region filter bar sticks to top of scroll area.

### CSS approach

Use CSS Grid + CSS custom properties (you already have CSS variables). No framework needed for layout -- your current CSS is already 90% there. The main gap is the `@media` queries for responsive breakpoints.

**Recommended breakpoints:**
- Mobile: < 640px (single column, cards)
- Tablet: 640-1024px (2 columns, compact grid)
- Desktop: > 1024px (full grid, sidebar)

---

## 4. Real-Time Updates: Use SSE (Server-Sent Events)

### Recommendation: SSE over WebSocket

| Criterion | SSE | WebSocket | Polling (current) |
|-----------|-----|-----------|-------------------|
| Direction | Server -> Client | Bidirectional | Client -> Server |
| Complexity | Low | Medium | Lowest |
| Auto-reconnect | Built-in | Manual | N/A |
| HTTP/2 compatible | Yes | Separate protocol | Yes |
| Proxy-friendly | Yes | Sometimes blocked | Yes |
| Python stdlib support | No (need FastAPI) | No (need library) | Yes |
| Right for odds updates | **Yes** | Overkill | Works but wasteful |

**Why SSE wins for MoneyPuck:**
- Odds flow one direction: server to client. You never need the client to push data to the server (except config changes, which are regular HTTP POST).
- SSE has built-in reconnection. If the Railway container restarts, clients auto-reconnect.
- SSE works through HTTP proxies, corporate firewalls, CDNs. WebSocket sometimes doesn't.
- FastAPI has native SSE support via `StreamingResponse` with `text/event-stream` content type.

### Implementation pattern

```python
# FastAPI SSE endpoint
@app.get("/api/stream/odds")
async def stream_odds():
    async def event_generator():
        while True:
            data = await get_latest_odds()  # Your existing pipeline
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(30)  # Update interval
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

```html
<!-- HTMX SSE integration -->
<div hx-ext="sse" sse-connect="/api/stream/odds" sse-swap="message">
  <!-- Content auto-updates when server pushes new data -->
</div>
```

### Recommended update intervals

| Data type | Interval | Rationale |
|-----------|----------|-----------|
| Odds/lines | 30-60s | Odds API rate limits, data freshness balance |
| Game scores (live) | 10-15s | If you add live game tracking |
| Performance/P&L | 5 min | Slow-changing, expensive to compute |
| Rankings | On-demand | Only changes after games complete |

**Confidence: HIGH** -- SSE is the standard recommendation for unidirectional real-time data. FastAPI supports it natively.

---

## 5. CSS Framework: Tailwind CSS via CDN (no build step)

### Recommendation: Tailwind CSS Play CDN for now, migrate to built Tailwind later

**Why Tailwind:**
- Your current CSS is already utility-like (custom properties, atomic styles). Tailwind formalizes this.
- Best-in-class responsive utilities (`md:grid-cols-3`, `sm:hidden`).
- Dark mode built-in (`dark:bg-gray-900`).
- Every betting dashboard template on the market uses Tailwind.

**Why CDN first:**
- Zero build step. Add one `<script>` tag. Matches the "no npm" constraint of HTMX approach.
- Tailwind Play CDN: `<script src="https://cdn.tailwindcss.com"></script>` -- works in production for small apps.
- Migrate to PostCSS build when/if you add a build step later.

**Why not Bootstrap:**
- Bootstrap's opinionated component styles look generic. You want the MoneyPuck brand to feel custom.
- Bootstrap's JS components (modals, dropdowns) conflict with HTMX's approach.
- Tailwind gives you the same grid/responsive system without the visual "Bootstrap look."

**Why not custom CSS only (current approach):**
- Your current CSS is 800+ lines of hand-written styles. Tailwind eliminates 90% of it.
- Responsive design with custom CSS requires writing every media query manually.
- Tailwind's utility classes are self-documenting in the HTML.

### DaisyUI consideration

DaisyUI adds component classes (`btn`, `card`, `badge`, `table`) on top of Tailwind. Useful for rapid prototyping. Also available via CDN. Consider adding it for form elements and badges.

```html
<head>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/daisyui@latest/dist/full.css" rel="stylesheet">
</head>
```

**Confidence: HIGH** -- Tailwind is the dominant CSS framework in 2025-2026. CDN usage is documented and supported.

---

## 6. Multi-Page Routing

### Current state

The `web_preview.py` has a single `do_GET` with path matching:
- `/` or `/index.html` -- Full dashboard HTML
- `/api/dashboard` -- JSON data
- `/api/performance` -- JSON performance data
- `/api/opportunities` -- JSON opportunities
- `/api/odds-history` -- JSON odds history

This is a single-page app with no real routing. All content renders on one page.

### FastAPI routing approach

```python
# app/web/main.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="app/web/templates")

# Page routes (return HTML)
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("games.html", {"request": request})

@app.get("/value-bets")
async def value_bets(request: Request):
    return templates.TemplateResponse("value_bets.html", {"request": request})

@app.get("/arbitrage")
async def arbitrage(request: Request):
    return templates.TemplateResponse("arbitrage.html", {"request": request})

@app.get("/tracker")
async def tracker(request: Request):
    return templates.TemplateResponse("tracker.html", {"request": request})

@app.get("/rankings")
async def rankings(request: Request):
    return templates.TemplateResponse("rankings.html", {"request": request})

# API routes (return JSON, same as current)
@app.get("/api/dashboard")
async def api_dashboard(): ...

@app.get("/api/performance")
async def api_performance(): ...
```

### HTMX partial navigation (feels like SPA, acts like MPA)

With HTMX, tab clicks swap only the main content area, not the full page:

```html
<nav>
  <a hx-get="/partials/games" hx-target="#main-content" hx-push-url="/games">Games</a>
  <a hx-get="/partials/value-bets" hx-target="#main-content" hx-push-url="/value-bets">Value Bets</a>
  <a hx-get="/partials/arbs" hx-target="#main-content" hx-push-url="/arbs">Arbitrage</a>
</nav>
<div id="main-content">
  <!-- Content swaps here without full page reload -->
</div>
```

This gives SPA-like navigation speed with zero JavaScript framework overhead. URLs update in the browser bar (`hx-push-url`), so bookmarks and back button work.

### Recommended page structure

| Page | URL | Content |
|------|-----|---------|
| Tonight's Games | `/` | Game cards with odds grid, model probabilities |
| Value Bets | `/value-bets` | Filtered list of +EV opportunities |
| Arbitrage | `/arbs` | Arb opportunities with calculator |
| Performance | `/tracker` | P&L chart, bet history, ROI stats |
| Power Rankings | `/rankings` | Team rankings table with strength scores |
| Settings | `/settings` | Region, bankroll, thresholds |

---

## 7. Chart Libraries: Use Lightweight Charts + Chart.js

### Two libraries for two purposes

| Use case | Library | Why |
|----------|---------|-----|
| Line movement / odds history | TradingView Lightweight Charts | Purpose-built for financial time series. 35KB. Looks exactly like what betting sites use for line movement. Crosshair, zoom, pan all built-in. |
| Performance / ROI / P&L | Chart.js | Better for bar charts, pie charts, area charts. 254KB but you likely only need it on the tracker page. Huge ecosystem of plugins. |

### TradingView Lightweight Charts for odds movement

This is the exact library that OddsJam-style line movement charts use. It renders candlestick/line/area charts optimized for time-series financial data.

```html
<script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
<script>
  const chart = LightweightCharts.createChart(container, {
    width: 600, height: 300,
    layout: { background: { color: '#0a0e1a' }, textColor: '#94a3b8' },
    grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
  });
  const series = chart.addLineSeries({ color: '#06b6d4' });
  series.setData(oddsHistory); // [{time: '2026-03-01', value: -125}, ...]
</script>
```

**Why not uPlot:** While uPlot is faster (10% CPU vs 40% for Chart.js at 3600 points), Lightweight Charts has better out-of-the-box styling for financial/betting data, and your dataset sizes (odds snapshots every 30-60min for a few days) are tiny -- performance is irrelevant.

**Why not D3:** D3 is a low-level visualization toolkit, not a charting library. You'd spend weeks building what Lightweight Charts gives you in 10 lines.

### Chart.js for performance metrics

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

Use for:
- Cumulative P&L area chart (tracker page)
- ROI by sport/book bar chart
- Win rate over time line chart
- Edge distribution histogram

### Sparklines (already in codebase)

Your `odds_history.py` already generates sparkline data. Use inline SVG sparklines (no library needed) or Lightweight Charts mini instances for the game cards.

**Confidence: HIGH** -- Both libraries are industry standard, CDN-available, well-documented.

---

## Summary: Recommended Stack for Professional UI

```
Backend:     FastAPI + Uvicorn (replace stdlib ThreadingHTTPServer)
Templating:  Jinja2 (replace f-string HTML generation)
Interactivity: HTMX (replace manual fetch/polling JS)
Styling:     Tailwind CSS via CDN (replace 800+ lines custom CSS)
Charts:      TradingView Lightweight Charts (line movement) + Chart.js (performance)
Real-time:   SSE via FastAPI StreamingResponse (replace 60s full-page polling)
Deployment:  Same Dockerfile on Railway, just change CMD to uvicorn
```

### What this does NOT require
- Node.js / npm / node_modules
- JavaScript build toolchain (webpack, vite, esbuild)
- React, Vue, Svelte, or any JS framework
- Separate frontend deployment
- Additional Docker stages

### Migration effort estimate

| Step | Effort | Scope |
|------|--------|-------|
| Add FastAPI + create route handlers | 1-2 days | Extract do_GET logic into @app.get() decorators |
| Extract presentation.py into Jinja2 templates | 2-3 days | Split 2261-line file into ~8 template files |
| Add HTMX for tab navigation + partial updates | 1 day | HTML attributes, no JS to write |
| Swap CSS to Tailwind classes | 2-3 days | Replace custom CSS in templates |
| Add Lightweight Charts for line movement | 1 day | Already have odds history data |
| Add SSE for live updates | 0.5 day | FastAPI StreamingResponse |
| **Total** | **~8-10 days** | Incremental, each step is independently deployable |

---

## Sources

- [FastAPI Static Files Documentation](https://fastapi.tiangolo.com/tutorial/static-files/)
- [Serving React Frontend with FastAPI](https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/)
- [FastAPI + HTMX Modern Approach](https://dev.to/jaydevm/fastapi-and-htmx-a-modern-approach-to-full-stack-bma)
- [Lightweight Python Stack: FastAPI + HTMX + Jinja2](https://dev.to/rerere_l_f165d08cdc06148/lightweight-python-stack-for-modern-frontend-fastapi-htmx-jinja2-1f19)
- [Building Real-Time Dashboards with FastAPI and HTMX](https://medium.com/codex/building-real-time-dashboards-with-fastapi-and-htmx-01ea458673cb)
- [OddsJam Review 2026 (RotoWire)](https://www.rotowire.com/betting/oddsjam-review)
- [Unabated Game Odds Screen](https://unabated.com/articles/learn-about-the-game-odds-screen)
- [BetQL Features 2025](https://betql.co/news/21-ways-you-should-use-betql-in-2025)
- [Design Patterns for Betting App Developers (Ably)](https://ably.com/blog/design-patterns-betting-apps)
- [SSE vs WebSockets Comparison](https://www.freecodecamp.org/news/server-sent-events-vs-websockets/)
- [SSE Beat WebSockets for 95% of Real-Time Apps](https://dev.to/polliog/server-sent-events-beat-websockets-for-95-of-real-time-apps-heres-why-a4l)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [uPlot GitHub - Performance Benchmarks](https://github.com/leeoniya/uPlot)
- [Best CSS Frameworks 2026](https://strapi.io/blog/best-css-frameworks)
- [Top Odds Screens for Sports Bettors 2025](https://www.bettoredge.com/post/top-odds-screens-for-sports-bettors-in-2025)
