# Spec Delta

## Purpose

Keeps the state of each run in project files that one script changes, so that agents, sessions and reports all read the same facts.

## ADDED Requirements

### Requirement: Each request has a run folder
Each routed request SHALL get a run folder under the project's `.groundwork/runs/<run-id>/`. It SHALL hold `run.yaml`, `tasks.yaml`, `decisions.jsonl`, `handoffs/`, `evidence/` and `review.md`. The `.groundwork/` directory SHALL be excluded from version control.

#### Scenario: New run is created
- **WHEN** a request is routed to T1 or higher
- **THEN** a run folder exists with `run.yaml` holding the run id, tier and stage

#### Scenario: Run files are not committed
- **WHEN** the project's ignore rules are checked
- **THEN** `.groundwork/` is ignored

### Requirement: Only the state script changes run state
`run.yaml` and `tasks.yaml` SHALL be changed only through the `gw` script. A direct edit or write to either file by any agent SHALL be denied.

#### Scenario: Agent edits tasks.yaml directly
- **WHEN** an agent uses the edit tool on `tasks.yaml`
- **THEN** the edit is denied with a message to use `gw task`

### Requirement: A task has one owner
`gw task claim` SHALL refuse to claim a task that another agent has already claimed and not released.

#### Scenario: Second claim is refused
- **WHEN** builder-kubernetes claims T4, which builder-terraform already holds
- **THEN** the claim fails and names the current owner

### Requirement: Done needs evidence
`gw task done` SHALL refuse to mark a task done unless at least one evidence file exists for it and every evidence hash still matches the files it covers.

#### Scenario: Done without evidence
- **WHEN** `gw task done T2` runs and there is no evidence file for T2
- **THEN** the command fails and the task stays open

#### Scenario: Stale evidence
- **WHEN** a file changed after the test evidence for it was recorded
- **THEN** the evidence is marked stale and `gw task done` fails until the check is run again

### Requirement: Writes check the run revision
Every state write SHALL carry the run revision that the writer last read. A write with an older revision SHALL be refused, with the instruction to re-read the state.

#### Scenario: Write based on old state
- **WHEN** an agent that read revision 14 writes after the run moved to revision 15
- **THEN** the write is refused and nothing changes

### Requirement: The report is built from files
The run board, the status line and the final report SHALL be produced by the `gw` script from the run files, not written freehand by a model. The report SHALL list done, pending and blocked tasks with evidence paths, open review items, decisions and next steps.

#### Scenario: Report matches tasks.yaml
- **WHEN** `gw run report` runs on a run with 4 done, 1 pending and 1 blocked task
- **THEN** the report shows the same counts, and every done task has an evidence path

### Requirement: The run log only grows
Every state change SHALL be appended to a run log with the time, the actor and the change. Entries SHALL NOT be rewritten or deleted.

#### Scenario: Task status history
- **WHEN** a task moves from claimed to blocked to done
- **THEN** the run log holds three entries in that order
