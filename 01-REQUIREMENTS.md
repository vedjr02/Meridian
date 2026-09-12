# 01 — Requirements

## Project one-liner

Given a real business event log (case ID, activity, timestamp, resource), reconstruct the
actual process as it really happens, diagnose where and why it breaks down, model the
organizational network running it, simulate proposed fixes before recommending them, and
produce an executive-ready business case with modeled ROI.

## Data

- **Primary dataset**: a BPI Challenge event log (e.g., BPI Challenge 2012 or 2017, loan/credit
  application process — real, anonymized, publicly available in XES/CSV format).
- Format after ingestion (all modules read from this normalized schema — do not let individual
  modules invent their own column names):
  `case_id | activity | timestamp | resource | (optional) cost | (optional) outcome`
- If the raw dataset lacks `resource` (who performed the activity), Module 3 (Organizational
  Network Mining) cannot run — check this during data ingestion and log it to
  `08-OPEN-QUESTIONS.md` immediately if so, rather than discovering it in week 5.

## Module A — Process Discovery (Core, Week 1)

**Goal**: turn raw event log rows into an actual process map with real statistics.

Requirements:
1. Ingest the raw log into the normalized schema above. Handle malformed rows (missing
   timestamps, out-of-order events within a case) by logging and excluding them — never
   silently dropping data without a count of how much was dropped and why.
2. Build a Directly-Follows Graph (DFG): for every case, compute activity-to-activity
   transitions; aggregate frequency and average duration per transition across all cases.
3. Implement a **Heuristic Miner** from first principles (see `02-TECH-STACK-AND-SKILLS.md`
   for the algorithm spec) to produce a discovered process model, not just the raw DFG.
4. Compute per-case statistics: total cycle time, number of activities, whether the case
   is a "happy path" match against the most common variant.
5. **Variant analysis**: count distinct end-to-end paths through the process and their
   frequency. Report the number of variants needed to cover 80% of cases (this number is
   the headline "your process is messier than you think" finding).

**Acceptance criteria**: given the raw log file, a single command produces (a) a DFG
visualization, (b) the mined heuristic process model, (c) a variant frequency table,
(d) a written summary of cycle time distribution (not just mean — include p50/p90/p99).

## Module B — Conformance & Bottleneck Diagnosis (Core, Week 2)

**Goal**: quantify exactly where and how much the real process deviates from the intended one.

Requirements:
1. Define a reference model — either the most frequent variant from Module A, or, if the
   dataset provides documentation of an intended process, use that instead (log which you used).
2. Implement **token-based replay**: for every case, replay it against the reference model
   and count missing tokens (skipped required steps) and remaining tokens (extra/unexpected
   steps). Produce a fitness score per case and in aggregate.
3. **Bottleneck analysis**: for every transition, compute the *distribution* of wait time,
   not just the mean. Flag transitions with high variance separately from transitions that
   are uniformly slow — these need different explanations and different fixes.
4. **Rework loop detection**: identify cases where the same activity recurs within one case;
   quantify total added cycle time attributable to rework across the dataset.
5. Output a written diagnostic report with specific, quantified findings — every claim must
   cite a number computed from the data, not a general observation.

**Acceptance criteria**: the diagnostic report can answer, with numbers: "what % of cases
deviate from the intended path," "which single transition costs the most aggregate time,"
"how much total cycle time does rework add."

## Module C — Automation Opportunity Scoring & Requirements Generation (Core, Week 3)

**Goal**: turn diagnosis into an actual BA deliverable.

Requirements:
1. Score every distinct activity on four dimensions, each computed from real data, not
   assigned by hand: repetitiveness (structural similarity of inputs/context across
   instances of this activity), volume (frequency), rule-clarity (variance in duration and
   path taken after this activity — low variance suggests a clear rule, high variance
   suggests judgment calls), exception rate (how often this activity appears inside a
   rework loop or off the happy path).
2. Combine into a single weighted automation-viability score per activity; the weights must
   be explicit and justified in the code comments, not a magic number.
3. For the top 3 ranked activities, auto-generate: a current-state/future-state one-paragraph
   comparison, 3–5 user stories in "As a [role], I want [capability], so that [benefit]"
   format, and acceptance criteria in Given/When/Then format.
4. Generate a simple to-be process diagram (Mermaid flowchart syntax is acceptable — does
   not need to be a full BPMN tool) for the proposed future-state process.

**Acceptance criteria**: running the scorer on the dataset produces a ranked list with
justified scores, and the top 3 have complete, well-formed requirements artifacts attached.

