# Phase 1: Persistent Storage - Research

**Researched:** 2026-03-06
**Domain:** Railway volumes, SQLite persistence, API response caching
**Confidence:** HIGH

## Summary

Phase 1 fixes the P0 data loss problem: SQLite data disappears on every Railway deploy because the filesystem is ephemeral. The fix is mounting a Railway volume at `/data` and updating `database.py` to write there when running on Railway.

Railway volumes are straightforward but have three critical gotchas: (1) volumes are NOT available at build time or pre-deploy time -- only at runtime, (2) Docker images running as non-root UID have permission issues requiring `RAILWAY_RUN_UID=0`, and (3) each service can only have one volume. The current Dockerfile creates an `appuser` (non-root), which will conflict with volume permissions.

The phase also includes server-side odds response caching to reduce Odds API credit burn from the 60-second auto-refresh. A simple in-memory dict with TTL is the right approach -- no external dependencies needed.

**Primary recommendation:** Set `RAILWAY_RUN_UID=0` as a Railway env var, mount volume at `/data`, update `DB_PATH` resolution to check `RAILWAY_VOLUME_MOUNT_PATH` first, and add a `time`-based cache wrapper around `fetch_odds`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Keep SQLite -- no migration to PostgreSQL
- Mount a Railway volume at `/data`
- Point `DB_PATH` to `/data/tracker.db` when running on Railway
- Use `RAILWAY_VOLUME_MOUNT_PATH` or `MONEYPUCK_DB_PATH` env var to configure
- If `RAILWAY_VOLUME_MOUNT_PATH` is set, use that path for DB
- If `MONEYPUCK_DB_PATH` is set, use that (existing behavior)
- Fallback to `~/.moneypuck/tracker.db` for local dev
- Update Dockerfile to create `/data` directory
- Ensure `appuser` has write permissions to the volume mount
- Add server-side response caching to reduce API credit burn from 60s auto-refresh
- Cache odds responses for 60-120 seconds (in-memory dict with TTL)

