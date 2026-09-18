# RebootErasedDiscovery — `memory reboot` left nothing for `discover_gts_path()` to find

*Created: 2026-09-18*

*Branch: main*

> **Owner report — 2026-09-18:** *"cgitsync is bugged since you reboot the
> memory. The working gts disappeared. It is a serious bug to erase the
> working gts when rebooting memory."*

## What was observed

Right after `cgitsync memory reboot` ran on this project's own tree,
every ordinary command broke:

```
$ pixi run cgitsync status
cgitsync status: No .gts snapshot found under CGSHOME/.cgitsync: .../.cgitsync
(CGSHOME came from current directory). Run 'cgitsync initialise' first,
or pass --gts FILE explicitly.
```

`cgitsync commit --private --dry-run` failed the identical way. The
ticket's own new revision commit had to be made with a bare `git commit`
inside `.localSpec`, because `cgitsync commit --private` could not even
discover the tree to know what `--private` meant.

## Root cause

`memory reboot`'s step 4 (`memory-dev_1-4_MemoryReboot_DevPlanTicket.md`
§1) clears `state/`, `lgr/`, `logs/`, `commit-logs/` from the fresh
branch, by design, so the branch's eventual first commit is a true
beginning rather than the old history re-committed under a new name. Step
1 had already folded everything pending into the branch being archived,
so `.cgitsync` (pending) was also empty by the time step 4 ran.

The result: **no `.gts` file existed anywhere** — not in
`.cgitsync/.memory/state` (just cleared), not in `.cgitsync/state`
(already folded away). `snapshot_resolver.discover_gts_path()` has three
fallbacks — the ledger, the legacy register, "most recent `.gts` on
disk" — and all three come up empty when there is no State at all. Every
command that starts by discovering a `.gts` (which is effectively every
command) failed immediately, including read-only ones (`status`,
`verify`) that never asked to touch the memory in the first place.

This was a real gap in the original ticket's own design, not a
regression introduced afterward: "clear the memory's history" and "leave
the workspace usable" were never checked against each other, because
nothing in that ticket's acceptance criteria ran an ordinary command
*right after* a reboot.

## The fix

`memory_reboot()` now writes one fresh State immediately after clearing
the fresh branch's tracked content — `self.write_gts_snapshot(command_origin="memory_reboot")`,
using the same `self.registry` the method already loaded at the top. This
writes into the *pending* half (`.cgitsync/state` and `.cgitsync/lgr`),
exactly where an ordinary command's own write already lands — never onto
the fresh branch itself, so "nothing is committed on the fresh branch"
(§1 step 4's own promise) still holds. The State this writes describes
the tree *as it is at the moment of the reboot*, not any of the archived
history — a reboot still starts the memory's own record over; it no
longer also breaks the tool's ability to read the tree that record is
about.

## Repairing this project's own workspace

The code fix only protects *future* reboots. This workspace had already
gone through the broken one, so it needed a one-time manual repair:
`ComplexGitSyncClient.load_cgs(examples/complexgitsync4dev.cgs,
project_root=<cgshome>, discover_nested=True)` followed by
`write_gts_snapshot()` — the same two calls `load()` makes internally,
with an explicit `project_root` because the `.cgs` sits under `examples/`
while the tree's actual root is the current directory
(`load_cgs`'s own docstring names exactly this case, citing
`PullOutsideRoot_DevPlanTicket.md`). `cgitsync status`/`verify` both
answer normally afterward; `verify` reports `status=verified`,
`findings=0`.

`.cgitsync/.memory` itself is still commit-less on its fresh branch —
unaffected by this fix, since folding and committing it is `memory
push`'s job, which pushes to a remote and was not run, per the standing
rule that nothing pushes without being asked.

## Acceptance

- `cgitsync status`, `cgitsync verify`, and any other read-only command
  succeed immediately after `cgitsync memory reboot`, with no other
  command run in between.
- The State `memory reboot` writes describes the tree's actual current
  content — the same thing an ordinary `checkout`/`commit` would have
  written, not a copy of anything from the archived branch.
- The fresh branch itself remains commit-less after `memory reboot`
  returns — this fix writes to the pending half only.
- `pixi run lint` and `pixi run test` pass.
