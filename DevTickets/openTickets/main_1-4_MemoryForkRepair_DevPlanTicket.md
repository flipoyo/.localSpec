# MemoryForkRepair — `main`'s memory verifies again, without a commit rewritten

*Created: 2026-10-02*

*Branch: main*

> **Ticket review — 2026-10-02.** Renumbered `main_1-3` → `main_1-4`: RuleConformity found rule breakages in 3.14.2 and takes `main_1-1`, per the owner's instruction.

> **From TmpBranchClosure** (WP1), the CorrTicket closing the `tmp`
> branches. It must land before any `.memory` branch is renamed.

## Abstract — read this first

**The one-line version.** `cgitsync verify` reports this project's memory
as `corrupt`, because entries 126–129 were recorded on the `tmpPyPi`
branch and never reached `main`. Bring them back by a merge, so the chain
holds again.

**What this document is.** The plan for one repair, and the rule it must
keep.

**Who it is for.** The worker and the orchestrator.

**What you need to do with it.** Diagnose (§1), repair (§2), check against
§3.

```mermaid
graph LR
    M["main memory<br/>seq ..125, 130.."] -->|"merge, adds a commit"| R["seq ..125, 126-129, 130..<br/>YOU ARE HERE"]
    T["ComplexGitSync_tmpPyPi<br/>seq 126-129"] --> R

    classDef here fill:#1565C0,color:#fff,stroke:#111,stroke-width:2px;
    class R here;
```

---

## 1. Diagnosis (2026-10-02)

`cgitsync verify`: `status=corrupt`, 31 findings. The first two: `seq=130
SEQ_GAP missing 4 seq(s) between 125 and 130`, and `seq=130 BROKEN_LINK`.
Every later finding is "chain already broken upstream". `.memory`'s
`ComplexGitSync_tmpPyPi` holds one commit `main` lacks: "129 state(s), 129
ledger entr(ies)", 2026-10-01. Confirm first that entries 126–129 are
exactly what that commit adds, and that 130's `prev` hash is 129's.

## 2. Repair

- Merge `.memory`'s `ComplexGitSync_tmpPyPi` into its `ComplexGitSync`,
  the shape `autofix`'s `DivergentUserRepair` already handles for a
  chain-shaped repository: both sides' new entries, verified before the
  merge commit is made. If the existing repair recognises the situation,
  use it rather than a hand merge.
- The same for `.self-history`'s `ComplexGitSync_tmpPyPi` and
  `ComplexGitSync_tmpAutoFix` records, and `.memory`'s
  `ComplexGitSync_tmpAutoFix` and `ComplexGitSync_tmp-main-1-2_DiscoverRoundTrip`
  commits, if they hold entries or records `main` lacks. An agent-work
  record must not be lost.
- **Rewrites nothing**: no rebase, no amend, no reset, no force-push
  (`AdditionalSpecs.md`, *The hard prohibitions*). If the chain cannot be
  made to verify by adding commits alone, stop and report to the owner.
- `.memory` is private. Pushing it is the owner's call.

## 3. Acceptance

- `cgitsync verify` passes on this tree.
- No commit in `.memory` or `.self-history` changed sha; the repair added
  merge commits only.
- `pixi run lint` and `pixi run test` pass, and `cgitsync status` shows
  `errors=0`. If code changed, `bump-build`, then `bump-version patch` at
  least.
