# External Integrations

**Analysis Date:** 2026-03-06

## APIs & External Services

**The Odds API (primary odds source):**
- Purpose: Live NHL moneyline, spreads, and totals odds from 15+ sportsbooks
- SDK/Client: stdlib `urllib.request` with custom retry logic in `app/data/data_sources.py::_fetch_with_retry()`
- Auth: API key via `ODDS_API_KEY` env var, passed as `apiKey` query parameter
- Base URL: `https://api.the-odds-api.com/v4/sports/icehockey_nhl/odds`
- Markets fetched: `h2h,spreads,totals` (moneyline, point spreads, over/under)
- Odds format: American
- Player props endpoint: `https://api.the-odds-api.com/v4/sports/icehockey_nhl/events/{event_id}/odds` (`app/data/player_props.py`)
- Rate limiting: Handled with exponential backoff on HTTP 429
- Retry logic: 3 attempts with exponential backoff on 429/5xx/network errors (`app/data/data_sources.py::_fetch_with_retry()`)
- Region support: `ca` (Quebec books default), `us`, `qc`, `on`
- Bookmaker mappings: `app/data/data_sources.py` - `QUEBEC_BOOKS`, `ONTARIO_BOOKS`, `US_BOOKS` dicts

**MoneyPuck (team analytics source):**
- Purpose: NHL advanced stats (xG, Corsi, Fenwick, shooting%, save%, etc.)
- SDK/Client: stdlib `urllib.request` + `csv.DictReader`
- Auth: None (public data), but requires `User-Agent: MoneyPuck/1.0` header
- Endpoints:
  - Per-team game-by-game: `https://moneypuck.com/moneypuck/playerData/teamGameByGame/{year}/regular/{TEAM}.csv` (`app/data/data_sources.py::fetch_team_game_by_game()`)
  - Bulk games CSV (legacy fallback): `https://moneypuck.com/moneypuck/playerData/games.csv` (`app/data/data_sources.py::fetch_moneypuck_games()`)
- Data: 100+ advanced metrics per team per game (score-adjusted xG, flurry-adjusted xG, danger zones, rebounds, faceoffs, giveaways/takeaways)
- Season mapping: `mp_year = season` (e.g., 2025 = 2025-26 season starting Oct 2025)
- Fetches all 32 NHL teams individually with fallback to bulk CSV on failure

**NHL Public API (enrichment layer):**
- Purpose: Schedule, goalie stats, standings, game scores for settlement
- SDK/Client: stdlib `urllib.request` in `app/data/nhl_api.py`
- Auth: None (fully public)
- Base URL: `https://api-web.nhle.com/v1`
- Endpoints used:
  - Schedule: `/schedule/{date}` (`fetch_schedule()`)
  - Team schedule: `/club-schedule-season/{team_code}/{season}` (`fetch_team_schedule()`)
  - Goalie stats: `/goalie-stats-leaders/current?categories=savePctg&limit=200` (`fetch_goalie_stats()`)
  - Game score: `/gamecenter/{game_id}/landing` (`fetch_game_score()`)
  - Standings: `/standings/now` (`fetch_standings()`)
- Error handling: Best-effort only, returns empty collections on failure, never propagates exceptions
- Retry: 2 retries with 3-second backoff

**Polymarket (prediction market odds):**
- Purpose: Crowd-sourced NHL win probabilities from prediction markets
- SDK/Client: stdlib `urllib.request` in two modules:
  - `app/data/data_sources.py::fetch_polymarket_odds()` - Original integration, converts to Odds API format
  - `app/data/polymarket.py` - Newer module with series discovery, event matching
- Auth: None (fully public read API)
- Base URL: `https://gamma-api.polymarket.com`
- Endpoints:
  - Events: `/events?series_id=10346&active=true&closed=false&limit=50`
  - Sports discovery: `/sports` (for dynamic series_id lookup)
- NHL series_id: `10346`
- Team name mapping: Short names (e.g., "Bruins") to 3-letter codes in `_POLYMARKET_NAME_TO_CODE` dict
- Timeout: 12-15 seconds

