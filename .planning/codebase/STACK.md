# Technology Stack

**Analysis Date:** 2026-03-06

## Languages

**Primary:**
- Python 3.11+ (runtime target in `Dockerfile`; `.pyc` files indicate 3.13 used locally)

**Secondary:**
- HTML/CSS/JavaScript - Inline in `app/web/presentation.py` (dashboard templates rendered as string)
- Bash - `deploy.sh` deployment script

## Runtime

**Environment:**
- CPython 3.11 (Docker production) / 3.13 (local development, per `__pycache__` bytecode)
- No virtual environment tooling checked in (no `venv`, `poetry`, `pipenv` configs)

**Package Manager:**
- pip (standard)
- Lockfile: **missing** (no `requirements.lock`, `pip.lock`, or `poetry.lock`)

## Frameworks

**Core:**
- **No web framework** - Uses Python stdlib `http.server.ThreadingHTTPServer` for the web dashboard (`app/web/web_preview.py`)
- **No CLI framework** - Uses stdlib `argparse` (`tracker.py`)

**Testing:**
- pytest (inferred from test directory structure `tests/`)
- No test config file detected (no `pytest.ini`, `pyproject.toml`, `setup.cfg` with pytest section)

**Build/Dev:**
- Docker (`Dockerfile`) - Production container build
- `deploy.sh` - One-command local setup and launch script

## Key Dependencies

**Critical:**
- `numpy>=1.24` - Only declared dependency in `requirements.txt`. Used for numerical computations in math utilities.

**Stdlib-heavy architecture:**
- `urllib.request` - All HTTP calls (Odds API, MoneyPuck, NHL API, Polymarket). No `requests` or `httpx`.
- `csv` / `io` - CSV parsing for MoneyPuck data
- `json` - All JSON parsing/serialization
- `sqlite3` - Local database persistence
- `http.server` - Web dashboard server
- `dataclasses` - All data models (`TrackerConfig`, `TeamMetrics`, `ValueCandidate`, `MarketSnapshot`)
- `logging` - Structured logging via `app/logging_config.py`
- `argparse` - CLI argument parsing
- `math` - Mathematical computations (logistic functions, Kelly criterion)
- `collections.defaultdict` - In-memory data stores

**Notable absences (all handled by stdlib):**
- No `requests`, `httpx`, or `aiohttp` for HTTP
- No `pandas` for data processing
- No `Flask`, `FastAPI`, or `Django` for web
- No `click` or `typer` for CLI
- No `SQLAlchemy` or other ORM
- No `pydantic` for validation (uses `dataclasses`)

## Configuration

**Environment:**
- `.env` file present - loaded manually via `tracker.py::_load_dotenv()` (custom parser, no `python-dotenv`)
- `ODDS_API_KEY` - Required for live odds fetching (The Odds API)
- `MONEYPUCK_DB_PATH` - Optional, defaults to `~/.moneypuck/tracker.db`
- `LOG_LEVEL` - Optional, defaults to `INFO`
- `PREVIEW_HOST` - Web server bind address (default `0.0.0.0`)
- `PREVIEW_PORT` / `PORT` - Web server port (default `8080`, Railway sets `PORT`)

**Build:**
- `Dockerfile` - Python 3.11-slim base, pip install, non-root user, healthcheck
- `requirements.txt` - Single dependency (`numpy>=1.24`)

## Platform Requirements

**Development:**
- Python 3.11+ (3.13 used locally)
- `numpy` package
- `ODDS_API_KEY` from https://the-odds-api.com (free tier available)
- No OS-specific dependencies (pure Python + numpy)

**Production:**
- Docker (Python 3.11-slim image)
- Railway hosting platform
- Port 8080 exposed
- `ODDS_API_KEY` env var set in Railway settings
- Healthcheck: HTTP GET to `http://127.0.0.1:8080/`

**Data Storage:**
- SQLite database at `~/.moneypuck/tracker.db` (auto-created)
- In Docker: `/home/appuser/.moneypuck/tracker.db`
- In-memory odds history store (module-level singleton in `app/data/odds_history.py`)

---

*Stack analysis: 2026-03-06*
