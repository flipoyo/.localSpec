# DevPlanTicket — Robustness

| | |
|---|---|
| Status | OPEN |
| Priority | P0 |
| Predecessor | `GtsHashRepoPrecision` — must be at its Definition of Done |
| Written against | `flipoyo/ComplexGitSync` @ `e042a92` (4.4.1); re-verify after the predecessor lands |
| Scope | Behaviour of tree-wide and memory commands under failure: fault harness, partial-failure reporting, retry convergence, crash windows, `memory reboot` interruption |
| State contract | Consumed, never modified. `integrity_schema = 1` and its golden vectors are untouched |
| Split out | Architecture CI gates, cross-platform user-lifecycle CI, module isolation, warning/backlog/docs hygiene → separate tickets (§8) |

---

## 0. Why

`GtsHashRepoPrecision` defines what a valid State is. This ticket checks that
a failure — a Git error, a refused push, a killed process — never makes the
result **silently false, irrecoverably ambiguous, or destructive of the only
copy of work**.

CGS cannot roll back a push a remote has accepted. The guarantee is therefore
not atomicity across remotes but:

| Moment | Guarantee |
|---|---|
| before mutation | everything detectable without mutating is checked for the whole tree |
| during mutation | the only copy of work is never destroyed |
| after partial mutation | the command fails, and says exactly what completed, what failed, and what was not attempted |
| on retry | it converges, is a no-op, or refuses explicitly |
| after a crash | a persistent Memory inconsistency is named by an existing `Finding`; live Git divergence, or an operation interrupted before anything was persisted, is diagnosed from the live tree (`status`, Git probes, the next command) and never manufactures an integrity finding |

---

## 1. Phase 0 — premise verification (mandatory, before D1)

Checked at `e042a92`. Re-check each against `HEAD` once the predecessor has
landed; amend the ticket if one no longer holds.

| # | Premise | Where |
|---|---|---|
| P1 | Git is reached only through an injected runner; `GitRunnerProtocol` is a `Protocol` and `GitRunner` its one concrete class | `git_runner.py:232`, `:494`; `client.git_runner` |
| P2 | **Defect.** `push_tree` stops at the first `GitSyncError` and lets it propagate: the `RepoOutcome`s of repositories already pushed are lost, and no State is written. The user sees one error, not *A done, B failed, C not attempted* | `operations/push.py:36-119`, `orchestre/tree_commands.py:1152-1165` |
| P3 | **Defect.** A retry of `tag` / `freeze-release` after a failure on repository N can never converge: preflight treats *any* existing tag as `BLOCKING_ERROR` ("tag already taken") — including the tags this same operation created on repositories 1…N-1 — so the whole retry is refused before any mutation | `operations/preflight.py:131`, `:172-189`; `operations/push.py:151-240` |
| P4 | `fetch_tree` already reports per-repository failure with `RepoOutcome(failed=True)` — the model the write sweeps should follow | `operations/fetch.py:54`, `operations/outcome.py` |
| P5 | Preflight decides every repository's branch before any push: a refusal leaves the whole tree unpushed | `operations/push.py:67-73` |
| P6 | A State is written atomically (temp file + `replace`, no `fsync`); `state_files()` globs `*.gts`, so a stray `.…gts.tmp` is invisible | `memory/states.py:194-223`, `memory/pending.py:90` |
| P7 | A ledger entry is written `tmp` + `fsync` + `os.link` (`O_EXCL` semantics), **then** `HEAD` is updated | `memory/ledger_store.py:312-345` |
| P8 | A failed ledger append is logged, never raised ("recording must never cost the command its work"); the next `verify` reports `ORPHAN_STATE` | `orchestre/memory_commands.py:1799-1850` |
| P9 | Every ledger entry is written with `outcome="ok"`: the ledger records observed States, never attempts | same, `:1840` |
| P10 | Memory is folded and pushed **before** the project push, and its own failure only warns — so memory can never claim the current push | `memory_commands.py:943` (`_fold_memory_before_push`) |
| P11 | `memory reboot` mutates in this order: `push_ref_as(archived)` → `delete_remote_branch(current)` → `rename_branch` → `create_orphan_branch` → clear → write State → fold → commit → push. A retry is **refused** as soon as the archived branch exists locally or remotely, with no resume path | `memory_commands.py:1264-1330` |
| P12 | Findings already cover the crash windows: `MISSING_STATE`, `ORPHAN_STATE`, `HEAD_STALE`, plus the predecessor's `REPO_HASH_MISMATCH` / `GITTREE_ROOT_MISMATCH` / `STATE_DIGEST_MISMATCH` | `memory/integrity.py:61-83` |
| P13 | No test kills a process mid-command | `grep -rn "os._exit\|SIGKILL" tests` → empty |
| P14 | Repository names are not unique within a tree; records that must identify one repository key on `repo_id` | `memory_commands.py:115`, `:154`; `git_tree.py:488-496` |
| P15 | `check-ceilings` / `check-oo` / `check-spectree` already run inside `pixi run test` | `tests/unit/test_module_ceilings.py`, `test_oo_conformance.py`, `test_spec_tree.py` |

