## ADDED Requirements

### Requirement: Optional capability and Routines configuration during setup
`setup.sh` SHALL offer an optional, skippable capability/Routines selection stage after its existing profile/teams/schedule questions, defaulting to "skip" so the one-command path (`./setup.sh` with all defaults, or `--non-interactive` without `--capability-profile`) installs the unchanged core with no `config.json` written. When a capability profile is chosen (interactively or via `--capability-profile NAME`), `setup.sh` SHALL write it via `groundwork_config.py init` and schedule every routine the chosen profile enables, using the same scheduling mechanism as the existing report dashboard.

#### Scenario: Default path unchanged
- **WHEN** `./setup.sh --non-interactive --profile work` runs with no `--capability-profile`
- **THEN** no `config.json` is written, and `--doctor` afterward reports Capabilities as `NOT CONFIGURED` rather than a fabricated profile

#### Scenario: Capability profile chosen non-interactively
- **WHEN** `./setup.sh --non-interactive --capability-profile sre-cloudops` runs
- **THEN** `~/.claude/groundwork/config.json` (or the target `CLAUDE_CONFIG_DIR`) is written with `profile: sre-cloudops`, that profile's routines show `enabled: true` in the written file, and each enabled routine is scheduled

### Requirement: `--doctor` reports capability and Routine status alongside core health
`setup.sh --doctor` SHALL run the existing read-only installation checks and, additively, report the configured capability profile, cloud/platform/integration selections, skill availability, and every Routine's enabled/schedule/last-run status — even when one or more core checks fail. It SHALL NOT report a capability as CONNECTED without actually checking connectivity where that is safe to do, and SHALL say plainly when connectivity was not checked.

#### Scenario: Doctor on a healthy install
- **WHEN** `--doctor` runs against an install with a capability profile configured
- **THEN** it prints the existing core PASS/FAIL rows followed by a Capabilities section (profile, cloud, platform, integrations, skills) and a Routines section (one line per routine with enabled/mutates/schedule/last-run)

#### Scenario: Doctor on a partially broken install
- **WHEN** one or more core checks (rules, playbooks, hooks, telemetry, etc.) FAIL
- **THEN** `--doctor` still prints the full Capabilities and Routines sections after the core rows, and its exit code still reflects the core failure

### Requirement: `--configure` revisits capability selection without reinstalling
`setup.sh --configure` SHALL re-run only the capability/Routines selection (or accept `--capability-profile` directly), write the result the same way the initial setup does, and SHALL NOT take a new configuration backup or re-run `install.sh`.

#### Scenario: Reconfigure to a different profile
- **WHEN** `./setup.sh --configure --capability-profile minimal` runs against an already-configured install
- **THEN** `config.json`'s profile changes to `minimal`, no new backup directory is created, and Groundwork's core installation is untouched

### Requirement: `--routines` lists configured Routines and their last-run status
`setup.sh --routines` SHALL print every known Routine's enabled state, whether it mutates, its schedule, and its last recorded run status, read from the same `config.json` and telemetry `--doctor` uses.

#### Scenario: No routines ever run
- **WHEN** `--routines` runs against a freshly configured install with no routine ever executed
- **THEN** every routine line shows `never run`

### Requirement: Uninstall removes capability configuration and unschedules every Routine
`uninstall.sh` SHALL remove `config.json` (Groundwork's own configuration, not user data) and SHALL unschedule every known Routine's scheduled job before removing the Routines script, the same way it already unschedules the report dashboard's job.

#### Scenario: Uninstall after capability configuration
- **WHEN** `uninstall.sh` runs against an install with a capability profile configured and at least one Routine scheduled
- **THEN** `config.json` no longer exists afterward, and no `com.groundwork.routine.*` scheduled job remains
