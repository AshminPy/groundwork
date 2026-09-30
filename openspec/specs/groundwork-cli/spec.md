# groundwork-cli Specification

## Purpose
Gives Groundwork a single, discoverable user-facing command (`groundwork`) that dispatches to
existing, already-tested functionality — starting with `--help`, `version`, and `doctor` — without
duplicating logic, without weakening any existing compatibility guarantee (installed hook/
statusLine paths, scheduled launchd plist paths, direct script invocation), and without inventing
a packaging mechanism the project doesn't already use.

## Requirements

### Requirement: A single `groundwork` entry point exists after installation
After a real `install.sh` run, `groundwork --help` SHALL work from a normal terminal (a new shell,
or the current one after sourcing the installed PATH helper) without the user invoking any
source-tree or installed script by explicit path.

#### Scenario: Fresh install makes `groundwork` available
- **WHEN** `install.sh` completes and the user opens a new terminal (or sources the printed
  remedy)
- **THEN** `groundwork --help` runs and exits 0, listing the implemented subcommands

#### Scenario: `groundwork` with no arguments shows help, not an error
- **WHEN** `groundwork` is invoked with no arguments
- **THEN** it prints the same help text `groundwork --help` prints and exits 0

### Requirement: `groundwork version` reports the authoritative installed version
`groundwork version` SHALL read the same authoritative source `setup.sh --verify` already reads
(`$CLAUDE_CONFIG_DIR/groundwork/VERSION`) and SHALL NOT infer a version from git state when that
file exists.

#### Scenario: Installed version is reported
- **WHEN** `groundwork version` runs after a real install
- **THEN** it prints the exact content of `$CLAUDE_CONFIG_DIR/groundwork/VERSION`

### Requirement: `groundwork doctor` matches `setup.sh --doctor` exactly
`groundwork doctor` SHALL dispatch to the same code path `./setup.sh --doctor` already uses and
SHALL produce identical output for an identical configuration — it SHALL NOT reimplement any
health-check logic.

#### Scenario: Doctor output is identical via either entry point
- **WHEN** `groundwork doctor` and `./setup.sh --doctor` are both run against the same
  `$CLAUDE_CONFIG_DIR`
- **THEN** their output is byte-identical

### Requirement: PATH registration is additive, idempotent, and uninstall-safe
`install.sh` SHALL register `groundwork` on the user's `PATH` only via a guarded, idempotent
mechanism (an env script conditionally prepending the install directory, sourced from a single
marked line appended to shell rc files that already exist) — never by overwriting or duplicating
existing rc-file content, and never by requiring `sudo`. `uninstall.sh` SHALL remove exactly what
it added.

#### Scenario: Re-running install does not duplicate the PATH line
- **WHEN** `install.sh` is run twice against the same `$CLAUDE_CONFIG_DIR`/`$HOME`
- **THEN** the marked sourcing line appears exactly once in each rc file it was added to

#### Scenario: Uninstall removes the PATH registration and leaves the rest of the rc file intact
- **WHEN** `uninstall.sh` runs after a prior `install.sh`
- **THEN** the marked sourcing line and the env script are both removed, and every other line in
  the rc file is unchanged

#### Scenario: A shell with no existing rc file is not given one
- **WHEN** `install.sh` runs and, say, `~/.zshrc` does not exist
- **THEN** `install.sh` does not create `~/.zshrc` — only rc files that already exist are modified

### Requirement: Existing direct-script and `setup.sh`-flag invocations keep working unchanged
Introducing `groundwork` SHALL NOT remove, rename, or change the behavior of any existing
documented invocation (`./setup.sh --doctor`, `./setup.sh --verify`, `python3 <bin>/
groundwork_routines.py run NAME`, etc.) or any hard-compatibility path (literal hook/statusLine
paths in settings.json, literal script paths in scheduled launchd plists).

#### Scenario: Old invocations still work after `groundwork` is introduced
- **WHEN** a user runs `./setup.sh --doctor` directly after this change is installed
- **THEN** it behaves exactly as before, unaffected by the existence of `groundwork`
