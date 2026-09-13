# Audit Log

Checkpoint entries per `06-AUDIT-PROTOCOL.md`. Newest first.

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
