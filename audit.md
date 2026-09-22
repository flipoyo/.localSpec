# Architecture and Consistency Audit

*Created: 2026-05-14*

This file tracks audit findings for the `.cgs` format, CLI authoring,
provider identity, and runtime boundary: intentional legacy references that
are not bugs, the acceptance checks that back this project's format/provider
guarantees, and open decisions or risks as they arise. The static
architecture reference this file used to carry (the Ring model, module
responsibility table, format ownership, and provider contract) moved to
`AdditionalSpecs.md`'s "Architectural Overview" section — see
that file, or `docs/DevGuide/architecture.md`, for how the system is built.
Historical regrouping plans are kept under `.localSpec/DevTickets/archive/`, and are
explicitly marked as archives.

## Intentional legacy references

- `examples/normalized_template.cgs` is a developer-facing canonical expansion,
  paired with the minimal `examples/template.cgs`.
- Explicit/verbose `.cgs` data in tests verifies advanced overrides and backward
  compatibility; it is not the recommended authoring style.
- Files explicitly marked as historical under `.localSpec/DevTickets/`, and the archived
  `.localSpec/DevTickets/archive/20260519_CorPlan.md` diagram, may retain old terminology
  to document migrations.
- `.gts`, `.lgr`, synchronization, freeze, and kernel semantics remain outside
  this format/provider audit and were not redesigned.

## Acceptance checks

Repository tests cover repository-ID parsing, canonical normalization, invalid
provider and identifier rejection, Codeberg equivalence between file and CLI
authoring, SSH/HTTPS remote generation for all providers, explicit custom URLs,
offline `create-cgs`, minimal serialization, and semantic tree round trips.
The authoritative execution results are reported with the Phase 6 change set.

## Open decisions / risks

- `ledger_entry.py`/`integrity.py`/`ledger_store.py` implement the
  hash-chained register's mechanics, but `SyncLedger`'s actual write path
  (backing `cgitsync verify`) is not yet wired to them — tracked here until
  that wiring lands, rather than left implicit in the module table it used
  to live next to.
- **Tree-wide branch propagation defeats per-repository branch pinning.**
  `operations.restart_tree` (behind `pull`/`pull-force`) reads the root
  repository's current branch and propagates it to every repository in the
  tree before pulling. The AgenticMounts layout pins `.localSpec` and
  `.claude` to a branch named after the project (`default_branch` per
  repository entry, honoured correctly by `initialise`/`bootstrap`), so a
  `pull` on such a tree would move those two mounts off their pinned branch
  onto the root's. Not yet decided: whether `restart_tree` should respect a
  repository's declared `default_branch` instead of the global one, or
  whether the global-branch model is the intended contract and the pinning
  is what should give. Surfaced while implementing
  `.localSpec/DevTickets/archive/20260905_agenticMountStep2-DevPlanTicket.md`, and
  **confirmed by an incident on 2026-09-05**: a `cgitsync checkout` run to
  review a branch created that branch in all six mounts, four of them shared
  with other projects, and the following `pull` failed outright. Nothing was
  pushed and the repair was one `git branch -d` per mount. Now tracked as its
  own priority ticket, `.localSpec/DevTickets/archive/20260906_BranchPinning_DevPlanTicket.md`.
- **An attached tree root never records its resolved branch.** When
  `initialise` attaches the existing checkout as the root rather than cloning
  it, nothing sets `resolved_ref_name`, so any code falling back through
  `resolved_ref_name or target_ref_name` reaches the branch the `.cgs`
  *declares* rather than the one actually resolved. The two differ whenever a
  clone fell back — the runtime log records exactly that for `docs`:
  `target_ref_name: autoTest, resolved_ref_name: main`. This was defect B in
  `.localSpec/DevTickets/archive/20260906_DetachedHeadPreflight_DevPlanTicket.md`; the ticket fixed the
  symptom (the preflight no longer guesses a branch for a detached HEAD) and
  deferred this cause by decision D3. Not yet decided: whether attaching a
  root should record its checked-out branch, or whether the fallback chain
  should prefer `fallback_branch` over the declared name.
- **A private/local repository's branch is computed two different ways,
  and only the privacy-blind one runs before the first clone.**
  `resolve_declared_ref` (`registry.py`'s GT-LOAD, `discovery.py`'s
  GT-DISCOVER) has no `private`/`writable` parameter and cannot apply
  `private_local_branch`; `resolve_propagated_ref`
  (`git_tree_branch.py`, every branch move after the tree exists) does.
  The two agree only if a `.cgs` author hand-types
  `private_local_branch(project_name, project_branch)` into the entry's
  `default_branch` field — which goes stale silently (`examples/molonari.cgs`
  still carries `"lMOLO"`, `molonari-light.cgs`'s project name, instead of
  `"MOLONARI"`) and has to name a branch that exists on the remote before
  the very first `initialise`, when a private/local branch is meant to be
  created lazily. Reproduced against this tree's own remote: `cgitsync
  initialise examples/molonari-light.cgs` fails with `No cloneable branch
  found for ComplexGitSync: expected one of ['lMOLO', 'lMOLO']` — the
  duplicate is the declared/fallback pair collapsing onto one hand-typed
  string. Tracked as
  [PrivateLocalBranchAtClone](DevTickets/openTickets/main_1-7_PrivateLocalBranchAtClone_DevPlanTicket.md).
- No other open finding is outstanding as of this rewrite. This section is
  a live log, not a fixed list — add a bullet here as soon as a real
  decision or risk surfaces, and remove it once resolved.
