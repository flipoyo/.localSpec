# UniversalClock — one owner for "what time is it", and what that can prove about a State

*Created: 2026-09-20*

*Branch: main*

> **Owner ticket — `shortTickets/universal-clock.md`, 2026-09-20:**
> *"universal-clock.py must be an independent script that will be the one
> in charge of timestamping too. For now it serves to securise the gts."*

> **Ranked 1-1, ahead of [TreeEnvironment](20260920_TreeEnvironment_DevPlanTicket.md),
> which the owner had called very high.** Not a demotion of that ticket —
> a dependency claim, and the owner should overrule it if they disagree.
> Everything queued behind this writes timestamped records: an environment
> record, a release row, a `.self-history` entry. Each one built before the
> clock has an owner is another set of call sites to migrate afterwards.
> This module is small and it is the seam those records should be written
> through from their first line.
>
> It also finishes what [ClockSeam](../archive/20260920_ClockSeam_DevPlanTicket.md)
> started and deliberately left: that ticket fixed the two sites a test had
> an opinion about and listed the rest *"so that the next person adding a
> dated assertion knows the seam exists"*. This is that next person.

> **Closed 2026-09-20 — WP1–WP4 landed, WP5–WP7 split out.** The owner's
> instruction: *"enqueue what remains at the end of the reorder priority1
> if consistent with the other DevPlan, maybe it should land after
> memory-dev Omniscience, or even in it."*
>
> The two remaining halves are not one piece, so they split two ways:
>
> - **WP6 (as-of retrieval, §4.4)** touches no external witness at all —
>   it is a query over the local chain, correct only because WP3 already
>   landed. It travels with the rest of "what remains" to the end of the
>   `main` priority-1 pile: see
>   [AsOfRetrieval](main_1-6_AsOfRetrieval_DevPlanTicket.md).
> - **WP5 (attestation) and WP7 (the push anchor)** are property 3 — the
>   external-witness half — and D5 already said they meet Omniscience
>   there: *"the universal reference and the lag against it belong to
>   Omniscience §1.1."* Reading Omniscience's own §2 record format closed
>   the gap further than expected: `[local] state = "state(<hash>)"`
>   *already is* the attestation WP5 asked for, and falsifiable via
>   `git ls-remote` rather than merely asserted — strictly stronger than
>   what this ticket had planned to build alone. They land **in**
>   Omniscience, not merely after it — see that ticket's §1.2.
>
> **One thing worth being explicit about, since it is a real design
> tension and not a formality.** D5 kept the push anchor *here*, on
> `main`, specifically because it is "the witness a project has when it
> has nothing else" — the fallback for a project that never mounts
> Omniscience. Folding it into a `memory-dev` ticket must not make that
> fallback depend on Omniscience's shared-register machinery landing
> first; Omniscience §1.2 keeps it as an independent, no-omniscience-
> required milestone for exactly that reason. See that ticket's §1.2 and
> its D10.

Everything below this point is the design record as it stood when the
ticket was open. §1–§4 remain accurate; §6's WP5–WP7 rows and part of §7's
acceptance list describe work that continued elsewhere — see the pointers
above rather than this ticket for their current status.

## Abstract — read this first

**The one-line version.** Time is meant to be the backbone of a cgitsync
memory. `universal_clock.py` now owns every read of it (WP1/WP2, landed
2026-09-20) — nine call sites that used to read the wall clock
independently; what still needs building is the check that makes a
recorded moment trustworthy and the way a State becomes findable by time.

**What this document is.** The design for `universal_clock.py`: one module
owning every read of time, the check that makes a recorded moment
trustworthy, and the way a State becomes findable *by* time.

**Why it exists.** A State's name says *what* a tree was and — by a rule
this project has defended twice — never *when*. That is correct and it is
not the end of it: "when" then has to be carried by the memory instead,
rigorously enough to be relied on. Today it is carried by nine scattered
`datetime.now()` calls that nothing validates.

**What you will find.** §1 what ClockSeam left. §2 the module and where it
sits. §3 two defects found in the existing anchor code. §4 time as the
backbone — the three properties "trackable by time" needs, and which are
missing. §5 decisions. §6 work packages. §7 acceptance. §8 what this
refuses.

