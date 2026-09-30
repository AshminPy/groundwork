# Proposal

## Why

Groundwork today has no terminal/statusLine presence at all — its state (active capability profile, last playbook, Integration Catalog readiness, validation outcome) is only visible by running separate CLI commands (`groundwork_config.py show`, `groundwork_integrations.py list`, `setup.sh --doctor`) or reading chat prose. An investigation this session (accepted by the user, with one binding architecture adjustment before implementation) established: Claude Code's native `statusLine` feature is fully documented (exact stdin JSON schema, 10 refresh triggers, 300ms debounce, in-flight-script-cancelled-not-queued behavior, no hard timeout but an explicit "keep scripts fast" recommendation); several fields Groundwork would want to show (playbook, execution mode, validation, Integration Catalog readiness) have no live signal and are only available as last-completed-turn telemetry or a cached probe result; and the Integration Catalog's own probes (`claude mcp list` up to 15s, `gh auth status` up to 10s) are categorically unsafe to run inside a statusLine process, which Claude Code cancels rather than queues on the next refresh trigger.

## What Changes

- Add `scripts/groundwork_statusline.py`: a Claude Code `statusLine` command that renders a compact, truthful, single/few-line Groundwork status from: the stdin JSON Claude Code supplies (model, context %, cost, workspace/repo identity), Groundwork's own `config.json` (capability profile), a session-`session_id`-filtered tail of the existing telemetry (`events.jsonl`) for last-completed-turn playbook/execution-mode/validation, a pre-computed Integration Catalog readiness cache (never a live probe), and one short-timeout `git` subprocess call for live branch/dirty state.
- Add an explicit `refresh` subcommand to `scripts/groundwork_integrations.py` that computes the same observations `list` does and atomically persists them, each with its own `checked_at` timestamp, to a new `~/.claude/groundwork/integrations/cache.json`. No cron/launchd/daemon is introduced — the cache is refreshed only at existing lifecycle points: after `install.sh` (best-effort), after `setup.sh`'s capability configurator writes `config.json`, and every time `setup.sh --doctor` already runs (its existing Integrations section now writes the cache as a byproduct of the same live probe it already performs).
- Add a small, standalone personalization file, `~/.claude/groundwork/statusline-config.json` (compact/detailed, per-section show/hide, plain-text-vs-Unicode-symbol fallback) — deliberately **not** inside `config.json`, because `groundwork_config.py init --force` (run on every `setup.sh --configure`) unconditionally rewrites `config.json` from a fixed-shape `default_config()` template and would silently discard any other key placed there.
- Wire `statusLine` into `settings.json` via `scripts/merge_settings.py` (a new merge rule, additive and non-clobbering: set only if the key is absent, exactly like the existing env-default rules — a user's own custom `statusLine` is never overwritten).
- Install the new script via `install.sh`, matching the existing script-install pattern.

Explicitly **not** in this change: any background/scheduled process for cache refresh; a review/MUST-FIX-state field (no durable source exists); a role/persona field (prompt-only convention, no data source); evidence-label counts (never parsed or stored anywhere); live Integration Catalog probing from inside the statusLine process; any Integration Usage Telemetry / per-invocation dashboard (investigated and found NOT reliably supported by current telemetry — see design.md; a separate future change after a `PostToolUse`-capture investigation); a theme engine, custom shell prompt framework, startup banner, Nerd Font dependency, animation, or plugin architecture.

## Capabilities

### New Capabilities
- `groundwork-statusline`: A Claude Code `statusLine` integration rendering Groundwork-specific state, with an explicit, documented LIVE / LAST-COMPLETED-TURN / CACHED / UNAVAILABLE data-source contract, correct session isolation, and a lifecycle-driven (not scheduled) Integration Catalog cache.

### Modified Capabilities
- `integration-catalog`: adds a `refresh` subcommand and a persisted cache file; the existing `list`/`show` commands and their live-probe semantics are unchanged.

## Impact

- **New files:** `scripts/groundwork_statusline.py`, `tests/test_groundwork_statusline.py`.
- **Modified files:** `scripts/groundwork_integrations.py` (new `refresh` subcommand + cache writer), `install.sh` (install the new script; call `refresh` once, best-effort), `setup.sh` (call `refresh` after capability configuration; the two existing `--doctor` Integrations sections call `refresh` instead of `list` so doctor's existing live probe also persists to the cache), `scripts/merge_settings.py` (additive `statusLine` key), `docs/ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`.
- **Dependencies:** none new — stdlib Python only, matching every other Groundwork script.
- **Security surface:** the statusLine process itself performs no subprocess calls except one short-timeout `git` read; it never runs `claude mcp list`, `gh auth status`, or any network/cloud-CLI call. Cache/config files are read-only from the statusLine's perspective, written only by `groundwork_integrations.py refresh` and (for personalization) hand-edited or defaulted.
