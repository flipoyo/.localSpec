# TicketTreeMove — move `DevTickets/` to `.dev`, and fix the citations that will not survive it

*Created: 2026-09-19*

*Branch: main*

> **Ticket review — 2026-09-30, from the owner's short ticket `archive/.closedUserTicket/20260930_ReorderPriority-mem-multiUser.md`.** Renumbered `main_2-4` → `main_2-3`: the owner's order did not name it; it keeps its place relative to AsOfRetrieval and stays above AutofixBlindSpot.

> **Ticket review — 2026-09-23.** Renumbered again, `main_1-4` → `main_1-3`:
> [AgentContract](../archive/20260923_AgentContract_DevPlanTicket.md)
> finished and archived, compacting the pile by one. Everything below is
> otherwise unchanged.

> **Ticket review — 2026-09-22, part 3.** Renumbered again, `main_1-4` →
> `main_1-5`: [Autofix](../archive/20260923_Autofix_DevPlanTicket.md) is queued first
> in the pile, on the owner's explicit instruction. Everything below is
> otherwise unchanged.

> **Ticket review — 2026-09-22, part 2.** Renumbered again, `main_1-5` →
> `main_1-4`: [ProjectSpecSplit](../archive/20260922_ProjectSpecSplit_DevPlanTicket.md)
> finished and archived in the same pass, compacting the pile by one, and
> its own WP3 path sweep corrected the `.agent/` prefix everywhere —
> including on the `universal_clock.py` citation below. It did **not**
> touch the citation's target, only its prefix: `universal_clock.py` still
> points at the dead `openTickets/main_1-1_UniversalClock_DevPlanTicket.md`
> path this ticket's §1 already names, which is this ticket's job to fix,
> not ProjectSpecSplit's — a stale prefix and a stale target are the two
> different defects these two tickets each own.

> **Ticket review — 2026-09-22.** Promoted from `main_2-4` (stand-by) to
> `main_1-5` (pick up now), on the owner's request to reorganise the
> backlog into: finalize the agentic, then what's important before
> data-repo, then data-repo, then Omniscience. Worth doing before
> data-repo specifically because that workstream is about to add seven
> more tickets that will themselves get archived and renamed over time —
> exactly the churn this rot check exists to catch — and because this
> same review already found a fresh instance of it:
> `universal_clock.py` still cites
> `.agent/.local/.localSpec/DevTickets/openTickets/main_1-1_UniversalClock_DevPlanTicket.md`,
> which is archived as `archive/20260920_UniversalClock_DevPlanTicket.md`.
> Add it to §1's table.

> **Found while auditing the planning surface on 2026-09-19.** Not
> reported by anyone: it was found by checking every ticket path cited in
> `src/` against the filesystem, which nothing does today.

> **Merged and renamed 2026-09-30**, from `CitationRot` (2026-09-19) and
> `shortTickets/mv-tickets.md` (owner, 2026-09-30): *"DevTickets should be
> in `.dev` not `.localSpec`. It is a more intuitive organisation of private
> repos."* The two belong together and in that order: this ticket already
> lists five source citations that point at ticket paths which no longer
> exist, and the move rewrites **every** such path at once — every
> `.localSpec/DevTickets/...` reference in `src/`, plus every relative link
> inside the tickets themselves (`../AdditionalSpecs.md`,
> `../../.distant/...`). Building the check first (§3) and then moving turns
> the largest breakage this tree can suffer into a list the check prints.
> Moving first means finding out one dead link at a time.
>
> The sections below are the original ticket, unchanged, and remain
> accurate: §1 the five stale citations, §2 why they recur by design, §3 the
> check, §4 the two decisions. §6 is the move itself.

## Abstract — read this first

**The one-line version.** Five docstrings in `src/` point at planning
tickets by their open path. Those tickets were archived, which renames
them — so the paths are dead, and nothing noticed.

**What this document is.** A small, verifiable maintenance ticket: fix
the five, and add the check that would have caught them.

