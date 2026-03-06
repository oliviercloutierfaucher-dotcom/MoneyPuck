# Codebase Concerns

**Analysis Date:** 2026-03-06

## Tech Debt

**Massive Presentation File:**
- Issue: `app/web/presentation.py` is 2,261 lines -- the largest file in the project. It mixes HTML generation, CSS, JavaScript, and data formatting all in a single Python module.
- Files: `app/web/presentation.py`
- Impact: Extremely difficult to modify the dashboard UI. Any CSS/JS/HTML change requires editing a giant Python string. No IDE support for embedded languages.
- Fix approach: Extract HTML/CSS/JS into separate template files (Jinja2 or static assets). Serve static files from the web server. This also enables frontend tooling (linting, minification, live reload).

**Custom HTTP Server Instead of Framework:**
- Issue: `app/web/web_preview.py` uses `http.server.BaseHTTPRequestHandler` (stdlib) with manual routing, header management, and response serialization. The `do_GET` handler is a single 150+ line method with nested if/elif for routing.
- Files: `app/web/web_preview.py` (lines 920-1061)
- Impact: No middleware support, no request parsing utilities, no async support, no WSGI compatibility. Adding new endpoints requires adding more branches to the monolithic handler. Hard to add features like rate limiting or authentication for a paid product.
- Fix approach: Migrate to Flask or FastAPI. The existing route structure maps cleanly to decorator-based routing. FastAPI would also provide automatic OpenAPI docs for the API.

**Duplicate .env Loading:**
- Issue: Both `tracker.py` and `app/web/web_preview.py` implement their own `_load_dotenv()` functions with identical logic, rather than using the `python-dotenv` package.
- Files: `tracker.py` (lines 177-188), `app/web/web_preview.py` (lines 1066-1077)
- Impact: If the .env format changes or edge cases emerge (quoted values, multiline, export prefix), both must be updated. The current parser is naive and does not handle these cases.
- Fix approach: Add `python-dotenv` to requirements and call `load_dotenv()` at each entry point. Remove both custom implementations.

**Hardcoded Demo Data:**
- Issue: Demo mode data (matchups, strength ratings, team stats) is hardcoded across multiple files with overlapping but inconsistent data.
- Files: `app/web/web_preview.py` (lines 104-123 DEMO_MATCHUPS, DEMO_STRENGTH), `live_preview.py` (lines 29-185 _build_demo_game_rows), `live_preview.py` (lines 188-230 _build_demo_odds)
- Impact: Demo data diverges from the real model output format over time. Changes to the data model require updating demo data in multiple places.
- Fix approach: Create a single `app/data/demo.py` module that generates all demo data from one source of truth.

**Private Member Access in Service Layer:**
- Issue: `app/core/service.py` directly accesses `db._conn` to manage transactions in `settle_outstanding()`.
- Files: `app/core/service.py` (lines 528, 625, 627)
- Impact: Breaks encapsulation. If the database class changes its connection management, the service layer silently breaks. The settlement logic should not need to know about SQLite connection internals.
- Fix approach: Add a `begin()`, `commit()`, and `rollback()` method to `TrackerDatabase`, or add a transaction context manager.

**Backtester ROI Simulation Uses Synthetic Odds:**
- Issue: `simulate_betting_roi()` in `app/core/backtester.py` cannot use real historical odds, so it synthesizes market lines. The comments in the code (lines 346-368) show extensive deliberation and uncertainty about the correct approach, with multiple crossed-out strategies.
- Files: `app/core/backtester.py` (lines 289-432)
- Impact: ROI simulation results are unreliable. The synthetic market always uses a fixed `market_base = 0.537`, which does not reflect real line movement or book-specific pricing. Backtest ROI numbers ($1K to $29.7K) are likely inflated.
- Fix approach: Store historical odds snapshots via `app/data/odds_history.py` and replay real lines in the backtester. Until then, clearly label ROI as "synthetic" in output.

