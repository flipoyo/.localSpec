# DevPlanTicket — Repository-Level Data Management (DVC first, Git LFS ready)

**Status:** proposed / supersedes the earlier “DVC-backed Data Repositories” ticket  
**Target:** `flipoyo/ComplexGitSync`  
**Implementation scope:** native CGS data orchestration + DVC backend  
**Architectural extension only:** Git LFS backend (separate ticket)

## 0. Decision and objective

ComplexGitSync (CGS) **MUST contain a native data-management class** responsible for synchronising an application's data across its GitTree. The CGS orchestrator dispatches each relevant CGS command **per Git repository** to its Git operation and the data-backend operations appropriate to that repository.

DVC is the first concrete backend. CGS owns the **application-level orchestration, dispatch, path ownership, preflight, ordering, reporting, and release readiness**. DVC owns DVC hashes, its cache, its metadata, remote transfers, and its own CLI semantics. A future Git LFS backend must fit the same *semantic* interface, but must **not** be implemented or enabled by this ticket.

**Replace the former Section 14 entirely:** DVC data authoring and removal **are part of CGS orchestration** when invoked through CGS `add`, `rm`, `commit`, etc. The user need not manually execute DVC for the supported lifecycle. This does **not** mean adding DVC's full CLI under `cgitsync`, nor implementing `dvc repro`, experiment tracking, remotes, or garbage collection.

The existing CGS `project` / `private` classification and its write permissions remain intact. `data` is an independent capability of a `GitRepo`, **not** a third, mutually exclusive repository kind and **not** a separate repository hierarchy.

## 1. Existing boundaries to preserve

- `.cgs` declares the GitTree; `.gts` freezes the state of that tree. Keep both backwards-compatible.
- `checkout` is offline today; preserve that guarantee. Remote data retrieval belongs to network-enabled commands, not implicit checkout.
- `private/distant` repositories remain read-only. `--private` and `--all` retain their current selection/permission semantics; a DVC command must not bypass them.
- `commit --no-stage` must not implicitly stage Git metadata, run `dvc add`, or run `dvc commit`.
- `--dry-run` makes **no** filesystem, Git, DVC-cache, remote, or registry modifications.
- Git-only projects must not require DVC or change behaviour.
- The existing CLI is authoritative: extend existing commands, do not invent `cgitsync data-*` verbs.

## 2. Configuration and repository contract

**Minimal `.cgs` extension** (the precise key must be implemented consistently in the existing parser, serializer, domain contract, and CLI authoring path):

```toml
project = { name = "HydrologicalTwin", default_branch = "main" }

repos = [
  { repository = "github:org/HydrologicalTwin", fallback_branch = "main" },
  { repository = "github:org/CaWaQS", relative_path = "models/CaWaQS" },
  { repository = "github:org/SeineForcing", relative_path = "data/forcing",
    data_backend = "dvc", data_paths = ["SAFRAN/", "climate/"] },
  { repository = "github:org/PrivateParameters", relative_path = "data/private",
    private = true, writable = true, data_backend = "dvc",
    data_paths = ["grids/"] },
]
```

`data_backend` is absent for plain Git repositories; `"dvc"` is the **only accepted backend in this ticket**. Reserve `"git-lfs"` as a future identifier in the type contract and documentation, **but reject it as not implemented** at parse/validation time in this release. Do not silently treat it as Git or DVC.

`data_paths` is an optional, repository-relative declaration of **which newly added, untracked paths CGS is authorised to enroll in the data backend**. It is needed because a DVC-enabled repository may also contain Git-owned source, scripts, small TOML/YAML parameters, and `.dvc` metadata. Existing DVC-tracked targets can be identified from DVC's own metadata even when `data_paths` is absent. Do not automatically `dvc add .` or track the entire repository. For an ambiguous new path with no backend ownership rule, fail with an actionable diagnostic instead of staging a potentially enormous raw dataset into Git.

