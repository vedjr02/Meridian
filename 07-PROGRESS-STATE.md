# 07 — Progress State

> Update this file at the end of every session, without exception. This is the only memory
> a new session has of everything that came before it. Be specific — "working on Module A"
> is useless; "implemented dependency measure function in miner.py, next step is loop
> handling for length-two loops, see TODO comment at line 84" is useful.

## Current phase

`Week 1, Day 3 — done. Next: Week 1, Day 4 — Heuristic Miner core (footprint matrix, dependency measure).`

Active branch: `module-a-discovery` (pushed, HEAD at end of session 2). `origin/main` already
contains Day 1 via PR #1, merged by Ved on GitHub; local `main` has not been fast-forwarded (not
needed for branch work — never commit to `main` directly).

## Day 1 checklist (session 1)

- [x] Repo initialised, planning docs on `main`, structure `backend/ frontend/ data/ tests/`
- [x] Python 3.12.13 venv at `.venv`; system `python3` is 3.9 — do not use it
- [x] FastAPI app factory + `GET /health`; pytest configured
- [x] Central config `backend/meridian/config.py`; BPI 2017 downloader with pinned SHA-256
- [x] Next.js 16.3.5 frontend shell with design tokens; WCAG contrast test
- [x] pre-commit hook (ruff, eslint, pytest)
- [ ] **Deferred**: Claude Code post-edit test hook (06-AUDIT-PROTOCOL). Check current syntax at
      code.claude.com/docs/en/hooks before writing `.claude/settings.json`.

## Day 2 checklist (session 2)

- [x] PostgreSQL 18.6 installed via Homebrew, running as a brew service; databases `meridian` and `meridian_test`
- [x] Streaming XES parser + independent byte-level event count — `backend/meridian/ingestion/xes.py`
- [x] Normalization with per-reason exclusion accounting — `backend/meridian/ingestion/normalize.py`
- [x] Before/after row-count tests — `tests/test_xes.py`, `tests/test_ingestion_pipeline.py`
- [x] PostgreSQL storage (atomic TRUNCATE + COPY, `ingestion_run` audit table) — `backend/meridian/ingestion/store.py`
- [x] CLI `python -m meridian.ingestion [--no-db]` — `backend/meridian/ingestion/pipeline.py`
- [x] Real run loaded into `meridian`: ingestion run id 1
- [x] Day 2 checkpoint logged in `AUDIT-LOG.md` (60 tests, all green)

## Day 3 checklist (session 2)

- [x] Typed CSV reader for the normalized log — `backend/meridian/ingestion/io.py` (`read_event_log_csv`)
- [x] DFG computation — `backend/meridian/discovery/dfg.py` (`build_dfg` → `DirectlyFollowsGraph`: edges with frequency, case_frequency, mean and median duration; start/end activities; activity counts; `frequency(a, b)` lookup for the miner)
- [x] Hand-computed synthetic-log tests — `tests/test_dfg.py`
- [x] Command `python -m meridian.discovery.dfg [--top N]` → `data/processed/dfg_edges.csv`
- [x] Real-log invariants (integration) — `tests/test_dfg_cli.py`
- [x] Day 3 checkpoint logged in `AUDIT-LOG.md` (74 tests, all green)

## Real-data facts established (BPI 2017, measured session 2)

- 31,509 cases, 1,202,267 events, 26 activities, 149 resources. Every event has case id, activity,
  timestamp (all UTC `Z`), resource and lifecycle transition. 0 malformed, 0 out-of-order, 0 nested attributes.
- Lifecycle: complete 475,306 · suspend 215,402 · schedule 149,104 · start 128,227 · resume 127,160 · ate_abort 85,224 · withdraw 21,844.
- `complete`-only normalized log (current default): 475,306 events, 31,509 cases, 24 activities, 144 resources.
- Outcomes: pending 17,228 · cancelled 10,431 · denied 3,752 · no terminal state 98. No case reaches two different terminal states.
- Full ingestion takes ~16 s (parse ~11 s).
- DFG (`complete`-only log): 443,797 transitions, 159 distinct edges, built in 0.7 s. All 31,509 cases start with `A_Create Application`. Top edge `O_Create Offer -> O_Created` (42,995). Early bottleneck signal for Module B: `A_Complete -> A_Validating` median 7.2 d, mean 8.9 d.
- The raw XES is one line with no newlines — never grep or line-read it.

## Status by module

