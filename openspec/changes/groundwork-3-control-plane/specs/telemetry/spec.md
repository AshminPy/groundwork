# Spec Delta

## Purpose

Records privacy-safe facts about every run and agent, so the eval dashboard, model routing, the learning loop and the release gate can measure what works.

## ADDED Requirements

### Requirement: One record per agent run and per run
Groundwork SHALL append a telemetry record for each agent run and each finished run. Each record SHALL hold the run id, tier, stage, agent, model, effort, component versions, duration, tool counts, the outcome, denial counts by kind, and the loop rounds used.

#### Scenario: Agent record
- **WHEN** builder-terraform finishes a task
- **THEN** a record with its model, effort, component version, duration and outcome is appended

### Requirement: Telemetry holds no sensitive content
Telemetry SHALL NOT contain prompt text, command text, file contents, credentials or reasoning. File paths SHALL be stored only as hashes.

#### Scenario: Secret in a command
- **WHEN** a Bash command containing a token runs during a run
- **THEN** no telemetry record contains the token or the command text

### Requirement: Telemetry never breaks work
A telemetry write that fails SHALL be logged and SHALL NOT stop or change the action that caused it.

#### Scenario: Disk full
- **WHEN** the telemetry file can't be written
- **THEN** the tool call still completes, and the failure is logged once

### Requirement: Telemetry stays local and per profile
Telemetry SHALL be stored only on the local machine, in a folder for the active profile. It SHALL NOT be sent to any external service.

#### Scenario: Work and personal
- **WHEN** a personal-profile session reads telemetry
- **THEN** it reads only the personal-profile folder
