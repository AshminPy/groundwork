## ADDED Requirements

### Requirement: One generic Routines framework, not bespoke per-routine scripts
Groundwork SHALL implement Routines as one generic framework — a name, a prompt-template function, a `mutates` boolean, and a default schedule — rather than a separate script per routine.

#### Scenario: Registry shape
- **WHEN** `scripts/groundwork_routines.py`'s `ROUTINES` registry is inspected
- **THEN** it contains exactly `jira_eod`, `news`, `weekly_status`, `pr_followup`, `work_digest`, `doc_drift`, each with `mutates`, `default_schedule`, `prompt`, and `needs_offline_work` keys, and only `jira_eod` has `mutates: true`

### Requirement: Safe unattended invocation
A Routine SHALL invoke Claude Code headlessly via `claude -p` using `--permission-mode dontAsk`, `--permission-prompts none`, and an explicit `--allowedTools` allowlist scoped to what that routine needs. A Routine SHALL NEVER use `--dangerously-skip-permissions` or `--bare`.

#### Scenario: Command construction
- **WHEN** `build_command()` is called for any routine, with `dry_run` either `True` or `False`
- **THEN** the resulting command never contains `--dangerously-skip-permissions` or `--bare`, and always contains `--permission-mode dontAsk`, `--permission-prompts none`, and a non-empty `--allowedTools` value

### Requirement: Off-switches
A Routine run SHALL be skippable, without attempting any subprocess invocation, via `GROUNDWORK_ROUTINES=off` (the whole subsystem) or `GROUNDWORK_ROUTINES_<NAME>=off` (one routine), and SHALL report `status: skipped` with a reason when skipped this way.

#### Scenario: Subsystem off-switch
- **WHEN** `GROUNDWORK_ROUTINES=off` is set and `run_routine()` is called for any routine name
- **THEN** the result has `status: skipped` and no `claude` process is ever spawned, even if `claude` is unreachable on `PATH`

#### Scenario: Per-routine off-switch
- **WHEN** `GROUNDWORK_ROUTINES_WORK_DIGEST=off` is set
- **THEN** `run_routine("work_digest", ...)` is skipped but `run_routine("news", ...)` is not affected by that variable

### Requirement: Structured, secret-free telemetry only
A Routine run SHALL record only structured, non-sensitive fields to its own telemetry file — never raw prompt text, raw model output, or credentials — using the same owner-only (0600), append-only file discipline as `hooks/groundwork_telemetry.py`. Telemetry writes SHALL fail open: a telemetry failure SHALL NOT fail the routine run.

#### Scenario: Telemetry record shape and permissions
- **WHEN** a routine completes (successfully or not) against a real `claude` invocation
- **THEN** `~/.claude/groundwork/telemetry/routines.jsonl` (or `GROUNDWORK_ROUTINES_TELEMETRY_PATH` if set) gains one JSON line with `routine`, `mutates`, `dry_run`, `status`, `exit_code`, `duration_s`, `output_chars` fields, the file has mode `0600`, and the record contains none of the routine's actual output text

### Requirement: Scheduling reuses the existing launchd/cron pattern
Routine scheduling SHALL extend `scripts/groundwork_report.py`'s existing macOS-launchd scheduler pattern (one plist per routine, labeled `com.groundwork.routine.<name>`) rather than introducing a new scheduler, and SHALL report that automatic scheduling needs macOS launchd on any other OS, naming the manual/cron alternative instead of silently doing nothing.

#### Scenario: Non-macOS schedule request
- **WHEN** `schedule_routine(name, freq)` is called with `GROUNDWORK_OS` (or the real platform) not `darwin`
- **THEN** no plist is written, and the result names the manual/cron invocation as the fallback

#### Scenario: macOS schedule request
- **WHEN** `schedule_routine(name, freq, hour)` is called with the platform resolved to `darwin`
- **THEN** a plist named `com.groundwork.routine.<name>.plist` is written under the LaunchAgents directory, with `StartCalendarInterval` matching the requested frequency and hour, and `CLAUDE_CONFIG_DIR` carried through in `EnvironmentVariables` when set

### Requirement: Jira end-of-day routine drafts from evidence only and never invents work
The `jira_eod` routine SHALL draft ticket updates only from evidence (git log/diff, PRs, OpenSpec task-checkbox changes, investigation-continuity state, test/review/deployment results actually observed), SHALL support a dry-run mode that drafts but never posts, and SHALL require the prompt to instruct reading a posted comment back before reporting a live post `VERIFIED`.

#### Scenario: No evidenced work
- **WHEN** the routine finds no ticket with real evidenced work for the day
- **THEN** its prompt instructs it to say so plainly and post or draft nothing, rather than manufacturing a comment

### Requirement: Documentation-drift routine reports drift, never auto-rewrites
The `doc_drift` routine SHALL compare implementation against documentation and report meaningful drift with the exact file/line and mismatch, and SHALL NOT rewrite documentation itself.

#### Scenario: Drift found
- **WHEN** the routine's prompt runs against a repository with a documented-but-unshipped capability
- **THEN** the prompt instructs it to report the drift for a human or follow-up session to fix, not to edit the documentation in place
