# CLAUDE.md — Operating Instructions for This Project

> This file is auto-loaded by Claude Code at the start of every interactive session in this repo.
> Read this fully before touching any code. If anything here conflicts with a request typed
> in chat during a session, the in-session request wins for that session only — but do not
> silently drop these rules for future sessions.

## 0. What this project is

**Repository**: https://github.com/vedjr02/Meridian.git

**Meridian** — a portfolio-grade business analytics platform that mines
real event-log data to reconstruct actual business processes, diagnoses where they break down,
simulates interventions before recommending them, and produces an executive-ready business case.

This is not a script. It is a multi-module system built over several weeks. Treat it with the
rigor of a real engineering project: tests, structure, documentation, and small reviewable commits.

Full scope lives in `01-REQUIREMENTS.md`. Do not expand or shrink scope without flagging it in
`07-PROGRESS-STATE.md` under "Scope Decisions" and explaining why.

## 1. Session start-of-work checklist (do this every time, no exceptions)

1. Read `07-PROGRESS-STATE.md` in full. This is the single source of truth for what has been
   done, what is in progress, and what is blocked. Do not trust your own memory of prior
   sessions — you don't have any. Trust the file.
2. Read the "Current Phase" section of `04-BUILD-PLAN.md` that corresponds to where
   `07-PROGRESS-STATE.md` says you are.
3. Run the existing test suite before writing any new code. If it's not green, fixing that
   is the first task of the session, before any new feature work.
4. Check `06-AUDIT-PROTOCOL.md` — if the last session ended mid-checkpoint, finish the
   checkpoint before starting new work.
5. Only after 1–4: begin the next unchecked task in `04-BUILD-PLAN.md`.

## 2. Autonomy rules — when to keep going vs. when to stop and ask

**Keep going without asking, when:**
- The next step is already specified in `04-BUILD-PLAN.md`.
- You hit a bug in your own code from earlier in the session — fix it, don't ask permission to fix your own mistake.
- A test fails and the fix is unambiguous (typo, wrong import, off-by-one).
- You need to make a small implementation-detail decision that doesn't change requirements
  (e.g., which specific pandas method to use). Make the call, note it briefly in the commit message.

**Stop and write a question into `08-OPEN-QUESTIONS.md`, then continue with other unblocked
work instead of halting entirely, when:**
- A requirement in `01-REQUIREMENTS.md` is ambiguous or internally contradictory.
- You'd need to install a new major dependency not listed in `02-TECH-STACK-AND-SKILLS.md`.
- Something in `03-UIUX-RULES.md` conflicts with a technical constraint you've discovered.
- You believe a scope change would meaningfully improve the project (e.g., a better algorithm
  than the one specified). Log it, don't unilaterally switch approaches mid-build.

**Stop everything and wait for the human, when:**
- A destructive git operation seems necessary (force-push, history rewrite, deleting a branch
  with unmerged work). Never do these autonomously. See `05-GIT-WORKFLOW.md`.
- You cannot get the test suite green after two genuine attempts on the same failure.
- Real data (the BPI Challenge event log) appears corrupted, missing, or its schema doesn't
  match what `01-REQUIREMENTS.md` assumes.

## 3. Non-negotiable engineering rules

- No function without a docstring explaining *why*, not just what — this codebase is meant to
  be read by an interviewer later, not just executed.
- No algorithm from `02-TECH-STACK-AND-SKILLS.md` (heuristic miner, token-based replay, etc.)
  gets imported from a library that does the whole job for you. Implement the core logic
  yourself; libraries are fine for supporting utilities (dataframes, plotting, networkx graph
  primitives), not for the algorithm that is the point of the project. If unsure whether
  something crosses that line, log it in `08-OPEN-QUESTIONS.md` rather than guessing.
- Every module (mining, conformance, scoring, simulation, network analysis) must be runnable
  and testable in isolation, not only through the full pipeline. This is both good engineering
  and what makes the eventual case-study write-up credible.
- Follow `05-GIT-WORKFLOW.md` exactly for commit granularity, messages, and push cadence.
- Follow `06-AUDIT-PROTOCOL.md` checkpoints exactly — do not skip a checkpoint because you're
  "confident" the code is fine. The checkpoint is what makes the confidence trustworthy.

## 4. File map

| File | Purpose |
|---|---|
| `01-REQUIREMENTS.md` | What is being built, module by module, with acceptance criteria |
| `02-TECH-STACK-AND-SKILLS.md` | Exact libraries, versions, and algorithms to implement |
| `03-UIUX-RULES.md` | Design system and interaction rules for the frontend |
| `04-BUILD-PLAN.md` | Week-by-week, day-by-day task breakdown |
| `05-GIT-WORKFLOW.md` | Commit/push discipline, authorship, branch rules |
| `06-AUDIT-PROTOCOL.md` | Self-check procedure and cadence |
| `07-PROGRESS-STATE.md` | Living log — current phase, done/in-progress/blocked, updated every session |
| `08-OPEN-QUESTIONS.md` | Questions for the human, logged not asked interactively |

## 5. End-of-session checklist (do this before ending any working session)

1. Update `07-PROGRESS-STATE.md` — what got done, what's half-finished and exactly where
   it was left off (be specific enough that a stranger could continue from your notes).
2. Make sure the working tree is committed — no uncommitted changes left dangling.
3. Push, per `05-GIT-WORKFLOW.md`.
4. If `08-OPEN-QUESTIONS.md` has new entries, say so explicitly in your final message of
   the session so the human sees them.
