# Phase 6: FastAPI Migration - Research

**Researched:** 2026-03-07
**Domain:** Python web framework migration (stdlib HTTP to FastAPI)
**Confidence:** HIGH

## Summary

This phase replaces the stdlib `BaseHTTPRequestHandler` + `ThreadingHTTPServer` in `web_preview.py` (1174 lines) with FastAPI + Uvicorn, and converts the 2314-line f-string HTML in `presentation.py` into a Jinja2 template. The existing codebase has 5 routes (1 HTML page + 4 JSON APIs), a `TTLCache` utility, demo mode, and security headers -- all of which map directly to FastAPI patterns.

FastAPI is the standard Python web framework for this kind of migration. It supports both sync and async endpoints, has built-in Jinja2 template support via `Jinja2Templates`, and `TestClient` makes testing straightforward without running a live server. The migration is mechanical: each `if parsed.path == "/api/..."` block becomes an `@router.get()` decorated function.

**Primary recommendation:** Clean swap -- delete `PreviewHandler` class entirely, create `app/web/app.py` with FastAPI app + APIRouter, single `base.html` Jinja2 template, update Dockerfile CMD to uvicorn.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Minimal template split: single `base.html` Jinja2 template with CSS/JS still inline
- No component decomposition (Phase 7 does full UI rebuild)
- Extract `to_serializable()` and data prep functions as Python utility functions
- Templates in `app/web/templates/`
- Keep existing paths: `/`, `/api/dashboard`, `/api/performance`, `/api/opportunities`, `/api/odds-history`
- Use `APIRouter(prefix="/api")` for JSON endpoints, page routes on main app
- All existing JSON response formats preserved -- no breaking changes
- Full replacement -- delete `BaseHTTPRequestHandler` and `ThreadingHTTPServer` entirely
- No fallback, no gradual migration -- clean swap
- `TTLCache` stays as-is
- `web_preview.py` becomes `app/web/app.py`; old file deleted
- Dockerfile CMD: `uvicorn app.web.app:app --host 0.0.0.0 --port $PORT`
- Single worker (Railway), no hot reload in prod
- `requirements.txt` adds: `fastapi`, `uvicorn[standard]`, `jinja2`

### Claude's Discretion
- Whether to use async endpoints or sync (FastAPI supports both)
- How to handle the existing demo mode toggle in FastAPI context
- Error handling middleware design
- Whether to add a `/health` endpoint now or defer to Phase 8
- How to structure the app factory pattern (if any)
- Test strategy for FastAPI routes (TestClient vs direct)

### Deferred Ideas (OUT OF SCOPE)
- Multi-page routing with Tailwind/HTMX -- Phase 7
- SSE for real-time odds push -- Phase 7
- Health check endpoint -- Phase 8
- Auth middleware -- Phase 10
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| R5.1 | Migrate backend to FastAPI + Uvicorn (keep existing pipeline) | FastAPI app with APIRouter, sync endpoints, Uvicorn CMD in Dockerfile |
| R5.2 | Extract HTML to Jinja2 templates (proper .html files) | Single `base.html` template via `Jinja2Templates`, `TemplateResponse` pattern |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.115 | Web framework | De facto Python API framework, built-in validation, OpenAPI, template support |
| uvicorn[standard] | >=0.30 | ASGI server | Official FastAPI server, production-ready, supports graceful shutdown |
| jinja2 | >=3.1 | Template engine | FastAPI's built-in template integration via `Jinja2Templates` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | (bundled with fastapi) | TestClient backend | Testing -- `TestClient` uses httpx internally |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fastapi | starlette (raw) | FastAPI adds validation, docs, dependency injection on top of Starlette -- no reason to go lower-level |
| uvicorn | gunicorn+uvicorn | Multi-worker unnecessary for Railway single-container; uvicorn alone is simpler |
| sync endpoints | async endpoints | All data fetching (Odds API, MoneyPuck CSVs) uses `requests` (sync). Making endpoints async would require wrapping in `run_in_executor`. Use sync endpoints -- FastAPI handles them in a thread pool automatically |

**Installation:**
```bash
pip install fastapi uvicorn[standard] jinja2
```

