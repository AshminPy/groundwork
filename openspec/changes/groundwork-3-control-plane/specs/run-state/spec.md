# Spec Delta

## Purpose

Keeps the state of each run in project files that one script changes, so that agents, sessions and reports all read the same facts.

## ADDED Requirements

### Requirement: Each run has a run folder in the main checkout
Each T1-or-higher run SHALL get a folder `.groundwork/runs/<run-id>/` in the main checkout. The folder SHALL be found the same way from the main checkout and from every git worktree of it. `.groundwork/` SHALL be excluded from version control.

#### Scenario: Builder in a worktree
- **WHEN** a builder working in a git worktree runs `gw task list`
- **THEN** it reads the same run folder as the main session

#### Scenario: Run files are not committed
- **WHEN** the project's ignore rules are checked
- **THEN** `.groundwork/` is ignored

### Requirement: State files follow published formats
Run state SHALL be stored as JSON files whose formats are given in the design's data-formats section. Files the owner edits, such as the domain pack, MCP catalog and project settings, SHALL be TOML. Every state file SHALL carry a format version.

#### Scenario: Unknown format version
- **WHEN** `gw` reads a state file with a newer format version than it supports
- **THEN** it stops with a message naming the file and both versions

### Requirement: Only the state script changes run state
`run.json` and `tasks.json` SHALL be changed only through `gw`. The guard SHALL deny direct edits to them. Each run-log entry SHALL chain to the previous one and record the hash of both state files. `gw` SHALL check both on every read. A mismatch SHALL stop the run until the owner repairs it.

#### Scenario: Agent edits tasks.json directly
- **WHEN** an agent uses the edit tool on `tasks.json`
- **THEN** the edit is denied with a message to use `gw task`

#### Scenario: Write through a script
- **WHEN** a Bash command rewrites `tasks.json` without `gw`
- **THEN** the next `gw` read reports a state-hash mismatch and refuses to continue

### Requirement: A task has one owner
`gw task claim` SHALL refuse to claim a task that another agent holds and has not released. A claim SHALL record the claiming agent's id.

#### Scenario: Second claim is refused
- **WHEN** an agent claims T4, which another agent already holds
- **THEN** the claim fails and names the current owner

### Requirement: Done needs fresh evidence
`gw task done` SHALL refuse unless the task has at least one evidence record, and every hash in it still matches the files it covers. For T2 and higher, this SHALL include passing results from qa's tests.

#### Scenario: Done without evidence
- **WHEN** `gw task done T2` runs and T2 has no evidence record
- **THEN** the command fails and the task stays open

#### Scenario: Stale evidence
- **WHEN** a covered file changed after its evidence was recorded
- **THEN** the evidence is marked stale and `gw task done` fails until the check runs again

### Requirement: Concurrent writes are safe
`gw` SHALL take an exclusive lock for every write, and write through a temporary file that replaces the original atomically. Each task SHALL carry its own revision number. A write based on an older revision of that task SHALL be refused. Writes to different tasks SHALL NOT refuse each other.

#### Scenario: Two builders on different tasks
- **WHEN** builders on T3 and T4 mark their tasks done at the same moment
- **THEN** both writes succeed

#### Scenario: Stale write to the same task
- **WHEN** an agent writes T4 based on revision 3 after T4 moved to revision 4
- **THEN** the write is refused and nothing changes

### Requirement: The report is built from files
The run board, the status line and the final report SHALL be produced by `gw` from the run files. They SHALL list done, pending and blocked tasks with evidence paths, open review items, owner decisions, denials and next steps.

#### Scenario: Report matches the task file
- **WHEN** `gw run report` runs on a run with 4 done, 1 pending and 1 blocked task
- **THEN** the report shows those counts, and each done task shows its evidence path

### Requirement: The run log only grows
Every state change SHALL be appended to the run log with the time, the actor and the change. Entries SHALL NOT be rewritten or deleted.

#### Scenario: Task status history
- **WHEN** a task moves from claimed to blocked to done
- **THEN** the run log holds three entries in that order