Validate `data_paths`: nonempty relative paths, canonicalised within their owning repository, no `..` escape, no symlink escape, no overlap with a nested Git repository, no `.git`, `.dvc` internals, or CGS state directories. Clearly define ownership where one DVC-tracked directory contains another path. `data_paths` is a **routing rule**, not a dataset manifest; DVC metadata remains authoritative for tracked targets and hashes.

The runtime representation is conceptually:

```python
@dataclass(frozen=True)
class DataSpec:
    backend: str                    # only "dvc" implemented now
    paths: tuple[str, ...] = ()     # new-data ownership policy, not hashes

@dataclass
class GitRepo:
    # existing fields stay unchanged
    data: DataSpec | None = None
```

Keep on-disk naming compatible with existing `.cgs` conventions; the Python sketch is architectural, not an instruction to replace the current `GitRepo` dataclass.

`.gts` **MUST retain the backend identity (and any routing policy necessary for standalone restoration)** for every repository. A `.gts` can restore a workspace without relying on an external `.cgs`. Prefer existing supported extensibility/serialization mechanisms; define a backward-compatible schema evolution if necessary. Keep the existing Git commit identifiers authoritative; never introduce CGS-owned DVC content hashes or `state(hash)_i`.

## 3. Native CGS data architecture

```text
CGS CLI command
    |
    v
CGS GitTree orchestrator (scope, order, preflight, errors, release)
    |
    +-- GitRepo A [Git-only] ------> current Git path
    |
    +-- GitRepo B [data=dvc] -----> DataManager
    |                                  |
    |                                  +-- DvcBackend --> DVC CLI / cache / remote
    |                                  +-- Git publication via existing CGS Git layer
    |
    +-- GitRepo C [data=git-lfs] -> future GitLfsBackend (NOT in scope)
```

Implement `DataManager` as the CGS-owned **per-repository dispatch and coordination layer**. `DataBackend` is a backend-neutral protocol/ABC; `DvcBackend` implements it. Do not create a competing `DataRepo`, duplicate repository discovery, or add a second CLI dispatcher. Only the existing orchestrator selects repositories and decides when an operation is legal.

**Use semantic operations, not an assumed one-to-one mapping of CLI verbs.** DVC's `commit` updates its cache/metadata; Git LFS typically relies on Git filters and pre-push integration. Backends need different steps to implement the same CGS-level contract.

Illustrative interface (refine signatures to existing project conventions):

```python
class DataBackend(Protocol):
    def inspect(self, repo, *, offline: bool) -> DataStatus: ...
    def plan_add(self, repo, paths) -> DataPlan: ...
    def plan_remove(self, repo, paths) -> DataPlan: ...
    def prepare_staging(self, repo, plan) -> DataResult: ...
    def pre_git_commit(self, repo, *, no_stage: bool) -> DataResult: ...
    def pre_git_change(self, repo, *, destructive: bool) -> DataResult: ...
    def materialize(self, repo, *, allow_network: bool) -> DataResult: ...
    def publish(self, repo, *, revisions) -> DataResult: ...
    def verify_release(self, repo, *, revision) -> DataResult: ...

class DataManager:
    def backend_for(self, repo) -> DataBackend | None: ...
    def dispatch(self, command, repo, context) -> DataResult: ...
```

A `DataResult` must distinguish `READY`, `DIRTY`, `NOT_MATERIALIZED`, `MISSING_CACHE`, `REMOTE_UNAVAILABLE`, `UNSUPPORTED`, `FAILED`, and `UNKNOWN` without claiming that a merely clean Git tree is data-ready. Record backend, repository, operation, attempted step, safe-to-retry status, and redacted diagnostics. Do not serialize credentials or backend internals in CGS state.

All subprocess calls use argument arrays, explicit `cwd=repo.root`, bounded/cancellable execution as appropriate, controlled logging, consistent failure handling, and **no** shell interpolation. Keep command execution out of `.cgs` parsing/domain validation. If no DVC repositories are selected, do not probe, install, or require DVC. A missing DVC executable in a selected DVC repo gives a precise per-repository error; never install it silently.

