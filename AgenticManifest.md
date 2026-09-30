# Agentic manifest — every mount under `.agent/`, and which of its files are specs

*Created: 2026-09-30*

## Abstract — read this first

**What this document is.** The one written list of the repositories mounted
under `.agent/` by `examples/complexgitsync4dev.cgs`, what each is for, and
which Markdown files in them are specs the spec tree must reach.

**Why it exists.** `scripts/spec_tree.py` used to hold a hand-written list of
spec files, and the list fell behind the mounts. It now reads this file, and
fails when a mount is in the `.cgs` and not here, or here and not in the
`.cgs` (the SpecTreeManifest ticket).

**What you will find.** A table of mounts, then a table of spec files.

**Who it is for.** An agent looking for where a kind of rule lives; the
script that checks the spec tree.

**What you need to do with it.** Read the *role* column to find the right
mount. When a mount is added to or removed from the `.cgs`, or a spec file
is added to a mount, change this file in the same change.

```mermaid
graph TD
    CGS["complexgitsync4dev.cgs<br/>mounts under .agent/"] -->|same set, checked| M["AgenticManifest.md<br/>YOU ARE HERE"]
    M -->|lists the spec files of| SPEC["scripts/spec_tree.py"]
    SPEC -->|reachable from| ROOT["CLAUDE.md"]
    SPEC -->|cited or exempt in| DIG["digest.md"]

    classDef here fill:#1565C0,color:#fff,stroke:#111,stroke-width:2px;
    class M here;
```

---

## Mounts

*Side* is `local` (this project's own, writable) or `distant` (shared by every
project that conforms to `DevSpec`, read-only here). The project's own
`docs/` and the `.memory` mounted at `.cgitsync` are not agentic mounts and
are not listed. Who may write which mount is `AGENT.md`'s subject, not this
file's.

| mount | repository | side | role |
|---|---|---|---|
| `.agent/.distant/ticket` | `github:flipoyo/.ticketing` | distant | How a planning ticket is named, ranked, moved and closed. |
| `.agent/.distant/dev-sync` | `github:flipoyo/DevSpec` | distant | The development philosophy, the agent conduct rules (checklist shape, commit message, attribution) and the generic agent-role template. |
| `.agent/.distant/documentation` | `github:flipoyo/DocSpec` | distant | How any Markdown document in the project is written. |
| `.agent/.local/.dev` | `github:flipoyo/.dev` | local | This project's own fill-ins for the before-committing checklist: which commands, which repository, which paths. |
| `.agent/.local/.versioning` | `github:flipoyo/.versioning` | local | How this project versions and releases: the SemVer rules, who bumps what, and the release script. |
| `.agent/.local/.auto` | `github:flipoyo/.auto` | local | How ComplexGitSync manages its own tree with its own tool. |
| `.agent/.local/.localSpec` | `github:flipoyo/.localSpec` | local | The deeper specs: architecture, agent roles, audit findings, the digest, this manifest, and the planning tickets. |
| `.agent/.local/.claude` | `github:flipoyo/.claude` | local | What an agent is handed at session start: `CLAUDE.md` and the reading order. |

## Spec files

*Digest* is `cited` when a line of `digest.md` cites the file, or
`exempt: <reason>` when it states no rule of its own. The spec tree reaches
every file below from `CLAUDE.md`, and a file listed here that does not
exist is a failure.

| file | mount | digest |
|---|---|---|
| [CLAUDE.md](../.claude/CLAUDE.md) | `.agent/.local/.claude` | cited |
| [AGENT.md](../.claude/AGENT.md) | `.agent/.local/.claude` | exempt: a pointer stating the reading order; carries no rules of its own |
| [AdditionalSpecs.md](AdditionalSpecs.md) | `.agent/.local/.localSpec` | cited |
| [audit.md](audit.md) | `.agent/.local/.localSpec` | exempt: findings and open risks, not rules |
| [AGENT.md](AGENT.md) | `.agent/.local/.localSpec` | exempt: the roster of agent roles; the handoff rules are cited from dev-sync/AGENT.md |
| [README.md](DevTickets/README.md) | `.agent/.local/.localSpec` | cited |
| [digest.md](digest.md) | `.agent/.local/.localSpec` | exempt: the digest itself |
| [AgenticManifest.md](AgenticManifest.md) | `.agent/.local/.localSpec` | cited |
| [AgentConduct.md](../../.distant/dev-sync/AgentConduct.md) | `.agent/.distant/dev-sync` | cited |
| [AgentDataContract.md](../../.distant/dev-sync/AgentDataContract.md) | `.agent/.distant/dev-sync` | exempt: states the owner's intent and what a document can and cannot deliver; the binding half is AgentConduct.md §3 |
| [DevSpecs.md](../../.distant/dev-sync/DevSpecs.md) | `.agent/.distant/dev-sync` | cited |
| [AGENT.md](../../.distant/dev-sync/AGENT.md) | `.agent/.distant/dev-sync` | cited |
| [anthropic.md](../../.distant/dev-sync/legalTerms/anthropic.md) | `.agent/.distant/dev-sync` | exempt: a provider-terms assessment, not a rule set |
| [DOCSTYLE.md](../../.distant/documentation/DOCSTYLE.md) | `.agent/.distant/documentation` | cited |
| [TICKETLIFECYCLE.md](../../.distant/ticket/TICKETLIFECYCLE.md) | `.agent/.distant/ticket` | cited |
| [README.md](../.dev/README.md) | `.agent/.local/.dev` | exempt: a pointer to the mount's one document; carries no rules |
| [cgitsync-dev.md](../.dev/cgitsync-dev.md) | `.agent/.local/.dev` | exempt: fills in CLAUDE.md's checklist; the binding rules are the ones the digest already cites from CLAUDE.md |
| [README.md](../.versioning/README.md) | `.agent/.local/.versioning` | exempt: a pointer to the mount's one document; carries no rules |
| [Versioning.md](../.versioning/Versioning.md) | `.agent/.local/.versioning` | cited |
| [README.md](../.auto/README.md) | `.agent/.local/.auto` | exempt: a pointer to the mount's one document; carries no rules |
| [dogfooding.md](../.auto/dogfooding.md) | `.agent/.local/.auto` | exempt: describes how the tree is laid out and says itself it may be stale; not a rule set |
