# AdditionalSpecs — ComplexGitSync-Specific Constraints

*Created: 2026-05-13*

This file documents project-specific constraints and refinements that apply
**on top of** the general [DevSpecs](../../.distant/dev-sync/DevSpecs.md). Every rule in `DevSpecs.md`
applies here; this file only adds or tightens rules for `ComplexGitSync`.

**Planning lives next door.** `.agent/.local/.localSpec/DevTickets/` holds every planning
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
(`.agent/.local/.localSpec/DevTickets/archive/20260828_Isolation_DevPlanTicket.md`) — `orchestre.py` used to
carry most of this table's Tier 2/3 responsibility directly; it now
delegates each to its own module. See each module's own docstring header
(`Ring:`/`Contract:`/`Imports:`, `.agent/.local/.localSpec/DevTickets/IsolationPlan.md` §3.2) for the
authoritative, machine-cross-checked version of this table — this is the
human-readable summary.

| Module | Ring | Responsibility |
|---|---|---|
| `errors.py` | 0 | The package's public exception hierarchy. |
| `git_repo.py` | 0 | Per-repository identity types, state enumerations, provider registry, remote-URL construction. Also `RepoScope`, the one definition of which repositories a tree-wide command may touch: `private` marks a repository that configures the project rather than being it, shared with the author's other projects, read-only unless the `.cgs` entry adds `writable = true`. `RepoScope.includes` reads `effective_private`/`effective_writable`, the flags after `git_tree.propagate_privacy` has pushed each parent's privacy down; the declared `private`/`writable` are what gets serialized. `RepoScope` does not know about the memory mount, and since `memory-dev_WorkingTransitionState` (2026-09-17) nothing else needs to either: the mount sits at `.cgitsync/.memory`, one level inside the workspace's own live state area (`.cgitsync` itself — States, the ledger, logs), so it is an ordinary private/writable repository everywhere — `add`/`commit`/`push`/`pull`/`merge`/`tag`/`freeze-release` all reach it the same way they reach `.localSpec`/`.claude`, with no scope exclusion, no preflight exemption, and no `WorkingRepo` field marking it out. Only `memory push`'s own fold (`orchestre._fold_memory_pending`) ever writes into its worktree, moving `.cgitsync`'s pending `lgr`/`state`/`logs`/`commit-logs`/`.cgs` into the mount before committing — which is what makes the mount reliably clean the rest of the time. `memory push` still bypasses the ordinary write-scope refresh (it commits directly via `git_runner`, not through `commit_tree`/`push_tree`), so `orchestre.write_gts_snapshot` separately re-reads the mount's actual `commit_sha`/branch — read-only, every State, regardless of which command triggered it (`orchestre._refresh_memory_mount_state`, `memory-dev_MemoryRecordedRefresh`) — or `status`'s `HEAD ending with *` marker would appear the first time `memory push` moved it and never clear again. |
| `git_branch.py` | 0 | The single owner of the `.cgs` branch fallback chain (`fallback_branch` → `default_branch` → `project.default_branch` → `DEFAULT_BRANCH`) and of the privacy rule that decides what a repository targets under a tree-wide branch move. A pure resolver: declared fields in, a `BranchResolution` (branch, `RefKind`, and the `BranchSource` that answered) out. Holds no tree, no root and no privacy *state* — `git_tree.py` owns those, and `git_tree_branch.py` owns branch state the same way (which branch the tree is on, and which branch each repository is actually on). Also owns the private/local naming rule: `private_local_branch` composes `<project name>` on `main` and `<project name>_<branch>` otherwise, and `PRIVATE_LOCAL_SEPARATOR` never leaves this module — `tests/unit/test_git_branch.py` fails if either escapes, the same guard the `"main"` literal already has. `resolve_propagated_ref` now answers three cases, not two: a project repo follows the move, private/distant never moves, private/local takes the derived branch. |
| `ledger_entry.py` | 0 | Hash-chained register-entry construction and canonicalisation (pure chain math). |
| `integrity.py` | 0 | `Finding` taxonomy and `verify_chain` — pure arithmetic checks over a register-entry sequence. |
| `json_render.py` | 0 | The machine-readable shape of what a command reports — `status`, `verify`, and the error object a JSON-capable command prints when it fails — with `SCHEMA_VERSION` and the serialiser. One module for every command's shape, so field names are decided once rather than re-invented per command, and `cli/` carries none of them. Separate from `status_render.py` on purpose: that renders one table for humans, where a column can be renamed when the wording improves; a JSON field cannot, because something is parsing it. The promise is **additive only**. See `.agent/.local/.localSpec/DevTickets/archive/20260916_CliContract_DevPlanTicket.md`. |
| `status_render.py` | 0 | Pure text rendering for `cgitsync status`'s repository table, including the `SCOPE` column. That column is where the developer vocabulary is translated for end users: `private` reads as **private**, `writable` as **local**, private read-only as **distant**, and a repo that is not private as **project**. `_status_scope_label` is the only place that mapping lives; it reads the effective flags, so a repo nested in a private one is labelled like its parent. Docs, tutorials and CLI output use the user words; code, docstrings and this table keep `private`/`writable`. |
| `config_document.py` | 0 (+ Ring-1 adapter) | Pure `ConfigDocument` base — dict wrapping, dot-path reads, the `validate()` hook. |
| `config_document_io.py` | 1 | `ConfigDocumentIOMixin` — the six file-I/O methods (`from_toml`/`to_toml`/etc.) `ConfigDocument` used to carry directly. |
| `environment_spec.py` | 0 | Pure Environment record/Drift value objects, canonical digest, and static validation for `.cgs` `environment_root` and `[environment]` requirements. `tree_env.py` re-exports these values but does not own their schema, which lets the Ring-1 store import downward. |
| `cgs_format.py` | 0 (+ Ring-1 adapter) | `.cgs` TOML parsing, authoring grammar (`parse_repo_id` — the *only* implementation), normalization, static validation, `CgsDocument`, minimization, serialization. |
| `gts_document.py` | 0 (+ Ring-1 adapter) | `.gts` runtime state-snapshot parsing/validation; the one canonical content-hash builder. |
| `master.py` | 1 | Local, workspace-scoped Git identity for ComplexGitSync's own automated commits; persisted per `CGSHOME` via `.cgitsync/master.toml` — not part of the `.cgs`/`.gts` project spec. |
| `paths.py` | 1 | Environment-marker path portability (`$HOME`/`%USERPROFILE%`/etc.) and `CGSHOME`/`CGSPATH` resolution. |
| `state_store.py` | 1 | The one place that composes a State's path: `.cgitsync/state/<hash>.gts`, where the hash is the document's own content digest (`state_path`). Still reads the older `state(<hash>)_n/` directories, so a workspace written before the flat layout resolves without being rewritten — and `snapshot_resolver.py` imports that grammar from here rather than carrying the copy it used to. Formerly content-addressed directory allocation — the general mechanism every lifecycle command uses (not related to the deleted Memory transport, despite the class name). |
| `settings.py` | 1 | Where ComplexGitSync keeps its own workspaces, answered before any workspace is open — which is what separates it from `master.py`, whose `.cgitsync/master.toml` cannot be read until one has been found. Owns the root (`$CGSPATH`, else `$HOME/.cgs`), the **default workspace** that `snapshot_resolver.py` falls back to when none of its three inputs finds one, the `$HOME/.cgs/default` pointer that makes that workspace minted-once-then-reused, the empty but valid `.gts` written into it (`UNLOADED`, `is_ready = false` — an empty tree must never claim to be ready), the list of other workspaces under the root that the CLI prints as a hint and never selects from, and the `UseCase` (`STANDALONE`/`NESTED`) derived from whether the running installation sits inside the resolved CGSHOME. Derived, never stored: two callers in one process cannot disagree. See `.agent/.local/.localSpec/DevTickets/archive/20260916_CgshomeDefault_DevPlanTicket.md`. |
| `snapshot_resolver.py` | 1 | Resolves which `.gts` snapshot the CLI defaults to when a command omits one explicitly — and, when none of its three inputs finds a workspace at all, falls back to `settings.py`'s default workspace rather than raising (`CGSHOME_ORIGIN_DEFAULT`), except under an explicit `--search-dir`, where a directory the user named is never silently replaced, and — through its `describe_*` functions — reports *which input decided it*: `--search-dir`, `$CGSHOME`, or the current directory, in that order of precedence. The precedence is deliberate (the documented bootstrap tells users to export `$CGSHOME`), which is exactly why the reason has to travel with the answer: a stale export silently retargets every command at another workspace that holds the same repositories. This module never prints — `cli/_shared.py` turns a `CgshomeResolution`/`SnapshotResolution` into the `cgshome=`/`source=` lines and the mismatch warning. |
| `memory/` | 1 | **Everything a workspace remembers, in one package.** `repository.py` defines the memory mount and branch without running Git — including, now, self-history's own nested mount: `config_memory_document()` renders the `.cgs` that makes `.self-history` a discoverable child of `.memory`, and `self_history_mount_path`/`self_history_commit_message` give it the same path/commit-message shape `.memory` itself has. `states.py` owns States; `environment.py` atomically stores content-addressed Environment records; `agent_contract.py` atomically stores content-addressed `AgentContractRecord`s the same way, under a caller-given `dev-sync` directory rather than `.cgitsync/` — signed once per provider, not scoped to one workspace — plus a plain `current` pointer naming the record in force; `self_history.py` stores content-addressed `SelfHistoryRecord`s the same way again, under `.cgitsync/.self-history/` (pending) and `.cgitsync/.memory/.self-history/` (folded, a repository of its own once adopted — `orchestre.py`'s `_adopt_self_history_if_declared`/`self_history_adopt`, AgentReport WP2/WP2b); `ledger_entry.py`/`ledger_store.py` own the hash chain; `commit_log.py` owns commit/publish evidence; `integrity.py` verifies; `store.py` reads the legacy register. `pending.py` merges folded and pending views so callers do not care where an entry, State, Environment, or log currently sits. **No Git, ever**: repository operations remain in `operations.py`/`git_runner.py`. |
| `discovery.py` | 1 | Nested `.cgs` auto-discovery and `.gitmodules` parsing. |
| `git_tree.py` | 1 | `GitTree`/`WorkingGitTree` structures, traversal, lifecycle state; `to_cgs()` delegates to `cgs_format.py`; `.gitignore` maintenance across the tree (`sync_gitignore`) — the reason this is Ring 1, not 0. Also the single rule for "which repo sits inside which": `resolve_repo_for_path` for a live tree, `innermost_containing_path` for plain paths before one exists. Owns privacy *state* as well: `propagate_privacy` pushes each parent's `private`/`writable` onto everything nested inside it (a parent defines its leaves; a leaf may restrict itself further, never open itself wider) and records the answer in `WorkingRepo.propagated_private`/`propagated_writable`. Every build path calls it beside `normalize_node_types`. |
| `git_tree_branch.py` | 2 | The tree's branch *state*, and the counterpart to `git_branch.py`'s *rule*: which branch the tree is on (the root's — what `status` prints as `cgitsync_branch`), which branch each repository targets when the tree moves (`target`, a pass to `git_branch.resolve_propagated_ref` with the project's name filled in), which branch Git says each is on (`observed`, read once per repository and cached so one `status` costs one call per repository instead of two), and where the two disagree (`deviations`). Also holds `tree_project_name`, moved here from `operations.py` because the project's name exists in that code path only to name a private/local branch. Restates no rule: every answer it gives comes from `git_branch.py`. Four call sites computed all of this separately before it existed — `validate_branch_topology`, `_collect_branch_alignment_diagnostics`, `_branch_incoherence`, and the root read in `_restart_tree_common` — and the three that asked the same question disagreed about a detached root. `deviations(ignore_unreadable=...)` keeps the one difference that is real: a report skips a repository Git cannot answer for, a preflight gate must not. An instance is a snapshot — build a new one after a checkout or a pull. See `.agent/.local/.localSpec/DevTickets/archive/20260916_StatusCurrentBranch_DevPlanTicket.md`. |
| `provider.py` | 0 | **Which command-line tool creates a repository on which host, and with what arguments.** Runs nothing: `git_runner.run_tool` does that, for the same reason `toolchain.py` asks it for a version. Holds no credential, reads none and sends none — `gh`, `glab` and `tea` each keep their own, under their own `auth login`. The owner or group comes from `parse_repo_id` and from nowhere else. |
| `toolchain.py` | 2 | The five version strings every ledger entry records — cgitsync, git, pixi, dvc, git-lfs — read at most once per process and reported as `none` when a tool is not installed. Asks `git_runner.tool_version` rather than importing `subprocess`, so the single-importer rule holds. A data backend is asked only when the operation being recorded used one: `dvc --version` starts a Python interpreter and would be felt on every `status`. |
| `tree_env.py` | 2 | Observes secret-free machine, tool, provider-authentication, environment-root and manifest facts; content-hashes that record and compares it with `.cgs` requirements. Reads manifests but stores only tree-relative pointers and digests. |
| `git_runner.py` | 2 | Git subprocess wrapper — the *only* module that imports `subprocess`, and therefore the one place the **decoding policy** for Git output lives. Git writes bytes, not text: `merge-tree`'s legacy form prints the content of the files it could not merge, and paths need not be UTF-8 either. Both wrappers (`_run`, `_query`) decode with `errors="replace"`, and `_query_bytes` hands back the raw bytes for the one caller that searches output it does not control. Strict decoding used to raise before the caller could read the exit code — see `AgentSpec/archive/20260910_MergeOutputDecoding_DevPlanTicket.md`. Owning the subprocess boundary also means owning the **environment** those subprocesses run in: `_non_interactive_git_env()` both stops Git blocking on a credential prompt and pins the language Git writes its messages in. ComplexGitSync reads Git's prose — no exit code says whether a fetch failed for want of credentials — so a translated message silently cost non-English users the `--force-protocol` recovery hint. `_english_message_locale()` is the only place that decision lives; it removes an inherited `LC_ALL` after copying its value into every other category, so only the language changes and encoding and collation are left alone. `LC_ALL=C.UTF-8` is the obvious fix and does not work: gettext still consults `$LANGUAGE`. See `AgentSpec/archive/20260911_GitLocaleIndependence_DevPlanTicket.md`. Every method that asks Git a question goes through `_query`/`_query_bytes`; none calls `subprocess.run` directly, which is what makes both the decoding policy and the environment policy inescapable rather than merely conventional. `can_merge_cleanly` returns the conflicting paths rather than a verdict, and reads both Git forms into the same answer: the modern form stops at the blank line before Git's notes, and the legacy form keeps a path only when its own block carries a conflict marker, since "changed in both" alone is not a conflict. A binary conflict prints no marker at all and is detected from Git's stderr warning — it used to be reported as clean, which let a tree-wide merge pass the preflight and then break halfway. See `AgentSpec/archive/20260910_MergeConflictReporting_DevPlanTicket.md`. |
| `clone_guard.py` | 2 | Answers one question about a directory `initialise` is about to delete and re-clone: **would clearing this lose work that exists nowhere else?** Two read-only checks per destination — a dirty worktree, and commits reachable from `HEAD` that no remote-tracking ref holds. The second is deliberately *not* "is the branch ahead of its upstream": that form both misses a branch with no upstream carrying local commits, and wrongly blocks a detached `HEAD` parked on a commit the remote already has — which is exactly what a submodule checkout is, and what `init-from-submodules` depends on. Touches no worktree, which is what lets `orchestre.py` ask about every pending repository before deleting any of them, so a refusal anywhere leaves everything on disk. Decides nothing about whether a mount point is owned outright — that is `AppendCloneMode`'s question about the same `shutil.rmtree`. See `AgentSpec/archive/20260910_InitialiseDestroysExistingClones_DevPlanTicket.md`. |
| `operations.py` | 2 | Leaf/parent-first Git operations over a `WorkingGitTree` + `GitRunner`. Asks `git_tree_branch.py` which branch the tree is on and which branch each repository should follow, rather than working it out per call site — `checkout_tree`, `branch_tree`, `add_tree`, `commit_tree`, `push_tree`, `tag_tree`, `freeze_release_tree`, branch-topology validation. Requires a `READY` tree; raises `TreeNotReadyError` otherwise. `add_tree`/`commit_tree`/`push_tree` each return one `RepoOutcome` per repository they visited — what changed there, or why nothing did — so a sweep that wrote nowhere is distinguishable from one that wrote everywhere. Every scoped operation here — these three, `_restart_tree` behind `pull`/`pull-force`, `merge`/`tag`/`freeze-release` — iterates via plain `iter_tree_leaf_first`/`iter_tree`, with no memory-mount exclusion anywhere: since `memory-dev_WorkingTransitionState` the mount's own worktree is written to only by `memory push`'s fold, so it needs no more routing-around than `.localSpec`/`.claude` do, and preflight (`_run_preflight_checks`/`_collect_*_diagnostics`) needs no exemption for it either — a folded, pushed memory is simply clean. The client stores the write-outcome tuple on `ComplexGitSyncClient.last_write_outcomes` and `cli/` prints it; deciding what happened stays here. `remove_paths` reports the same way, and is the one scoped operation handed its paths rather than sweeping for them: its scope is checked against the repository each path resolves to — a filter — and one path outside it refuses the whole call before any removal. Bare `rm` keeps its original reach (`RepoScope.ALL`); `cli/_shared.py` warns when that reach lands in a configuration repository. |
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

