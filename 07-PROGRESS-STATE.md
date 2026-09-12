# 07 — Progress State

> Update this file at the end of every session, without exception. This is the only memory
> a new session has of everything that came before it. Be specific — "working on Module A"
> is useless; "implemented dependency measure function in miner.py, next step is loop
> handling for length-two loops, see TODO comment at line 84" is useful.

## Current phase

`Week 1, Day 1 — done (one sub-item deferred, see below). Next: Week 1, Day 2 — data ingestion.`

Active branch: `module-a-discovery` (pushed). `main` holds only the planning-docs commit.

## Day 1 checklist

- [x] Repo initialised locally (remote was empty, so no clone), planning docs committed to `main`, pushed
- [x] Structure: `backend/meridian/` (Python package), `frontend/` (Next.js), `data/raw` + `data/processed` (gitignored contents), `tests/`
- [x] Python 3.12.13 venv at `.venv` (`pip install -e ".[dev]"`); system `python3` is 3.9 — do not use it
- [x] FastAPI app factory + `GET /health` in `backend/meridian/api/main.py`
- [x] pytest configured in `pyproject.toml` — 25 tests passing
- [x] Central config `backend/meridian/config.py` (paths + dataset source; `MERIDIAN_DATA_DIR` override)
- [x] BPI Challenge 2017 downloaded to `data/raw/BPI Challenge 2017.xes.gz` via `python -m meridian.datasets` (SHA-256 pinned in config)
- [x] Next.js 16.3.5 frontend: design tokens + app shell + empty state (`frontend/src/app/`); `npm run build` passes
- [x] Palette contrast verified by `tests/test_design_tokens.py` (all 16 text pairings ≥ 4.5:1)
- [x] pre-commit hook: ruff check, ruff format, eslint, full pytest — installed and passing
- [x] Day 1 checkpoint logged in `AUDIT-LOG.md`
- [ ] **Deferred**: Claude Code post-edit hook (06-AUDIT-PROTOCOL "recommended enforcement"). Must check current hook syntax at code.claude.com/docs/en/hooks before writing `.claude/settings.json` — not done this session for time.

## Status by module

| Module | Status | Notes |
|---|---|---|
| A — Process Discovery | Day 1 (infra) done | Ingestion starts Day 2 |
| B — Conformance & Diagnosis | Not started | |
| C — Automation Scoring | Not started | |
| D — Business Case & ROI | Not started | |
| E — Organizational Network | Not started | XES declares `org:resource` as a global event attribute; completeness per event still to be measured on Day 2 |
| F — What-If Simulation | Not started | |
| G — NL Query Layer | Not started (lowest priority) | |

## Last session summary

**2026-09-13 (session 1)** — Completed Day 1 scaffolding, 14 commits, all authored by Vedjr02
(no AI co-author trailers — Ved must be the sole contributor; see `05-GIT-WORKFLOW.md`).

Exact stopping point: working tree clean on `module-a-discovery`, pushed. Nothing mid-change.

**Start Day 2 here:**
1. Read the two new entries in `08-OPEN-QUESTIONS.md` (Postgres not installed; lifecycle
   transitions vs. single timestamp) — both affect Day 2 design.
2. The raw XES is a **single line with no newlines** (~30 MB gzipped). The parser must stream it
   (e.g. `xml.etree.ElementTree.iterparse` over `gzip.open`), never read/grep it line by line.
3. Write the XES → normalized schema converter as a new module (suggested:
   `backend/meridian/ingestion/`), with the before/after row-count test from
   `02-TECH-STACK-AND-SKILLS.md`, and a count-and-reason log of excluded malformed rows.

## Scope decisions

- 2026-09-13 — Dataset: BPI Challenge 2017 (not 2012), chosen by Ved; larger resource population helps Module E.
- 2026-09-13 — Build plan said "clone the existing repo"; the remote was empty, so the repo was initialised locally instead (Ved approved).
- 2026-09-13 — Added a checksum-pinned downloader (beyond "a script that downloads it") so every run starts from byte-identical input — supports the reproducibility requirement, no scope expansion.
- 2026-09-13 — Next.js-generated `frontend/AGENTS.md` / `frontend/CLAUDE.md` are gitignored (tool hint files, not project code).

## Known issues / technical debt

- `pytest` emits two upstream deprecation warnings from Starlette's TestClient (httpx / anyio aliases). Harmless now; revisit if Starlette drops httpx support.
- Dependencies use lower-bound pins in `pyproject.toml`; no lock file yet. Consider `pip freeze > requirements.lock` before the README 10-minute setup test (Day 28).
- `README.md` is a Day 1 quickstart only; full instructions are a Day 28 task.

## Real pace vs. planned pace

*(Session 1: Day 1 completed in one short session. Too early to judge pace.)*
