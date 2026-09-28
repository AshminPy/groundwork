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

### Requirement: A routine's identity, scope, access mechanism and mutation permission are configured once
Each routine's identity (e.g. a Jira site/user, a GitHub username), scope (e.g. ticket/PR/repository selection), access mechanism, and mutation permission SHALL be collected once via the setup/configure flow and persisted in `config.json`, and SHALL NOT be re-requested at routine-run time. A routine's own prompt SHALL reference this configured scope explicitly rather than operating generically.

#### Scenario: Configured scope appears in the prompt
- **WHEN** `jira_eod`'s prompt is built for a routine configured with a specific site, identity, and ticket scope
- **THEN** the generated prompt text names that exact site, identity, and scope description, and instructs the model to operate only within it

#### Scenario: PR follow-up queries are identity-scoped, never an unfiltered account-wide scan
- **WHEN** `pr_followup`'s prompt is built for a routine configured with a specific GitHub identity
- **THEN** the generated prompt text names that identity, instructs every query to be filtered by it, and explicitly forbids an unfiltered scan of every PR the account can see

### Requirement: An unconfigured access mechanism blocks the routine before any subprocess is spawned
A routine that requires an access mechanism (`jira_eod`, `pr_followup`, and `weekly_status`/`work_digest` when configured to reuse either) SHALL report `status: blocked` with a clear reason when that access is `"unconfigured"` (or, for `jira_eod`'s `jira_mcp` access, when no MCP server name is configured) — and SHALL NOT invoke `claude` at all in that case.

#### Scenario: Unconfigured Jira access
- **WHEN** `jira_eod` is enabled but its `access` field is `"unconfigured"`, and `claude` is not reachable on `PATH`
- **THEN** `run_routine("jira_eod", ...)` returns `status: blocked` with a reason naming the missing configuration, not a crash from the missing binary — because the binary is never invoked

#### Scenario: Dependent routine blocks on a borrowed, unconfigured mechanism
- **WHEN** `work_digest` is configured with `use_github: true` but `pr_followup`'s own `access` is `"unconfigured"`
- **THEN** `work_digest` reports `status: blocked` naming the missing GitHub configuration, without ever invoking `claude`

### Requirement: The runtime capability set is built from routine + configured access + configured scope + configured mutation permission
`scripts/groundwork_routines.py` SHALL build each routine's `--allowedTools` allowlist from its own configured access mechanism, never from one flat global allowlist shared across all routines. A routine that never mutates (`pr_followup`, `news`, `weekly_status`, `work_digest`, `doc_drift`) SHALL NEVER be granted a write-shaped tool for any external system, regardless of configuration.

#### Scenario: PR follow-up never receives a GitHub mutation tool
- **WHEN** `pr_followup`'s capability set is built for any configured access mechanism (`gh_cli` or `github_mcp`)
- **THEN** the resulting tool list contains only read-shaped GitHub operations, never a create/merge/update/close/comment-shaped one

#### Scenario: Each routine's grant differs by its own configuration
- **WHEN** `news`, `doc_drift`, and a configured `jira_eod` are each asked for their capability set
- **THEN** `news` receives `WebSearch`/`WebFetch` and no Jira/GitHub-shaped tool, `doc_drift` receives only base repository-read tools, and `jira_eod` receives the base tools plus exactly its own configured Jira access mechanism's tools — no routine's grant is copied from another's

#### Scenario: Cross-referencing Jira never borrows jira_eod's own write-capable grant
- **WHEN** `weekly_status` (`jira_projects` non-empty) or `work_digest` (`use_jira: true`) is asked for its capability set, and `jira_eod`'s own configured access is `jira_mcp` (a server-level wildcard, since jira_eod itself is permitted to mutate)
- **THEN** the resulting tool list contains no Jira-shaped tool at all (no `mcp__<server>__*`, no `Bash(jira *)`, no `mcp__Claude_Browser__*`/`mcp__claude-in-chrome__*`) — its prompt instead points at `jira_eod`'s own already-stored result file (read via the already-granted `Read`/`Glob` tools), never a live Jira call, so a non-mutating routine can never inherit a mutating routine's write-shaped surface

### Requirement: Routine completion status is semantic, never exit-code-only
Every routine's prompt SHALL require a structured `ROUTINE RESULT` block (`Status: COMPLETE|PARTIAL|BLOCKED|FAILED|SKIPPED`) in its output. A `claude -p` exit code of 0 SHALL NOT by itself be treated as `COMPLETE`: a missing or unparseable block on an otherwise-successful process run SHALL be recorded as `FAILED`, and a block whose own `Status` is `BLOCKED` or `PARTIAL` SHALL be recorded as exactly that, never upgraded.

#### Scenario: Exit 0 with a BLOCKED block is recorded as blocked
- **WHEN** a routine's `claude -p` process exits 0, but its own output's `ROUTINE RESULT` block reports `Status: BLOCKED`
- **THEN** the routine run's recorded status is `blocked`, not `complete`

#### Scenario: Exit 0 with no result block is recorded as failed
- **WHEN** a routine's `claude -p` process exits 0 but its output contains no parseable `ROUTINE RESULT` block
- **THEN** the routine run's recorded status is `failed`, with a reason naming the missing block — never silently treated as `complete`

### Requirement: Routine output is stored separately from telemetry, with bounded retention
A routine's own useful output (the digest/report/status content) SHALL be stored separately from its telemetry record, under an owner-only directory, retained only for a bounded number of the most recent runs per routine, and retrievable on demand. Telemetry SHALL continue to contain no routine output content.

#### Scenario: Result content never appears in telemetry
- **WHEN** a routine completes and both its telemetry record and its stored result are inspected
- **THEN** the telemetry record contains no `content` field and none of the routine's actual output text, while the stored result file does contain that text

#### Scenario: Latest result is retrievable
- **WHEN** `groundwork_routines.py latest <name>` (or `setup.sh --routines <name>`) is run after a routine has completed at least once
- **THEN** it prints that routine's most recent semantic status and its actual stored output content

#### Scenario: Retention is bounded
- **WHEN** a routine has run more times than the configured retention limit
- **THEN** only the most recent runs up to that limit are kept on disk; older result files are pruned automatically

### Requirement: Setup only asks about routines the user actually enables
The setup/configure flow SHALL ask routine-specific configuration questions only for routines the user has enabled, and SHALL NOT ask about a routine's fields when the user declines to enable it.

#### Scenario: Declining a routine asks nothing further
- **WHEN** the user answers "No" to enabling a given routine during setup or `--configure`
- **THEN** no further question is asked for that routine, and its configuration is saved as disabled with no other fields required

#### Scenario: Enabling a routine via profile selection actually asks its questions
- **WHEN** a capability profile that enables one or more routines is chosen — interactively (first-time `./setup.sh`, or `--configure` → "Change capability profile") or via `--capability-profile NAME` — and at least one routine in that profile is enabled
- **THEN** `configure_routines_interactive()` actually invokes each enabled routine's own `configure_routine_*` wizard function on that same run (not only when the user separately chooses the "reconfigure one routine" menu), and `config.json` reflects the answers given

### Requirement: `--configure` allows revisiting any single routine's configuration without reinstalling
`setup.sh --configure` SHALL offer a way to reconfigure one specific routine's fields (identity, scope, access, schedule, etc.) in place, without requiring a backup or reinstall of Groundwork.

#### Scenario: Reconfiguring one routine leaves everything else untouched
- **WHEN** `--configure` is used to change only `pr_followup`'s GitHub identity
- **THEN** `jira_eod`, `news`, and every other already-configured routine's fields are unchanged, and no new backup directory is created
