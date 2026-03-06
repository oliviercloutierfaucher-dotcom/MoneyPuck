# Reliability, Automation & Operations Research

**Project:** MoneyPuck NHL Betting Edge Platform
**Researched:** 2026-03-06
**Overall Confidence:** HIGH (verified against official docs)

---

## 1. Automated Scheduling on Railway

### Railway Cron Jobs (Recommended)

Railway has native cron job support. A cron service runs its start command on schedule, then must exit cleanly. This is the right fit for MoneyPuck's batch tasks.

**How it works:**
- Define a cron schedule in the Railway service settings (standard crontab syntax, UTC timezone)
- The service container starts, runs the task, and must exit
- If a previous run is still active when the next fires, the new run is skipped
- Minimum interval: 5 minutes
- Timing precision: not guaranteed to the minute (can vary by a few minutes)

**Architecture: Two Railway services from the same repo.**

| Service | Type | Schedule | Command |
|---------|------|----------|---------|
| `web` | Always-on | N/A | `python -m app.web.web_preview` |
| `cron` | Cron | See below | `python -m app.cron.runner` |

**Recommended cron schedules (all UTC):**

| Task | Schedule | Rationale |
|------|----------|-----------|
| Settlement | `30 10 * * *` (10:30 UTC / 5:30 AM ET) | After all west coast games finish |
| Model update (Elo + team strength cache) | `0 16 * * *` (16:00 UTC / 11 AM ET) | Before afternoon odds are posted |
| Stale data check | `*/30 * * * *` | Every 30 min, lightweight health ping |

**Implementation:** Create `app/cron/runner.py` that accepts a `--task` argument:
```python
# python -m app.cron.runner --task settle
# python -m app.cron.runner --task refresh
# python -m app.cron.runner --task healthcheck
```

Railway cron services share the same Docker image but use a different start command. Set the cron service's start command to the specific task.

**Confidence:** HIGH -- verified against Railway docs (https://docs.railway.com/reference/cron-jobs)

### Railway Cron vs Alternatives

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Railway cron** | Same infra, same env vars, same volume access, zero config | 5-min minimum, UTC only, imprecise timing | **Use this** |
| GitHub Actions cron | Free for public repos, precise timing | No access to Railway volume/DB, needs Railway CLI or API to trigger | Only for CI/CD, not runtime tasks |
| cron-job.org | Free, reliable | External dependency, needs webhook endpoint, security surface | Unnecessary complexity |

**Recommendation:** Use Railway cron for all operational tasks. Use GitHub Actions only for CI/CD (tests on push, deploy gate).

---

## 2. Data Source Reliability

### MoneyPuck CSV Stability

**Current status:** MoneyPuck is active for 2025-2026 season. Per-team game-by-game CSVs work. The bulk `games.csv` endpoint has returned 403 errors historically (already noted in codebase -- fallback exists in `fetch_team_game_by_game`).

**Risk assessment: MEDIUM.** MoneyPuck is a one-person project (Peter Tanner). No SLA, no status page, no API versioning. Schema changes happen without notice. The bulk CSV endpoint already broke once.

**Existing mitigations in codebase (good):**
- Retry logic with exponential backoff (`_fetch_with_retry`)
- Per-team CSV fetching with fallback to bulk CSV
- User-Agent header set

**Missing mitigations (need to add):**
- No caching of successfully fetched data
- No alerting when fetches fail
- No fallback to alternative data sources

### Fallback Data Sources

| Source | Data Available | Access Method | Reliability | Recommendation |
|--------|---------------|---------------|-------------|----------------|
| **NHL API** (api-web.nhle.com) | Schedule, scores, basic stats, EDGE tracking | Free REST API, undocumented | HIGH (official NHL) | **Primary fallback.** Already used for schedule/scores. Expand to team stats. |
| **Natural Stat Trick** | xG, Corsi, Fenwick, all advanced stats | HTML scraping (BeautifulSoup) | MEDIUM (one-person site, but long-running) | **Secondary fallback.** Same underlying data as MoneyPuck, different aggregation. |
| **Hockey Reference** | Historical stats, game logs | HTML scraping | HIGH (Sports Reference is established) | Good for historical validation, not real-time |
| **nhl-api-py** (PyPI) | Python wrapper for NHL API | `pip install nhl-api-py` | MEDIUM (community maintained) | Consider for cleaner NHL API access |

**Key insight:** Both MoneyPuck and Natural Stat Trick derive their data from the NHL's play-by-play feed. If MoneyPuck goes down, the underlying data is still accessible -- you just need to compute xG yourself or scrape Natural Stat Trick.

**Recommended strategy:**
1. Primary: MoneyPuck per-team CSVs (current)
2. Cache successful fetches to SQLite/Postgres (new)
3. If MoneyPuck fails: Fall back to cached data (up to 24h old is fine for team strength)
4. If cache is stale: Alert, and optionally scrape Natural Stat Trick
5. NHL API for scores/schedule (already implemented)

**Confidence:** MEDIUM -- MoneyPuck reliability assessment based on project memory notes and general one-person-project risk patterns.

---

## 3. Monitoring and Alerting

### Health Checks

**Already implemented:** Dockerfile has a `HEALTHCHECK` that pings `http://127.0.0.1:8080/`. Railway uses this automatically.

**Missing:** No `/health` endpoint that checks downstream dependencies. The current healthcheck only confirms the HTTP server is responding, not that data is fresh or APIs are reachable.

**Recommended `/health` endpoint response:**
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "last_odds_fetch": "2026-03-06T14:00:00Z",
    "odds_age_minutes": 45,
    "last_moneypuck_fetch": "2026-03-06T12:00:00Z",
    "moneypuck_age_minutes": 165,
    "circuit_breaker": "closed",
    "brier_score": 0.2430
  }
}
```

### Alerting Strategy

For a solo/small-team project, avoid heavyweight solutions (PagerDuty, Datadog). Use what Railway and free tiers provide.

| Alert Condition | Detection | Notification Method |
|----------------|-----------|---------------------|
| Web server down | Railway health check failure | Railway notifications (email) |
| Data source failure | Cron job logs error on fetch | Discord/Slack webhook from cron runner |
| Odds stale (>2 hours) | `/health` endpoint check | Cron healthcheck task + webhook |
| Model drift (Brier > 0.26) | Circuit breaker (already implemented) | Log + webhook notification |
| Settlement failure | Cron settle task error | Webhook notification |

**Implementation: Discord webhook** (simplest, free, no account needed beyond a Discord server).

```python
import urllib.request, json

