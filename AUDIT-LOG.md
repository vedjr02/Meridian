# Audit Log

Checkpoint entries per `06-AUDIT-PROTOCOL.md`. Newest first.

---

## 2026-09-13 — Session 2 — End of Week 1 Day 6 checkpoint (branch `module-a-discovery`, HEAD `5ec012e`)

| # | Check | Result |
|---|---|---|
| 1 | Full test suite incl. integration | **Pass** — 167 passed in 46.9 s; all four real-data integration tests ran |
| 2 | Linters/formatters (`ruff check`, `ruff format --check`, `eslint`) | **Pass** — all clean |
| 3 | Requirements re-read: Module A req. 4–5 and the Module A acceptance criteria, Day 6 plan | Req. 4, per-case statistics (cycle time, activity count, happy-path match against the most common variant): **pass** — `case_statistics.csv`. Req. 5, variants, frequencies and the 80%-coverage count: **pass** — `variants.csv` and the summary headline. **Acceptance, verified by running the command**: `python -m meridian.discovery` from the raw log produces (a) the DFG visualization `dfg.mmd`, also embedded in the summary; (b) the mined model `heuristic_net.json`; (c) the variant table `variants.csv`; (d) the written summary `discovery_summary.md` with p50/p90/p99, not only the mean. **All four met**, and `tests/test_discovery_pipeline.py` covers them on synthetic and real logs. The interactive frontend view is Day 7. |
| 4 | Scope drift | **Pass, documented** — Mermaid as the command-line visualization format; outcome mix per variant and the most common variant within each outcome added to the summary (prompted by the finding below); the single command pulled forward from Day 7. All logged in `07-PROGRESS-STATE.md`. |
| 5 | Hand-implemented list / LLM rule | **Pass** — no pm4py, networkx or SimPy; no LLM SDK installed or imported. The summary is template-only, with a determinism test. |
| 6 | Git authorship | **Pass** — 72 commits, all `Vedjr02`, 0 co-author trailers. |

**Real-log results (`complete`-only log, threshold 0.9)**: 5,623 variants for 31,509 cases; 80%
coverage needs 610 of them (10.8%); 4,150 variants (73.8%) occur once. Cycle time p50 19.1 d, p90
35.0 d, p99 59.1 d, mean 21.8 d, max 169.1 d. **Finding raised to the human**: the three most common
variants (5,704 cases) all end cancelled, so "most common variant" as happy path and as Module B's
default reference model is questionable. Logged in `08-OPEN-QUESTIONS.md`.

**Failed → fixed during this unit of work**
- Test expectation error: variant ranks for tied single-case variants were [2, 3] where the
  documented tie-break gives [3, 2]. The test was wrong, not the code; corrected with an explanatory comment.
- Presentation: loop measures printed as "1.000" (false certainty; measures are below 1 by
  construction), and "forward/back" did not name directions. Fixed in a separate `fix` commit with tests.
- Preempted before commit: `Series.map(dict)` with tuple keys (a pandas MultiIndex conversion
  hazard) replaced by a plain lookup.
- Several E501 line-length failures; reworded or auto-wrapped.

---

## 2026-09-13 — Session 2 — End of Week 1 Day 5 checkpoint (branch `module-a-discovery`, HEAD `0727a75`)

| # | Check | Result |
|---|---|---|
| 1 | Full test suite incl. integration | **Pass** — 130 passed in 32.2 s; all three real-data integration tests ran (ingestion→Postgres, DFG invariants, Module A end-to-end) |
| 2 | Linters/formatters (`ruff check`, `ruff format --check`, `eslint`) | **Pass** — all clean |
| 3 | Requirements re-read: Module A req. 3, 02-TECH-STACK §1 steps 4–5, Day 5 plan | Step 4, loops detected separately from the footprint: **pass** — `length_one_loop_measure`, `length_two_loop_measure` and `count_length_two_patterns`, with a test showing the footprint alone calls a loop parallel. Step 5, model output of start activities, end activities and causal edges: **pass** — `HeuristicNet` / `heuristic_net.json`. Threshold configuration: **pass** — config/env plus `--threshold`. Day 5 end-to-end real-data check: **pass** — `tests/test_module_a_pipeline.py`: no orphan activities, sole start `A_Create Application` with no incoming edge, ends sum to cases, all edges between known activities. Module A acceptance (single command producing DFG visualization, model, variant table, cycle-time summary) is not yet complete: variants and cycle times are Day 6, visualization and the single command Days 6–7. |
| 4 | Scope drift | **Pass, documented** — "all activities connected" heuristic (edge kind `best_connection`), and one threshold shared by the causal and both loop measures; both logged in `07-PROGRESS-STATE.md`. |
| 5 | Hand-implemented algorithms list | **Pass** — loop measures, pattern counting and model assembly hand-written over pandas; no pm4py, networkx or SimPy installed or imported. |
| 6 | Git authorship | **Pass** — 56 commits, all `Vedjr02`, 0 co-author trailers. |

