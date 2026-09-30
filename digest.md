# Digest — every MUST/NEVER rule in the spec tree, one line each

*Created: 2026-09-25*

## Abstract — read this first

**What this document is.** The binding rules of this project's spec tree,
compressed to one line each, with a citation back to its source. No
rationale, no abstract, no example — that stays in the source, on purpose.
**`DevSpecs.md` comes first**, because it states what the package *is* —
one monolithic package, domain logic in classes, one CLI as the only way
in — and every other rule is a rule about changing that thing.

**Why it exists.** `main_1-7_SpecTree_DevPlanTicket.md` §1: a rule that is
correctly stated but two hops behind a pointer, read once, competes badly
against a freshly-repeated instruction sitting one token away from where
it needs to win. This file is what a session loads in full, every time,
so the rule is adjacent instead of buried — see `CLAUDE.md`'s own
pointer to this file for the instruction to do so.

**What you will find.** One bulleted list, grouped by topic, each line
ending in a source citation `` `File.md` §N ``. `scripts/spec_tree.py
--check-digest` verifies every citation still resolves inside the spec
tree, **and that every declared spec is cited by at least one line** — a
spec that states rules and is never cited is the gap this file once had
(it held no line from `DevSpecs.md` at all). A spec that genuinely states
no rule is named in `spec_tree.py`'s `DIGEST_EXEMPT`, with its reason. The
check cannot verify a line still says what its source currently says —
that is this file's own editorial upkeep, not a graph property.

**Who it is for.** Any agent, at the start of any session in this
repository, before drafting a commit, a push, a version bump, or a
ticket.

**What you need to do with it.** Read it in full — it is short by
design. When a line and its source disagree, the source wins; fix this
file to match, in the same change that noticed the drift.

---

## What this package is

- The project is one self-contained deliverable: no plugins, adapters, or loosely coupled extension points unless the project's purpose is to be a framework. — `DevSpecs.md` §Monolithic Canonical API
- Domain concepts are classes that own their own validation, serialisation and lifecycle; no free-standing function mutates shared state. — `DevSpecs.md` §Object-Oriented Design
- Every `.py` has one clear major class that gives the module its name, and at most two or three classes in all. — `AdditionalSpecs.md` §Module shape
- A source file that passes 2000 lines becomes a directory of that name, split so each file keeps one major class. — `AdditionalSpecs.md` §Module shape
- `memory/` and the ledger are class-based: no domain concept there lives in module-level functions. — `AdditionalSpecs.md` §Module shape
- `cli/` is the one exemption from the class rules: it is derived from client methods implemented elsewhere, and it collects arguments and prints. — `AdditionalSpecs.md` §Module shape
- Every entry point shares one implementation — no hidden forks — and CLI behaviour mirrors the Python API one-to-one. — `DevSpecs.md` §Monolithic Canonical API
- A capability exists in both layers or in neither: a `ComplexGitSyncClient` method carries the semantics, `cli/` only collects arguments and prints. — `CLAUDE.md` §Architecture boundary
- Every exported symbol appears in its module's `__all__` and is documented. — `DevSpecs.md` §Object-Oriented Design
- The module shape is measured by `check_oo_conformance.py` against a baseline that only shrinks; never add a module to one of its lists to make the check pass. — `AdditionalSpecs.md` §Module shape
- Configuration and state are exchanged as structured data, never raw string manipulation; every document class carries `to_*`/`from_*` helpers. — `DevSpecs.md` §Interface Conventions
- Python work goes through `pixi` — never bare `pip`, `python -m pip`, or `venv`, in code, docs, or CI. — `DevSpecs.md` §Python Environment and Package Management

## Attribution and commits

- An agent is never credited on a commit, merge, or pull request — no co-authorship trailer, no "generated with" line, in any repository of the tree. — `AgentConduct.md` §3
- A self-history/accounting record of an agent's work must never reach a public repository, and nothing in it may be copied into one. — `AgentConduct.md` §3
- Never push to a remote without being asked; deliver the commit message and let the owner decide whether to commit. — `AgentConduct.md` §1
- A commit message starts with `<project-name><version>`, is one message reused for every repository the change touched, plain English, three lines at most. — `AgentConduct.md` §2
- `cgitsync commit` refuses a message that breaks that rule — wrong prefix, more than three lines, a backtick, a `$(`, or an agent-credit trailer — in a tree that adopts DevSpec, naming the rule it broke. — `CLAUDE.md` §Before committing

## Before a task is finished

- `pixi run lint` and `pixi run test` must both pass before any task is considered closed. — `CLAUDE.md` §1
- Run `pixi run bump-build` for any change under `src/`. — `CLAUDE.md` §1
- `cgitsync status`, run from the tree's own root, must show `errors=0` before a task is finished. — `CLAUDE.md` §1
- Never hand-edit a version field; run `pixi run bump-version` — the one command that syncs all of them. — `CLAUDE.md` §1
- Document any new CLI command in the README command table and its client method in the API docs. — `CLAUDE.md` §1

## Implementing a ticket

- Implementing a ticket from `openTickets/` takes a worker agent and an independent orchestrator agent — one making the change, the other quoting it against the checklist. — `AgentConduct.md` §4
- A planning ticket's filename branch prefix and its own `*Branch:*` line must agree. — `TICKETLIFECYCLE.md` §2.3
- A short ticket is stamped and moved to `archive/.closedUserTicket/` in the same change that satisfies it, and never edited afterwards. — `.agent/.local/.localSpec/DevTickets/README.md` §3
- One concern per commit across agents: a `DELETE`/`MOVE`/`CHANGE` by one role is never bundled with another role's change. — `.agent/.distant/dev-sync/AGENT.md` §Handoff rules

## Documents

- Every Markdown document opens with an abstract carrying a mermaid graph. — `DOCSTYLE.md` §1
- There is one authoritative file per purpose. — `DOCSTYLE.md` §7
- Documents and finishing reports are plain English. — `DOCSTYLE.md` §5
- Documents never carry dated "recent improvements" blocks that rot. — `DOCSTYLE.md` §6

## Architecture — single-implementation rules

- A memory the `.cgs` does not declare is created locally by ComplexGitSync and never pushed, even with a remote added by hand; only `memory adopt` opts in. — `AdditionalSpecs.md` §Architectural Overview
- `initialise` is the nested install and `bootstrap` the standalone one; each refuses the other's job by name before touching the disk. — `AdditionalSpecs.md` §The install frontier
- `.gts` prevails over `.cgs`: a hand-edited `.cgs` must never widen write access behind an attested snapshot. — `AdditionalSpecs.md` §Architectural Overview
- `parse_repo_id()` in `cgs_format.py` is the only repo-identifier parser in the codebase. — `CLAUDE.md` §Architecture boundary
- `git_branch.py` is the only implementation of the `.cgs` branch fallback chain and the privacy rule. — `CLAUDE.md` §Architecture boundary
- `git_runner.py` is the sole module allowed `import subprocess`. — `CLAUDE.md` §Architecture boundary
- `universal_clock.py` is the sole reader of the real wall clock, PID, or entropy source; every other module takes an injected `ClockProtocol`. — `CLAUDE.md` §Architecture boundary