**Who it is for.** Whoever builds it, and the owner for §5.

**What you need to do with it.** Read §4.1's three properties, then §4.2.
The second one is small, local, costs a comparison per entry, and is what
turns a recorded date into a checked one — it is the piece that makes the
rest worth having.

```mermaid
graph TD
    UC["universal_clock.py<br/>Ring 1 — the only clock read<br/>YOU ARE HERE"] --> L["ledger entries<br/>recorded_at"]
    UC --> ST["State attestation<br/>state(hash) ↔ a moment"]
    UC --> N["workspace names, logs,<br/>generated_at"]
    ST -.->|"cannot be proved<br/>by a local clock alone"| A["external anchor<br/>§4.2"]

    classDef here fill:#1565C0,color:#fff,stroke:#111,stroke-width:2px;
    class UC here;
```

---

## 1. What ClockSeam left

It closed two sites and named the rest. Those rest are still open, and the
count is exact:

| Module | Reads | What for |
|---|---|---|
| `orchestre.py` | 3 | a run-log filename, a `moment` field, a log filename |
| `settings.py` | 2 | a workspace directory name, `generated_at` |
| `memory/store.py` | 2 | register timestamps |
| `paths.py` | 1 | a workspace directory name |
| `registry.py` | 1 | the `.gts`'s own `generated_at` |

Plus the real implementation itself, `SystemClock`, which lives in
`orchestre.py` — **Ring 3**. That placement is the reason the others never
used it: a Ring-1 or Ring-2 module cannot import Ring 3, so `settings.py`
and `memory/store.py` had no choice but to read `datetime.now(UTC)`
themselves. The seam was unreachable from most of the code that needed it.

`ComplexGitSyncClient` now holds a `clock` field (ClockSeam WP2), and
`build_next_entry` takes one. Everything else still reads the module-level
`datetime`.

## 2. The module

### 2.1 Its name

`universal_clock.py`, underscored. The owner wrote `universal-clock.py`;
Python cannot import a module with a hyphen in its name, and every module
in `src/ComplexGitSync/` is already snake_case.

### 2.2 "Independent script" — a module, not a `scripts/` entry

`scripts/` holds `bump_version.py`, `check_module_ceilings.py` and
`tikz2mermaid.py`: standalone programs run by a person, never imported by
`src/`. A clock that everything imports cannot live there.

So "independent" is read as **a module that owns this concern alone and
depends on nothing else** — which is exactly what it should be, and what
`SystemClock` failed to be by living inside a 5000-line orchestration
module. D1 confirms the reading.

### 2.3 Ring 1, and why it cannot be Ring 0

The natural instinct is Ring 0 — a clock looks pure. **The ring rules
forbid it explicitly**: *"Ring 0 performs no I/O at all — no `subprocess`,
no `open()`, no `pathlib` writes, no `os.environ`, no clock reads."*
Reading a clock is the named example.

So the split already in the code is the right one and only needs moving:

| Piece | Ring | Where |
|---|---|---|
| `ClockProtocol` — the interface | 0 | stays pure; it reads nothing |
| The real implementation | **1** | moves down from `orchestre.py`'s Ring 3 |

Ring 1 is the lowest a clock read may sit, and it is reachable by Rings
1–4 — every module in §1's table. That single move is most of the value
here: it turns a seam nobody could reach into one everybody can.

`ClockProtocol` currently lives in `memory/ledger_entry.py`, which is a
memory-specific home for something about to become universal. D2.

## 3. Two defects in the anchor code, found while planning this

`memory/ledger_entry.py` carries `new_time_l0_anchor`, `TimeL0State` and
`hash_time_l0_anchor`, inherited from a deleted `L0.py`. They are unit
tested. **Nothing in `src/` calls them** — the only non-test references are
the re-export in `memory/__init__.py` and a docstring mention. If
universal-clock is to do timestamping, this is the code it would build on,
so both defects matter now.

### 3.1 The anchor throws away the thing that would make it provable

