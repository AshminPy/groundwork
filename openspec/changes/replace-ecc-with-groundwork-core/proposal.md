## Why

ECC (github.com/affaan-m/ECC, plugin `ecc@ecc`, pinned v2.2.1) is installed by Groundwork in full, but almost none of it is used, and the parts that run on every tool call cost real time and tokens:

- **Tokens:** ECC's 68 agent descriptions and 369 skill names add about 6.5k input tokens to every request (`claude -p /context`, 2026-10-27). Across every transcript kept on this Mac (since 22 Aug 2026), only 5 ECC agents and 3 ECC skills were used.
- **Speed:** ECC's `pre:mcp-health-check` hook runs on every tool call and loads Node's `https` module at start. With `NODE_USE_SYSTEM_CA=1` that load takes about 7.5 s on this Mac. This explains the measured ECC PreToolUse p90 of 7.5 s; Groundwork's own hooks take about 0.16 s.
- **Friction:** ECC's fact-forcing gate denies the first edit of every file and the first shell command of every session. It denied 121 tool calls in this planning session's transcript, for re-statements that changed nothing.
- **Hidden behaviour:** ECC hooks start `claude -p --model haiku` on PreCompact and on some Stops, log every shell command to `~/.claude/bash-commands.log` and `cost-tracker.log` (9 MB together), and record 25 MB of tool observations that produced 0 learned rules.

A few ECC parts do protect quality or safety and are not covered by Groundwork. They must be rebuilt before ECC goes, so that nothing valuable is lost silently.

This reverses Groundwork 2.0 decision D4 (`openspec/changes/groundwork-2-enterprise-sre/specs/ecc-capability-policy/spec.md`: install ECC in full, never copy ECC content). That decision rested on there being no way to install part of ECC; it did not weigh the cost measured here.

## What Changes

- **Rebuild in Groundwork (Python, no Node):**
  - A block on bypassing git hooks (`--no-verify`, `commit -n`, `-c core.hooksPath=`), from ECC `block-no-verify`. This is the only ECC hook that stops something no other control stops.
  - A prompt before editing an existing linter or formatter config, from ECC `config-protection`, so Claude does not quietly weaken a check to make it pass.
  - A Groundwork-owned reviewer agent, built from ECC `code-reviewer` (used 88 times), with Python and security sections merged in. It ends with Groundwork's `REVIEW RESULT` block, and its name contains "review" so the review gate counts it.
  - Token totals per turn (main thread and subagents) in Groundwork telemetry, which replaces ECC `cost-tracker`.
- **Remove:**
  - **BREAKING:** `install.sh` no longer installs ECC. On existing installs, a one-time migration takes a full config-dir backup first, then uninstalls `ecc@ecc` and removes its marketplace and settings keys. `./setup.sh --rollback` restores everything offline.
  - All other ECC hooks, agents, skills, commands and its `chrome-devtools` MCP server. Each one's fate is listed with evidence in design.md.
  - References to `ecc:*` agents and `/ecc:*` commands in Groundwork rules, the review gate's guidance text, `setup.sh --doctor`, tests and docs.
- **Not deleted automatically:** ECC's data outside the plugin (session files, command logs, the 25 MB observation store). Removal prints the paths and one command to delete them. The command log holds shell history, so deleting it is the owner's call.
- **Attribution:** copied ECC text keeps ECC's MIT notice (`THIRD_PARTY_NOTICES.md`, `CREDITS.md`).

## Capabilities

### New Capabilities
- `ecc-independence`: Groundwork installs, runs and checks its health without ECC. It migrates existing installs off ECC safely and can roll back.
- `git-integrity-guards`: shell commands that bypass git hooks are blocked, and edits to existing linter or formatter configs ask first.
- `code-review-agent`: Groundwork ships its own code reviewer agent whose verdict the MATERIAL review gate reads.

### Modified Capabilities
- `usage-telemetry`: adds per-turn token totals (input, output, cache read, cache write, requests) for the main thread and subagents, read from the transcripts at Stop, to replace ECC's cost tracker.

## Impact

- **Code:**
  - `install.sh`, `setup.sh`, `uninstall.sh`
  - `scripts/merge_settings.py`, `scripts/unmerge_settings.py`
  - `hooks/block_protected_push.py` (no-verify block) and `hooks/groundwork_task_gate.py` (config-protection ask)
  - new `scripts/migrate_off_ecc.py` and `scripts/backup.sh`; `scripts/groundwork_report.py` (token section)
  - a new `agents/` folder in the repo, installed to the config dir
  - `hooks/require_material_review.py` (guidance text only)
  - `hooks/groundwork_telemetry.py`
  - `rules/engineering-workflow.md`
- **Tests:** `tests/test_setup.py` (ECC rows), new tests for the guards, the agent install and token telemetry.
- **Docs:** `README.md`, `docs/ARCHITECTURE.md`, `docs/TROUBLESHOOTING.md`, `docs/UPGRADE-ROLLBACK.md`, `CREDITS.md`, `CHANGELOG.md`.
- **Dependencies:** removes the ECC plugin and the `affaan-m/ECC` marketplace. Node stays required for OpenSpec.
- **User-visible:** about 6.5k fewer input tokens per request; no 7.5 s hook wait; no fact-forcing denials; `/ecc:*` commands disappear.