**Hardcoded Season String in NHL API:**
- Issue: `fetch_goalie_stats()` and `fetch_team_schedule()` default to `season="20242025"` as a hardcoded string, not derived from the config's season parameter.
- Files: `app/data/nhl_api.py` (lines 94, 130)
- Impact: When the season changes, goalie stats and team schedules will silently return stale or empty data. The rest of the pipeline uses `config.season` (an int like 2025), but the NHL API expects `"20252026"`.
- Fix approach: Accept season as a parameter derived from `config.season` and convert using `f"{season}{season+1}"`.

## Security Considerations

**No Authentication on Web Dashboard:**
- Risk: The web dashboard at `0.0.0.0:8080` is completely unauthenticated. Anyone with network access can view betting recommendations, trigger live API calls (consuming Odds API quota), and view performance data.
- Files: `app/web/web_preview.py` (lines 920-1061, 1080-1094)
- Current mitigation: The API key is read from environment variables and never exposed to the client. Security headers (CSP, X-Frame-Options) are sent.
- Recommendations: Add at minimum HTTP Basic Auth or an API token for the dashboard. Critical for a paid product. Consider adding rate limiting per IP to prevent API quota abuse.

**API Key Passed Through Config Objects:**
- Risk: `TrackerConfig` contains `odds_api_key` as a plain string field. If configs are ever logged, serialized to JSON, or included in error messages, the key leaks.
- Files: `app/core/models.py` (line 70), `app/core/service.py` (lines 668-677 -- config serialized to JSON for model_runs table, but api_key is excluded)
- Current mitigation: The `_persist_recommendations` function manually selects which config fields to serialize, excluding the API key. But this is fragile.
- Recommendations: Either exclude `odds_api_key` from the dataclass entirely (pass separately), or implement `__repr__` on `TrackerConfig` that redacts the key.

**Custom .env Parser May Have Edge Cases:**
- Risk: The custom `_load_dotenv()` does not strip quotes from values. A value like `ODDS_API_KEY="sk-abc123"` would set the env var including the quotes, causing API auth failures. The parser does not validate the file path and reads from a relative path.
- Files: `tracker.py` (lines 177-188), `app/web/web_preview.py` (lines 1066-1077)
- Current mitigation: `.env` is in `.gitignore`.
- Recommendations: Use `python-dotenv` which handles edge cases properly.

**Web Server Binds to 0.0.0.0 by Default:**
- Risk: The server listens on all interfaces by default, exposing it to the network.
- Files: `app/web/web_preview.py` (line 1083)
- Current mitigation: Railway deployment sets PORT; local dev exposes on all interfaces.
- Recommendations: Default to `127.0.0.1` for local dev. Only bind to `0.0.0.0` when `PORT` env var is set (production).

## Performance Bottlenecks

**Sequential Per-Team Data Fetching:**
- Problem: `fetch_team_game_by_game()` fetches 32 individual CSV files from MoneyPuck sequentially, one team at a time.
- Files: `app/data/data_sources.py` (lines 453-498)
- Cause: The loop `for team in target_teams` makes sequential HTTP requests with retry logic. Each request has a 20-second timeout. Worst case: 32 * 20s = 640 seconds.
- Improvement path: Use `concurrent.futures.ThreadPoolExecutor` to fetch all 32 team CSVs in parallel (already used elsewhere in the codebase for similar patterns). This would reduce fetch time from ~30-60s to ~5-10s.

**N+1 API Calls in Score Settlement:**
- Problem: `fetch_scores_for_date()` calls `fetch_game_score()` individually for each completed game, creating an N+1 API pattern.
- Files: `app/data/nhl_api.py` (lines 279-296)
- Cause: The function first fetches the schedule, then makes a separate API call per finished game to get the score. For a full slate of 16 games, this is 17 API calls.
- Improvement path: The NHL API `/score/{date}` endpoint returns scores for all games in one call. Replace the N+1 pattern with a single bulk fetch.

**Backtester Grid Search is O(N * M):**
- Problem: Default grid search tests 1,050 parameter combinations, each running a full season backtest. Each backtest iterates all game dates and rebuilds team strength from scratch.
- Files: `app/core/backtester.py` (lines 641-729)
- Cause: No caching of intermediate results. The `TeamStrengthAgent` is instantiated fresh for every game date in every combination.
- Improvement path: Cache team strength computations across parameter combinations that share the same `half_life` and `regression_k`. Use `multiprocessing` for parallel grid search.