**Why it exists.** This project's modules carry unusually heavy
docstrings that cite the ticket a design came from, and that habit is
worth keeping — it is how a reader finds the reasoning behind a module.
But TICKETLIFECYCLE guarantees the citation breaks: finishing a ticket
*renames* it, from `openTickets/<branch>_<p>-<r>_<Name>_DevPlanTicket.md`
to `archive/<YYYYMMDD>_<Name>_DevPlanTicket.md`. Every citation to an
open ticket is a reference with a known expiry date, and no step in the
lifecycle updates them.

**What you will find.** §1 the five. §2 why this recurs by design. §3 the
check. §4 the two ways to stop it. §5 acceptance.

**Who it is for.** Whoever picks it up; §4 has one owner decision, and a
recommendation that needs no decision at all.

**What you need to do with it.** §1 is a five-line fix. §3 is the part
worth having.

```mermaid
graph LR
    T["openTickets/<br/>main_1-1_Foo_DevPlanTicket.md"] -->|"cited in a docstring"| S["src/…py"]
    T -->|"implemented → renamed"| A["archive/<br/>20260918_Foo_DevPlanTicket.md"]
    S -.->|"still points at<br/>the old path"| X["dead reference<br/>YOU ARE HERE"]

    classDef here fill:#1565C0,color:#fff,stroke:#111,stroke-width:2px;
    class X here;
```

---

## 1. The five

Two tickets, archived, still cited by their open paths:

| Cited path | Now at |
|---|---|
| `openTickets/memory-dev_1-2_WorkingTransitionState_DevPlanTicket.md` | `archive/20260917_WorkingTransitionState_DevPlanTicket.md` |
| `openTickets/main_1-1_CheckoutForkGuard_DevPlanTicket.md` | `archive/20260918_CheckoutForkGuard_DevPlanTicket.md` |

Cited from `memory/pending.py`, `memory/repository.py`, `orchestre.py`,
`git_runner.py` and `operations.py`.

Three open tickets cite the same two stale paths in prose —
`main_2-1_MemoryArchitecture` (twice) and `main_2-3_StateLocking` — and
should be corrected in the same pass.

**A third archived ticket, found 2026-09-20**, cited the same way:
`openTickets/memory-dev_1-2_MemoryOnboarding_DevPlanTicket.md`, now
`archive/20260917_MemoryOnboarding_DevPlanTicket.md`, cited from
`main_2-1_MemoryArchitecture`. Note that both it and
`WorkingTransitionState` were filed at `memory-dev_1-2` — the rank was
reused after the first was archived, which is §1's retargeting hazard
happening a second time in the same pile.

**`main_1-1_CheckoutForkGuard` is the sharper one.** That path is not
merely dead: as of 2026-09-19 it names a *different live ticket*,
[TreeEnvironment](../archive/20260920_TreeEnvironment_DevPlanTicket.md), because
rank `1-1` on `main` was reused the moment the pile changed. A reader
following that citation lands on a real, current document about something
else entirely. A dead link is an inconvenience; a link that silently
retargets is a wrong answer.

**A fourth instance, found during the 2026-09-22 ticket review that
promoted this ticket:** `universal_clock.py` cites
`openTickets/main_1-1_UniversalClock_DevPlanTicket.md`, archived as
`archive/20260920_UniversalClock_DevPlanTicket.md`. That same rank,
`main_1-1`, was reused again in this very review — it now names
[ProjectSpecSplit](../archive/20260922_ProjectSpecSplit_DevPlanTicket.md), a
different ticket again — the retargeting hazard recurring for a third
time on the same rank.

## 2. Why it recurs by design

The lifecycle is working as specified. `TICKETLIFECYCLE.md` §5 requires
the rename, and it is what makes a directory listing answer "is this
still open?". The rank prefix is deliberately rewritten whenever the
queue is re-ranked, so even a ticket that stays open changes its path.

So a citation to an open ticket is guaranteed to break. There are only two
honest responses: stop citing paths that move, or check them. §4 takes
both.

## 3. The check

