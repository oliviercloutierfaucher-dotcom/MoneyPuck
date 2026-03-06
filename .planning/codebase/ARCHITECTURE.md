# Architecture

**Analysis Date:** 2026-03-06

## Pattern Overview

**Overall:** Agent-based pipeline with service orchestration

The system follows a multi-agent pipeline architecture where specialized "agents" (classes) each handle one phase of the data-to-recommendation workflow. A central service layer (`app/core/service.py`) orchestrates data fetching in parallel, then runs agents sequentially through the pipeline.

**Key Characteristics:**
- 6-agent sequential pipeline: data fetch (2 agents in parallel) -> team strength -> edge scoring -> line shopping -> risk management
- Single shared `MarketSnapshot` object flows through the pipeline, avoiding redundant API calls
- Frozen dataclasses (`TeamMetrics`, `ValueCandidate`, `TrackerConfig`, `MarketSnapshot`) enforce immutability of domain objects
- Two entry points: CLI (`tracker.py`) and web server (`app/web/web_preview.py`), both converging on the same service layer
- "Army mode" runs multiple risk profiles against one shared snapshot in parallel via `ThreadPoolExecutor`

## Layers

**CLI / Entry Points:**
- Purpose: Parse user input, dispatch to service layer, format output
- Location: `tracker.py` (CLI), `app/web/web_preview.py` (HTTP server)
- Contains: Argument parsing, output formatting, mode routing (--tonight, --arbs, --backtest, etc.)
- Depends on: `app/core/service.py`, `app/core/models.py`, `app/web/presentation.py`
- Used by: End users (CLI) and Railway deployment (web)

**Service / Orchestration:**
- Purpose: Coordinate data fetching, build snapshots, run the scoring pipeline
- Location: `app/core/service.py`
- Contains: `build_market_snapshot()`, `score_snapshot()`, `run_tracker()`, `settle_outstanding()`, circuit breaker, data freshness checks, injury overrides
- Depends on: All agents (`app/core/agents.py`), data sources, Elo, database
- Used by: CLI, web server, army mode, backtester

**Agents (Core Pipeline):**
- Purpose: Implement each phase of the betting model pipeline
- Location: `app/core/agents.py`
- Contains: `MarketOddsAgent`, `MoneyPuckDataAgent`, `TeamStrengthAgent`, `EdgeScoringAgent`, `LineShoppingAgent`, `RiskAgent`
- Depends on: `app/math/`, `app/data/data_sources.py`, `app/data/nhl_api.py`
- Used by: `app/core/service.py`, `app/core/backtester.py`

**Domain Models:**
- Purpose: Define frozen dataclass types shared across all layers
- Location: `app/core/models.py`
- Contains: `TrackerConfig`, `TeamMetrics` (16 metrics + composites), `ValueCandidate`, `MarketSnapshot`
- Depends on: Nothing (leaf module)
- Used by: Every other module

**Math / Analytics:**
- Purpose: Pure mathematical functions for odds, probability, Kelly criterion, Elo, arbitrage, situational factors
- Location: `app/math/` directory
- Contains: `math_utils.py` (core odds/probability/Kelly/composite), `elo.py` (Elo rating system), `arbitrage.py` (arb detection), `situational.py` (rest/travel adjustments), `hedge.py` (hedge calculator), `validation.py` (Brier score, model health)
- Depends on: Nothing external (pure functions, no API calls)
- Used by: Agents, service layer, web server, backtester

**Data Sources / API Clients:**
- Purpose: Fetch external data from APIs and CSVs
- Location: `app/data/` directory
- Contains: `data_sources.py` (Odds API, MoneyPuck CSVs, Polymarket), `nhl_api.py` (NHL public API), `database.py` (SQLite persistence), `polymarket.py` (dedicated Polymarket client), `player_props.py` (player prop markets), `odds_history.py` (line movement tracking)
- Depends on: External HTTP APIs (no third-party SDKs, uses stdlib `urllib`)
- Used by: Agents, service layer, web server