def send_alert(message: str, webhook_url: str):
    data = json.dumps({"content": message}).encode()
    req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)
```

Set `ALERT_WEBHOOK_URL` as a Railway environment variable. Call from the cron runner on failures.

### Model Drift Detection

The circuit breaker in `service.py` already tracks Brier score degradation (threshold: 0.26 over last 50 predictions). This is solid.

**Enhancement:** Log Brier score to a `model_health` table on every cron run so you can track trends, not just trip/no-trip.

**Confidence:** HIGH -- patterns are standard and well-understood.

---

## 4. SQLite Limitations on Railway

### The Problem

**Railway's filesystem is ephemeral by default.** Every deploy wipes the filesystem. The current SQLite database at `~/.moneypuck/tracker.db` is destroyed on every deploy. This means all prediction history, bet tracking, and CLV data is lost.

This is a critical issue that is likely already causing data loss if deploys have happened since persistence was added.

### Solution Options

| Option | Effort | Reliability | Cost | Recommendation |
|--------|--------|-------------|------|----------------|
| **Railway Volume + SQLite** | Low | Good for single-instance | ~$0.25/GB/month | **Good for now** |
| **Railway Managed Postgres** | Medium | Excellent | ~$5/month minimum | **Migrate when charging users** |
| **Neon/Supabase free Postgres** | Medium | Good | Free tier available | Alternative if Railway Postgres is too expensive |

### Option A: Railway Volume + SQLite (Recommended Now)

**How:** Mount a Railway volume at `/data`, set `MONEYPUCK_DB_PATH=/data/tracker.db`.

**Volume specs (Hobby plan):** 5GB max, 3000 read/write IOPS, live-resizable. Billed per GB/minute of actual usage.

**Gotcha:** Railway prevents multiple deployments from mounting the same volume simultaneously, causing brief downtime during deploys. This is acceptable for MoneyPuck (not a high-availability service).

**Gotcha:** Non-root Docker images need `RAILWAY_RUN_UID=0` env var or explicit permissions. The current Dockerfile runs as `appuser`, so permissions on the volume mount need to be handled.

**Implementation changes needed:**
1. Create a volume in Railway, mount at `/data`
2. Set env var: `MONEYPUCK_DB_PATH=/data/tracker.db`
3. Update Dockerfile: ensure `appuser` can write to `/data` or use `RAILWAY_RUN_UID=0`
4. The cron service needs to mount the SAME volume (both services access same DB)

**Important caveat:** A Railway volume can only be mounted to one service. If you have separate `web` and `cron` services, they cannot share a volume. This is a strong argument for either:
- Using an in-process scheduler (APScheduler) instead of a separate cron service, OR
- Migrating to PostgreSQL (network-accessible, shared by all services)

### Option B: Railway Managed PostgreSQL (Recommended When Charging)

**Why migrate:**
- Multiple services can connect (web + cron)
- Automatic backups
- No filesystem permission headaches
- Better concurrent access (SQLite + WAL mode handles this okay for low traffic, but Postgres is cleaner)
- Railway provides managed Postgres with one click

**Migration effort:** MEDIUM. The database layer (`database.py`) uses raw SQL, not an ORM. Changing from SQLite to Postgres requires:
- Replacing `sqlite3` with `psycopg2` or `asyncpg`
- Adjusting SQL syntax (minimal -- schema is simple)
- Changing `PRAGMA journal_mode=WAL` to nothing (Postgres handles this)
- Changing `datetime('now')` to `NOW()`
- Connection string from env var instead of file path

**Alternative approach:** Use `sqlalchemy` or keep raw SQL but abstract the connection. Given the schema is 3 tables, raw `psycopg2` is fine.

### Backup Strategy

**With SQLite + Volume:**
- Cron job: copy `tracker.db` to a timestamped backup file daily
- Optional: upload to S3/R2 (add `boto3` dependency)
- Volume snapshots are not a Railway feature -- you must handle backups yourself

**With PostgreSQL:**
- Railway managed Postgres includes automatic backups
- `pg_dump` via cron for extra safety

**Confidence:** HIGH -- verified against Railway volume docs.

---

## 5. API Cost Optimization

### The Odds API Pricing

| Plan | Credits/Month | Cost | Credits/Day |
|------|--------------|------|-------------|
| Starter | 500 | Free | ~16 |
| 20K | 20,000 | $30/mo | ~667 |
| 100K | 100,000 | $59/mo | ~3,333 |
| 5M | 5,000,000 | $119/mo | ~167,000 |
| 15M | 15,000,000 | $249/mo | ~500,000 |

**What counts as 1 credit:** One API call, regardless of how many games/events are returned. Requesting NHL moneyline odds for all games tonight = 1 credit.

**Current usage pattern:** Each `fetch_odds` call = 1 credit. The call fetches `h2h,spreads,totals` markets in a single request. This is already efficient -- 3 markets in one call.

### Cost Analysis for MoneyPuck

| Scenario | Calls/Day | Credits/Month | Plan Needed |
|----------|-----------|---------------|-------------|
| Dashboard refresh on page load only | 5-10 | 150-300 | Free (500) |
| Auto-refresh every 60s for 8 hours | 480 | 14,400 | 20K ($30) |
| Cron: 4x daily + dashboard | 4 + 10 | 420 | Free (500) |
| Cron: 4x daily + moderate dashboard | 4 + 50 | 1,620 | 20K ($30) |

### Caching Strategy (Critical for Free/Cheap Plans)

**Problem:** The web dashboard currently fetches fresh odds on every page load. With 60-second auto-refresh, this burns credits fast.

**Solution: Server-side cache with TTL.**

```python
import time

