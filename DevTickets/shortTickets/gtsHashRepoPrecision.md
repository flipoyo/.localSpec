| Scope | `.gts` State identity: repository leaf hash → GitTree Merkle root → State hash |
| Migration policy | Pre-release breaking change. No compatibility path. `memory reboot` opens the new genesis. |

---

## 0. Why

`GtsDocument.compute_snapshot_hash()` hashes one flat canonical JSON payload
(`gts_document.py:383`, canonicalisation 3). It answers *"is this the same
State?"* and nothing else: when it says no, `memory_facts.py:107-118` reports
a single `STATE_DIGEST_MISMATCH` for the whole snapshot. Which repository
diverged is not something the hash structure can say.

CGS has no released State contract. This is the last moment the State name
can change shape without a migration story. The ticket therefore replaces the
flat hash with a three-level one and **deletes** canonicalisations 1, 2 and 3
rather than carrying them.

```
commit_sha (Git OID)  ─┐
repo_state[i] fields  ─┴─► H_REPO_i ─► Merkle ─► H_GITTREE ─┐
project, tree_state, freeze_manifest ──────────────────────┴─► H_STATE = state_id ─► ledger
```

What a State attests to does **not** change: the leaf payload is exactly
today's per-repository canonical dict. Only the structure of the hash changes.

---

## 1. Phase 0 — premise verification (mandatory, before any commit)

Each premise below was checked at `e042a92`. Re-check every one against `HEAD`
before D1; stop and amend the ticket if any no longer holds.

| # | Premise | Check |
|---|---|---|
| P1 | One hash builder: `GtsDocument._build_canonical_payload` | `grep -rn "_build_canonical_payload\|compute_snapshot_hash" src` |
| P2 | Current canonicalisation is 3; legacy 1 and 2 still live | `grep -n "HASH_CANONICALISATION" src/ComplexGitSync/gts_document.py` |
| P3 | Only callers of the `canonicalisation=` override are tests | `grep -rn "canonicalisation=" src tests` → `test_state_identity.py:157`, `test_gts_document.py:142-143` |
| P4 | `hash_canonicalisation` leaks into CLI output (`memory show`) | `grep -rn "hash_canonicalisation" src` → `cli/expert.py:1540`, `orchestre/memory_commands.py:1611` |
| P5 | READY repositories already require `commit_sha` | `gts_document.py:242-244` |
| P6 | `state_id` is `state(<snapshot_hash>)` and is what the ledger chains | `memory/states.py:83-86`, `memory_commands.py:1840` |
| P7 | Digest verification lives in `memory_facts.py` and collapses to `STATE_DIGEST_MISMATCH` | `grep -n "STATE_DIGEST_MISMATCH" src/ComplexGitSync/orchestre/memory_facts.py` |
| P8 | **Defect:** `relative_path` is written with `str(Path)`, not `.as_posix()` | `git_tree.py:1312`, `registry.py:474` — on `win-64` (declared in `pixi.toml`) this yields `lib\io` and a different hash |
| P9 | `gts_document.py` is 509 LOC, above `MODULE_LOC_HARD_CEILING = 500` | `pixi run check-ceilings` — the new code must not land in this file |
| P10 | CI runs on `ubuntu-latest` only | `.github/workflows/ci.yml` |
| P11 | `memory reboot` writes one fresh State with the running build | `memory_commands.py:1234` docstring, step 4 |
| P12 | No `.gts` fixture or literal 64-hex digest is checked into `tests/` | `find tests -name "*.gts"`; `grep -rlE "[0-9a-f]{64}" tests` |

P12 means "regenerate fixtures" is close to a no-op: the fixtures are built at
test time. The golden vectors added in D3 are the first pinned digests.

---

## 2. Decisions (settled)

