# 06 — Audit Protocol

The point of this file: an agent working autonomously across many sessions will drift —
forgetting earlier constraints, quietly loosening a requirement it found inconvenient,
letting test coverage slip, or accumulating small inconsistencies that compound. This
protocol forces a genuine check against reality at defined points, rather than trusting
"it feels done."

## Checkpoint cadence

Run a full checkpoint (below) at three trigger points, whichever comes first:
1. End of every day in `04-BUILD-PLAN.md`.
2. Every 15 commits, regardless of which day that falls within.
3. Before merging any module branch into `main`.

A lighter **rolling check** (just the test suite + lint) runs before every single commit —
see the pre-commit hook setup at the bottom of this file for making this automatic rather
than relying on remembering to do it.

## Full checkpoint procedure

1. **Run the entire test suite**, not just tests for the module you were just working on.
   A change in Module B's data model can silently break Module A's tests if they share
   fixtures — this is exactly the kind of regression that only a full-suite run catches.
2. **Run the linter/formatter** across the whole codebase.
3. **Re-read the relevant section of `01-REQUIREMENTS.md`** for the module just worked on,
   line by line, and check each acceptance criterion explicitly — not "I believe this is
   satisfied" but actually verify it (run the specific command, check the specific output).
4. **Check for scope drift**: does anything built in this session go beyond what
   `01-REQUIREMENTS.md` specifies, without a corresponding entry in `07-PROGRESS-STATE.md`'s
   "Scope Decisions" section explaining why? If so, either roll it back or document it — don't
   leave undocumented scope changes in the codebase.
5. **Check the "must be hand-implemented" list** in `02-TECH-STACK-AND-SKILLS.md` — has a
   library import crept in anywhere it shouldn't have (easy to do accidentally when debugging
   under time pressure and reaching for a quick fix)?
6. **Write an audit entry** to `AUDIT-LOG.md` (create this file on first use) with: date/session
   marker, what was checked, what passed, what didn't, and what was fixed as a result. This
   log is itself evidence for the eventual case-study write-up ("the project maintained
   continuous test coverage and passed N audit checkpoints") — treat it as a real artifact,
   not busywork.
7. Only after all of the above passes: proceed to the next task, or merge, as applicable.

## If a checkpoint fails

- **Test failures**: fix before proceeding. Do not comment out or skip a failing test to
  "come back to it later" — this is exactly the kind of drift the checkpoint exists to catch.
- **Scope drift found**: either revert the drifted code or formally update
  `01-REQUIREMENTS.md` and log why in `07-PROGRESS-STATE.md`. Silent scope creep left as-is
  is not an acceptable outcome of a checkpoint.
- **Acceptance criterion genuinely not met and you're not sure why**: this is a "stop and
  ask" situation per `CLAUDE.md` section 2 if two genuine debugging attempts don't resolve it.

## Recommended technical enforcement (not just relying on remembering to follow this doc)

Prose instructions get followed less reliably over long autonomous stretches than actual
enforced mechanisms. Set these up once, at the start of the project:

- **A pre-commit hook** (via `pre-commit` framework, or a plain git hook) that runs the test
  suite and linter automatically before any commit is allowed to complete. This makes the
  "rolling check" from above non-optional rather than a step that can be quietly skipped.
- **A Claude Code hook** (configured in the project's Claude Code settings) that runs after
  file edits to automatically re-run the relevant test file — check current syntax for this
  against the official docs at code.claude.com/docs/en/hooks when setting it up, since hook
  configuration format can change between versions; don't assume a config you find in an old
  blog post is current.

These two mechanisms together mean the audit protocol is partially self-enforcing rather
than depending entirely on the agent choosing to follow this document every time.