**Dashboard Rebuilds Full Pipeline Per Request:**
- Problem: Every request to `/api/dashboard` or `/` in live mode triggers `build_market_snapshot()` + `score_snapshot()`, which fetches from 3 external APIs (Odds API, MoneyPuck, NHL API).
- Files: `app/web/web_preview.py` (lines 940-945), `app/core/service.py` (lines 35-138)
- Cause: No caching layer. The 60-second auto-refresh on the frontend means these API calls happen every minute per connected user.
- Improvement path: Cache the snapshot with a TTL (e.g., 60 seconds). Serve cached data to all concurrent users. The `MAX_DATA_AGE_SECONDS` (6 hours) constant already exists for staleness but is only checked downstream, not used for caching.

## Fragile Areas

**Polymarket Title Parsing:**
- Files: `app/data/data_sources.py` (lines 299-341)
- Why fragile: Relies on Polymarket event titles following the exact format `"Away vs. Home"`. If Polymarket changes their title format (e.g., adds "NHL:" prefix, uses "at" instead of "vs."), all parsing breaks silently -- the function returns empty results.
- Safe modification: Add regex-based parsing with fallback patterns. Log unmatched titles at WARNING level.
- Test coverage: Tests exist in `tests/web/test_arb_detection.py` but mock the data, so format changes in the real API would not be caught.

**Team Name Mapping Dictionaries:**
- Files: `app/data/data_sources.py` (lines 81-117, 228-261)
- Why fragile: Two separate hardcoded dictionaries map team names to codes (`TEAM_NAME_TO_CODE` for Odds API full names, `_POLYMARKET_NAME_TO_CODE` for Polymarket short names). If a team rebrands (e.g., "Utah Hockey Club" to "Utah Mammoth" -- both are already listed), relocates, or if the API changes its name format, edges will be silently dropped.
- Safe modification: Always log when a team name fails to map. Consider a fuzzy-match fallback.
- Test coverage: No tests verify the completeness of these mappings against live API responses.

**Settlement Transaction Logic:**
- Files: `app/core/service.py` (lines 456-643)
- Why fragile: The `settle_outstanding()` function is 187 lines with deeply nested logic: date grouping, score lookups, CLV calculation, postponement detection, and transaction management. It directly accesses `db._conn` for manual transaction control. A single exception in any nested block rolls back all settlements for that run.
- Safe modification: Break into smaller functions: `_match_scores()`, `_calculate_clv()`, `_settle_prediction()`. Use the database's own transaction API.
- Test coverage: Tests exist in `tests/core/test_settlement.py` (373 lines) but rely heavily on mocking.

**MoneyPuck CSV Schema Detection:**
- Files: `app/core/agents.py` (lines 120-125)
- Why fragile: The code detects data format by checking `"playerTeam" in games_rows[0]`. If MoneyPuck changes column names or the first row is malformed, the entire pipeline falls back to legacy mode silently, using fewer metrics and producing degraded predictions without any warning to the user.
- Safe modification: Validate the full schema at ingestion time. Log which format was detected and what columns are available.
- Test coverage: Both paths are tested, but there is no test for partial schema (some columns missing).

## Scaling Limits

**SQLite Single-Writer Bottleneck:**
- Current capacity: SQLite handles the current single-user workload fine.
- Limit: If the product scales to multiple concurrent users or processes writing predictions, SQLite's single-writer lock will cause contention. WAL mode (enabled) helps for read concurrency but not write concurrency.
- Scaling path: Migrate to PostgreSQL. The database layer is already abstracted behind `TrackerDatabase`, so the migration surface is manageable.

**Odds API Rate Limits:**
- Current capacity: Free tier allows 500 requests/month. Each dashboard refresh uses 1 request. Each full pipeline run uses 1-2.
- Limit: At 60-second auto-refresh, a single user consumes ~43,200 requests/month in live mode (well above free tier).
- Scaling path: Implement server-side caching (already noted above). Upgrade to paid Odds API tier for production. Add request counting/budget tracking.

