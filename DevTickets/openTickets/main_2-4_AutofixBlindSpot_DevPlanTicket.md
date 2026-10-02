# AutofixBlindSpot — autofix only reacts to an error cgitsync already logged, and this whole class of defect raises none

*Created: 2026-09-24*

*Branch: main*

> **Correction — 2026-10-02, owner's decision.** WP2 as first written asked `autofix` to rewrite a commit message with `git commit --amend`, and to amend a pushed commit and force-push it given `force=True`. That was a wrong reading of what `autofix` is for: it eases the merge procedure, it does not rewrite commits. The `tmpAutoFix` branch built exactly that WP2 and is being closed for it (CorrTicket TmpBranchClosure). ComplexGitSync now rewrites nothing (`AdditionalSpecs.md`, *The hard prohibitions*), so WP2 and the acceptance criteria below are rewritten: `autofix` reports a bad message and proposes ways to extract it intact, and nothing more. The read-only detection already written on `tmpAutoFix` is what this ticket takes back.

> **Ticket review — 2026-09-30, from the owner's short ticket `archive/.closedUserTicket/20260930_ReorderPriority-mem-multiUser.md`.** Demoted `main_1-1` → `main_2-4`: the owner's words, *"AutoFixBlindSpot is not prioritary before MemoryArchitecture, UserInstallPath, StateLocking or AsofRetrieval."* Its content is unchanged.

> **Ticket review — 2026-09-30, after DefaultUserMemory.** Renumbered `main_1-2` → `main_1-1`: [DefaultUserMemory](../archive/20260930_DefaultUserMemory_DevPlanTicket.md) was implemented and archived, so the priority-1 ranks were compacted.

> **Ticket review — 2026-09-30, after InstallFrontier.** Renumbered `main_1-3` → `main_1-2`: [InstallFrontier](../archive/20260930_InstallFrontier_DevPlanTicket.md) was implemented and archived, so the priority-1 ranks were compacted.

> **Ticket review — 2026-09-30, after ModulePackagisation.** Renumbered `main_1-4` → `main_1-3`: [ModulePackagisation](../archive/20260930_ModulePackagisation_DevPlanTicket.md) was implemented and archived, so the priority-1 ranks were compacted.

> **Diagnosis ticket**, opened from a live incident on this project's own
> tree, per the owner's instruction to correct what happened and write up
> autofix's gap rather than patch around it silently. §1-§2 are the
> diagnosis; §3 is the correction plan.

> **Renumbered 1-4 → 1-6 and narrowed in the priority-1 reorganisation of
> 2026-09-30** (1-4 → 1-5 in that pass, then → 1-6 when
> [DefaultUserMemory](../archive/20260930_DefaultUserMemory_DevPlanTicket.md) took 1-5). The old WP1 — validating a commit message *before*
> committing it — moved to
> [AgentGuardrails](../archive/20260930_AgentGuardrails_DevPlanTicket.md) WP4, with the
> digest work, because preventing bad agent output is one subject and
> detecting it afterwards is another. That guardrail closes the case where
> `cgitsync commit` is the one committing. **This ticket is now only about
> the case it cannot reach**: a commit made by a bare `git commit` outside
> `cgitsync`, which leaves no logged error for `autofix` to start from. It
> is ranked last in the priority-1 pile because the guardrail removes the
> common path, not because the blind spot stopped mattering.

## Abstract — read this first

**The one-line version.** `cgitsync autofix` starts from "the former
error" — the last `command_end`/`status=error` line in
`.cgitsync/logs/*.log` — but a commit whose *message* got mangled by the
shell it was pasted into is not an error `git commit` ever raises: the
commit succeeds, `git` is satisfied, and `find_last_error` finds nothing
because the last logged command's own `status` was `"ok"`.

**What this document is.** The diagnosis of a real commit on this
project's own `main` (`701a98f`, already pushed to
`git@github.com:flipoyo/ComplexGitSync.git`) whose message lost every
backtick-quoted phrase — replaced by whatever a shell substituted for it,
including the literal output of `git rev-parse --abbrev-ref HEAD` — and
collapsed from several paragraphs to one line, plus a correction plan.

**Why it exists.** An agent drafted the commit message with inline code
spans (`` `git rev-parse --abbrev-ref HEAD` ``, `` `bump-version` ``, and
similar) the way technical prose ordinarily marks up a command name. The
owner pasted it into a shell. Backticks are command substitution in a
shell, quoted or not, and unlike a name genuinely quoted in a way a shell
would leave alone, these were executed for real: `` `git rev-parse
--abbrev-ref HEAD` `` really did run, in that repository, and really did
print `main`, which is exactly what took its place. Every other
backtick-quoted phrase named a program that does not exist standalone
(`bump-version`, `.versioning`, `release/`) and silently substituted to
nothing. `cgitsync autofix` was then asked to fix it and found nothing to
do, correctly, given what it currently is: a dispatcher over one
`Situation` shape — an already-raised, already-logged error string — and
this incident produced none.

