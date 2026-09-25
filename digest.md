# Digest — every MUST/NEVER rule in the spec tree, one line each

*Created: 2026-09-25*

## Abstract — read this first

**What this document is.** Every binding rule this project's spec tree
states, compressed to one line each, with a citation back to its source.
No rationale, no abstract, no example — that stays in the source, on
purpose.

**Why it exists.** `main_1-7_SpecTree_DevPlanTicket.md` §1: a rule that is
correctly stated but two hops behind a pointer, read once, competes badly
against a freshly-repeated instruction sitting one token away from where
it needs to win. This file is what a session loads in full, every time,
so the rule is adjacent instead of buried — see `CLAUDE.md`'s own
pointer to this file for the instruction to do so.

**What you will find.** One bulleted list, grouped by topic, each line
ending in a source citation `` `File.md` §N ``. `scripts/spec_tree.py
--check-digest` verifies every citation still resolves inside the spec
tree; it cannot verify a line still says what its source currently says
— that is this file's own editorial upkeep, not a graph property.

**Who it is for.** Any agent, at the start of any session in this
repository, before drafting a commit, a push, a version bump, or a
ticket.

**What you need to do with it.** Read it in full — it is short by
design. When a line and its source disagree, the source wins; fix this
file to match, in the same change that noticed the drift.

---

## Attribution and commits

- An agent is never credited on a commit, merge, or pull request — no co-authorship trailer, no "generated with" line, in any repository of the tree. — `AgentConduct.md` §3
- A self-history/accounting record of an agent's work must never reach a public repository, and nothing in it may be copied into one. — `AgentConduct.md` §3
- Never push to a remote without being asked; deliver the commit message and let the owner decide whether to commit. — `AgentConduct.md` §1
- A commit message starts with `<project-name><version>`, is one message reused for every repository the change touched, plain English, three lines at most. — `AgentConduct.md` §2

## Before a task is finished

- `pixi run lint` and `pixi run test` must both pass before any task is considered closed. — `CLAUDE.md` §1
- Run `pixi run bump-build` for any change under `src/`. — `CLAUDE.md` §1
- `cgitsync status`, run from the tree's own root, must show `errors=0` before a task is finished. — `CLAUDE.md` §1
- Never hand-edit a version field; run `pixi run bump-version` — the one command that syncs all of them. — `CLAUDE.md` §1
- Document any new CLI command in the README command table and its client method in the API docs. — `CLAUDE.md` §1

## Implementing a ticket

- Implementing a ticket from `openTickets/` takes a worker agent and an independent orchestrator agent — one making the change, the other quoting it against the checklist. — `AgentConduct.md` §4
- A planning ticket's filename branch prefix and its own `*Branch:*` line must agree. — `TICKETLIFECYCLE.md` §2.3

## Architecture — single-implementation rules

- `.gts` prevails over `.cgs`: a hand-edited `.cgs` must never widen write access behind an attested snapshot. — `AdditionalSpecs.md` §Architectural Overview
- `parse_repo_id()` in `cgs_format.py` is the only repo-identifier parser in the codebase. — `CLAUDE.md` §Architecture boundary
- `git_branch.py` is the only implementation of the `.cgs` branch fallback chain and the privacy rule. — `CLAUDE.md` §Architecture boundary
- `git_runner.py` is the sole module allowed `import subprocess`. — `CLAUDE.md` §Architecture boundary
- `universal_clock.py` is the sole reader of the real wall clock, PID, or entropy source; every other module takes an injected `ClockProtocol`. — `CLAUDE.md` §Architecture boundary
