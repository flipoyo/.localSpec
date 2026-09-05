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