**Discretion recommendation -- sync vs async:** Use **sync endpoints**. The existing codebase uses synchronous `requests` library calls throughout the agent pipeline. FastAPI automatically runs sync endpoints in a thread pool, so there is no performance penalty. Converting to async would require wrapping every `requests.get()` call in `asyncio.to_thread()` for no benefit. Keep it simple.

## Architecture Patterns

### Recommended Project Structure
```
app/web/
    app.py              # FastAPI app instance + page routes + startup
    routes/
        api.py          # APIRouter(prefix="/api") with JSON endpoints
    templates/
        base.html       # Single Jinja2 template (converted from f-string)
    presentation.py     # to_serializable() + data prep utilities (kept)
    deep_links.py       # Unchanged
    web_preview.py      # DELETED after migration
```

**Note:** The `routes/` subdirectory is optional. Given only 4 API endpoints + 1 page route, putting everything in `app.py` with a single `APIRouter` is also clean. Recommendation: use a single `app.py` file with the `APIRouter` defined inline -- keeps the migration minimal and matches the "surgical" intent.

### Simplified structure (recommended):
```
app/web/
    app.py              # FastAPI app + all routes (5 total)
    templates/
        base.html       # Single Jinja2 template
    presentation.py     # to_serializable() + data prep (kept, render_dashboard removed)
    deep_links.py       # Unchanged
```

### Pattern 1: FastAPI App with APIRouter
**What:** FastAPI application with router separation for API vs page routes
**When to use:** When you have both HTML-serving and JSON API endpoints

```python
# app/web/app.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI(title="MoneyPuck Edge Intelligence")

templates = Jinja2Templates(
    directory=str(Path(__file__).parent / "templates")
)

# Page route
@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request, demo: str = "0", region: str = "qc"):
    use_demo = demo in {"1", "true", "yes"} or not os.getenv("ODDS_API_KEY", "")
    data = _build_demo_dashboard(params) if use_demo else _build_live_dashboard(params)
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context={"data": data}
    )

# API routes
api_router = APIRouter(prefix="/api")

@api_router.get("/dashboard")
def api_dashboard(demo: str = "0", region: str = "qc"):
    # ... build data ...
    return dashboard_data  # FastAPI auto-serializes to JSON

app.include_router(api_router)
```

### Pattern 2: Security Headers Middleware
**What:** Replace `_send_security_headers()` with FastAPI middleware
**When to use:** Every response needs the same headers

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'unsafe-inline'; "
        "style-src 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

### Pattern 3: Exception Handlers
**What:** Replace try/except in do_GET with FastAPI exception handlers
**When to use:** Global error handling for all routes

```python
from fastapi import HTTPException
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": "Invalid request parameters"})

@app.exception_handler(OSError)
async def network_error_handler(request: Request, exc: OSError):
    return JSONResponse(status_code=502, content={"error": "Upstream data source unavailable"})

@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    log.exception("Unexpected error")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
```

### Pattern 4: Demo Mode via Dependency
**What:** Extract demo mode detection into a reusable dependency
**When to use:** Multiple routes need the same demo/live toggle

```python
def get_demo_mode(demo: str = "0") -> bool:
    if not os.getenv("ODDS_API_KEY", ""):
        return True
    return demo in {"1", "true", "yes"}
```

### Pattern 5: Query Parameter Handling
**What:** Replace manual `parse_qs` with FastAPI query parameters
**When to use:** All routes with query params

```python
# Old: params = parse_qs(parsed.query); region = params.get("region", ["ca"])[0]
# New: FastAPI declares params directly in function signature
@api_router.get("/dashboard")
def api_dashboard(
    region: str = "qc",
    bankroll: float = 1000.0,
    min_edge: float = 2.0,
    min_ev: float = 0.02,
    demo: str = "0",
):
    ...
```

