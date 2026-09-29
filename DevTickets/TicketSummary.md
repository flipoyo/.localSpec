# Ticket Summaries

*Created: 2026-09-29*

Summary of all open planning tickets: what each ticket tackles, ranked by current priority.

---

## main_1 — Priority 1: Core Robustness (Merge-First)

### main_1-3: InitialiseNonGitRoot
`install.cgs` is fine (adding `relative_path = "."` changes nothing). `initialise` never clones the root, and when CGSHOME is not a git checkout it clones the other repos anyway, then fails with a message that names nothing. Plan: refuse up front and point at `bootstrap`, drop the misleading "Try clean-init" hint, document the root-must-exist rule.

### main_1-4: AutofixCommitHygiene
`cgitsync autofix` starts from the last logged error, but a mangled commit message (shell substitution) succeeds at the Git level — never becomes an error, never caught. Four work packages to detect commit hygiene failures without relying on Git's exit code, diagnose shell-quote damage, and let autofix help when a message got corrupted in transit.

### main_1-5: PrivateLocalBranchAtClone
Private/local branch naming rule has two implementations; the privacy-aware one runs after the tree exists, but the blind one runs at first clone — so initialise fails with "no cloneable branch found" for a private repo. Three work packages unify them and add a test that clone works before anything else can run on it.

### main_1-6: AsOfRetrieval
Query: "what was this tree at time *T*?" The chain already records it in order; what's missing is the command. One command, built on two existing pieces: the chain's order + UniversalClock's monotonicity check. Minimal work package, ready to implement, no owner decision needed.

---

## main_2 — Priority 2: Architecture & Long-Term

### main_2-1: MemoryArchitecture
A project's memory — the ledger, states, environment records — lives locally and is answerable from one place. Four work packages: finish the typing contract, add a retrieval interface that pairs with AsOfRetrieval, wire everything through ClockProtocol for full determinism, add verification that a ledger's own hash-chain is unbroken.

### main_2-2: UserInstallPath
Separate install stories: Pixi for contributors (full dev environment), one command for end users (just the tool + docs). One work package: move Pixi/editable-package logic into contributor docs and a separate `Makefile`/shell script, leaving the public `install.cgs` self-contained.

### main_2-3: StateLocking
Two cgitsync processes touching one workspace: who wins? Needs a lightweight per-workspace lock (directory-level advisory lock, or a marker file) and a timeout so a dead process doesn't block forever. Two work packages: add the lock primitive, add backoff + logging when a lock is held.

### main_2-4: CitationRot
Five docstrings in `src/` point at tickets by their open path; those tickets were archived and renamed — paths go dead. Fix: update the five citations + add a CI check that catches it next time. Small maintenance ticket, low architectural impact.

---

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

**Merge issues go first** because they block the owner on real work (main_1-2 was stuck). MergeUX is the blockedpath; AutofixCommitHygiene makes autofix useful for merge fallout; PrivateLocalBranchAtClone is a prerequisite for initialise to work in the merge scenario; AsOfRetrieval is a clean, no-risk add-on that unblocks timeline queries.

**CitationRot moved to main_2-4** because it's a maintenance task (fix five links + add a test), not an architectural weakness. It's worth doing but not before merge robustness is solid.

**Priority-2 tickets** are solid designs with no owner blockers — they can land in any order. Data-repo and memory-dev are separate workstreams, unblocked by priority-1 finishing.
