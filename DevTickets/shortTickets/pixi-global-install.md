Owner, 2026-10-01: *"écris un shortTicket pixi global install. Introduis une analyse critique pro and con car il y a des risques d'appropriation et de bug en intégrant en plus qu'il semble s'agir d'une version alpha en cours de stabilisation"*

Context: the pipx/PyPI route prepared on `tmpPyPi` contradicts the shared rule in `DevSpecs.md` (*Python Environment and Package Management*: `uv` or `pixi` exclusively, one consistent choice per project). The candidate replacement is a Pixi-only user install, so the rule holds end to end:

    pixi global install --git https://github.com/flipoyo/ComplexGitSync.git
    cgitsync --help

Not decided. Nothing is to be built until the owner says so.

## What was actually tried (2026-10-01, scratch only, nothing changed in the repository)

- Pixi 0.65.0. `pixi global install --path .` on the repository as it is fails: "the pixi.toml does not describe a package".
- On a throwaway copy, adding a `[package]` section (backend `pixi-build-python`, run-dependencies `python >=3.11`, `tomli-w`, `git`) **and** `preview = ["pixi-build"]` made it work: `cgitsync --version` gave 3.9.2, and a real `bootstrap` + `status` outside the repository, offline, gave `ready=true errors=0`, on Pixi's own Python, not the system one.
- Not tried: the `--git` URL route (needs the change pushed), macOS/Windows, upgrading an installed copy, the real `pixi.toml` (which also carries the editable `pypi-dependencies` the contributor workflow relies on).

## For

- **One rule, everywhere.** Contributors and users both go through Pixi; no `pipx`, no `pip`, no exception to argue about in DevSpecs.
- **No publication infrastructure.** No PyPI account, no name to claim, no trusted publisher, no token, no release workflow. Installing from the Git URL needs only the repository the project already has.
- **Its own Python.** Pixi brings the interpreter; the user's system Python is never touched, and `git` can be declared as a dependency instead of assumed.
- **Small change.** About fifteen lines in `pixi.toml`, plus README and a CI check. The tested parts of `tmpPyPi` that do not depend on PyPI (`CHANGELOG.md`, the `bootstrap` hint without `pixi run`, the clean source archive) can be kept.

## Against — the risks the owner named

- **Preview feature: it can change under us.** `pixi-build` must be switched on with `preview = [...]`; Pixi is pre-1.0 and preview features are explicitly allowed to change. A manifest that works today may need rewriting at a later Pixi release, and a user's `pixi global install` may break with no change on our side. **Mitigation:** pin the build backend version instead of `"*"`, state the minimum Pixi version in the README, and have CI run the install with a pinned Pixi so a break is caught by us before a user hits it.
- **Bugs where we have no control.** A failure in the build backend or in `pixi global` lands on a user as "cgitsync does not install", and the fix is upstream, not here. **Mitigation:** keep the clone + `pixi run cgitsync` route documented as the fallback that always works.
- **Appropriation cost for the owner.** One more Pixi concept to own (a workspace that is also a package, a build backend, the `global` environments), on top of the workflow already mastered. **Mitigation:** do it only when there is time to read the result; no change to the contributor commands (`pixi install`, `pixi run test`, `pixi run cgitsync`) is acceptable.
- **Two descriptions of one package.** `pyproject.toml` stays authoritative for the Python package, and `[package]` in `pixi.toml` would repeat the name, version and dependencies. **Mitigation:** `bump-version` must write `[package].version` too, and a test must fail when the two dependency lists disagree.
- **Unknown interaction with the dev setup.** Whether `[package]` coexists cleanly with `complexgitsync = { path = ".", editable = true }` in the same `pixi.toml` is untested; breaking `pixi install` for contributors would cost far more than the user route gains.
- **Users still need Pixi.** One binary to install, not a Python environment, but it is still a prerequisite that `pipx install` from PyPI would not have.
- **Platforms.** Only Linux was tried. Claim nothing else until tested.

## Suggested next step, when the owner chooses

1. Owner decides: Pixi global (this ticket), keep `tmpPyPi` (pipx/PyPI), or neither (clone + `pixi run` stays the only route).
2. If Pixi global: a `main` planning ticket replacing `tmpPyPi_1-1_pending-UserInstallPath`, whose first work package is the coexistence test with the real `pixi.toml`, and which ships nothing to users until the `--git` route is proven in CI.
3. Separately, and whatever is chosen: reconcile the memory branch `ComplexGitSync_tmpPyPi`, which is why `cgitsync verify` reports `corrupt` today.