## 4. Path ownership and staging policy

CGS `add [PATH ...]` and `rm <PATH ...>` MUST first resolve **the owning Git repository** using the existing GitTree path rules, then resolve **Git vs data-backend ownership within that repository**. Never dispatch across a nested repo boundary. A path owned by DVC must not also be staged as raw bytes in Git.

For `add`:

1. Explicit new path under `data_paths` -> `dvc add <target>` (track/update data); stage only corresponding `.dvc`/`dvc.yaml`/`dvc.lock`/`.gitignore` metadata that changed and belongs to the target.
2. Explicit already-DVC-tracked output -> update the owning DVC target using a validated target-aware DVC command (`dvc add` or, when appropriate, `dvc commit`); stage resulting DVC metadata in Git. A file inside a DVC-tracked directory is handled by that tracked target, not as a new standalone pointer without justification.
3. Git-owned source/small configuration -> existing `git add` path.
4. New ambiguous path -> refuse with a message explaining `data_paths`, rather than guessing.
5. No-argument `add` -> inspect known DVC-tracked outputs for changes, update their corresponding metadata, and stage eligible Git changes. Never auto-enroll every unknown file in DVC or Git.

If DVC pipeline outputs are detected, do **not** treat `dvc add` as universally valid: respect the target's DVC stage semantics and do not silently rerun `dvc repro`. Do not run a blanket `dvc commit` that blesses changed pipeline dependencies and potentially misrepresents reproducibility. Require targeted, explicitly supported handling or fail with a clear instruction. Preserve an explicit distinction between source-data tracking and computed outputs.

For `rm`, define **deleting data** separately from **stopping tracking**. For a standalone `.dvc` target, CGS `rm` can use the corresponding supported DVC removal workflow and stage resulting metadata, while deleting the requested workspace path under CGS's existing remove semantics. DVC `remove` without `--outs` only stops tracking and may leave the bytes in the workspace; do **not** mistake it for `cgitsync rm`. Never delete remote DVC objects or run `dvc gc`. For a path inside a tracked directory, update the owning DVC directory safely; do not remove the whole dataset pointer by accident. Pipeline-stage removal, shared outputs, ambiguous selectors and destructive removals require a safe refusal unless fully specified/tested. Respect `--dry-run` and existing writable/private guardrails.

## 5. CGS command-to-data dispatch matrix

| CGS orchestration command | DataManager/DVC responsibility | Ordering and safety |
|---|---|---|
| `validate` | Structural config/backend/path checks only | No Git, DVC process, or network required. |
| `discover`, `configure`, `create-cgs` | Preserve/author backend and path policy | Optional local DVC detection; do not introduce network discovery. |
| `clone`, `bootstrap`, `initialise` | Validate DVC repo after Git checkout; materialize selected data | Git clone/checkout -> `dvc pull` when online; fail if required data absent. Preflight DVC data before deleting/re-cloning an existing workspace. |
| `add [PATH ...]` | Route paths; `dvc add` or targeted data update; Git-stage generated metadata | No raw data in Git. No-arg add updates known tracked outputs only. |
| `rm <PATH ...>` | Backend-aware removal plus Git metadata staging | Distinguish remove bytes vs untrack; never delete remote/cache objects. |
| `commit` | Verify DVC metadata/cache and targeted prepared changes, then Git commit | If staging is enabled, reuse `add` preparation; `--no-stage` only commits pre-staged Git state after safe validation and may refuse stale data. |
| `status` | Local `dvc status`/cache/materialisation assessment | Keep offline; do not conflate data state with Git's `LOCAL`/`SYNC`. |
| `view-tree` | Annotate backend (e.g. `[DVC]`) | No traversal of individual large data files. |
| `pull` | Preflight local data changes; Git sync; `dvc pull` for final selected revision | Never materialize stale revision first. |
| `checkout` | Preflight; Git checkout; `dvc checkout` from local cache | **Offline only**; on missing cache, report data-not-ready and direct user to network-enabled `pull`/restore. |
| `pull-force`, `clean-init`, `initialise --force-reclone` | Preflight tracked and untracked data, data-only changes, cache and locally-only bytes | Never infer safety from clean Git alone; report exact data-loss scope. No hidden DVC `--force`. |
| `branch` | No new data objects; preserve backend contract | Existing Git branch semantics, no unnecessary DVC transfer. |
| `merge` | Preflight per-repo data state; after Git metadata merge, reconcile/materialize data | Keep existing Git conflict handling; DVC metadata conflicts must remain explicit. |
| `push` | Validate referenced objects cached; `dvc push` then Git push for each DVC repo | If data publication fails, do not publish that repo's Git refs. |
| `tag`, `freeze` | Verify publishability and data availability for refs being advertised | A tag/release must not advertise missing required data. |
| `freeze-release`, `freeze-release-force` | Run coordinated add/commit/sync/data publish/Git publish/freeze | Full preflight, ordered phases, no successful snapshot on partial failure. |
| `launch-release`, `.gts` restoration | Restore exact recorded Git revision and DVC data | Git checkout -> network-enabled `dvc pull` if required -> verify materialisation. |
| `verify`, `purge` | Preserve existing registry verification; data cleanup respects ownership | Do not conflate CGS register verification with a DVC object-integrity audit. |