**Web / Presentation:**
- Purpose: HTTP server, HTML rendering, sportsbook deep links
- Location: `app/web/` directory
- Contains: `web_preview.py` (ThreadingHTTPServer with all API routes), `presentation.py` (HTML dashboard rendering, JSON serialization), `deep_links.py` (sportsbook URL generation)
- Depends on: Service layer, math utilities, data sources
- Used by: Railway deployment, `live_preview.py` (dev mode)

**Persistence:**
- Purpose: SQLite storage for predictions, model runs, closing odds, CLV tracking
- Location: `app/data/database.py`
- Contains: `TrackerDatabase` class with schema migrations, CRUD for predictions/runs/closing_odds
- Depends on: stdlib `sqlite3`
- Used by: Service layer (settlement, persistence), web server (bet tracker)

## Data Flow

**Primary Pipeline (--tonight / default mode):**

1. `tracker.py` or `web_preview.py` calls `build_market_snapshot(config)` in `app/core/service.py`
2. Service spawns 4 parallel threads: `MarketOddsAgent` (Odds API), `MoneyPuckDataAgent` (MoneyPuck CSVs), goalie stats (NHL API), Polymarket odds
3. Polymarket events are merged into the odds events list as an additional "bookmaker"
4. `TeamStrengthAgent.run()` processes game rows: extract metrics -> weighted averages (exponential decay) -> Z-score normalize -> Bayesian regression -> composite scores -> rolling windows (5g, 10g, momentum) -> enrich with goalie save%
5. Result is a `MarketSnapshot` containing `odds_events` + `team_strength` dict
6. `score_snapshot()` checks circuit breaker -> data freshness -> loads injury overrides -> builds Elo ratings from game history -> `EdgeScoringAgent` scores each bookmaker line against model probability (logistic + Elo ensemble + situational + goalie adjustments) -> `RiskAgent` applies line shopping + Kelly sizing + bankroll caps
7. Recommendations are returned as `list[dict]` with `candidate: ValueCandidate` and `recommended_stake: float`

**Arbitrage Scanning (--arbs):**

1. `build_market_snapshot(config)` fetches odds (same as above)
2. `find_arbitrages(odds_events)` in `app/math/arbitrage.py` extracts best moneyline/spread/total odds per side across all bookmakers
3. Checks if combined implied probability < 100% (guaranteed arb) or < 102% (near-arb)
4. Returns sorted opportunities with optimal stake splits

**Settlement Flow (--settle):**

1. `settle_outstanding()` in `app/core/service.py` queries unsettled predictions from SQLite
2. Fetches closing odds from Odds API (best-effort CLV capture)
3. Fetches NHL game scores grouped by date via `app/data/nhl_api.py`
4. Matches predictions to outcomes, computes P&L, updates database in a single transaction
5. Calculates CLV summary from `app/core/clv.py`

**Backtesting Flow (--backtest):**

1. Fetches full season of MoneyPuck data
2. For each game date, uses only prior games as training data (rolling window)
3. Builds team strength + Elo ratings from training window
4. Predicts outcomes, compares against actual scores
5. Computes Brier score, accuracy, log loss, ROI, and production readiness assessment

**State Management:**
- `TrackerConfig` is a frozen dataclass created once from CLI args or web request params
- `MarketSnapshot` is built once per cycle and shared (read-only) across all scoring agents
- `TeamMetrics` and `ValueCandidate` are frozen dataclasses -- no mutation after creation
- Army mode uses `dataclasses.replace()` to create per-profile config variants from a shared snapshot
- SQLite database at `~/.moneypuck/tracker.db` stores predictions, model runs, closing odds
- Injury overrides stored in `~/.moneypuck/overrides.json` (manual JSON file)

## Key Abstractions

**Agent Classes:**
- Purpose: Encapsulate one pipeline phase as a callable class
- Examples: `app/core/agents.py` -- `MarketOddsAgent`, `MoneyPuckDataAgent`, `TeamStrengthAgent`, `EdgeScoringAgent`, `LineShoppingAgent`, `RiskAgent`
- Pattern: Each agent has a `run()` method that takes inputs from prior stages and returns typed output. Agents are stateless -- all state comes from parameters.

