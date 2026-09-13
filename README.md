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