**What you will find.** §1 the incident, reproduced from the real
repository. §2 the root cause: `autofix`'s `Situation`/`matches()` model
has exactly one way to learn about trouble, and this class of defect never
reaches it. §3 three work packages. §4 acceptance criteria.

**Who it is for.** Whoever picks up `autofix` work next — a peer
workstream to [Autofix](../archive/20260923_Autofix_DevPlanTicket.md),
which built the one repair `autofix` currently knows (a diverged,
chain-shaped private repository); this ticket is about the detection side
autofix has never had at all: a defect with no logged error to start from.

**What you need to do with it.** Read §2 for exactly which line in
`repair_from_cli.py` says "no failing command found" and why that is the
right answer today, then WP1 in §3 — the rest follow from it.

```mermaid
graph TD
    CLI["cgitsync autofix"] --> FIND["FromCliRepair.find_last_error()<br/>reads .cgitsync/logs/*.log"]
    FIND -->|"last command_end.status == ok"| NONE["returns None<br/>YOU ARE HERE"]
    NONE --> RAISE["NoMatchingRepairError:<br/>no failing command found"]

    GIT["a plain git commit,<br/>run outside cgitsync entirely"] -->|"succeeds, message mangled"| NOLOG["never logged<br/>to .cgitsync/logs at all"]
    NOLOG --> RAISE

    classDef here fill:#B71C1C,color:#fff,stroke:#111,stroke-width:2px;
    class NONE here;
```

---

## 1. What happened today

A commit landed on this project's own `main`, already pushed:

```
$ git show -s --format=%B 701a98f
cgitsync3.1.1 Fixes a live crash: self-history's push path assumed any
adopted mount already had a commit, but an unborn branch makes main raise
instead of answering none the way a detached HEAD does; / before the
first  is now a harmless no-op. Also repoints pixi.toml's  task at ,
its actual mount path since the release skill was renamed — the stale
 path had been silently breaking every  run
```

Drafted, before it met a shell:

