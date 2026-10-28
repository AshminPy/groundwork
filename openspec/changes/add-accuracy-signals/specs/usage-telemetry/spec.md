## MODIFIED Requirements

### Requirement: Privacy limits
The record SHALL NOT contain prompt text, command text, file paths, credentials, tokens, secrets, full logs, or reasoning; the working directory SHALL be stored only as a hash. Accuracy signals SHALL store only enums, booleans, counts, ids that match `[\w.:-]{1,100}`, a commit SHA and a GitHub `owner/repo`; prompt, command, error and reply text SHALL be read in memory only.

#### Scenario: Secret in a command
- **WHEN** a Bash command in the turn contained a token
- **THEN** neither the token nor the command appears in the record

#### Scenario: Credentials in the remote URL
- **WHEN** a commit turn's `origin` is `https://user:token@github.com/owner/repo.git`
- **THEN** only `owner/repo` is stored

### Requirement: Install and uninstall
The installer SHALL register the hook idempotently and write `~/.claude/groundwork/VERSION`; uninstall SHALL remove the hook and VERSION but keep existing telemetry records.

#### Scenario: Round trip
- **WHEN** install runs twice then uninstall
- **THEN** exactly six telemetry hook entries existed (one each on Stop, PostToolUse, PostToolUseFailure, SubagentStop, UserPromptSubmit and PostCompact, all the same script), 18 hook entries in all, and the records files survive the uninstall

### Requirement: Per-tool-call record
In addition to the per-turn record, a PostToolUse/PostToolUseFailure hook SHALL append one JSON line per tool call to `~/.claude/groundwork/telemetry/tool_events.jsonl` containing: timestamp, session id, prompt id, tool call id, the tool name, a category (`builtin` or `mcp`, with the server slug when `mcp`), and success/failure, plus `interrupted: true` when a PostToolUseFailure carries `is_interrupt: true`. For Bash only it SHALL read the command and the first line of `error` in memory to store `kind`, `result` and `git_commit` (design D5); command and output text SHALL never be stored. It SHALL share the per-turn record's permission model (0600 file, 0700 directory), fail-open behaviour, and `GROUNDWORK_TELEMETRY=off` switch, with its own path override `GROUNDWORK_TOOL_TELEMETRY_PATH`.

#### Scenario: A tool call succeeds
- **WHEN** a `PostToolUse` event fires for `mcp__github__search_repositories`
- **THEN** a record is appended with `category: "mcp"`, `mcp_server: "github"`, `success: true`, and no trace of the call's arguments or result

#### Scenario: A tool call fails
- **WHEN** a `PostToolUseFailure` event fires, with an error message containing a token or secret
- **THEN** a record is appended with `success: false` and the error text never appears anywhere in the file

#### Scenario: No tool name
- **WHEN** the event carries no `tool_name`
- **THEN** no record is appended

#### Scenario: A tool call is aborted
- **WHEN** a `PostToolUseFailure` event fires with `is_interrupt: true`
- **THEN** a record is appended with `success: false` and `interrupted: true`, and the report counts it separately and excludes it from the success-rate denominator instead of treating it as a tool failure

#### Scenario: A call never executes
- **WHEN** a tool call is denied by permissions or rejected before execution
- **THEN** Claude Code fires neither hook event, no record exists, and no report presents the row count as the number of calls attempted

#### Scenario: A running tool is cancelled
- **WHEN** a running tool is cancelled
- **THEN** Claude Code fires no PostToolUseFailure event for it, so no failure row exists

#### Scenario: A failing test
- **WHEN** `pytest -q` fails with `Exit code 1`
- **THEN** the row has `kind: "test"` and `result: "fail"`; with `| tail`, `;`, a background run or an interrupt the result is `unknown`

## ADDED Requirements

### Requirement: Event-shaped signals
The hook SHALL append to `~/.claude/groundwork/telemetry/signals.jsonl` (override `GROUNDWORK_SIGNALS_PATH`) a `review` record for each completed reviewer call, a `prompt` record with a `correction` flag for each `UserPromptSubmit`, and a `compact` record for each `PostCompact`.

#### Scenario: Review result
- **WHEN** a reviewer subagent ends with `REVIEW RESULT` / `Must-fix: 1`
- **THEN** a `review` signal with `must_fix: 1` and the agent id is written, with no reply text

#### Scenario: Correction prompt
- **WHEN** the user's prompt is "that didn't work"
- **THEN** a `prompt` signal with `correction: true` is written; "if it doesn't work, tell me" is not a correction

### Requirement: Signals file safety
The signals writer SHALL never follow a symlink, never block on a FIFO, and write only to a regular file with mode 0600 in a 0700 directory.

#### Scenario: Symlinked path
- **WHEN** the signals path is a symlink to another file
- **THEN** nothing is written to the link's target and the hook exits 0

### Requirement: Per-turn accuracy facts
The Stop record SHALL add `observed.citations` (`checked`, `resolved`, `unchecked`), `observed.ctx_pct` and `observed.cost_usd` from a fresh statusLine reading, and on a turn with a successful, unmasked `git commit` the `head` SHA and GitHub `owner/repo`.

#### Scenario: Citation outside the project
- **WHEN** a reply cites `db.example.com:5432` or a file reached through a symlink out of the project
- **THEN** it is counted as unchecked, never as unresolved

### Requirement: Guardrail decisions recorded
The push guard, task gate, review gate and reply check SHALL record each deny, ask or block with the hook, decision, cause (`policy` or `internal_error`) and ids, after printing the decision; a missing or broken recorder SHALL never change the decision.

#### Scenario: Recorder missing
- **WHEN** `groundwork_shared.py` is absent
- **THEN** the push guard still denies a push to `main` and exits 0
