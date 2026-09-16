# AdditionalSpecs — ComplexGitSync-Specific Constraints

*Created: 2026-05-13*

This file documents project-specific constraints and refinements that apply
**on top of** the general [DevSpecs](../.agentSpec/DevSpec/DevSpecs.md). Every rule in `DevSpecs.md`
applies here; this file only adds or tightens rules for `ComplexGitSync`.

**Planning lives next door.** `.localSpec/DevTickets/` holds every planning
ticket for this project — the owner's short tickets, the ranked open plans,
and the archive — and [its README](DevTickets/README.md) explains the loop
they move through. It is in this private repository, not in the public
`ComplexGitSync` one, so that installing the tool never ships the workshop:
the same PROJECT/private separation the tool itself implements. This file
stays the authoritative *specification*; a ticket only plans a change to it.

---

## Architectural Overview

The design is split into three explicit tiers.  Every class belongs to exactly
one tier; dependencies only flow **downward** (API → Actions → Core).

```
┌─────────────────────────────────────────────────────┐
│  Tier 3 — Client / API                              │
│  ComplexGitSyncClient  ·  Orchestre  ·  CLI         │
│  Exposes class methods gated by TreeLifecycleState  │
└────────────────────────┬────────────────────────────┘
                         │ calls (state-gated)
┌────────────────────────▼────────────────────────────┐
│  Tier 2 — Actions                                   │
│  initialise · load · pull · clone                   │
│  checkout · add · commit · push · tag · freeze      │
│  Each action is only accessible from VALID states   │
└────────────────────────┬────────────────────────────┘
                         │ reads / mutates
┌────────────────────────▼────────────────────────────┐
│  Tier 1 — Core Data (information processing)        │
│  GitTree · GitRepo · WorkingGitTree · WorkingRepo   │
│  RepoAddress                                        │
│  Centred on reference and working tree structures   │
└─────────────────────────────────────────────────────┘
```

### Architectural positioning (T37)

ComplexGitSync is not a replacement for Git, monorepos, or submodule metadata.
It is a deterministic synchronization layer that coordinates multiple Git
repositories as one workspace contract.

The model explicitly combines:

- **Git DAG**: each repository keeps its own commit graph and remote semantics.
- **GitTree DAG**: the workspace-level parent/leaf dependency graph used for
  propagation and execution ordering.

Operational consequences:

- workspace state propagation uses ordered graph traversal (parent-first for
  branch targeting and restore preparation; leaf-first for mutation actions),
- `.gts` is the canonical deterministic workspace checkpoint (schema + hash),
- `.lgr` is the local identity and replay layer (stable snapshot ids + ledger),
- cross-declared nested references may form a local declaration tangle, but
  runtime expansion is normalized to a DAG by `fix_circularities`.

### Tier 1 — Core Data

The reference model is centred on **`GitTree`**, which owns canonical
**`GitRepo`** identities. **`WorkingGitTree`** extends it with the parent-leaf
runtime graph of mutable **`WorkingRepo`** nodes.

```
GitTree
  ├── project identity  (GitRepo)
  └── dependency identities (GitRepo, ...)

WorkingGitTree
  └── root       (WorkingRepo, NodeType = ROOT)
        ├── dep  (WorkingRepo, NodeType = PARENT)
        │     └── sub  (WorkingRepo, NodeType = LEAF)
        └── lib  (WorkingRepo, NodeType = LEAF)
```

Key classes and their role in information processing:

| Class | Role |
|---|---|
| `GitRepo` | Canonical reference identity of one repository (provider, namespace, project name, protocol, SHA) |
| `GitTree` | Reference-tree structure containing `GitRepo` objects and format-adapter metadata |
| `WorkingGitTree` | Authoritative runtime graph; maps repo IDs to mutable `WorkingRepo` records |
| `WorkingRepo` | One mutable runtime node — canonical identity plus tree and synchronization state |
| `RepoAddress` | Derives the remote URL from a `GitRepo`; no side-effects |
| `RepoNode` | Immutable snapshot of a node's tree position for read-only traversal |
| `ProjectTreeState` | Frozen snapshot of overall tree readiness (returned by the Client to callers) |

`GitRepo` construction is side-effect free. Remote branch and tag availability
is resolved explicitly by `GitRunner` during runtime clone/resolution steps;
`.cgs` parsing and validation never query a remote.

Supporting enumerations:

| Enum | Values |
|---|---|
| `NodeType` | ROOT / PARENT / LEAF |
| `TreeLifecycleState` | user-facing: LOADED → PENDING → READY; implementation retains internal readiness states |
| `RepoLifecycleState` | DECLARED → PENDING → READY / FALLBACK_READY; side: MISSING, ERROR |
| `SyncState` | ALIGNED / FALLBACK_APPLIED / DIRTY / AHEAD / BEHIND / DIVERGED / ERROR / PENDING |
| `DiscoveryState` | PENDING / RESOLVED / DISABLED / MISSING |
| `RefKind` | AUTO / BRANCH / TAG / DETACHED / UNKNOWN |
| `GitProvider` | github / gitlab / codeberg / custom |
| `AccessProtocol` | ssh / https |

### Tier 2 — Actions

Actions are operations that read or mutate the Core tier.  Each action is
implemented as a method on `ComplexGitSyncClient` or a free function called by
the client.  **Every action is gated by the current `TreeLifecycleState`**:

| Action | Minimum required state | Produces state |
|---|---|---|
| `initialise(.cgs)` | none | `.gts READY` (clone) |
| `initialise(.gts)` | none | `.gts READY` (restore) |
| `load(.cgs)` | none | `.gts DECLARED` |
| `load(.gts)` | none | `.gts READY` (direct) |
| `expand(.cgs)` | none | `.gts PENDING`; runs nested discovery + `fix_circularities` (SCC + hash-compatibility) |
| `fix_circularities()` | any (after load/expand) | two-phase cycle-breaking engine; removes back-edge duplicates; state unchanged |
| `pull(.cgs)` | none | `.gts READY` |
| `pull(.gts)` | none | `.gts READY` |
| `checkout(.gts)` | `READY` | `READY` |
| `add` | `READY` | `READY` |
| `git(tree, "commit", msg)` | `READY` | `READY` |
| `git(tree, "push")` | `READY` | `READY` + updated hash |
| `git(tree, "tag", name)` | `READY` | `READY` + updated tag |
| `freeze` | `READY` | next `.gts` id |

Actions that **must reject** a non-READY tree:
`add`, `git("commit")`, `git("push")`, `git("tag")`, `freeze`.

CLI dry-run mode (T36): `add`, `commit`, `push`, `tag`, and `freeze` accept
`--dry-run` to print a non-mutating execution plan (`plan_actions`,
`plan_order`) without dispatching write operations.

Workspace preflight invariants:
- `commit`, `push`, `tag`, and `freeze` all run a workspace preflight engine before mutation.
- The engine checks dirty worktrees, detached HEADs, missing remotes, branch divergence,
  unresolved merges, and stale recorded `commit_sha` values.
- Diagnostics are severity-based: warnings are emitted for actionable-but-allowed states
  (for example ahead branches, dirty trees on `commit`/`freeze`, or stale snapshot SHAs),
  while blocking errors stop the operation.
- `tag` must still reject dirty worktrees and pre-existing tags.
- Tag creation is always non-forcing (`git tag <name>`); replacing an existing tag is not allowed.

### Branch Topology Propagation Rules (T35)

`validate_branch_topology(registry, git_runner) → BranchTopologyReport` is the
authoritative inspection function for workspace branch coherence.  It formalises
the propagation rules used by `checkout_tree`, `commit_tree`, `push_tree`,
`tag_tree`, and `freeze_release_tree`.

**Propagation rules (deterministic and inspectable):**

1. **Reference branch**: The root repository's current branch is the canonical
   reference.  All other repositories must match it.

2. **Leaf-to-root inheritance direction**: Branch targeting flows root-first
   (parent to children) via `propagate_global_branch` and
   `create_global_branch`.  `validate_branch_topology` verifies that the
   on-disk state is coherent with this rule without issuing any git writes.

3. **Allowed divergence**: Repositories whose `resolved_ref_kind` is `TAG` are
   flagged as `tag_divergence` but do **not** make the topology incoherent —
   they represent frozen (released) state.

