## ADDED Requirements

### Requirement: Discoveries are recorded, not acted on
Groundwork SHALL provide a way to record an unrelated discovery against the current task without creating a task, and SHALL list at completion the changed files that the task's plan never names.

#### Scenario: Unrelated TODO
- **WHEN** work on a task finds an unrelated TODO
- **THEN** it can be recorded with `groundwork task note`, and no new task is created

#### Scenario: Changed file outside the plan
- **WHEN** completion finds a changed file that the plan never mentions
- **THEN** completion lists it as a warning and does not block
