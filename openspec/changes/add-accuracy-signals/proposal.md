## Why

The health dashboard cannot answer whether Groundwork's answers are accurate. Its only accuracy signals are what the
model declares about itself (outcome, validation) and a broad "a test-shaped command was seen" match that ignores the
result. The owner asked for every high-value accuracy signal to be collected and calculated accurately, so the
dashboard can answer the performance-gap questions: does Groundwork claim more than it proved, do tests end green,
is MATERIAL work reviewed before it ships, do users have to correct finished work, do citations resolve, does pushed
work pass CI, where do guardrails step in, what a completed turn costs, and whether quality changes after compaction
or between versions.

## What Changes

- **Collection** (`hooks/groundwork_telemetry.py`, documented hook fields only, no prompt, command or reply text
  stored):
  - Bash tool rows gain `kind` (`test`, `check`, `deploy`, `runtime_read`), `result` (`pass`, `fail`, `unknown`)
    and `git_commit`; every tool row gains `prompt_id` and `tool_use_id`.
  - New `signals.jsonl`: `review` (completed reviewer Agent calls and `SubagentStop`), `prompt` (correction flag),
    `compact` (`PostCompact`) and `guardrail` records.
  - The per-turn Stop record gains `citations`, `ctx_pct`, `cost_usd` and, on commit turns, `head` and `repo`.
- **Guardrail records** from the push guard, task gate, review gate and reply check (hook, decision, cause, ids).
- **Registration**: the telemetry hook moves from 3 to 6 events (`TELEMETRY_EVENTS`): 18 hook entries in all.
- **Report** (`scripts/groundwork_report.py`): a Performance gaps section answers questions 1a to 11 of the design,
  each with its definition, count, labels and the "insufficient data" rule; opt-in `generate --github` checks CI
  read-only. The "Verified outcome" card is renamed to say what it is: a broad match.
- **Test hygiene**: the suite isolates `signals.jsonl` so test runs never write the real telemetry folder.
- **Removed by the owner** (2026-10-28): the re-edit metric and file hashing.

## Capabilities

### Modified Capabilities
- `usage-telemetry`: privacy limits, install counts and the per-tool-call record change; event-shaped signals,
  per-turn accuracy facts and guardrail records are added.
- `health-dashboard`: the dashboard and honest-metrics rules change; the Performance gaps section and opt-in CI truth
  are added.

## Impact

- Code: `hooks/groundwork_telemetry.py`, `hooks/groundwork_shared.py`, the four guard hooks,
  `scripts/groundwork_report.py`, `scripts/merge_settings.py`, `scripts/unmerge_settings.py`, `uninstall.sh`.
- Data: additive fields; `signals.jsonl` is new. Older readers ignore both.
- Latency: one short hook process on three more events (measured 55-72 ms median).
- Network: none, except the opt-in `--github` flag.
