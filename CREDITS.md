# Credits and attribution

Groundwork is a thin governance layer, not a fork. This page states plainly what is original to this repository and what is not, so nobody mistakes one for the other.

## What Groundwork installs from elsewhere (not modified, not redistributed here)

| Project | What it is | License | Source |
|---|---|---|---|
| **ECC** | Agent harness plugin for Claude Code — agents, skills, hooks, session persistence, GateGuard, continuous learning. Author: Affaan Mustafa. | MIT | https://github.com/affaan-m/ECC |
| **OpenSpec** | Spec-driven development CLI — proposal/spec/design/tasks lifecycle. Author/org: Fission AI. | MIT | https://github.com/Fission-AI/OpenSpec |

`install.sh` installs both from their own official channels (the Claude Code plugin marketplace for ECC, the official npm package for OpenSpec). Groundwork does not vendor, copy, or modify either project's source. Bugs in ECC or OpenSpec belong upstream, not here — please report them to those repositories, not this one.

## What is original to Groundwork

Everything under `rules/`, `hooks/`, `scripts/`, `tests/`, and this documentation was written for this repository:

- `rules/engineering-workflow.md` — the tiering system, the autonomy rule, the completion status block
- `rules/evidence-policy.md` — evidence priority, the decision format, the uncertainty labels
- `hooks/require_material_review.py` — the deterministic independent-review gate
- `hooks/block_protected_push.py` — the protected-branch/force-push guard
- `scripts/merge_settings.py`, `scripts/unmerge_settings.py`, `install.sh`, `uninstall.sh`
- All of `docs/`

© Ashmin ([@AshminPy](https://github.com/AshminPy)), MIT licensed — see [LICENSE](LICENSE).

## Development history

Groundwork's rules and hooks were developed and validated through an actual migration of a personal Claude Code harness from a large custom system (22 hooks, 39 skills, ~200KB of enforcement scripts) onto ECC + OpenSpec. The gaps Groundwork fixes — non-deterministic review, an unnecessary approval stop, unproven completion claims — were found by testing the plain ECC + OpenSpec combination against a battery of controlled scenarios, documented honestly including the first attempts that didn't work. See [docs/VALIDATION.md](docs/VALIDATION.md).

## Naming

"Groundwork" was chosen to name this repository's own contribution specifically — the evidence-grounded rules and gates — not as a name for ECC, OpenSpec, or Claude Code themselves. If you're citing this project, cite it as "Groundwork (built on ECC and OpenSpec)", not as a component of either upstream project.
