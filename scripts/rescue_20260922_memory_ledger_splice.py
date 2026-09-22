"""RESCUE SCRIPT — memory-dev_1-1_DivergedPrivateRepo, WP1.

Not general tooling. This is the one-off repair for one incident: two
sessions ("cgsN", local, and "cgsDbg", origin) both folded pending memory
into `.cgitsync/.memory` after the same ancestor commit, each computing
the same next ledger `seq` (16, then 17 for the "cgsN" side) and writing
different content there. A plain `git merge` treats that as an add/add
conflict on `lgr/000016.toml`/`000017.toml` and stops — see
`memory-dev_1-1_DivergedPrivateRepo_DevPlanTicket.md` §2 for why nothing
this codebase has (`merge_tree`, `pull-force`, or hand-picking a side)
resolves it correctly: `memory/ledger_entry.py`'s chain has a `seq`/`prev`
invariant a text merge does not know about, and picking one side silently
discards the other's ledger entries.

**What "correct" means here.** Every entry keeps exactly the fields it
was originally written with (`command`, `argv`, `state_id`, `outcome`,
`recorded_at`, ...) — only `seq`, `prev` and `entry_hash` are recomputed,
using `ledger_entry.compute_entry_hash`, the same function the running
system uses to write a real entry. The six colliding/orphaned entries
(local's old seq 16-19, origin's old seq 16-17) are re-sequenced in
`recorded_at` order, not "one side then the other" — the two sessions
interleave in real time (`cgsN`'s first entry, 2026-09-21T23:23:57Z,
predates both of `cgsDbg`'s), and only a chronological splice keeps
`memory/integrity.py`'s `verify_chain` monotonic-time check clean instead
of reporting `TIME_REGRESSION` (not corruption, but not clean either) on
an outcome this script did not have to produce.

**Preconditions** (checked at the top of `main`): run from inside
`.cgitsync/.memory`, mid-merge, with `lgr/000016.toml`/`000017.toml` and
`lgr/HEAD` still conflicted (git status shows `AA`/`UU`) exactly as `git
merge origin/ComplexGitSync --no-commit` leaves them — this script reads
both sides' original entries straight from git history by commit hash
below, so it does not depend on which side (if any) is currently staged
for those three files, but it does expect `lgr/000018.toml`/`000019.toml`
(local-only, unflagged by git because origin never had them, but stale
once the collision above is resolved) to still be sitting at the wrong
seq numbers, and removes them.

**What it leaves for the caller**: entries written and `HEAD` repaired,
but nothing staged or committed — inspect (`memory verify`, or run
`verify_chain` again by hand) before `git add`/`git commit`.

Run once:
    pixi run --manifest-path <repo-root>/pixi.toml python \\
        .agent/.local/.localSpec/scripts/rescue_20260922_memory_ledger_splice.py

A general version of this operation, for any future divergence and not
just this one incident's commit hashes, is this ticket's own WP2.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

from ComplexGitSync.memory import ledger_store
from ComplexGitSync.memory.ledger_entry import LedgerEntry, compute_entry_hash

# This incident's own commits — not parameters, on purpose (see the module
# docstring: this is not general tooling).
_LOCAL_TIP = "02c9375"  # cgsN's pre-merge HEAD of .memory; holds old seq 16-19
_ORIGIN_TIP = "8846dd9"  # cgsDbg's HEAD; holds old seq 16-17
_ANCESTOR_HEAD_HASH = (
    "sha256:7170f935c6966da59d56a156dece4bc5385a3fd025519e43c0d7853c2f34767e"
)  # seq 15's entry_hash — the last entry both sides agree on


def _read_original(commit: str, seq: int, *, cwd: Path) -> dict:
    """The exact TOML `[entry]` table `commit` wrote at `seq`, read straight
    from git history rather than transcribed by hand."""
    raw = subprocess.run(
        ["git", "show", f"{commit}:lgr/{seq:06d}.toml"],
        cwd=cwd,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return tomllib.loads(raw)["entry"]


def main() -> None:
    lgr_dir = Path.cwd() / "lgr"
    if not lgr_dir.is_dir():
        raise SystemExit("run this from inside .cgitsync/.memory")

    originals = [
        _read_original(_LOCAL_TIP, seq, cwd=Path.cwd()) for seq in (16, 17, 18, 19)
    ] + [_read_original(_ORIGIN_TIP, seq, cwd=Path.cwd()) for seq in (16, 17)]
    originals.sort(key=lambda e: e["recorded_at"])

    print("Chronological order this script will re-chain into seq 16..21:")
    for e in originals:
        print(f"  {e['recorded_at']}  seq(was)={e['seq']:<3} command={e['command']}")

    # The two stale local-only files: their content is one of the six
    # entries above, about to be rewritten at a new seq — remove them so
    # write_entry's O_EXCL guard does not refuse to overwrite a name that
    # is about to be legitimately reused.
    for stale in (18, 19):
        path = ledger_store.entry_path(lgr_dir, stale)
        if path.exists():
            path.unlink()
    # 16/17 may currently hold either side's conflict resolution (or be
    # mid-conflict markers) — remove unconditionally; both are about to be
    # rewritten too.
    for seq in (16, 17):
        path = ledger_store.entry_path(lgr_dir, seq)
        if path.exists():
            path.unlink()

    prev_hash = _ANCESTOR_HEAD_HASH
    next_seq = 16
    for original in originals:
        toolchain = tuple(sorted(original.get("toolchain", {}).items()))
        environment = original.get("environment", "")
        commit_log = original.get("commit_log", "")
        entry_hash = compute_entry_hash(
            seq=next_seq,
            prev=prev_hash,
            recorded_at=original["recorded_at"],
            command=original["command"],
            argv=original["argv"],
            state_id=original["state_id"],
            state_dir=original["state_dir"],
            outcome=original["outcome"],
            toolchain=toolchain,
            commit_log=commit_log,
            environment=environment,
        )
        entry = LedgerEntry(
            seq=next_seq,
            prev=prev_hash,
            recorded_at=original["recorded_at"],
            command=original["command"],
            argv=tuple(original["argv"]),
            state_id=original["state_id"],
            state_dir=original["state_dir"],
            outcome=original["outcome"],
            toolchain=toolchain,
            commit_log=commit_log,
            entry_hash=entry_hash,
            environment=environment,
        )
        written = ledger_store.write_entry(lgr_dir, entry)
        print(f"wrote seq={next_seq} (was seq {original['seq']} in its own branch) -> {written}")
        prev_hash = entry_hash
        next_seq += 1

    head = ledger_store.verify_and_repair_head(lgr_dir)
    if head is None:
        raise SystemExit("no entries after splice — something is wrong")
    print(f"HEAD repaired: seq={head.seq} entry_hash={head.entry_hash}")


if __name__ == "__main__":
    main()