**ThreadPoolExecutor for Concurrency:**
- Current capacity: `ThreadPoolExecutor(max_workers=4)` in service.py handles the 4 parallel API fetches.
- Limit: Python's GIL means CPU-bound work (team strength computation, z-score normalization) does not benefit from threads. For the grid search backtester, this is a significant bottleneck.
- Scaling path: Use `multiprocessing.Pool` for CPU-bound backtesting. Keep `ThreadPoolExecutor` for I/O-bound API fetches.

## Dependencies at Risk

**MoneyPuck Data Source:**
- Risk: The bulk `games.csv` endpoint already returns 403 (noted in project memory). The per-team CSV endpoints could suffer the same fate. MoneyPuck is a free community resource with no SLA.
- Impact: If MoneyPuck goes down or blocks scraping, the model loses all team strength data. The fallback chain goes: team-gbg -> bulk CSV (already dead) -> empty.
- Migration plan: Add NHL API as an alternative data source for basic stats. The NHL API provides shots, goals, and other basic metrics. MoneyPuck's xG models would be lost, but core functionality would survive.

**NHL Public API (api-web.nhle.com):**
- Risk: Undocumented API with no versioning or stability guarantees. Endpoint structure and response format could change without notice.
- Impact: Breaks goalie stats, schedule, scores, and standings. Settlement would stop working.
- Migration plan: Pin response schemas. Add defensive parsing that logs unexpected formats rather than crashing.

## Missing Critical Features

**No User Account / Multi-Tenancy:**
- Problem: The system assumes a single user. There is no concept of user accounts, API key management, or subscription tiers.
- Blocks: Cannot charge for the product. Cannot support multiple users with different bankrolls/configs.

**No Confirmed Starting Goalie Feed:**
- Problem: `infer_likely_starter()` uses season GP leader as a proxy for tonight's starter. This is explicitly documented as a known limitation in `app/data/nhl_api.py` (lines 222-236).
- Blocks: Goalie matchup adjustments (+/- 1-3pp) are unreliable on backup-start nights, degrading edge detection accuracy.

## Test Coverage Gaps

**Web Server Handler Not Integration-Tested:**
- What's not tested: The `PreviewHandler.do_GET()` method routes and builds responses, but no test actually starts the HTTP server and makes real HTTP requests.
- Files: `app/web/web_preview.py` (lines 920-1061)
- Risk: Routing bugs, header issues, and content-type mismatches would go unnoticed. The test file `tests/web/test_web_preview.py` tests helper functions but not the handler itself.
- Priority: Medium

**No Tests for Live Data Pipeline Integration:**
- What's not tested: The full pipeline from `build_market_snapshot()` through `score_snapshot()` to `run_tracker()` is never tested end-to-end with realistic (even mocked) data flowing through all agents.
- Files: `app/core/service.py`, `app/core/agents.py`
- Risk: Agent interface mismatches, data format issues between agents, and error propagation bugs could go unnoticed.
- Priority: High

**No Tests for .env Loading or CLI Argument Validation Edge Cases:**
- What's not tested: The custom `_load_dotenv()` functions are not tested with malformed .env files. CLI validation in `tracker.py` `_validate_args()` has no direct test.
- Files: `tracker.py` (lines 55-71, 177-188)
- Risk: Low -- these are well-understood patterns, but the custom .env parser could cause subtle bugs.
- Priority: Low

**No Regression Test for Backtest Performance Metrics:**
- What's not tested: The headline backtest result ($1K to $29.7K, 18.6% ROI) is not captured in any test assertion. If a code change silently degrades model performance, the only way to notice is manually re-running the backtest.
- Files: `app/core/backtester.py`
- Risk: Model regressions go undetected. Changes to TeamStrengthAgent, EdgeScoringAgent, or math functions could worsen predictions without any test failure.
- Priority: High -- Add a "golden file" test that runs the backtester on a fixed dataset and asserts key metrics stay within acceptable bounds.

---

*Concerns audit: 2026-03-06*