```python
private_anchor = f"TIME-L0:{instant}:{time_ns}:{pid}:{token_hex(16)}"
return TimeL0State(state_hash=hash_time_l0_anchor(private_anchor))
```

`private_anchor` is a local variable. Only its hash is returned; the
pre-image is discarded when the function returns.

A commitment scheme works by publishing a hash *and keeping the secret*,
so you can reveal it later and let anyone recompute the hash. **Destroy the
pre-image and there is nothing left to reveal.** As built, the anchor
produces a unique opaque identifier and can attest nothing at all — which
is fine if identification was the intent, and fatal if timestamping was.

### 3.2 A time anchor is shaped exactly like a tree State

`TimeL0State.state_id` returns `state(<64 hex>)`. `memory/states.py`
matches State ids with `^state\(([0-9a-f]{64})\)$` and builds them with
`_format_state_id`. **The two are indistinguishable**: an anchor id parses
as a State id and vice versa.

Nothing collides today because nothing emits anchors. The moment this
ticket does, a reader — human or `_STATE_ID_RE` — cannot tell a snapshot
of a tree from a moment in time. Whatever this module emits needs a
distinct form.

## 4. Time as the backbone

> **Owner direction — 2026-09-20:** *"time anchoring is fundamental for
> the project. a snapshot in the tree must be trackable by time. Time is
> the backbone of any memory of cgitsync projects."*
>
> So anchoring is not a §5 option to be weighed against its cost. It is a
> requirement, and the question is only how each layer of it is built.
> §4.1 splits it into three, of which **two are cheap, local and missing
> today** — those are the ones this ticket delivers.

### 4.1 What "trackable by time" actually requires

Three separate properties, usually collapsed into one word:

| # | Property | Status today | Whose |
|---|---|---|---|
| 1 | **Order** — this State came before that one | **Have it.** The hash chain proves it outright | — |
| 2 | **A time that cannot silently go backwards** — the recorded moments agree with that order | **Missing.** Nothing checks, and §4.2 says why that bites | **This ticket** |
| 3 | **An outside witness** — the date means something to someone who does not trust the machine | Missing. §4.3 | Mostly [Omniscience](memory-dev_2-1_Omniscience_DevPlanTicket.md) |

A backbone needs all three, and they are independent: the chain can be
perfect while every timestamp on it is nonsense, which is exactly the
state the project is in now.

**The boundary with omniscience, set by the owner on 2026-09-20.** This
module owns **the local clock** — every read of *this machine's* time, for
every project. The **universal reference**, and the lag between it and
each machine, belong to omniscience, which is the only thing that needs
them: comparing clocks is a question you can only ask once there is more
than one participant.

*"A public-only complexgitsync project uses its internal clock"* — so
properties 1 and 2 must stand alone, with no omniscience, no network and
no reference. They do: both are computed from the chain the workspace
already has. That is what keeps this ticket implementable now and keeps
the tool offline-safe.

### 4.2 The local half: the chain and the clock check each other

**This is the cheap, decisive piece, and it needs no third party.**

The chain fixes the order of entries beyond dispute. Each entry also
carries `recorded_at`. Put those together and each validates the other:
**along a chain, `recorded_at` must never decrease.** Entry *N+1* was
written after entry *N* — the chain proves that — so a timestamp that
moves backwards is not a matter of opinion. It is a detected fault.

That turns a local clock from an unchecked claim into a checked one. It
catches, without any network:

- an NTP correction or a manual `date` set in the middle of a session
- a VM or container snapshot restored to an earlier moment
- a dual-boot machine with a different idea of the hour
- **a backdated entry**, which is the tampering case — you cannot forge a
  date downward without contradicting the chain that surrounds it

It costs one comparison per entry and one new member in `Finding`
(`memory/integrity.py`, which already carries ten and is the declared home
for this taxonomy): a `TIME_REGRESSION` beside `BROKEN_LINK` and
`SEQ_GAP`, reported by `verify` like any other. `AdditionalSpecs.md`'s
register section lists that taxonomy and is updated in the same change.

**Monotonic time is what makes time a backbone rather than a decoration.**
Property 1 without property 2 gives an order with meaningless labels;
property 2 makes every label consistent with the order, which is most of
what anyone asking "when was this tree like that?" actually needs.

