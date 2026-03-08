# Phase 8: Automated Operations - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated daily settlement, model refresh, health monitoring, and odds API cost optimization. No new features -- make existing operations run unattended. Settlement already works manually (settle_outstanding() in service.py); this phase puts it on autopilot.

</domain>

<decisions>
## Implementation Decisions

### Scheduling approach
- Railway cron service (separate from main web app)
- Cron hits internal API endpoints on the main app (no CLI/subprocess)
- Two protected endpoints: POST /api/cron/settle and POST /api/cron/refresh
- Endpoints secured with a shared CRON_SECRET env var (Bearer token)
- Settlement: daily at 10:30 UTC (6:30 AM ET) -- all NHL games final by then
- Model refresh: daily at 16:00 UTC (12:00 PM ET) -- fresh model before evening games
- Single Dockerfile for cron service that runs curl commands on schedule

### Failure handling & alerts
- Log all cron results to SQLite (new cron_log table: timestamp, task, status, details, duration_ms)
- On failure: retry once after 5 minutes, then log as failed
- No external alerting (Slack/email) for now -- /health endpoint exposes staleness
- Settlement failures are non-critical (next day catches up)
- Data source failures (Odds API, MoneyPuck CSV, ESPN) logged with source name and error
- Polymarket 422 errors should be caught and silenced (known broken, don't spam logs)

### Health check design
- GET /health returns JSON with service status:
  - status: "healthy" | "degraded" | "unhealthy"
  - last_settlement: ISO timestamp (null if never)
  - last_model_refresh: ISO timestamp (null if never)
  - odds_cache_age_seconds: int
  - db_writable: bool
  - data_sources: {odds_api: "ok"|"error"|"exhausted", moneypuck: "ok"|"error", espn: "ok"|"error", polymarket: "ok"|"error"}
- "degraded" if last_settlement > 36 hours ago or any non-Polymarket data source erroring
- "unhealthy" if db not writable or last_settlement > 72 hours
- Railway HEALTHCHECK in Dockerfile already hits / -- update to hit /health instead
- No auth on /health (public, used by uptime monitors)

### Odds API cost control
- Existing 90s TTLCache stays for web requests
- Add disk-based odds cache: save last successful odds response to /data/odds_cache.json with timestamp
- On Odds API failure (401/429/5xx): serve from disk cache with "cached" flag
- Skip odds fetching between 6:00-14:00 UTC (no games, save credits)
- Add request counter: track daily API calls in SQLite, warn at 80% of monthly quota
- Dashboard shows "Cached" or "Stale" indicator when serving from disk cache vs live

### Claude's Discretion
- Exact cron service Dockerfile and railway.json configuration
- cron_log table schema details
- How model refresh updates Elo ratings (incremental vs full rebuild)
- Retry timing and backoff strategy
- Health check response format details

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core/service.py:settle_outstanding()` -- Full settlement logic, matches predictions to NHL results
- `app/core/service.py:build_market_snapshot()` -- Pipeline that computes team strength, Elo, edges
- `app/math/elo.py` -- Elo rating system with incremental game updates
- `app/web/app.py:TTLCache` -- 90s in-memory cache for odds responses
- `app/data/database.py:BetTracker.settle()` -- Individual bet settlement in SQLite
- `app/data/data_sources.py` -- All external API fetchers (Odds, MoneyPuck, ESPN, Polymarket)

### Established Patterns
- FastAPI route handlers in app/web/app.py with @app.get/@app.post decorators
- SQLite via app/data/database.py BetTracker class
- 3-tier DB path: RAILWAY_VOLUME_MOUNT_PATH > MONEYPUCK_DB_PATH > ~/.moneypuck/tracker.db
- Security middleware in app.py (CSP, X-Frame-Options, etc.)

### Integration Points
- /api/cron/settle and /api/cron/refresh endpoints go in app/web/app.py
- cron_log table added to app/data/database.py BetTracker
- Health check at /health in app/web/app.py
- Dockerfile HEALTHCHECK updated to /health
- Railway cron service needs separate service config (railway.json or Railway dashboard)

### Key Constraints
- No npm/external tools -- cron service is just curl + cron in a minimal container
- Must work with Railway volume at /data
- CRON_SECRET shared between cron service and main app via Railway env vars

</code_context>

<specifics>
## Specific Ideas

- Disk-based odds cache at /data/odds_cache.json as fallback when API is exhausted
- Quiet hours (6-14 UTC) skip odds fetching to conserve API credits
- Polymarket 422 errors should be silenced (API changed, not worth retrying)
- Health endpoint designed for uptime monitoring services (UptimeRobot, etc.)

</specifics>

<deferred>
## Deferred Ideas

- Slack/email alerting on failures -- add when there are actual users to notify
- Grafana/metrics dashboard -- overkill at current scale
- Multi-timezone schedule awareness -- single UTC schedule is fine for NHL

</deferred>

---

*Phase: 08-automated-operations*
*Context gathered: 2026-03-08*
