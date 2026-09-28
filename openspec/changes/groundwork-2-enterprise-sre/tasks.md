## 0. Audit and design (this change's current scope)

- [x] 0.1 Read README, ARCHITECTURE, VALIDATION, TROUBLESHOOTING, UPGRADE-ROLLBACK, FUTURE-SCOPE, CHANGELOG, CREDITS in full
- [x] 0.2 Read all 5 rules files and all 10 playbooks in full
- [x] 0.3 Independently audit all 4 hooks and 5 scripts against their actual source (not docs claims)
- [x] 0.4 Independently audit install.sh/uninstall.sh/setup.sh version-check and idempotency logic against actual source
- [x] 0.5 Independently audit all 5 test files for coverage gaps (continuity, conflicting evidence, telemetry privacy)
- [x] 0.6 Repo-wide search for hardcoded personal/machine identity
- [x] 0.7 Verify OpenSpec's current Node.js requirement against primary upstream sources
- [x] 0.8 Verify ECC's current agent/skill counts against the actual published npm package
- [x] 0.9 Verify current Claude Code plugin/skill selective-enablement mechanisms against official docs
- [x] 0.10 Verify ECC's real agent/skill name list for the §D.2/D.3 capability-matrix tables (checksum-verified npm tarball; 286 skills / 68 agents, real names, grouped and summed)
- [x] 0.11 Inspect `openspec/changes/` for an existing Groundwork 2.0 change before creating this one (found `intelligent-engineering-harness`, a predecessor — not a duplicate; see design.md §H item 1)
- [x] 0.12 Write proposal.md, design.md (current-state audit, gap analysis, target architecture, ECC matrix, migration plan, decisions, risks), this tasks.md
- [ ] 0.13 Owner review and sign-off on Decisions D1-D5 and the phase order in design.md §E (**STOP POINT — nothing below this line may start until this task is checked by the owner**)

---

Everything below is **planned, not implemented**. Nothing is checked. Each phase gets its own `/opsx:apply` pass, its own independent review, and its own `docs/VALIDATION.md` entry when it actually ships — matching how every prior Groundwork capability shipped. A task here is complete only when its stated evidence exists, not when this checklist is edited.

## 1. Phase 1 — Correctness fixes (Decision D1, approved-as-proposed; no owner fork)

- [ ] 1.1 Correct the documented Node floor (README.md, install.sh error text, setup.sh, docs/ARCHITECTURE.md) from "≥18" to "≥20.19.0", citing OpenSpec's verified `engines.node` requirement
- [ ] 1.2 Add an actual Node version-number check to `install.sh` (currently checks presence only) — fail with a clear message before any other install step runs
- [ ] 1.3 Extract `dirty_change_names()` from `hooks/require_material_review.py` and `hooks/groundwork_session_snapshot.py` into one shared helper; both hooks import it; no behavior change
- [ ] 1.4 Refresh ECC (2.2.1, npm-published) and OpenSpec (1.13.2) version references in README.md, docs/ARCHITECTURE.md, CHANGELOG.md; note the ECC GitHub-main-vs-npm-publish drift risk in docs/ARCHITECTURE.md
- [ ] 1.5 New/extended test: `install.sh` refuses on a stubbed Node <20.19.0 with a clear message and makes no other change (mirrors the existing `setup.sh` old-Node test pattern)
- [ ] 1.6 Non-regression: re-run the full existing suite (`test_hooks.py`, `test_playbooks.py`, `test_report.py`, `test_setup.py`, `test_telemetry.py`, `pytest tests -q`) and confirm all currently-passing counts hold plus the new cases
- [ ] 1.7 Independent fresh-context review (MATERIAL tier — touches install.sh, a user-facing behavior change)
- [ ] 1.8 CHANGELOG entry explicit that this corrects a pre-existing bug (Node floor was always wrong), not a new requirement
- [ ] 1.9 docs/VALIDATION.md entry with the live evidence (stubbed old-Node install run, real install run against a compliant Node)

## 2. Phase 2 — Evidence taxonomy (rule text only)

