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
**Status**: open

## 2026-09-13 — Module A — Lifecycle transitions vs. the single-timestamp schema

**Question**: BPI 2017 events carry `lifecycle:transition` (e.g. schedule / start / complete /
suspend / resume / abort / withdraw). The normalized schema in `01-REQUIREMENTS.md` has one
`timestamp` per row and no lifecycle column. Should ingestion keep only `complete` events, or
keep all transitions with an added `lifecycle` column?
**Why it's blocking (or what it's blocking)**: Day 2 schema design. It changes DFG and
variant counts (Module A), and whether Module B can separate processing time (start→complete)
from waiting time (complete→next start) for bottleneck analysis.
**Claude's best guess if forced to proceed anyway**: Mine on `complete` events only (standard
for heuristic mining; avoids start/complete pairs inflating self-loops), but preserve the raw
transitions in a separate processed file so Module B can compute processing vs. waiting time
later. Adding a column to the shared schema is a requirements change, so not done without a yes.
**Status**: open

## 2026-09-13 — Module A (infra) — Which BPI dataset, and repo setup

**Question**: BPI 2012 vs. 2017; the build plan said to clone a repo already containing the
docs, but the remote was empty.
**Why it's blocking (or what it's blocking)**: Day 1 download and first commit.
**Claude's best guess if forced to proceed anyway**: n/a
**Status**: resolved — 2026-09-13, Ved: use BPI Challenge 2017; initialise the repo locally and
push directly; Ved must be the sole git contributor (no AI co-author trailers).
