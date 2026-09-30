# Proposal

## Why

Groundwork documents external-system integrations (`docs/INTEGRATIONS.md`) as a static research table only — there is no way for a user or a Claude session to ask "what integrations does Groundwork know about, and what state are they actually in right now?" The only live check that exists today is narrow and buried inside the Routines subsystem (`groundwork_routines.py`'s `check_access()`, used only by `jira_eod`/`pr_followup`), and it conflates "the MCP server is listed" with "it's connected" in its own doctor output. Users setting up a new capability profile have no single place to see, per integration: what mechanism to use, whether it's configured, and whether it actually works — grounded investigation (this session, 2026-09-30) confirmed no such catalog exists and that a competing approach (installing `anaisbetts/mcp-installer` to manage MCP servers) is unsafe (Claude-Desktop-only, no uninstall, plaintext secrets, unsandboxed arbitrary code execution) and was rejected.

## What Changes

- Add a structured, code-defined Integration Catalog (not a Markdown-parsed one) covering the integrations already researched in `docs/INTEGRATIONS.md`, each with: capabilities (dotted ids like `kubernetes.logs.read`), one or more approved access mechanisms (typed `mcp` | `cli` | `api`), trust/access characteristics, and configuration requirements.
- Add truthful, **independent** readiness observations per integration — `available` / `configured` / `connected` (booleans; any combination is valid, e.g. configured-but-not-available) — plus a separate task/session observation, `used` (`true` / `false` / `unknown`, read from existing telemetry, never guessed). `connected` is only ever set true after a real, successful reachability/auth check; presence alone never sets it true. For display, `list`/`show` derive one concise summary label (`CONNECTED` > `CONFIGURED` > `AVAILABLE` > `NOT CONFIGURED`) from the readiness booleans — a display convenience, not a stored state, and `used` is never folded into it.
- Add non-mutating, timeout-bounded, credential-free probes (same spirit as `groundwork_routines.py`'s `check_access()`, implemented fresh — `hooks/` and `scripts/` ship to different directories post-install, so cross-importing between them is unsafe).
- Add `scripts/groundwork_integrations.py` (mirrors `groundwork_config.py`/`groundwork_routines.py`'s existing CLI shape): `list` (table of integration/access/state) and `show <name>` (purpose, capabilities, approved mechanisms, trust characteristics, configuration requirements, current state, and which Routines explicitly depend on it — derived deterministically from Routines' own config, never guessed for playbooks).
- Wire the script into `install.sh` (installed alongside the existing three scripts) and into `setup.sh --doctor` (a new section, same pattern as the existing Routines doctor section).
- Add a deterministic test that keeps `docs/INTEGRATIONS.md`'s domain list consistent with the structured catalog's integration names, so they cannot silently drift apart, without any runtime Markdown parser.
- Document the explicit architecture decision that Groundwork does **not** implement custom dynamic MCP tool-loading/activation — Claude Code's native Tool Search already does context-efficient, lazy tool-schema discovery; Groundwork provides capability/integration *guidance* only, and never claims to enforce per-task MCP activation.

Explicitly **not** in this change: any MCP installer/marketplace/package manager, statusLine/terminal UX (a separate future change consumes this catalog's state), any state beyond the 4 listed above, and any credential storage or handling.

## Capabilities

### New Capabilities
- `integration-catalog`: A structured, code-defined catalog of Groundwork-known external-system integrations, their capabilities, approved access mechanisms, and a truthfully-observed readiness state, exposed via a CLI (`list`/`show`) and folded into `setup.sh --doctor`.

### Modified Capabilities
(none — this is a new, additive capability; it does not change the documented behavior of Routines, task-routing, telemetry, or the health dashboard)

## Impact

- **New files:** `scripts/groundwork_integrations.py`, `tests/test_groundwork_integrations.py`.
- **Modified files:** `install.sh` (install the new script), `setup.sh` (new `--doctor` section), `docs/INTEGRATIONS.md` (add capability-id/approved-mechanism columns + a short section on the new command), `docs/ARCHITECTURE.md` (short note on the Tool Search / no-custom-loading decision), `README.md` (repository-layout entry), `CHANGELOG.md` (entry).
- **Dependencies:** none new — stdlib Python only, matching every other Groundwork script.
- **Security surface:** read-only probes (subprocess version/status checks, `claude mcp list`/`gh auth status`-style presence checks) — no installation, no credential handling, no mutation of Claude Code's own config.