- [ ] 2.1 Add `CONFLICTING EVIDENCE` and `UNKNOWN` to `rules/evidence-policy.md` §2's label set, with a one-line definition matching the requesting brief's distinction (UNKNOWN = cannot be determined at all; CONFLICTING EVIDENCE = two or more sources disagree and neither dominates by the §1 priority order)
- [ ] 2.2 Tighten `rules/evidence-policy.md` §7 RCA rule to require one of the two new labels when the evidence chain does not support a root cause, instead of only "say hypothesis"
- [ ] 2.3 Cross-reference the new labels from `playbooks/troubleshoot.md` and `playbooks/research.md` (reference only — do not restate the rule, matching the existing inheritance pattern)
- [ ] 2.4 docs/ARCHITECTURE.md: note the extended label set in the evidence-policy row
- [ ] 2.5 Model-behavior validation: representative TROUBLESHOOT/RESEARCH prompts constructed so the correct answer is genuinely UNKNOWN or genuinely CONFLICTING, confirm the label is used correctly and not silently upgraded to a confident answer (matches the validation style used for every prior rule-text-only change in docs/VALIDATION.md)
- [ ] 2.6 Non-regression: SHA-256 baseline check that no other rule/hook/script changed
- [ ] 2.7 docs/VALIDATION.md entry

## 3. Phase 3 — Review evidence strengthening (Decision D3)