**Real-log result (threshold 0.9, `complete`-only log)**: 98 edges — 83 causal, 5 length-one
loops, 10 length-two-loop edges, 0 best connections; mined in 0.3 s. The Day 4 finding is resolved:
`O_Create Offer ⇄ O_Created` is now a length-two loop, not parallel. Largest rework loop surfaced
for Module B: `A_Incomplete ⇄ A_Validating` (12,282 and 4,427 transitions).

**Failed → fixed during this unit of work**: two long lines (one docstring reworded, one call
auto-wrapped by the formatter).

---

## 2026-09-13 — Session 2 — End of Week 1 Day 4 checkpoint (branch `module-a-discovery`, HEAD `ff3bb29`)

| # | Check | Result |
|---|---|---|
| 1 | Full test suite incl. integration | **Pass** — 106 passed in 16.8 s, no skips |
| 2 | Linters/formatters (`ruff check`, `ruff format --check`, `eslint`) | **Pass** — all clean |
| 3 | Requirements re-read: Module A req. 3, 02-TECH-STACK §1 steps 1–3, Day 4 plan | Step 1 (|A>B|): **pass** — read from the DFG, never recounted. Step 2 (dependency measure): **pass** — `dependency_measure`, verified on hand-computed values and antisymmetry. Step 3 (configurable, justified threshold): **pass** — `DEFAULT_DEPENDENCY_THRESHOLD` in config with count-level justification, `MERIDIAN_DEPENDENCY_THRESHOLD` override, invalid values rejected. Footprint classification (causal / parallel / unrelated): **pass**, each class tested on a pair with a known answer, including the Day 3 synthetic log as the plan requires. Steps 4–5 (loops, full model output) are Day 5 and not yet built. |
| 4 | Scope drift | **Pass, documented** — `INFREQUENT` footprint class added (one-directional pair below threshold, which the spec's three classes do not cover); logged in `07-PROGRESS-STATE.md`. |
| 5 | Hand-implemented algorithms list | **Pass** — miner written by hand over DFG counts with plain Python/pandas; no pm4py, networkx or SimPy installed or imported. |
| 6 | Git authorship | **Pass** — 47 commits, all `Vedjr02`, 0 co-author trailers. |

**Real-log sanity check (not yet a pinned test)**: 24 activities give 552 off-diagonal footprint
cells (310 `#`, 83 `->`, 83 `<-`, 36 `||`, 40 `~`; the two causal directions match as mirror
consistency requires). 83 causal edges at 0.9, connecting all 24 activities. Found a concrete
case of the documented length-two-loop limitation: `O_Create Offer -> O_Created` (42,995 vs
3,913 reverse, dependency 0.833) is classed parallel, and all 3,913 reverse transitions are
`Create Offer, Created, Create Offer` sequences from cases with several offers. Day 5's loop
detection must fix exactly this.

**Failed → fixed during this unit of work**: one E501 in a test docstring and one long signature
(auto-wrapped by the formatter).

---

## 2026-09-13 — Session 2 — End of Week 1 Day 3 checkpoint (branch `module-a-discovery`, HEAD `143b54a`)

| # | Check | Result |
|---|---|---|
| 1 | Full test suite incl. integration | **Pass** — 74 passed in 16.1 s (both real-data integration tests ran; no skips) |
| 2 | Linters/formatters (`ruff check`, `ruff format --check`, `eslint`) | **Pass** — all clean |
| 3 | Requirements re-read: Module A req. 2 (DFG), Day 3 plan | "For every case, compute activity-to-activity transitions; aggregate frequency and average duration per transition": **pass** — `build_dfg` in `backend/meridian/discovery/dfg.py`. "Unit tests against a hand-crafted synthetic log where you know the correct answer": **pass** — `tests/test_dfg.py`, every expected value hand-computed and annotated. Real log: 443,797 transitions = 475,306 events − 31,509 cases (identity holds); 159 distinct edges; runs in 0.7 s. Module A acceptance (a) "DFG visualization" not yet built — scheduled with the single-command output (Days 5–7). |
| 4 | Scope drift | **Pass, documented** — `case_frequency` and median duration added beside the required frequency and mean; typed CSV reader; `python -m meridian.discovery.dfg` command. Logged in `07-PROGRESS-STATE.md`. |
| 5 | Hand-implemented algorithms list | **Pass** — DFG built with pandas grouping only; no pm4py, networkx or SimPy installed or imported. |
| 6 | Git authorship | **Pass** — 42 commits, all `Vedjr02`, 0 co-author trailers. |

**Failed → fixed during this unit of work**: two E501 line-length failures (docstring, f-string); reworded.

---

## 2026-09-13 — Session 2 — End of Week 1 Day 2 checkpoint (branch `module-a-discovery`, HEAD `31330e8`)

| # | Check | Result |
|---|---|---|
| 1 | Full test suite incl. integration (`.venv/bin/pytest -q`) | **Pass** — 60 passed in 15.7 s, including the real BPI 2017 reconciliation test and 4 PostgreSQL tests (none skipped) |
| 2 | Linters/formatters (`ruff check`, `ruff format --check`, `eslint`) | **Pass** — all clean |
| 3 | Requirements re-read: Module A req. 1, Data section, 02 dataset note, Day 2 plan | Normalized schema: **pass** (plus documented `event_index`). Malformed rows logged and excluded with per-reason counts, never silently: **pass** — accounting identity enforced in code and tests; real log has 0 malformed events. Row-count test before/after conversion: **pass** — independent byte count (1,202,267) = parsed rows; normalized + filtered + excluded = parsed. Resource check: **pass** — `org:resource` on every raw event; 0 of 475,306 normalized events lack it (149 resources raw, 144 in the `complete`-only view — logged in 08). Stored in PostgreSQL: **pass** — `meridian.event_log` holds 475,306 rows, `ingestion_run` id 1. Module A acceptance criteria (DFG, model, variants, cycle times) not due until Days 3–7. |
| 4 | Scope drift | **Pass, documented** — `event_index` ordering column, `raw_events.csv` output, derived `outcome` values, `ingestion_run` table and psycopg driver are all logged under "Scope decisions" in `07-PROGRESS-STATE.md`. |
| 5 | Hand-implemented algorithms list | **Pass** — no pm4py, SimPy, networkx or XES-import library installed or imported. Parsing uses the standard library's `xml.etree`. No mining algorithm code exists yet. |
| 6 | Git authorship | **Pass** — all 31 branch commits authored by `Vedjr02 <ambreved3@gmail.com>`, 0 co-author trailers. The one other author in `git log --all` is Ved's own GitHub merge of PR #1 into `origin/main`. |

**Failed → fixed during session**
- Two E501 line-length failures in docstrings; reworded.
- A docstring claimed a BPI 2017 case "passes through a terminal state and continues", citing the
  3,753 A_Denied events vs 3,752 denied cases. Verified in PostgreSQL before committing: 0 cases
  reach two different terminal states; the gap is one case recording A_Denied twice. Corrected.

**Process notes**
- The every-15-commits trigger fell at commit 29; this checkpoint ran at commit 31, the end of the
  same unit of work, rather than splitting it.
- Pre-commit now runs everything except `integration` tests (~16 s each commit otherwise); those
  run at every checkpoint, as this one did.

**Not done / deferred**
- Claude Code post-edit test hook — still deferred (see Day 1 entry).

---

## 2026-09-13 — Session 1 — End of Week 1 Day 1 checkpoint (branch `module-a-discovery`)

| # | Check | Result |
|---|---|---|
| 1 | Full test suite (`.venv/bin/pytest -q`) | **Pass** — 25 passed (config 2, health 1, downloader 5, design-token contrast 17) |
| 2 | Linters/formatters (`ruff check`, `ruff format --check`, `eslint`, `tsc --noEmit`, `next build`) | **Pass** — all clean; production build succeeds |
| 3 | Requirements re-read (`01-REQUIREMENTS.md` non-functional + Module A data section) | Day 1 is infrastructure; no Module A acceptance criterion is due yet. "No hardcoded file paths": **pass** — paths live only in `backend/meridian/config.py`. "README lets a stranger run the pipeline": **not yet met** — expected, scheduled for Day 28. Resource-column check: `org:resource` is declared as a global event attribute in the XES header; per-event completeness to be measured during Day 2 ingestion. |
| 4 | Scope drift | **Pass, documented** — checksum-pinned downloader and gitignored Next.js agent-hint files logged under "Scope decisions" in `07-PROGRESS-STATE.md`. Nothing built beyond Day 1 intent. |
| 5 | Hand-implemented algorithms list (`02-TECH-STACK-AND-SKILLS.md`) | **Pass** — `pip list` shows no pm4py or other process-mining/simulation packages. No algorithm code exists yet. |
| 6 | Git authorship (Ved's instruction this session) | **Pass** — all 14 commits authored by `Vedjr02 <ambreved3@gmail.com>`; 0 co-author trailers. |

**Failed → fixed during session**
- `ruff` import-sort (I001) failures in two test files: `meridian` was not declared first-party.
  Fixed by adding `[tool.ruff.lint.isort] known-first-party` rather than suppressing the rule.

**Not done / deferred**
- Claude Code post-edit test hook (06-AUDIT-PROTOCOL "recommended enforcement") — deferred to
  the next session; the pre-commit hook (the mandatory rolling check) is installed and working.
