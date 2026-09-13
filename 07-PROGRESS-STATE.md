# 07 — Progress State

> Update this file at the end of every session, without exception. This is the only memory
> a new session has of everything that came before it. Be specific — "working on Module A"
> is useless; "implemented dependency measure function in miner.py, next step is loop
> handling for length-two loops, see TODO comment at line 84" is useful.

## Current phase

`Week 1, Day 6 — done; Module A acceptance criteria (a)–(d) met by `python -m meridian.discovery`. Next: Week 1, Day 7 — frontend for Module A, then the pre-Week-2 checkpoint and merge.`

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

## Day 4 checklist (session 2)

- [x] Configurable dependency threshold — `DEFAULT_DEPENDENCY_THRESHOLD = 0.9` + `validate_dependency_threshold` in `backend/meridian/config.py`; env `MERIDIAN_DEPENDENCY_THRESHOLD`
- [x] `backend/meridian/discovery/heuristic_miner.py`: `dependency_measure`, `classify_pair` → `Relation` (`->`, `<-`, `||`, `#`, `~`), `dependency_matrix`, `footprint_matrix`, `causal_edges`
- [x] Tests with hand-computed expectations — `tests/test_heuristic_miner.py` (purpose-built `VARIANTS` log + the Day 3 log)
- [x] Day 4 checkpoint logged in `AUDIT-LOG.md` (106 tests, all green)

## Day 5 checklist (session 2)

- [x] Loop measures in `heuristic_miner.py`: `length_one_loop_measure`, `length_two_loop_measure`, `count_length_two_patterns` (A,B,A from ordered events) — `tests/test_heuristic_loops.py`
- [x] Full model: `mine_heuristic_net(event_log, threshold, connect_all=True)` → `HeuristicNet` (activities, start/end activities, edges with `kind` ∈ causal / length_one_loop / length_two_loop / best_connection, `orphan_activities`, `to_dict`) — `tests/test_heuristic_net.py`
- [x] Command `python -m meridian.discovery.heuristic_miner [--threshold T] [--no-connect-all]` → `data/processed/heuristic_net.json`
- [x] End-to-end real-data plausibility test (raw XES → ingestion → DFG → model) — `tests/test_module_a_pipeline.py`
- [x] Day 5 checkpoint logged in `AUDIT-LOG.md` (130 tests, all green)

## Day 6 checklist (session 2)

- [x] Variant analysis — `backend/meridian/discovery/variants.py` (`analyze_variants` → `VariantAnalysis.variants`, `.case_variants`, `.variants_to_cover(share)`) — `tests/test_variants.py`
- [x] Per-case statistics and distributions — `backend/meridian/discovery/cycle_time.py` (`case_statistics`, `summarize_distribution` → count/mean/min/p50/p90/p99/max) — `tests/test_cycle_time.py`
- [x] Mermaid DFG rendering — `backend/meridian/discovery/visualize.py` (`dfg_to_mermaid`, top 40 edges with coverage caption) — `tests/test_visualize.py`
- [x] Deterministic written summary — `backend/meridian/discovery/summary.py` (`render_summary`) — `tests/test_summary.py`
- [x] Single command `python -m meridian.discovery [--reingest] [--no-db]` — `backend/meridian/discovery/pipeline.py` — `tests/test_discovery_pipeline.py` (incl. real-log acceptance test)
- [x] Outputs generated on the real log in `data/processed/` (`dfg.mmd`, `dfg_edges.csv`, `heuristic_net.json`, `variants.csv`, `case_statistics.csv`, `discovery_summary.md`)
- [x] Day 6 checkpoint logged in `AUDIT-LOG.md` (167 tests, all green)

## Real-data facts established (BPI 2017, measured session 2)

- 31,509 cases, 1,202,267 events, 26 activities, 149 resources. Every event has case id, activity,
  timestamp (all UTC `Z`), resource and lifecycle transition. 0 malformed, 0 out-of-order, 0 nested attributes.
- Lifecycle: complete 475,306 · suspend 215,402 · schedule 149,104 · start 128,227 · resume 127,160 · ate_abort 85,224 · withdraw 21,844.
- `complete`-only normalized log (current default): 475,306 events, 31,509 cases, 24 activities, 144 resources.
- Outcomes: pending 17,228 · cancelled 10,431 · denied 3,752 · no terminal state 98. No case reaches two different terminal states.
- Full ingestion takes ~16 s (parse ~11 s).
- Variants (`complete`-only log): 5,623 distinct for 31,509 cases; 610 cover 80% of cases; top variant 7.0% of cases; 4,150 single-case variants. **Top 3 variants (5,704 cases) all end cancelled** (see 08-OPEN-QUESTIONS.md). Most common variant among `pending` cases is rank 4 (969 cases).
- Cycle time (`complete`-only log): p50 19.1 d, p90 35.0 d, p99 59.1 d, mean 21.8 d, max 169.1 d. Most common variant p50 31.7 d against 17.9 d for all others.
- Heuristic net (threshold 0.9, `complete`-only log): 98 edges — 83 causal, 5 length-one loops, 10 length-two-loop edges, 0 best connections; no orphans; mined in 0.3 s. `O_Create Offer ⇄ O_Created` is a length-two loop (multiple offers). Largest rework loop: `A_Incomplete ⇄ A_Validating` (12,282 / 4,427 transitions) — a Module B lead.
- DFG (`complete`-only log): 443,797 transitions, 159 distinct edges, built in 0.7 s. All 31,509 cases start with `A_Create Application`. Top edge `O_Create Offer -> O_Created` (42,995). Early bottleneck signal for Module B: `A_Complete -> A_Validating` median 7.2 d, mean 8.9 d.
- The raw XES is one line with no newlines — never grep or line-read it.