## Module D — Business Case & ROI Modeling (Core, Week 4)

**Goal**: justify the recommendations with numbers grounded in Modules A–C, not invented ones.

Requirements:
1. For each of the top 3 automation candidates from Module C, model: implementation cost
   (a reasonable estimate range, stated as an assumption), time saved per case (from Module
   B's cycle-time data), converted to a cost-per-hour assumption (stated explicitly),
   resulting in a payback period and 3-year NPV.
2. Run a **sensitivity analysis**: vary the two riskiest assumptions (e.g., adoption rate,
   volume growth) across a reasonable range and show how payback period changes — do not
   present a single point estimate as if it were certain.
3. Produce a prioritization matrix (ROI vs. implementation ease) across all three candidates.
4. Generate an executive one-pager per recommendation, in prose suitable for a steering
   committee — no jargon, clear ask, clear number.

**Acceptance criteria**: each recommendation has a documented payback period, an NPV range
(not a single number), and a one-page written summary a non-technical stakeholder could read
in two minutes and understand the ask.

## Module E — Organizational Network Mining (Extension, Week 5)

**Goal**: analyze the people running the process, not just the process itself.

Requirements:
1. Build a handoff network: nodes are resources (people/roles), edges are handoffs between
   them weighted by frequency, derived directly from the normalized event log.
2. Compute and report: betweenness centrality (who is a structural bottleneck because work
   routes through them disproportionately), a bus-factor flag (activities where one resource
   handles an unusually high share of volume), and team-to-team interaction sparsity (pairs
   of frequently-adjacent activities handled by resources who rarely otherwise interact).
3. Render the network as an actual interactive graph in the frontend, not a static image —
   this is meant to be explored, not just viewed once.

**Acceptance criteria**: given the same event log, the tool identifies at least one genuine
bottleneck resource and one bus-factor risk, each with a supporting number (e.g., "handles
34% of all approvals, more than 3x the next resource").

## Module F — What-If Simulation Engine (Extension, Week 6)

**Goal**: let a user test an intervention before recommending it, rather than estimating
its effect from static assumptions alone.

Requirements:
1. Build a discrete-event simulation (see `02-TECH-STACK-AND-SKILLS.md` for library choice)
   of the mined process from Module A, calibrated against real cycle-time and volume
   distributions from Modules A–B — the simulation must reproduce the *actual* cycle time
   distribution reasonably closely before it's trusted for what-if scenarios (state the
   validation check explicitly, e.g., simulated p50 within X% of real p50).
2. Support at minimum these three intervention types as user-configurable scenarios:
   adding capacity at a named bottleneck step, changing volume (e.g., +30% next quarter),
   and removing a specified rework loop.
3. Output: simulated cycle-time distribution under the intervention, compared side-by-side
   against the real baseline distribution.
4. Feed simulation output back into Module D's ROI model as an option — "modeled outcome"
   instead of a purely static assumption.

**Acceptance criteria**: running a scenario produces a distribution comparison (not a single
number) and the validation check from requirement 1 passes and is visible to the user.

## Module G — Natural Language Query Layer (Extension, only if time allows after F)

**Goal**: a chat interface over the structured outputs of Modules A–F.

Requirements:
1. Answer questions by translating them into queries against the *structured* outputs
   (the mined model, the diagnostic tables, the network graph, the simulation results) —
   not by summarizing raw text. If a question can't be mapped to a structured query, say so
   rather than guessing an answer from the LLM's general knowledge.
2. Every answer must show which underlying data/table it came from.

**Acceptance criteria**: this module is explicitly lowest priority. Do not start it until
Modules A–F are complete and their acceptance criteria are met. If time runs out before this
module, that is an acceptable outcome — log it as a "future work" item, not a failure.

## Non-functional requirements (apply to all modules)

- Every module has automated tests covering at least the acceptance criteria above.
- No hardcoded file paths — configuration lives in one place.
- The frontend must clearly communicate uncertainty (confidence ranges, not false precision)
  everywhere Module D or F output is shown — see `03-UIUX-RULES.md`.
- README at project root must let a stranger clone the repo and run the full pipeline against
  the sample dataset in under 10 minutes, following only the written instructions.

## Explicitly out of scope (do not build unless `08-OPEN-QUESTIONS.md` confirms otherwise)

- User accounts / multi-tenant support.
- Real-time/streaming event ingestion — batch processing of a static log file is sufficient.
- Support for arbitrary event log schemas beyond the normalized one above.
- Mobile responsiveness beyond "doesn't visibly break" — this is a desktop analytical tool.
