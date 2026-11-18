## ADDED Requirements

### Requirement: Discoveries are recorded, not acted on
Groundwork SHALL provide a way to record an unrelated discovery against the current task without creating a task, and SHALL list at completion the changed files that the task's plan never names.

#### Scenario: Unrelated TODO
- **WHEN** work on a task finds an unrelated TODO
- **THEN** it can be recorded with `groundwork task note`, and no new task is created

#### Scenario: Changed file outside the plan
- **WHEN** completion finds a changed file that the plan never mentions
- **THEN** completion lists it as a warning and does not block

#### Scenario: TODO added during the task
- **WHEN** the change adds a TODO or FIXME line that was not there when the task started
- **THEN** status and completion list it with its file and line, and a TODO that existed before the task is not listed
