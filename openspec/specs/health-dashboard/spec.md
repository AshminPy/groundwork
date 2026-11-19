# health-dashboard Specification

## Purpose
A local, offline health dashboard built from Groundwork telemetry. It reports only metrics the data supports, regenerates on a schedule, and never breaks a session when it fails.

## Requirements

### Requirement: Local health dashboard from telemetry
The system SHALL generate `~/.claude/groundwork/reports/dashboard.html` from the telemetry file without a server, network access or an LLM, embedding only aggregated counters and short labels, with client-side filters for period, profile, playbook, version and environment.

#### Scenario: empty telemetry
- **WHEN** the telemetry file is missing or empty
- **THEN** the dashboard is still written, shows 0 tasks and N/A metrics, and the command exits 0

### Requirement: Honest metrics
Every rate SHALL show its numerator and denominator; metrics without data SHALL show N/A or "insufficient data", never 0%; trends SHALL appear only when both the current and previous period have at least 5 known outcomes.

#### Scenario: no ground truth
- **WHEN** telemetry carries no rework or accuracy ground truth
- **THEN** the Rework rate and Verified accuracy cards show N/A / insufficient data, not 0%

### Requirement: Scheduled regeneration
`schedule` SHALL accept disabled, daily, weekly, monthly, yearly (default weekly), SHALL replace any existing job so at most one exists, and the scheduled run SHALL write the dashboard plus dated HTML and Markdown snapshots.

#### Scenario: schedule replaced
- **WHEN** the schedule is changed from weekly to daily
- **THEN** exactly one launchd plist exists and its calendar interval is daily

### Requirement: Failure isolation
Report generation SHALL run only as a separate process (launchd or manual) and SHALL never be invoked from a hook, so a reporting failure cannot affect task execution or telemetry collection.

#### Scenario: generator absent or failing
- **WHEN** the report script is missing or raises
- **THEN** hooks, telemetry writes and task execution are unaffected (no hook references the script)

### Requirement: Outcome by context fill
The dashboard and the dated Markdown snapshot SHALL show, for the selected period, completion, verified outcome and gap rate per context-fill band (0–30, 30–50, 50–70, 70–85, 85–100%, lower edge inclusive). The band SHALL use the recorded `observed.ctx_pct`. When that is missing, it SHALL use the session's statusLine reading at or before the task end and no more than 15 minutes earlier. Tasks with neither SHALL be counted as not placed. Bands with fewer than 5 known outcomes SHALL be marked low data. The section SHALL state that it shows association, not cause, and SHALL embed no session identifiers.

#### Scenario: Recorded and matched tasks
- **WHEN** one task recorded `ctx_pct` 75 and another has only a statusLine reading of 20 two minutes before it ended
- **THEN** the section reports 2 tasks placed, one in 70–85% marked low data and one in 0–30%

#### Scenario: Reading after the task
- **WHEN** the only statusLine reading for a session is after the task ended
- **THEN** that task is not placed in a band

#### Scenario: No task has a reading
- **WHEN** no task in the period has a recorded or matched context reading
- **THEN** the section states that no task has a context reading and shows no band table