## Status by module

| Module | Status | Notes |
|---|---|---|
| A — Process Discovery | Days 1–6 done; acceptance (a)–(d) met by `python -m meridian.discovery` | Day 7 next: frontend view, checkpoint, merge |
| B — Conformance & Diagnosis | Not started | Will need start/end pairing from `raw_events.csv` for processing vs. waiting time |
| C — Automation Scoring | Not started | |
| D — Business Case & ROI | Not started | |
| E — Organizational Network | Not started | Resource data is complete. 5 resources (User_145–149) exist only in non-`complete` transitions |
| F — What-If Simulation | Not started | |
| G — NL Query Layer | Not started (lowest priority) | |

## Last session summary

**2026-09-13 (session 2)** — Completed Days 2–6: ingestion, DFG, heuristic miner (core, loops,
full model), variants, cycle times, written summary and the single Module A command, with a
checkpoint after each day. All commits authored by Vedjr02 with no AI co-author trailers (see
`05-GIT-WORKFLOW.md`).

Exact stopping point: Day 6 checkpoint passed and logged; working tree clean on
`module-a-discovery`, pushed. Nothing mid-change.

**Start Day 7 here:**
1. `08-OPEN-QUESTIONS.md` has **two open questions for Ved**: lifecycle transitions (all real
   numbers depend on it) and the most common variant being a cancellation path (blocks Module B's
   reference model, Day 8). Neither blocks the Day 7 frontend code.
2. Day 7 = frontend for Module A (03-UIUX-RULES.md §3): the mined process graph as the hero
   element (large, pannable/zoomable, edge thickness = frequency), the variant table **beside**
   it rather than below, and a cycle-time **distribution** chart (histogram or box plot, never a
   bare mean). Also the designed loading, empty and error states (§4).
3. The backend needs read-only FastAPI endpoints serving `heuristic_net.json`, `variants.csv`
   and `case_statistics.csv` from `settings.processed_dir`; test them like `/health`.
4. Library check before installing anything: 02-TECH-STACK lists Recharts or Plotly (charts) and
   react-force-graph or d3-force (graphs). A layered process-map layout library (dagre, elkjs) is
   **not** listed; either lay out the graph by hand or log a question first (CLAUDE.md §2).
5. Then the pre-Week-2 checkpoint, and merge `module-a-discovery` into `main` via a PR only after
   the full suite passes (05-GIT-WORKFLOW.md).

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
- 2026-09-13 — Command-line DFG visualization is Mermaid (`dfg.mmd`, top 40 edges with a coverage caption), embedded in the summary. Reason: renders on GitHub and in editors with no new dependency, and Mermaid is already accepted for Module C. The interactive map remains the Day 7 frontend's job.
- 2026-09-13 — The single Module A command (`python -m meridian.discovery`) was built on Day 6 rather than left to Day 7, because it is what satisfies the acceptance criterion; it ingests automatically when no normalized log exists.
- 2026-09-13 — The written summary adds each top variant's outcome mix and the most common variant within each outcome. Reason: the rank-1 "happy path" variant ends cancelled 100% of the time on BPI 2017, and presenting it unqualified would mislead.
- 2026-09-13 — Mined model includes the HeuristicsMiner "all activities connected" heuristic (edge kind `best_connection`, on by default, `--no-connect-all` to disable). Reason: a global threshold can leave a rare activity disconnected, and Day 5's plausibility check requires no orphan nodes; the separate kind keeps these edges distinguishable from threshold-backed ones. On BPI 2017 at 0.9 it adds 0 edges.
- 2026-09-13 — One threshold governs the causal, length-one-loop and length-two-loop measures (the literature allows separate ones). Reason: one setting explains the model's strictness; revisit if real-data tuning shows loops need a different bar.
- 2026-09-13 — Footprint relations add `INFREQUENT` (`~`) beside the spec's causal / parallel / unrelated. Reason: with a dependency threshold, a pair seen in one direction only but below the threshold fits none of the three (not causal, not parallel, not "never follow"); forcing it into one would either admit noise or misstate the log.
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
