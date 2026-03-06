# Testing Patterns

**Analysis Date:** 2026-03-06

## Test Framework

**Runner:**
- pytest (version 9.0.2)
- Config: No `pytest.ini`, `pyproject.toml`, or `setup.cfg` found. Uses pytest defaults.

**Assertion Library:**
- pytest built-in `assert` statements
- `pytest.raises` for exception testing
- `pytest.approx` for floating-point comparison

**Run Commands:**
``` bash
pytest                    # Run all tests
pytest tests/math/        # Run math module tests
pytest tests/core/        # Run core module tests
pytest -v                 # Verbose output
```

## Test File Organization

**Location:** Separate `tests/` directory mirroring `app/` structure (NOT co-located)

**Naming:** `test_<module_name>.py` matching the source module

**Structure:**
```
tests/
  __init__.py
  core/
    __init__.py
    test_army.py
    test_backtester.py
    test_clv.py
    test_pipeline.py
    test_risk.py
    test_rolling_features.py
    test_settlement.py
    test_team_strength.py
  data/
    __init__.py
    test_database.py
    test_nhl_api.py
    test_odds_history.py
    test_player_props.py
  math/
    __init__.py
    test_arbitrage.py
    test_elo.py
    test_hedge.py
    test_math_utils.py
    test_situational.py
    test_validation.py
    test_win_probability.py
  web/
    __init__.py
    test_arb_detection.py
    test_deep_links.py
    test_performance.py
    test_presentation.py
    test_web_preview.py
```

## Test Structure

**Two patterns coexist:**

**Pattern 1: Test classes (preferred for math/pure functions):**
- One class per function/component under test
- Class docstring names the function
- Method names: `test_<scenario>` or `test_<input>_<expected_behavior>`
- Test docstrings explain the "why" when non-obvious

**Pattern 2: Standalone functions (for integration/pipeline tests):**
- Used in `tests/core/test_pipeline.py`, `tests/core/test_team_strength.py`
- Inline test data construction (no shared fixtures)

**Section separators:**
- Comment blocks divide test files into logical groups

## Test Data and Helpers

**Factory functions (module-level, prefixed with underscore):**
- Located at the top of each test file, NOT in a shared fixtures module
- Use keyword arguments with sensible defaults for flexibility
- Return plain dicts matching the data format expected by the code under test

**Key helper patterns:**

| File | Helper | Purpose |
|------|--------|---------|
| `tests/core/test_team_strength.py` | `_make_game_row()` | Build legacy CSV game rows |
| `tests/math/test_elo.py` | `_make_team_gbg_row()` | Build MoneyPuck team-gbg rows |
| `tests/math/test_arbitrage.py` | `_make_event()`, `_make_bookmaker()`, `_h2h_market()` | Build Odds API format events |
| `tests/data/test_database.py` | `_tmp_db()`, `_make_recommendation()` | Temp SQLite DB + recommendation dict |
| `tests/core/test_settlement.py` | `_make_unique_recommendation()` | Recommendations with unique timestamps |
| `tests/web/test_performance.py` | `_make_prediction()` | Full prediction dict with all fields |

**No conftest.py:** Each test file is self-contained with its own helpers.

## Mocking

**Framework:** `unittest.mock` (stdlib)

**Patterns:**

**1. Patching external API calls:** Use `@patch("app.data.nhl_api._fetch_json")` decorator

**2. Patching database class for integration tests:** Custom `_patch_db(db)` helper in `tests/core/test_settlement.py`

**3. monkeypatch for module attributes:** Used for `app.data.database.DB_PATH` override

**What to Mock:**
- Network calls to external APIs (NHL API, Odds API, MoneyPuck, Polymarket)
- Database constructors (use temp SQLite files instead of production DB)
- File system paths (override `OVERRIDES_PATH` for override tests)

**What NOT to Mock:**
- Math functions (always test real calculations)
- Data model constructors (`TeamMetrics`, `ValueCandidate`, `TrackerConfig`)
- Agent pipeline logic (test with real agents, mock only data sources)

## Fixtures and Factories

**Test Data:**
- All test data is constructed inline or via `_make_*()` helper functions
- No fixture files, JSON fixtures, or CSV test data on disk
- `_tmp_db()` creates real SQLite databases in `tempfile.mkdtemp()` for database tests

**Location:** Helpers defined at the top of each test file. No shared `tests/fixtures/` directory.

## Coverage

**Requirements:** No formal coverage targets enforced. No coverage config found.

## Test Types

**Unit Tests (majority):**
- Pure function tests in `tests/math/`: odds conversion, Kelly, Elo, decay, win probability
- Thorough edge case coverage: zero inputs, negative values, extreme values, boundary conditions
- Numerical stability tests for overflow/underflow scenarios
- Cross-function consistency checks (e.g., EV and Kelly sign agreement)
- Example: `tests/math/test_math_utils.py` has 70+ test methods across 12 test classes

**Integration Tests:**
- Pipeline tests in `tests/core/test_pipeline.py`: end-to-end EdgeScoringAgent -> RiskAgent
- Settlement tests in `tests/core/test_settlement.py`: DB + mock API -> settlement logic
- Circuit breaker tests: create N predictions, settle them, verify breaker behavior
- Override tests: write temp JSON file, load and apply overrides

**E2E Tests:**
- Not used. No browser/HTTP-level testing.
- Web dashboard tested via function calls to `_build_demo_dashboard()`, not HTTP requests.

## Common Patterns

**Floating-point comparison:**
- `assert abs(result - 0.5) < 0.001` -- most common pattern (legacy)
- `assert win_probability(1500, 1500) == pytest.approx(0.5)` -- preferred for new tests
- `assert round(american_to_decimal(150), 2) == 2.50` -- for exact decimal comparison

**Exception Testing:**
- `with pytest.raises(ValueError, match="cannot be 0"):`

**Parameterized-style testing (manual loops, NOT @pytest.mark.parametrize):**
- Loop-based parameterization is the convention; `pytest.mark.parametrize` is NOT used anywhere

**Property-based assertions:**
- Zero-sum checks for Elo (winner gain == loser loss)
- Monotonicity checks (larger inputs produce larger outputs)
- Symmetry checks (swapping teams swaps probabilities)

**Test naming conventions:**
- `test_<scenario>`: `test_positive_150`, `test_equal_teams_fifty_percent`
- `test_<input>_<behavior>`: `test_zero_raises_value_error`, `test_negative_days_returns_zero`
- Descriptive docstrings on most tests

## Test Count

**Approximate test distribution (306 total):**
- `tests/math/` (~150 tests): Heaviest coverage, pure math functions
- `tests/core/` (~80 tests): Pipeline, settlement, team strength, circuit breaker
- `tests/web/` (~40 tests): Dashboard, performance, deep links, presentation
- `tests/data/` (~36 tests): Database, NHL API, odds history, player props

---

*Testing analysis: 2026-03-06*
