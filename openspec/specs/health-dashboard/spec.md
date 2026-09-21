# health-dashboard Specification

## Purpose
TBD - created by archiving change report-dashboard. Update Purpose after archive.

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