4. **Incoherent (blocking) states**:
   - `misaligned_branch`: repo is on a different branch than root.
   - `detached_head`: repo is in detached HEAD state without a tag reference.

**`BranchTopologyReport` fields:**

| Field | Type | Description |
|---|---|---|
| `reference_branch` | `str \| None` | Root's active branch (reference for all repos) |
| `is_coherent` | `bool` | `True` when no blocking conflicts are present |
| `conflicts` | `list[BranchTopologyConflict]` | One entry per problematic repo |
| `repo_branches` | `dict[str, str \| None]` | `{repo_name: current_branch}` |

**`BranchTopologyConflict.conflict_kind` values:**

| Kind | Blocking | Description |
|---|---|---|
| `misaligned_branch` | ✓ | Repo is on a different branch than root |
| `detached_head` | ✓ | Repo is in detached HEAD without a tag |
| `tag_divergence` | — | Repo is on a tag (allowed divergence) |
| `missing_root` | ✓ | Registry has no root entry |

**Python API:**

```python
from ComplexGitSync import ComplexGitSyncClient

client = ComplexGitSyncClient()
client.load_gts("project.gts")
report = client.validate_branch_topology()
print(report.format())           # human-readable summary
assert report.is_coherent        # True if all repos are aligned
```

**CLI:**

```bash
cgitsync validate-topology --gts project.gts
# exits 0 if coherent, 1 if not
```

Actions that **must produce READY** or fail explicitly:
`initialise(.cgs)`, `initialise(.gts)`, `pull(.cgs)`, `pull(.gts)`, `checkout(.gts)`.

When `.cgs` entries declare `branch` or `tag`, format validation checks only
their static document representation. Runtime resolution selects the declared
target (`tag` takes precedence when both are present) and verifies its remote
availability through `GitRunner`.

### Tier 3 — Client / API

`ComplexGitSyncClient` is the single public facade.  It:

- Holds references to `Orchestre`, `GitRunner`, `RuntimeStateStore`, and the
  live `WorkingGitTree`.
- Computes the current `TreeLifecycleState` on demand and gates every action
  against it.
- Emits structured log events for every state transition, action start/end,
  fallback decision, and `.gts` write/load.
- Exposes both rich tree rendering (`format_project_tree`) and minimalist
  repo-outline rendering (`format_repo_tree`).
- Exposes terminal observability views: `view_tree` (topology + branch/local/sync)
  and `view_operation` (tabular runtime state).

`Orchestre` is the coordination layer between the Client and the tree models.
The CLI (`cli.py`) collects arguments or interactive prompt values and delegates
them to the non-interactive `ComplexGitSyncClient.configure()` Python API.
That facade delegates format semantics to `cgs_format.py`; runtime commands
remain separate Client operations.

### Tier and Ring are two different groupings of the same modules

The sections below (moved here from `audit.md`, which used to
carry them alongside its actual audit findings) describe the same module
set through a second, orthogonal lens: **Ring**, an *import-direction/
I/O-boundary* grouping, mechanically checked by
`scripts/check_module_ceilings.py`, as opposed to Tier's *lifecycle-role*
grouping above. The two do not collapse 1:1 — see
`docs/DevGuide/architecture.md` §1 for the full Tier↔Ring reconciliation
table; that document remains the place to look when the mapping between a
Tier and a Ring needs spelling out precisely.

## Responsibility boundaries

Rewritten 2026-08-30 against the post-isolation-Wave-2 module set
(`.localSpec/DevTickets/archive/20260828_Isolation_DevPlanTicket.md`) — `orchestre.py` used to
carry most of this table's Tier 2/3 responsibility directly; it now
delegates each to its own module. See each module's own docstring header
(`Ring:`/`Contract:`/`Imports:`, `.localSpec/DevTickets/IsolationPlan.md` §3.2) for the
authoritative, machine-cross-checked version of this table — this is the
human-readable summary.