The matrix is a **required behaviour specification**; implementation must reconcile the exact current call graph and flags rather than assuming any particular existing method names.

## 6. Publication and release invariants

A DVC-aware commit has two distinct records: DVC updates data cache/pointers; Git commits the DVC metadata. `dvc push` uploads objects referenced by DVC metadata; it does not publish the Git commit. Therefore the *publication dependency* is:

```text
prepare/update data + DVC metadata
    -> Git stage & commit metadata
    -> resolve any Git pull/merge and revalidate FINAL metadata
    -> dvc push objects referenced by FINAL Git state
    -> Git push final commit / tags
    -> freeze/emit successful .gts
```

Never assume that a previous `dvc push` remains sufficient after a Git merge changes DVC metadata. Validate the **final revision and reference set** before publishing. `dvc push` of the current workspace alone does not automatically guarantee every historical tag/branch is remotely available; release/tag publication must explicitly cover the relevant frozen reference(s), using targeted or `--all-tags`/equivalent semantics only when justified. Do not promise that a remote retention policy will preserve objects indefinitely: record that as a reproducibility prerequisite and verify what is verifiable.

For a multi-repo release, preflight **all affected repositories** before publishing any Git refs; finish all required DVC uploads before the first release Git-ref publication where feasible. Because independent Git and object-store remotes do not offer an atomic cross-repository transaction, **do not claim global atomicity**. On partial failure: mark the operation failed, do not publish a successful `.gts`, report exactly which repos/refs and data objects were published, and provide an idempotent retry/recovery procedure. Avoid a false all-or-nothing promise.

A successful `.gts` snapshot captures the Git revisions, repository topology, backend type, and routing configuration required to reconstruct the same workspace. It does **not** duplicate `.dvc` hashes, data bytes, storage credentials, or invent `state(hash)_i`.

## 7. Safety, local work, and offline operation

- **Git clean != DVC clean.** Check data-workspace changes and missing cache separately before checkout, destructive pull, re-clone, and freeze. Never overwrite uncommitted data in a normal command. A `--force` option must use existing CGS force semantics and explicitly disclose the additional data-loss scope; do not silently pass DVC `--force`.
- `dvc checkout` uses the local cache and may not restore objects missing there; `dvc pull` can retrieve and materialise remote objects. Keep `checkout` offline and surface `MISSING_CACHE` instead of doing surprise network I/O.
- `dvc status` (local mode) is not a remote availability guarantee. For publication, check/upload objects needed by the final reference. For `status`, indicate `UNKNOWN` rather than pretending remote availability has been proven.
- Never place remote credentials, tokens, signed URLs, DVC cache contents, or object hashes into `.cgs`, `.gts`, `.cgitsync` or logs. Use native backend credential configuration.
- Keep a repository's data directory and cache outside unsafe deletion scope unless explicit and safe. Do not let generated DVC ignored files bypass initialise's existing unpushed-work guard.
- No data operation on private/distant repos that writes Git or DVC metadata, cache, or remote; read-only materialisation is allowed where existing read semantics allow it.
- Large-data operations need visible progress, cancellation-safe failure reporting, and no silent background execution.

