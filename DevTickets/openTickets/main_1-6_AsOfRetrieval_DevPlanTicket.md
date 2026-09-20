# AsOfRetrieval — what was this tree at time *T*?

*Created: 2026-09-20*

*Branch: main*

> **Split out of [UniversalClock](../archive/20260920_UniversalClock_DevPlanTicket.md)
> §4.4 on 2026-09-20**, when that ticket closed with WP1–WP4 landed. This
> is its WP6, unchanged, given a ticket of its own because it is the one
> piece of "what remains" that touches no external witness and needed no
> further owner decision — see that archived ticket's closing note for
> the two-way split (this ticket, and Omniscience §1.2, for the other
> half). Filed last in the `main` priority-1 pile per the owner's
> instruction: *"enqueue what remains at the end of the reorder
> priority1."*

## Abstract — read this first

**The one-line version.** Recording a moment is useless if nothing can be
asked in terms of it. `memory_timeline` already returns every entry in
order; what is missing is the query — "what was this tree at time *T*?"

**What this document is.** One command, built on two things that already
exist: the chain's own order, and the monotonicity check UniversalClock
WP3 landed on 2026-09-20.

**Why it exists.** The owner's short ticket that started UniversalClock
said a snapshot in the tree "must be trackable by time." Recording a
timestamp on write answers half of that; being able to look a tree up by
one answers the other half, and nothing does that yet.

**What you will find.** §1 the query, unchanged from UniversalClock §4.4.
§2 why it had to wait for monotonicity. §3 the one open question. §4
acceptance.

**Who it is for.** Whoever picks it up. No owner decision is needed.

**What you need to do with it.** Build it — the design is already
settled; only the command surface (§3) is open, and it is a small,
implementer-level choice.

```mermaid
graph LR
    T["time T"] -->|"walk the chain to the<br/>last entry at or before T"| E["ledger entry"]
    E -->|"read state_id"| S["state(hash)<br/>YOU ARE HERE"]

    classDef here fill:#1565C0,color:#fff,stroke:#111,stroke-width:2px;
    class S here;
```

---

## 1. The query

States are content-addressed, the ledger orders them, and
`memory/pending.py`'s `memory_timeline` already returns every entry in
ledger order — it is what `memory explore --timeline` prints. What is
missing is the question itself:

> **What was this tree at time *T*?** — walk the chain to the last entry
> whose `recorded_at` is at or before *T*, and read its `state_id`.

That is a few lines on top of `memory_timeline`. Read-only, local-only, no
network, no omniscience.

## 2. Why this waited for WP3

An as-of query over non-monotonic timestamps returns a confident wrong
answer, silently: if a clock moved backwards somewhere in the chain, "the
last entry at or before *T*" can name an entry that is not actually the
one the workspace held at *T*, and nothing about the answer looks
uncertain. `verify`'s `TIME_REGRESSION` finding (landed with UniversalClock
WP3, 2026-09-20) is what makes this trustworthy: a workspace whose chain
verifies clean is a workspace where "at or before" means what it says.

**Recommendation, not a requirement:** a query against a chain that
`verify` would currently call `time-inconsistent` should say so rather
than answer silently. Left to §3/acceptance rather than promoted to a
decision, since it is a small implementation choice with an obvious
answer.

## 3. The one open question

Whether this is `memory show --as-of`, a flag on `explore`, or a new
verb — the implementer's call, per the CLI mirror rule: a client method
carrying the semantics, a thin CLI pair, the README command table and
`user_guide.tex` updated in the same change.

## 4. Acceptance

- Given a workspace with a real chain and a time *T* between two recorded
  moments, the answer is the `state_id` recorded at or before *T* — not
  the nearest, not the latest, the last one at or before.
- A time before the chain's first entry answers "nothing recorded yet,"
  not the genesis entry by accident.
- A query against a chain `verify` would call `time-inconsistent` says so,
  rather than answering as if the chain were clean.
- Documented in the README command table, `user_guide.tex`, and
  `api_python.tex` if it gains a client method (which the CLI mirror rule
  requires it to).
- `pixi run lint` and `pixi run test` pass; `cgitsync status` shows
  `errors=0`.
