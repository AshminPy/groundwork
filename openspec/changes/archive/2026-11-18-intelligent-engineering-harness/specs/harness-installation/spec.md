## Purpose
Keeps Groundwork's installer additive, idempotent, and reversible while adding the SessionStart hook, migrating the pre-Groundwork rule copy, and offering opt-in Agent Teams enablement.

## ADDED Requirements

### Requirement: Idempotent, additive settings merge
`install.sh` SHALL register the SessionStart snapshot hook, the PreToolUse push guard, and the Stop review gate in `settings.json` without duplicating entries on re-run and without modifying any key it does not own.

#### Scenario: Run twice
- **WHEN** the installer runs twice against the same `settings.json`
- **THEN** the second run reports nothing to do and the file is byte-identical to the first result

#### Scenario: User override present
- **WHEN** the user has already set an `env` key or `hook_profile` Groundwork would otherwise default
- **THEN** the user's value is preserved

### Requirement: Legacy rule copy is migrated, not duplicated
The installer SHALL detect `~/.claude/rules/harness/engineering-workflow.md` and `evidence-policy.md` (the pre-Groundwork copy), move them to a timestamped backup directory, and tell the user to update any `CLAUDE.md` pointer to `~/.claude/rules/groundwork/`.

#### Scenario: Legacy copy exists
- **WHEN** both legacy files exist
- **THEN** they are moved (not deleted) to `~/.claude/backups/groundwork-legacy-<timestamp>/` and a notice is printed

#### Scenario: No legacy copy
- **WHEN** the directory does not exist
- **THEN** nothing happens and nothing is printed about migration

### Requirement: Agent Teams are opt-in
The installer SHALL NOT enable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` unless `--agent-teams` is passed, and SHALL NOT overwrite a value the user already set.

#### Scenario: Default install
- **WHEN** `install.sh` runs without `--agent-teams`
- **THEN** the env var is untouched

### Requirement: Uninstall reverses exactly what install added
`uninstall.sh` SHALL remove the three hook files, the `rules/groundwork` directory, the three hook entries, the Groundwork deny rules, and the Groundwork env defaults, leaving every other key untouched.

#### Scenario: Round trip
- **WHEN** install then uninstall run against a settings file that had user content
- **THEN** the resulting file equals the original except for key ordering