| Module | Ring | Responsibility |
|---|---|---|
| `errors.py` | 0 | The package's public exception hierarchy. |
| `git_repo.py` | 0 | Per-repository identity types, state enumerations, provider registry, remote-URL construction. Also `RepoScope`, the one definition of which repositories a tree-wide command may touch: `private` marks a repository that configures the project rather than being it, shared with the author's other projects, read-only unless the `.cgs` entry adds `writable = true`. `RepoScope.includes` reads `effective_private`/`effective_writable`, the flags after `git_tree.propagate_privacy` has pushed each parent's privacy down; the declared `private`/`writable` are what gets serialized. Preflight is scoped the same way, and measures a private repo against its own declared branch via `git_branch.resolve_propagated_ref`. |
| `git_branch.py` | 0 | The single owner of the `.cgs` branch fallback chain (`fallback_branch` → `default_branch` → `project.default_branch` → `DEFAULT_BRANCH`) and of the privacy rule that decides what a repository targets under a tree-wide branch move. A pure resolver: declared fields in, a `BranchResolution` (branch, `RefKind`, and the `BranchSource` that answered) out. Holds no tree, no root and no privacy *state* — `git_tree.py` owns those, and `git_tree_branch.py` owns branch state the same way (which branch the tree is on, and which branch each repository is actually on). Also owns the private/local naming rule: `private_local_branch` composes `<project name>` on `main` and `<project name>_<branch>` otherwise, and `PRIVATE_LOCAL_SEPARATOR` never leaves this module — `tests/unit/test_git_branch.py` fails if either escapes, the same guard the `"main"` literal already has. `resolve_propagated_ref` now answers three cases, not two: a project repo follows the move, private/distant never moves, private/local takes the derived branch. |
| `ledger_entry.py` | 0 | Hash-chained register-entry construction and canonicalisation (pure chain math). |
| `integrity.py` | 0 | `Finding` taxonomy and `verify_chain` — pure arithmetic checks over a register-entry sequence. |
| `json_render.py` | 0 | The machine-readable shape of what a command reports — `status`, `verify`, and the error object a JSON-capable command prints when it fails — with `SCHEMA_VERSION` and the serialiser. One module for every command's shape, so field names are decided once rather than re-invented per command, and `cli/` carries none of them. Separate from `status_render.py` on purpose: that renders one table for humans, where a column can be renamed when the wording improves; a JSON field cannot, because something is parsing it. The promise is **additive only**. See `.localSpec/DevTickets/archive/20260916_CliContract_DevPlanTicket.md`. |
| `status_render.py` | 0 | Pure text rendering for `cgitsync status`'s repository table, including the `SCOPE` column. That column is where the developer vocabulary is translated for end users: `private` reads as **private**, `writable` as **local**, private read-only as **distant**, and a repo that is not private as **project**. `_status_scope_label` is the only place that mapping lives; it reads the effective flags, so a repo nested in a private one is labelled like its parent. Docs, tutorials and CLI output use the user words; code, docstrings and this table keep `private`/`writable`. |
| `config_document.py` | 0 (+ Ring-1 adapter) | Pure `ConfigDocument` base — dict wrapping, dot-path reads, the `validate()` hook. |
| `config_document_io.py` | 1 | `ConfigDocumentIOMixin` — the six file-I/O methods (`from_toml`/`to_toml`/etc.) `ConfigDocument` used to carry directly. |
| `cgs_format.py` | 0 (+ Ring-1 adapter) | `.cgs` TOML parsing, authoring grammar (`parse_repo_id` — the *only* implementation), normalization, static validation, `CgsDocument`, minimization, serialization. |
| `gts_document.py` | 0 (+ Ring-1 adapter) | `.gts` runtime state-snapshot parsing/validation; the one canonical content-hash builder. |
| `master.py` | 1 | Local, workspace-scoped Git identity for ComplexGitSync's own automated commits; persisted per `CGSHOME` via `.cgitsync/master.toml` — not part of the `.cgs`/`.gts` project spec. |
| `paths.py` | 1 | Environment-marker path portability (`$HOME`/`%USERPROFILE%`/etc.) and `CGSHOME`/`CGSPATH` resolution. |
| `state_store.py` | 1 | The one place that composes a State's path: `.cgitsync/state/<hash>.gts`, where the hash is the document's own content digest (`state_path`). Still reads the older `state(<hash>)_n/` directories, so a workspace written before the flat layout resolves without being rewritten — and `snapshot_resolver.py` imports that grammar from here rather than carrying the copy it used to. Formerly content-addressed directory allocation — the general mechanism every lifecycle command uses (not related to the deleted Memory transport, despite the class name). |
| `settings.py` | 1 | Where ComplexGitSync keeps its own workspaces, answered before any workspace is open — which is what separates it from `master.py`, whose `.cgitsync/master.toml` cannot be read until one has been found. Owns the root (`$CGSPATH`, else `$HOME/.cgs`), the **default workspace** that `snapshot_resolver.py` falls back to when none of its three inputs finds one, the `$HOME/.cgs/default` pointer that makes that workspace minted-once-then-reused, the empty but valid `.gts` written into it (`UNLOADED`, `is_ready = false` — an empty tree must never claim to be ready), the list of other workspaces under the root that the CLI prints as a hint and never selects from, and the `UseCase` (`STANDALONE`/`NESTED`) derived from whether the running installation sits inside the resolved CGSHOME. Derived, never stored: two callers in one process cannot disagree. See `.localSpec/DevTickets/archive/20260916_CgshomeDefault_DevPlanTicket.md`. |
| `snapshot_resolver.py` | 1 | Resolves which `.gts` snapshot the CLI defaults to when a command omits one explicitly — and, when none of its three inputs finds a workspace at all, falls back to `settings.py`'s default workspace rather than raising (`CGSHOME_ORIGIN_DEFAULT`), except under an explicit `--search-dir`, where a directory the user named is never silently replaced, and — through its `describe_*` functions — reports *which input decided it*: `--search-dir`, `$CGSHOME`, or the current directory, in that order of precedence. The precedence is deliberate (the documented bootstrap tells users to export `$CGSHOME`), which is exactly why the reason has to travel with the answer: a stale export silently retargets every command at another workspace that holds the same repositories. This module never prints — `cli/_shared.py` turns a `CgshomeResolution`/`SnapshotResolution` into the `cgshome=`/`source=` lines and the mismatch warning. |
| `memory/` | 1 | **Everything a workspace remembers, in one package.** `repository.py` says what it takes for a memory to *be* a repository — the `.cgs` entry that mounts it, which branch of the shared `.memory` repository this project uses, and the message its own commit carries — while running no Git itself: `orchestre.py` asks `git_runner.py`, as it does for every other repository. `states.py` (where a State is written and how its path is spelled), `ledger_entry.py` (one chain entry and the hash over it), `ledger_store.py` (one file per entry, atomically, with an untrusted `HEAD`), `integrity.py` (whether a chain holds, and the four answers `verify` owes), `store.py` (the State writer, plus the single-file register that predates the chain — read-only, and written by nothing). `__init__.py` is the surface everything outside imports. **No Git, ever**: the next milestone makes a memory a repository that is committed and pushed, and that work belongs to `operations.py`/`git_runner.py` driven *by* this package, never done inside it. `snapshot_resolver.py` stays outside — it answers which workspace and snapshot a command line meant, not what is remembered. |
| `discovery.py` | 1 | Nested `.cgs` auto-discovery and `.gitmodules` parsing. |
| `git_tree.py` | 1 | `GitTree`/`WorkingGitTree` structures, traversal, lifecycle state; `to_cgs()` delegates to `cgs_format.py`; `.gitignore` maintenance across the tree (`sync_gitignore`) — the reason this is Ring 1, not 0. Also the single rule for "which repo sits inside which": `resolve_repo_for_path` for a live tree, `innermost_containing_path` for plain paths before one exists. Owns privacy *state* as well: `propagate_privacy` pushes each parent's `private`/`writable` onto everything nested inside it (a parent defines its leaves; a leaf may restrict itself further, never open itself wider) and records the answer in `WorkingRepo.propagated_private`/`propagated_writable`. Every build path calls it beside `normalize_node_types`. |
| `git_tree_branch.py` | 2 | The tree's branch *state*, and the counterpart to `git_branch.py`'s *rule*: which branch the tree is on (the root's — what `status` prints as `cgitsync_branch`), which branch each repository targets when the tree moves (`target`, a pass to `git_branch.resolve_propagated_ref` with the project's name filled in), which branch Git says each is on (`observed`, read once per repository and cached so one `status` costs one call per repository instead of two), and where the two disagree (`deviations`). Also holds `tree_project_name`, moved here from `operations.py` because the project's name exists in that code path only to name a private/local branch. Restates no rule: every answer it gives comes from `git_branch.py`. Four call sites computed all of this separately before it existed — `validate_branch_topology`, `_collect_branch_alignment_diagnostics`, `_branch_incoherence`, and the root read in `_restart_tree_common` — and the three that asked the same question disagreed about a detached root. `deviations(ignore_unreadable=...)` keeps the one difference that is real: a report skips a repository Git cannot answer for, a preflight gate must not. An instance is a snapshot — build a new one after a checkout or a pull. See `.localSpec/DevTickets/archive/20260916_StatusCurrentBranch_DevPlanTicket.md`. |
| `toolchain.py` | 2 | The five version strings every ledger entry records — cgitsync, git, pixi, dvc, git-lfs — read at most once per process and reported as `none` when a tool is not installed. Asks `git_runner.tool_version` rather than importing `subprocess`, so the single-importer rule holds. A data backend is asked only when the operation being recorded used one: `dvc --version` starts a Python interpreter and would be felt on every `status`. |
| `git_runner.py` | 2 | Git subprocess wrapper — the *only* module that imports `subprocess`, and therefore the one place the **decoding policy** for Git output lives. Git writes bytes, not text: `merge-tree`'s legacy form prints the content of the files it could not merge, and paths need not be UTF-8 either. Both wrappers (`_run`, `_query`) decode with `errors="replace"`, and `_query_bytes` hands back the raw bytes for the one caller that searches output it does not control. Strict decoding used to raise before the caller could read the exit code — see `AgentSpec/archive/20260910_MergeOutputDecoding_DevPlanTicket.md`. Owning the subprocess boundary also means owning the **environment** those subprocesses run in: `_non_interactive_git_env()` both stops Git blocking on a credential prompt and pins the language Git writes its messages in. ComplexGitSync reads Git's prose — no exit code says whether a fetch failed for want of credentials — so a translated message silently cost non-English users the `--force-protocol` recovery hint. `_english_message_locale()` is the only place that decision lives; it removes an inherited `LC_ALL` after copying its value into every other category, so only the language changes and encoding and collation are left alone. `LC_ALL=C.UTF-8` is the obvious fix and does not work: gettext still consults `$LANGUAGE`. See `AgentSpec/archive/20260911_GitLocaleIndependence_DevPlanTicket.md`. Every method that asks Git a question goes through `_query`/`_query_bytes`; none calls `subprocess.run` directly, which is what makes both the decoding policy and the environment policy inescapable rather than merely conventional. `can_merge_cleanly` returns the conflicting paths rather than a verdict, and reads both Git forms into the same answer: the modern form stops at the blank line before Git's notes, and the legacy form keeps a path only when its own block carries a conflict marker, since "changed in both" alone is not a conflict. A binary conflict prints no marker at all and is detected from Git's stderr warning — it used to be reported as clean, which let a tree-wide merge pass the preflight and then break halfway. See `AgentSpec/archive/20260910_MergeConflictReporting_DevPlanTicket.md`. |
| `clone_guard.py` | 2 | Answers one question about a directory `initialise` is about to delete and re-clone: **would clearing this lose work that exists nowhere else?** Two read-only checks per destination — a dirty worktree, and commits reachable from `HEAD` that no remote-tracking ref holds. The second is deliberately *not* "is the branch ahead of its upstream": that form both misses a branch with no upstream carrying local commits, and wrongly blocks a detached `HEAD` parked on a commit the remote already has — which is exactly what a submodule checkout is, and what `init-from-submodules` depends on. Touches no worktree, which is what lets `orchestre.py` ask about every pending repository before deleting any of them, so a refusal anywhere leaves everything on disk. Decides nothing about whether a mount point is owned outright — that is `AppendCloneMode`'s question about the same `shutil.rmtree`. See `AgentSpec/archive/20260910_InitialiseDestroysExistingClones_DevPlanTicket.md`. |
| `operations.py` | 2 | Leaf/parent-first Git operations over a `WorkingGitTree` + `GitRunner`. Asks `git_tree_branch.py` which branch the tree is on and which branch each repository should follow, rather than working it out per call site — `checkout_tree`, `branch_tree`, `add_tree`, `commit_tree`, `push_tree`, `tag_tree`, `freeze_release_tree`, branch-topology validation. Requires a `READY` tree; raises `TreeNotReadyError` otherwise. `add_tree`/`commit_tree`/`push_tree` each return one `RepoOutcome` per repository they visited — what changed there, or why nothing did — so a sweep that wrote nowhere is distinguishable from one that wrote everywhere. The client stores the tuple on `ComplexGitSyncClient.last_write_outcomes` and `cli/` prints it; deciding what happened stays here. `remove_paths` reports the same way, and is the one scoped operation handed its paths rather than sweeping for them: its scope is checked against the repository each path resolves to — a filter — and one path outside it refuses the whole call before any removal. Bare `rm` keeps its original reach (`RepoScope.ALL`); `cli/_shared.py` warns when that reach lands in a configuration repository. |
| `registry.py` | 2 | Translates `.cgs`/`.gts` documents to/from `WorkingGitTree`. **The `.gts` prevails over the `.cgs`.** A snapshot is the attested state — the `.lgr` register hash-chains it — so a hand-edited `.cgs` must never override what a snapshot records, or editing a text file would silently widen write access to a shared repository. |
| `orchestre.py` | 3 | The `ComplexGitSyncClient` public facade and `Orchestre` coordination layer — gates every mutating action on `TreeLifecycleState`; delegates document parsing, path resolution, state allocation, registry translation, discovery, and status rendering to the Ring 0–2 modules above rather than re-implementing them; still owns structured run logging (`CommandRunLogger`) and the local `.lgr` register/sync ledger (`LocalGitRegister`/`SyncLedger`) directly. |
| `cli/` | 4 | CLI argument/prompt collection only; delegates all `.cgs`/`.gts` semantics downstream. Package: `exit_codes.py` (the three documented exit codes — `0` did it, `1` ran and the answer is no, `2` could not run — and the one function mapping an expected failure to one of them; it returns `None` for anything unrecognised, which is what keeps a programming defect a traceback instead of a tidy `2`), `_shared.py` (helpers used across every command group), `minimalist.py`/`expert.py`/`configuration.py` (one module per README's own command grouping, each owning its subset's parser registration + `_handle_*`/`_execute_*` pairs), `suggest.py` (the "did you mean ...?" hint: which known command a mistyped one most likely meant, printed after argparse's own error and never instead of it — it re-raises argparse's `SystemExit` untouched rather than subclassing `ArgumentParser.error`, so no part of this project depends on argparse's private message wording, and it never rewrites the arguments or runs the command it names), `__init__.py` (assembles the parser from the three groups, exposes `main`/`build_parser`/`_PLANNED_COMMANDS`). |

`__init__.py` and `__main__.py` are out of scope for this audit (public
re-exports and the module entry-point shim respectively) — they carry no
`.cgs`/provider/runtime boundary logic of their own. `L0.py` no longer
exists — its TIME-L0 anchor generation was absorbed into `ledger_entry.py`
with an injectable clock (Wave 1).

The `.cgs` dependency path is:

```text
CLI values --------> ComplexGitSyncClient.configure() <-------- Python caller
              \                   |
               \-----------> master.py
                                  |
.cgs TOML ----------------> cgs_format.py <----> config_document.py / config_document_io.py
                                  |          \---> git_branch.py (Ring 0: which branch,
                                  |                 and why -- the only fallback chain)
                              CgsDocument
                                  |
                                GitTree
                                  |
                              orchestre.py -------> registry.py (Ring 2: .cgs/.gts <-> WorkingGitTree)
                                  |            \---> operations.py (Ring 2: Tier 2 actions)
                                  |            \---> git_tree_branch.py (Ring 2: which branch the
                                  |                  tree is on, and who follows it -- asks
                                  |                  git_branch.py for every rule)
                                  |            \---> discovery.py, paths.py, memory/,
                                  |                  settings.py, status_render.py
                                  |                  (Ring 1/0: delegated concerns)
                                  |            \---> git_branch.py (Ring 0: the same resolver
                                  |                  registry/operations/discovery/git_tree call)
                                  |
                        GitRepo / git_runner.py (Ring 2: the sole subprocess boundary)
```

`cgs_format.py` is deterministic and offline at its Ring-0 core. It does not
import `subprocess`, run Git, resolve remote references, or check repository
existence. Constructing a `GitRepo`, `RepoAddress`, `GitTree`, or
`CgsDocument` has no remote side effects. (Its `ConfigDocumentIOMixin`-derived
`from_toml`/`to_toml` methods do real file I/O — that boundary is now
explicit via the Ring-1-adapter co-location noted in the table above, not
implicit in an otherwise "pure" module.)

## Ring model and import rules

Added by `.localSpec/DevTickets/archive/20260828_Isolation_DevPlanTicket.md` (P6) once the
isolation work gave the package enough real modules for these rules to be
checkable rather than aspirational. See `.localSpec/DevTickets/IsolationPlan.md` for
the full design rationale; this section is the enforced-in-practice
summary, and the authoritative source the rest of the docs (`CLAUDE.md`,
`docs/DevGuide/architecture.md`) point back to.

### The ring table

Imports flow downward only — a module may import from a lower-numbered
ring, never a higher one.

| Ring | Modules |
|---|---|
| 4 — ADAPTER | `cli/` package (`_shared.py`, `minimalist.py`, `expert.py`, `configuration.py`, `suggest.py`, `__init__.py` assembling them) |
| 3 — ORCHESTRATION | `orchestre.py` (`Orchestre`, `ComplexGitSyncClient`) |
| 2 — GIT PROCESS | `git_runner.py` (sole `subprocess` importer), `clone_guard.py`, `git_tree_branch.py`, `operations.py`, `registry.py`, `toolchain.py` |
| 1 — FILESYSTEM | `paths.py`, `memory/` (`states`, `ledger_entry`, `ledger_store`, `integrity`, `store`), `settings.py`, `snapshot_resolver.py`, `discovery.py`, `master.py`, `git_tree.py` (`.gitignore` writes) |
| 0 — PURE / OFFLINE | `errors.py`, `git_repo.py`, `git_branch.py`, `ledger_entry.py`, `integrity.py`, `json_render.py`, `status_render.py`, plus the Ring-0 core of `config_document.py`/`cgs_format.py`/`gts_document.py` (each also carries a Ring-1 I/O adapter for real call-site compatibility — see those modules' own docstrings) |

### The four import rules (machine-checked)

1. **No upward imports.** Ring *n* imports from rings `< n` only.
2. **`import subprocess` appears in exactly one module** — `git_runner.py`.
3. **Ring 0 performs no I/O at all** — no `subprocess`, no `open()`, no
   `pathlib` writes, no `os.environ`, no clock reads. Enforced for modules
   listed in `scripts/ceiling_baseline.json`'s `ring0_modules` by
   `pixi run check-ceilings`; extend that list as more modules earn it.
4. **Ring 1 performs no `subprocess`.** Filesystem only.

### Ceilings

`scripts/check_module_ceilings.py` (`pixi run check-ceilings`) enforces a
**ratchet, not a fixed number**: a module may never grow past its recorded
baseline in `scripts/ceiling_baseline.json`; it may always shrink one.

**Raising a baseline is the owner's call, never the implementer's.** When a
change genuinely needs room, report that and ask — do not contort code to
fit, and do not raise the number quietly. The owner granted such a raise on
2026-09-06, with a standing allowance of roughly 1000 LOC per module where a
change needs it, on the grounds that the project is already held by many
other invariants. That allowance is a ceiling to ask against, not a target
to fill: the ratchet still tightens automatically every time a module
shrinks, and `--write-baseline` records both directions at once.
Directional targets, for context: ≤500 LOC hard / ≤350 target per module,
≤7 public symbols, ≤6 internal imports. Cyclomatic complexity is enforced
separately and absolutely via `ruff`'s `C90` selector (`pyproject.toml`,
max 12) — a handful of pre-existing functions carry a documented
`# noqa: C901` (search the codebase for "Pre-existing complexity debt");
new code has no such exemption.

### Docstring contracts

Every module in `src/ComplexGitSync/` should open with:

```python
"""module_name — one-line summary.

Ring: <0-4> (why, if not obvious)
Contract: what this module guarantees, in one or two sentences.
Imports: comma-separated internal modules, or "none"
"""
```

`scripts/check_module_ceilings.py` cross-checks the declared `Imports:`
list against the module's real `from .x import ...` statements when both
are non-trivial — keep them in sync rather than let the header rot.

### Commit discipline

One concern per commit — `DELETE`/`MOVE`/`CHANGE` never mixed in the same
commit. This is the same discipline
`.localSpec/DevTickets/archive/20260826_Deletion_DevPlanTicket.md` and
`.localSpec/DevTickets/archive/20260828_CleanupPass2_DevPlanTicket.md` used successfully; the isolation
work continues it. A commit that both deletes duplicated code from
`orchestre.py`/`cli/` and authors a brand-new module is two concerns —
split it.

### The one hard prohibition

> **Never hand-edit anything under `.cgitsync/`.** If a workspace's state
> looks wrong, fix it by running the normal lifecycle commands again, or —
> once wired into real use — `cgitsync verify --repair`, which only ever
> repairs the `HEAD` cache and never rewrites or deletes a register entry.
> An agent that corrupts `.cgitsync/` by hand and doesn't notice is the
> realistic worst case in this workflow.

## Format ownership

`cgs_format.py` contains the only implementation of `parse_repo_id()` and the
only repository-authoring regexes (`_PROVIDER_RE` and
`_REPOSITORY_SEGMENT_RE`). Both `.cgs` input and repeatable CLI `--repo` values
flow through `CgsDocument` normalization. The public
`ComplexGitSyncClient.configure()` facade delegates to that boundary without
parsing identifiers itself. No parser exists in `cli/`, `git_tree.py`,
`git_repo.py`, or `orchestre.py`.

**The same rule applies to branches.** `git_branch.py` contains the only
implementation of the `.cgs` branch fallback chain
(`fallback_branch` → `default_branch` → `project.default_branch` →
`DEFAULT_BRANCH`) and of the privacy rule. Before it, that chain was written
out by hand in six places across five modules, none of which read
`DEFAULT_BRANCH` — each was a private copy stopping at a different link, so
changing the constant moved only one of them. Do not add a second one:
`cgs_format.py`, `discovery.py`, `registry.py`, `operations.py`,
`git_tree.py` and `orchestre.py` all call the resolver. Four sites in the
source still spell the literal `"main"`; each is a *different* decision
(Git's own `.gitmodules` default, a bare-path last resort, a frozen
snapshot-hash input), each carries a comment saying so, and
`tests/unit/test_git_branch.py` counts them and fails when a new one
appears.

The supported authoring grammar is:

```text
provider:owner/repository
```

Minimal TOML is the standard serialized form. Exceptional configuration uses
inline repository tables. `GitTree.to_cgs()` delegates conversion to
`CgsDocument.from_git_tree()`; TOML formatting and minimization remain in
`cgs_format.py`. The required round trip is semantic, not byte-for-byte.

## Provider contract

| Provider | Canonical host | SSH and HTTPS | Validation |
|---|---|---|---|
| `github` | `github.com` | deterministic | owner and repository required |
| `gitlab` | `gitlab.com` | deterministic | group/owner and repository required |
| `codeberg` | `codeberg.org` | deterministic | owner and repository required |
| `custom` | none | derived from explicit URL | `gitprovider_url` required; no host guessing |

The provider registry is defined once in `git_repo.py`, next to remote
construction. `cgs_format.py` uses that registry for static document validation
without performing Git or network operations.

---

## Object Model — Class Grouping by Tier

### Tier 1: Core Data

```
git_repo.py   GitRepo, WorkingRepo, RepoAddress, RepoNode,
              provider registry and repository-level enums
git_tree.py   GitTree, WorkingGitTree, ProjectTreeState,
              TreeLifecycleState, traversal and tree-state helpers
```

### Tier 2: Actions

```
operations.py            propagate_global_branch, create_global_branch
                         checkout_tree, commit_tree, push_tree
                         tag_tree, freeze_release_tree
orchestre.py             registry builders, nested discovery, runtime
                         documents and orchestration services
```

### Tier 3: Client / API

```
orchestre.py             Orchestre, ComplexGitSyncClient, GitRunner,
                         CommandRunLogger, RuntimeStateStore
master.py                MasterConfig — workspace-local Git identity for
                         ComplexGitSync-authored commits (not project spec)
cli.py                   argument/prompt collection, build_parser, main
```

### Document layer (cross-cutting, read by Tier 2)

```
config_document.py       ConfigDocument  (shared format-neutral base)
cgs_format.py            CgsDocument and the complete .cgs boundary
orchestre.py             GtsDocument runtime document
errors.py                exception hierarchy
```

---

## Monolithic Package

The package is `ComplexGitSync`, exposed through the `cgitsync` CLI entrypoint.
Do **not** split it into plugins or separate packages.

---

## Python Tooling

`DevSpecs.md` allows Python projects to standardise on either `uv` or `pixi`.
`ComplexGitSync` standardises on `pixi` for contributor and CI workflows.

- Local bootstrap, dependency installation, and command execution use `pixi`.
- Repository instructions must not prescribe direct `pip` / `venv` workflows.

---

## Document Formats

| Document type | Extension | Format |
|---|---|---|
| Local authoring spec | `.cgs` | TOML |
| Generated Git Tree State snapshot | `.gts` | TOML |
| Local Git Register | `.lgr` | TOML |

- TOML read uses stdlib `tomllib`; TOML write uses `tomli-w`.
- YAML support is optional and guarded by a soft import of `PyYAML`.
- Every document class must expose `to_toml`, `to_json`, `to_yaml`,
  `from_toml`, `from_json`, and `from_yaml`.

### `.cgs` authoring contract

The preferred TOML form contains `project = "<name>"` and a `repos` array of
`provider:owner/repository` identifiers. Loading is explicitly
`PARSE -> NORMALIZE -> VALIDATE`: normalization produces the complete
canonical `CgsDocument` used by `GitTree`, supplies `main`, `ssh`, automatic
nested discovery, and deterministic relative paths, and infers `.` for one
unambiguous project-name repository. Inline or legacy repository tables remain
available for explicit overrides. Authoring syntax is not the internal
representation.

`cgs_format.py` is the unique, bidirectional `.cgs` boundary. Its parse,
normalize, validate, tree-projection, minimize, and serialize paths are offline
and deterministic. `GitTree.to_cgs()` is only a delegation point. Serializing
and parsing again must preserve canonical semantics, although byte equality is
not required.

### `.gts` formal snapshot contract

`.gts` snapshots are canonical workspace checkpoints with deterministic hashing.

- `document.format_version` tracks the broad `.gts` compatibility family (`1.0` today).
- `document.schema_version` identifies the concrete `.gts` field-level contract (current: `1.1`) used by validation and canonical hashing logic.
- `document.hash_algorithm` is `sha256`.
- `document.snapshot_hash` is the SHA-256 digest of the canonical payload
  (`project`, `tree_state`, and sorted `repo_state`), excluding volatile
  metadata (`generated_at`, `command_origin`).
- freeze snapshots (`document.command_origin` in `freeze`, `freeze_release`,
  `freeze_state`) must include `[freeze_manifest]` with invariant markers:
  immutable snapshot, validated workspace, synchronized tag reference,
  ledger checkpoint, and restore operation `launch_state`.
- Canonical ordering is deterministic: repositories are serialized in stable
  absolute-path/name order, and non-root entries must include
  `parent_absolute_path`.
- READY/FALLBACK_READY repositories must include `commit_sha`; every repo state
  must include at least one resolved/current/target ref name.

Why these fields are required:

- `format_version` allows compatibility grouping across long-lived document families.
- `schema_version` allows strict parser/validator behavior to evolve while preserving explicit backward intent.
- `snapshot_hash` gives deterministic identity for workspace state, enabling integrity checks on load and stable `.lgr` snapshot deduplication.

---

## Lifecycle Contract

The canonical user-facing lifecycle contract is:

1. `initialise(.cgs)` → clone all repos → `.gts READY`  *(new project)*
   - `client.initialise("install.cgs")`
   
   OR `initialise(.gts)` → restore from snapshot → `.gts READY`  *(existing project)*
   - `client.initialise(".cgitsync/state/<hash>.gts")`
   - Before the tree is confirmed ready, every repo with children (root or
     any nested repo that itself has further nested children) is safely
     pulled (parent-first) and has its `.gitignore` updated with the
     relative path of each immediate child — nested repos are plain
     independent clones, not gitlinks, so without this a parent's `git
     status`/`git add` would otherwise see a child's working tree as
     ordinary untracked content. If the safe pull for one of these repos
     fails, `initialise` raises immediately and nothing is written — no
     forcing is attempted on the caller's behalf, unless `--force-gitignore-sync`
     is explicitly passed, in which case that one repo falls back to a
     pull-force recovery (never a force-*push*) instead of erroring out.
     By default nothing is staged, committed, or pushed by this step; it
     only writes the file and prints what changed
     (`.gitignore updated (not committed): ...`). Passing
     `--commit-gitignore` is explicit approval to also stage (only
     `.gitignore`, never `git add --all`), commit — with a message listing
     exactly which children were added — and push each changed repo; the
     printed report then reads `committed and pushed` instead. The CLI logs
     this as the `GT-GITIGNORE` phase, after `GT-CLONE`. The commit identity
     defaults to whatever `git config user.name`/`user.email` already
     resolves to locally — nothing extra is passed to `git commit` unless an
     override is configured. `--git-user-name`/`--git-user-email` set that
     override via `MasterConfig` (`master.py`) and persist it to
     `CGSHOME/.cgitsync/master.toml`, a workspace-local file that is not part
     of the `.cgs`/`.gts` project spec and is preserved by `purge`/
     `clean-init` (unlike generated clone state). `MasterConfig.load()` reads
     any previously persisted override at the start of `initialise`/
     `clean-init`/`pull`, so it applies to every subsequent invocation on
     that workspace without repeating the flags.

2. `pull(.cgs/.gts)` → resync an existing tree → `READY`
   - `client.pull("install.cgs")`
   - `.gts` input is loaded as the starting registry, then the tree is pulled
     in parent-first order: `ROOT -> PARENT -> LEAF`. Every repository — root,
     parent, and leaf alike — is a plain independent clone and receives its
     own `git pull`.
   - If the safe fast-forward pull fails because local files would be
     overwritten, the CLI prints `You can try cgitsync pull-force command`.
   - `pull-force(.cgs/.gts)` is the destructive recovery variant: every
     repository runs `git fetch`, `git checkout -B <branch> FETCH_HEAD`, and
     `git clean -fd`, in `ROOT -> PARENT -> LEAF` order.
   - `pull` (`.cgs` source) also runs the same `.gitignore` sync described
     under `initialise` above, once the tree-wide pull completes.
     `pull-force` does not — it is a destructive recovery command, not a
     lifecycle path this sync is wired into.

3. Global git operations driven by a GitTree instance; same command for all
   GitRepos from leaves to parents to the root project repository:
   - `client.checkout("feature/my-branch")`
   - `client.add()`
   - `client.git(registry, "commit", "message CGS#VERSION")`
   - `client.git(registry, "push")`  — updates hash in GitTree
   - `client.git(registry, "tag", "v1.2.3")`  — updates tag in GitTree

4. `freeze` → emit the next `.gts` id
   - `client.freeze("release-2026.05")`
   - freeze snapshots include deterministic `freeze_manifest` invariants and are
     restored through `launch_state(<snapshot.gts>)`

Python API power users:

- `load(.cgs)` — smart load: parses spec, runs expand+validate pipeline, writes `.gts`
- `load(.gts)` — direct load of a saved snapshot

Additional guidance:

- **`READY`** means the dependency-tree registry is complete and synchronised —
  not that worktrees are clean.
- `initialise` is the canonical entry point; `clone` remains available for direct use.
- `git(tree, command, ...)` is the unified interface for git operations; individual
  `commit`, `push`, and `tag` methods remain available.
- `load`, `expand`, `validate` are internal implementation steps; users do not need
  to call them directly.

---

## Cycle Breaking Engine

`fix_circularities` is the authoritative algorithm for resolving cyclic
cross-references in the dependency registry.  It operates in two phases.

### Phase 1 — SCC detection (Tarjan's algorithm)

A directed dependency graph is built from the registry (function
`_build_path_graph`): each node is an absolute path; each edge goes from the
parent's absolute path to the child's absolute path.

`find_strongly_connected_components(graph)` runs Tarjan's algorithm on this
graph and returns all SCCs.  Any SCC with more than one node represents a
genuine cycle (e.g., A→B→A where A and B are physical repository paths).

For each non-trivial SCC, `_select_scc_anchor` selects an *Anchor* path using
three heuristics applied in order:

1. **Most external incoming edges** — the node with the most edges from
   outside the SCC is the most externally referenced and is preferred.
2. **Closest to project root** — fewest `:`-separated segments in `repo_id`.
3. **Smallest SHA-256 hash** — deterministic tie-breaker on the path string.

All registry entries that resolve to the anchor's path *and* whose parent
belongs to a non-anchor SCC node are *back-edge* entries.  These are flagged
`is_external_reference = True` then removed from the registry.

The `is_external_reference` flag on `WorkingRepo` marks a repository
reference that must **not** be cloned recursively.  It represents a
SYNC_DEPENDENCY edge that has been downgraded to an EXTERNAL_REFERENCE to
break the cycle.

### Phase 2 — Hash-compatibility deduplication

After cycle breaking, entries are grouped by resolved absolute path.  Residual
duplicates (entries not caught by Phase 1) are removed when compatible with
the canonical entry (same lifecycle/sync state, no conflicting commit SHA or
worktree marker).

### Sync stack

`clone_cgs` maintains a `sync_stack: set[Path]` — the set of absolute paths
already entered into the clone pipeline during the current run.
`_pending_clone_entries` excludes:
- entries whose `repo_lifecycle_state` is not `DECLARED`,
- entries whose `is_external_reference` is `True`,
- entries whose `absolute_path` is already in the sync stack.

This provides defence-in-depth against infinite-recursion scenarios where a
residual back-reference escapes the registry cleanup phase.

### Topological sort

`topological_sort(registry)` uses Kahn's algorithm (BFS-based) to return
registry entries in **parent-first** order, which is the safe sequential order
for clone/pull operations.  It is also exported from the public package API.

---

## Local Git Register and Sync Ledger (`.lgr`)

Each project maintains a project-local register file named `<Project_name>.lgr`.
The file is a TOML document with three sections:

| Section | Purpose |
|---|---|
| `[register]` | Current snapshot pointer (id, hash, path) |
| `[[snapshots]]` | Stable `gts-XXXXXX` identifiers, deduplicated by SHA-256 hash |
| `[[ledger]]` | Append-only DAG of sync operation events |

### Register and Snapshots

The `.lgr` register is responsible for:

- assigning one local id to each generated `.gts`
- tracking the current snapshot associated with the project
- staying in sync with the project-local lifecycle state

`print(.gts)` and `pull(.gts)` are available. Snapshot writes update the
project-local `.lgr` register and keep the current snapshot pointer aligned.

### Sync Ledger (`[[ledger]]`)

Every synchronisation operation that produces a `.gts` snapshot is recorded as
an immutable event appended to the `[[ledger]]` array.  Events form a directed
acyclic graph (DAG) via `parent_sync_ids`, enabling full reconstruction of
workspace evolution history.

**Event schema:**

```toml
[[ledger]]
sync_id         = "lgr-000001"      # sequential, lgr-XXXXXX format
parent_sync_ids = []                 # list of parent sync_ids (DAG links)
operation       = "clone"            # command_origin that produced the snapshot
timestamp       = "2026-05-20T19:48:50.159Z"
actor           = "username"         # OS user detected at event time
workspace_hash  = "<sha256>"         # document.snapshot_hash of the .gts file
gts_snapshot_id = "gts-000001"       # links to [[snapshots]] entry
affected_repos  = ["demo", "dep-a"]  # sorted list of repo names in registry
```

**Guarantees:**

- Events are **append-only** — past events are never modified.
- `workspace_hash` is the canonical SHA-256 digest (`GtsDocument.snapshot_hash`)
  linking each ledger event directly to the immutable workspace state.
- `parent_sync_ids` chains events into a DAG; the first event always has an
  empty list.
- `SyncLedger.history()` and `SyncLedger.replay()` return events in topological
  order (parents before children), enabling deterministic replay.

**Python API:**

```python
from ComplexGitSync import SyncLedger

# Direct ledger access
ledger = SyncLedger("project/demo.lgr")
history = ledger.history()   # topological order
replay  = ledger.replay()    # alias for history()

# Via ComplexGitSyncClient
client.get_ledger_history("project/demo.lgr")
client.replay_ledger("project/demo.lgr")
```

---

## What a State's name is computed from

A **State** is one `.gts` snapshot, written at `.cgitsync/state/<hash>.gts`.
The hash is the document's own content digest, so the same tree yields the
same file name on any machine — which is what makes a memory portable, and
what lets two writes over an unchanged workspace produce one State instead
of two.

**A State is named by what it contains; the ledger is ordered by time.**
Those are the two halves, and each keeps out of the other's business: a
State says *what* a workspace held, an entry in the register says *when* it
was seen and by what. Being seen twice is two entries pointing at one
name, which is why nothing counts occurrences in a file name any more.

`document.hash_canonicalisation` says which algorithm computed it. A
document is always measured with the version it declares; a snapshot
written before the field existed is version 1 for ever and is never
silently rewritten.

### Identity, or metadata

The rule: **identity is what the workspace *is*; metadata is what was
observed about it on one machine.** Only identity is hashed.

| Hashed — identity | Not hashed — metadata |
|---|---|
| `project.name` | `project.root_absolute_path` — where this tree was materialised |
| Each repository's `relative_path`, and the tree order that follows from it | Each repository's `absolute_path` and `parent_absolute_path` |
| `name`, `node_type`, provider, owner, repo name, group, provider URL | `source_cgs_path` — where the `.cgs` happened to sit |
| `commit_sha`, the three refs, `fallback_branch` and why it applied | `access_protocol` — ssh or https is a transport preference |
| `repo_lifecycle_state`, `sync_state`, `discovery_state`, `worktree_state`, `is_reachable` | `private` / `writable` — what commands may touch a repository, not what it is |
| `tree_state` and the `freeze_manifest` | `generated_at`, `command_origin` — facts about the run |
| | **Toolchain versions** — cgitsync, git, pixi, dvc, git-lfs |

**Toolchain versions are the one worth stating twice.** They belong to the
ledger entry, never to a State: hashing them would give one tree two names
on two machines running different git versions, and a version bump would
rename every State in a workspace.

Version 1 hashed the three path rows above and ordered repositories by
absolute path. That is a location, not an identity, and it is why the
digest was useless as a name two parties could agree on.

### What sits beside a State

| Path | What it is |
|---|---|
| `.cgitsync/state/<hash>.gts` | The State |
| `.cgitsync/state/<hash>.cgs` | The spec it was built from — part of what that State was |
| `.cgitsync/<project>.lgr` | The register, at one path. It used to be copied into every state directory before each write |
| `.cgitsync/logs/<command>-<timestamp>.log` | A record of a run, named for the run. Two runs leaving the tree identical share one State and keep their own logs |

Writing a State goes through a temporary file in the same directory and one
rename, so a reader never sees a half-written snapshot.

---

## The hash-chained register: schema, storage and threat model

**This is the register ComplexGitSync writes.** One file per entry under
`.cgitsync/lgr/`, hash-chained, appended to by every command that writes a
State. The single-file `.lgr` described in the section above is the older
format: still read — every workspace created before this holds one — and no
longer written by anything.

Its rules were written in `IsolationPlan.md` §2, a planning document that no
longer exists; they are **binding**, so they live here. `src/` cites this
section, not a ticket: an archived ticket is a historical record and is
never edited, and a live schema must not sit inside one.

### Entry schema

One entry is these nine fields, and adding or renaming one is a change to
this section first:

| Field | Meaning |
|---|---|
| `seq` | Position in the chain, from 1, no gaps and no duplicates |
| `prev` | The previous entry's `entry_hash`; the genesis entry carries `sha256:` + 64 zeros |
| `recorded_at` | When the entry was written |
| `command` | The command that produced it |
| `argv` | Its arguments, secrets scrubbed |
| `state_id` | The State the entry records |
| `state_dir` | Where that State was written |
| `outcome` | How the command ended |
| `toolchain` | The versions that produced it: cgitsync, git, pixi, dvc, git-lfs |
| `entry_hash` | `sha256:` over every field above, in canonical form |

The toolchain is inside the hash like every other field, so an edited
version string is as detectable as an edited command. An entry written
before the field existed carries none, and hashes exactly as it did then —
the key is absent from the payload rather than present and empty.

**The canonical form is an explicit field list**, serialised with sorted
keys and no whitespace — never "whatever the record happens to hold" — so
an unrelated addition to the entry object cannot silently change a hash.
`entry_hash` covers every other field and never itself.

### Storage

One file per entry, written with `O_EXCL` so two writers cannot silently
share a sequence number. The `HEAD` pointer beside them is a **cache and is
always treated as untrusted**: it is compared against the chain recomputed
from the entries, never believed. Permission bits are best-effort — a
filesystem that cannot honour them is not a reason to refuse to record
history.

### What is scrubbed

Command arguments and URLs are scrubbed of credentials **before** hashing
and writing, so a secret never enters the chain at all and no later pass
has to rewrite an entry to remove one.

### Threat model, and the rule that follows from it

The register is **tamper-evident, not tamper-proof**. Anyone who can write
the files can edit them; the chain's job is to make that visible.

Two consequences, both load-bearing:

- **A break contaminates everything downstream.** Once a link fails,
  `verify` reports every later entry as unverifiable rather than
  resynchronising on a later entry's own hash. Bytes that are
  self-consistent among themselves still describe a history nobody can
  vouch for.
- **`verify` never heals.** `--repair` corrects the untrusted `HEAD` cache
  and nothing else. Entries are never rewritten or deleted: a register that
  can be edited back into looking clean is evidence of nothing.

### What the chain is checked against

Two passes, and the second became possible only once a State was named by
its content:

- **The chain**, on its own: links, entry hashes, sequence gaps and
  duplicates, and the `HEAD` cache against the recomputed head.
- **The States on disk**: an entry naming a State that is not there
  (`MISSING_STATE`), a stored snapshot whose content no longer hashes to the
  name it is filed under (`STATE_DIGEST_MISMATCH`), and a State on disk that
  no entry records (`ORPHAN_STATE`).

### What a State records about the machine that wrote it

**One path, and it is the tree's own root.** Everything else a State
records — each repository's path, its parent's, the `.cgs` it came from —
is written against the tree as `$CGSTREE/...`, and a path outside the tree
is not recorded at all.

The reason is that a memory gets pushed. A snapshot that said
`$HOME/work/demo/docs` published one developer's directory layout to
everyone who could read the memory; `$CGSTREE/docs` says the same thing
about the tree and nothing about the disk. The root survives because a
snapshot handed to `pull` from outside any workspace still has to say where
its tree goes; it carries no user name, because `$HOME` is substituted.

`$CGSTREE` is deliberately not `$CGSHOME`: that names an environment
variable which may be unset or pointing at a different workspace, and a
path that resolves differently depending on a shell is the trap the token
exists to avoid. A reader resolves it against the workspace it found the
snapshot in — which is what makes a memory cloned onto another machine
rebuild *that* machine's tree — and falls back to the root the document
records.

The same rule governs a ledger entry's `argv`: a path inside the tree
becomes `$CGSTREE/...`, and a path outside it keeps only its file name.

### Which snapshot is "current"

The newest entry names it. Resolution asks the chain first, then falls back
to the single-file register and finally to the most recently modified
snapshot — the two rules that serve workspaces written before the chain
existed. Deciding from a filesystem timestamp is what the register used to
do to pick a parent, and it is what the chain exists to stop.

### The four answers `verify` owes

A verification pass ends in exactly one of these, never a blur of two:

| Answer | When | Exit |
|---|---|---|
| **verified** | A non-empty chain was read and every link checked out | `0` |
| **no history** | Nothing has been recorded here yet. A new workspace is not a broken one | `0` |
| **legacy** | History exists only in the single-file `.lgr` format, which carries no chain: readable, not verifiable | `1` |
| **corrupt** | A chain was read and it does not hold | `1` |

`Finding` enumerates what "does not hold" can mean: `BROKEN_LINK`,
`BAD_ENTRY_HASH`, `SEQ_GAP`, `SEQ_DUPLICATE` and `HEAD_STALE` for the chain
and its cache, plus `MISSING_STATE`, `ORPHAN_STATE` and
`STATE_DIGEST_MISMATCH`, reserved for the store-level pass that becomes
possible once a State is named by its content.

---

## Per-Repo Identity Keys

Every repository entry is identified by three fields: provider, namespace, and
repository name. The namespace field is called `project_owner_name`; note that
GitLab uses the term _group_ for the same concept.

**Provider: `gitprovider`**

One of `github`, `gitlab`, `codeberg`, or `custom`; defaults to `github`.

| Provider | Host URL (auto-set) | Required namespace field | Required name field |
|---|---|---|---|
| `github` | `github.com` | `project_owner_name` | `repo_name` (defaults to `project_name`) |
| `gitlab` | `gitlab.com` | `group_name` (fallback: `project_owner_name`) | `repo_name` (defaults to `project_name`) |
| `codeberg` | `codeberg.org` | `project_owner_name` | `repo_name` (defaults to `project_name`) |
| `custom` | `gitprovider_url` (required) | `project_owner_name` | `repo_name` (defaults to `project_name`) |

> **Terminology note:** GitHub calls the top-level namespace an _owner_;
> GitLab calls it a _group_. This project uses `project_owner_name` for both;
> `project_owner_name` is the portable namespace. For GitLab, an explicit
> `group_name` overrides it when constructing the remote URL.

**`RepoAddress` composition**

`RepoAddress` composes the full remote URL from:

```
<gitprovider_url>/<project_owner_name>/<repo_name>[.git]   (SSH or HTTPS)
```

- SSH format: `git@<host>:<project_owner_name>/<repo_name>.git`
- HTTPS format: `https://<host>/<project_owner_name>/<repo_name>.git`

Access protocol defaults to `ssh`; use `https` only when explicitly selected.
`gitprovider_url` is required when `gitprovider` is `custom`; it is
automatically inferred for `github`, `gitlab`, and `codeberg`. No host is
guessed for `custom`.

---

## Logging — Additional Events

On top of the general DevSpecs logging requirements, the following events must
always be preserved in file logs regardless of console verbosity:

- command start and end
- `GitTree` and `GitRepo` state transitions
- fallback proposals and decisions
- `.gts` writes and loads
- validation failures
- readiness-gating failures
- release operations

`whisper_sync` mode may reduce informational console noise but must **never**
suppress `WARNING`, `ERROR`, fallback decisions, `.gts` events, or state
transitions.

CLI display requirements:

- `initialise(.cgs)` must explicitly show the lifecycle pipeline
  (`load -> expand -> validate -> clone -> gitignore`).
- command output must explicitly show the selected per-run log file path
  (`log_file=...`).
- git actions must print the concrete git command being applied.
- tree display should have a minimalist repo-only outline (project / parent /
  leaf with indentation or line connectors).

---

## Testing

- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Integration suite includes: CGSi topology expansion checks, local file-remote
  `clone_cgs` / `launch_release` lifecycle restoration, and a CLI-first READY
  `.gts` git command cycle (`add → commit → push → tag → freeze`) mirrored in
  Python API.
- Install dev extras: `pixi install`
- Run suite: `pixi run test` from the repository root
- Tests must not depend on network access or live git remotes.

---

## Branches and ticket topics

`main` is where ComplexGitSync's work lands, with two exceptions.

| Workstream | Branch | Ticket filename prefix |
|---|---|---|
| Everything else | `main` | `main_` |
| Memory — `.cgitsync/`, the state area, the register/ledger, `memory/` and the distant reference ledger | `memory-dev` | `memory-dev_` |
| Data — the `DataManager` layer, the DVC backend, `data_backend`/`data_paths`, and data materialisation and publication | `data-repo` | `data-repo_` |

**Every change to a project's memory is developed on `memory-dev`.** The
memory work is seven dependent milestones — see the MemoryArchitecture
ticket in [DevTickets/openTickets/](DevTickets/openTickets/) — that between them rename the state
area, rewrite the register, move code into a new `memory/` package and add
a network protocol. Interleaving those with releases on `main` would put a
half-migrated memory format in front of users, and the one thing this
project cannot afford to corrupt by accident is the record of what it
synchronised. `memory-dev` merges into `main` when a milestone is finished
and `pixi run lint` and `pixi run test` both pass.

`memory-dev` and `data-repo` are this project's branches other than
`main`, so those three are the only ticket filename prefixes it has. An
open memory ticket is named
`.localSpec/DevTickets/openTickets/memory-dev_<priority>-<rank>_<Name>_DevPlanTicket.md`
and carries `*Branch: memory-dev*` under its `*Created:*` line; every other
open ticket is `main_<priority>-<rank>_<Name>_DevPlanTicket.md` and carries
`*Branch: main*`. The prefix is written out in both cases — `main_` is not
implied by its absence. Both conventions are defined in
[.agentSpec/TICKETLIFECYCLE.md](../.agentSpec/TICKETLIFECYCLE.md) §2.3 and
§3 — this section only says which branches exist here.

**Every change to the data layer is developed on `data-repo`.** The data
work is six dependent milestones — see the DataArchitecture ticket in
[DevTickets/openTickets/](DevTickets/openTickets/) — that between them add a
`.cgs`/`.gts` declaration, a `DataManager` dispatch layer, a DVC backend,
and new refusals in the authoring, materialisation and release paths. A
half-built data layer that stages a multi-gigabyte dataset into Git, or
freezes a release whose data cannot be fetched, is not something to ship by
accident on `main`. The branch merges back when a milestone is finished and
`pixi run lint` and `pixi run test` both pass. DVC itself stays an optional
Pixi feature: a Git-only project installs none of it.

The prefix replaced an earlier topic prefix (`memDev-`), which named the
same group one spelling differently and left the reader to map the two.
See `DevTickets/archive/20260916_TicketBranchNaming_DevPlanTicket.md`.

The private configuration repositories mounted in the developer tree keep
their own branches (`.localSpec` and `.claude` on `ComplexGitSync`,
`.agentSpec` on `main`), and this rule does not change them: a memory
ticket edited in `.localSpec` is still committed on the `ComplexGitSync`
branch of `.localSpec`. The branch line names the branch of the project's
own repository.

---

## Versioning

The authoritative version is kept in `pyproject.toml`. CI auto-increments it
on every push or merge to the main branch following the `YYYY.XX` scheme
defined in `DevSpecs.md`.

For a manual bump (e.g. after finishing a feature branch, before CI runs),
use `pixi run bump-version` (`scripts/bump_version.py`). It reads the
current version from `pyproject.toml`, computes the next `YYYY.XX` value,
and writes that same value into every other file that mirrors it —
**six in total**:

| File | Field |
|---|---|
| `pyproject.toml` | `[project].version` — the authoritative one |
| `pixi.toml` | `[workspace].version` |
| `src/ComplexGitSync/__init__.py` | `__version__` |
| `README.md` | the version in the title heading |
| `docs/Setup/Shortcuts.tex` | `\newcommand{\cgsversion}{...}` |
| `docs/preamble.tex` | `\newcommand{\cgsversion}{...}` |

Pass `--dry-run` to preview the `old -> new` transition without writing
anything.

**The bump is all six files or none of them.** The version is one fact; a
run that wrote four manifests and then failed on the docs would leave the
package claiming a release its documentation has never heard of, and would
do it quietly enough that the release still looked finished. So
`apply_version()` reads and rewrites every target in memory first, and only
a complete set of new texts reaches the disk. A missing file, an unwritable
one, or a version field the patterns cannot find stops the whole bump with
nothing changed.

The last two live in `docs/`, a separate repository (`DocComplexGitSync`).
When they are absent — a checkout of `ComplexGitSync` alone — the script
dogfoods `cgitsync initialise examples/complexgitsync4dev.cgs` to clone them
into place, *before* the first write rather than after four of them.
Working on this repository from a standalone checkout is legitimate;
releasing from one is not, which is why `tests/unit/test_bump_version.py`
skips its two docs checks there instead of failing. Those checks assert both
that each `\cgsversion` macro is still reachable by the script's pattern and
that its value equals `pyproject.toml`'s — matchability alone let 2.49 ship
with its documentation left on 2.48.

`bump-version` rewrites `.tex` sources only. The tracked PDFs in `docs/`
embed the version on their title pages, so rebuild them (`cd docs &&
latexmk -pdf MASTER.tex`, plus each `c_*.tex`) and commit the result in the
same change.
