# PullOutsideRoot — `pull` breaks on the exact `.cgs` layout this project uses

*Created: 2026-09-17*

*Branch: main*

> **Found, not asked for.** While running
> [MemoryOnboarding](../openTickets/memory-dev_1-2_MemoryOnboarding_DevPlanTicket.md)'s
> §2 step 4 — `cgitsync pull examples/complexgitsync4dev.cgs`, on this
> project's own tree, right after mounting its memory for real — the
> command failed. Twice, on two different errors, after two different
> workarounds.

## Abstract — read this first

**The one-line version.** `cgitsync pull <path>` assumes the `.cgs` file
sits at the tree's own root. `examples/complexgitsync4dev.cgs` — this
project's own developer spec — deliberately does not
(`CLAUDE.md`, *Layout*: *"where a `.cgs` lives never affects the tree it
describes"*), and `pull` breaks on it.

**What this document is.** Two measured failures, in order, on a real
workspace — this one — with what was ruled out for each. Neither root
cause is fully traced; both need a clear head, not a live production tree,
to finish.

**Why it exists.** `.cgitsync/DevTickets/…MemoryOnboarding…`'s own §2.3
tells a reader to use `pull` for exactly this workspace, on exactly this
`.cgs`, as the safe alternative to the destructive commands. That advice
does not currently work.

**What you will find.** §1 failure one, root-caused. §2 failure two,
reproduced but not fully traced. §3 what this means for MemoryOnboarding.
§4 decisions. §5 work packages. §6 acceptance.

**Who it is for.** Whoever picks this up next — the fixes are self-
contained, no owner decision blocks them.

**What you need to do with it.** Read §1 first; it is the one with an
actual fix already found.

---

## 1. Failure one — the tree root is read from the wrong place

```
$ cgitsync pull examples/complexgitsync4dev.cgs
cgitsync pull: [Errno 2] No such file or directory:
'.../cgs-mem-dev/examples/.agentSpec'
```

`examples/.agentSpec` was never supposed to exist — `.agentSpec` lives at
CGSHOME's own root. Traced to
`orchestre.load_cgs`, which `restart` (what `pull` calls) uses:

```python
self.registry = build_registry_from_cgs_document(document, source_path)
```

`build_registry_from_cgs_document` already accepts a `project_root`
override precisely for this case:

```python
root_path = (
    Path(project_root).resolve() if project_root is not None
    else source_path.parent.resolve()
)
```

`load_cgs` never passes it, so every call falls back to
`source_path.parent` — the `.cgs` file's own directory. For
`examples/complexgitsync4dev.cgs` that is `examples/`, not CGSHOME, and
every `relative_path` in the document is then resolved from the wrong
place. Setting `$CGSHOME` explicitly does not help — `resolve_cgshome`
(used only to pick where a *fresh* `restart` would clone things) is a
different function from the one that actually derives the registry's root.

**The fix is narrow**: `restart` (and anywhere else `load_cgs` is called to
re-sync an *already-loaded* tree, rather than to create one) should pass
the already-established root — `self.registry.get(ROOT_REPO_ID).absolute_path`
when a registry is already loaded, else the resolved CGSHOME — as
`project_root`.

## 2. Failure two — a name collision, not yet traced

Working around §1 by copying the `.cgs` to CGSHOME's own root (so
`source_path.parent` is correct) reaches further, then fails differently:

```
$ cgitsync pull ./__tmp_root_copy.cgs
cgitsync pull: [Errno 21] Is a directory: '.../.cgitsync/.cgs'
```

`.cgitsync/.cgs` is a real directory in a workspace with any memory history
— `orchestre.write_gts_snapshot` creates it (`stable_cgs_dir`) to hold one
stable copy of the `.cgs` per branch. Something later in `restart`'s own
sequence — after registry-building succeeds, since no `gts_write` event
appears in the log before the crash this time — tries to treat that same
path as a plain file and write to it directly.

**Ruled out**, by reading the code, not by guessing: `RuntimeStateStore`
(`~/.local/state/ComplexGitSync/snapshots/*.ptr`, unrelated path),
`MasterConfig` (writes `.cgitsync/master.toml`, never `.cgs`). Not yet
found: which call between "registry built" and "command failed" — most
likely `discover_nested_configs()`, since a workspace's own `.cgitsync/.cgs`
directory holds real `*.cgs` files and nothing stops nested-config
discovery from walking into `.cgitsync/` itself and mistaking one of them
for a project repository's own spec.

This needs a debugger or added logging on a disposable workspace, not
another guess against the live one.

## 3. What this means for MemoryOnboarding

Its §2 step 4 — `cgitsync add`, `commit`, `push`, then `pull
examples/complexgitsync4dev.cgs` to let the tree learn about the new mount
— cannot be completed with `pull` until this lands. Steps 0–3 do not
depend on it and are unaffected: **this project's own memory is already a
real, pushed repository** (`github:flipoyo/.memory`, branch
`ComplexGitSync`, 29 States, 35 ledger entries, verified) — that part
finished before this bug was hit. What is missing is the registry
formally listing `.cgitsync` as a mounted repository, which today only
`pull` can do and today `pull` cannot do here.

## 4. Decisions

### D1. Does §1's fix change behaviour for any `.cgs` that already sits at the root?

No. `project_root` defaults to `source_path.parent` when the caller does
not have an established root yet — the same value it already computes.
Only a `restart`/`pull` on an *already-loaded* tree changes, and only when
the `.cgs` is not colocated with it.

## 5. Work packages

| # | Depends on | Touches | Delivers |
|---|---|---|---|
| **WP-1** | D1 | `orchestre.py` | `restart` passes the tree's already-established root as `project_root` |
| **WP-2** | — | `orchestre.py`, `discovery.py` | Trace and fix §2's collision |
| **WP-3** | WP-1, WP-2 | `tests/` | `pull` against a `.cgs` outside CGSHOME, on a workspace with real memory history, as a permanent regression test — the exact case this ticket was found in |
| **WP-4** | all | this ticket | Archived under [TICKETLIFECYCLE.md](../../../.agentSpec/TICKETLIFECYCLE.md) |

## 6. Acceptance

- `cgitsync pull examples/complexgitsync4dev.cgs`, run from this project's
  own CGSHOME with `.cgitsync` holding real memory history, succeeds and
  the resulting tree lists `.memory` as a mounted repository.
- `pixi run lint` and `pixi run test` pass.
