# 08 — Open Questions

> Per `CLAUDE.md` section 2: when something needs human input, log it here and continue
> with other unblocked work rather than stopping entirely. Check this file at the start of
> every session you (Ved) run — anything listed here is waiting on you specifically.

Format:

```
## [DATE] — [Module] — short title

**Question**: ...
**Why it's blocking (or what it's blocking)**: ...
**Claude's best guess if forced to proceed anyway**: ...
**Status**: open / resolved — [resolution + date]
```

---

*(This file should never be deleted — resolved questions stay, marked resolved, as a record of
decisions made during the build.)*

## 2026-09-13 — Module A (infra) — PostgreSQL is not installed on this machine

**Question**: Day 2 says "store normalized data in Postgres", but `psql` is not installed and
neither Homebrew nor Docker is available to install it. How do you want Postgres provided
(Postgres.app, Homebrew `postgresql@16`, Docker, or a hosted instance)?
**Why it's blocking (or what it's blocking)**: The "store in Postgres" part of Day 2 only. The
XES → normalized converter and its row-count test do not need a database.
**Claude's best guess if forced to proceed anyway**: Build the converter to write a normalized
file to `data/processed/` first, and keep the Postgres load as a separate function added once a
server exists — so no ingestion logic depends on the database being present. Installing
Postgres is a machine setup step for Ved, not something to do autonomously.
**Status**: resolved — 2026-09-13: Ved installed Homebrew and asked Claude to install Postgres.
Installed `postgresql@18` (18.6), started with `brew services start postgresql@18` (starts at
login; stop with `brew services stop postgresql@18`), created databases `meridian` and
`meridian_test`. Homebrew's default local `trust` authentication applies — fine for local
development only.

## 2026-09-13 — Module A — Lifecycle transitions vs. the single-timestamp schema

**Question**: BPI 2017 events carry `lifecycle:transition` (schedule / start / suspend / resume /
complete / ate_abort / withdraw). The normalized schema in `01-REQUIREMENTS.md` has one
`timestamp` per row and no lifecycle column. Which transitions should the normalized log keep?
**Why it's blocking (or what it's blocking)**: Not Days 3–4 (the DFG and heuristic-miner core are
built and tested on synthetic logs). It does decide what the real-data process map, variant
counts (Day 5–6) and Module B bottlenecks will show. Measured on the full log (2026-09-13), it
matters more than first assumed:
- Application (`A_`) and offer (`O_`) events are all `complete`, so they are unaffected.
- Workflow (`W_`) work items mostly end in `ate_abort` or `withdraw`, not `complete`:
  W_Call after offers: 31,485 starts, 342 completes, 31,085 ate_abort;
  W_Validate application: 39,444 starts, 15,848 completes, 23,161 ate_abort;
  W_Call incomplete files: 23,218 starts, 2,793 completes, 20,220 ate_abort.
- So `complete`-only (the current default) keeps 475,306 of 1,202,267 events, makes W_Call after
  offers look ~90x rarer than it is, drops W_Personal Loan collection and W_Shortened completion
  entirely, and drops 5 resources (User_145–User_149, 41 events).

Options (all four are a config change plus re-run, because every transition is preserved in
`data/processed/raw_events.csv`):
- **A.** `complete` only — the current default. Conventional, but distorts workflow activities as above.
- **B.** One row per activity *started*: `start` for work items that record starts (W_),
  `complete` for instantaneous events (A_, O_). No schema change. Work that was scheduled but never
  begun (e.g. 16,802 withdrawn W_Handle leads items) is correctly absent.
- **C.** One row per work item *ended* (`complete`, `ate_abort`, `withdraw`). Every item appears
  once, but withdrawn, never-worked items would show up as if they were handled.
- **D.** Keep all transitions and add a `lifecycle` column to the shared schema (a requirements
  change; every module then has to handle transitions).

**Claude's best guess if forced to proceed anyway**: **B**. It reflects work that actually
happened with one timestamp per activity and no schema change, and Module B/F can still pair
start with complete/ate_abort from `raw_events.csv` for processing times. The default stays A
until you decide, per "log it, don't unilaterally switch approaches".
**Status**: resolved — 2026-09-13, Ved chose **B** (start where recorded, complete otherwise).
Ved's reasoning, recorded as given:
- Complete-only (A) is not acceptable even temporarily. It is a data-integrity problem, not a
  minor caveat: 342 of 31,485 actual `W_Call after offers` occurrences is a ~99% undercount of the
  process's real human work.
