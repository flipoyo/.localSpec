# MemoryScopeExclusion — the memory can never come out clean from a sweep that records itself into it

*Created: 2026-09-17*

*Branch: memory-dev*

> **Owner direction, in the short ticket
> (`.localSpec/DevTickets/archive/.closedUserTicket/20260917_memory-dirty.md`):**
> *"the memory repo remains in dirty state after add --all commit --all,
> push --all. add --private modifies status but commit and push go back to
> dirty."*

## Abstract — read this first

**The one-line version.** `.memory` was declared `private = true, writable
= true`, the same as `.localSpec`/`.claude` — so `add`/`commit`/`push`
swept it into their own scope. Every one of those commands also records
itself *into* `.cgitsync` after it runs, so the record of the very sweep
that just committed the memory is never part of what got committed. The
memory could never come out clean from an ordinary sweep, structurally,
no matter how many times you ran one.

**What this document is.** The measured cause, and the fix: the memory is
excluded from every write scope but `ALL`, so ordinary commands stop
touching it — `memory push` already writes it directly, bypassing scope
entirely, and loses nothing.

**Why it exists.** The owner's own words: three commands ran, in the
documented order, and the memory was dirty after every one. That reads as
a broken promise, because it is one.

**What you will find.** §1 why this cannot be fixed by reordering. §2 the
fix. §3 what changes and what does not. §4 acceptance, measured on this
project's own tree.

**Who it is for.** Whoever reads this later, wondering why the memory is
excluded from `--private`/`--all`.

```mermaid
graph TD
    A["commit --all<br/>sweeps .memory in"] --> B["commit_tree() commits it"]
    B --> C["write_gts_snapshot()<br/>records THIS commit, into .cgitsync"]
    C --> D[".memory is dirty again<br/>by exactly its own record"]
    E["commit --all<br/>.memory excluded<br/>YOU ARE HERE"] --> F["never touches .cgitsync at all"]
    F --> G["memory push, later,<br/>commits everything in one pass"]

    classDef here fill:#1565C0,color:#fff,stroke:#111,stroke-width:2px;
    class E here;
```

---

## 1. Why reordering cannot fix this

A write command's own record — the State and ledger entry
`write_gts_snapshot` produces — needs facts that do not exist until *after*
the git operation ran: the resulting commit SHAs, whether anything moved,
what the tree looks like now. So the sequence inside `orchestre.commit()`
is necessarily commit-the-scope, *then* record-what-happened, and that
recording step is itself new content written into `.cgitsync` — which, if
`.cgitsync` was part of the scope that just committed, is now sitting there
uncommitted. `push` follows the same shape.

This is not an ordering bug to fix by moving a line. It is what happens
whenever the repository being swept is also the repository that receives
the sweep's own record. The only way out is to stop sweeping it in.

Measured before this ticket: `pixi run cgitsync commit --all "…"; pixi run
cgitsync push --all` left `.memory` reporting `dirty` afterward, every
time, on this project's own tree — matching the owner's report exactly.

## 2. The fix

**`add`/`commit`/`push` are the only commands that exclude the memory —
`RepoScope` itself does not know about it.** A first version of this fix
put the exclusion in `RepoScope.includes()`, and it was wrong: `RepoScope`
is shared by `merge`, `tag` and `freeze-release` too, and excluding the
memory there silently broke something already shipped and relied on —
`merge --private`/`--all` reconciling the memory's branches across a
project branch merge, exactly the way it already reconciles
`.localSpec`/`.claude`. Measured before reverting that version:
`merge memory-dev --into main --all`'s dry-run plan simply stopped naming
`.memory` at all.

So the exclusion is narrower, and lives one level up, in a new
`operations.iter_write_scope`:

```python
def iter_write_scope(tree, scope):
    return (repo for repo in iter_tree_leaf_first(tree, scope)
            if not repo.is_memory_mount)
```

`add_tree`, `commit_tree` and `push_tree` — and only those three — call
this instead of `iter_tree_leaf_first(tree, scope)` directly. `merge_tree`,
`merge_into_tree`, `tag_tree`, `freeze_release_tree`, and every preflight
check keep using `iter_tree_leaf_first` unchanged, so the memory stays
exactly as reachable to them as `.localSpec`/`.claude` are.

`is_memory_mount` (`WorkingRepo`, `git_repo.py`) is never declared in a
`.cgs` and never read back from a `.gts` — recognised the same way the
tool already recognises the memory everywhere else, by where it sits
(`relative_path == memory.repository.MOUNT_PATH`), computed once when the
registry is built from either document (`registry.py`).

This costs `memory push`/`memory adopt` nothing: both already operate
directly on `memory_mount_path(workspace)` through `git_runner`, never
through `RepoScope` at all.

## 3. What changes, and what stays the same

- **`add`, `commit`, `push` — with no flag, `--private`, or `--all` — never
  touch `.cgitsync` again.** Only `memory push` (and, later,
  `memory reboot`) does.
- **`merge`, `tag`, `freeze-release` are unaffected.** `merge --private`/
  `--all` still reconciles the memory's branches across a project-branch
  merge, the same way it always has for `.localSpec`/`.claude` — this is
  the thing the first version of this fix broke and this version restores.
- **`cgitsync status` still reports `.memory` honestly.** It reads every
  repository's real git status independent of scope, so a memory with
  unpushed content still shows `dirty` — correctly: that is what tells a
  reader `memory push` has something to do. What changed is that `add`/
  `commit`/`push` no longer *pretend* to have handled it.
- **The SCOPE column keeps saying `private/local`.** The memory did not
  become read-only or shared; it is still entirely the workspace's own to
  write, only through a different command (or through `merge`, for the
  cross-branch case).

## 4. Acceptance — measured, not asserted

On this project's own tree, 2026-09-17:

```
$ cgitsync add --all && cgitsync commit --all "…" && cgitsync push --all
# .memory's HEAD is unchanged throughout — never touched.

$ cgitsync memory push
committed=19 path(s)
$ cgitsync status
.memory   .cgitsync   private/local   …   clean   synced
```

And, restoring what the first version broke:

```
$ cgitsync merge main --into memory-dev --all --dry-run
plan_order=… -> .memory: ComplexGitSync_memory-dev <- ComplexGitSync (…) -> …
```

`.memory` is back in the plan.

Plus `tests/unit/test_repo_scope.py`'s new `TestIterWriteScope`: the
memory is absent from `iter_write_scope(tree, PRIVATE)` but present in
plain `iter_tree_leaf_first(tree, PRIVATE)` — the two commands that use
each. `test_each_scope_selects_what_the_documentation_promises` confirms
`RepoScope` itself still includes `.memory` in `PRIVATE`.

`pixi run lint` and `pixi run test` pass — 1517 tests.