Added by `.agent/.local/.localSpec/DevTickets/archive/20260828_Isolation_DevPlanTicket.md` (P6) once the
isolation work gave the package enough real modules for these rules to be
checkable rather than aspirational. See `.agent/.local/.localSpec/DevTickets/IsolationPlan.md` for
the full design rationale; this section is the enforced-in-practice
summary, and the authoritative source the rest of the docs (`CLAUDE.md`,
`docs/DevGuide/architecture.md`) point back to.

### The ring table

Imports flow downward only — a module may import from a lower-numbered
ring, never a higher one.

| Ring | Modules |
|---|---|
| 4 — ADAPTER | `cli/` package (`_shared.py`, `minimalist.py`, `expert.py`, `configuration.py`, `environment.py`, `suggest.py`, `__init__.py` assembling them) |
| 3 — ORCHESTRATION | `orchestre.py` (`Orchestre`, `ComplexGitSyncClient`) |
| 2 — GIT PROCESS | `git_runner.py` (sole `subprocess` importer), `clone_guard.py`, `git_tree_branch.py`, `operations.py`, `registry.py`, `toolchain.py`, `tree_env.py` |
| 1 — FILESYSTEM | `paths.py`, `universal_clock.py` (sole reader of the real wall clock/PID/entropy source — see `.agent/.local/.localSpec/DevTickets/archive/20260920_UniversalClock_DevPlanTicket.md`), `memory/` (`states`, `environment`, `agent_contract`, `self_history`, `ledger_entry`, `ledger_store`, `commit_log`, `integrity`, `store`, `repository`), `settings.py`, `snapshot_resolver.py`, `discovery.py`, `master.py`, `git_tree.py` (`.gitignore` writes) |
| 0 — PURE / OFFLINE | `errors.py`, `git_repo.py`, `git_branch.py`, `provider.py`, `environment_spec.py`, `ledger_entry.py`, `integrity.py`, `json_render.py`, `status_render.py`, plus the Ring-0 core of `config_document.py`/`cgs_format.py`/`gts_document.py` (each also carries a Ring-1 I/O adapter for real call-site compatibility — see those modules' own docstrings) |

### The five import rules (machine-checked)

1. **No upward imports.** Ring *n* imports from rings `< n` only.
2. **`import subprocess` appears in exactly one module** — `git_runner.py`.
3. **Ring 0 performs no I/O at all** — no `subprocess`, no `open()`, no
   `pathlib` writes, no `os.environ`, no clock reads. Enforced for modules
   listed in `scripts/ceiling_baseline.json`'s `ring0_modules` by
   `pixi run check-ceilings`; extend that list as more modules earn it.
4. **Ring 1 performs no `subprocess`.** Filesystem only.
5. **`datetime.now`/`datetime.utcnow`/`time.time_ns`/`os.getpid`/
   `secrets.token_hex` appear in exactly one module** — `universal_clock.py`
   (Ring 1), which defines `ClockProtocol` and `SystemClock`, the real
   implementation. Every other module injects a `ClockProtocol` rather than
   reading the wall clock, PID or entropy source itself — the same shape as
   rule 2, and enforced the same way, unconditionally, by
   `pixi run check-ceilings` (not tied to a declared subset the way rule 3
   is). `memory/ledger_entry.py` keeps a structurally identical
   `ClockProtocol` of its own — Ring 0 must be self-contained, so it cannot
   import Ring 1's — which Python's structural typing makes interchangeable
   with the canonical one at every call site. See
   `.agent/.local/.localSpec/DevTickets/archive/20260920_UniversalClock_DevPlanTicket.md`.

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
`.agent/.local/.localSpec/DevTickets/archive/20260826_Deletion_DevPlanTicket.md` and
`.agent/.local/.localSpec/DevTickets/archive/20260828_CleanupPass2_DevPlanTicket.md` used successfully; the isolation
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

An author may also identify the repository where the working environment is
installed and declare requirements that observation alone cannot infer:

```toml
environment_root = "my-project"

[environment]
tools = { git = "2.43", pixi = "0.66" }
compilers = ["cc"]
system_libraries = ["libssl"]
services = ["postgresql"]
manifests = ["Cargo.lock"]
```

The root must name a configured repository (or `root`). Dependency values are
minimum versions when supplied. Manifest entries extend the fixed discovery
list; Environment records keep their tree-relative paths and digests, never
their contents. `initialise` and `pull` only warn about drift, while the
explicit `cgitsync env check` command returns non-zero for missing or older
requirements and never installs anything.

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

**A reader that meets a version it does not know refuses by name, before
computing anything.** This is the general rule every stored format in this
project follows, not a `.gts`-specific one: a document declares its own
version, and a build encountering a *higher* one than it understands must
say so and stop, rather than apply its own rules to a payload it was never
designed for. Applying today's canonicalisation to a document written
under tomorrow's produces a hash that is simply wrong — not close, not a
useful approximation — and a wrong hash next to a mismatch check reads as
*corrupt*, which is the worst possible answer, because it is not true and
it invites deleting the one thing that was fine. This is exactly what
happened once, self-hosted (`SnapshotVersionGuard`,
`.agent/.local/.localSpec/DevTickets/archive/20260918_SnapshotVersionGuard_DevPlanTicket.md`):
`checkout main` wrote a version-2 State and, in the same run, swapped this
editable checkout's own code to a build that only understood version 1 —
which then recomputed the hash the old way, got a different digest, and
reported a perfectly good snapshot as corrupt. `GtsDocument.compute_snapshot_hash`
now raises `UnsupportedSnapshotFormatError` — a `ConfigValidationError`
subclass the CLI maps to exit `2` unconditionally, even under `validate` —
the moment a document's declared `hash_canonicalisation` exceeds
`CURRENT_HASH_CANONICALISATION`, before `_build_canonical_payload` runs at
all. A version this build *does* know, including every legacy one still on
disk, is completely unaffected: the guard only fires going forward in
time, never backward.

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
| | **Environment records** — machine, Python and tool versions, credential facts and manifest digests |

**Toolchain versions are the one worth stating twice.** They belong to the
ledger entry, never to a State: hashing them would give one tree two names
on two machines running different git versions, and a version bump would
rename every State in a workspace.

**The tool's own version leaked in exactly this way, from version 2 until
version 3 closed it.** `hash_canonicalisation` was meant to be the one
fixed format marker; version 2's payload also put `CGS_VERSION` — the
running package's own version — inside the `document` block it hashed,
never pinned to a real fixed value, so it read back whatever `__version__`
happened to be at write time. Two machines on different builds, or one
machine before and after an upgrade, computed two different names for the
identical tree — precisely the failure the paragraph above describes,
just not yet found when it was written
(`memory-dev_1-2_StateVersionLeak_DevPlanTicket.md`). Version 3 drops that
block from the payload entirely; every version-2 document already on disk
keeps validating under version 2, leak included, for as long as it declares
that version — the same rule that already protects version-1 documents.

Version 1 hashed the three path rows above and ordered repositories by
absolute path. That is a location, not an identity, and it is why the
digest was useless as a name two parties could agree on.

### What sits beside a State

| Path | What it is |
|---|---|
| `.cgitsync/state/<hash>.gts` | The State |
| `.cgitsync/state/<hash>.cgs` | The spec it was built from — part of what that State was |
| `.cgitsync/env/<hash>.toml` | The content-addressed Environment record observed when a ledger entry was written; metadata only, never part of the State hash |
| `.cgitsync/<project>.lgr` | The register, at one path. It used to be copied into every state directory before each write |
| `.cgitsync/logs/<command>-<timestamp>.log` | A record of a run, named for the run. Two runs leaving the tree identical share one State and keep their own logs |
| `.cgitsync/.cgs/<project>-<branch-slug>.cgs` | The stable copy of the hand-authored spec the tree was last built from — one file, overwritten on every write |
| `.cgitsync/.memory/.cgs/<project>-v<N>.cgs` | **Not** the stable copy above, and never overwritten: `memory reboot`'s export of the tree's *current shape* (`to_cgs()` against the loaded `.gts`, not a hand-authored file), one file per reboot, `N` incrementing from the implicit, never-written `v1`. A permanent, ordered record of every shape this project's memory has ever described — the one thing a reboot's own "clear this branch's tracked content" step does not clear (`memory-dev_1-4_MemoryReboot_DevPlanTicket.md` §1.4, §2) |

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

One entry is these twelve fields and the hash over them, and adding or
renaming one is a change to this section first:

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
| `commit_log` | The digest of the commit-log rows this entry wrote; absent when it wrote none |
| `environment` | `env(<hash>)`, pointing to `.cgitsync/env/<hash>.toml`; absent when none was observed |
| `release` | `semver`, `git_tag`, and one `artefact:<name>` pair per versioned artefact (`src` and `agent_contract` today; `data` once that ticket lands); absent except on the entry `freeze_release()` writes for an actual release |
| `entry_hash` | `sha256:` over every field above, in canonical form |

The toolchain is inside the hash like every other field, so an edited
version string is as detectable as an edited command. An entry written
before the field existed carries none, and hashes exactly as it did then —
the key is absent from the payload rather than present and empty.
`commit_log`, `environment`, and `release` were added the same way and
follow the same rule: an older entry omits them and therefore retains its
original hash.

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
- **The commit logs**: rows that no longer digest to what the entry that
  wrote them recorded — edited, added or removed (`COMMIT_LOG_MISMATCH`) —
  and commit messages kept under a State that is gone
  (`ORPHAN_COMMIT_LOG`). The second is reported and never deleted: removing
  a record because the thing beside it went missing is how a record stops
  being one.

### Merging when the tree contains the tool

`pixi.toml` installs this checkout editable and the developer tree *is*
`CGSHOME` — the `NESTED` use case `settings.py` names. So a tree-wide
checkout rewrites the code that runs the **next** command.

> **A checkout and the merge that follows it must be one command.**
> `cgitsync checkout <older>` then `cgitsync merge <newer>` makes the older
> build perform the merge, against a workspace the newer one wrote.

`merge --into <target>` (`operations.merge_into_tree`) is that one command.
The property it relies on is that **Python imports its modules at start-up**,
so a running process keeps the build it began with whatever happens to
`src/` underneath it; the code on disk when it finishes is the merged code.
Nothing may be inserted between its checkout and its merge that starts
another process, and the two must never be split into separate commands
again.

Three supporting rules:

- **Every repository is checked before any is touched**, so a conflict or a
  missing target leaves the whole tree on the source branch — the promise
  `merge_tree` already made, extended to cover the checkout.
- **`checkout` warns and never refuses** when it is about to install a
  different build (`ComplexGitSyncClient._warn_if_build_changes`). Checking
  out an older branch to read it is legitimate; `main_1-2_SnapshotVersionGuard`
  is what makes that older build fail honestly if it is then used.
- **A scoped call's preflight does not check branch alignment.** The shared
  preflight (`operations._run_preflight_checks`) enforces "this repository
  is on the branch the tree expects" for every other command, because for
  them that is a real precondition — `checkout`/`branch` were meant to have
  put it there already. `merge --into` is the one command whose job is
  taking a repository *from* wherever it sits *to* the branch named by the
  call, so "not yet there" is this command's input, not a fault. Without
  this, a `--private` or `--all` call run after an earlier scoped `--into`
  would refuse the very repositories it exists to move — see
  `main_1-1_MergeIntoScopeSync`.

### Creating a repository: the one thing this project asks another tool to do

ComplexGitSync used to state that it never creates a repository on a host,
"because that would mean a network call and a stored credential where there
is neither". The second half was the reason, and it still holds. The rule is
therefore amended rather than dropped:

> **This project stores no credential and implements no provider's API.**
> When a repository must be created, it runs the provider's own
> command-line tool, which the user has already signed in to.

| Provider | Tool | Signed in with |
|---|---|---|
| `github` | `gh` | `gh auth login` |
| `gitlab` | `glab` | `glab auth login` |
| `codeberg` / Gitea | `tea` | `tea login add` |

`provider.py` (Ring 0) decides which tool and which arguments;
`git_runner.run_tool` runs it, because that module is the project's only
`import subprocess` and a second importer would put the decoding and
environment policies out of reach. The same split `memory/repository.py`
already uses: decide in one place, run in another.

Three answers, and none of them is an exception for the ordinary cases:

- **created** — it did not exist and now does.
- **exists** — it was already there. Asked with `git ls-remote` before any
  tool runs, so creating a repository twice costs nothing and cannot fail.
  This is the normal answer for anybody who created it by hand first.
- **unavailable** — the tool is missing or signed out. The command to run is
  returned, and the exit code is `2` (*could not run*) — which is what this
  project did for repository creation before it could do any of it.

Everything else about a repository is still plain Git.

### The commit log: what was written, and whether anyone else has seen it

**One file per State**, at `.cgitsync/commit-logs/<state hash>.toml`, so
"given this State, what was committed?" is answered by swapping one
directory name. Two tables, both **append-only**:

| Table | One row per | Fields |
|---|---|---|
| `[[commit]]` | Repository a `commit` wrote to | `entry`, `repository`, `repo_id`, `scope`, `branch`, `sha`, `message`, `authored_at` |
| `[[published]]` | Commit a `push` made public | `entry`, `repository`, `sha`, `remote`, `ref`, `at` |

`entry` is the ledger `seq` that wrote the row. `repo_id` is the
repository's position in the tree, which is what tells two repositories of
the same name apart; `scope` is `project` or `private`, the two halves of
one change. `remote` is the canonical `provider:owner/repository`, the form
`parse_repo_id` reads — never a URL, which can carry a user name.

**Publication is a row of its own, not a field inside the commit's row.**
An entry carries the digest of the rows it wrote, so a later `push` editing
a commit's row would break a digest recorded before that push existed. Rows
are therefore only ever appended, and every digest stays true for ever —
the same rule the ledger follows, for the same reason.

**The digest covers the rows one entry wrote, in a fixed order**: the
commits first, then the publications, each ordered by State name and then
by the order the file lists them. A `push` writes into the logs of the
States whose commits it publishes, which is why the order has to be stated
rather than assumed — an entry can write into more than one file.

Nothing here records a path or a user name. A commit made outside
`cgitsync` gets no row at all: the memory speaks for what it watched.

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

### The five answers `verify` owes

A verification pass ends in exactly one of these, never a blur of two:

| Answer | When | Exit |
|---|---|---|
| **verified** | A non-empty chain was read and every link checked out | `0` |
| **no history** | Nothing has been recorded here yet. A new workspace is not a broken one | `0` |
| **legacy** | History exists only in the single-file `.lgr` format, which carries no chain: readable, not verifiable | `1` |
| **corrupt** | A chain was read and it does not hold | `1` |
| **time-inconsistent** | The chain holds — every link checked out — and its own timestamps move backwards somewhere | `1` |

`Finding` enumerates what "does not hold" can mean: `BROKEN_LINK`,
`BAD_ENTRY_HASH`, `SEQ_GAP`, `SEQ_DUPLICATE` and `HEAD_STALE` for the chain
and its cache, plus `MISSING_STATE`, `ORPHAN_STATE` and
`STATE_DIGEST_MISMATCH`, reserved for the store-level pass that becomes
possible once a State is named by its content, and `TIME_REGRESSION`
below.

#### `time-inconsistent`, and why it is not `corrupt`

**The chain fixes the order of entries; each entry also says when it was
written. Put those together and each checks the other**: entry *N+1* was
written after entry *N*, which the hash chain proves, so `recorded_at`
moving backwards is a detected fault rather than a difference of opinion.
That is what turns a local clock reading from an unchecked claim into a
checked one, with no network, no signature and no third party.

It catches a clock corrected mid-session, a restored VM snapshot, a
dual-boot machine disagreeing about the hour — and a **backdated entry**,
which is the tampering case: a date cannot be forged downwards without
contradicting the chain around it.

**It is a verdict of its own, and never folded into `corrupt`.** The
history *did* hold; only the clock that stamped it did not, and the two
send a reader to look at completely different things. Calling an intact
chain corrupt is the specific false alarm this project has already paid
for once — see *What a State's name is computed from*, where a perfectly
good snapshot was reported as corrupt and the note that this "is the worst
possible answer, because it is not true and it invites deleting the one
thing that was fine". It still exits `1`: the history holds, but something
is wrong that a build gating on `verify` should not sail past.

**What it does not claim.** That the dates are *true*. A machine whose
clock was wrong from the start, consistently, produces a perfectly
monotonic chain of wrong timestamps. Absolute time needs a witness outside
the machine, which is the Omniscience layer's business, not this one's.

`integrity.resolve_state()` is the single authority on which findings mean
which verdict — structural findings beat `TIME_REGRESSION`, which beats
`ORPHAN_STATE` (reported, never fatal). Both the chain pass and the
store-level pass call it, so a finding cannot mean one thing to one of
them and something else to the other.

---

## The self-history record: schema and what has landed so far

**This is the AgentReport ticket's own record**, content-addressed the
same way an Environment record or an `AgentContractRecord` is —
`memory/self_history.py`, `SelfHistoryRecord.digest()` over sorted-key
compact JSON, sha256, no prefix. Written to
`.cgitsync/.self-history/<hash>.toml` (the pending half); `memory push`
folds it into `.cgitsync/.memory/.self-history/<hash>.toml` (the folded
half, a repository of its own once adopted — see *What has landed so far*
below) leaf-first, before folding and pushing `.memory` itself.

### Entry schema

| Field | Meaning | Source |
|---|---|---|
| `ticket` | The ticket served, by its short name — never a path, which the lifecycle renames | Declared |
| `goal` | The ticket's objective, at most 3 lines of plain English | Declared |
| `action` | The main action taken, at most 3 lines of plain English | Declared |
| `worker` | `{role, vendor, model}` — the agent that implemented the ticket. `role` is validated against `.localSpec/AGENT.md`'s six-role roster | Declared |
| `orchestrator` | Same three fields, for the independent agent that quoted the work and wrote the record | Declared |
| `conformity` | `{spec_respect, gating, quality}`, each `{score, basis, reasoning}` — `basis` is `"measured"` or `"asserted"`, never blended | Declared |
| `contract` | The current signed `AgentContractRecord`'s own hash, or `""` when nothing is signed | **Observed** — `agent_contract.read_current_contract()` |
| `checks.status_errors` | This workspace's own `errors=` count, when a tree is loaded | **Observed** — `ComplexGitSyncClient._collect_status()` |
| `checks.lint_passed` / `checks.tests_passed` | Whether `pixi run lint`/`pixi run test` passed | Declared — the tool cannot run Pixi itself; `subprocess` stays confined to `git_runner.py` |
| `state_before` / `state_after` | `state(<hash>)` ids | `state_before` Declared; `state_after` **Observed** when omitted (the ledger's own most recent entry) — both **verified** against the ledger regardless of who supplied them (see below) |
| `repos_written` | `[{repo, scope}, ...]` | **Observed** when `state_before`/`state_after` both resolve — `_repos_written_between` diffs the two States' own `commit_sha` per repo (WP4/D5); Declared otherwise (no `state_before` to diff against) |
| `pushed` / `pushed_reason` | Whether anything reached a remote, and on whose instruction | Declared |
| `recorded_at` | ISO timestamp, from the caller's own `ClockProtocol` — this module reads no clock | Declared, by the caller |

`checks` is present only when at least one of its three fields has a
value — the same "absent, not present-and-empty" discipline the ledger's
own optional fields use, so a record written before a field existed (or a
record whose caller genuinely could not observe it) hashes honestly rather
than carrying a fabricated default.

### What has landed so far (AgentReport WP1, WP2, WP2b, WP3, WP4, WP5, WP6 — done, ticket archived)

- `ComplexGitSyncClient.self_history_add()` and `cgitsync self-history add`
  — write one record to the pending half, filling `contract` and
  `checks.status_errors` in from what the tool can itself check.
- The record format above, with validation: `goal`/`action` at most 3
  lines, `ticket` non-empty, `worker`/`orchestrator` roles from the AGENT.md
  roster, `conformity` bases restricted to `measured`/`asserted`.
- **The nested repository, and its own lifecycle riding `.memory`'s.**
  `memory/repository.py`'s `config_memory_document()` writes the nested
  `.cgs` that makes `.self-history` a real, discoverable child of `.memory`
  (`relative_path = ".self-history"`, both entries falling back to the
  same `project.default_branch` so the two mounts can never disagree about
  which branch they are on). `ComplexGitSyncClient.self_history_adopt()`
  (`cgitsync self-history adopt`) is the **one place this fact is decided**
  — it writes `config-memory.cgs` the first time, for a brand-new project
  or as the explicit retrofit for a `.memory` adopted before self-history
  existed (this project's own, among others). Every other reader only
  repeats that decision back, never re-derives or probes for it: `memory_adopt()`
  follows it automatically (`_adopt_self_history_if_declared`, see below)
  when `.memory`'s own just-fetched content already has it — via
  `fallback_branch`, the same mechanism that lets `.memory`'s own adopt
  inherit shared history; `memory_push()` folds and pushes it leaf-first,
  before folding and pushing `.memory`; `memory_clone()` brings it back
  too, reading which repository to clone from `config-memory.cgs` itself
  (`_clone_self_history_if_declared`); `memory_reboot()` never touches it,
  by construction — it only ever opens `.memory`'s own mount (D7).
- `ComplexGitSyncClient.memory_self_history()` and `cgitsync memory
  self-history` — every record this workspace holds, folded and pending
  merged, for consultation.
- **"Empty but initiated" means a real commit, not an unborn branch.**
  `_finish_self_history_adopt` gives `.self-history` one contentless
  commit (`git commit --allow-empty`) the moment it is adopted, before
  configuring its remote or fetching. Without it, `.self-history` was a
  genuinely unborn branch — no commit for `HEAD` to resolve at all — which
  crashed three different call sites the same way, in three separate live
  incidents on this project's own tree, before `git_runner.py` itself was
  fixed: `current_branch()` (`git rev-parse --abbrev-ref HEAD`, used by
  `memory push`/`memory reboot`'s `_push_self_history` and by `pull`'s
  tree-wide checkout) now asks `git symbolic-ref --short -q HEAD` instead,
  which answers with the branch's real name for an unborn branch exactly
  as it does for one with commits — only a genuinely detached `HEAD`
  degrades to `None`. `head_commit_sha_or_none()` is `rev_parse_head`'s
  sibling for the one caller (`operations._refresh_repo_after_checkout`,
  run by `pull`'s tree-wide checkout for every discovered repository) that
  can legitimately meet a repository with no commit yet — `git_repo.py`'s
  `commit_sha: str | None` already modelled that state; nothing did until
  now. `rev_parse_head` itself keeps raising for every other caller, where
  an unresolved `HEAD` is a real bug (after a `commit`, after checking out
  a branch already known to have one), not a normal shape. Without the
  initial commit, `.self-history` would still crash nothing, but could
  never make a tree `READY`: `git_tree.py`'s `is_ready()` requires a real
  `commit_sha` for every repository it holds.
- **`state_before`/`state_after` verified against the ledger, not merely
  shape-checked (WP3).** `orchestre._resolve_ledger_state` asks the same
  three questions `verify`'s own `MISSING_STATE`/`STATE_DIGEST_MISMATCH`
  findings ask (`_verify_states_on_disk`): does some ledger entry actually
  name this state_id, is the State it names on disk, and does that file's
  content still hash to the name it is filed under. `self_history_add`
  raises rather than recording a citation that fails any of the three — a
  fabricated or stale reference is refused, not accepted as fact.
  `state_after` is additionally **observed**, not merely validated, when
  not given: the ledger's own most recent entry at the moment
  `self_history_add` runs.

**Why this is a ledger question, not a `.cgs`/registry one.** A `.gts` is
a static snapshot of an already-discovered tree — a READY tree does not
re-run discovery, and the fact that a `.gts` can be loaded at all is
downstream of it having been generated from a tree that went through
discovery once already. Two mistakes an earlier draft of this section made,
both from asking the wrong layer:

- Whether `memory_adopt` should also handle self-history was first designed
  as a check against `.memory`'s own `nested_config` field on the loaded
  registry. That fails silently for the ordinary case, because
  `registry.build_registry_from_gts_document` never sets `nested_config` at
  all (it is `.cgs`-only information — see `_apply_repo_identity` in
  `git_tree.py`) — not a bug to route around, just the wrong question:
  `.gts` does not need to re-answer "should I discover this," because a
  properly-discovered tree already has the answer baked into its own
  `repo_state` entries the moment such an entry exists. The actual
  question `_adopt_self_history_if_declared` asks is simpler and does not
  touch the registry at all: has *this project's `.memory`, as actually
  committed*, already decided to use self-history —
  `config-memory.cgs`'s presence in what `.memory`'s own adopt just
  fetched.
- A later revision replaced that check with a blind `remote_reachable`
  probe on every `.memory` adopt, treated as the opt-in itself. That is
  also the wrong mechanism: it asks a network question to answer a
  question about the tree's own declared shape, and a repository being
  reachable is not evidence that *this* tree decided to use it.
  `_self_history_identity_from_config` — reading `config-memory.cgs` back,
  the one artefact `self_history_adopt` actually committed — is the
  correct signal; reachability is only ever checked afterward, to decide
  whether the already-declared repository can actually be fetched right
  now.

Both mistakes shared a root cause: reaching for a runtime check
(re-discovery, a network probe) to answer a question the tree's own
already-verified state — what the ledger recorded, what `.memory` already
committed — could answer directly. `_resolve_ledger_state` (WP3, above) is
the same correction applied to a different question: whether a State
citation is real is a ledger question, answered the way `verify` already
answers it, never a matter of re-parsing or re-deriving something from a
transformed document.

**`repos_written` is now observed too, when it can be (WP4/D5).** The
session-wide write-outcome accumulator this client does not have
(`last_write_outcomes` is overwritten by every write call, not
accumulated) turned out to be the wrong tool for the job: `orchestre.
_repos_written_between` diffs two already-verified States' own per-repository
`commit_sha` instead — any repository whose commit changed between
`state_before` and `state_after` was written, and its scope reads from the
same `private`/`writable` flags `cgitsync status` labels a row with. No
accumulator, no new state to keep consistent — just two `.gts` documents
already on disk, read the same way `_resolve_ledger_state` already reads
one. It falls back to whatever the orchestrator declared only when there
is no `state_before` to diff against.

**`checks.lint_passed`/`checks.tests_passed` stay caller-supplied,
permanently, by design.** Making them genuinely observed would need
`cgitsync` itself to run Pixi, which the `subprocess` confinement rule
does not allow — not a gap this client will close later, a boundary it
does not cross.

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
- **A test that asserts on a date injects the date.** Every dated fact a
  command writes goes through `ClockProtocol`
  (`memory/ledger_entry.py`) — real by default (`orchestre.SystemClock`),
  fake by injection — so a test asserting on one supplies a fixed clock
  rather than reaching for `monkeypatch` on the real one. A test that
  patches only part of a scenario and lets the rest read the real
  calendar is green only until the two happen to agree, which is not
  really green at all — see
  `.agent/.local/.localSpec/DevTickets/archive/20260920_ClockSeam_DevPlanTicket.md`.

---

## Branches and ticket topics

`main` is where ComplexGitSync's work lands, with two exceptions.

| Workstream | Branch | Ticket filename prefix |
|---|---|---|
| Everything else | `main` | `main_` |
| Memory — a change that **migrates a stored memory format**: the state area's layout, the register/ledger schema, or the distant reference ledger | `memory-dev` | `memory-dev_` |
| Data — the `DataManager` layer, the DVC backend, `data_backend`/`data_paths`, and data materialisation and publication | `data-repo` | `data-repo_` |

**A change that migrates a stored memory format is developed on
`memory-dev`.** The memory work was seven dependent milestones — see the
MemoryArchitecture ticket in [DevTickets/openTickets/](DevTickets/openTickets/) — that between them renamed
the state area, rewrote the register, moved code into a new `memory/`
package and added a network protocol. Interleaving those with releases on
`main` would put a half-migrated memory format in front of users, and the
one thing this project cannot afford to corrupt by accident is the record
of what it synchronised. `memory-dev` merges into `main` when a milestone
is finished and `pixi run lint` and `pixi run test` both pass.

**The test is migration, not subject matter.** Touching `.cgitsync/` or
`memory/` does not by itself send a ticket to `memory-dev`: work that only
*adds* — a new content-addressed directory beside the State, a ledger field
that is absent on older entries and so leaves every chain already written
verifying byte for byte — puts no half-migrated format in front of anyone,
and lands on `main`. That is the rule the 2026-09-18 review applied when it
moved MemoryArchitecture and StateLocking onto `main`, and the 2026-09-19
one when it opened
[TreeEnvironment](DevTickets/archive/20260920_TreeEnvironment_DevPlanTicket.md)
there. This paragraph records the narrowing those reviews already made, so
the rule and the filing agree.

`memory-dev` and `data-repo` are this project's branches other than
`main`, so those three are the only ticket filename prefixes it has. An
open memory ticket is named
`.agent/.local/.localSpec/DevTickets/openTickets/memory-dev_<priority>-<rank>_<Name>_DevPlanTicket.md`
and carries `*Branch: memory-dev*` under its `*Created:*` line; every other
open ticket is `main_<priority>-<rank>_<Name>_DevPlanTicket.md` and carries
`*Branch: main*`. The prefix is written out in both cases — `main_` is not
implied by its absence. Both conventions are defined in
[.agent/.distant/ticket/TICKETLIFECYCLE.md](../../.distant/ticket/TICKETLIFECYCLE.md) §2.3 and
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

`DevSpecs.md`'s *Versioning* section leaves the choice between calendar
`YYYY.XX` and SemVer to each project, against a stability promise. This
project chooses **real SemVer** (`MAJOR.MINOR.PATCH`, with an optional
`-<stage>.<N>` pre-release suffix), authoritative in `pyproject.toml` —
because it publishes a package under exactly the promise SemVer exists to
state (see *What SemVer measures here*, below). **No workflow writes it.**
`.github/workflows/ci.yml` has never auto-incremented anything — it
installs, reconstitutes the tree, lints, and tests, and nothing more. A
version bump is a release decision, made by a reader, not a byproduct of a
push — the general rule `DevSpecs.md`'s *Versioning* section and
[AgentConduct.md](../../.distant/dev-sync/AgentConduct.md) §1.3 both state.

### What SemVer measures here

SemVer's positions are defined against a public API, and this project
already has one written down: README's *What is stable, and what is not*
table.

| Position | Increments when | From the CLI contract |
|---|---|---|
| **MAJOR** | The public interface breaks | A command or documented flag is removed or renamed; an exit code changes meaning; a `--json` field is repurposed or removed; a `.cgs`/`.gts` grammar change an older reader cannot load |
| **MINOR** | Capability is added, compatibly | A new command, a new flag, a new `--json` field, a new provider — everything the contract calls "additive only" |
| **PATCH** | Behaviour is fixed, nothing added | A bug fix with no interface change |

Two things this narrows a great deal: `src/ComplexGitSync/` is **not a
public interface** (the contract says so outright — an internal refactor
never forces a major bump and owes no deprecation), and `verify` is
**experimental**, so its output changing is not a break either, until it
stops being.

Pre-release identifiers (`3.1.0-alpha.1`, `3.1.0-beta.2`, `3.1.0-rc.1`,
then `3.1.0`) are SemVer's own answer for a release still in progress —
sorting correctly by specification, understood by every tool already, and
what `pixi run bump-version`'s `--pre`/`--release` flags produce.

### Two numbers, two cadences

| Number | Where | Moves when | Says |
|---|---|---|---|
| **SemVer** | `pyproject.toml`, `pixi.toml`, `src/ComplexGitSync/__init__.py`'s `__version__` | A release is made, deliberately | What the project promises |
| **Build counter** | `src/ComplexGitSync/__init__.py`'s `__build__` | Every change to `src/`, automatically as part of that change | Exactly which build produced a given ledger entry |

They have genuinely different cadences: a build counter that only moved on
releases could not identify the build behind a given ledger entry, and a
SemVer that moved on every merge would promise a release every time someone
fixed a typo. The build counter keeps the calendar scheme the whole package
used to follow (`YYYY.XX`, `XX` rolling 01→99 into `YYYY+1`) — it is
provenance, never identity, and (like every toolchain version) never enters
a State's hash. See *What a State's name is computed from*, below.

### Who bumps what

| Who | Does | With |
|---|---|---|
| **Worker** — the agent changing `src/` | Bumps `__build__`, as part of that change | `pixi run bump-build` (`scripts/bump_build.py`) — writes one file |
| **Orchestrator** — independent, quotes the work | Decides MAJOR/MINOR/PATCH, runs `bump-version`, tags, writes the release row | `pixi run bump-version {major,minor,patch} [--pre <stage>] [--release]` (`.agent/.local/release/scripts/bump_version.py` — private, see ProjectSpecSplit) |
| **CI** | Verifies: lint, tests, tree reconstitution | Never writes a version; needs no credentials to |

**CI cannot make the MAJOR/MINOR/PATCH judgement** — no diff distinguishes
a renamed flag from a new one — so it never runs `bump-version`, and it is
never asked to: `bump-version` needs a reader present, and CI is present at
the push, not at the change. This is a frontier, not a preference: CI's
`permissions: contents: read` never changes for this.

**The build counter is bumped by the worker, not derived, and not by
CI.** A number derived from git history (`rev-list --count`) would need no
credentials either, but it would also leave no act to check — an
orchestrator quoting a change can see whether `bump-build` ran (it shows in
the diff) and cannot see whether a number "should" have moved. A visible
act beats an invisible automatism when the whole point is accountable
agent work.

### `bump-version`

Reads the current version from `pyproject.toml`, and writes the version the
caller names — **five targets**:

| File | Field |
|---|---|
| `pyproject.toml` | `[project].version` — the authoritative one |
| `pixi.toml` | `[workspace].version` |
| `src/ComplexGitSync/__init__.py` | `__version__` |
| `README.md` | the version in the title heading (`v<semver>`) |
| `docs/Setup/Shortcuts.tex`, `docs/preamble.tex` | `\newcommand{\cgsversion}{...}` |

Exactly one of a bump level or a pre-release action is required —
`major`/`minor`/`patch` (bumps that position, drops any pre-release
suffix), `--pre <alpha\|beta\|rc>` (alone, advances an existing
pre-release; combined with a level, starts a new pre-release cycle at
`.1`), or `--release` (finalises a pre-release into its base version).
`--dry-run` previews the `old -> new` transition without writing anything.

**The bump is all five files or none of them.** The version is one fact; a
run that wrote three manifests and then failed on the docs would leave the
package claiming a release its documentation has never heard of, and would
do it quietly enough that the release still looked finished. So
`apply_version()` reads and rewrites every target in memory first, and only
a complete set of new texts reaches the disk. A missing file, an unwritable
one, or a version field the patterns cannot find stops the whole bump with
nothing changed.

The last two live in `docs/`, a separate repository (`DocComplexGitSync`).
When they are absent — a checkout of `ComplexGitSync` alone — the script
dogfoods `cgitsync initialise examples/complexgitsync4dev.cgs` to clone them
into place, *before* the first write rather than after three of them.
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

`bump_version.py` is orchestrator tooling and lives in
`.agent/.local/release/scripts/` — private, not in the public
`ComplexGitSync` repository — so a public-only checkout structurally cannot
cut a release (ProjectSpecSplit). It moved there from
`.agent/.local/.localSpec/scripts/`, where WP4 first placed it, once the
`release` skill was split out on its own — the `.localSpec` copy was dead
weight and has been removed. It is not in the shared `.agent/.distant/dev-sync`
either: every target path it touches (`pyproject.toml`,
`src/ComplexGitSync/__init__.py`, `docs/Setup/`, ...) is specific to this
project.

### `bump-build`

Writes exactly one file: `src/ComplexGitSync/__init__.py`'s `__build__`.
`scripts/bump_build.py`, same `--dry-run` convention as `bump-version`. This
is a worker step, run alongside a change to `src/` — see `CLAUDE.md`'s
before-committing checklist — not a release step.

### The release register

The release register the owner asked for is the Ledger: a release is one
ledger entry carrying an additive `release` field (`memory/ledger_entry.py`
— see *The hash-chained register*, below, for the field's schema), written
automatically by `ComplexGitSyncClient.freeze_release()` from the currently
installed `__version__`/`__build__` and the release tag name the caller
gave it. Tamper-evidence is then free: the field is inside the same hash
chain as every other field, so a release row cannot be edited afterwards
without breaking the chain from that point on. A version never enters a
State's hash (see *What a State's name is computed from*) — a release row
only ever cites a State by id, alongside it in the ledger, never inside it.

`freeze_release()` also reads `.agent/.distant/dev-sync/agent-contracts/current`
(`memory/agent_contract.py`) and, when it names a signed
`AgentContractRecord`, adds `artefact:agent_contract` to the row, naming
that record's terms version — absent, not fatal, when nothing has been
signed yet. See the **AgentContract** ticket (cited by name, not path, per
its own lifecycle rule) for the record's own content-addressing and why it
lives beside `AgentConduct.md` rather than under `.cgitsync/`.