| Module | Status | Notes |
|---|---|---|
| A — Process Discovery | Days 1–3 done (infra, ingestion, DFG) | Day 4 next: heuristic miner core |
| B — Conformance & Diagnosis | Not started | Will need start/end pairing from `raw_events.csv` for processing vs. waiting time |
| C — Automation Scoring | Not started | |
| D — Business Case & ROI | Not started | |
| E — Organizational Network | Not started | Resource data is complete. 5 resources (User_145–149) exist only in non-`complete` transitions |
| F — What-If Simulation | Not started | |
| G — NL Query Layer | Not started (lowest priority) | |

## Last session summary

**2026-09-13 (session 2)** — Completed Day 2 (ingestion) and Day 3 (DFG). All commits authored
by Vedjr02 with no AI co-author trailers (see `05-GIT-WORKFLOW.md`).

Exact stopping point: Day 3 checkpoint passed and logged; working tree clean on
`module-a-discovery`, pushed. Nothing mid-change.

**Start Day 4 here:**
1. Check `08-OPEN-QUESTIONS.md`: the lifecycle question is still **open** (Claude recommends
   option B). It does not block Day 4.
2. Day 4 = Heuristic Miner core, hand-implemented (02-TECH-STACK-AND-SKILLS.md §1). Suggested
   home: `backend/meridian/discovery/heuristic_miner.py`. Take |A>B| from
   `DirectlyFollowsGraph.frequency(a, b)` — do not recount transitions.
3. Dependency measure `(|A>B| - |B>A|) / (|A>B| + |B>A| + 1)`; classify pairs as causal /
   parallel / unrelated; threshold configurable. Unit-test specific classifications on the Day 3
   synthetic log (`tests/test_dfg.py::LOG`) plus any purpose-built logs.

## Scope decisions

- 2026-09-13 — Dataset: BPI Challenge 2017 (not 2012), chosen by Ved; larger resource population helps Module E.
- 2026-09-13 — Build plan said "clone the existing repo"; the remote was empty, so the repo was initialised locally instead (Ved approved).
- 2026-09-13 — Added a checksum-pinned downloader (beyond "a script that downloads it") so every run starts from byte-identical input — supports reproducibility, no scope expansion.
- 2026-09-13 — Next.js-generated `frontend/AGENTS.md` / `frontend/CLAUDE.md` are gitignored (tool hint files, not project code).
- 2026-09-13 — **Normalized schema gains `event_index`** (position of the event in its source trace). Reason: SQL tables are unordered and timestamps cannot order ties, so without it event order — and so DFG counts — would not be reproducible from the database.
- 2026-09-13 — Ingestion also writes `data/processed/raw_events.csv` (all lifecycle transitions) so the open lifecycle decision is a re-run, not a re-parse, and Module B/F can pair start/end transitions.
- 2026-09-13 — Optional `outcome` column filled from each case's last terminal application state (A_Pending/A_Denied/A_Cancelled → pending/denied/cancelled; NULL for 98 open cases). `cost` stays NULL: BPI 2017 has no per-event cost.
- 2026-09-13 — Added `psycopg[binary]` (the driver for the PostgreSQL already in the tech stack) and an `ingestion_run` audit table (tech stack: Postgres stores "past decision/audit runs").
- 2026-09-13 — Pre-commit runs every test except `integration` (real-data, ~16 s); integration tests run at each checkpoint.
- 2026-09-13 — DFG edges report `case_frequency` and median duration beside the required frequency and mean. Reason: median guards against skew (03-UIUX rule 1) and case frequency exposes rework; both are one aggregation each. Full distributions stay in Module B.

## Known issues / technical debt

- **Open decision**: lifecycle transitions kept in the normalized log (08-OPEN-QUESTIONS.md). Default `complete` distorts W_ workflow activities; switch via `MERIDIAN_LIFECYCLE_TRANSITIONS` or code change once decided, then update the pinned counts in `tests/test_ingestion_pipeline.py`.
- Out-of-order detection flags events earlier than the running maximum in their case. One bogus far-future timestamp would flag every later event in that case. Real log has 0, so not addressed; revisit if a future dataset shows clusters of out-of-order exclusions.
- `count_raw_events` would count an `<event` inside an XML comment (documented limitation; XES writers don't emit them).
- Homebrew is at `/opt/homebrew/bin/brew` and is not on PATH in non-login shells; Postgres binaries are at `/opt/homebrew/opt/postgresql@18/bin`.
- `pytest` emits two upstream deprecation warnings from Starlette's TestClient (httpx / anyio aliases). Harmless now.
- Dependencies use lower-bound pins; no lock file yet. Consider one before the README 10-minute setup test (Day 28).

## Real pace vs. planned pace

Days 1 and 2 both completed on 2026-09-13, across two sessions. Too early to judge the 3–4
hours/day assumption.