### 4.3 The honest limit, and the external witness

§4.2 makes local time *consistent*. It cannot make it *true*: a machine
whose clock was wrong from the start, consistently, produces a perfectly
monotonic chain of wrong dates. **Anyone who can write the files can set
the clock, and the same party writes both.** That is not an argument
against anchoring — it is the reason property 3 exists as its own layer.

This project already draws that line twice and should draw it a third
time: the register is *"tamper-evident, not tamper-proof"*, and a
conformity score says `asserted` where it is not measured. A date with no
outside witness is recorded as a claim, and labelled as one.

| Claim | After §4.2 | How |
|---|---|---|
| This State came before that one | **Yes** | The hash chain |
| Nobody edited this State afterwards | **Yes** | Its name is its content digest |
| The dates are consistent with the order | **Yes** | Monotonicity, checked by `verify` |
| This State existed by this date | Only where witnessed | §4.3's anchor |

**A timestamp must never enter the State's name.** Hashing `generated_at`
would give one tree two names on two machines — precisely the failure
canonicalisation version 3 exists to fix. Time is the backbone of the
*memory*, not of a State's identity: the ledger carries it, the name never
does.

#### The external anchor this project already has

The last row becomes provable only if something outside the machine
witnesses the State. The options, cheapest first:

| Anchor | What it gives | Cost |
|---|---|---|
| **The memory's own push** — recommended | The forge records when it received a push, and a local clock cannot backdate someone else's server. The memory is already pushed to a private remote | Nearly free: record which push carried which State, and the remote's receipt is the witness |
| RFC 3161 timestamp authority | A signed token from a third party, verifiable offline, the standard answer | A network dependency and a trust choice, on a tool whose core is offline-safe |
| OpenTimestamps / blockchain anchoring | No trusted party at all | A second network dependency and hours of confirmation latency |

The first one is worth stating plainly because it costs almost nothing:
**this project already sends its memory somewhere it does not control.**
That push is an observation it can cite. It is weaker than a TSA — it
proves "no later than", it needs the forge to be honest, and it proves
nothing about a State that was never pushed — but it is the difference
between *no* external witness and *one*.

### 4.4 Tracking a snapshot *by* time, not only recording one

*"A snapshot in the tree must be trackable by time"* is a reading
requirement as much as a writing one. Recording a moment is useless if
nothing can be asked in terms of it.

The pieces are nearly all there. States are content-addressed, the ledger
orders them, and `memory/pending.py`'s `memory_timeline` already returns
every entry in ledger order — it is what `memory explore --timeline`
prints. What is missing is the question itself:

> **What was this tree at time *T*?** — walk the chain to the last entry
> whose `recorded_at` is at or before *T*, and read its `state_id`.

That is a few lines on top of `memory_timeline`, and it is only correct
**because** of §4.2: an as-of query over non-monotonic timestamps returns
a confident wrong answer, silently. The monotonicity check is what makes
time answerable rather than merely present.

Worth stating as the shape of the capability, not the command surface —
whether it is `memory show --as-of`, a flag on `explore`, or something
else is the implementer's call, and the CLI mirror rule applies either way
(a client method carrying the semantics, a thin CLI pair, the README table
and `user_guide.tex` updated).

## 5. Decisions

