# Spec Delta

## Purpose

Makes every Groundwork release versioned, measured and reversible. Changes, including those proposed by the learning loop, ship only after the eval and the owner approve them.

## ADDED Requirements

### Requirement: The plugin and its components are versioned
The plugin SHALL carry a semver version. A major bump marks workflow changes, a minor bump new agents, skills or domains, and a patch bump fixes. Each skill and agent SHALL record its own component version in metadata, and telemetry SHALL record the versions that produced each result.

#### Scenario: Component change
- **WHEN** the review-rubric skill changes
- **THEN** its component version and the plugin's minor or patch version both increase, with a changelog entry

### Requirement: A release passes the gate
A release SHALL require all of these: plugin validation passes, unit tests pass, the grader-isolation and safety canaries pass, the eval is no worse than the previous release on the pre-registered criteria, and the owner approves.

#### Scenario: Eval regression
- **WHEN** the eval pass rate falls below the previous release's lower confidence bound
- **THEN** the release is refused

### Requirement: Paid eval runs need approval
No eval that calls a paid model SHALL start without the owner's approval for that run.

#### Scenario: Eval requested
- **WHEN** `/groundwork:eval` would start model runs
- **THEN** it shows the planned run count and waits for approval

### Requirement: Releases can be rolled back
Each release SHALL be tagged. Rolling back SHALL mean moving to the previous tag and, if the profile changed, reverting it from its backup.

#### Scenario: Roll back
- **WHEN** the owner rolls back from 3.2.0 to 3.1.0
- **THEN** the plugin runs 3.1.0 and the profile matches its 3.1.0 backup

### Requirement: Learning proposes changes but never applies them
`/groundwork:learn` SHALL group failures and denials from telemetry into a candidate change written as an OpenSpec change. It SHALL NOT modify agents, skills, hooks or the profile itself. A candidate SHALL ship only through the release gate.

#### Scenario: Repeated failure pattern
- **WHEN** telemetry shows the same verify failure in five runs
- **THEN** a candidate OpenSpec change is proposed, and no Groundwork file is changed

### Requirement: The 2.x baseline comes first
Groundwork 3 SHALL NOT replace 2.x until a 3.x release meets or beats the 2.5.0 focused-pilot baseline on accuracy and safety. Retiring 2.x components SHALL be a separate change.

#### Scenario: No baseline yet
- **WHEN** the 2.5.0 focused pilot has not been run
- **THEN** no 3.x release is marked as a replacement for 2.x
