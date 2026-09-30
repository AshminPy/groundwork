# groundwork-update-lifecycle Specification

## Purpose
Gives an installed Groundwork a supported way to discover and install a newer published release,
and to roll back to a prior one, without requiring a repository clone or any new credential —
`groundwork update [--check|--version X]` / `groundwork rollback [--version X]`, both implemented
as thin orchestration over the existing, already-tested `setup.sh`/`install.sh` and GitHub
Releases API, never as a second installer.

## Requirements

### Requirement: `groundwork update --check` is non-mutating and never guesses
`update --check` SHALL report the installed version, the latest published (non-draft,
non-prerelease) release, and whether an update is available, without changing any installed state.
When the comparison cannot be determined (network unreachable, an unparseable version string), it
SHALL report `UNKNOWN` rather than a guessed yes/no answer.

#### Scenario: an older installed version reports an update is available
- **GIVEN** the installed VERSION is older than the latest published release
- **WHEN** `groundwork update --check` runs
- **THEN** it prints the current version, the latest version, and "Update available: YES", and
  exits 0, with no installed file changed

#### Scenario: network failure never resolves to a false answer
- **GIVEN** the GitHub Releases API is unreachable
- **WHEN** `groundwork update --check` runs
- **THEN** it prints "Latest: UNKNOWN" and "Update available: UNKNOWN", and exits non-zero —
  never "NO" and never a fabricated version

### Requirement: `groundwork update` only ever installs a real, published, stable release
`update` (with no flags, or with `--version VERSION`) SHALL install only a release that the GitHub
Releases API reports as published, non-draft, and non-prerelease. It SHALL NOT accept `origin/main`,
a branch name, a commit SHA, a draft release, or a prerelease as a valid target under any
circumstance.

#### Scenario: a draft or prerelease is never selectable
- **GIVEN** a release tagged `v3.2.0` exists but is marked draft or prerelease
- **WHEN** the user runs `groundwork update --version 3.2.0`
- **THEN** the command refuses with a clear error and installs nothing

#### Scenario: an arbitrary ref is never accepted as a version
- **GIVEN** the user passes a branch name, a commit SHA, or any string that is not a published
  release's exact tag
- **WHEN** `groundwork update --version <that string>` runs
- **THEN** the command refuses with a clear error before any network fetch of source content and
  installs nothing

### Requirement: `update` reuses the existing installer end to end and never duplicates its logic
`update` SHALL fetch the target release's source tree and invoke that tree's own, unmodified
`setup.sh` to perform the installation. It SHALL NOT reimplement any step `setup.sh`/`install.sh`
already perform (backup, file sync, settings merge, capability application, routine/statusline
wiring).

#### Scenario: a successful update runs the fetched tree's real setup.sh
- **GIVEN** a valid target release is resolved and its source tarball is fetched and extracted
- **WHEN** `update` proceeds to install
- **THEN** it invokes the fetched tree's own `setup.sh --non-interactive`, and the installed
  `VERSION` afterward matches the target release

#### Scenario: an archive missing required files is refused before installing anything
- **GIVEN** a fetched release archive is missing `install.sh`, `setup.sh`, or `CHANGELOG.md`
- **WHEN** `update` validates the extracted tree
- **THEN** it refuses to invoke any installer and exits non-zero, leaving the current installation
  untouched

### Requirement: `update` preserves the installation's current profile, schedule, and Agent-Teams
setting across a non-interactive run
`update` SHALL read the installation's current profile, report schedule, and Agent-Teams setting
before installing, and SHALL explicitly pass them to the fetched `setup.sh --non-interactive` —
never relying on that installer's own non-interactive-mode defaults for any setting whose omission
would silently change existing user configuration.

#### Scenario: a custom report schedule survives a non-interactive update
- **GIVEN** the installation's current report schedule is `monthly` (not the installer's own
  non-interactive default of `weekly`)
- **WHEN** `groundwork update` runs
- **THEN** the fetched `setup.sh` is invoked with `--schedule monthly`, not left to its own default

#### Scenario: no profile ever configured is never overwritten with a guessed one
- **GIVEN** the installation has no `GROUNDWORK_PROFILE` set
- **WHEN** `groundwork update` runs
- **THEN** no `--profile` flag is passed to the fetched `setup.sh`, preserving the same
  correct-by-omission behavior a fresh `setup.sh --non-interactive` run already has

### Requirement: a fetched archive is extracted with path-traversal protection
`update` SHALL reject any archive member whose resolved path would land outside the extraction
target directory, before extracting anything from that archive.

#### Scenario: a path-traversal archive member is rejected
- **GIVEN** a fetched archive contains a member named e.g. `../evil.txt`
- **WHEN** `update` extracts the archive
- **THEN** extraction is refused and no file is written outside the intended temporary directory

### Requirement: `groundwork rollback` reuses the existing backup/restore mechanism, never a new one
`rollback` (with no flags, or with `--version VERSION`) SHALL dispatch to the installed
`setup.sh --rollback` mechanism. `--version VERSION` SHALL resolve to the specific backup directory
whose `BACKUP-INFO.txt` records it was taken immediately before that version was installed; if no
such backup exists, `rollback` SHALL refuse cleanly rather than substituting a different backup.

#### Scenario: rollback with no version restores the most recent backup
- **GIVEN** at least one backup exists under the installation's backup root
- **WHEN** `groundwork rollback` runs with no `--version`
- **THEN** it dispatches to `setup.sh --rollback` with no directory argument (the installed
  mechanism's own "most recent" behavior)

#### Scenario: rollback --version with no matching backup fails clean
- **GIVEN** no backup's `BACKUP-INFO.txt` records `groundwork_version_before=<requested version>`
- **WHEN** `groundwork rollback --version <that version>` runs
- **THEN** the command refuses with a clear error and does not fall back to restoring a different
  backup

### Requirement: no credential storage, no privilege escalation, no OS package installation
This feature SHALL NOT store, request, or require any credential (GitHub, Claude, AWS, MCP, or
otherwise); SHALL NOT invoke `sudo` or otherwise escalate privileges; and SHALL NOT install any OS
package as part of `update`.

#### Scenario: update never installs OS-level prerequisites itself
- **GIVEN** a fetched release's `setup.sh` would otherwise prompt to install a missing prerequisite
- **WHEN** `groundwork update` invokes it
- **THEN** `--no-install-prereqs` is always passed, so no OS package is installed by this code path
