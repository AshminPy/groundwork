## Purpose
Captures lightweight, privacy-safe usage metadata for every substantive Groundwork task — visible to the user as a small block and recorded as one structured JSONL event — so playbook usage, execution mode, tool usage, clarification, outcome and validation can be reported later, without changing how tasks are executed.

## ADDED Requirements

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