### Anti-Patterns to Avoid
- **Don't use `async def` with sync blocking calls:** The agent pipeline uses `requests` (blocking). Use `def` (sync), not `async def`. FastAPI runs sync handlers in a thread pool automatically.
- **Don't over-decompose templates:** CONTEXT.md says single `base.html`. Don't create component templates -- that is Phase 7.
- **Don't add new routes:** This is a migration, not a feature addition. Preserve exact same 5 routes.
- **Don't change JSON response formats:** Existing consumers (dashboard JS) depend on the exact response shapes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query param parsing | Manual `parse_qs` + type conversion | FastAPI function parameters with type hints | Auto-validation, type coercion, error responses |
| JSON serialization | `json.dumps().encode()` + content-type header | Return dict from endpoint (FastAPI auto-serializes) | Less boilerplate, consistent content-type |
| Error responses | try/except per route | `@app.exception_handler()` decorators | DRY, consistent error format across all routes |
| Security headers | Per-response header setting | `@app.middleware("http")` | Applied once, covers all routes including errors |
| Template rendering | f-string HTML generation | `Jinja2Templates` + `TemplateResponse` | Proper escaping, template inheritance ready for Phase 7 |
| Test HTTP client | Manual HTTP requests to running server | `TestClient(app)` | No server needed, direct ASGI communication |

**Key insight:** FastAPI eliminates ~200 lines of boilerplate (response building, header setting, param parsing, error handling) that currently lives in `PreviewHandler`.

## Common Pitfalls

### Pitfall 1: Async/Sync Confusion
**What goes wrong:** Using `async def` for endpoints that call blocking code (e.g., `requests.get()`) blocks the event loop.
**Why it happens:** Developers assume async is always better.
**How to avoid:** Use plain `def` for all endpoints. FastAPI runs sync endpoints in a thread pool automatically. The entire agent pipeline uses `requests` (sync).
**Warning signs:** Dashboard hangs under concurrent requests.

### Pitfall 2: Template Path Resolution
**What goes wrong:** Templates not found in production because path is relative to CWD.
**Why it happens:** `Jinja2Templates(directory="templates")` is relative.
**How to avoid:** Use `Path(__file__).parent / "templates"` for absolute path resolution.
**Warning signs:** `TemplateNotFound` error in production but works locally.

