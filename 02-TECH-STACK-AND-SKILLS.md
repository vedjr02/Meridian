# 02 — Tech Stack, Libraries, and Algorithm Specifications

## Stack overview

| Layer | Choice | Why |
|---|---|---|
| Core data processing | Python 3.11+, pandas | Standard, and Ved already knows it |
| Graph structures | networkx | Use for graph *representation and utility ops* (shortest path, centrality) — not for the mining/discovery algorithm itself, which must be hand-implemented (see below) |
| Simulation | SimPy | Discrete-event simulation, the standard library for this in Python |
| Backend API | FastAPI | Type-safe, async, easy to test |
| Database | PostgreSQL | Ved's existing preference; stores normalized event log, mining results, past decision/audit runs |
| Frontend | Next.js + React (Ved's existing stack) | No new frontend framework to learn mid-project |
| Graph visualization (frontend) | react-force-graph or d3-force | For Module E's interactive network |
| Charts | Recharts or Plotly | Distribution charts (cycle time, sensitivity analysis) — must support showing a distribution, not just a bar of the mean |
| LLM usage (Module C, D, G only) | Claude API (Sonnet) | Used ONLY for narrative generation (user stories, executive prose) and Module G's query translation — never for the core mining/conformance/scoring/simulation algorithms |
| Testing | pytest | All modules |

## Algorithms that must be hand-implemented (do not import a full solution)

This is the actual skill demonstration of the project. A library call that does the whole
job defeats the purpose — the point is that you understand and can explain the algorithm.

### 1. Heuristic Miner (Module A)

Core idea: build a **footprint matrix** between every pair of activities based on direct
succession in the log, then classify each pair as one of: causality (A always/mostly
followed by B, never B followed by A), parallel (both A→B and B→A occur with similar
frequency), or unrelated (never directly follow each other).

Steps to implement:
1. Compute `|A>B|` — count of direct follows from A to B across all cases.
2. Compute the **dependency measure**: `(|A>B| - |B>A|) / (|A>B| + |B>A| + 1)`. Values near
   +1 indicate strong causality A→B.
3. Apply a dependency threshold (make this configurable, not hardcoded — a common default is
   0.9, but log-specific tuning matters and should be justified in comments) to decide which
   edges become causal connections in the mined model.
4. Handle loops explicitly: length-one loops (A immediately follows itself) and length-two
   loops (A→B→A) need separate detection logic from the basic footprint matrix, or they will
   be silently misclassified as noise.
5. Output: a process model as a graph structure (start activities, end activities, causal
   edges) — this is what gets rendered as the mined process map.

### 2. Token-Based Replay (Module B)

Core idea: represent the reference process model as a Petri-net-like structure (places and
transitions is the formal version; a simplified directed-graph-with-required-order version
is acceptable if documented as a simplification). For each real case, "play" its actual
sequence of activities against the model:
- A token consumed correctly = the case did what the model expected.
- A **missing token** = the case skipped a required step (had to be inserted to let replay continue).
- A **remaining token** = the case did something extra the model didn't expect.
- Fitness per case = a function of correctly consumed vs. missing/remaining tokens (a common
  formula: `1 - (missing + remaining) / (total expected + total actual)` — implement and
  justify whichever formula you use in a code comment).

### 3. Network centrality (Module E)

Betweenness centrality itself can use `networkx.betweenness_centrality()` — this is a
well-defined graph-theory primitive, not the "point" of the module. The mining work that
matters is: correctly constructing the handoff graph from raw event-log resource data in
the first place (who hands off to whom, weighted correctly by frequency, direction-aware).

### 4. Discrete-event simulation calibration (Module F)

Do not just simulate "average" behavior. Fit the real distributions:
- Sample inter-arrival times and per-activity durations from the empirical distribution in
  the real log (or fit a known distribution — e.g., log-normal is common for service times —
  and justify the choice with a goodness-of-fit check, however basic).
- Validate the simulation reproduces real aggregate statistics within a stated tolerance
  before trusting it for what-if scenarios. This validation step is a stated requirement in
  `01-REQUIREMENTS.md` — do not skip it even though it adds time.

## Where the LLM (Claude API) is and isn't allowed

**Allowed**:
- Module C: turning a scored activity + its data into readable user stories and a
  current/future-state paragraph.
- Module D: turning ROI numbers into an executive-readable one-pager.
- Module G: translating a natural-language question into a structured query against
  already-computed tables (not answering from general knowledge).

**Not allowed**:
- Computing the mining, conformance, scoring, or simulation results themselves. These are
  Modules A, B, C's scoring step, E, and F's core logic — deterministic, auditable,
  reproducible code. If a reviewer re-runs the pipeline on the same data, they must get the
  same numbers every time. An LLM call in the middle of that breaks reproducibility and
  undermines the entire "this is real analytics, not a chatbot" premise of the project.

## Dataset

- Use a BPI Challenge event log (bpi challenge datasets are public, XES format, searchable
  via "4TU.ResearchData BPI Challenge"). Convert XES to the normalized CSV schema in
  `01-REQUIREMENTS.md` as the very first ingestion step, and write a test that checks row
  counts before/after conversion so silent data loss during parsing is caught immediately.
