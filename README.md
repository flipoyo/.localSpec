# .localSpec

Per-project deeper specs, agent roster, and audit findings — the
project-specific half of the `.agentSpec`/`.localSpec`/`claude` split (see
`.agentSpec`'s `DevSpecs.md`, *Planning* section).

This `main` branch carries nothing project-specific; it exists only so a
project's `fallback_branch = "main"` resolves before that project's own
branch exists. Each consuming project gets its own branch here, named after
the project, holding:

- `AdditionalSpecs.md` — that project's architecture and technical rules.
- `AGENT.md` — that project's filled-in instance of `.agentSpec`'s generic
  `AGENT.md` template.
- `audit.md` — that project's audit findings, legacy references, and open
  decisions/risks.
- `DevTickets/` — that project's whole planning surface: the owner's short
  tickets, the ranked open planning tickets, and the archive of closed
  ones. It is here rather than in the project's own repository because how
  the work is decided is private; `DevTickets/README.md` explains the loop,
  and `.agentSpec/TICKETLIFECYCLE.md` the naming.
- `scripts/` — release tooling specific to that project (e.g.
  ComplexGitSync's own `bump_version.py`), kept out of the project's public
  repository so a checkout of it alone cannot cut a release. Each target
  path it touches is project-specific, which is also why it lives here
  rather than in the shared `.agentSpec/DevSpec` — see ProjectSpecSplit,
  archived in that project's `DevTickets/`.