_odds_cache = {"data": None, "fetched_at": 0}
CACHE_TTL = 300  # 5 minutes

def get_odds_cached(api_key, region, bookmakers):
    if time.time() - _odds_cache["fetched_at"] < CACHE_TTL:
        return _odds_cache["data"]
    data = fetch_odds(api_key, region, bookmakers)
    _odds_cache["data"] = data
    _odds_cache["fetched_at"] = time.time()
    return data
```

**Recommended TTL:** 5 minutes for live odds (odds don't change that fast for NHL moneylines). This reduces 480 calls/day to 96 calls/day.

**Additional optimizations:**
1. **Separate markets into separate calls only when needed.** Currently fetching h2h, spreads, and totals together -- this is already optimal (1 credit for all 3).
2. **Cache MoneyPuck data aggressively.** Team stats don't change until games are played. Cache for 6-12 hours.
3. **Use the `x-requests-remaining` response header** to track budget in real-time and throttle when running low.

### Cheapest Endpoints

All Odds API endpoints cost 1 credit per call. There's no difference between endpoints. The optimization is about reducing call frequency, not choosing different endpoints.

**Confidence:** HIGH -- verified against the-odds-api.com pricing page.

---

## 6. CI/CD Pipeline

### Recommended Setup

**GitHub Actions for CI (tests), Railway for CD (deploy).**

Railway already auto-deploys on push to the connected branch. The missing piece is running tests before deploy.

### GitHub Actions Workflow

Railway supports a "wait for GitHub Actions" toggle: if enabled, Railway waits for all GitHub Actions workflows to pass before deploying. If any workflow fails, the deploy is skipped.

**Create `.github/workflows/ci.yml`:**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest

      - name: Run tests
        run: pytest tests/ -v --tb=short

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install ruff
        run: pip install ruff

      - name: Lint
        run: ruff check app/ tests/
```

