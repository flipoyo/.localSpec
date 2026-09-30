# Ticket Summaries

*Created: 2026-09-29*

Summary of all open planning tickets: what each ticket tackles, ranked by current priority.

---

## main_1 — Priority 1: one memory strategy, for users and developers

Re-ranked 2026-09-30 from the owner's short ticket
`ReorderPriority-mem-multiUser`: AutofixBlindSpot is not prioritary before
MemoryArchitecture, UserInstallPath, StateLocking or AsOfRetrieval, and the
owner's idea — a memory is always local; a USER tree holds no private
repository, a DEV tree does and syncs its memory — was adopted.

### main_1-1: UserDevProfile
New, from the owner's idea. A tree holding no private repository is USER, one holding any is DEV, read off `effective_private` in one place; `status` prints `profile=user|dev`; a DEV tree with no memory entry is told its memory is not synced. Decisions answered 2026-09-30: rule in `git_tree.py`; any private repository makes a tree DEV; one shared memory branch; and a DEV tree with no memory is offered, in a terminal, to create one (provider, owner, name asked, repository created with `gh`/`glab`/`tea`, entry added to the `.cgs`), otherwise warned that its work has no memory back-up.

### main_1-2: UserInstallPath
One install command for someone evaluating the tool, without Pixi or a clone. A user install must stay a USER tree: no private repository, local memory only.

### main_1-3: LocalRunLogs
From the owner's answer to MemoryArchitecture's D1: a memory push keeps sending the ledger, States, environments and commit logs, but the run logs stay local. Also fixes a real gap: a fold moves the logs `autofix` reads out of its reach. Decisions answered 2026-09-30: logs already pushed stay; local logs are capped at the last 200.

## main_2 — Priority 2

### main_2-1: StateLocking
Two cgitsync processes in one workspace race on the state area and the ledger, and the loser wins silently. More likely now that developers sync their memories while they work.

### main_2-2: AsOfRetrieval
"What was this tree at time *T*?" — one query on the chain's own order. Design settled; ready to build.

### main_2-3: TicketTreeMove
Five `src/` docstrings cite tickets by their open path, which archiving renames; add the check, then move `DevTickets/` to its own mount.

### main_2-4: AutofixBlindSpot
`autofix` starts from the last logged error, and a commit whose message the shell mangled raises none. Plan: a second, non-error-driven source that inspects a repository's tip commit. Demoted from 1-1 by the owner.

## data-repo — Priority 2: Data Pipeline (Separate Workstream)

### data-repo_2-1 through data-repo_2-7
Seven tickets spanning data schema, backend contract, authoring, materialisation, publication, and acceptance. Together they define how data gets versioned, retrieved, cached, and published within cgitsync as a first-class entity (not just a Git blob).

---

## memory-dev — Priority 2: Memory Workstream (Separate Workstream)

### memory-dev_2-1: Omniscience
The project's own shared journal, whose chain is Git's commit history: appended to by everyone, rewritable by nobody without every clone noticing. Since 2026-09-30 its "everyone" means developers only — a USER memory is never synced.

### memory-dev_2-2: WorkingAreaRename
`.cgitsync/working` → `.cgitsync/.working` (dot-prefix to signal "transient, not a public API"). One-line rename with a migration path for existing workspaces.

---

## Rationale for Reordering

**2026-09-30, MemoryArchitecture closed.** On the owner's word it was archived before M6: its reference role moved to `AdditionalSpecs.md`'s *Memory architecture* section and M6 to Omniscience. D1's answer opened LocalRunLogs at 1-3; UserDevProfile and UserInstallPath moved up to 1-1 and 1-2.

**2026-09-30, from `ReorderPriority-mem-multiUser`.** The owner ranked AutofixBlindSpot below MemoryArchitecture, UserInstallPath, StateLocking and AsOfRetrieval, and proposed one memory strategy for everyone. MemoryArchitecture (reference) and the new UserDevProfile (the rule) went to priority 1 with UserInstallPath, the USER side of the same split; StateLocking, AsOfRetrieval, TicketTreeMove and AutofixBlindSpot follow at priority 2 in that order. The paragraphs below describe earlier reviews; their ranks are the ones of their day.

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
