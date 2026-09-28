## 0. Audit and design (this change's current scope — both passes)

### First pass (core harness audit)
- [x] 0.1 Read README, ARCHITECTURE, VALIDATION, TROUBLESHOOTING, UPGRADE-ROLLBACK, FUTURE-SCOPE, CHANGELOG, CREDITS in full
- [x] 0.2 Read all 5 rules files and all 10 playbooks in full
- [x] 0.3 Independently audit all 4 hooks and 5 scripts against their actual source (not docs claims)
- [x] 0.4 Independently audit install.sh/uninstall.sh/setup.sh version-check and idempotency logic against actual source
- [x] 0.5 Independently audit all 5 test files for coverage gaps (continuity, conflicting evidence, telemetry privacy)
- [x] 0.6 Repo-wide search for hardcoded personal/machine identity
- [x] 0.7 Verify OpenSpec's current Node.js requirement against primary upstream sources
- [x] 0.8 Verify ECC's current agent/skill counts against the actual published npm package
- [x] 0.9 Verify current Claude Code plugin/skill selective-enablement mechanisms against official docs
- [x] 0.10 Verify ECC's real agent/skill name list for the capability-matrix tables (checksum-verified npm tarball; 286 skills / 68 agents, real names, grouped and summed)
- [x] 0.11 Inspect `openspec/changes/` for an existing Groundwork 2.0 change before creating this one (found `intelligent-engineering-harness`, a predecessor — not a duplicate)
- [x] 0.12 Write first-pass proposal.md, design.md, tasks.md

### Second pass (builders, SRE consolidation, presentation, teach/learn, D3/D5 redesign)
- [x] 0.13 Re-read the existing OpenSpec change in full before extending it (not creating a second one)
- [x] 0.14 Verify Claude Code's native output-styles mechanism against current official docs (file location, invocation, enforcement status, replace-vs-layer behavior)
- [x] 0.15 Verify Claude Code CLI's native presentation/document-generation capability against current official docs — corrected an initial assumption: Artifacts DO exist in CLI, gated by plan/login/provider, not by CLI-vs-web; confirmed the first-party `document-skills` plugin (docx/pdf/pptx/xlsx) is installable in plain CLI with no such gate
- [x] 0.16 Design repository-understanding as a shared capability extending existing playbooks, confirming no new always-loaded rule is needed
- [x] 0.17 Design the four builder execution roles as dynamic personas, confirming no permanent agent files or new task-routing category is needed
- [x] 0.18 Analyze ~20 SRE capabilities named in the brief against existing composable capabilities, confirming zero new files are needed for SRE consolidation
- [x] 0.19 Design presentation/output-style/teach-learn architecture composing native mechanisms and existing playbooks
- [x] 0.20 Build the comprehensive capability-ownership matrix (`design.md` §J) auditing every proposed and existing capability for duplicate ownership
- [x] 0.21 Redesign D3 (review evidence) after confirming the first pass's "any tool call" proposal was too weak — new design reuses the existing `Harness metadata` block pattern and `groundwork_telemetry.py`'s `TEST_CMD` regex
- [x] 0.22 Redesign D5 (deterministic safety) into a tiered, builder-aware menu after confirming the first pass's single vague candidate was not concrete enough to approve
- [x] 0.23 Re-evaluate the migration plan into 5 dependency-ordered stages (Foundation/Trust/Capability/Experience/Validation) rather than appending new work as one undifferentiated phase
- [x] 0.24 Write the extended design.md, updated proposal.md, this tasks.md, and 4 new capability specs; redesign 2 existing specs (review-evidence-strengthening, deterministic-safety-expansion); light-touch 1 existing spec (investigation-continuity, field-list alignment)
- [ ] 0.25 Owner review and sign-off on all Decisions (D1-D5) and the full 13-phase order in design.md §K (**STOP POINT — nothing below this line may start until this task is checked by the owner**)

---

