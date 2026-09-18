# MergeProjectBeforePrivate — merge finishes every project repository before touching any private one

*Created: 2026-09-18*

*Branch: main*

> **Owner correction — 2026-09-18**, after `cgitsync merge --all --resolve
> memory-dev` stopped at a conflict in `.memory` with the project's own
> root repository ("`ComplexGitSync`") not yet reached: *"merge should
> first address the project repo, and after, only after the private one.
> This is what is in the specs but again wasn't implemented properly cause
> we stopped in the middle of the road on a --private/local while project
> root remains unmerged."*

## What was observed

```
merged DocComplexGitSync <- memory-dev
merged .localSpec <- ComplexGitSync_memory-dev
stopped at .memory: lgr/000095.toml, lgr/000096.toml, lgr/HEAD
not reached: ComplexGitSync
```

`ResolveMergeToolCrash_DevPlanTicket.md` (same session, filed first) fixed
the crash this run also hit. This ticket is the second, independent
problem in the same run: even without the crash, the tree was left with
two private/local repositories merged and the **project's own root
repository not even attempted**, because a real conflict in a private
repository (`.memory`) happened to come first in the traversal order.

## Root cause

`--all` (`RepoScope.WRITABLE`) merges the project's own repositories and
its writable configuration repositories "in one pass" — but that pass was
a single flat `iter_tree_leaf_first(tree, scope)` walk over the *union* of
both, ordered by physical mount position in the tree, not by which kind of
repository each one is. `.memory` and `.localSpec` are both mounted as
children of the root, exactly like any project leaf would be, so a
leaf-first walk visits them in whatever order they happen to sit in —
ahead of the root either way, since leaf-first always visits the root
last, but with no guarantee about *which other leaves* (project or
private) come before it.

The result: a conflict in a private repository can leave this project's
own root — the thing the whole tree exists to synchronise — completely
untouched, while private configuration repositories the project merely
depends on have already moved. Backwards, and exactly what the owner's
correction names.

## The fix

A new `operations.py::_iter_merge_scope_project_first(tree, scope)`
replaces the raw `iter_tree_leaf_first(tree, scope)` call in every merge
function: it walks `RepoScope.PROJECT` first (leaf-first, root last within
that half), then `RepoScope.PRIVATE` (leaf-first, again). `PROJECT` and
`PRIVATE` never overlap, so nothing is yielded twice, and a `scope` of
exactly `PROJECT` or exactly `PRIVATE` behaves exactly as before —
this only changes anything when `scope` is `WRITABLE` (`--all`), the one
case that ever mixes the two.

Applied to all three merge entry points: `merge_tree` (the atomic,
all-or-nothing merge — ordering could still matter if an unanticipated
failure hits mid-run, per its own docstring), `merge_tree_one_at_a_time`
(`--resolve`, where a stop really can happen), and `merge_into_tree`
(`--into`).

**What this does not change:** `merge_tree`'s and `merge_into_tree`'s
own whole-scope preflight, which already checks every repository before
merging any of them — that guarantee (nothing merges if anything would
conflict) is unaffected; this ticket only orders what happens once the
preflight has already said yes, and what `--resolve` walks when it hasn't.

## Acceptance

- `merge --all` (any of the three merge modes) processes every project
  repository, root included, before touching any private/local one.
- `test_one_writable_pass_merges_both_halves_project_first` (renamed from
  `test_one_writable_pass_merges_both_halves`) asserts the corrected order.
- `test_resolve_all_reaches_the_project_root_before_a_private_conflict` is
  the regression test for the exact field failure: a private repository
  conflicting under `--all --resolve` no longer leaves the project root
  in `not_reached`.
- `pixi run lint` and `pixi run test` pass.

## What this does not cover

- **The `.memory` ledger-fork conflict itself**, resolved separately and
  by hand on this project's own tree (two independently-numbered chains
  cannot be reconciled by a text merge without rewriting an already-hashed
  entry — kept, not rewritten, on `ComplexGitSync_memory-dev` by name).
- **`add`/`commit`/`push`'s own scope ordering.** Not reported as broken,
  not touched here — `iter_write_scope` already routes those three
  differently for reasons specific to them (memory-mount exclusion during
  their own sweep), and changing their order without a reported problem
  would be scope creep on an already eventful ticket.