| # | Question | Decision |
|---|---|---|
| Q1 | Record `gittree_root` in each `LedgerEntry`? | **No.** `state_id = H_STATE` already commits cryptographically to `H_GITTREE`, and the `.gts` the entry names carries it. A second copy would widen the persistence contract (`AdditionalSpecs.md` *The hash-chained ledger*, `LedgerEntryLike`) without adding any detection power. |
| Q2 | Ship Merkle inclusion proofs (`proof`/`verify_proof`) now? | **Deferred.** No caller exists, and feature freeze is in effect. The tree construction in §3.3 is chosen so proofs can be added later without changing `H_GITTREE` or any other digest. |
| Q3 | Cross-platform CI targets | **Linux + macOS + Windows**, for the golden-vector job only (D7). `win-64` is a declared platform and P8 is a Windows-only defect. |

Versioning is out of scope for this ticket.

---

## 3. Specification (frozen as `integrity_schema = 1`)

### 3.1 Encoding

All three hashes use the same canonical JSON discipline as today
(`sort_keys=True, separators=(",", ":"), ensure_ascii=False`, UTF-8), prefixed
by a domain tag and a NUL byte. Node hashes concatenate **raw 32-byte**
digests, never hex.

```
H_REPO    = SHA256( b"CGS:REPO:v1\x00"  || canonical_json(repo_leaf) )
H_NODE    = SHA256( b"CGS:NODE:v1\x00"  || raw(H_LEFT) || raw(H_RIGHT) )
H_STATE   = SHA256( b"CGS:STATE:v1\x00" || canonical_json(state_payload) )
```

`state_payload` carries `gittree_root` as a hex string inside the JSON, not as
a byte concatenation, so there is no field-boundary ambiguity.

### 3.2 Leaf payload (`repo_leaf`)

Exactly the per-repository dict of canonicalisation 3 (`gts_document.py:412-457`):

`name, node_type, relative_path, repo_lifecycle_state, sync_state,
current_ref, target_ref, resolved_ref, commit_sha, project_owner_name,
project_name, repo_name, gitprovider, group_name, gitprovider_url,
fallback_branch, fallback_applied, fallback_reason, discovery_state,
worktree_state, is_reachable`

Excluded, unchanged from today and for the same documented reasons:
`absolute_path, parent_absolute_path, source_cgs_path, access_protocol,
private, writable`, and the running `CGS_VERSION`.

`relative_path` MUST be a POSIX path (`/` separators), `.` for the root
repository. `commit_sha` keeps its wire name; it holds the Git object ID.

### 3.3 Tree

- **Ordering key:** `relative_path`, compared as UTF-8 bytes. `relative_path`
  MUST be unique within a State; a duplicate is a validation error, never a
  tie broken by `name`.
- **N = 0** is a validation error (a tree always contains its root repository).
- **N = 1:** `H_GITTREE = H_REPO_0`.
- **N > 1:** RFC 6962 §2.1 split — `k` = largest power of two `< N`;
  `H = H_NODE(MTH(leaves[0:k]), MTH(leaves[k:N]))`. No leaf is ever
  duplicated, which closes the duplicate-last-leaf ambiguity of
  pairwise-promote schemes and keeps inclusion proofs well-defined if Q2 is
  revisited.

### 3.4 State payload

```json
{
  "project":        { "name": ... },
  "tree_state":     { "lifecycle_state", "is_ready", "registry_complete" },
  "gittree_root":   "<hex H_GITTREE>",
  "freeze_manifest": { ...same eight fields as today... }
}
```

`repo_state[]` no longer appears in the State payload; it contributes only
through `gittree_root`.

### 3.5 `.gts` layout

```toml
[document]
hash_algorithm   = "sha256"
integrity_schema = 1          # replaces hash_canonicalisation
snapshot_hash    = "<H_STATE>"

[tree_integrity]
merkle_root = "<H_GITTREE>"

[[repo_state]]
relative_path = "lib/solver"
commit_sha    = "..."
repo_hash     = "<H_REPO>"
# ...all other fields unchanged
```

A **new field name** is deliberate. Under today's rules a document with no
`hash_canonicalisation` is read as canonicalisation 1; resetting that same
field to 1 would collide with that meaning. A document without
`integrity_schema` is refused with `UnsupportedSnapshotFormatError`
("written before integrity schema 1 — run `cgitsync memory reboot`"), never
silently measured.

