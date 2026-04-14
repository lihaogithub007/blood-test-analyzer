# Blood Test Analyzer Reorg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve maintainability and reliability by reorganizing frontend assets, clarifying backend boundaries/config, adding minimal tests, and documenting verification steps without changing core behavior.

**Architecture:** Keep FastAPI + SQLite + single-page UI, but split the large HTML file into dedicated CSS/JS assets, isolate configuration/logging in backend, and add a thin test layer for the most fragile parsing/normalization logic.

**Tech Stack:** FastAPI, uvicorn, sqlite3, PyMuPDF, httpx, vanilla HTML/JS, ECharts, pytest (dev-only).

---

## Current state map (files & responsibilities)

- `app.py`: FastAPI app + routes + static mount
- `database.py`: SQLite schema + CRUD + name normalization + chart aggregation
- `pdf_processor.py`: PDF→images + LLM call + JSON extraction/repair
- `static/index.html`: UI + CSS + all JS logic (charts/tables/modals/tabs)
- `.cursor/hooks/*`: dev automation (auto restart)

## Gaps / shortcomings (what to fix)

### Maintainability
- `static/index.html` is a monolith: hard to review, hard to diff, easy to break.
- Backend config/logging are partially global side-effects (`basicConfig`, file handlers).

### Reliability
- Parsing logic (`extract_json_from_text`, `fix_json`, `normalize_item_name`) has no tests.
- Frontend has no build/lint safety net (acceptable for vanilla, but tests help).

### Security / hygiene
- Need guardrails to avoid committing secrets and accidental logs growth.
- Prefer consistent env var names & clear startup errors.

## Plan tasks

### Task 1: Add project docs plan + verification checklist

**Files:**
- Create: `docs/superpowers/plans/2026-04-13-project-reorg.md`

- [x] **Step 1: Save this plan file**

### Task 2: Frontend asset split (no behavior change)

**Files:**
- Create: `static/styles.css`
- Create: `static/app.js`
- Modify: `static/index.html`

- [ ] **Step 1: Move all CSS from `<style>` to `static/styles.css`**
- [ ] **Step 2: Replace inline `<style>` with `<link rel="stylesheet" href="/static/styles.css">`**
- [ ] **Step 3: Move all JS from `<script>` to `static/app.js`**
- [ ] **Step 4: Replace inline `<script>` with `<script src="/static/app.js" defer></script>`**
- [ ] **Step 5: Manual smoke check**
  - Run: `python -m uvicorn app:app --reload --port 8000`
  - Open: `http://127.0.0.1:8000`
  - Verify: tabs switch, charts render, upload still triggers file picker

### Task 3: Backend configuration cleanup (no behavior change)

**Files:**
- Create: `settings.py` (or `config.py`) with env var reading
- Modify: `app.py`, `pdf_processor.py`

- [ ] **Step 1: Centralize env lookup and error messages**
- [ ] **Step 2: Make logging setup idempotent and avoid duplicated handlers**
- [ ] **Step 3: Verify endpoints still work**
  - Run: `python -c "import app; print('import ok')"`

### Task 4: Minimal tests for fragile logic (dev-only)

**Files:**
- Create: `tests/test_database_normalize_item_name.py`
- Create: `tests/test_pdf_processor_json_extract.py`
- Create: `requirements-dev.txt` (include `pytest`)

- [ ] **Step 1: Add tests for `normalize_item_name` mapping stability**
- [ ] **Step 2: Add tests for JSON extraction/repair (`extract_json_from_text`, `fix_json`)**
- [ ] **Step 3: Run tests**
  - Run: `python -m pip install -r requirements-dev.txt`
  - Run: `pytest -q`

### Task 5: Final verification

- [ ] **Step 1: Restart server and verify HTTP 200**
  - Run: `python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/').getcode())"`
- [ ] **Step 2: Confirm no secrets are introduced**
  - Ensure `.env` remains ignored

