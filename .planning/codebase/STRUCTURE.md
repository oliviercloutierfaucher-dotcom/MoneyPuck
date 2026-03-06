# Codebase Structure

**Analysis Date:** 2026-03-06

## Directory Layout

```
MoneyPuck/
+-- app/                    # Application source code
|   +-- __init__.py
|   +-- logging_config.py   # Centralized logging setup
|   +-- core/               # Pipeline orchestration and domain models
|   |   +-- agents.py       # 6-agent pipeline (strength, scoring, risk)
|   |   +-- army.py         # Multi-profile parallel execution
|   |   +-- backtester.py   # Historical backtesting and grid search
|   |   +-- clv.py          # Closing Line Value calculations
|   |   +-- models.py       # Frozen dataclasses (TeamMetrics, ValueCandidate, etc.)
|   |   +-- service.py      # Pipeline orchestration, snapshot building, settlement
|   +-- data/               # External API clients and persistence
|   |   +-- data_sources.py # Odds API, MoneyPuck CSVs, Polymarket adapter
|   |   +-- database.py     # SQLite persistence (TrackerDatabase)
|   |   +-- nhl_api.py      # NHL public API client (schedule, goalies, scores)
|   |   +-- odds_history.py # Line movement tracking and sparkline data
|   |   +-- player_props.py # Player prop market fetching
|   |   +-- polymarket.py   # Dedicated Polymarket Gamma API client
|   +-- math/               # Pure mathematical functions
|   |   +-- arbitrage.py    # Cross-bookmaker arb detection
|   |   +-- elo.py          # FiveThirtyEight-style Elo rating system
|   |   +-- hedge.py        # Hedge calculator for open positions
|   |   +-- math_utils.py   # Odds conversion, Kelly, composite strength, win prob
|   |   +-- situational.py  # Rest/travel/B2B adjustments
|   |   +-- validation.py   # Brier score, model health metrics
|   +-- web/                # Web server and presentation
|       +-- deep_links.py   # Sportsbook URL generation
|       +-- presentation.py # HTML dashboard rendering, JSON serialization
|       +-- web_preview.py  # HTTP server (ThreadingHTTPServer, all routes)
+-- tests/                  # Test suite (mirrors app/ structure)
|   +-- core/               # Tests for app/core/
|   +-- data/               # Tests for app/data/
|   +-- math/               # Tests for app/math/
|   +-- web/                # Tests for app/web/
+-- tracker.py              # CLI entry point
+-- live_preview.py         # Development web preview
+-- deploy.sh               # Railway deployment script
+-- Dockerfile              # Production container (python:3.11-slim)
+-- requirements.txt        # Python dependencies
+-- ASSUMPTIONS.md          # Model assumptions documentation
+-- README.md               # Project documentation
```

## Directory Purposes

**`app/core/`:**
- Purpose: Pipeline orchestration, domain models, and core business logic
- Contains: Agent classes, service orchestration, backtester, CLV calculations, frozen dataclass models
- Key files: `agents.py` (783 lines, the 6-agent pipeline), `service.py` (686 lines, orchestration), `models.py` (103 lines, all domain types)

**`app/data/`:**
- Purpose: All external data fetching and local persistence
- Contains: API clients for Odds API, MoneyPuck, NHL, Polymarket; SQLite database; line movement tracking; player props
- Key files: `data_sources.py` (498 lines, primary data fetching + team name mappings), `database.py` (375 lines, SQLite CRUD), `nhl_api.py` (337 lines, NHL public API)

**`app/math/`:**
- Purpose: Pure mathematical functions with no external dependencies (no API calls, no database)
- Contains: Odds conversion, Kelly criterion, logistic win probability, Elo system, arbitrage detection, situational adjustments, model validation
- Key files: `math_utils.py` (406 lines, core math), `elo.py` (220 lines, Elo system), `arbitrage.py` (301 lines, arb scanner), `situational.py` (257 lines, rest/travel)

**`app/web/`:**
- Purpose: HTTP server, HTML rendering, sportsbook integration
- Contains: Web server with all API routes, dashboard HTML generation, deep link URLs
- Key files: `web_preview.py` (large, HTTP server + all route handlers), `presentation.py` (HTML template rendering), `deep_links.py` (sportsbook URL mappings)

**`tests/`:**
- Purpose: Unit and integration tests mirroring the app/ structure
- Contains: pytest test files, one per source module
- Key files: 306 tests across 20 test files

## Key File Locations

**Entry Points:**
- `tracker.py`: CLI entry point with argparse, mode routing, output formatting
- `app/web/web_preview.py`: HTTP server entry point (python -m app.web.web_preview), started by Docker CMD
- `live_preview.py`: Development preview server with demo data

**Configuration:**
- `.env`: Environment variables (ODDS_API_KEY) -- loaded by custom _load_dotenv() in tracker.py
- `Dockerfile`: Production container definition (python:3.11-slim, port 8080)
- `deploy.sh`: Railway deployment automation
- `requirements.txt`: Python package dependencies (numpy only external dep)
- `~/.moneypuck/overrides.json`: Runtime injury/roster overrides (user-managed, not in repo)