| D | Question | Recommendation | Whose call |
|---|---|---|---|
| **D1** | Module under `src/ComplexGitSync/`, or a `scripts/` program? | **A module** (§2.2). `scripts/` is not importable by the package, and every caller in §1 is inside it | **Owner** |
| **D2** | Does `ClockProtocol` move out of `memory/ledger_entry.py`? | Yes — the interface belongs with the clock, not with the ledger. `ledger_entry.py` is Ring 0 and self-contained by rule, so it keeps a structurally identical Protocol of its own or imports the Ring-0 half. Protocols are structural; nothing breaks either way | Implementer |
| **D3** | All nine call sites at once, or only the ones that matter? | **All nine.** They are one-line changes, and the point of a universal clock is that there is no tenth. A module named "universal" that owns six of nine reads is worse than none | Implementer |
| **D4** | What happens to the TIME-L0 anchor code (§3)? | **ANSWERED 2026-09-20: delete it** (WP4, landed). *The reasoning, kept:* decide, do not inherit — Either it becomes this module's attestation primitive — and §3.1 is fixed by retaining the pre-image, §3.2 by giving it its own id form — or it is deleted as a tested-but-unused leftover. Carrying it forward unchanged is the one option that helps nobody | **Owner** |
| **D5** | How far does time anchoring go (§4)? | **Not a question of whether — the owner settled that on 2026-09-20.** Properties 1 and 2 are required and land here; they are local, cheap and need no network. Property 3 splits: the **push anchor** stays here, as the witness a project has when it has nothing else, and the **universal reference and the lag against it belong to [Omniscience](memory-dev_2-1_Omniscience_DevPlanTicket.md)** §1.1 — a project mounting no omniscience uses its internal clock and stops at property 2 | **Owner** |
| **D7** | Does a time regression fail `verify`, or only report? | **ANSWERED 2026-09-20: its own verdict, `time-inconsistent`, exit 1** (WP3, landed) — not folded into `corrupt`, because the chain did hold. *The reasoning, kept:* report as a finding, exit non-zero like any other — `verify`'s contract is that "corrupt" means the chain does not hold, and a backwards timestamp is the chain disagreeing with itself. But it must be its own finding (`TIME_REGRESSION`), never folded into `BROKEN_LINK`: the two have different causes and different fixes, and a clock correction is not history rewriting | **Owner** |
| **D6** | Is the attestation part of the State file, or beside it? | **Beside it**, cited by hash. `generated_at` may stay in the `.gts` as the unverified local claim it already is; the attestation is a separate record that points at `state(<hash>)`. Nothing time-related enters the canonical payload, ever (§4.1) | Implementer |

## 6. Work packages

**WP1 and WP2 landed 2026-09-20.**

| WP | Does | Depends on |
|---|---|---|
| **WP1 — landed** | `universal_clock.py` at Ring 1, holding the real implementation moved out of `orchestre.py`. `ClockProtocol`/`SystemClock` defined there; `memory/ledger_entry.py` keeps its own structurally identical Protocol, Ring-0-self-contained, per D2. `AdditionalSpecs.md`'s ring table (now five import rules, not four) and `CLAUDE.md`'s module table updated in the same change | D1, D2 |
| **WP2 — landed** | All nine direct reads (§1) go through it, each via an injected `clock: ClockProtocol` — required where a test asserts on the exact value (`memory_reboot`'s archive name, `commit_message`'s moment, from ClockSeam), optional-and-defaulted elsewhere, following that ticket's own precedent for sites nothing asserts on. `pixi run check-ceilings` gained a fourth check, unconditional across every module rather than tied to a declared Ring-0 subset — proven to actually fail (not just report) on both an existing module regressing and a brand-new module born with a violation, which needed a small fix to `run_check`'s own logic (§WP2 note below) | WP1, D3 |
| **WP3 — landed** | **Monotonic time (§4.2)**: `TIME_REGRESSION` on `Finding`, `TIME_INCONSISTENT` on `HistoryState` as a fifth `verify` answer (D7), `_check_time_monotonic` in `verify_chain`, and `resolve_state()` — one authority on which findings mean which verdict, replacing the rule `orchestre.verify` used to keep its own copy of. Documented in `AdditionalSpecs.md` (taxonomy + the five answers + why it is not `corrupt`), `README.md`, `user_guide.tex`, `api_python.tex` | WP1, D7 |
| **WP4 — landed** | D4 answered **delete**: `TimeL0State`, `new_time_l0_anchor`, `hash_time_l0_anchor`, their re-exports and their tests are gone; `ledger_entry.py` shrank 220 → 201 LOC and the ratchet locked that in. Its module docstring records what was removed and why, so the next person reaching for an attestation primitive knows to write one that keeps its pre-image | D4 |
| **WP5 — moved** | Attestation: a record binding `state(<hash>)` to a moment, beside the State, never inside it (D6). Superseded by Omniscience §2's own record, which already does this and does it falsifiably | Omniscience O1 |
| **WP6 — moved** | **As-of retrieval (§4.4)**: "what was this tree at time *T*", built on `memory_timeline`, as a client method with a thin CLI pair | [AsOfRetrieval](main_1-6_AsOfRetrieval_DevPlanTicket.md) |
| **WP7 — moved** | The push anchor (§4.3): record which push carried which State, so the remote's receipt is citable | Omniscience §1.2 |

