## Why

Groundwork has no record of how it is used: which playbooks run, whether tasks use one agent, subagents or a team, which tools and MCP servers are touched, and where tasks stall as blocked or unverified. Without that, deciding which playbook needs improvement is guesswork. Groundwork also has no audit log of its own today (three hooks, none of which write anything), so there is nothing to reuse — the smallest compatible mechanism is a fourth fail-open hook in the existing Stop-hook pattern.

## What Changes

- **User-visible `Harness metadata` block** at the end of substantive task responses (output-contract.md): harness, profile, playbook, execution mode, agents, evidence types, validation — only values actually known; omitted for trivial replies.
- **New Stop hook `hooks/groundwork_telemetry.py`**: when the finished response contains that block, append one JSON line to `~/.claude/groundwork/telemetry/events.jsonl` with identifiers and aggregates from the block, the current transcript turn, and the outcome. No prompt text, commands, paths, secrets or reasoning. Never blocks; failure is silent.
- Installer registers the hook, writes `~/.claude/groundwork/VERSION`; uninstall removes the hook but keeps the records. Snapshot shows version and profile so the block can be filled honestly.

Unchanged: routing, playbooks, evidence and validation rules, the other three hooks, safety controls.

## Capabilities

### New Capabilities
- `usage-telemetry`: the metadata block, the telemetry record schema, privacy limits, and fail-open behaviour.

## Impact

One more Stop hook (~150 ms), one more short section in the shared contract, one `VERSION` file. Records accumulate at roughly 500 bytes per task.
