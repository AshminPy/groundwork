# Spec Delta

## MODIFIED Requirements

### Requirement: Data-source contract
The system SHALL classify every displayable field as exactly one of five classes:
- LIVE: supplied directly by Claude Code's stdin JSON, or computed by a fast, bounded-timeout operation performed fresh on each render;
- LAST-COMPLETED-TURN: available only from the most recently completed turn's own telemetry record;
- CACHED: read from a file populated by a separate, earlier process, never computed fresh inside the statusLine;
- RECORDED: read fresh on each render from the repository's task ledger, the durable record that Groundwork's own hooks write. It is shown as recorded state, never as re-verified against the current code;
- UNAVAILABLE: no durable, authoritative source exists anywhere in Groundwork today.

The system SHALL NOT display a field classified UNAVAILABLE. It SHALL NOT convert an UNAVAILABLE field into an inferred or guessed value.

#### Scenario: Unavailable fields are never displayed
- **WHEN** rendering the statusLine
- **THEN** no role or persona label and no evidence-label count (VERIFIED, UNVERIFIED, ASSUMPTION and the like) appears anywhere in the output, because none has a durable, authoritative source

#### Scenario: A recorded review is shown as recorded
- **WHEN** the current task's ledger record holds a review with verdict `approve` and Must-fix 0
- **THEN** the review field carries the documented recorded-state marker, and the statusLine shows the task as complete only when the ledger records it as complete

#### Scenario: A last-completed-turn field is visually distinguished from a live field
- **WHEN** the statusLine displays a LAST-COMPLETED-TURN field (playbook, execution mode, or validation/tests-run state)
- **THEN** its rendering uses a documented, consistent visual convention that a live field does not use, so a reader cannot mistake it for the current, in-progress turn's state

## ADDED Requirements

### Requirement: Current task segment
When the session's working directory is inside a git repository whose task ledger holds open tasks, the statusLine SHALL show a task segment:
- **One open task:** its key, phase, task progress (checked of total) and blocked state. It SHALL add the latest recorded review verdict and Must-fix count when one exists.
- **Several open tasks:** the number of open tasks and the key of the recommended next task.

The segment SHALL read only the ledger files and the change's `tasks.md`. It SHALL find the repository root with the existing bounded git call. It SHALL NOT run the OpenSpec CLI or compute a code fingerprint. Any read error SHALL omit the segment rather than fail the render. The segment SHALL be hideable through the existing per-section show/hide setting, under the section name `task`, and SHALL be shown by default.

#### Scenario: One open task
- **WHEN** COR-123 is the only open task, implementing, with 3 of 7 tasks checked and no review yet
- **THEN** the statusLine shows COR-123, implementing and 3/7, and shows no review field

#### Scenario: Several open tasks
- **WHEN** three tasks are open and COR-202 is the recommended next task
- **THEN** the statusLine shows 3 open tasks and COR-202 as next

#### Scenario: Outside a repository or with no open tasks
- **WHEN** the working directory is not in a git repository, or the ledger has no open task
- **THEN** no task segment is shown and the render does not fail

#### Scenario: Hidden by the user
- **WHEN** the personalization file hides the `task` section
- **THEN** no task segment is shown

#### Scenario: No expensive work
- **WHEN** the task segment renders
- **THEN** no subprocess other than the bounded git call runs, and the measured render time is recorded as validation evidence