### Railway Configuration

1. Connect GitHub repo to Railway (likely already done)
2. In Railway service settings, enable "Check Suites" -- this makes Railway wait for GitHub Actions to pass
3. Set trigger branch to `main`
4. Deploy happens automatically after CI passes

### Deployment Flow

```
Push to main
  -> GitHub Actions runs tests + lint
  -> Railway waits for CI to pass
  -> Railway builds Docker image
  -> Railway deploys new container
  -> Health check passes
  -> Old container terminated
```

For PRs:
```
Open PR
  -> GitHub Actions runs tests + lint
  -> PR shows check status
  -> Merge to main triggers deploy
```

**Confidence:** HIGH -- Railway auto-deploy + GitHub Actions integration is well-documented.

---

## Summary of Priorities

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| **P0** | Add Railway volume for SQLite persistence | 1 hour | Prevents data loss on every deploy |
| **P0** | Add server-side odds caching (5-min TTL) | 2 hours | Prevents blowing API budget |
| **P1** | Set up GitHub Actions CI | 1 hour | Prevents deploying broken code |
| **P1** | Enable Railway "wait for CI" | 5 minutes | Gates deploys on test passage |
| **P1** | Add cron service for settlement | 4 hours | Automates daily settlement |
| **P2** | Add Discord webhook alerting | 2 hours | Know when things break |
| **P2** | Add `/health` endpoint with dependency checks | 2 hours | Better monitoring |
| **P2** | Cache MoneyPuck data to DB | 3 hours | Resilience against MoneyPuck outages |
| **P3** | Migrate to PostgreSQL | 6 hours | Multi-service DB access, backups |
| **P3** | Add Natural Stat Trick fallback | 8 hours | Redundant data sourcing |

## Architecture Decision: Volume Sharing Problem

The biggest architectural tension is that Railway cron services and the web service cannot share a volume. Three paths forward:

1. **In-process scheduler (APScheduler)** -- Run cron tasks inside the web server process. Simple, shares filesystem. Downside: if the web server crashes, cron stops too.

2. **PostgreSQL** -- Both services connect over the network. Clean separation. Costs $5+/month.

3. **HTTP trigger** -- Cron service calls an HTTP endpoint on the web service to trigger settlement. Web service does the DB work. Cron service is stateless.

**Recommendation:** Start with option 1 (APScheduler in the web process) for simplicity. Migrate to option 2 (PostgreSQL) when you start charging users. Option 3 is a reasonable middle ground if you want service separation without Postgres.

## Sources

- [Railway Cron Jobs Docs](https://docs.railway.com/reference/cron-jobs)
- [Railway Volumes Docs](https://docs.railway.com/reference/volumes)
- [Railway GitHub Auto-deploys](https://docs.railway.com/deployments/github-autodeploys)
- [The Odds API Pricing](https://the-odds-api.com/)
- [The Odds API Rate Limits](https://the-odds-api.com/guide/rate-limit.html)
- [GitHub Actions Python CI](https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python)
- [NHL API Reference (Unofficial)](https://github.com/Zmalski/NHL-API-Reference)
- [nhl-api-py on PyPI](https://pypi.org/project/nhl-api-py/)
- [Natural Stat Trick](https://www.naturalstattrick.com/)
- [MoneyPuck Data Downloads](https://moneypuck.com/data.htm)
