# installer-upstream-compatibility Specification

## Purpose
Corrects a real, pre-existing bug: Groundwork documents and enforces "Node ≥ 18", but OpenSpec (installed by the same installer) has required Node ≥ 20.19.0 since at least version 1.12.0 — verified against OpenSpec's own `package.json`, README, and npm registry metadata on 2026-09-28. Also closes the gap that `install.sh` performs no Node version check at all today (only `setup.sh` does), and adds a lightweight, non-network way to notice future upstream (ECC/OpenSpec) version drift.

## ADDED Requirements

### Requirement: Correct, enforced Node version floor
`install.sh` and `setup.sh` SHALL both check that Node's major.minor version is at least 20.19, matching OpenSpec's actual published `engines.node` requirement, and SHALL refuse to proceed with a clear message naming the required version when it is not met.

#### Scenario: install.sh with an old Node on PATH
- **WHEN** `install.sh` is run directly with Node 18.x or 19.x on `PATH`
- **THEN** it stops before any other install step with a message stating the required version and that OpenSpec's own CLI requires it, and makes no change to `~/.claude`

#### Scenario: setup.sh with an old Node on PATH
- **WHEN** `setup.sh` is run with Node 18.x or 19.x on `PATH` and `--install-prereqs` is not given
- **THEN** it lists the required Node version alongside the other prerequisite gaps and does not proceed past the prerequisite check

### Requirement: install.sh version-checks Node, not just presence
`install.sh` SHALL perform an actual version-number comparison for Node (not only a presence check), matching the check `setup.sh` already performs.

#### Scenario: Manual/advanced install path parity
- **WHEN** an engineer uses the documented "manual/advanced" path (`./install.sh` directly, without `setup.sh`)
- **THEN** the same Node version guarantee applies as the `setup.sh` path

### Requirement: Documented requirement matches enforced requirement
`README.md`, `docs/ARCHITECTURE.md`, and any other document stating Groundwork's prerequisites SHALL state the same Node version floor that `install.sh`/`setup.sh` actually enforce.

#### Scenario: Documentation consistency check
- **WHEN** the test suite runs
- **THEN** the Node version number in `install.sh`, `setup.sh`, and `README.md` are identical

### Requirement: Lightweight upstream version awareness, no network dependency added
`setup.sh --verify` SHALL be able to report the currently-installed ECC and OpenSpec versions alongside the versions Groundwork's own documentation last recorded as verified, without adding a live network call to the installer's critical path (consistent with the existing no-network design of `groundwork_report.py`).

#### Scenario: Verify reports installed-vs-last-verified versions
- **WHEN** `setup.sh --verify` runs and ECC/OpenSpec are installed
- **THEN** it prints the installed version of each next to the version last recorded as verified in Groundwork's own docs, without making a network request

### Requirement: Breaking-change transparency
The change SHALL be documented in `CHANGELOG.md` as a correction to a pre-existing incorrect requirement, not as a new requirement being introduced, and SHALL state plainly that any environment previously relying on Node 18/19 for Groundwork's OpenSpec-dependent workflows was already non-functional for that specific path.

#### Scenario: Changelog entry
- **WHEN** this phase ships
- **THEN** the CHANGELOG entry names the corrected version, cites OpenSpec's own requirement as the source, and does not present the change as new functionality
