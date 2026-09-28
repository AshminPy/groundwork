# ecc-capability-policy Specification

## Purpose
Documents Groundwork's actual, verified ECC capability posture for SRE/CloudOps/Platform Engineering, after Phase 1 implementation (independent-review finding "M4") disproved this spec's original mechanism. Never forks, vendors, or copies ECC content, and never builds a Groundwork-maintained duplicate catalog.

**Correction notice (2026-09-28, finding M4)**: the original version of this spec required curating ECC's install using "ECC's own existing install-time selection mechanisms (`--profile`, `--with capability:*`)" and, conditionally, `skillOverrides`. Both were investigated directly against the installed tooling and found **not usable on Groundwork's actual install path**:
- `install.sh` installs ECC with `claude plugin marketplace add affaan-m/ECC` + `claude plugin install ecc@ecc`, not ECC's own standalone installer. `claude plugin install --help` (Claude Code 2.1.283) confirms this command has no skill/agent selection flag — only `--config <key>=<value>` against the plugin's own declared `userConfig` schema (`hooks_enabled`, `hook_profile`). The `--profile`/`--with capability:*` flags exist only on ECC's separate standalone installer, which ECC's own README and Groundwork's `install.sh` both say must never be run alongside the plugin path.
- Direct inspection of the installed Claude Code CLI's own source confirms the `skillOverrides` resolution path explicitly returns early for any skill whose `source` is `"plugin"` — `skillOverrides` is never consulted for ECC's skills, by design, in the installed version.

There is currently no upstream-supported mechanism to install or restrict ECC to a skill/agent subset on Groundwork's install path. This is a genuine, evidence-backed limitation, not an unmet requirement: Decision D4 required using upstream-supported mechanisms *only after validating them* and retaining a full-ECC opt-out — it did not require that curation succeed. See `openspec/changes/groundwork-2-enterprise-sre/design.md` §A.6, §A.8, §D.1 for the full evidence trail.

## ADDED Requirements

### Requirement: ECC installs at its full, unrestricted capability set
`install.sh` SHALL continue installing ECC's complete catalog (all skills, agents, hooks, and MCP servers ECC's `main` branch currently ships), matching Groundwork 1.5.1's actual behavior, because no upstream-supported mechanism exists to install a curated subset on the plugin-marketplace install path Groundwork uses.

#### Scenario: Default install
- **WHEN** `install.sh` runs
- **THEN** ECC installs via `claude plugin marketplace add affaan-m/ECC` + `claude plugin install ecc@ecc`, with no skill/agent subset flag passed (none exists), and the installed capability set is whatever ECC's `main` branch currently ships

### Requirement: The plugin's own hook configuration remains the one real install-time lever
`install.sh` SHALL continue passing `--config hook_profile=standard` (already Groundwork's existing behavior), the only customization the plugin's manifest actually declares (`hooks_enabled`, `hook_profile`).

#### Scenario: Hook profile applied
- **WHEN** `install.sh` installs or updates ECC
- **THEN** `claude plugin install`/`claude plugin update` is called with `--config hook_profile=standard`, and `claude plugin details ecc@ecc` reflects that config value

### Requirement: Whole-plugin disable remains the documented full opt-out
Groundwork's documentation SHALL continue to name `claude plugin disable ecc@ecc` (and `claude plugin enable ecc@ecc` to restore it) as the supported way to remove ECC's footprint entirely, since no finer-grained curation is available.

#### Scenario: Opt-out
- **WHEN** an engineer wants zero ECC footprint (cost or otherwise)
- **THEN** `docs/TROUBLESHOOTING.md` documents `claude plugin disable ecc@ecc` as the supported mechanism, and no other, unimplemented curation flag is referenced anywhere in Groundwork's docs

### Requirement: skillOverrides is documented as confirmed ineffective for ECC, not pending
`docs/TROUBLESHOOTING.md` and `docs/VALIDATION.md` SHALL state that `skillOverrides` does not affect ECC's (plugin-provided) skills as a **confirmed, source-verified fact** (installed Claude Code CLI version noted), not as an assumption or an open question.

#### Scenario: Documentation matches verified behavior
- **WHEN** an engineer reads `docs/TROUBLESHOOTING.md`'s context-cost section
- **THEN** it states plainly that `skillOverrides` has no effect on ECC's plugin-provided skills, with the Claude Code version this was verified against, and does not suggest trying it as a cost-reduction lever

### Requirement: Context-cost is measured and documented, not estimated
The capability that ships from this specification SHALL be accompanied by a measured (not estimated) session-start token cost for the full ECC install, since no curated-vs-full comparison is possible.

#### Scenario: Cost evidence recorded
- **WHEN** this phase ships
- **THEN** `docs/VALIDATION.md` records the measured session-start token cost of the full ECC install (from `claude plugin details ecc@ecc`'s "Always-on" total), states plainly that no curated alternative exists today, and names the two real levers available (`hook_profile`, whole-plugin disable)

### Requirement: No hard-coded ECC roster is treated as authoritative
Nothing in Groundwork's rules, hooks, or scripts SHALL hard-code a specific ECC skill/agent name list as if it were the permanently-installed set, since ECC installs unpinned from `main` and its content changes independently of Groundwork releases.

#### Scenario: Builder-capability reasoning stays roster-independent
- **WHEN** `rules/engineering-workflow.md` or a playbook references what ECC does or does not provide (e.g. "ECC has no Terraform/cloud-provider capability")
- **THEN** the reference is to a *category* of capability confirmed absent by direct inspection at implementation time, not to a specific counted catalog that could silently go stale as ECC's `main` branch moves
