# ResolveMergeToolCrash — `merge --resolve` crashed opening the merge tool for any repo whose id isn't its name

*Created: 2026-09-18*

*Branch: main*

> **Owner report — 2026-09-18**, running
> `cgitsync merge --all --resolve memory-dev` on this project's own tree:
> the run merged `DocComplexGitSync` and `.localSpec` cleanly, stopped at a
> real conflict in `.memory`, then crashed with
> `KeyError: '.memory'` instead of opening a merge tool or printing manual
> resolution instructions. *"It is not acceptable to crash like that."*

## What was observed

```
merged DocComplexGitSync <- memory-dev
merged .localSpec <- ComplexGitSync_memory-dev
stopped at .memory: lgr/000095.toml, lgr/000096.toml, lgr/HEAD
not reached: ComplexGitSync
Traceback (most recent call last):
  ...
  File ".../orchestre.py", line 3455, in open_merge_tool
    repo = registry.get(repo_name)
  File ".../git_tree.py", line 470, in get
    return self.repos[repo_id]
KeyError: '.memory'
```

The preflight and the partial merge both worked correctly — two
repositories genuinely merged, the tree was correctly left partly merged
(as `--resolve` documents it can be), and the conflict was correctly found
and left in `.memory`'s worktree. Only the very last step — opening a
merge tool for the user to resolve it — crashed.

## Root cause

`operations.py::merge_tree_one_at_a_time` reports where it stopped as
`ResolveOutcome.stopped_at = repo.name` — the repository's **display
name**, exactly what the CLI prints ("stopped at .memory: ..."). The CLI
(`cli/expert.py::_execute_merge_resolve`) then handed that same value
straight to `ComplexGitSyncClient.open_merge_tool(repo_name)`, which did
`registry.get(repo_name)` — a lookup by **`repo_id`**, not by name.

The two are different strings for any repository whose id is not simply
its own name — which is every mounted repository: `repo_id` is built by
`git_tree.py::make_repo_id()` as `"<parent_id>:<relative_path>"`, so
`.memory`'s id is `"root:.cgitsync/.memory"`-shaped, never the bare string
`".memory"`. The root repository has the identical mismatch
(`repo_id="root"`, `name=<project name>`) — a `--resolve` run that
happened to stop at the root instead would have crashed exactly the same
way, and there is no test that ever exercised this end-to-end call, only
`ResolveOutcome.stopped_at`'s own value in isolation.

## The fix

`ResolveOutcome` now carries both: `stopped_at` (the name, for printing,
unchanged) and `stopped_at_id` (the `repo_id`, for lookup). The CLI passes
`stopped_at_id` to `open_merge_tool`. `open_merge_tool` itself now catches
a bad lookup and raises a clear `GitSyncError` naming the mistake instead
of letting a bare `KeyError` reach the user — so a future caller that
repeats this mistake gets a message, not a traceback.

**Touches:** `operations.py` (`ResolveOutcome`, `merge_tree_one_at_a_time`),
`orchestre.py` (`open_merge_tool`), `cli/expert.py`
(`_execute_merge_resolve`).

## Acceptance

- `merge_tree_one_at_a_time` reports `stopped_at_id` as the repository's
  real `repo_id`, distinct from its display name whenever they differ.
- `ComplexGitSyncClient.open_merge_tool(outcome.stopped_at_id)` finds the
  repository and does not raise `KeyError`, for a repository whose id
  differs from its name (root included, not only mounted repos).
- Calling `open_merge_tool` with a display name instead of an id raises a
  clear `GitSyncError`, never a bare `KeyError`.
- `pixi run lint` and `pixi run test` pass.

## What this does not cover

- **Resolving `.memory`'s actual conflict** on this project's own tree
  (`lgr/000095.toml`, `lgr/000096.toml`, `lgr/HEAD`) — two independently
  numbered ledger entries colliding is a real content conflict, not a
  crash, and needs the owner's own judgment about which entry (or both,
  renumbered) survives. Left exactly as `--resolve` left it: merged
  repositories stay merged, the conflict sits in `.memory`'s worktree, and
  `ComplexGitSync` (root) has not been merged yet.
- **A general ledger-merge story.** Two branches' memories both writing
  ledger entries independently and then merging is exactly the kind of
  divergent-chain problem `memory-dev_1-1_MemoryArchitecture_DevPlanTicket.md`
  §5 (What this architecture refuses to do) already says is out of scope
  for a local, single-writer chain — this incident is real evidence for
  that section, not a reason to reopen it here.
