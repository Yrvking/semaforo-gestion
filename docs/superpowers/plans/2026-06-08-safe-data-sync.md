# Safe Data Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish Evolta data only as a complete validated four-report set and add DOMINGO ORUE throughout the dashboard.

**Architecture:** Introduce a focused report pipeline module for report definitions, validation, manifests, backups and atomic publication. Keep Selenium responsible only for authenticated report downloads, then let FastAPI orchestrate staging, validation and publication before reloading the existing processor.

**Tech Stack:** Python 3.11, FastAPI, Selenium, pandas/openpyxl, unittest, React 19, Vite.

---

### Task 1: Project And Report Contracts

**Files:**
- Create: `backend/report_pipeline.py`
- Create: `backend/tests/test_report_pipeline.py`
- Modify: `backend/processor.py`
- Modify: `frontend/src/components/SemaforoExcel.jsx`

- [ ] Write failing tests asserting five target projects and four required report definitions.
- [ ] Run `python -m unittest discover -s backend/tests -v` and confirm the contract tests fail.
- [ ] Add centralized target projects and report definitions, including DOMINGO ORUE.
- [ ] Run the tests and confirm the contract tests pass.

### Task 2: Dataset Validation

**Files:**
- Modify: `backend/report_pipeline.py`
- Modify: `backend/tests/test_report_pipeline.py`

- [ ] Write failing tests for missing files, missing columns, empty reports and out-of-period primary dates.
- [ ] Run the focused tests and confirm each failure is caused by missing validation behavior.
- [ ] Implement structured validation returning file path, row count, size and date range per report.
- [ ] Run the full backend test suite and confirm it passes.

### Task 3: Backup And Atomic Publication

**Files:**
- Modify: `backend/report_pipeline.py`
- Modify: `backend/tests/test_report_pipeline.py`

- [ ] Write failing tests proving validation failure leaves active files unchanged and successful publication creates a backup and manifest.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement timestamped backup and same-filesystem `os.replace` publication with rollback on replacement failure.
- [ ] Run the full backend test suite and confirm it passes.

### Task 4: Scraper Configuration And Lima Dates

**Files:**
- Modify: `backend/scraper.py`
- Create: `backend/tests/test_scraper_config.py`

- [ ] Write failing tests for the default Lima period and report-specific selection candidate configuration.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement `America/Lima` default dates through yesterday and explicit per-report selector candidates.
- [ ] Run the full backend test suite and confirm it passes.

### Task 5: FastAPI Orchestration

**Files:**
- Modify: `backend/main.py`
- Create: `backend/tests/test_sync_orchestration.py`

- [ ] Write a failing test proving a partial download sets error status and does not publish.
- [ ] Run the focused test and confirm the current implementation incorrectly completes.
- [ ] Implement staging, validation, backup, publication, cleanup and processor reload.
- [ ] Run the full backend test suite and confirm it passes.

### Task 6: Frontend API Contract And Fifth Project

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/components/SemaforoExcel.jsx`
- Modify: `frontend/src/components/SemaforoExcel.css`
- Modify: `frontend/.env.example`

- [ ] Normalize the backend origin once and route metas, reset and report download through the shared API client/helpers.
- [ ] Add DOMINGO ORUE to every project-based view and make five-card layouts responsive.
- [ ] Remove current lint errors in touched frontend code.
- [ ] Run `npm run lint` and `npm run build`.

### Task 7: Operations Documentation

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `DEPLOY_README.md`
- Modify: `detalle de pestañas que se descargan.txt`

- [ ] Document the four-report contract, Lima date range, backups, failure behavior and DOMINGO ORUE.
- [ ] Document `VITE_API_URL` as an origin without `/api`.
- [ ] Run Python compilation, backend tests, frontend lint and frontend build as final verification.

