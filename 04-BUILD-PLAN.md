# 04 — Build Plan

Each day below is scoped to be independently committable in multiple small pieces (see
`05-GIT-WORKFLOW.md` for commit granularity). Check off tasks in `07-PROGRESS-STATE.md` as
you complete them — this file describes what to do; `07-PROGRESS-STATE.md` tracks what's done.

Assumption baked into this plan: roughly 3–4 focused hours of work per day. If actual daily
time differs a lot, that's fine — the task breakdown still holds, just adjust how many days
of calendar time each week takes. Log the real pace in `07-PROGRESS-STATE.md` so the plan
stays honest.

---

## Week 1 — Module A: Process Discovery

**Day 1**: Repo scaffolding. Clone https://github.com/vedjr02/Meridian.git (already created, contains this planning doc set at root — commit those docs first per the setup steps before starting Day 1 code). Initialize project structure (`/backend`, `/frontend`,
`/data`, `/tests`). Set up Python virtual env, FastAPI skeleton with a health-check endpoint,
pytest configured and running (even on zero tests). Set up Next.js frontend skeleton with
the base layout from `03-UIUX-RULES.md` (typography, palette, no content yet). Get the
BPI Challenge dataset downloaded into `/data/raw` (do not commit the raw dataset itself if
it's large — commit a script that downloads it, and a `.gitignore` entry).

**Day 2**: Data ingestion. Write the XES/CSV → normalized schema converter. Write the test
that checks row counts before/after (per `02-TECH-STACK-AND-SKILLS.md`). Handle and log
malformed rows. Store normalized data in Postgres.

**Day 3**: Directly-Follows Graph. Compute transition frequencies and average durations.
Unit tests against a small hand-crafted synthetic log where you know the correct answer
(this matters — testing only against the real messy dataset means you can't verify
correctness, only that it runs without crashing).

**Day 4**: Heuristic Miner core — footprint matrix and dependency measure calculation.
Unit tests against the same synthetic log, checking specific expected causal/parallel/
unrelated classifications.

**Day 5**: Heuristic Miner — loop handling (length-one and length-two), threshold
configuration, full mined-model output. Integration test: run the whole Module A pipeline
end-to-end against the real dataset and sanity-check the output is plausible (no orphan
nodes, start/end activities make sense).

**Day 6**: Variant analysis (distinct paths, frequency, 80% coverage count) and cycle-time
statistics (p50/p90/p99, not just mean). Written summary generator for the "your process is
messier than you think" finding.

**Day 7**: Frontend for Module A — render the mined process graph, variant table,
cycle-time distribution chart. Checkpoint per `06-AUDIT-PROTOCOL.md` before moving to Week 2.

---

## Week 2 — Module B: Conformance & Bottleneck Diagnosis

**Day 8**: Reference model selection logic (most frequent variant vs. documented model if
available). Simplified Petri-net-like structure to represent it.

**Day 9**: Token-based replay core algorithm. Unit tests against the synthetic log with
known expected fitness scores for hand-crafted "perfect," "one deviation," and "very
different" test cases.

**Day 10**: Run replay against the full real dataset. Produce per-case and aggregate
fitness scores.

**Day 11**: Bottleneck analysis — wait-time distributions per transition (not just means),
variance-based flagging (high-variance vs. uniformly-slow classification).

**Day 12**: Rework loop detection and its cycle-time cost quantification.

**Day 13**: Written diagnostic report generator (deterministic template + numbers, not
LLM-generated at this stage — see `02-TECH-STACK-AND-SKILLS.md` on where LLM use is allowed).

**Day 14**: Frontend for Module B (stat cards, bottleneck chart, rework findings).
Checkpoint before Week 3.

---

## Week 3 — Module C: Automation Scoring & Requirements Generation

**Day 15**: Repetitiveness and volume scoring components — implement and unit test each
scoring dimension independently before combining them.

**Day 16**: Rule-clarity and exception-rate scoring components.

**Day 17**: Weighted combination into final score; ranking output; justify weights in
comments per the requirement.

**Day 18**: LLM integration (Claude API) for user story and current/future-state paragraph
generation — this is one of the allowed LLM use cases. Write tests that check the *structure*
of the output (has the required Given/When/Then fields, etc.) since you can't unit-test
exact LLM prose.

**Day 19**: Mermaid diagram generation for to-be process flow.

**Day 20**: Frontend for Module C — ranked list view, requirements artifact display per
top-3 candidate.

**Day 21**: Checkpoint before Week 4.

---

## Week 4 — Module D: Business Case & ROI Modeling

**Day 22**: ROI/payback/NPV calculation core — implement as pure functions with clear
documented assumptions, unit tested against hand-calculated expected values.

**Day 23**: Sensitivity analysis — vary key assumptions across a range, produce the
resulting payback-period spread.

**Day 24**: Prioritization matrix (ROI vs. ease) computation and rendering.

**Day 25**: LLM-generated executive one-pager (allowed use case) — test structure, and
manually review at least one output for tone/quality per `03-UIUX-RULES.md`'s "executive
document" standard.

**Day 26**: Frontend for Module D, including the exportable one-pager view — actually test
the export, don't assume.

**Day 27**: Full end-to-end pipeline test: raw data in, all four core modules run in
sequence, executive output out. This is the "core spine complete" milestone.

**Day 28**: Buffer day. Use it to fix whatever the Day 27 end-to-end test revealed, update
the README with real setup instructions, and do a full audit per `06-AUDIT-PROTOCOL.md`
before starting extensions.

---

## Week 5 — Module E: Organizational Network Mining

**Day 29**: Handoff graph construction from resource data in the normalized log.

**Day 30**: Centrality and bus-factor computation; unit tests against a synthetic
organizational log with a known bottleneck resource.

**Day 31**: Team interaction sparsity analysis.

**Day 32–33**: Frontend — interactive force-directed graph with node-selection detail panel.

**Day 34**: Checkpoint.

---

## Week 6 — Module F: What-If Simulation Engine

**Day 35**: Empirical distribution fitting for inter-arrival and service times from real data.

**Day 36**: Core SimPy simulation of the mined process, calibrated to real data.

**Day 37**: Validation check — simulated vs. real aggregate stats within stated tolerance.
Do not proceed to scenario features until this passes; if it doesn't, this is a legitimate
multi-day debugging task, not a quick fix.

**Day 38**: Implement the three required intervention types (add capacity, change volume,
remove rework loop).

**Day 39**: Feed simulation output into Module D's ROI model as a "modeled outcome" option.

**Day 40**: Frontend — baseline vs. scenario distribution comparison view.

**Day 41–42**: Buffer / checkpoint / full-system audit.

---

## Week 7 (only if ahead of schedule) — Module G: NL Query Layer

Only start this if Weeks 1–6 are genuinely complete against their acceptance criteria in
`01-REQUIREMENTS.md`. If not, Week 7 becomes a continuation buffer for whichever module
slipped — log this decision in `07-PROGRESS-STATE.md`, it is not a failure.

**Day 43–44**: Query translation layer (NL question → structured query against computed tables).

**Day 45–46**: Frontend chat interface, wired to the query layer, showing source attribution
per answer.

**Day 47+**: Final case-study write-up: run the full pipeline against the real dataset, write
the README as a genuine consulting-engagement-style summary with real numbers from the run,
prepare 2–3 example "scenarios" (a specific bottleneck found, a specific simulation result)
as demo talking points.