### Pitfall 3: Jinja2 Double-Brace Escaping
**What goes wrong:** The existing f-string HTML uses `{{` and `}}` to escape Python f-string braces. Jinja2 uses `{{ }}` for variable interpolation.
**Why it happens:** f-string and Jinja2 have opposite escaping conventions.
**How to avoid:** When converting `presentation.py`:
  - f-string `{{` (escaped literal brace) becomes `{` in Jinja2
  - f-string `{variable}` becomes `{{ variable }}` in Jinja2
  - JavaScript template literals with `${...}` stay as-is (Jinja2 doesn't interpret `${}`)
  - CSS with `{` stays as-is (Jinja2 only interprets `{{ }}` and `{% %}`)
**Warning signs:** Broken CSS/JS in the rendered page.

### Pitfall 4: PORT Environment Variable
**What goes wrong:** Uvicorn doesn't pick up Railway's `$PORT` env var.
**Why it happens:** Uvicorn's `--port` flag needs an explicit value, not a shell variable in Dockerfile CMD.
**How to avoid:** Use shell form in Dockerfile CMD or handle PORT in Python:
```dockerfile
CMD uvicorn app.web.app:app --host 0.0.0.0 --port ${PORT:-8080}
```
Or use exec form with a startup script.
**Warning signs:** App binds to wrong port on Railway.

### Pitfall 5: Dockerfile HEALTHCHECK
**What goes wrong:** Old healthcheck uses `python -c "import urllib.request..."` which still works but should be updated.
**Why it happens:** Forgetting to update the healthcheck command.
**How to avoid:** Update HEALTHCHECK to use `curl` or keep the Python urllib approach (both work since the endpoint is still `/`).

### Pitfall 6: Missing `__init__.py` in templates directory
**What goes wrong:** Not really an error, but `templates/` should NOT have `__init__.py` -- it's not a Python package.
**How to avoid:** Don't add `__init__.py` to `templates/`.

### Pitfall 7: Request Object in TemplateResponse
**What goes wrong:** Forgetting to pass `request` to `TemplateResponse`.
**Why it happens:** JSON endpoints don't need `request`, but template endpoints do.
**How to avoid:** Always include `request: Request` in page route parameters and pass it to `TemplateResponse`.

## Code Examples

### Complete App Structure
```python
# app/web/app.py
# Source: FastAPI official docs + project-specific patterns
import json
import os
from pathlib import Path

from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.logging_config import get_logger, setup_logging
from app.web.presentation import to_serializable

log = get_logger("web")

app = FastAPI(title="MoneyPuck Edge Intelligence")

TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Reuse TTLCache from old code
class TTLCache:
    # ... same implementation ...
    pass

_snapshot_cache = TTLCache(ttl_seconds=90.0)

# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'unsafe-inline'; "
        "style-src 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"error": "Invalid request parameters"})

# API Router
api = APIRouter(prefix="/api")

@api.get("/dashboard")
def api_dashboard(region: str = "qc", demo: str = "0", bankroll: float = 1000.0):
    use_demo = _is_demo(demo)
    params = {"region": [region], "bankroll": [str(bankroll)]}
    data = _build_demo_dashboard(params) if use_demo else _build_live_dashboard(params)
    return data

@api.get("/performance")
def api_performance():
    return _build_performance_data()

@api.get("/opportunities")
def api_opportunities(region: str = "qc", demo: str = "0"):
    # ... same logic ...
    pass

@api.get("/odds-history")
def api_odds_history(game_id: str = ""):
    if not game_id:
        return JSONResponse(status_code=400, content={"error": "game_id parameter required"})
    # ... same logic ...
    pass

app.include_router(api)

# Page route
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def dashboard_page(request: Request, region: str = "qc", demo: str = "0"):
    use_demo = _is_demo(demo)
    params = {"region": [region]}
    data = _build_demo_dashboard(params) if use_demo else _build_live_dashboard(params)
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context={"data": data, "data_json": json.dumps(data).replace("</", r"<\/")}
    )

def _is_demo(demo: str) -> bool:
    if not os.getenv("ODDS_API_KEY", ""):
        return True
    return demo in {"1", "true", "yes"}
```

### TestClient Test Pattern
```python
# tests/web/test_app.py
# Source: FastAPI testing docs
from fastapi.testclient import TestClient
from app.web.app import app

client = TestClient(app)

def test_dashboard_page_returns_html():
    response = client.get("/?demo=1")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_api_dashboard_returns_json():
    response = client.get("/api/dashboard?demo=1")
    assert response.status_code == 200
    data = response.json()
    assert "games" in data
    assert "value_bets" in data

def test_security_headers():
    response = client.get("/?demo=1")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

def test_api_odds_history_requires_game_id():
    response = client.get("/api/odds-history")
    assert response.status_code == 400
```

### Jinja2 Template Conversion
```html
{# app/web/templates/base.html #}
{# Source: converted from presentation.py render_dashboard() f-string #}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>MoneyPuck Edge Intelligence</title>
  {# CSS stays inline -- Phase 7 extracts to Tailwind #}
  <style>
    :root {
      --bg: #0a0e1a;
      {# ... all CSS variables and rules from presentation.py ... #}
    }
  </style>
</head>
<body>
  {# HTML structure from presentation.py #}
  {# JavaScript at bottom, using data_json passed from route #}
  <script>
    const DATA = {{ data_json | safe }};
    {# ... all JS from presentation.py ... #}
  </script>
</body>
</html>
```

### Dockerfile Update
```dockerfile
# Old:
# CMD ["python", "-m", "app.web.web_preview"]

# New:
CMD uvicorn app.web.app:app --host 0.0.0.0 --port ${PORT:-8080}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `BaseHTTPRequestHandler` | FastAPI + Uvicorn | FastAPI stable since 2019 | Proper async, middleware, validation, testing |
| f-string HTML | Jinja2 templates | Always best practice | Separation of concerns, auto-escaping, inheritance |
| `ThreadingHTTPServer` | ASGI (uvicorn) | ASGI standard since 2018 | Better concurrency, graceful shutdown |
| Manual JSON serialization | FastAPI auto-serialization | Built into FastAPI | Return dicts, framework handles content-type |
| `parse_qs` + manual validation | FastAPI query params with type hints | Built into FastAPI | Auto-validation, documentation, type coercion |

**Deprecated/outdated:**
- `http.server` for production: Only appropriate for development/debugging, never production
- `ThreadingHTTPServer`: Works but has no graceful shutdown, no middleware, no request validation

## Open Questions

1. **Dotenv loading in app startup**
   - What we know: `web_preview.py` has `_load_dotenv()` that manually parses `.env`
   - What's unclear: Whether to keep this manual approach or add `python-dotenv` dependency
   - Recommendation: Keep manual `_load_dotenv()` -- it works, adding a dependency for 10 lines of code is unnecessary. Call it in a `@app.on_event("startup")` handler or at module level.

2. **`/index.html` path alias**
   - What we know: Current handler serves both `/` and `/index.html` as the dashboard
   - What's unclear: Whether `/index.html` is actually used anywhere
   - Recommendation: Keep it for backward compatibility. FastAPI supports multiple decorators on one function.

3. **`__main__` entry point**
   - What we know: Current `web_preview.py` has `if __name__ == "__main__"` block and Dockerfile uses `python -m app.web.web_preview`
   - What's unclear: Whether to keep a `__main__.py` entry point alongside uvicorn
   - Recommendation: Add a `__main__.py` in `app/web/` that runs uvicorn programmatically for local dev. Dockerfile uses uvicorn CLI directly.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=9.0 |
| Config file | pyproject.toml or pytest.ini (existing) |
| Quick run command | `pytest tests/web/ -x -q` |
| Full suite command | `pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| R5.1-a | FastAPI app starts and serves `/` | smoke | `pytest tests/web/test_app.py::test_dashboard_page_returns_html -x` | Wave 0 |
| R5.1-b | API endpoints return correct JSON | unit | `pytest tests/web/test_app.py::test_api_dashboard_returns_json -x` | Wave 0 |
| R5.1-c | Security headers on all responses | unit | `pytest tests/web/test_app.py::test_security_headers -x` | Wave 0 |
| R5.1-d | Error handling returns proper status codes | unit | `pytest tests/web/test_app.py::test_error_handling -x` | Wave 0 |
| R5.1-e | Demo mode works without API key | unit | `pytest tests/web/test_app.py::test_demo_mode -x` | Wave 0 |
| R5.2-a | Template renders valid HTML | unit | `pytest tests/web/test_app.py::test_template_renders_html -x` | Wave 0 |
| R5.2-b | Template contains dashboard data | unit | `pytest tests/web/test_app.py::test_template_has_data -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/web/ -x -q`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/web/test_app.py` -- new test file for FastAPI TestClient tests (replaces `test_web_preview.py` patterns)
- [ ] `httpx` -- already bundled with fastapi, no separate install needed
- [ ] Existing `tests/web/test_web_preview.py` and `tests/web/test_presentation.py` need updating to work with new module structure

## Sources

### Primary (HIGH confidence)
- [FastAPI Templates docs](https://fastapi.tiangolo.com/advanced/templates/) - Jinja2Templates setup, TemplateResponse pattern
- [FastAPI TestClient docs](https://fastapi.tiangolo.com/reference/testclient/) - TestClient usage, pytest integration
- [FastAPI Middleware docs](https://fastapi.tiangolo.com/advanced/middleware/) - Security headers middleware pattern
- [FastAPI PyPI](https://pypi.org/project/fastapi/) - Current version >=0.129

### Secondary (MEDIUM confidence)
- [Real Python FastAPI Jinja2](https://realpython.com/fastapi-jinja2-template/) - Template integration patterns
- [Better Stack FastAPI Error Handling](https://betterstack.com/community/guides/scaling-python/error-handling-fastapi/) - Exception handler patterns
- [Essential FastAPI Middlewares](https://davidmuraya.com/blog/adding-middleware-to-fastapi-applications/) - Middleware ordering and security

### Tertiary (LOW confidence)
- None -- all findings verified against official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - FastAPI/Uvicorn/Jinja2 is the de facto Python web stack, well-documented
- Architecture: HIGH - Direct mapping from existing routes to FastAPI decorators, minimal design decisions
- Pitfalls: HIGH - Common issues (async/sync confusion, template paths, f-string-to-Jinja2 escaping) well-documented
- Testing: HIGH - FastAPI TestClient is mature and straightforward

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable ecosystem, 30-day validity)