**Core Logic:**
- `app/core/agents.py`: The 6-agent pipeline -- TeamStrengthAgent (builds 16-metric team profiles), EdgeScoringAgent (logistic + Elo ensemble win probability), RiskAgent (Kelly sizing)
- `app/core/service.py`: build_market_snapshot() (parallel data fetch), score_snapshot() (run pipeline with safety checks), settle_outstanding() (match predictions to outcomes)
- `app/math/math_utils.py`: logistic_win_probability(), composite_strength(), kelly_fraction(), exponential_decay_weight(), DEFAULT_METRIC_WEIGHTS dict
- `app/math/elo.py`: EloTracker class, build_elo_ratings() from game history

**Data Layer:**
- `app/data/data_sources.py`: fetch_odds(), fetch_team_game_by_game(), fetch_polymarket_odds(), TEAM_NAME_TO_CODE mapping, NHL_TEAMS list
- `app/data/database.py`: TrackerDatabase class, SQLite schema with predictions, model_runs, closing_odds tables
- `app/data/nhl_api.py`: fetch_schedule(), fetch_goalie_stats(), fetch_scores_for_date(), infer_likely_starter()

**Testing:**
- `tests/core/test_pipeline.py`: End-to-end pipeline tests
- `tests/math/test_math_utils.py`: Core math function tests
- `tests/math/test_elo.py`: Elo system tests
- `tests/math/test_arbitrage.py`: Arbitrage detection tests

## Naming Conventions

**Files:**
- Snake_case for all Python files: `math_utils.py`, `data_sources.py`, `web_preview.py`
- Test files prefixed with test_: `test_math_utils.py`, `test_pipeline.py`
- No plural directory names: `app/core/`, `app/math/`, `app/web/`, `app/data/`

**Directories:**
- Flat package structure: app/{layer}/ -- no deeper nesting
- Test directories mirror source: tests/core/, tests/math/, tests/data/, tests/web/
- Every directory has __init__.py (empty)

**Classes:**
- PascalCase agent names with Agent suffix: TeamStrengthAgent, EdgeScoringAgent, RiskAgent
- PascalCase dataclasses: TeamMetrics, ValueCandidate, TrackerConfig, MarketSnapshot
- Each agent class has a name class attribute (kebab-case): "team-strength-agent", "edge-scoring-agent"

**Functions:**
- Snake_case for all functions: build_market_snapshot(), logistic_win_probability()
- Private functions prefixed with underscore: _fetch_with_retry(), _clamp_probability()
- Static methods on agents: TeamStrengthAgent._extract_team_gbg(), TeamStrengthAgent._z_score_all()

## Where to Add New Code

**New Mathematical Model / Adjustment:**
- Primary code: `app/math/new_module.py` -- pure functions, no API calls
- Import and use in: `app/core/agents.py` (integrate into pipeline) or `app/core/service.py` (if it is a safety check)
- Tests: `tests/math/test_new_module.py`
- Example: `app/math/situational.py` is a good template -- pure functions, clear docstrings, returns adjustment values

**New External Data Source:**
- Primary code: `app/data/new_source.py` -- fetch function with retry logic
- Use _fetch_with_retry() from `app/data/data_sources.py` for HTTP calls
- Integrate into parallel fetch in `app/core/service.py` build_market_snapshot()
- Tests: `tests/data/test_new_source.py`

**New Agent in the Pipeline:**
- Add class to `app/core/agents.py` following existing pattern: class with name attribute and run() method
- Wire into `app/core/service.py` score_snapshot() or build_market_snapshot()
- Tests: `tests/core/test_new_agent.py`

**New CLI Mode:**
- Add --new-mode argument in `tracker.py` parse_args()
- Add handler in main() (follow the if args.arbs: pattern)
- Delegate to service layer or new function

**New Web API Endpoint:**
- Add route handler in `app/web/web_preview.py` inside the RequestHandler class
- Add URL pattern matching in do_GET() or do_POST()
- Return JSON via _send_json() helper

**New Database Table:**
- Add CREATE TABLE to _SCHEMA_SQL in `app/data/database.py`
- Add CRUD methods to TrackerDatabase class
- Tests: `tests/data/test_database.py`

**Utilities / Shared Helpers:**
- Math utilities: `app/math/math_utils.py`
- Team name/code mappings: `app/data/data_sources.py` (contains TEAM_NAME_TO_CODE, NHL_TEAMS)
- Logging: Use from app.logging_config import get_logger and call get_logger("your_module")

## Special Directories

**~/.moneypuck/:**
- Purpose: User data directory (SQLite database, injury overrides)
- Generated: Automatically by TrackerDatabase on first use
- Committed: No (lives outside repo, in user home)
- Contains: tracker.db (SQLite), overrides.json (optional manual file)

**.planning/:**
- Purpose: GSD planning and analysis documents
- Generated: By Claude Code planning tools
- Committed: Yes

**.venv/:**
- Purpose: Python virtual environment
- Generated: Yes (by python -m venv)
- Committed: No (in .gitignore)

---

*Structure analysis: 2026-03-06*