## 8. Future Git LFS contract (design only)

The design **MUST** accommodate `data_backend = "git-lfs"` as a *future* `DataBackend` implementation, but it MUST NOT be accepted as functioning or silently enabled in this PR.

Git LFS stores Git pointer files and commonly integrates data upload/download into ordinary Git filters and Git push/checkout behaviour. Therefore **do not** hardwire `dvc add`, `dvc commit`, `dvc push` or a separate remote into `DataManager` itself. The shared API expresses semantic phases (`prepare_staging`, `materialize`, `publish`, `inspect`) and each backend decides whether an explicit operation is required. A future `GitLfsBackend` may use existing Git operations/hooks plus `git lfs fetch`/`checkout`/`push` as appropriate; that is for the next ticket and requires its own tests. Backend configuration, authentication, transfer and content-hash formats remain separate. Prevent selecting multiple data backends for the same repository under this first schema unless a subsequent ticket defines deterministic path-level routing.

**Extensibility acceptance check:** implement a fake backend in tests that records semantic calls without importing DVC. The CGS orchestration tests must pass using this fake backend, proving that the orchestrator is not DVC-specific.

## 9. Phased implementation and required tests

Every phase updates relevant README/docs/examples/tests in the same PR or commit. No commit is considered ready without the project's `pixi` lint/test entry points passing or a documented reproducible environment blocker.

### P1 — Schema and persistence

Implement `data_backend`, optional `data_paths`, normalized DataSpec and `.cgs` round-trip; extend `.gts` snapshot/restore to preserve the data capability. Backward compatibility is mandatory.

Tests: Git-only config unchanged; project+DVC and private+DVC parse; invalid `git-lfs` reports *not implemented*; invalid/escaping/overlapping paths rejected; `.cgs` round-trip; **restore from `.gts` without `.cgs` still selects DVC**; structural validate works without DVC/network.

### P2 — DataManager + backend-neutral contract

Introduce CGS-owned `DataManager`, `DataBackend`, `DataStatus`, `DataPlan`, and a DVC backend. Use one subprocess boundary and one path ownership resolver; no extra CLI verbs.

Tests: fake backend dispatch; Git-only never loads DVC; DVC missing failure; cwd and argument safety; private access; failure propagates with correct repo/operation; dry-run no effects.

### P3 — Authoring and local data status

Implement backend-aware `add`, `rm`, `commit`, `status`, and `view-tree` with explicit target ownership and safe metadata staging.

Tests: new forcing NetCDF in configured data path -> DVC pointer, not Git blob; edited existing tracked data -> updated metadata; Git-owned YAML -> normal Git add; ambiguous untracked path -> refusal; no-arg add does not enroll unknown files; removal removes intended workspace bytes and metadata but not remote objects; `commit --no-stage` does not mutate DVC state; modified DVC data with clean Git detected; pipeline output not silently blessed.

### P4 — Clone, sync, checkout, restore

Integrate materialisation with `clone`/`bootstrap`/`initialise`, `pull`, offline `checkout`, `merge`, and `launch-release`. Harden preflight in `pull-force` and destructive reinitialisation.

Tests: Git checkout before DVC materialisation; offline checkout cache hit succeeds, cache miss reports `MISSING_CACHE` without remote call; network-enabled restore fetches missing objects; A->B->A release restores A's exact bytes; altered data blocks destructive operations; interrupted pull reports partial readiness; private/distant materialisation never pushes.

### P5 — Publication and release

Integrate `push`, `tag`, `freeze`, `freeze-release`, `freeze-release-force` with final-revision data publication and whole-tree preflight.

