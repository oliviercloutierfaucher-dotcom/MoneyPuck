---
phase: 6
slug: fastapi-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pytest discovery (no explicit config) |
| **Quick run command** | `python -m pytest tests/web/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/web/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | R5.1 | unit | `pytest tests/web/test_app.py -x` | Wave 0 | pending |
| 06-01-02 | 01 | 1 | R5.2 | unit | `pytest tests/web/test_templates.py -x` | Wave 0 | pending |
| 06-02-01 | 02 | 2 | R5.1 | integration | `pytest tests/web/ -x` | Wave 0 | pending |

---

## Wave 0 Requirements

- [ ] `tests/web/test_app.py` — covers R5.1 (FastAPI routes, JSON responses, status codes)
- [ ] `tests/web/test_templates.py` — covers R5.2 (Jinja2 template rendering)
- [ ] Tests must use FastAPI TestClient (no live server needed)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard visual rendering | R5.2 | Visual verification needed | Start server with `python -m app.web.app` and check dashboard renders correctly |
| Railway deployment | R5.1 | Requires Railway environment | Deploy to Railway and verify `uvicorn` serves correctly with PORT env var |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