Everything below is **planned, not implemented**. Nothing is checked. Each phase gets its own `/opsx:apply` pass, its own independent review, and its own `docs/VALIDATION.md` entry when it actually ships. A task here is complete only when its stated evidence exists, not when this checklist is edited.

## STAGE 1 — FOUNDATION

### Phase 1 — Correctness fixes (Decision D1, approved-as-proposed; no owner fork)
- [ ] 1.1 Correct the documented Node floor (README.md, install.sh error text, setup.sh, docs/ARCHITECTURE.md) from "≥18" to "≥20.19.0"
- [ ] 1.2 Add an actual Node version-number check to `install.sh` (currently checks presence only)
- [ ] 1.3 Extract `dirty_change_names()` from `hooks/require_material_review.py` and `hooks/groundwork_session_snapshot.py` into one shared helper
- [ ] 1.4 Refresh ECC (2.2.1, npm-published) and OpenSpec (1.13.2) version references; note the ECC GitHub-main-vs-npm-publish drift risk
- [ ] 1.5 New/extended test: `install.sh` refuses on a stubbed Node <20.19.0 with a clear message
- [ ] 1.6 Non-regression: full existing suite green plus new cases
- [ ] 1.7 Independent fresh-context review (MATERIAL — touches install.sh)
- [ ] 1.8 CHANGELOG entry explicit that this corrects a pre-existing bug, not a new requirement
- [ ] 1.9 docs/VALIDATION.md entry

### Phase 2 — Evidence taxonomy (rule text only)
- [ ] 2.1 Add `CONFLICTING EVIDENCE` and `UNKNOWN` to `rules/evidence-policy.md` §2
- [ ] 2.2 Tighten §7 RCA rule to require one of the two new labels when applicable
- [ ] 2.3 Cross-reference from `playbooks/troubleshoot.md` and `playbooks/research.md`
- [ ] 2.4 docs/ARCHITECTURE.md updated
- [ ] 2.5 Model-behavior validation on constructed genuinely-UNKNOWN and genuinely-CONFLICTING prompts
- [ ] 2.6 Non-regression check
- [ ] 2.7 docs/VALIDATION.md entry

### Phase 3 — Capability ownership documentation (new this pass, cheap)
- [ ] 3.1 Fold design.md §J's capability-ownership matrix into `docs/ARCHITECTURE.md`
- [ ] 3.2 Confirm `architecture-quality.md` §4's existing "no abstraction without a concrete reason" rule is cross-referenced as the anti-fragmentation principle (no new rule mechanism)
- [ ] 3.3 docs/VALIDATION.md entry (documentation-only change; non-regression check suffices as evidence)

## STAGE 2 — TRUST

