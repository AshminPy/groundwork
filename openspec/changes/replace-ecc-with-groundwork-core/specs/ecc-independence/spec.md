## Purpose

Groundwork installs, runs, checks its health and reviews work without the ECC plugin, and it moves existing installs off ECC safely, with a full backup first and an offline way back.

## ADDED Requirements

### Requirement: A fresh install does not install ECC
`install.sh` SHALL NOT add the `affaan-m/ECC` marketplace, SHALL NOT install `ecc@ecc`, and SHALL NOT write `pluginConfigs["ecc@ecc"]` or `GATEGUARD_EXEMPT_GLOBS`.

#### Scenario: Fresh install on a config directory without ECC
- **WHEN** `install.sh` runs on a config directory that has no ECC
- **THEN** `claude plugin list --json` for that directory lists no `ecc@ecc`, the settings file has none of the three ECC keys, and every Groundwork hook entry and the Groundwork reviewer agent are installed

### Requirement: An existing ECC install is migrated off after a full backup
When `install.sh` finds `ecc@ecc` installed at user scope in the target config directory, it SHALL, in this order: take a full backup of the config directory in the format `./setup.sh --rollback` restores; confirm Groundwork's hooks and reviewer agent are installed; uninstall the plugin keeping its data directory; remove the `ecc` marketplace; remove `enabledPlugins["ecc@ecc"]`, `extraKnownMarketplaces.ecc`, `pluginConfigs["ecc@ecc"]` and any parent object left empty; and print the backup path, the rollback command and a notice to restart open sessions. If the backup or the confirmation fails, nothing SHALL be removed.

#### Scenario: Upgrade from Groundwork 2.5 with ECC installed
- **WHEN** `install.sh` runs where `ecc@ecc` 2.2.1 is installed and enabled
- **THEN** afterwards `claude plugin list --json` lists no `ecc@ecc`, the three settings keys are gone, a backup directory with `BACKUP-INFO.txt` exists, and the output names `./setup.sh --rollback <that directory>`

#### Scenario: Backup fails
- **WHEN** the backup step fails (for example the backup folder is not writable)
- **THEN** ECC is still installed, settings are unchanged, and install reports the migration as skipped with the reason

#### Scenario: Offline rollback
- **WHEN** the owner runs `./setup.sh --rollback <backup dir>` after migration, with no network
- **THEN** `claude plugin list --json` lists `ecc@ecc` again and `settings.json` is byte-identical to its state before the migration

#### Scenario: Running the migration twice
- **WHEN** `install.sh` runs again on a migrated config directory
- **THEN** it reports that ECC is absent, makes no backup for the migration, and leaves `settings.json` byte-identical

#### Scenario: Owner keeps ECC
- **WHEN** `install.sh` runs with `GROUNDWORK_KEEP_ECC=1`
- **THEN** ECC, its marketplace and its settings keys are left exactly as they were, and the output says ECC was kept by the owner

#### Scenario: Claude CLI not available
- **WHEN** `claude` is not on PATH during `install.sh`
- **THEN** the migration is skipped with a warning and the rest of the install completes

### Requirement: Migration acts only on the target config directory
Every `claude plugin` call made by the migration SHALL run with the target config directory, and the migration SHALL NOT change any other config directory.

#### Scenario: Bench copy migration
- **WHEN** `CLAUDE_CONFIG_DIR=<bench copy> ./install.sh` runs on a machine whose `~/.claude` also has ECC
- **THEN** ECC is removed from the bench copy only, and `claude plugin list --json` for `~/.claude` still lists `ecc@ecc`

### Requirement: ECC's data outside the plugin is never deleted
The migration SHALL NOT delete `~/.claude/session-data`, `~/.local/share/ecc-homunculus`, `~/.claude/bash-commands.log`, `~/.claude/cost-tracker.log`, `~/.claude/metrics/costs.jsonl`, `~/.gateguard` or ECC's plugin data directory. It SHALL list the ones that exist, with sizes, and print one command that removes them. It SHALL report, without editing, any other settings value that points into `plugins/cache/ecc/`.

#### Scenario: ECC data present at migration
- **WHEN** the migration runs and `~/.claude/bash-commands.log` exists
- **THEN** the file still exists afterwards and the output lists it with its size and the removal command

### Requirement: Health check does not depend on ECC
`setup.sh --verify` and `--doctor` SHALL pass without ECC, SHALL check every hook entry Groundwork registers and the Groundwork reviewer agent, and SHALL describe ECC, when present, as "present, not used by Groundwork" (or "kept by owner" when `GROUNDWORK_KEEP_ECC=1`), never as a requirement or a failure.

#### Scenario: Verify on a migrated config directory
- **WHEN** `setup.sh --verify` runs after migration
- **THEN** the result is PASS and no row requires ECC

#### Scenario: A Groundwork part is missing
- **WHEN** one registered Groundwork hook entry or the reviewer agent file is missing
- **THEN** `setup.sh --verify` reports FAIL and names it

### Requirement: Groundwork text does not direct anyone to ECC
Groundwork's rules, playbooks, hooks, scripts, installer and docs SHALL NOT tell Claude or the owner to use an ECC agent, command, skill or hook. The only matches of `ecc[:@/]` or the word `ECC` (case-insensitive) SHALL be in: `CHANGELOG.md`, `CREDITS.md`, `THIRD_PARTY_NOTICES.md`, `docs/RELEASE-REPORT-*.md`, `docs/designs/`, `openspec/`, `scripts/migrate_off_ecc.py`, `scripts/unmerge_settings.py`, the reviewer agent's licence header, and `tests/`.

#### Scenario: Searching the repository and the installed tree
- **WHEN** `grep -rniE 'ecc[:@/]|\bECC\b'` runs over the repository and the installed `rules/groundwork`, `groundwork/playbooks` and `hooks`
- **THEN** every match is in the allow-list