## Data Storage

**Databases:**
- SQLite 3 (stdlib `sqlite3`)
  - Connection: `MONEYPUCK_DB_PATH` env var, defaults to `~/.moneypuck/tracker.db`
  - Client: Direct `sqlite3` module, no ORM (`app/data/database.py::TrackerDatabase`)
  - Tables:
    - `predictions` - Bet predictions with outcomes and P&L tracking
    - `model_runs` - Model execution summaries
    - `closing_odds` - Captured closing line odds for CLV analysis
    - `odds_history` - Line movement snapshots (optional, schema in `app/data/odds_history.py`)
  - WAL mode enabled for concurrent reads
  - Schema auto-applied on connection

**In-Memory Storage:**
- Odds history snapshots: Module-level singleton `dict[str, list[OddsSnapshot]]` in `app/data/odds_history.py::_store`
- Used for sparkline charts and line movement tracking in the dashboard

**File Storage:**
- Local filesystem only (SQLite DB file)
- No cloud storage integration

**Caching:**
- None (all API data fetched fresh on each run)

## Authentication & Identity

**Auth Provider:**
- None - No user authentication system
- API key (`ODDS_API_KEY`) is the only credential, used for The Odds API calls
- All other APIs (MoneyPuck, NHL, Polymarket) are unauthenticated

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, etc.)

**Logs:**
- Python `logging` module via `app/logging_config.py`
- Namespace: `moneypuck.*` (child loggers for each module)
- Output: stderr via `StreamHandler`
- Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- Level: Configurable via `LOG_LEVEL` env var or `--log-level` CLI flag (default `INFO`)

## CI/CD & Deployment

**Hosting:**
- Railway (PaaS)
- Docker container deployment
- Port binding: `0.0.0.0:8080` (respects Railway's `PORT` env var)

**CI Pipeline:**
- None detected (no `.github/workflows/`, no `Jenkinsfile`, no `.gitlab-ci.yml`)

**Deploy Script:**
- `deploy.sh` - Local setup helper (Python check, pip install, API key prompt, sanity test, first run)
- Not a CI/CD pipeline, meant for first-time local setup

## Environment Configuration

**Required env vars:**
- `ODDS_API_KEY` - The Odds API key (required for live mode; demo mode works without it)

**Optional env vars:**
- `MONEYPUCK_DB_PATH` - SQLite database location (default: `~/.moneypuck/tracker.db`)
- `LOG_LEVEL` - Logging verbosity (default: `INFO`)
- `PORT` - Web server port, set by Railway (default: `8080`)
- `PREVIEW_HOST` - Web server bind address (default: `0.0.0.0`)
- `PREVIEW_PORT` - Web server port override (default: `8080`)

**Secrets location:**
- `.env` file in project root (loaded by custom parser in `tracker.py::_load_dotenv()`)
- Railway environment settings for production

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## HTTP Client Configuration

**Shared patterns across all API integrations:**
- User-Agent header: `MoneyPuck/1.0` (set on all requests)
- Timeout: 15-30 seconds depending on endpoint
- Retry strategy in `app/data/data_sources.py::_fetch_with_retry()`:
  - Max 3 attempts
  - Exponential backoff: `2^attempt` seconds
  - Retries on: HTTP 429, HTTP 5xx, `URLError`, `TimeoutError`, `OSError`
  - No retry on: HTTP 4xx (except 429)
- NHL API has its own simpler retry in `app/data/nhl_api.py::_fetch_json()`: 2 retries, 3-second fixed backoff

## Sportsbook Deep Links

- `app/web/deep_links.py` - Maps bookmaker API keys to NHL section URLs for 15+ sportsbooks
- Used in CLI output and dashboard to link directly to sportsbook NHL pages
- Covers Canadian books (Bet365, Betway, Bet99, FanDuel, DraftKings, BetMGM, Pinnacle, etc.) and US books (Caesars, WynnBET, etc.)

---

*Integration audit: 2026-03-06*
