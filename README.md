# .localSpec

*Created: 2026-08-31*

A project's own deeper specs, its agent roster, and its audit findings: how
the *product* is built. How the work gets done (the checklist, versioning,
tickets) is in the project's `.dev` repository, and what an agent is handed
at session start is in `.claude`.

This `main` branch carries nothing project-specific; it exists only so a
project's `fallback_branch = "main"` resolves before that project's own
branch exists. Each consuming project gets its own branch here, named after
the project, holding:

- `AdditionalSpecs.md` — that project's architecture and technical rules. It
  is the project's own specification, so it has no pattern above it
  (`standalone` in the manifest).
- `AGENT.md` — that project's filled-in instance of `DevSpec`'s generic
  `AGENT.md` template.
- `audit.md` — that project's audit findings, legacy references, and open
  decisions/risks.
- `digest.md` — every MUST/NEVER of the project's spec tree, one line each.
- `AgenticManifest.md` — the one list of the project's agentic mounts and
  their spec files, with each file's level (`pattern`, `standalone`, or
  `fills in`).

`DevTickets/` and the release scripts used to live here and moved to `.dev`
(`AgenticTwoLevels`, 2026-10-08): a ticket and a release script are part of
how the work gets done, not specifications. The rule for the two levels is
`DevSpec`'s `SpecTree.md`.