**Frozen Dataclasses:**
- Purpose: Immutable domain objects that flow through the pipeline
- Examples: `app/core/models.py` -- `TeamMetrics` (26 fields), `ValueCandidate` (14 fields), `TrackerConfig` (17 fields), `MarketSnapshot` (7 fields)
- Pattern: `@dataclass(frozen=True)` ensures no mutation. New variants created via `dataclasses.replace()`.

**Odds API Format (Shared Event Schema):**
- Purpose: Common JSON structure for odds data regardless of source
- Examples: Used by `app/data/data_sources.py` (Odds API), `app/data/data_sources.py` (Polymarket adapter), `app/math/arbitrage.py`
- Pattern: `{"home_team": str, "away_team": str, "commence_time": str, "bookmakers": [{"key": str, "title": str, "markets": [{"key": "h2h", "outcomes": [...]}]}]}`. Polymarket data is converted to this format so the entire pipeline treats all sources uniformly.

**EloTracker:**
- Purpose: Maintains and updates Elo ratings across a season
- Examples: `app/math/elo.py` -- `EloTracker` class
- Pattern: Stateful object (unlike agents) that accumulates ratings via `.update()` calls. Built once from historical data via `build_elo_ratings()`, then passed into `EdgeScoringAgent` for ensemble blending (25% Elo + 75% logistic).

## Entry Points

**CLI (`tracker.py`):**
- Location: `tracker.py`
- Triggers: `python tracker.py --tonight`, `python tracker.py --arbs`, `python tracker.py --backtest`, etc.
- Responsibilities: Load .env, parse args, validate config, dispatch to appropriate mode, format and print output. Supports JSON output via `--json` flag.

**Web Server (`app/web/web_preview.py`):**
- Location: `app/web/web_preview.py`
- Triggers: `python -m app.web.web_preview` or Docker container (Railway deployment)
- Responsibilities: HTTP server on `0.0.0.0:PORT` using stdlib `ThreadingHTTPServer`. Serves dashboard HTML, JSON API endpoints for games/bets/arbs/props/polymarket/hedge/bet-tracker. Supports demo mode (random data) when no API key is set.

**Dev Preview (`live_preview.py`):**
- Location: `live_preview.py`
- Triggers: `python live_preview.py`
- Responsibilities: Development-mode web preview with auto-refresh and demo data generation.

## Error Handling

**Strategy:** Fail-soft with logging. External data failures are caught and degraded gracefully rather than crashing.

**Patterns:**
- All external API calls wrapped in try/except with retry logic (`_fetch_with_retry` in `data_sources.py` -- 3 retries with exponential backoff)
- `ThreadPoolExecutor` futures have 45-second timeouts; failures produce empty results, not crashes
- Circuit breaker in `service.py`: if recent Brier score > 0.26 (worse than coin flip), stop generating recommendations
- Data freshness validation: critical warnings block recommendations, non-critical warnings are logged
- NHL API client (`nhl_api.py`) returns empty collections on any failure -- "best-effort enrichment"
- Database operations wrapped in context managers with rollback on failure
- Settlement uses explicit transaction with BEGIN/COMMIT/ROLLBACK for atomicity

## Cross-Cutting Concerns

**Logging:** Centralized via `app/logging_config.py`. All modules use `get_logger("module_name")` which returns a child logger under the `moneypuck` namespace. Output to stderr with timestamp + level + name format. Controlled by `LOG_LEVEL` env var or `--log-level` CLI arg.

**Validation:** Input validation happens at CLI argument level (`_validate_args` in `tracker.py`). Math functions use clamping (`_clamp_probability`) rather than raising. Config uses frozen dataclasses so invalid state cannot be set after construction.

**Authentication:** The Odds API key is the only credential. Loaded from `ODDS_API_KEY` env var or `--odds-api-key` CLI arg. The `.env` file is loaded by a custom `_load_dotenv()` function (no python-dotenv dependency). NHL API and Polymarket require no authentication.

**Concurrency:** `ThreadPoolExecutor` used in two places: (1) parallel data fetching in `build_market_snapshot()` with 4 workers, (2) army mode parallel profile evaluation in `run_agent_army()` with 5 workers. Web server uses `ThreadingHTTPServer` for concurrent request handling.

---

*Architecture analysis: 2026-03-06*