- Keeping all transitions with a lifecycle column (D) is legitimate **future work** (full
  lifecycle and duration modelling), not built now, because every module would have to handle
  start/complete pairs, not just ingestion.
- Action: re-ingest, regenerate Module A outputs, update the pinned real-data test counts, then
  publish Module B.
Implementation: the rule is data-driven, not keyed on the `W_` prefix. An activity is represented
by its `start` events if the log records any `start` for it, otherwise by its `complete` events.
On BPI 2017 this selects exactly the eight `W_` activities.

## Future work — full lifecycle modelling (option D above)

Keep every lifecycle transition and add a `lifecycle` column to the shared schema so modules can
pair start with complete/ate_abort for processing versus waiting time. Deferred by Ved on
2026-09-13: it changes every module, not just ingestion. `data/processed/raw_events.csv` already
preserves all transitions, so it needs no re-parse when picked up.

## 2026-09-13 — Module A / B — The most common variant is a cancellation path

**Question**: 01-REQUIREMENTS.md defines the "happy path" as the most common variant (Module A
req. 4), and Module B req. 1 defaults its reference model to the most frequent variant. On BPI 2017
(current `complete`-only log) the three most common variants, 5,704 cases, all end **cancelled**:
offer created and sent, customer never returns it, application cancelled. The rank-1 variant
(2,209 cases, 7.0%) has a median cycle time of 31.7 days against 17.9 days for all other cases.
Should "happy path" and the Module B reference model stay "most frequent variant", or become
"most frequent variant among successful cases" (outcome `pending`)? BPI 2017 publishes no
documented intended process, so Module B's documented-model alternative is not available.
**Why it's blocking (or what it's blocking)**: Not Module A — Day 6 implements the definition as
written, and the generated summary states the rank-1 variant's outcome mix so nobody reads it as a
success path. It blocks Module B (Day 8): conformance measured against a cancellation path would
make "% of cases deviating from the intended path" mean the opposite of what it says.
**Evidence added 2026-09-13 (Day 10 code, `complete`-only log, both computed, neither chosen)**:

| Reference model | Cases fitting exactly | Deviating | Log fitness | Mean case fitness: pending / cancelled / denied |
|---|---|---|---|---|
| A. Most frequent variant (as written) | 2,209 | 93.0% | 0.576 | 0.477 / 0.868 / 0.506 |
| B. Most frequent variant among `pending` cases | 969 | 96.9% | 0.677 | 0.755 / 0.610 / 0.595 |

- Under A, successful (`pending`) cases score as the *least* conforming and cancellations as the
  most, so "deviation from the intended path" would effectively mean "not cancelled".
- Under B the ordering is coherent: successful cases fit best.
- Under either, exact-fit deviation is above 90%: no single path covers more than 7% of cases. The
  report should therefore lead with log fitness and the fitness distribution, not only "% deviating".

**Claude's best guess if forced to proceed anyway**: Keep requirement 4's literal definition for
Module A's "happy path" statistics (clearly labelled "most common variant"), and for Module B use
the most frequent variant among `pending` cases as the reference model (B above), logging that
choice. This also depends on the lifecycle question above, which changes the variants themselves.
Until answered, `select_reference_model` has no default and the conformance command will require
the strategy to be named explicitly.
**Status**: resolved — 2026-09-13, Ved chose **A**: the most frequent variant overall, as originally
specified in 01-REQUIREMENTS.md. Ved's reasoning, recorded as given:
- Option B's "coherent ordering" argument is circular: whichever group's variant is picked as the
  reference will always score best against itself. (Claude agrees; the evidence above cannot favour
  B for that reason.)
- Option A has a much larger sample: 2,209 cases against 969.
- The modal path ending in cancellation rather than approval is itself a diagnostic finding worth
  reporting, not something to route around.
Consequences: the conformance command defaults to `most_frequent_variant`, and the diagnostic
report presents the modal path's outcome as a finding. The reference is re-selected on the log
produced by the lifecycle decision above, so the modal path itself may change from the one described
here.

## 2026-09-13 — Module A (infra) — Which BPI dataset, and repo setup

**Question**: BPI 2012 vs. 2017; the build plan said to clone a repo already containing the
docs, but the remote was empty.
**Why it's blocking (or what it's blocking)**: Day 1 download and first commit.
**Claude's best guess if forced to proceed anyway**: n/a
**Status**: resolved — 2026-09-13, Ved: use BPI Challenge 2017; initialise the repo locally and
push directly; Ved must be the sole git contributor (no AI co-author trailers).