```
cgitsync3.1.1

Fixes a live crash: self-history's push path assumed any adopted mount
already had a commit, but an unborn branch makes `git rev-parse
--abbrev-ref HEAD` raise instead of answering "none" the way a detached
HEAD does; `memory push`/`memory reboot` before the first `self-history
add` is now a harmless no-op. Also repoints pixi.toml's `bump-version`
task at `.versioning`, its actual mount path since the release skill was
renamed — the stale `release/` path had been silently breaking every
`bump-version` run.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

Every backtick-quoted span is gone. `` `git rev-parse --abbrev-ref HEAD` ``
became the literal word `main` — that command really ran, in that
repository, on that branch, and its real stdout took the phrase's place.
The others (`` `memory push`/`memory reboot` ``, `` `self-history add` ``,
`` `bump-version` ``, `` `.versioning` ``, `` `release/` ``) named nothing
runnable and substituted to empty. The blank-line paragraph breaks and the
trailer are gone too — the whole message is one physical line. This is
what a shell does to an unescaped backtick inside a double-quoted (or
unquoted) `-m` argument: not a `cgitsync` error, not a `git` error, a
correct commit made from a corrupted string.

This is also, separately, a rule violation independent of the shell
damage: [AgentConduct.md](../../../../.distant/dev-sync/AgentConduct.md) §2-3
requires plain English, three lines at most, and no co-authorship trailer
on any commit — the drafted message before it even reached a shell was
already too long and already carried a forbidden trailer.

`pixi run cgitsync autofix` was run against this. It raised
`NoMatchingRepairError("autofix: no failing command found in the run
log.")` — see `repair_from_cli.py:114` — because the tree's own
`.cgitsync/logs/` most recent entry was an unrelated `push` that had
already completed with `"status": "ok"` before this commit was even made
outside `cgitsync` entirely. There was nothing wrong from `cgitsync`'s own
point of view to find.

## 2. Root cause: `autofix` has exactly one door in, and this defect never uses it

`autofix/base.py`'s `Situation` carries a `repo` and a `source_error: str`
— nothing else. Every `Repair.matches()` in the registry, today just
`DivergentUserRepair`, pattern-matches on that one string. `Situation` is
only ever constructed one way: `FromCliRepair.run()`, from
`find_last_error()`, which reads the newest `.cgitsync/logs/*.log` and
returns `None` — refused outright, per `NoMatchingRepairError`'s own
docstring: *"I don't know what this is" is the safe answer, never a reason
to guess* — whenever the last recorded command there succeeded.

Two independent gaps compound here, either one enough on its own:

- **A commit made outside `cgitsync` is invisible to it.** `cgitsync
  commit` (`orchestre/tree_commands.py`, `TreeCommands.commit`) takes `message: str` as a real Python
  argument — no shell involved, no backtick hazard — and logs
  `commit_start`/`commit_end` events. A plain `git commit -m "..."`, run
  directly against a mounted repository the way this incident's commit
  was, produces nothing in `.cgitsync/logs/` at all, successful or not:
  `cgitsync` has no visibility into a Git operation it did not itself
  run.
- **A *logged* commit is checked, but only by `cgitsync commit`.** Since
  AgentGuardrails (commit `8ffecce`), `CommitMessagePolicy`
  (`commit_message.py`, called from `TreeCommands.commit`) refuses a message
  that breaks `AgentConduct.md` §2 (prefix `<project><version>`, three
  lines, plain English, no trailer) before committing, in a tree that has
  adopted DevSpec. This ticket first said `commit()` validated nothing;
  that was corrected on 2026-10-02 (RuleConformity G1). What nothing checks
  is a commit made by a bare `git commit`, which is the case that remains.

`autofix`'s entire model assumes trouble announces itself as a raised,
logged error. This class of defect is the opposite: `git` accepted the
string it was given without complaint, and the only way to notice
something is wrong is to read the *result* — the tip commit's own message
— against a rule, not against a stack trace.

## 3. Correction plan

| WP | Touches | Deliverable |
|---|---|---|
| **WP1** | `autofix/base.py`, a new `autofix/repair_commit_message.py` | A second, non-error-driven entry point: `FromCliRepair` (or a sibling dispatcher) gains a mode that inspects the *tip commit* of every writable/project repository directly — `git log -1 --format=%B` — rather than only `.cgitsync/logs/*.log`. `Situation` gains an optional `commit_message: str \| None` alongside `source_error`, so a `Repair.matches()` can pattern-match on either source without every existing repair needing to change. `MalformedCommitMessageRepair.matches()` flags a message that violates AgentConduct §2's shape or looks shell-mangled (a bare word where a backtick-quoted phrase would be — heuristically, a bare `` `<runnable-name>` `` reduced to something matching `git rev-parse --abbrev-ref HEAD`'s own output space, i.e. an existing branch name, is the strongest signal this incident actually offers; a run of two consecutive spaces where a phrase silently substituted to empty is the second). |
| **WP2** | `autofix/repair_commit_message.py` | **Report, never repair.** When WP1 flags a tip commit, `autofix` prints the repository, the commit, the rule it breaks (or the suspected shell damage, called suspected), and ways to extract the message intact so a person can fix it by hand: `git show -s --format=%B <sha> > message.txt`, `git log -1 --format=%B`, or `git cat-file commit <sha>` for the raw object. It runs no Git command that writes: no `--amend`, no rebase, no force-push, no `force` flag, whatever message it is handed. When the same commit is what makes a merge fail, it says so in the merge diagnosis and stops there. |
| **WP3** | `tests/`, `.agent/.local/.localSpec/AdditionalSpecs.md` | An integration test for WP1/WP2 building a repository with a tip commit that violates the rule, confirming `autofix` finds and reports it, prints the extraction commands, and leaves every ref and commit unchanged. `AdditionalSpecs.md`'s `orchestre/`/`autofix/` rows updated to state the new validation point and the second `Situation` source, per `CLAUDE.md`'s *before-committing* checklist item 6. |

WP1 alone would have caught this incident's rule violations (length,
trailer) before any shell ever saw the message — it does not, and cannot,
catch shell-substitution damage that happens after `cgitsync` has already
handed the string to `git`. WP2-3 report exactly that residual case, and
for any commit made by a bare `git commit` outside `cgitsync` entirely,
which WP1 can never see no matter how strict it gets.

## 4. Acceptance criteria

- (The "refuse before committing" criterion moved with WP1 to
  [AgentGuardrails](../archive/20260930_AgentGuardrails_DevPlanTicket.md).)
- `cgitsync autofix` can be pointed at a repository's own tip commit, not
  only at the last logged error, and correctly identifies a message that
  violates the house style or shows signs of shell-substitution damage.
- `autofix` never changes a commit, pushed or not: every ref, sha and message is
  the same before and after it runs, and a test checks it.
- A report for a bad message includes at least one way to extract that
  message intact.
- The real `701a98f` incident (or an equivalent fixture built from it) is
  covered by a regression test.
- `.localSpec/AdditionalSpecs.md`'s `orchestre/`/`autofix/` rows describe
  the new validation point and the second `Situation` source.
- `pixi run lint` and `pixi run test` pass; `cgitsync status` shows
  `errors=0`.