**Phase 0 deliverable:** `RobustnessOperationMatrix.md` — for `push`, `tag`,
`freeze-release`, `pull --force`, `checkout`, `merge`, `branch close|delete`,
`memory push`, `memory reboot`: the ordered list of mutating calls (Git
runner method, State write, ledger write, fold), as read from the source. Each
row is a failpoint candidate for D1.

Each operation is also given exactly one class:

| Class | Meaning | Handled by |
|---|---|---|
| `PARTIAL_REPORT_REQUIRED` | mutates repository after repository; can stop half-way | D4 |
| `PREMUTATION_REFUSAL_SUFFICIENT` | decides everything in preflight; a later failure cannot leave some repositories done | D2 pins it |
| `SINGLE_MUTATION` | one mutating call; nothing partial to report | D2 pins it |
| `CRASH_ONLY` | its only partial outcome is a killed process | D6 / D7 |

The set of `PARTIAL_REPORT_REQUIRED` operations is fixed in the matrix before
D1 and is not widened afterwards without amending this ticket. Deviations from
P1–P15 go at the top of the matrix, or the single line `PREMISES VERIFIED`.

---

## 2. Decisions (settled)

| # | Question | Decision |
|---|---|---|
| Q1 | Distributed rollback across remotes? | **No.** Preflight, never-destroy, explicit partial report, convergent retry. |
| Q2 | Fault injection in `src/`? | **No.** Failpoints live entirely in `tests/support/`: the harness patches named targets (a `GitRunner` method, `MemoryStates.write_atomically`, `LedgerStore.write_head`, …). No `FaultInjector`, no env var, no CLI flag, no production cost. A test asserts every named target still exists, so a rename breaks loudly. |
| Q3 | How is a crash simulated? | **Two modes.** `raise` (error path: `GitSyncError` / `OSError` at call *N*) runs in-process. `kill` runs the command in a child Python process that calls `os._exit(137)` at call *N* — no `finally`, no context-manager exit — then the test reads the disk. A `raise` test never claims to cover a crash window. |
| Q4 | Power loss / `fsync` durability? | **Out of scope.** `kill` models process death; the OS page cache survives it. P6's missing `fsync` is noted, not fixed here. |
| Q5 | Partial failure: record a State? | **No.** On a failed sweep no State and no ledger entry are written (keeps P9: the ledger never records attempts). The tree Git now holds is real and is recorded by the next successful command. |
| Q6 | What counts as duplicated history on retry? | A second tag, release, project commit, or memory genesis for the same intent. A new ledger entry observing the same content-addressed State is **not** duplication — it is a new observation. |
| Q7 | Implicit force-push or deletion during recovery? | **Never.** Preserve or refuse. |

---

## 3. Failure-report contract

A failed tree-wide write raises one `TreePartialFailure(GitSyncError)`
carrying, in visit order and keyed by `repo_id` (P14 — a name is not an
identity):

```
completed      (repo_id, RepoOutcome)                 — Git accepted it
failed         (repo_id, RepoOutcome(failed=True))    — exactly one: where the sweep stopped
not_attempted  [repo_id, …]                           — never touched by this run
```