### 3.6 Verification order and integrity reference

Three integrity levels, each a primitive in its own right:

```
repo_hash     = integrity identity of one GitTree member
merkle_root   = integrity identity of the GitTree
snapshot_hash = integrity identity of the complete State
```

Verification runs bottom-up, all pure, and reports every finding rather than
stopping at the first:

1. each `repo_state[i]` → recompute `H_REPO_i`, compare with `repo_hash` → `REPO_HASH_MISMATCH(relative_path)`
2. recompute `H_GITTREE`, compare with `[tree_integrity].merkle_root` → `GITTREE_ROOT_MISMATCH`
3. recompute `H_STATE`, compare with `snapshot_hash` and with the hash in the State's name → `STATE_DIGEST_MISMATCH`

Stored `repo_hash` and `merkle_root` values are **intermediate integrity
checkpoints**. Their authoritative validity derives from recomputation, and
ultimately from `H_STATE` as referenced by the ledger: an edit that also
rewrites the stored checkpoints still fails at step 3.

The authoritative internal consistency reference is `state_id` recorded in
the hash-chained ledger. The ledger provides tamper-evidence within the CGS
integrity model. This ticket does **not** establish an external trust anchor,
nor resistance to malicious tampering: anyone with full control of the
memory could recompute a consistent chain from a new genesis.

Checking `commit_sha` against the live working tree (the "Git OID" level) is
I/O and stays in Ring 1+ (`git_probes.py`), outside the pure integrity module.

---

## 4. Steps

One step, one commit. `DELETE`, `MOVE`, `ADD` and `CHANGE` are never mixed.
Each commit body carries the verification command shown and its output.

**D1 — DELETE canonicalisations 1 and 2.**
Remove `LEGACY_HASH_CANONICALISATION`, the `version == LEGACY…` and
`version < 3` branches, the absolute-path sort key, and the
`canonicalisation=` override on `compute_snapshot_hash`. Delete the tests
that exercise them (`test_state_identity.py:157`, `test_gts_document.py:142`).
Tag `pre-GtsHashRepoPrecision` first.
Verify: `grep -rn "LEGACY_HASH_CANONICALISATION\|canonicalisation=" src tests` → empty.

**D2 — CHANGE `relative_path` to POSIX at write time.**
`git_tree.py:1312` and `registry.py:474`: `str(...)` → `.as_posix()`.
Add a unit test building the entry from a `PureWindowsPath`.
Verify: `grep -n '"relative_path": str(' src -r` → empty.

**D3 — ADD `src/ComplexGitSync/gts_integrity.py` (Ring 0).**
Pure functions only: `repo_leaf_hash`, `node_hash`, `merkle_root`,
`state_hash`, plus a frozen `INTEGRITY_SCHEMA = 1` and the three domain tags.
No import of `GtsDocument`; input is plain dicts. Within ceilings
(≤ 500 LOC, ≤ 7 public symbols, ≤ 6 internal imports), covered by
`check_module_ceilings.py`'s Ring-0 purity check.
Add `tests/unit/test_gts_integrity.py` with **golden vectors**: fixed leaf
dicts → fixed hex digests for N = 1, 2, 3, 4, 5 and 7. These literals are the
cross-platform contract.
Verify: `pixi run check-ceilings && pytest tests/unit/test_gts_integrity.py`.

**D4 — CHANGE `GtsDocument` to the new schema.**
`_build_canonical_payload` delegates to `gts_integrity`; `ensure_snapshot_hash`
stamps `repo_hash` on each `repo_state`, `[tree_integrity].merkle_root`, and
`integrity_schema = 1`; `hash_canonicalisation` and
`CURRENT_HASH_CANONICALISATION` are removed; `validate()` rejects duplicate
`relative_path`, N = 0, and a missing/unknown `integrity_schema`.
`gts_document.py` must end **below** its current 509 LOC.
Update `memory show` (`cli/expert.py:1540`, `memory_commands.py:1611`) to print
`integrity_schema` and `gittree_root`; update `test_cli_contract.py` accordingly.
Verify: `grep -rn "hash_canonicalisation" src tests` → empty;
`pixi run check-ceilings`.

