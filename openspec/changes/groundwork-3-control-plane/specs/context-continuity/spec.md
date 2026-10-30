# Spec Delta

## Purpose

Makes sure no agent, compaction or new session loses the facts of a run, by moving context through files instead of through the conversation.

## ADDED Requirements

### Requirement: Agents start with a context packet
When a Groundwork agent starts, it SHALL receive a packet built from the run files. The packet holds the run id and revision, tier, stage, its task and acceptance criteria, the files it owns, linked decisions, open review items, the previous handoff summary, and its turn budget. The packet SHALL pass file paths and ids, not copies of file contents.

#### Scenario: Builder packet
- **WHEN** builder-kubernetes starts on task T4
- **THEN** its first context holds T4's criteria, owned paths, linked decision ids and the path of the previous handoff

### Requirement: Agents return a structured handoff
Each agent SHALL end by writing a handoff with the sections Done, Changed files, Evidence, Decisions, Open questions and Next. The agent SHALL NOT be accepted as finished if a section is missing, an evidence path does not exist, or a decision id is not recorded.

#### Scenario: Handoff cites missing evidence
- **WHEN** a builder's handoff lists `evidence/T4-lint.txt` and that file does not exist
- **THEN** the builder keeps working with that reason

#### Scenario: Second failure blocks the task
- **WHEN** the same agent fails the handoff check twice
- **THEN** its task is marked blocked with the reason

### Requirement: Compaction does not lose run facts
Before compaction, a brief SHALL be written from the run files: goal, tier, stage, open tasks, recent decisions and open review items. After compaction, the brief and the run status SHALL be added back to context. The brief SHALL be written without blocking compaction.

#### Scenario: Resume after compaction
- **WHEN** the conversation is compacted during a T3 run
- **THEN** the next turn's context includes the brief and the current task counts

### Requirement: A new session on the same machine can resume a run
At session start, Groundwork SHALL list the open runs of the current project and offer to resume one. It SHALL work from the run folders when the shared session index is not available.

#### Scenario: Mod not loaded
- **WHEN** a new session starts without the console mod
- **THEN** the open runs are still found from the run folders

### Requirement: Runs can move between machines
`gw handoff export` SHALL write a bundle with the plan, task status, decisions and handoff summaries into the change's OpenSpec folder, so it can be committed on the work branch. `gw handoff load` SHALL rebuild the run state from it on another machine.

#### Scenario: Cloud to Mac
- **WHEN** a run is exported in a cloud session and loaded on the owner's Mac
- **THEN** the Mac session shows the same task status and decisions

### Requirement: Exports never carry evidence or secrets
An export SHALL NOT include evidence files. All exported text SHALL pass a secret scan, and matches SHALL be redacted. If the scan cannot run, the export SHALL fail.

#### Scenario: Token in a handoff summary
- **WHEN** a handoff summary contains a string that matches a token pattern
- **THEN** the exported copy shows it redacted

### Requirement: Work and personal context stay apart
Runs, indexes and exports under the work profile SHALL NOT be readable from sessions using the personal profile, and the reverse.

#### Scenario: Personal session lists runs
- **WHEN** a personal-profile session lists open runs
- **THEN** no work-profile run is shown

### Requirement: Inter-session messages carry notices, not state
Messages between live sessions SHALL carry only run ids and short notices, such as started, done or blocked. Run state SHALL be read from files.

#### Scenario: Done notice
- **WHEN** a session finishes a task that another session is waiting on
- **THEN** the message names the run and task id, and the receiver reads the status from the run folder
