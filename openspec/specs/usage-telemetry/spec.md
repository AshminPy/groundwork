# usage-telemetry Specification

## Purpose
Captures lightweight, privacy-safe usage metadata for every substantive Groundwork task — visible to the user as a small block and recorded as one structured JSONL event — so playbook usage, execution mode, tool usage, clarification, outcome and validation can be reported later, without changing how tasks are executed.

## Requirements

### Requirement: Harness metadata block
Substantive Groundwork task responses SHALL end with a `Harness metadata` block containing only known values (harness, profile, playbook, execution, agents, evidence, validation, environment when known), SHALL mark unknown values as unknown rather than inventing them, and SHALL omit the block for trivial conversational replies.

#### Scenario: Substantive task
- **WHEN** a response used a playbook
- **THEN** it ends with the block and the `Validation` value matches the evidence shown in the response

#### Scenario: Trivial reply
- **WHEN** no playbook was used
- **THEN** no block is printed

### Requirement: One structured event per task
A Stop hook SHALL append one JSON line per response that contains the block to `~/.claude/groundwork/telemetry/events.jsonl`, with timestamp, session and prompt ids, harness name and version, profile, playbook, execution mode (`single_agent` | `subagents` | `agent_team`), agent count and roles, tools and MCP servers used in the current turn, evidence source types, clarification flag, environment, outcome (`complete` | `partial` | `blocked` | `failed` | `unknown`), validation (`verified` | `partial` | `not_verified` | `unknown`), tests-run flag, implementation and deployment flags, files-changed count, and a short hash of the working directory.

#### Scenario: Record contents
- **WHEN** a response with the block is finished after a turn that edited two files, ran a test command, called one MCP server and two agents
- **THEN** the record has `files_changed: 2`, `tests_run: true`, the MCP server name, two agents, and the playbook/execution/validation values from the block

#### Scenario: Current turn only
- **WHEN** an earlier turn in the same session ran a deploy command
- **THEN** the record for the current turn does not report `deployment_performed: true`

### Requirement: Privacy limits
The record SHALL NOT contain prompt text, command text, file paths, credentials, tokens, secrets, full logs, or reasoning; the working directory SHALL be stored only as a hash.

#### Scenario: Secret in a command
- **WHEN** a Bash command in the turn contained a token
- **THEN** neither the token nor the command appears in the record

### Requirement: Fail-open, never blocking
The hook SHALL always exit 0 with no output; malformed input, an unreadable transcript, an unwritable path or any exception SHALL leave the task unaffected; `GROUNDWORK_TELEMETRY=off` SHALL disable recording.

#### Scenario: Unwritable path
- **WHEN** the telemetry path cannot be created
- **THEN** the hook exits 0 silently and the task completes normally

### Requirement: Install and uninstall
The installer SHALL register the hook idempotently and write `~/.claude/groundwork/VERSION`; uninstall SHALL remove the hook and VERSION but keep existing telemetry records.

#### Scenario: Round trip
- **WHEN** install runs twice then uninstall
- **THEN** exactly one telemetry hook entry existed, and the records file survives the uninstall

### Requirement: Record layout separates observed from declared
Each record SHALL contain an `observed` object (facts the hook determined from the transcript and environment: profile, tools, MCP servers, agent calls and types, files changed, tests run, implementation and deployment flags) and a `declared` object (fields taken from the model's response: playbook, execution mode, agent count and roles, evidence sources, validation, environment, outcome, clarification flag). Declared fields SHALL be recorded as stated, never presented as verified.

#### Scenario: profile comes from the environment
- **WHEN** `GROUNDWORK_PROFILE=work` is set and the response block states a different profile
- **THEN** `observed.profile` is `work`

### Requirement: Outcome from status language
`declared.outcome` SHALL be derived from the response's own status language — an `Overall:` line, the Status / Result sentence (state word first: complete, partial, blocked, failed, or a playbook status word), a bold verdict opener, or the result heading of a non-status playbook — with precedence failed > blocked > partial > complete, and SHALL be `unknown` when nothing recognisable is present.

#### Scenario: ambiguous status stays unknown
- **WHEN** the Status paragraph is "I looked at the code and the tests."
- **THEN** `declared.outcome` is `unknown`

### Requirement: Agent facts reconciled with observed calls
`declared.agent_count`, `declared.execution_mode` and `declared.agent_roles` SHALL be reconciled against the Agent calls observed in the current turn: when calls were observed, the count is the observed number, the mode is at least `subagents`, and declared roles are kept only when their number matches; when no calls were observed and the block declares a single agent, the count is 0 with no roles; when nothing could be observed (unreadable transcript) the declared values are kept as stated.

#### Scenario: declared count disagrees with observed calls
- **WHEN** the block says `2 subagents` and lists two roles but one Agent call was observed
- **THEN** `declared.agent_count` is 1 and `declared.agent_roles` is the observed agent type
