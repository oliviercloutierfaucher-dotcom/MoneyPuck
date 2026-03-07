# Phase 6: FastAPI Migration - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the stdlib `BaseHTTPRequestHandler` in `web_preview.py` with FastAPI + Uvicorn. Extract the 2314-line f-string HTML in `presentation.py` into Jinja2 templates. Same functionality, proper web framework. No UI redesign (that's Phase 7).

</domain>

<decisions>
## Implementation Decisions

### Template decomposition
- Minimal split: convert the single f-string into a single `base.html` Jinja2 template with CSS/JS still inline
- No component decomposition now — Phase 7 does the full UI rebuild with Tailwind/HTMX/multi-page
- Extract `to_serializable()` and data prep functions out of presentation.py — they stay as Python utility functions
- Jinja2 templates live in `app/web/templates/`

### API structure
- Keep existing paths: `/`, `/api/dashboard`, `/api/performance`, `/api/opportunities`, `/api/odds-history`
- Use `APIRouter(prefix="/api")` for JSON endpoints, page routes on main app
- This sets up Phase 7 to add page routes (`/games`, `/value-bets`, etc.) and Phase 10 to add auth middleware
- All existing JSON response formats preserved — no breaking changes

### Migration scope
- Full replacement — delete `BaseHTTPRequestHandler` and `ThreadingHTTPServer` entirely
- No fallback, no gradual migration — clean swap
- `TTLCache` stays (it's a simple utility, not tied to stdlib HTTP)
- `web_preview.py` becomes `app/web/app.py` (FastAPI app instance + routes)
- Old `web_preview.py` deleted after migration complete
- FastAPI's async + uvicorn replaces `ThreadingHTTPServer`

### Deployment changes
- Dockerfile CMD: `uvicorn app.web.app:app --host 0.0.0.0 --port $PORT`
- Single worker (Railway), no hot reload in prod
- `requirements.txt` adds: `fastapi`, `uvicorn[standard]`, `jinja2`
- Railway config unchanged (still uses PORT env var, same Docker build)

### Claude's Discretion
- Whether to use async endpoints or sync (FastAPI supports both)
- How to handle the existing demo mode toggle in FastAPI context
- Error handling middleware design
- Whether to add a `/health` endpoint now or defer to Phase 8
- How to structure the app factory pattern (if any)
- Test strategy for FastAPI routes (TestClient vs direct)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TTLCache` at `app/web/web_preview.py:45` — simple in-memory cache with 90s TTL, reuse as-is
- `to_serializable()` at `app/web/presentation.py:8` — converts ValueCandidate to JSON-safe dicts
- `render_dashboard()` at `app/web/presentation.py:48` — the massive f-string to convert to Jinja2
- `build_sportsbook_url()` from `app/web/deep_links.py` — already separated, no changes needed

### Established Patterns
- Route handling via if/elif path matching in `do_GET()` at `web_preview.py:1011`
- 4 API routes: `/api/dashboard`, `/api/performance`, `/api/opportunities`, `/api/odds-history`
- Page route: `/` serves full HTML dashboard
- JSON responses with `json.dumps()` and `application/json` content type
- Error handling: try/except around route handlers, 500 response on failure

### Integration Points
- `build_market_snapshot()` and `score_snapshot()` from `app/core/service.py` — called by web handler
- `build_player_tiers()` and `calculate_injury_adjustment()` from `app/core/injury_impact.py` — per-game enrichment
- `fetch_player_props()` and related from `app/data/player_props.py` — props API endpoint
- `record_snapshots_from_dashboard()` from `app/data/odds_history.py` — sparkline data recording
- `tracker.py` imports and starts the web server — needs updating to use uvicorn
- `Dockerfile` CMD line — needs updating to uvicorn command
- All web tests in `tests/web/` — need updating to use FastAPI TestClient

</code_context>

<specifics>
## Specific Ideas

- User wants deployment tonight — keep migration surgical, don't over-engineer
- Phase 7 does the real UI work — this phase is purely backend swap + template extraction
- Same look, same feel, same data — just served by FastAPI instead of stdlib
- R5.1 says "keep existing pipeline" — the agent pipeline is untouched, only the HTTP layer changes

</specifics>

<deferred>
## Deferred Ideas

- Multi-page routing with Tailwind/HTMX — Phase 7
- SSE for real-time odds push — Phase 7
- Health check endpoint — Phase 8
- Auth middleware — Phase 10

</deferred>

---

*Phase: 06-fastapi-migration*
*Context gathered: 2026-03-07*