`scripts/check_module_ceilings.py` already walks every module in
`src/ComplexGitSync/` and already cross-checks a docstring claim — its
declared `Imports:` list — against reality. Adding one more check to the
same script and the same `pixi run check-ceilings` task is the cheap
option: extract every `.localSpec/DevTickets/...md` path in `src/` and
report the ones that do not exist.

Roughly the check, run today:

```bash
grep -rhoE "\.localSpec/DevTickets/[A-Za-z0-9_./-]+\.md" src/ | sort -u |
  while read p; do [ -f "$p" ] || echo "STALE: $p"; done
```

Two caveats for whoever implements it. It must run from the tree root
where `.localSpec` is mounted, and **it must not fail when `.localSpec`
is absent** — it is a private mount, and a user who installed from
`install.cgs` has no `DevTickets/` at all. Absent means skip, not fail.

## 4. The two ways to stop it

| D | Question | Recommendation | Whose call |
|---|---|---|---|
| **D1** | Cite tickets by path, or by name only? | **By name only, for a ticket still open.** `AdditionalSpecs.md` already states the principle for a different reason — "`src/` cites this section, not a ticket: an archived ticket is a historical record and is never edited, and a live schema must not sit inside one." A docstring saying "see the WorkingTransitionState ticket" survives every rename the lifecycle performs. An *archived* ticket's path is stable and may be cited in full | Implementer |
| **D2** | Does the check gate `pixi run lint`, or only `check-ceilings`? | `check-ceilings`, which is where the other docstring check lives and which is not on the commit path. A dead documentation link should not block a commit that fixes a bug | **Owner** |

## 6. The move

`DevTickets/` today is a directory inside the `.localSpec` mount
(`github:flipoyo/.localSpec`, branch `ComplexGitSync`), alongside
`AdditionalSpecs.md`, `audit.md`, `digest.md` and `AGENT.md`. The owner wants
it in its own `.dev` mount under `.agent/.local/`, so the private repos split
by purpose: specifications in `.localSpec`, the planning surface in `.dev`.

What the move touches, and why it is worth doing with §3's check in hand:

| Touches | Why |
|---|---|
| `examples/complexgitsync4dev.cgs` | a new private, writable entry for `.dev` at `.agent/.local/.dev`; `.localSpec` keeps the rest |
| every relative link **inside** a ticket | `../AdditionalSpecs.md`, `../README.md`, `../../.distant/ticket/TICKETLIFECYCLE.md` all change depth |
| `src/` citations | §3's grep pattern is literally `.localSpec/DevTickets/` — the check must learn the new path, and every citation must move with it |
| `scripts/spec_tree.py` | `DECLARED_SPEC_FILES` is hand-maintained and names paths in the tree |
| `CLAUDE.md` *Layout*, `AdditionalSpecs.md`, `DevTickets/README.md` | all describe where the planning surface lives |
| `digest.md` | citations resolve against the declared universe |

**Do §3's check first, then the move, then re-run it.** A move with a working
link check is a mechanical change with a printed list of everything it broke;
a move without one is exactly how the five citations in §1 came to exist.

**Order.** §1's five citations → §3's check (D2 says where it runs) → the
move → re-run everything: `--check`, `--check-digest`, `check-ceilings`, and
`cgitsync status` from the tree's own root, which is what proves the new
mount actually resolves.

## 7. Acceptance

- The five citations name their archived tickets, or name the ticket
  without a path.
- No path under `src/` matching `.localSpec/DevTickets/**.md` fails to
  resolve.
- `pixi run check-ceilings` reports stale citations, and passes cleanly in
  a checkout with no `.localSpec` mounted.
- `DevTickets/` lives in a `.dev` mount at `.agent/.local/.dev`, declared in
  `examples/complexgitsync4dev.cgs`, and a fresh bootstrap of that spec
  produces it.
- No relative link inside any ticket, and no citation in `src/`, points at
  the old location; `spec_tree.py --check` and `--check-digest` exit 0.
- `pixi run lint` and `pixi run test` pass; `cgitsync status`, run from the
  tree's own root, shows `errors=0` — which is what proves the new mount
  resolves.
