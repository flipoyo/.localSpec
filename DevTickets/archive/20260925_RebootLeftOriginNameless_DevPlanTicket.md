# RebootLeftOriginNameless — `memory reboot` left origin without the project's branch until the next `memory push`

*Created: 2026-09-25*

*Branch: main*

> **Owner report — 2026-09-25, in conversation:** *"i did yesterday evening
> a memory reboot from cgitsync on another machine just before to back up
> and restart the treatment of a DevPlanTicket that is still running. For
> this machine today when i made a bootstrap of
> examples/complexgitsync4dev.cgs it didn't work because the branch
> 'ComplexGitSync' of .memory didn't exist and the 'main' one didn't
> contained any .cgs and especially config-memory.cgs. I had to trick the
> system for changing the default branch in complexgitsync4dev.cgs and use
> git on .memory to recreate the branch ComplexGitSync and propagate it
> upstream origin."*

## What was observed

`memory reboot` ran on one machine, then nothing else touched that
memory before a second machine ran `cgitsync bootstrap
examples/complexgitsync4dev.cgs`. Bootstrap fell back past `.memory`'s
`default_branch` (`ComplexGitSync`) to its `fallback_branch` (`main`) —
`git_branch.py`'s own chain, working exactly as designed — but `main` had
never held this project's memory at all, so it held no `config-memory.cgs`
either, and self-history's nested discovery inside `.memory` had nothing
to find. The owner had to hand-repair it: change
`complexgitsync4dev.cgs`'s default branch as a workaround, then use `git`
directly against `.memory` to recreate `ComplexGitSync` and push it.

## Root cause

`memory_reboot()`'s step 3 (`memory-dev_1-4_MemoryReboot_DevPlanTicket.md`
§1) renames the current branch on origin to its archived name and then
**deletes the old name from origin** (`push_ref_as` then
`delete_remote_branch`, in that order, so the commits stay reachable
under some name throughout). Step 4 then builds a fresh, minimal local
branch under the original name and — per that ticket's own design and
`20260918_RebootErasedDiscovery_DevPlanTicket.md`'s later fix — commits
one genesis State to it, but never pushed it: *"nothing is pushed here,
the same way `memory_push`'s own commit step never pushes on its own —
the next `memory push` ... is what sends it."*

That reasoning holds for an ordinary day's commits, where "offline is the
normal case" is the whole point of `memory_push` being a separate,
deliberate command. It does not hold for reboot's own genesis commit,
because reboot itself already deleted the *only* thing that made the old
name resolvable on origin. From the moment `delete_remote_branch` returns
to the moment somebody happens to run `memory push`, origin has no ref
named `<branch>` at all — not "empty," *absent*. A bootstrap on any other
machine in that window never sees the branch exists, falls back past it
in the chain `git_branch.py` already implements correctly, and lands
somewhere that was never rebooted and never held this project's `.cgs`.
The window's width was never bounded: an owner who reboots right before
switching machines, exactly as reported here, can leave it open
indefinitely.

This is the same failure mode the original short ticket
(`archive/.closedUserTicket/20260925_debug-memory-reboot.md`) first
described — "the gitRepo is left without any 'project-name' branch ...
impossible to reload a project" — for the *local* half of which
`RebootErasedDiscovery` was believed to be the complete fix. It was
complete for `cgitsync status` reading the local checkout; it was never
checked against a second machine reading only origin.

## The fix

`memory_reboot()` now pushes the fresh branch's genesis commit to origin
immediately, the same call `memory_push` itself makes
(`self.git_runner.push(mount, ref_name=current_branch,
set_upstream=True)`), right after committing it. The window with no
`<branch>` ref on origin is now bounded by this method's own running
time — the same guarantee step 3 already gives the *archived* branch
(pushed under its new name before the old one is removed) extended to
the *fresh* branch as well.

## Acceptance

- `cgitsync memory reboot`, run against a real remote, leaves the
  project's branch name resolvable on origin the moment it returns — a
  `git clone --branch <name>` from a second checkout succeeds immediately
  afterward, with no other command run in between.
- That clone holds `.cgs/<project>-v<N>.cgs` and exactly one ledger
  entry — never the archived history, never `commit-logs/`.
- `pixi run lint` and `pixi run test` pass, including
  `test_the_fresh_branch_is_pushed_by_reboot_itself` (renamed from
  `..._is_not_pushed_..._itself`, whose assertion this fix inverts on
  purpose).

## What this does not change

- The archive step's own ordering and guarantees
  (`memory-dev_1-4_MemoryReboot_DevPlanTicket.md` §1 step 3) are
  untouched — this fix only extends "never leave a name unreachable, even
  for a moment" to the branch's fresh half.
- `memory_push`'s own commit-then-push-only-when-asked behaviour for
  *ordinary* commits is untouched; only reboot's own genesis commit,
  which follows a delete this same method just performed, pushes
  unconditionally.
