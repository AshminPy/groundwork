# Spec Delta

## Purpose

Makes every Groundwork release versioned, measured and reversible, and lets changes, including those the learning loop proposes, ship only after the eval and the owner approve them.

## ADDED Requirements

### Requirement: The plugin and its components are versioned
The plugin SHALL carry a semver version. Each skill SHALL record its component version in `metadata`. Each agent's component version SHALL be recorded in a component manifest, because agent files have no metadata field. Every component change SHALL come with a version bump and a changelog entry.

#### Scenario: Component change without a bump
- **WHEN** the review-rubric skill changes and its component version doesn't
- **THEN** the release check fails

### Requirement: A release passes the gate
A release SHALL need all of these: plugin validation passes, unit tests pass, the hook-replay tests pass, the safety canaries pass, every agent declares `tools`, the eval is no worse than the previous release on the pre-registered criteria, and the owner approves.

#### Scenario: Eval regression
- **WHEN** the eval pass rate falls below the previous release's lower confidence bound
- **THEN** the release is refused

### Requirement: Paid and live runs need approval
No eval or test that starts a live Claude session or calls a paid model SHALL run without the owner's approval for that run. The request SHALL show the planned number of runs.

#### Scenario: Eval requested
- **WHEN** `/groundwork:eval` would start 30 model runs
- **THEN** it shows "30 runs" and waits for approval

### Requirement: Releases can be rolled back
Each release SHALL be tagged. A rollback SHALL move to the previous tag and, if the profile changed, restore the profile from its backup.

#### Scenario: Roll back
- **WHEN** the owner rolls back from 3.2.0 to 3.1.0
- **THEN** the plugin runs 3.1.0, and the profile matches its 3.1.0 backup

### Requirement: Doctor finds and explains drift
`gw doctor` SHALL check the plugin version, hook registration, profile drift from the last applied profile, the OpenSpec CLI, the MCP catalog and the run log chains. It SHALL print each problem with the exact command that fixes it. It SHALL NOT change anything itself.

#### Scenario: Profile drift
- **WHEN** a settings key from the profile was changed by hand
- **THEN** `gw doctor` names the key and the `gw profile apply` command that restores it

### Requirement: Learning proposes changes but never applies them
`/groundwork:learn` SHALL group failures and denials from telemetry into a candidate change written as an OpenSpec change. It SHALL NOT change agents, skills, hooks or the profile. A candidate SHALL ship only through the release gate.

#### Scenario: Repeated failure pattern
- **WHEN** telemetry shows the same verify failure in five runs
- **THEN** a candidate OpenSpec change is proposed, and no plugin file changes

### Requirement: The 2.x baseline comes before replacement
No 3.x release SHALL be marked as replacing 2.x until it meets or beats the 2.5.0 focused-pilot baseline on accuracy and safety. Retiring 2.x components SHALL be a separate change.

#### Scenario: No baseline yet
- **WHEN** the 2.5.0 focused pilot hasn't been run
- **THEN** no 3.x release is marked as replacing 2.x