Tests: DVC upload before Git publication; upload failure blocks Git ref publication; Git merge introducing new DVC metadata requires fresh data upload; tagged prior revision covered; cross-repo partial failure is explicitly reported and `.gts` not recorded as successful; retry is safe; Git-only release regression; private permissions preserved.

### P6 — End-to-end scientific example and acceptance

Add one **real local-only DVC integration test** using temporary Git repositories and a temporary filesystem DVC remote; no cloud credentials or external network. Use a small stand-in dataset (not actual huge NetCDF) to test the same workflow:

```text
1. Create HydrologicalTwin code repo and SeineForcing DVC repo.
2. Declare both in .cgs; forcing has data_backend=dvc and data_paths.
3. cgitsync initialise/bootstrap -> dataset A materialised.
4. Modify the forcing dataset through CGS add -> commit -> push.
5. cgitsync freeze-release R1 -> .gts captures exact Git SHA + DVC backend.
6. Modify the forcing dataset to B; CGS add -> commit -> push.
7. From a fresh workspace, launch-release R1 using its .gts only.
8. Assert code SHA == R1 SHA, forcing SHA == R1 SHA, bytes == A.
9. Remove needed object from a test remote/cache and assert restore fails,
   leaving release state NOT READY instead of reporting success.
10. Assert no DVC object hashes or credentials exist in CGS snapshots.
```

Run existing full tests/lint with Pixi and document command/output. Add a concise HydrologicalTwin user guide for data authoring, publication, offline checkout, restoration, and diagnosing missing data.

## 10. Non-goals and prohibitions

Not in scope: implementing Git LFS; simultaneous DVC+LFS ownership in one repo; DVC pipelines/`repro` execution; experiments; building an object store; CGS-computed data hashes; object-level manifests; data transformation; configuring DVC remotes/credentials; DVC GC; migrating existing data; network actions during `.cgs` validation; silent auto-install; unexpected creation of new CLI verbs.

**Rejected designs:** separate `DataRepo` lifecycle; hard-coded DVC calls inside CLI/parser/GitTree domain model; adding a blanket `dvc add .` or blanket `dvc commit`; passing DVC `--force` automatically; storing per-object hashes in `.gts`/`.cgitsync`; classifying all files in a DVC Git repository as data; promising globally atomic multi-repo publication without a transaction protocol.

## 11. Definition of Done

1. One `cgitsync` lifecycle drives Git-only and DVC-backed repositories through a CGS-owned `DataManager`, without requiring users to call DVC for the supported `add`/`rm`/`commit`/sync/release operations.
2. Data paths are dispatched correctly; large datasets never accidentally become raw Git blobs; small Git-owned parameters remain reviewable text.
3. `.gts` alone is sufficient to recover repository backend identity and exact previously published data from a fresh workspace (assuming required remote objects are retained and accessible).
4. Offline checkout and existing private repository policies remain intact.
5. Failed or incomplete data publication cannot produce a successful CGS release; partial cross-repo effects are reported honestly.
6. Git-only projects retain current behaviour and do not require DVC.
7. Git LFS remains unimplemented, but the contract is validated with a fake alternative backend and requires no redesign of CGS orchestration.

**Design principle:** *CGS owns orchestration of code and data at GitRepo level. A data backend owns its own data format and storage protocol.*

## Reference documentation (verify against the version pinned by the project)

- CGS README and current CLI: https://github.com/flipoyo/ComplexGitSync
- DVC add: https://doc.dvc.org/command-reference/add
- DVC commit: https://doc.dvc.org/command-reference/commit
- DVC remove: https://doc.dvc.org/command-reference/remove
- DVC checkout: https://doc.dvc.org/command-reference/checkout
- DVC pull: https://doc.dvc.org/command-reference/pull
- DVC push: https://doc.dvc.org/command-reference/push
- DVC status: https://doc.dvc.org/command-reference/status
- Git LFS architecture: https://git-lfs.com/
