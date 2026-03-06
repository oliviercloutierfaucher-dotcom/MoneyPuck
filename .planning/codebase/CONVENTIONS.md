# Coding Conventions

**Analysis Date:** 2026-03-06

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules: `math_utils.py`, `data_sources.py`, `web_preview.py`
- Test files: `test_<module>.py` matching the source module name
- `__init__.py` present in all packages (mostly empty, for namespace)

**Functions:**
- Use `snake_case` for all functions and methods: `fetch_odds()`, `build_market_snapshot()`, `composite_strength()`
- Private/internal functions prefixed with underscore: `_clamp_probability()`, `_safe_int()`, `_fetch_with_retry()`
- Helper factory functions in tests: `_make_game_row()`, `_make_recommendation()`, `_tmp_db()`

**Variables:**
- Use `snake_case` for local variables and parameters: `home_team`, `goal_diff`, `odds_events`
- Short abbreviations acceptable for loop/temporary vars: `hp`, `ap`, `dec`, `ev`, `kf`
- Dict keys use `snake_case`

**Constants:**
- Use `UPPER_SNAKE_CASE` for module-level constants: `INITIAL_ELO`, `K_FACTOR`, `HOME_ADVANTAGE`, `MAX_RETRIES`
- Dict-typed constants also `UPPER_SNAKE_CASE`: `DEFAULT_METRIC_WEIGHTS`, `QUEBEC_BOOKS`, `TEAM_NAME_TO_CODE`

**Classes:**
- Use `PascalCase`: `TeamStrengthAgent`, `EdgeScoringAgent`, `EloTracker`, `MarketSnapshot`
- Agent classes follow the pattern `<Name>Agent`: `MarketOddsAgent`, `RiskAgent`
- Data classes follow domain naming: `TeamMetrics`, `ValueCandidate`, `TrackerConfig`

**Types:**
- Type hints use modern Python syntax: `dict[str, float]`, `list[dict]`, `tuple[float, float]`
- Union types use pipe syntax: `str | None`, `EloTracker | None`

## Code Style

**Formatting:**
- No explicit formatter configured (no .prettierrc, pyproject.toml, setup.cfg, or ruff.toml)
- 4-space indentation throughout
- Line length varies but generally stays under ~100-110 characters
- Blank lines separate logical sections within functions

**Linting:**
- No explicit linter configured
- `# noqa: BLE001` used to suppress bare-except warnings in `app/core/service.py`

**Future imports:**
- Every module starts with `from __future__ import annotations`

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first)
2. Standard library imports: math, json, os, csv, io, time, datetime, collections, typing
3. Third-party imports: `numpy as np`, `pytest`
4. Local application imports: `from app.core.models import ...`

**Style:**
- Prefer explicit named imports over star imports
- Long import lists wrapped with parentheses across multiple lines (see `app/core/agents.py` lines 42-57)
- Use `import numpy as np` (the only third-party runtime dependency)

**Path Aliases:**
- None. All imports use full dotted paths: `from app.core.agents import EdgeScoringAgent`

## Error Handling

**Patterns:**
- Use ValueError for invalid inputs in `app/math/math_utils.py`
- Use ValueError for schema validation in `app/data/data_sources.py`
- Broad `except Exception` with `# noqa: BLE001` for non-critical operations: return default/empty rather than crash
- Try/except at boundaries (CLI, network calls); core math functions do NOT catch exceptions
- `log.exception()` for unexpected failures; `log.warning()` for degraded but recoverable states

**Clamping pattern:**
- Probability values clamped to [0.01, 0.99] or [0.0, 1.0] using `max(min_val, min(max_val, value))`
- Used in `_clamp_probability()`, `logistic_win_probability()`, `edge_adjusted_confidence()`

**Retry pattern:**
- Network calls use `_fetch_with_retry()` in `app/data/data_sources.py` with exponential backoff
- Max 3 retries, retries on HTTP 429/5xx and network errors, raises on 4xx client errors

**Fail-open pattern:**
- Circuit breaker check fails open: `app/core/service.py` line 183
- Goalie fetch is best-effort via `_fetch_goalies_safe()`: returns empty list on failure
- Polymarket merge is best-effort: errors swallowed, returns empty list

## Logging

**Framework:** Python logging module via centralized config in `app/logging_config.py`

**Setup:**
- Root logger: moneypuck namespace
- Child loggers via `get_logger(name)`
- Output to stderr
- Default level: INFO (configurable via LOG_LEVEL env var or --log-level CLI flag)

**Patterns:**
- Each module creates a logger at module level: `log = get_logger("agents")`
- Use %s style formatting (not f-strings) for lazy evaluation
- `log.info()` for normal operations, `log.warning()` for degraded states
- `log.error()` for critical failures, `log.debug()` for verbose tracing
- `log.exception()` only for unexpected errors where traceback is needed

## Comments

- Extensive parameter audits in `app/math/math_utils.py` with mathematical rationale and backtester grid values
- Section separators using comment blocks to divide agent classes and function groups
- Module-level docstrings in `app/core/agents.py` list known limitations and missing data
- Function docstrings use free-form prose, not formal RST/Google style
- Some functions use numpy-style Parameters/Returns sections (see `app/math/elo.py`)

## Function Design

**Size:** Most functions are 5-30 lines. Agent `.run()` methods can be 50-100+ lines.

**Parameters:**
- Use typed parameters throughout
- Config objects passed as `config: TrackerConfig` rather than individual params
- Optional params use `| None` with default None

**Return Values:**
- Typed returns: `-> float`, `-> tuple[float, float]`, `-> list[ValueCandidate]`
- Tuple returns for related values; dict returns for complex results

## Module Design

- No `__all__` defined in any module
- `__init__.py` files are empty (no re-exports)
- Imports always reference the exact module: `from app.math.elo import EloTracker`

## Data Modeling

**Immutable data classes:** All core types use `@dataclass(frozen=True)`
- Fields have sensible defaults (0.5 for share metrics, 0.0 for rates)
- No mutation after construction; new instances created when changes needed

**Agent pattern:**
- Each agent is a class with a `name` attribute and a `run()` method
- Agents are stateless (no instance state between runs)
- Pipeline: MarketOddsAgent -> MoneyPuckDataAgent -> TeamStrengthAgent -> EdgeScoringAgent -> LineShoppingAgent -> RiskAgent

## CLI Design

- Single entry point: `tracker.py` with argparse
- Boolean flags for modes: --tonight, --arbs, --polymarket, --backtest, --army
- --json flag for machine-readable output; human-readable by default
- Return codes: 0 success, 1 config error, 2 runtime error

---

*Convention analysis: 2026-03-06*
