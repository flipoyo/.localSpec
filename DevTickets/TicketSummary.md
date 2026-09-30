# Ticket Summaries

*Created: 2026-09-29*

Summary of all open planning tickets: what each ticket tackles, ranked by current priority.

---

## main_1 — Priority 1: three structural goals

Reorganised 2026-09-30 around the owner's three goals. Every priority-1
ticket serves exactly one of them; anything that served none moved to
priority 2.

| Goal | Tickets |
|---|---|
| **2. Constrained agentic behaviour** — no more week-long failures | 1-2 AutofixBlindSpot (AgentGuardrails, its other half, is done and archived) |
| **1. Class-first package, CLI-only public exposure** | none open: ClassFirstPackage and ModulePackagisation are both done and archived |
| **3. A clear nested/standalone frontier** | 1-1 DefaultUserMemory (InstallFrontier, its other half, is done and archived) |

### main_1-1: DefaultUserMemory
`install.cgs` mounts no private repository by design, so a user install has a `.cgitsync/` that accumulates states, logs and ledger entries with **no `.memory` repository to fold them into** — the record exists and can never become one. Plan: create it automatically, locally, with no remote, on the first command that records something; the `.cgs` overrides the default; the branch is the one `memory_branch()` already computes, so publishing later needs no rename; and a defaulted memory is never pushed, because publishing is a developer's privilege. Branch `main`, not `memory-dev`: this only adds a default, it migrates no stored format.

### main_1-2: AutofixBlindSpot
`autofix` starts from the last logged error, and a commit whose message was mangled by the shell raises none — `git commit` succeeded. Plan: a second, non-error-driven `Situation` source that inspects a repository's tip commit directly. Ranked last because AgentGuardrails' commit-message check removes the common path (a commit made *by* `cgitsync`); this ticket covers what it cannot reach, a bare `git commit` outside the tool.

### Sequencing

Four tickets landed in order: AgentGuardrails, ClassFirstPackage, ModulePackagisation, then InstallFrontier (the nested/standalone frontier is enforced: `initialise` and `bootstrap` each refuse the other's job by name, both take a `.cgs` or a `.gts`, and a State is a `.gts` only).

1. **1-1 DefaultUserMemory** edits `orchestre/memory_commands.py`; its class-work dependency (`memory/repository.py`) is already satisfied, and the install path it touches now has the frontier rule to build on.
2. **1-2 AutofixBlindSpot last.**

## main_2 — Priority 2: Architecture & Long-Term

### main_2-1: MemoryArchitecture
A project's memory — the ledger, states, environment records — lives locally and is answerable from one place. Four work packages: finish the typing contract, add a retrieval interface that pairs with AsOfRetrieval, wire everything through ClockProtocol for full determinism, add verification that a ledger's own hash-chain is unbroken.

### main_2-2: UserInstallPath
Separate install stories: Pixi for contributors (full dev environment), one command for end users (just the tool + docs). One work package: move Pixi/editable-package logic into contributor docs and a separate `Makefile`/shell script, leaving the public `install.cgs` self-contained.

### main_2-3: StateLocking
Two cgitsync processes touching one workspace: who wins? Needs a lightweight per-workspace lock (directory-level advisory lock, or a marker file) and a timeout so a dead process doesn't block forever. Two work packages: add the lock primitive, add backoff + logging when a lock is held.

### main_2-4: TicketTreeMove
Merged with `shortTickets/mv-tickets.md`: move `DevTickets/` out of the `.localSpec` mount into its own `.dev` mount, so the private repos split by purpose — specifications in `.localSpec`, the planning surface in `.dev`. Paired with the original CitationRot work because the move rewrites every `.localSpec/DevTickets/...` path in `src/` and every relative link inside the tickets at once. Build the link check first, then move, then re-run it: that turns the largest breakage this tree can suffer into a list the check prints.

### main_2-5: AsOfRetrieval
"What was this tree at time *T*?" — one query built on the chain's own order and the monotonicity check UniversalClock landed. Moved down from priority 1 on 2026-09-30: it serves none of the three structural goals, blocks nothing, and nothing waits on it. Ready to pick up whenever.

## data-repo — Priority 2: Data Pipeline (Separate Workstream)

### data-repo_2-1 through data-repo_2-7
Seven tickets spanning data schema, backend contract, authoring, materialisation, publication, and acceptance. Together they define how data gets versioned, retrieved, cached, and published within cgitsync as a first-class entity (not just a Git blob).

---

## memory-dev — Priority 2: Memory Workstream (Separate Workstream)

### memory-dev_2-1: Omniscience
Record every observable fact about a cgitsync run (not just errors, but timing, environment, which tickets were served, which agents acted). Separate ledger from the state chain; enables diagnostics + analytics over the project's own development.

### memory-dev_2-2: WorkingAreaRename
`.cgitsync/working` → `.cgitsync/.working` (dot-prefix to signal "transient, not a public API"). One-line rename with a migration path for existing workspaces.

---

## Rationale for Reordering

**2026-09-30 — reorganised around three structural goals.** (Ranks in this paragraph and the next are those before AgentGuardrails was archived and the pile compacted.) See the table
and sequencing notes under *main_1* above. Six tickets became five: the
`DevSpecs`-in-digest work split along its natural seam (write the rules
down → 1-1; correct the code → 1-2), `AutofixCommitHygiene`'s prevention
half joined 1-1 while its detection half stayed as 1-5, and three tickets
about the install path (`InitialiseNonGitRoot`, `ReinforceGitTreeState`,
`PrivateLocalBranchAtClone`) merged into 1-4 — the third's own diagnosis
concludes that standalone never shows its bug, which is the frontier the
other two draw.

**The last two short tickets landed 2026-09-30.** `memory-install` became
1-5 DefaultUserMemory, under goal 3 — *publishing a memory is a DEV
privilege* is a behavioural difference between the two install
configurations — kept out of 1-4, which already merges three tickets.
`mv-tickets` folded into 2-4, renamed TicketTreeMove, because the move and
the stale-citation check are one job in the right order. `shortTickets/` is
now empty.

**InstallFrontier archived 2026-09-30**, compacting the priority-1 ranks a fourth time (1-2..1-3 became 1-1..1-2). **ModulePackagisation archived 2026-09-30**, compacting the priority-1 ranks a third time (1-2..1-4 became 1-1..1-3). **AgentGuardrails archived 2026-09-30**, after the priority-1 ranks were compacted (1-2..1-6 became 1-1..1-5). **ClassFirstPackage archived the same day**, compacting them again (1-2..1-5 became 1-1..1-4).

**AsOfRetrieval moved to main_2-5.** It serves none of the three goals, is
built on machinery that already exists, blocks nothing, and nothing waits
on it.

**CitationRot stays at main_2-4** — a maintenance task (fix five links, add
a test), not a structural weakness.

**Priority-2 tickets** are solid designs with no owner blockers and can land
in any order. `data-repo` and `memory-dev` are separate workstreams,
unblocked by priority 1 finishing.
