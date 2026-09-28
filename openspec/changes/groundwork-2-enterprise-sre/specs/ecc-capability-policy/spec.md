# ecc-capability-policy Specification

## Purpose
Curates ECC's install to a default set relevant to SRE/CloudOps/Platform Engineering, using only ECC's own existing install-time selection mechanisms (`--profile`, `--with capability:*`) and, conditionally, Claude Code's own `skillOverrides` setting — never forking, vendoring, or copying ECC content, and never building a Groundwork-maintained duplicate catalog. Directly addresses the confirmed finding that ECC's default install (68 agents / 286 skills) spends roughly a third of its footprint (`agent_meta` + `business_ops`, 110 of 286 skills) on capabilities with no software-engineering relevance at all.

## ADDED Requirements

### Requirement: Curated default ECC profile for SRE/CloudOps
`install.sh` SHALL install ECC using a curated capability selection by default — CORE SRE and OPTIONAL SRE categories from the capability matrix (design.md §D.2/D.3) enabled, LANGUAGE/PROJECT-SPECIFIC categories available on demand, and NOT-RELEVANT categories (`agent_meta`, `business_ops`, `datasci_ml`, `design_ux`, `media_creative`, and equivalents) not enabled by default.

#### Scenario: Default install
- **WHEN** `install.sh` runs with no ECC profile flag given
- **THEN** the ECC install command includes the curated selection, and the installed capability set excludes the categories classified NOT RELEVANT TO GROUNDWORK DEFAULT in design.md §D.2/D.3

### Requirement: Explicit opt-out to the full catalog
`install.sh` SHALL accept a flag (e.g. `--ecc-profile full`) that installs ECC's complete, uncurated catalog, matching today's behavior exactly, for engineers who need it.

#### Scenario: Opt-out
- **WHEN** `install.sh --ecc-profile full` is run
- **THEN** ECC installs with all 68 agents and 286 skills, identical to Groundwork 1.5.1's behavior

### Requirement: Curation never silently drops a capability an existing install already used
Re-running `install.sh` on an existing installation SHALL NOT silently narrow an already-installed ECC capability set without an explicit, visible note in the install output naming what changed and how to restore it.

#### Scenario: Upgrade from an uncurated 1.5.1 install
- **WHEN** `install.sh` (2.0, curated-by-default) runs against a machine that previously ran 1.5.1's uncurated install
- **THEN** the install output states plainly that the default profile changed, names the categories no longer installed by default, and states the `--ecc-profile full` escape hatch

### Requirement: skillOverrides used only after runtime confirmation it applies to plugin skills
`scripts/merge_settings.py` SHALL add `skillOverrides` entries for finer-grained ECC skill control only after a live test confirms Claude Code's `skillOverrides` setting actually suppresses auto-invocation of a plugin-provided (not project-local) skill on the Claude Code version in use; until then, curation SHALL rely solely on ECC's own install-time selection.

#### Scenario: skillOverrides confirmed effective
- **WHEN** a live test shows a `skillOverrides` entry set to `off` for a specific ECC skill prevents its auto-invocation in a fresh session
- **THEN** `merge_settings.py` may add such entries for skills in the NOT-RELEVANT categories as an additional layer of curation

#### Scenario: skillOverrides confirmed ineffective for plugin skills
- **WHEN** the live test shows no effect on plugin-provided skill invocation
- **THEN** `merge_settings.py` does not add `skillOverrides` entries for ECC skills, `docs/TROUBLESHOOTING.md`'s existing claim is corrected either way with the tested result, and curation continues to rely solely on ECC's install-time selection

### Requirement: Context-cost evidence
The capability that ships from this specification SHALL be accompanied by a measured (not estimated) before/after token-cost comparison at session start, curated profile vs. full install.

#### Scenario: Cost evidence recorded
- **WHEN** this phase ships
- **THEN** `docs/VALIDATION.md` records the measured session-start token cost under both profiles, matching the measurement discipline used for ECC's original cost documentation in the 1.0.0 evidence