- [ ] 3.1 Owner confirms the narrow D3 approach (extend existing hook's transcript scan; do not build structured findings storage) or requests a different scope
- [ ] 3.2 RUNTIME VALIDATION REQUIRED: sample real ECC/subagent/teammate reviewer output for MUST-FIX vocabulary consistency before committing to a specific text match
- [ ] 3.3 Extend `hooks/require_material_review.py`: after a review-shaped call is found, if its output can be located and contains a MUST-FIX-shaped marker, also require at least one tool call after it before allowing Stop
- [ ] 3.4 Update `rules/engineering-workflow.md` §2.6 to state the strengthened expectation in rule text
- [ ] 3.5 New `test_hooks.py` cases: MUST-FIX review immediately followed by Stop (block), MUST-FIX review followed by an edit then Stop (allow), review with no MUST-FIX language (allow, unchanged from today) — must not regress any of the 14 existing review-gate cases
- [ ] 3.6 Independent fresh-context review (MATERIAL — modifies an enforced safety hook)
- [ ] 3.7 docs/VALIDATION.md entry with real transcript evidence

## 4. Phase 4 — ECC capability policy (Decision D4)

- [ ] 4.1 Translate design.md §D.2/D.3's now-verified category data into the actual `--profile`/`--with capability:*` flag set (task 0.10 is complete; this task is pure translation, not further research)
- [ ] 4.2 RUNTIME VALIDATION REQUIRED: live-test whether `skillOverrides` suppresses auto-invocation of a plugin-provided (ECC) skill on the current Claude Code version; record the result and update docs/TROUBLESHOOTING.md's existing (possibly stale) claim either way
- [ ] 4.3 Define the default SRE/CloudOps profile using ECC's own `--profile`/`--with capability:*` install-time flags in `install.sh`; add `--ecc-profile full` as an explicit opt-out to today's wholesale install
- [ ] 4.4 If 4.2 confirms plugin-skill scoping works: add `skillOverrides` entries via `scripts/merge_settings.py` for finer-grained defaults beyond ECC's own categories
- [ ] 4.5 New install-layout tests: profile flag reaches ECC's installer correctly; uninstall/reinstall with a different profile behaves idempotently
- [ ] 4.6 Live/runtime test: confirm a capability excluded by the default profile is genuinely not auto-invoked in a fresh session; confirm a CORE SRE capability still is
- [ ] 4.7 Context-cost measurement: before/after token cost at session start with the curated profile vs. today's full install (this is the evidence for acceptance criterion #12, "unnecessary context minimized")
- [ ] 4.8 Independent fresh-context review (MATERIAL — changes default installed capability set)
- [ ] 4.9 docs/VALIDATION.md entry; README/ARCHITECTURE updated with the new default and the opt-out flag

## 5. Phase 5 — Investigation continuity (Decision D2)

- [ ] 5.1 Owner picks Option A (extend existing convention-based model) or Option B (new capped state artifact) from design.md D2
- [ ] 5.2 Implement the chosen option (scope depends entirely on 5.1's outcome — see design.md §C/§E for what changes under each)
- [ ] 5.3 If Option B: add the new file to install.sh/uninstall.sh's managed set, and to the telemetry-privacy review (must never contain secrets; capped size matching the snapshot hook's discipline)
- [ ] 5.4 New deterministic test suite (both options need this): a constructed long session with multiple established facts, multiple rejected hypotheses, several decisions, changed files, validation results, and unresolved work; simulate compaction; verify DONE/PARTIAL/MISSING/BLOCKED/UNVERIFIED table reconstruction
- [ ] 5.5 New deterministic test: fresh-session recovery (Session A investigates/decides/partially implements/stops; Session B continues) — verify the recovered workflow correctly determines objective, completed work, remaining work, proven facts, unverified facts, rejected hypotheses, decisions, and next action
- [ ] 5.6 **Critical named test case** (requesting brief §9, explicit requirement): a rejected hypothesis must not become active or verified after recovery — construct the scenario, assert it directly, do not rely on it being implied by other tests
- [ ] 5.7 Test: stale saved state vs. current repository/runtime — repository wins, mismatch is reported (both options must satisfy this, since it is an existing Groundwork principle being extended, not a new one)
- [ ] 5.8 Independent fresh-context review (MATERIAL)
- [ ] 5.9 docs/VALIDATION.md entry with the actual constructed-scenario transcripts, not just the test pass count

## 6. Phase 6 — Deterministic safety expansion (Decision D5) — only if the owner approves a scope

- [ ] 6.1 Owner explicitly names the scope (none / narrow-IaC-apply-without-plan / a specific named list of destructive cloud-CLI patterns) — **do not proceed on an inferred scope**
- [ ] 6.2 Implement the narrowly-scoped hook, structurally mirroring `block_protected_push.py` (fail-open, depth-limited shell/eval parsing, exact pattern match, documented known limitations)
- [ ] 6.3 Adversarial test pass: reproduce every bypass class analogous to the ones found against the original push guard (nested shells, eval, wrapper commands)
- [ ] 6.4 **False-positive test pass** (this phase's distinguishing requirement vs. every other phase): a representative set of legitimate, safe commands that must NOT be blocked, reviewed by a security-reviewer for over-blocking risk specifically, not just under-blocking
- [ ] 6.5 `GROUNDWORK_<HOOK_NAME>=off` escape hatch, matching the existing opt-out pattern
- [ ] 6.6 Independent fresh-context review — code, security, and an explicit "would this have false-positived on a real legitimate command from this repo's own history" check
- [ ] 6.7 docs/VALIDATION.md entry with both the bypass and false-positive evidence shown, not just "tests pass"

## 7. Cross-phase regression gate (run once, after the last approved phase ships)

- [ ] 7.1 Every pre-existing critical file's behavior re-verified against its pre-2.0 baseline where unchanged by an approved phase (SHA-256 or equivalent, matching the pattern used in every prior Groundwork release)
- [ ] 7.2 Full existing test suite plus all new tests from shipped phases green in one run
- [ ] 7.3 Upgrade path tested: a real 1.5.1 installation upgraded via `git pull && ./setup.sh` (or `install.sh`) to 2.0, verified idempotent and non-destructive
- [ ] 7.4 Rollback tested: `./setup.sh --rollback` restores a pre-2.0 state cleanly
- [ ] 7.5 Uninstall tested: `./uninstall.sh` removes exactly what 2.0 added, keeps telemetry/reports
- [ ] 7.6 Documentation (README, ARCHITECTURE, VALIDATION, TROUBLESHOOTING, UPGRADE-ROLLBACK, FUTURE-SCOPE, CHANGELOG) matches actual shipped behavior for every phase that shipped
- [ ] 7.7 No completion claim in any shipped phase's VALIDATION.md entry exceeds its actual evidence (self-check against this document's own evidence-first premise)
- [ ] 7.8 `openspec validate groundwork-2-enterprise-sre --strict`