**D5 — CHANGE verification to localise.**
Add `REPO_HASH_MISMATCH` and `GITTREE_ROOT_MISMATCH` to `memory/integrity.Finding`.
`memory_facts.py` stops funnelling every failure into `STATE_DIGEST_MISMATCH`:
it runs §3.6's three levels and reports each finding with the repository's
`relative_path`. An unreadable/invalid document stays `STATE_DIGEST_MISMATCH`
("could not be read"); an unsupported schema gets its own message.
Integration test: corrupt one `repo_state` field in a three-repo State →
exactly one `REPO_HASH_MISMATCH` naming that path, plus root and State
mismatches; the other two repositories report nothing.

**D6 — ADD the remaining invariant tests** (unit unless noted):
- same leaves in any input order → same `H_GITTREE`
- `ssh` vs `https`, two different `absolute_path`s → same `H_REPO` and `H_STATE`
- same branch, different `commit_sha` → different `H_REPO`, root, State
- project-level change only (`tree_state`, `freeze_manifest`) → `H_STATE` changes, `H_GITTREE` does not
- `PureWindowsPath`-built tree → same digests as POSIX (closes P8)
- integration (`test_state_identity.py`): the same tree bootstrapped into two directories → identical `.gts` digests at all three levels

**D7 — CHANGE CI.** Add a `golden-vectors` job, matrix
`[ubuntu-latest, macos-latest, windows-latest]`, running only
`pytest tests/unit/test_gts_integrity.py tests/unit/test_gts_document.py`
(no private-repo dogfood step). The existing `test` job is unchanged.

Not in this ticket (Q1, Q2): no ledger field, no `proof`/`verify_proof` API.

---

## 5. Genesis (operational, once D1–D7 are merged)

1. On the developer tree (`pixi run cgitsync bootstrap examples/complexgitsync4dev.cgs`):
   `cgitsync memory push`, then `cgitsync memory reboot` **with the new build**.
   Step 4 of the reboot writes the first schema-1 State — that is the genesis.
2. `cgitsync verify` → `VERIFIED`, zero findings.
3. Accepted consequence: the archived branch `<branch>.archived-<YYYYMMDD>`
   stays on origin but its States are refused by this build
   (`UnsupportedSnapshotFormatError`). It is history, not something this build
   verifies.

---

## 6. Real-tree validation

`examples/cawaqs.cgs` (CaWaQS and its C libraries):

- bootstrap on Linux and on macOS into different directories, one with `--force-protocol https`, one with SSH;
- `cgitsync memory show` on each: every `repo_hash`, `merkle_root` and `snapshot_hash` identical;
- hand-edit one `repo_state` field in a copy of the `.gts`; `cgitsync verify` names exactly that repository.

---

## 7. Non-goals

Replacing Git object integrity; signing commits or tags; making refs
immutable; changing `private`/`writable` semantics or adding them to the
hash; fault injection (4.5.0 Robustness); any compatibility reader for
pre-schema-1 snapshots.

---

## 8. Definition of Done

1. Canonicalisations 1–3 and `hash_canonicalisation` are gone (`grep` empty).
2. Every `.gts` written carries `integrity_schema = 1`, a `repo_hash` per repository, and `[tree_integrity].merkle_root`.
3. Golden vectors pass on Linux, macOS and Windows in CI.
4. `relative_path` is POSIX on every platform.
5. `verify` reports a single corrupted repository by its `relative_path`, bottom-up.
6. `gts_document.py` is below 509 LOC; `gts_integrity.py` passes every ceiling and the Ring-0 purity check.
7. The developer memory has been rebooted under schema 1 and verifies clean.
8. CaWaQS reproduces identical digests at all three levels on two machines.
9. No ledger field and no proof API were added (Q1, Q2).

After the first release: **a released integrity schema is immutable.** Any
change from then on is `integrity_schema = 2` with schema 1 still verifiable.