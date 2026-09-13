# 07 — Progress State

> Update this file at the end of every session, without exception. This is the only memory
> a new session has of everything that came before it. Be specific — "working on Module A"
> is useless; "implemented dependency measure function in miner.py, next step is loop
> handling for length-two loops, see TODO comment at line 84" is useful.

## Current phase

`Week 2, Day 13 — done, and Ved's lifecycle and reference decisions are applied; Module B outputs are published in data/processed/. Next: Week 2, Day 14 — Module B API + frontend, then the pre-Week-3 checkpoint and PR.`

Active branch: `module-b-conformance`, created from `main` after Ved merged PR #3 (all of Module A
is in `main`). Pushed. Never commit to `main` directly.

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

## Day 7 checklist (sessions 2–3)

- [x] Hand-written layered layout — `backend/meridian/discovery/layout.py` (`layered_layout`, `count_crossings`) — `tests/test_layout.py`
- [x] Read-only API — `backend/meridian/api/discovery.py`: `GET /api/discovery/overview`, `/process-map`, `/variants?limit=N`, `/cycle-time/histogram`; structured 404 `discovery_outputs_missing` — `tests/test_api_discovery.py`
- [x] Frontend `/discovery` (home redirects there): `frontend/src/app/discovery/{page,loading}.tsx`, data layer `frontend/src/lib/discovery.ts` (server-side fetch after `connection()`, base URL `MERIDIAN_API_URL`, default `http://127.0.0.1:8000`), components in `frontend/src/components/discovery/` (`DiscoveryView`, `ProcessMap`, `VariantTable`, `CycleTimeHistogram`), shared `StateMessage`
- [x] Verified in the browser against the real API: map, variant highlighting, histogram, loading/empty/error states (details in `AUDIT-LOG.md`)
- [x] Fixed: NUL bytes that made `ProcessMap.tsx` a binary file in git; unreadable 6 px map labels; table overflow; incomplete missing-file list
- [x] Pre-merge checkpoint logged in `AUDIT-LOG.md` (186 tests, all green, build passes)
- [x] PR `module-a-discovery` → `main` (Ved merged PR #3)

## Day 8 checklist (session 3)

- [x] `VariantAnalysis.sequence(rank)` — exact activity tuples, not just display text (`backend/meridian/discovery/variants.py`)
- [x] Labelled Petri net + `sequence_net(activities)` — `backend/meridian/conformance/petri_net.py` — `tests/test_petri_net.py`
- [x] `select_reference_model(event_log, strategy, outcome=..., documented_activities=...)` → `ReferenceModel` with `description`, `supporting_cases`, `eligible_cases`; strategies `most_frequent_variant`, `most_frequent_variant_for_outcome`, `documented`; **no default strategy** — `backend/meridian/conformance/reference.py` — `tests/test_reference_model.py`
- [x] Day 8 checkpoint logged in `AUDIT-LOG.md` (200 tests, all green)

## Day 9 checklist (session 3)

- [x] `replay_trace(net, trace)` → `ReplayResult` (produced, consumed, missing, remaining, unknown_activities, `fitness`, `fits`) — `backend/meridian/conformance/replay.py`
- [x] Hand-traced tests (perfect, skipped, swapped, repeated, unknown, truncated, very different, empty) plus 500 seeded random traces checking conservation — `tests/test_replay.py`
- [x] Day 9 checkpoint logged in `AUDIT-LOG.md` (211 tests, all green)

## Day 10 checklist (session 3)

- [x] `replay_log(event_log, net)` → `LogReplay` (per-case rows; `fitting_cases`, `deviating_share`, pooled `log_fitness`, `case_fitness_summary()`); each distinct sequence replayed once — `backend/meridian/conformance/replay.py` — `tests/test_replay_log.py`
- [x] Command `python -m meridian.conformance --reference {most_frequent_variant|most_frequent_variant_for_outcome|documented} [--outcome X] [--documented-activity A ...]` → `conformance_cases.csv`, `conformance_summary.json` — `backend/meridian/conformance/pipeline.py` — `tests/test_conformance_pipeline.py`
- [x] Both candidate references replayed on the real log as evidence; results in `08-OPEN-QUESTIONS.md`
- [x] Run the command into `data/processed/` with the chosen reference (done after Ved's decision; see Day 13)
- [x] Day 10 checkpoint logged in `AUDIT-LOG.md` (222 tests, all green)

## Day 11 checklist (session 3)

- [x] `transition_occurrences(event_log)` extracted in `backend/meridian/discovery/dfg.py` (per-occurrence elapsed time, shared with `build_dfg`)
- [x] `analyze_bottlenecks(event_log)` → `BottleneckAnalysis` (per transition: occurrences, cases, total and share of time, mean, Q1/p50/Q3/p90/p99/max, quartile dispersion, `kind`; `most_costly()`, `flagged(kind)`) — `backend/meridian/conformance/bottlenecks.py` — `tests/test_bottlenecks.py` (hand-computed, plus cycle-time reconciliation on synthetic and real data)
- [x] Day 11 checkpoint logged in `AUDIT-LOG.md` (240 tests, all green)
- [x] Bottleneck output file `bottlenecks.csv`, written by the single Module B command (Day 13)

## Day 12 checklist (session 3)

- [x] `analyze_rework(event_log)` → `ReworkAnalysis` (per case: rework events, repeated activities, rework seconds, cycle time, share; per activity: cases, repeats, total/median span; totals `total_rework_seconds`, `rework_time_share`, `rework_case_share`; `rework_time_distribution()`) — `backend/meridian/conformance/rework.py` — `tests/test_rework.py`
- [x] Day 12 checkpoint logged in `AUDIT-LOG.md` (248 tests, all green)

## Day 13 checklist (session 3)

- [x] `render_diagnostic_report(DiagnosticInputs)` — deterministic Markdown answering the three acceptance questions, then conformance, bottleneck and rework evidence and caveats — `backend/meridian/conformance/report.py` — `tests/test_diagnostic_report.py`
- [x] Single Module B command: `python -m meridian.conformance --reference STRATEGY [--outcome X]` → `run_diagnosis` writes `conformance_cases.csv`, `conformance_summary.json`, `bottlenecks.csv`, `rework_cases.csv`, `rework_activities.csv`, `diagnostic_report.md` — `backend/meridian/conformance/pipeline.py`
- [x] Real-log preview rendered in the scratchpad and reviewed (not published)
- [x] Day 13 checkpoint logged in `AUDIT-LOG.md` (256 tests, all green)

## Decisions applied (session 3, after Day 13)

- [x] Ved chose reference **Option A, most frequent variant** and lifecycle **Option 2, start where recorded, otherwise complete**. Both are logged with his reasoning in `08-OPEN-QUESTIONS.md`.
- [x] `LifecyclePolicy` enum (`start_else_complete` default, `complete`, `all`) is in `backend/meridian/ingestion/lifecycle.py`. It is selected by env `MERIDIAN_LIFECYCLE_POLICY` and recorded in `ingestion_report.json`. Summaries, the diagnostic report and `/api/discovery/overview` state the policy that was actually recorded (`recorded_lifecycle_policy`).
- [x] `python -m meridian.conformance` defaults to `--reference most_frequent_variant`. `select_reference_model` itself still requires an explicit strategy. The summary and report add `reference_path_outcomes` (where the cases that follow the reference end).
- [x] Re-ingested (Postgres ingestion run 2, 561,671 rows) and regenerated Module A. Real-data pins in `tests/test_ingestion_pipeline.py` are updated. Module B is published to `data/processed/` (6 files, including `diagnostic_report.md`).
- [x] Checkpoint logged in `AUDIT-LOG.md` (258 tests, all green, build passes).

## Real-data facts established (BPI 2017)

Raw log (measured session 2):
- 31,509 cases, 1,202,267 events, 26 activities, 149 resources. Every event has case id, activity,
  timestamp (all UTC `Z`), resource and lifecycle transition. 0 malformed, 0 out-of-order, 0 nested attributes.
- Lifecycle: complete 475,306 · suspend 215,402 · schedule 149,104 · start 128,227 · resume 127,160 · ate_abort 85,224 · withdraw 21,844.
- W_ activities record 128,227 starts but 41,862 completes. Beside the completes there are 85,224 `ate_abort` and 21,844 `withdraw` events, against 149,104 scheduled. The worst case is `W_Call after offers`: 31,485 starts, 342 completes. This is why `complete`-only was rejected. `W_Personal Loan collection` and `W_Shortened completion` have no completes at all, so they were invisible under `complete`-only (24 activities rather than 26).
- Outcomes: pending 17,228 · cancelled 10,431 · denied 3,752 · no terminal state 98. No case reaches two different terminal states.
- Full ingestion takes ~16–19 s (parse ~11 s).
- The raw XES is one line with no newlines — never grep or line-read it.

**Published analysis: `start_else_complete` log, measured session 3.** The earlier `complete`-only figures are kept in `AUDIT-LOG.md` (Days 2–13).

Log and discovery:
- **Normalized log:** 561,671 events (433,444 A_/O_ completes + 128,227 W_ starts), 31,509 cases, 26 activities, 146 resources. 8 W_ activities are represented by their start events.
- **Variants:** 4,047 distinct; 207 cover 80% of cases; 2,924 single-case variants. The **top variant covers 3,656 cases (11.6%), has 12 activities and ends cancelled in 100% of cases**. Ved decided to report this as a finding.
- **Cycle time:** p50 19.1 d, p90 35.0 d, p99 59.2 d, mean 21.9 d, max 169.1 d. The most common variant has p50 31.8 d, against 17.1 d for all others.
- **DFG:** 530,162 transitions (= events − cases), 166 distinct edges. All cases start with `A_Create Application`. Top edges: `O_Create Offer → O_Created` (42,995) and `W_Validate application → A_Validating` (38,816).
- **Heuristic net (threshold 0.9):** 111 edges: 89 causal, 10 length-one loops (5 O_, 5 W_), 11 length-two-loop edges, 1 best connection. Loops include `O_Create Offer ⇄ O_Created`, `A_Validating ⇄ W_Validate application` and `A_Complete ⇄ W_Call after offers`.

Module B, reference = most frequent variant:
- **Conformance:** 88.4% of cases deviate (27,853 of 31,509). Log fitness 0.562. Case fitness p10 0.368 / p50 0.533 / p90 1.000, mean 0.607. Mean fitness by outcome: cancelled 0.873, no terminal state 0.672, denied 0.514, pending 0.465.
- **Bottlenecks:** the costliest transition is `A_Complete → A_Cancelled`: 218,926 case-days (31.8% of elapsed time), 8,004 occurrences, median 30.7 d, quartiles 30.5–30.8 d, uniformly slow. That looks like a fixed cancellation window (policy rather than capacity). Next is `A_Complete → W_Validate application` at 23.6%, median 7.1 d, uniformly slow. The slow threshold is 23.2 h. Kinds: 7 uniformly slow, 17 slow and variable, 51 high variance, 21 not flagged, 70 insufficient data.
- **Rework:** 16,537 cases (52.5%) repeat an activity. 148,282 case-days (21.5% of cycle time) sit inside loops; per affected case p50 5.2 d, p90 24.0 d. Most repeated: `W_Validate application` (11,839 cases), `A_Validating` (11,669), offer creation (8,559; possibly renegotiation, not errors).

## Status by module

| Module | Status | Notes |
|---|---|---|
| A — Process Discovery | **Complete** (Week 1): command-line acceptance met, frontend `/discovery` built and verified | Awaiting PR for last 4 commits |
| B — Conformance & Diagnosis | Days 8–13 done; command-line acceptance **met on real data** (`data/processed/diagnostic_report.md`) | Next: Day 14 API + frontend, pre-Week-3 checkpoint, PR. Separating processing from waiting time would need start/complete pairing (logged as future work in 08) |
| C — Automation Scoring | Not started | |
| D — Business Case & ROI | Not started | |
| E — Organizational Network | Not started | Resource data is complete: 149 resources raw, 146 in the published log |
| F — What-If Simulation | Not started | |
| G — NL Query Layer | Not started (lowest priority) | |

## Last session summary

**2026-09-13 (session 3)** — Week 1 was merged into `main` (Ved's PR #3). Completed Week 2 Days 8–13
on `module-b-conformance`: Petri net, reference selection, token replay, full-log replay and
aggregates, bottleneck analysis, rework analysis, diagnostic report and the single Module B command,
with a checkpoint after each day. All commits authored by Vedjr02 with no AI co-author trailers.

Ved then decided both open questions: reference = most frequent variant; lifecycle =
`start_else_complete`. Both were applied across ingestion, discovery, conformance, API and frontend.
The log was re-ingested, Module A regenerated, and real-data tests re-pinned. Module B was published
and its checkpoint logged.

Exact stopping point: decisions checkpoint passed and logged; README, AUDIT-LOG and this file
updated; working tree clean on `module-b-conformance`, pushed. Nothing mid-change. `data/processed/`
holds current Module A and Module B outputs (gitignored; regenerate with the two commands in README).

**Start here next session:**
1. `08-OPEN-QUESTIONS.md` has no open questions. It has one future-work entry: full lifecycle and
   duration modelling.
2. Day 14, backend: read-only API endpoints over the Module B outputs, mirroring
   `backend/meridian/api/discovery.py`:
   - serve precomputed files and never recompute;
   - return a structured 404 that names `python -m meridian.conformance`;
   - serve fresh data after a rerun.
   Sources: `conformance_summary.json`, `bottlenecks.csv`, `rework_cases.csv`,
   `rework_activities.csv`.
3. Day 14, frontend: a `/diagnosis` page (03-UIUX-RULES.md §3):
   - start with headline stat cards before any chart ("88.4% of cases deviate", "148,282 case-days
     inside rework loops", costliest transition);
   - then a bottleneck chart showing median and middle half per transition, coloured by kind;
   - then rework findings;
   - state the reference path and that it ends cancelled.
   Also add navigation between `/discovery` and `/diagnosis`.
4. Then the pre-Week-3 checkpoint and a PR from `module-b-conformance` into `main`. Ved opens it,
   because `gh` is not authenticated.
5. To run the frontend: `.venv/bin/uvicorn meridian.api.main:app` and
   `npm --prefix frontend run dev`, then open http://localhost:3000.

## Scope decisions

- 2026-09-13 — **Lifecycle policy `start_else_complete`** (Ved's decision; reasoning in 08).
  - Each activity is represented by its start events if it records any, otherwise by its completes. This is decided per activity from the data, not from a hard-coded W_ list.
  - `LifecyclePolicy` replaces the earlier free-form transition list (`MERIDIAN_LIFECYCLE_TRANSITIONS` → `MERIDIAN_LIFECYCLE_POLICY`) so only coherent choices are possible.
  - Full start/complete pairing (processing vs. waiting time) is future work: every module would need to handle pairs, not just ingestion.
- 2026-09-13 — **Reference model = most frequent variant** (Ved's decision; reasoning in 08). It is the default of `python -m meridian.conformance`, and the other strategies stay available as options. The report and summary add `reference_path_outcomes`, so a reader sees that the modal path ends cancelled rather than having it routed around.
- 2026-09-13 — The lifecycle change was made on `module-b-conformance` rather than a separate branch, because Module B's published numbers depend on it. It touches Module A code already merged to `main`; the Week 2 PR carries the change.
- 2026-09-13 — Dataset: BPI Challenge 2017 (not 2012), chosen by Ved; larger resource population helps Module E.
- 2026-09-13 — Build plan said "clone the existing repo"; the remote was empty, so the repo was initialised locally instead (Ved approved).
- 2026-09-13 — Added a checksum-pinned downloader (beyond "a script that downloads it") so every run starts from byte-identical input — supports reproducibility, no scope expansion.
- 2026-09-13 — Next.js-generated `frontend/AGENTS.md` / `frontend/CLAUDE.md` are gitignored (tool hint files, not project code).
- 2026-09-13 — **Normalized schema gains `event_index`** (position of the event in its source trace). Reason: SQL tables are unordered and timestamps cannot order ties, so without it event order — and so DFG counts — would not be reproducible from the database.
- 2026-09-13 — Ingestion also writes `data/processed/raw_events.csv` (all lifecycle transitions) so the open lifecycle decision is a re-run, not a re-parse, and Module B/F can pair start/end transitions.
- 2026-09-13 — Optional `outcome` column filled from each case's last terminal application state (A_Pending/A_Denied/A_Cancelled → pending/denied/cancelled; NULL for 98 open cases). `cost` stays NULL: BPI 2017 has no per-event cost.
- 2026-09-13 — Added `psycopg[binary]` (the driver for the PostgreSQL already in the tech stack) and an `ingestion_run` audit table (tech stack: Postgres stores "past decision/audit runs").
- 2026-09-13 — Pre-commit runs every test except `integration` (real-data, ~16 s); integration tests run at each checkpoint.
- 2026-09-13 — The single Module B command (`python -m meridian.conformance --reference ...`) runs conformance, bottlenecks and rework and writes the report, rather than separate commands per analysis. Reason: the acceptance criterion is one report answering all three questions, and sharing one read of the log guarantees the analyses describe the same events. The report adds caveats on reference dependence, repeated offers possibly being renegotiation, the rework attribution rule, and waits including processing time.
- 2026-09-13 — Rework time is attributed as the union of each repeated activity's first-to-last span per case. Reason: requirement 4 asks for time "attributable to rework" without defining attribution; this rule is transparent, never double-counts overlapping loops, and is labelled as attribution rather than a counterfactual saving. A per-activity table is added so the Day 13 report can name the loops.
- 2026-09-13 — Bottleneck classification adds `slow_and_variable` (both flags) and `insufficient_data` (under 30 occurrences) beside the required "uniformly slow" and "high variance". Reason: a transition can genuinely be both, and classifying tiny samples would report noise as findings.
- 2026-09-13 — The conformance summary adds mean case fitness per outcome. Reason: it is the evidence that shows whether a reference model is a sensible "intended path" (on BPI 2017 it exposed that the literal most-frequent variant rewards cancellations).
- 2026-09-13 — Token-replay fitness is the standard two-term formula 0.5(1 − m/c) + 0.5(1 − r/p) (Rozinat and van der Aalst 2008), not the single ratio 02-TECH-STACK suggests (the spec asks for a justified choice). Reason: missing and remaining deviations are scored separately so neither dilutes the other, and results match the standard definition. Activities absent from the reference count as one missing plus one remaining token.
- 2026-09-13 — Module B uses a formal labelled Petri net (places, transitions, markings) rather than the simplified "graph with required order" that 02-TECH-STACK also allows. Reason: missing/remaining tokens need places to refer to; restriction: no silent transitions.
- 2026-09-13 — Reference selection offers a third strategy, "most frequent variant for an outcome", beside the two in 01-REQUIREMENTS. Reason: the open question about the cancellation path; it is an option only, and the function has no default until Ved decides.
- 2026-09-13 — Process-map layout is hand-written (breadth-first stages plus barycenter crossing reduction) and computed in the backend. Reason: 02-TECH-STACK lists only force-directed graph libraries, which scatter a left-to-right process map; layered layout libraries (dagre, elkjs) are not in the stack. The map and histogram are hand-drawn SVG, so no chart or graph package was installed even though Recharts and react-force-graph are allowed.
- 2026-09-13 — Frontend reads a new read-only discovery API (`/api/discovery/*`) that serves precomputed outputs rather than recomputing, so the page and the written summary always show the same numbers.
- 2026-09-13 — The process map opens at a legible zoom (fills canvas height from the process start) rather than fit-to-width. Reason: measured 6.2 px labels at fit-to-width on a 1512 px viewport; the whole map is one click away.
- 2026-09-13 — Command-line DFG visualization is Mermaid (`dfg.mmd`, top 40 edges with a coverage caption), embedded in the summary. Reason: renders on GitHub and in editors with no new dependency, and Mermaid is already accepted for Module C. The interactive map remains the Day 7 frontend's job.
- 2026-09-13 — The single Module A command (`python -m meridian.discovery`) was built on Day 6 rather than left to Day 7, because it is what satisfies the acceptance criterion; it ingests automatically when no normalized log exists.
- 2026-09-13 — The written summary adds each top variant's outcome mix and the most common variant within each outcome. Reason: the rank-1 "happy path" variant ends cancelled 100% of the time on BPI 2017, and presenting it unqualified would mislead.
- 2026-09-13 — Mined model includes the HeuristicsMiner "all activities connected" heuristic (edge kind `best_connection`, on by default, `--no-connect-all` to disable). Reason: a global threshold can leave a rare activity disconnected, and Day 5's plausibility check requires no orphan nodes; the separate kind keeps these edges distinguishable from threshold-backed ones. On BPI 2017 at 0.9 it adds 0 edges.
- 2026-09-13 — One threshold governs the causal, length-one-loop and length-two-loop measures (the literature allows separate ones). Reason: one setting explains the model's strictness; revisit if real-data tuning shows loops need a different bar.
- 2026-09-13 — Footprint relations add `INFREQUENT` (`~`) beside the spec's causal / parallel / unrelated. Reason: with a dependency threshold, a pair seen in one direction only but below the threshold fits none of the three (not causal, not parallel, not "never follow"); forcing it into one would either admit noise or misstate the log.
- 2026-09-13 — DFG edges report `case_frequency` and median duration beside the required frequency and mean. Reason: median guards against skew (03-UIUX rule 1) and case frequency exposes rework; both are one aggregation each. Full distributions stay in Module B.

## Known issues / technical debt

- Under `start_else_complete`, a wait into a started activity ends when work begins. A case ending with a started activity also leaves out that activity's own processing time. Both points are stated in every summary and report. Changing the policy means re-ingesting, regenerating both modules, and re-pinning `tests/test_ingestion_pipeline.py`.
- Older scope-decision entries below that describe the reference as undecided, or `complete` as the default, are historical. The two decision entries at the top of the list supersede them.
- Out-of-order detection flags events earlier than the running maximum in their case. One bogus far-future timestamp would flag every later event in that case. Real log has 0, so not addressed; revisit if a future dataset shows clusters of out-of-order exclusions.
- `count_raw_events` would count an `<event` inside an XML comment (documented limitation; XES writers don't emit them).
- Homebrew is at `/opt/homebrew/bin/brew` and is not on PATH in non-login shells; Postgres binaries are at `/opt/homebrew/opt/postgresql@18/bin`.
- `pytest` emits two upstream deprecation warnings from Starlette's TestClient (httpx / anyio aliases). Harmless now.
- Dependencies use lower-bound pins; no lock file yet. Consider one before the README 10-minute setup test (Day 28).
- No automated frontend tests. The frontend is covered by `tsc`, `eslint`, `next build` and manual browser verification. A browser test runner (e.g. Playwright) would be a new dependency, so decide before adding one.
- The process map needs zooming on narrow screens: at "Whole map" on a 1512 px viewport, labels are about 6 px. The default view is legible; a layout that wraps long stages would be the real fix if it matters later.
- Commit-message check: an unpushed commit titled `abc` appeared on 2026-09-13 containing uncommitted work; at Ved's instruction only its message was reworded. If unexplained commits appear again, check before building on them.
- `ProcessMap.tsx` once contained literal NUL bytes, which git treats as binary. The checkpoint now scans tracked files for NUL bytes; keep doing so.

## Real pace vs. planned pace

Week 1 (Days 1–7) was completed on 2026-09-13 across three sessions: far ahead of the plan's
calendar (7 days × 3–4 h). The plan's day boundaries still worked as units of work and checkpoints.