`RepoOutcome` itself is not widened; the identity travels beside it. The
human rendering shows `name` and `relative_path`. The CLI prints the three groups and exits `EXIT_REFUSED`. Every fault test
asserts the five answers: what was attempted, what failed, what completed,
what definitely did not happen, and the safe next command.

---

## 4. Steps

One step, one commit. `ADD`, `CHANGE`, `MOVE`, `DELETE` never mixed. Each
commit body carries its verification command and output.

**D1 — ADD the fault harness** (`tests/support/faults.py`, `tests/support/failpoints.py`).
- `FaultingGitRunner(inner, method, nth, mode)` wrapping the real runner (P1).
- `run_cgitsync_killed(argv, target, nth)`: launches `python -c` that patches *target* to `os._exit(137)` on call *nth*, then calls `ComplexGitSync.cli.main(argv)`.
- `failpoints.py`: the named table built from the Phase 0 matrix (`push.repo[n]`, `state.after_write`, `ledger.after_link_before_head`, `reboot.after_push_ref_as`, …) mapped to patch targets; `test_failpoints_targets_exist`.
- Deterministic only: no sleep, no randomness, no network.
Verify: `grep -rn "faults\|failpoint" src` → empty.

**D2 — ADD characterisation tests that pin what already holds.**
- P5: push preflight refusal on repository 3 of 3 → zero repositories pushed (bare remotes unchanged).
- P9: no ledger entry with `outcome != "ok"` after any failed command.
- P10, local vs remote memory:
  - memory push failing before the project push → project push still succeeds (warning only);
  - memory push succeeding before the project push → **remote** memory holds only evidence preceding this project push;
  - project push succeeding afterwards → its `PublicationRecord`s exist only in **pending local** memory until the next fold/push.
- P8: `LedgerStore.write_entry` raising → State present, command exit 0, next `verify` → `ORPHAN_STATE`.
- `test_no_command_deletes_unpushed_work` re-run under `raise` faults on `pull --force` and `checkout` preflight.

**D3 — ADD failing tests for P2 and P3** (marked `xfail(strict=True)`, removed in D4/D5).
- push fails on repository B of A, B, C → expects §3 report: A completed, B failed, C not attempted; A's bare remote advanced, C's unchanged; no new State.
- tag fails on B; fix the cause; retry → converges: A unchanged, B and C tagged, no error.

**D4 — CHANGE write sweeps to report partial failure (§3).**
Every operation classified `PARTIAL_REPORT_REQUIRED` in the Phase 0 matrix —
and only those — catches `GitSyncError` per repository, stops, and raises
`TreePartialFailure`. At `e042a92` that set is expected to include
`push_tree`, `tag_tree` and `freeze_release_tree`. `tree_commands.push/tag` and
the CLI render it; the auth hint (`AuthFailureHints`) is kept on the failed
repository's detail. Leaf-first order and stop-at-first-failure are unchanged.
Verify: D3's push test passes without `xfail`.

**D5 — CHANGE tag conflicts from *existence* to *meaning* (P3).**
The rule moves into preflight, so it is decided for the whole tree before any
mutation:

| Local tag | Preflight | Sweep |
|---|---|---|
| absent | — | create, push |
| exists, points at `HEAD` | `INFO` "already tagged" | skip creation (`acted=False`); push (an identical tag is a Git no-op) |
| exists, points elsewhere | `BLOCKING_ERROR` naming both commits | never reached |

`_collect_tag_conflict_diagnostics` changes accordingly; `tag_tree` and
`freeze_release_tree` skip creation for the "already tagged" repositories.
A tag that exists only on the remote, pointing elsewhere, is rejected by the
push and becomes the `failed` outcome — never forced. In `freeze_release_tree`
a commit is skipped when nothing is staged (already true, pinned by a test).
Verify: D3's tag test passes without `xfail`; a `freeze-release` killed after
the tag on repository 2 and retried produces exactly one release entry.

**D6 — ADD crash-window tests** (`kill` mode), one per window. Each states its
observable outcome explicitly: an existing `Finding` when Memory is
inconsistent; otherwise `verify` clean **plus** the expected live-tree
condition.