### Phase 4 — Review evidence strengthening, redesigned (Decision D3)
- [ ] 4.1 Add the structured `REVIEW RESULT` block format to `rules/output-contract.md`
- [ ] 4.2 RUNTIME VALIDATION REQUIRED: sample real ECC/subagent/teammate reviewer output to confirm the block can be reliably prompted/emitted
- [ ] 4.3 Extend `hooks/require_material_review.py` to parse the block; on `Must-fix: N>0`, require both a post-review edit AND a post-review test/validation-shaped Bash call (reusing `groundwork_telemetry.py`'s `TEST_CMD` regex) before allowing Stop
- [ ] 4.4 Update `rules/engineering-workflow.md` §2.6 to state the strengthened expectation
- [ ] 4.5 New `test_hooks.py` cases per `specs/review-evidence-strengthening/spec.md` (no-follow-up blocks; edit-only-no-validation-rerun blocks; edit-plus-validation-rerun allows; zero-MUST-FIX/absent-block unchanged) — must not regress the existing 14 review-gate cases
- [ ] 4.6 Independent fresh-context review (MATERIAL — modifies an enforced safety hook)
- [ ] 4.7 docs/VALIDATION.md entry with real transcript evidence

### Phase 5 — Investigation continuity (Decision D2)
- [ ] 5.1 Owner picks Option A or Option B (design.md §M/D2)
- [ ] 5.2 Implement the chosen option
- [ ] 5.3 If Option B: add the new file to install.sh/uninstall.sh's managed set and to the telemetry-privacy review
- [ ] 5.4 New deterministic test suite: constructed long investigation, simulated compaction, fresh-session recovery
- [ ] 5.5 **Critical named test case**: a rejected hypothesis must not become active or verified after recovery
- [ ] 5.6 Test: stale saved state vs. current repository/runtime — repository wins, mismatch reported
- [ ] 5.7 Independent fresh-context review (MATERIAL)
- [ ] 5.8 docs/VALIDATION.md entry with actual constructed-scenario transcripts

### Phase 6 — Deterministic safety expansion, redesigned and tiered (Decision D5)
- [ ] 6.1 Owner explicitly names which Tier-2 candidate(s) to approve: none / Terraform-prod-guard / kubectl-prod-guard / IAM-mutation-guard / any combination — **do not proceed on an inferred scope**
- [ ] 6.2 Per approved candidate: implement the narrowly-scoped hook, structurally mirroring `block_protected_push.py`
- [ ] 6.3 Per approved candidate: adversarial bypass test pass
- [ ] 6.4 Per approved candidate: false-positive test pass (legitimate commands that must NOT be blocked), reviewed by a security-reviewer for over-blocking risk
- [ ] 6.5 Per approved candidate: `GROUNDWORK_<HOOK_NAME>=off` escape hatch
- [ ] 6.6 Per approved candidate: document the production-naming-detection limitation plainly
- [ ] 6.7 Independent fresh-context review per candidate — code, security, and an explicit false-positive check against this repo's own command history
- [ ] 6.8 docs/VALIDATION.md entry per candidate with both bypass and false-positive evidence shown

## STAGE 3 — CAPABILITY

### Phase 7 — ECC capability policy (Decision D4)
- [ ] 7.1 Translate design.md §D.2/D.3's verified category data into the actual `--profile`/`--with capability:*` flag set for `install.sh`
- [ ] 7.2 RUNTIME VALIDATION REQUIRED: live-test whether `skillOverrides` suppresses auto-invocation of a plugin-provided (ECC) skill; update `docs/TROUBLESHOOTING.md`'s existing claim either way
- [ ] 7.3 Add `--ecc-profile full` opt-out flag to `install.sh`
- [ ] 7.4 If 7.2 confirms plugin-skill scoping works: add `skillOverrides` entries via `scripts/merge_settings.py`
- [ ] 7.5 New install-layout tests; live/runtime test confirming a curated-out capability is not auto-invoked and a CORE SRE capability still is
- [ ] 7.6 Context-cost measurement: before/after token cost at session start
- [ ] 7.7 Cross-check against §D.5's builder-capability sourcing table — confirm no builder role needs a capability outside the recommended default set
- [ ] 7.8 Independent fresh-context review (MATERIAL — changes default installed capability set)
- [ ] 7.9 docs/VALIDATION.md entry; README/ARCHITECTURE updated

### Phase 8 — Repository understanding (new this pass)
- [ ] 8.1 Extend `playbooks/implement.md`, `playbooks/deploy.md`, `playbooks/design.md` with the domain-specific discovery checklist (§E.2), referencing `architecture-quality.md` §5 rather than restating it
- [ ] 8.2 Model-behavior validation: the "repository pattern vs. generic knowledge" and "rejected unsafe pattern" scenarios from design.md §L.2, run live against fixture repositories
- [ ] 8.3 Non-regression check (playbooks stay within their existing size discipline; no new always-loaded file)
- [ ] 8.4 Independent fresh-context review
- [ ] 8.5 docs/VALIDATION.md entry with the fixture-repository transcripts

### Phase 9 — Builder execution roles (new this pass)
- [ ] 9.1 Add the four role personas and the automatic orchestration extension to `rules/engineering-workflow.md` §6
- [ ] 9.2 Add the MCP/tool-access policy subsection (§F.5) to the same section
- [ ] 9.3 Add the closed-loop troubleshoot-and-revalidate line to `playbooks/deploy.md`
- [ ] 9.4 Confirm (no file change expected) that `evidence-policy.md` §6's existing completion-evidence table needs no builder-specific status vocabulary; add illustrative example rows to `deploy.md`'s Output Format only if genuinely useful
- [ ] 9.5 Model-behavior validation: the "repository-aware infra build," "platform onboarding," "delivery," "cross-domain build," "nonprod deployment," and "no authorization" scenarios from design.md §L.2, run live
- [ ] 9.6 Independent fresh-context review (MATERIAL)
- [ ] 9.7 docs/VALIDATION.md entry with live scenario transcripts
- [ ] 9.8 Depends on: Phase 7 (curated ECC composition) and Phase 8 (shared discovery) — do not start before both ship

## STAGE 4 — EXPERIENCE

### Phase 10 — Output-style and presentation architecture (new this pass)
- [ ] 10.1 RUNTIME VALIDATION REQUIRED: confirm whether selecting a non-Default output style affects `~/.claude/rules/**/*.md` loading, before any Groundwork-authored style file ships
- [ ] 10.2 Add the truth/style separation invariant to `rules/output-contract.md`
- [ ] 10.3 Add the presentation branch to `playbooks/document.md` (source-of-truth rule, portable-format default, optional `document-skills` plugin usage)
- [ ] 10.4 Model-behavior validation: the "presentation truth" and "output style invariance" scenarios from design.md §L.2
- [ ] 10.5 Independent fresh-context review
- [ ] 10.6 docs/VALIDATION.md entry
- [ ] 10.7 (OPTIONAL/LATER, not scheduled this phase) author Groundwork-provided output-style presets and the presentation design-system template — only after 10.1's runtime check and only if a real presentation task exposes what the template actually needs

### Phase 11 — Teach/learn capability (new this pass)
- [ ] 11.1 Extend `playbooks/explain.md` with the teach-from-verified-work branch
- [ ] 11.2 Model-behavior validation: complete-evidence and unavailable-prior-session scenarios
- [ ] 11.3 Non-regression check (no new storage introduced)
- [ ] 11.4 docs/VALIDATION.md entry

## STAGE 5 — VALIDATION

### Phase 12 — End-to-end acceptance scenarios
- [ ] 12.1 Run every scenario in design.md §L.2 as live/model-behavior evidence, matching docs/VALIDATION.md's existing discipline (real transcripts, not just pass counts)
- [ ] 12.2 Run the "deduplication" scenario explicitly: for each new capability shipped, confirm its independent review checked the diff against §J's ownership matrix
- [ ] 12.3 docs/VALIDATION.md entry consolidating all Stage 1-4 evidence into one coherent release record

### Phase 13 — Cross-phase regression gate (run once, after the last approved phase ships)
- [ ] 13.1 Every pre-existing critical file's behavior re-verified against its pre-2.0 baseline where unchanged by an approved phase
- [ ] 13.2 Full existing test suite plus all new tests from shipped phases green in one run
- [ ] 13.3 Upgrade path tested: a real 1.5.1 installation upgraded via `git pull && ./setup.sh` (or `install.sh`) to 2.0, verified idempotent and non-destructive
- [ ] 13.4 Rollback tested: `./setup.sh --rollback` restores a pre-2.0 state cleanly
- [ ] 13.5 Uninstall tested: `./uninstall.sh` removes exactly what 2.0 added (including any Phase 6 hooks and any Phase 5 state file), keeps telemetry/reports
- [ ] 13.6 Documentation matches actual shipped behavior for every phase that shipped
- [ ] 13.7 No completion claim in any shipped phase's VALIDATION.md entry exceeds its actual evidence
- [ ] 13.8 `openspec validate groundwork-2-enterprise-sre --strict`