### Claude's Discretion
- Exact cache implementation (dict with timestamp vs lru_cache)
- Whether to add a /health endpoint checking DB connectivity
- Test approach for volume persistence (can't test Railway deploys locally)

### Deferred Ideas (OUT OF SCOPE)
- PostgreSQL migration -- revisit if multi-server scaling needed
- Automated DB backups -- Phase 8 (Automated Operations)
- Redis caching -- overkill for now, in-memory dict is fine
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| R1.1 | Mount a Railway volume or migrate to Railway-managed PostgreSQL | Railway volume at `/data` with `RAILWAY_RUN_UID=0`; volume auto-provides `RAILWAY_VOLUME_MOUNT_PATH` env var |
| R1.2 | Existing SQLite schema migrates cleanly to new storage | No schema changes needed -- same SQLite file, just different path. `TrackerDatabase.__init__` auto-creates schema on first connect |
| R1.3 | Bet history, predictions, and settlement data survive deploys | Volume persists across deploys; verified by Railway docs. Brief downtime during redeploy (old instance stops, new mounts volume) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Database | Already in use, no changes needed |
| pathlib | stdlib | Path resolution | Already in use for DB_PATH |
| os | stdlib | Env var reading | Already in use for MONEYPUCK_DB_PATH |
| time | stdlib | Cache TTL tracking | Simple monotonic timestamps |

### Supporting
No new dependencies required. This phase uses only stdlib.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dict+TTL cache | `functools.lru_cache` | `lru_cache` doesn't support TTL expiry; dict+timestamp is simpler for time-based invalidation |
| Dict+TTL cache | `cachetools.TTLCache` | Adds dependency for something achievable in ~15 lines of stdlib |

## Architecture Patterns

### DB Path Resolution (priority order)
```python
# Source: CONTEXT.md decisions + Railway docs
import os
from pathlib import Path

def resolve_db_path() -> Path:
    """Resolve database path with Railway volume > explicit env > default fallback."""
    # 1. Railway volume mount (auto-set by Railway when volume attached)
    railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_mount:
        return Path(railway_mount) / "tracker.db"

    # 2. Explicit override (existing behavior)
    explicit = os.getenv("MONEYPUCK_DB_PATH")
    if explicit:
        return Path(explicit)

    # 3. Local dev fallback
    return Path.home() / ".moneypuck" / "tracker.db"
```

### In-Memory TTL Cache Pattern
```python
import time
from typing import Any

class TTLCache:
    """Simple in-memory cache with per-key TTL."""

    def __init__(self, ttl_seconds: float = 90.0):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)
```

### Cache Integration Point
The cache wraps `fetch_odds()` calls in `web_preview.py`. The cache key should include `region` and `bookmakers` params since those vary per request. The `build_market_snapshot` call in the request handler fetches odds internally via `data_sources.fetch_odds`, so the cache should be applied at the `fetch_odds` level or just above the `build_market_snapshot` call.

**Recommended approach:** Cache at the `web_preview.py` level, wrapping the snapshot-building call. This avoids modifying `data_sources.py` (which is also used by CLI and backtester where caching is undesirable).

### Anti-Patterns to Avoid
- **Writing to volume path at Docker build time:** Volumes are NOT mounted during build. Any files written to `/data` during `docker build` will be invisible at runtime.
- **Using `lru_cache` for time-based expiry:** `lru_cache` evicts by count, not time. Stale odds data would persist until cache fills up.
- **Hardcoding `/data` path:** Use the `RAILWAY_VOLUME_MOUNT_PATH` env var, not a hardcoded path. This keeps local dev working.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TTL cache | Full cache framework | Simple dict + `time.monotonic()` | Only need single-key TTL, ~15 lines of code |
| DB migrations | Migration framework | SQLite `CREATE TABLE IF NOT EXISTS` | Schema is already idempotent; no migration needed this phase |
| Health checks | Complex monitoring | Simple `/health` endpoint hitting DB | Just need "is DB writable?" check |

## Common Pitfalls

### Pitfall 1: Non-Root UID Permissions
**What goes wrong:** `SQLITE_READONLY: attempt to write a readonly database` on Railway.
**Why it happens:** Railway volumes are mounted as root. The Dockerfile creates `appuser` (non-root) which cannot write to the root-owned volume.
**How to avoid:** Set `RAILWAY_RUN_UID=0` as a Railway environment variable. This tells Railway to run the container as root, matching volume ownership. Alternatively, remove the `USER appuser` line from Dockerfile for Railway deploys.
**Warning signs:** App starts but crashes on first DB write. Works locally but fails on Railway.

### Pitfall 2: Build-Time vs Runtime Volume Availability
**What goes wrong:** Database created during `docker build` doesn't persist.
**Why it happens:** Volumes are only mounted at container START, not during build or pre-deploy.
**How to avoid:** The current code already handles this correctly -- `TrackerDatabase.__init__` creates the DB at runtime. Just ensure no Dockerfile `RUN` commands try to initialize the DB.
**Warning signs:** DB exists after build but is empty after deploy.

### Pitfall 3: Brief Downtime During Redeploy
**What goes wrong:** Users see errors during deploys.
**Why it happens:** Railway cannot mount the same volume to two instances simultaneously. Old instance must stop before new one starts.
**How to avoid:** This is expected behavior. No mitigation needed for a single-user/small-audience app. Document it.
**Warning signs:** 502 errors for ~10-30 seconds during deploys.

### Pitfall 4: WAL Mode with Volume Mounts
**What goes wrong:** SQLite WAL files (`-wal`, `-shm`) left on volume could cause issues.
**Why it happens:** SQLite WAL mode creates auxiliary files alongside the main DB. If process crashes, these files persist.
**How to avoid:** The current schema already sets `PRAGMA journal_mode=WAL;` which is fine. SQLite handles WAL recovery automatically on next connection. No action needed.
**Warning signs:** None expected -- SQLite WAL recovery is robust.

### Pitfall 5: Cache Serving Stale Odds During Market Moves
**What goes wrong:** User sees 90-second-old odds during fast line movement.
**Why it happens:** Cache TTL prevents fresh fetch.
**How to avoid:** Keep TTL at 60-90 seconds (matches the existing 60s auto-refresh). Add a manual refresh button or force-refresh query param.
**Warning signs:** User complains odds are stale, but this is acceptable given API cost savings.

## Code Examples

### Current DB_PATH (line 13 of database.py)
```python
# CURRENT - only checks MONEYPUCK_DB_PATH
DB_PATH = Path(os.getenv("MONEYPUCK_DB_PATH", str(Path.home() / ".moneypuck" / "tracker.db")))
```

### Updated DB_PATH Resolution
```python
# NEW - checks Railway volume first, then explicit override, then default
def _resolve_db_path() -> Path:
    railway_mount = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_mount:
        return Path(railway_mount) / "tracker.db"
    return Path(os.getenv("MONEYPUCK_DB_PATH", str(Path.home() / ".moneypuck" / "tracker.db")))

DB_PATH = _resolve_db_path()
```

### Current Dockerfile (relevant lines)
```dockerfile
RUN adduser --disabled-password --gecos '' appuser
RUN mkdir -p /home/appuser/.moneypuck && chown -R appuser:appuser /home/appuser/.moneypuck
USER appuser
```

### Updated Dockerfile
```dockerfile
RUN adduser --disabled-password --gecos '' appuser
RUN mkdir -p /home/appuser/.moneypuck && chown -R appuser:appuser /home/appuser/.moneypuck
RUN mkdir -p /data && chown -R appuser:appuser /data
USER appuser
```
Note: The `/data` mkdir in the Dockerfile is for local Docker testing. On Railway, the volume mount supersedes this directory. The `RAILWAY_RUN_UID=0` env var is still needed on Railway to avoid permission issues.

### Health Endpoint (optional, Claude's discretion)
```python
# Simple health check verifying DB is writable
def _handle_health(self):
    try:
        db = TrackerDatabase()
        db.close()
        self._respond(200, "application/json", json.dumps({"status": "ok"}).encode())
    except Exception as e:
        self._respond(503, "application/json", json.dumps({"status": "error", "detail": str(e)}).encode())
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Railway ephemeral FS | Railway Volumes (GA) | 2023 | Persistent storage without managed DB |
| PostgreSQL for persistence | SQLite + Volume | Current best practice for small apps | Simpler, no DB service cost |

**No deprecated features apply.** Railway Volumes are stable and actively maintained.

## Open Questions

1. **RAILWAY_RUN_UID=0 security implications**
   - What we know: Running as root in container solves permission issues
   - What's unclear: Whether this has security implications for Railway's isolation model
   - Recommendation: Acceptable for this use case. Railway containers are already isolated. The `appuser` was a defense-in-depth measure, not a hard requirement.

2. **Volume size for SQLite**
   - What we know: Hobby plan gets 5GB default, Pro gets 50GB
   - What's unclear: How fast the DB will grow
   - Recommendation: Default volume size is more than adequate. SQLite DB with thousands of predictions will be < 10MB.

3. **Cache invalidation on manual refresh**
   - What we know: 60-90s TTL is the plan
   - What's unclear: Whether users need a force-refresh option
   - Recommendation: Add a `?refresh=1` query param that bypasses cache. Low effort, high value.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | Standard pytest discovery |
| Quick run command | `pytest tests/data/test_database.py -x` |
| Full suite command | `pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R1.1 | DB path resolves to volume when RAILWAY_VOLUME_MOUNT_PATH set | unit | `pytest tests/data/test_database.py::test_railway_volume_path -x` | Wave 0 |
| R1.1 | DB path falls back to default when no env var | unit | `pytest tests/data/test_database.py::test_default_db_path -x` | Wave 0 |
| R1.2 | Schema applies cleanly on new DB file | unit | `pytest tests/data/test_database.py::test_database_round_trip -x` | Exists |
| R1.3 | Predictions survive DB reopen (simulates redeploy) | unit | `pytest tests/data/test_database.py::test_data_survives_reopen -x` | Wave 0 |
| N/A | Odds cache returns cached data within TTL | unit | `pytest tests/data/test_odds_cache.py::test_cache_hit -x` | Wave 0 |
| N/A | Odds cache expires after TTL | unit | `pytest tests/data/test_odds_cache.py::test_cache_expiry -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/data/test_database.py tests/data/test_odds_cache.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/data/test_database.py` -- add tests for Railway path resolution and data-survives-reopen
- [ ] `tests/data/test_odds_cache.py` -- new file for cache TTL behavior
- [ ] No new framework install needed -- pytest already configured

## Sources

### Primary (HIGH confidence)
- [Railway Volumes Reference](https://docs.railway.com/reference/volumes) - Volume size limits, permissions (RAILWAY_RUN_UID=0), single-volume-per-service limit
- [Using Volumes Guide](https://docs.railway.com/volumes) - Build-time vs runtime mount timing, RAILWAY_VOLUME_MOUNT_PATH auto-env var, Nixpacks /app path consideration
- [Railway SQLite Help](https://station.railway.com/questions/how-do-i-use-volumes-to-make-a-sqlite-da-34ea0372) - Community-verified SQLite + volume pattern
- Existing codebase: `app/data/database.py` (line 13 DB_PATH, line 16 WAL pragma), `Dockerfile` (appuser setup)

### Secondary (MEDIUM confidence)
- [Railway SQLITE_READONLY issue](https://station.railway.com/questions/sqlite-readonly-attempt-to-write-a-read-2e6e370a) - Permission fix via RAILWAY_RUN_UID=0

### Tertiary (LOW confidence)
- None -- all findings verified against official Railway docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies, stdlib only
- Architecture: HIGH - Railway volumes well-documented, pattern is straightforward
- Pitfalls: HIGH - Permission issue is well-documented across Railway community, WAL behavior verified from SQLite docs
- Caching: HIGH - Simple dict+TTL pattern, no edge cases beyond staleness (which is acceptable)

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (Railway volumes are stable GA feature)
