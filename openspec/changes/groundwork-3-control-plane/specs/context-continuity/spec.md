# Spec Delta

## Purpose

Makes sure no agent, compaction or new session loses the facts of a run, by moving context through files instead of through the conversation.

## ADDED Requirements

### Requirement: Agents start with a context packet
When a Groundwork agent starts on a task, it SHALL receive a packet built from the run files. The packet SHALL hold the run id, task revision, tier, stage, task and acceptance criteria, owned paths, linked decision ids, open review items, the path of the previous handoff, and its turn budget. It SHALL contain paths and ids only, never copies of file contents.

#### Scenario: Builder packet
- **WHEN** builder-kubernetes starts on task T4
- **THEN** its first context holds T4's criteria, owned paths, linked decision ids and the previous handoff path

### Requirement: Agents return a structured handoff
Each agent that works on a task SHALL end by writing a handoff file, with the Write tool, holding the sections Done, Changed files, Evidence, Decisions, Open questions and Next. Decisions in the handoff SHALL be recorded by the stop hook, so agents without Bash can hand off. It SHALL NOT be accepted as finished if a section is missing, an evidence path doesn't exist, or a decision id isn't recorded.

#### Scenario: Handoff cites missing evidence
- **WHEN** a builder's handoff lists an evidence file that doesn't exist
- **THEN** the builder is told to continue, with that reason

### Requirement: Stop checks cannot loop forever
A stop check SHALL NOT block the same agent or session more than twice in a row. On the third attempt, the task SHALL be marked blocked with the reason, and the stop SHALL be allowed. The count SHALL be kept in a file, not in conversation state.

#### Scenario: Agent keeps failing its handoff
- **WHEN** the same agent fails the handoff check a third time
- **THEN** its task is marked blocked, and the agent is allowed to stop

### Requirement: Compaction does not lose run facts
Before compaction, a brief SHALL be written from the run files and the project memory file. The brief SHALL hold the goal, tier, stage, open tasks, recent decisions, open review items and standing owner preferences. After compaction, it SHALL be added back to context. Writing the brief SHALL never block compaction.

#### Scenario: Resume after compaction
- **WHEN** the conversation is compacted during a T3 run
- **THEN** the next turn's context includes the brief and the current task counts

### Requirement: Owner preferences persist in a project memory file
Standing preferences the owner states, such as "always use workspace prd for X", SHALL be recorded in a project memory file through `gw remember`. The brief and every agent packet SHALL link to that file.

#### Scenario: Preference survives a new session
- **WHEN** the owner records a preference and later starts a new session
- **THEN** the new session's start context includes the memory file

### Requirement: A new session on the same machine can resume a run
At session start, Groundwork SHALL list the open runs of the current project and offer to resume one. This SHALL work from the run folders when the shared session index is not available.

#### Scenario: Mod not loaded
- **WHEN** a new session starts without the console mod
- **THEN** the open runs are still listed from the run folders

### Requirement: Runs can move between machines
`gw handoff export` SHALL write a bundle into the change's OpenSpec folder, built only from allow-listed fields: plan references, task ids and statuses, decision fields and handoff summaries. `gw handoff load` SHALL rebuild the run state from it on another machine.

#### Scenario: Cloud to Mac
- **WHEN** a run is exported in a cloud session and loaded on the owner's Mac
- **THEN** the Mac session shows the same task statuses and decisions

### Requirement: Exports refuse possible secrets
An export SHALL NOT include evidence files or any field outside the allow list. Every exported field SHALL pass a check against known secret patterns and an entropy check. On any match, the export SHALL be refused and the match shown to the owner, not silently redacted.

#### Scenario: Token-like string in a summary
- **WHEN** a handoff summary contains a string that matches a token pattern
- **THEN** the export is refused, and the owner is shown the field and the pattern

### Requirement: Work and personal context stay apart
Runs, indexes, memory files and exports under one profile SHALL NOT be listed or loaded by sessions using the other profile.

#### Scenario: Personal session lists runs
- **WHEN** a personal-profile session lists open runs
- **THEN** no work-profile run is shown
