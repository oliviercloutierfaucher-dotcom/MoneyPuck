# Phase 1: Persistent Storage - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Stop losing SQLite data on Railway deploys. Mount a Railway volume so predictions, bet history, settlement data, and closing odds survive across deployments. No schema changes, no database migration.

</domain>

<decisions>
## Implementation Decisions

### Storage approach
- Keep SQLite — no migration to PostgreSQL
- Mount a Railway volume at `/data`
- Point `DB_PATH` to `/data/tracker.db` when running on Railway
- Use `RAILWAY_VOLUME_MOUNT_PATH` or `MONEYPUCK_DB_PATH` env var to configure

### Environment detection
- If `RAILWAY_VOLUME_MOUNT_PATH` is set, use that path for DB
- If `MONEYPUCK_DB_PATH` is set, use that (existing behavior)
- Fallback to `~/.moneypuck/tracker.db` for local dev

### Dockerfile changes
- Update to create `/data` directory (or let Railway volume handle it)
- Ensure `appuser` has write permissions to the volume mount

### Odds API caching
- Add server-side response caching to reduce API credit burn from 60s auto-refresh
- Cache odds responses for 60-120 seconds (in-memory dict with TTL)
- Fits this phase because it's a reliability/cost concern

### Claude's Discretion
- Exact cache implementation (dict with timestamp vs lru_cache)
- Whether to add a /health endpoint checking DB connectivity
- Test approach for volume persistence (can't test Railway deploys locally)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `database.py:DB_PATH` — already uses `MONEYPUCK_DB_PATH` env var, just needs Railway volume awareness
- `_fetch_with_retry()` in data_sources.py — retry pattern can inform cache design

### Established Patterns
- Env var configuration: `ODDS_API_KEY`, `LOG_LEVEL`, `PREVIEW_HOST`, `PREVIEW_PORT` all use `os.getenv()`
- Database initialization: `TrackerDatabase.__init__` creates parent dirs and runs schema SQL

### Integration Points
- `app/data/database.py` line 13: `DB_PATH` constant — primary change point
- `Dockerfile` line 15-16: mkdir and chown for `.moneypuck` — needs volume path
- `app/web/web_preview.py`: odds fetching — cache integration point

</code_context>

<specifics>
## Specific Ideas

No specific requirements — straightforward infrastructure fix.

</specifics>

<deferred>
## Deferred Ideas

- PostgreSQL migration — revisit if multi-server scaling needed
- Automated DB backups — Phase 8 (Automated Operations)
- Redis caching — overkill for now, in-memory dict is fine

</deferred>

---

*Phase: 01-persistent-storage*
*Context gathered: 2026-03-06*