**WP2 note, found while implementing.** `check_module_ceilings.py`'s
`run_check` only ever checked Ring-0 purity, the clock seam, or the
docstring/`Imports:` cross-check for a module that **already had a
baseline entry** — a brand-new module born with a violation sailed through
`--check` silently until someone happened to run `--write-baseline`.
Confirmed by planting a real violation in a throwaway module before fixing
it: the table printed `CLOCK:1` but exit stayed `0`. Restructured so those
three absolute checks run unconditionally, and only the two ratchet
comparisons (LOC, public-symbol count) still require a prior baseline —
they have nothing to ratchet against otherwise. This was a pre-existing
gap in the script, not introduced by WP2; fixed here because WP2's own
acceptance criterion ("a check fails if a tenth call site appears") is the
first thing that would have silently failed to hold.

**D4 and D7 answered by the owner, 2026-09-20**, after being put with
their alternatives: **delete** the TIME-L0 anchor, and **give a time
regression its own verdict at exit 1** rather than calling it `corrupt`.
WP3 and WP4 landed the same day.

**WP5–WP7 remain.** WP5 (attestation) and WP7 (the push anchor) are the
external-witness half — property 3 of §4.1, the one this ticket always
said it shares with Omniscience. WP6 (as-of retrieval) needs no further
decision: it is buildable now that WP3 makes a timestamp answerable, and
is the natural next piece.

## 7. Acceptance

- **MET (WP1/WP2, 2026-09-20).** `datetime.now`, `time.time_ns`,
  `os.getpid` and `secrets.token_hex` appear in exactly one module of
  `src/ComplexGitSync/`, and a check fails if a tenth call site appears —
  proven by planting a real one and watching `pixi run check-ceilings`
  fail, in both an existing module and a brand-new one.
- **MET.** A test can run the whole suite at any fixed instant by
  injecting one clock, with no `monkeypatch` of a module-level `datetime`
  anywhere — the one test that still did this
  (`test_a_second_reboot_the_next_day_writes_v3`, which broke the moment
  `orchestre.py` stopped importing `datetime` at all) now injects a fixed
  clock through `ComplexGitSyncClient(clock=...)` instead.
- **MET.** A chain whose timestamps move backwards is reported as
  `TIME_REGRESSION`, by name, and is not confused with a rewritten
  history (§4.2, D7). Set the clock back mid-session and `verify` says so.
- **MET.** The documentation says what each layer proves: order and
  consistency from the chain, absolute time only where something outside
  the machine witnessed it (§4.3).
- **Moved to Omniscience O1.** Two machines holding the same tree at
  different moments still compute the same State hash, and an attestation
  names the State it attests without being mistaken for one (§3.2) —
  Omniscience's own record already satisfies both, more strongly than
  planned here.
- **Moved to AsOfRetrieval.** "What was this tree at time *T*?" is
  answerable from the memory alone, and the answer is a State hash (§4.4).
- `pixi run lint`, `pixi run test` and `pixi run check-ceilings` pass;
  `cgitsync status` shows `errors=0`.

## 8. What this refuses to do

- **It does not put time into a State's name.** Not `generated_at`, not an
  anchor, not a serial. The name is what the tree is.
- **It does not call a local timestamp proof.** Where the only witness is
  the machine that wrote the record, the record says so.
- **It does not add a network dependency to an offline path.** Anchoring
  happens when something is already going to the network — a push — or not
  at all until a TSA is chosen deliberately (D5).
- **It does not define or reach a universal clock.** That is omniscience's,
  along with the lag between it and this machine. A project with no
  omniscience uses its internal clock and is complete without one.
- **It does not keep the TIME-L0 code merely because it exists** (D4).
