# Spec Delta

## Purpose

Shows the owner the state of the current run at a glance in Claude Code's interface, using only facts read from the run files and the session.

## ADDED Requirements

### Requirement: A one-line status band
Where the band is supported, a band above the prompt SHALL show the tier, stage, tasks done of total, the verify result, context use and session cost. Every value SHALL come from the run files or the session's usage data.

#### Scenario: Band during build
- **WHEN** a T3 run is in the build stage with 2 of 6 tasks done
- **THEN** the band shows "T3 · build · 2/6" with the current verify state

#### Scenario: Unknown value
- **WHEN** a value can't be read
- **THEN** the band leaves it out instead of showing a guess

### Requirement: A run-board pane
A pane SHALL list each task with its owner, status and evidence path, the open review items, and the next step. It SHALL open on command and refresh when the run files change.

#### Scenario: Task finishes
- **WHEN** `gw task done T3` succeeds
- **THEN** the pane shows T3 as done with its evidence path within 2 seconds

### Requirement: Alerts for changes that need attention
The mod SHALL show a short alert when a stage changes, a task is blocked, an action is denied, or owner approval is needed.

#### Scenario: Approval needed
- **WHEN** a T4 run reaches the approval gate
- **THEN** an alert says approval is needed and names the run

### Requirement: The mod never enforces safety
No deny, block or gate SHALL exist only in the mod. Disabling the mod SHALL leave every safety guarantee in place.

#### Scenario: Mod disabled
- **WHEN** the mod is disabled and a builder runs `terraform destroy`
- **THEN** the command is still denied by the guard hook

### Requirement: A status line where the band isn't shown
Where the band isn't available, including VS Code and sessions without mods, the profile's status line SHALL show the tier, stage and task counts.

#### Scenario: Session without mods
- **WHEN** the session runs where the mod isn't loaded
- **THEN** the status line shows the tier, stage and task counts
