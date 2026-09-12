# 05 — Git Workflow, Commit Discipline, and Authorship

## First: how authorship actually works (read this before anything else)

Git commit authorship comes from your local `git config`, not from who or what typed the
`git commit` command. Claude Code running on your machine executes git commands as *you* —
it has no separate identity of its own unless you explicitly configure one. There is no
"SSH key for Claude" to set up, and you should never generate or hand over a credential
specifically for an AI tool.

**Verify this yourself, once, before starting (run these in your terminal, not something
Claude Code needs to do for you):**

```bash
git config user.name
git config user.email
```

These must show your actual name and the email address associated with your GitHub account
(check github.com/settings/emails — the email must be verified there for commits to show
your avatar and count toward your contribution graph). If either is wrong or unset:

```bash
git config --global user.name "Vedant Ambre"
git config --global user.email "your-github-account-email@example.com"
```

**Push authentication** (separate from authorship) — confirm you can already push to GitHub
from this machine:

```bash
ssh -T git@github.com
# or, if you use HTTPS + the GitHub CLI:
gh auth status
```

If either of these already works, you're done — Claude Code will push using your existing
authenticated access. If neither works, set up SSH keys or `gh auth login` yourself following
GitHub's own instructions; this is a one-time machine setup step that has nothing to do with
this project specifically, and Claude Code should not be asked to do it for you since it
would need access to credentials it should never hold.

**Sole contributor rule (Ved, 2026-09-13):** Ved is the only contributor to this repository.
Never add `Co-Authored-By:` trailers for Claude or any AI tool to commits, and never add
"Generated with Claude Code" (or similar) to PR descriptions — even if tooling suggests it.

## Commit granularity — the actual target

The goal is **atomic, reviewable commits**, not a specific number. That said, given the
volume of small tasks in `04-BUILD-PLAN.md`, 40–50 commits on a genuinely productive day is
realistic *if* commits are made at the right granularity — roughly: one commit per function
or small cohesive unit added, one commit per bug fixed, one commit per test added, one commit
per refactor. Do not artificially split a single logical change into multiple commits just to
inflate the count, and do not batch a day's work into 3 giant commits either — both defeat
the actual purpose, which is a readable, granular history you can point to later and say
"here's exactly when and why this piece was built."

**One honest caution**: a large number of commits is a side effect of working in small steps,
not a target to optimize for its own sake. If a session naturally produces 15 solid commits
instead of 40, that's a fine day — don't pad it.

## Commit message convention

```
<type>(<module>): <short imperative description>

<optional body — why, not just what, if the change isn't self-evident>
```

Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `perf`.
Module: `discovery`, `conformance`, `scoring`, `roi`, `network`, `simulation`, `nlquery`, `infra`.

Examples:
```
feat(discovery): implement dependency measure calculation for heuristic miner
test(discovery): add synthetic log fixtures for causality classification
fix(conformance): correct token count when case ends mid-loop
docs(readme): add dataset download instructions
```

## Push cadence

- Push after every commit if working on a stable internet connection and the test suite is
  green — this is the safest default and keeps GitHub as an up-to-date backup, not a
  once-a-day afterthought.
- If a commit temporarily leaves the test suite red (e.g., mid-refactor across several
  commits), it's acceptable to push once the suite is green again rather than every single
  commit in that sequence — but do not let more than a handful of commits sit unpushed.
- Always push to a feature branch, never directly to `main` (see branching below).

## Branching strategy

- `main` stays deployable/demo-able at all times.
- One branch per module (`module-a-discovery`, `module-b-conformance`, etc.), matching
  `04-BUILD-PLAN.md`'s week structure.
- Merge to `main` at the end of each week's checkpoint (per `06-AUDIT-PROTOCOL.md`), after
  the full test suite passes on the branch — not before.
- **Never force-push. Never rewrite history on `main`. Never delete a branch with unmerged
  work without being explicitly told to.** These are the destructive-operation red lines from
  `CLAUDE.md` section 2 — if any of these seem necessary, stop and ask, don't proceed.

## What to do if you (Claude Code) are running in an autonomous/background mode

If commits and pushes are happening without a human watching each one in real time:
- Never commit directly to `main`.
- Never use `--force` or `--force-with-lease` under any circumstance in this mode.
- If a push is rejected (e.g., remote has diverged), stop and log it in
  `08-OPEN-QUESTIONS.md` rather than attempting any form of forced resolution.
