## ADDED Requirements

### Requirement: One-click onboarding wrapper
`./setup.sh` SHALL check prerequisites, back up the complete Claude configuration directory to a timestamped owner-only directory that is never overwritten, ask for profile, Agent Teams and dashboard schedule, delegate installation to `install.sh`, apply the schedule through the existing report scheduler, verify the installation without any model call, generate the first dashboard, and print a summary with backup path, dashboard path and the verify/rollback commands.

#### Scenario: installer fails after the backup
- **WHEN** `install.sh` exits non-zero
- **THEN** setup.sh prints the failure, the backup path and the rollback command, and the previous configuration is untouched

### Requirement: Safe rollback
`--rollback` SHALL move the current configuration directory to a timestamped disabled copy before restoring, restore only an unambiguous latest setup.sh backup taken from the same directory (or an explicitly given one), verify the restored directory is readable, and print what was restored.

#### Scenario: ambiguous backups
- **WHEN** two backups share the same timestamp and no directory is given
- **THEN** rollback refuses and asks for an explicit backup directory