| Window | Expected after kill | Retry |
|---|---|---|
| repo mutation done, before State write | `verify` clean (Memory is consistent); live tree ahead of the last State, visible in `status` | records the new State |
| State renamed, before ledger write | `ORPHAN_STATE` | same State file name (no duplicate), one new entry, finding gone |
| ledger linked, before `HEAD` update | `HEAD_STALE` | `verify repair` recomputes `HEAD`; chain intact |
| during State temp write, before `replace` | `verify` clean; at most a `.…gts.tmp` (P6), invisible to `state_files()` | retry writes the State; the stray file is never read |
| after local fold, before memory push | local memory ahead of its remote; no remote success reported | `memory push` publishes once |

**D7 — CHANGE `memory reboot` to resume or diagnose an interruption (P11).**
Kill tests at each of the four Git mutations in P11 first; then make each
resulting shape recognisable at the start of the next `memory reboot`:

| Interrupted after | Remote | Local | Required behaviour |
|---|---|---|---|
| `push_ref_as` | current + archived | current | resume: delete remote current, continue |
| `delete_remote_branch` | archived only | current (upstream gone) | resume from rename |
| `rename_branch` | archived only | archived only | resume from orphan creation |
| orphan created, genesis not pushed | archived only | new orphan | resume: write genesis, push |

Anything not matching one of these shapes is refused with the observed
shape named. A finished reboot leaves exactly one genesis on origin; two
competing geneses are impossible by construction (each resume step is
idempotent on the named branch).

**D8 — ADD remote-race tests** with local bare repositories:
remote advances after preflight and before push → that repository is the
`failed` outcome (non-fast-forward), nothing forced; memory remote advances
between fold and memory push → memory push refuses, project push unaffected
(P10); a repository disappears after preflight → `failed`, the rest
`not_attempted`.

**D9 — Real-tree validation** (manual, disposable workspaces only):
`examples/molonari-light.cgs` and `examples/cawaqs.cgs` — bootstrap, add
local-only work in one child, confirm `pull --force` refuses or preserves it,
make one remote diverge, confirm no overwrite, synchronise normally, `verify`
clean, compare commits and State digests with a fresh bootstrap.

---

## 5. Regression families kept green

`test_state_identity`, `test_integrity`, `test_gts_document`,
`test_branch_ancestors`, `test_no_command_deletes_unpushed_work`,
`test_memory_reboot`, `test_push_folds_memory`, `test_golden_release_gaps`,
`test_golden_lifecycle_gaps`, `test_cli_contract`, `test_cli_grammar`,
and the predecessor's golden vectors (byte-identical).

---

## 6. Non-goals

A new State hash or schema; Merkle proofs; distributed transactions or
rollback; implicit force-push; power-loss durability (`fsync`); any public
fault-injection surface; new commands.

---

## 7. Definition of Done

1. Every failpoint in `failpoints.py` targets an existing callable; none lives in `src/`.
2. A failed `PARTIAL_REPORT_REQUIRED` operation never reports success and always yields §3's three groups, keyed by `repo_id`.
3. A retried `push`, `tag` or `freeze-release` after a fixed failure converges with no second tag, release or commit.
4. Every D6 crash window has an explicitly specified observable outcome — an existing `Finding` when Memory is inconsistent, otherwise clean `verify` plus the expected live-tree/`status` condition — proven in `kill` mode.
5. An interrupted `memory reboot` is resumed or refused with its shape named; never two geneses.
6. No remote race leads to a forced or silent overwrite.
7. D3's `xfail` markers are gone; the full suite and the predecessor's golden vectors pass unchanged.
8. MOLONARI-light and CaWaQS pass D9.

---

## 8. Split into other tickets

| Ticket | Content | Note |
|---|---|---|
| `PlatformCI` | macOS ARM + Windows user-lifecycle smoke (bootstrap a public fixture, `status`, `verify`) | extends the predecessor's golden-vector matrix |
| `ArchGates` | only if P15's pytest wrappers turn out weaker than the scripts (e.g. `--check-digest`) | otherwise nothing to do |
| `ModuleIsolation` | `cli/expert.py` (2 385 LOC), `orchestre/memory_commands.py` (1 931 LOC) | after this ticket, behaviour-neutral, baselines only go down |
| `Hygiene` | warnings classification, backlog triage (petgraph, old memory POCs), user docs | not P0 |