## ADDED Requirements

### Requirement: ECC is installed pinned to a tested ref, not floating `main`
`install.sh` SHALL install ECC via `claude plugin marketplace add affaan-m/ECC#<ref>` with a specific, previously-tested ref (not `main`), SHALL allow overriding that ref via `GROUNDWORK_ECC_REF` for a specific machine, and SHALL document that bumping the pinned ref requires re-testing clean install/upgrade/rollback/uninstall against the new tag.

#### Scenario: Default pinned install
- **WHEN** `install.sh` runs with `GROUNDWORK_ECC_REF` unset
- **THEN** it installs ECC pinned to the ref hardcoded as `ECC_REF`'s default (`v2.2.1` as of this change), not `main`

#### Scenario: Override for a specific machine
- **WHEN** `GROUNDWORK_ECC_REF=main ./install.sh` is run
- **THEN** ECC installs tracking `main`, overriding the default pin

### Requirement: Verification reports pin status accurately, not generic drift
`setup.sh --verify`/`--doctor` SHALL compare the installed ECC version against the same `ECC_REF` pin `install.sh` uses, SHALL still PASS (not FAIL) when the installed version differs from the pin — since a manual `claude plugin update` outside the pin is not a broken install — but SHALL name the pin and the mismatch distinctly from the matching case, rather than reporting unpinned "drift is normal" for a project that has pinned ECC.

#### Scenario: Version matches the pin
- **WHEN** `claude plugin list` reports the ECC version equal to `ECC_REF`
- **THEN** the ECC row PASSes with a message naming it as pinned, with no "differs" note

#### Scenario: Version differs from the pin
- **WHEN** `claude plugin list` reports an ECC version different from `ECC_REF`
- **THEN** the ECC row still PASSes (not FAIL — this is not necessarily a broken install), naming the pin and that the installed version differs from it, likely from a manual update outside the pin
