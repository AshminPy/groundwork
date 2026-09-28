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
- [x] 0.25 Owner review and sign-off on all Decisions (D1-D5) and the full 13-phase order in design.md §K — **SIGNED OFF 2026-09-28** via the owner's explicit implementation-authorization message: D1 approved as proposed; D2 approved as Option B (bounded investigation-state artifact, exact field list given); D3 approved **with further strengthening** beyond this document's own redesign (fresh independent re-review required after a MUST-FIX fix, not just edit+test — see the correction notice in `specs/review-evidence-strengthening/spec.md` and `design.md` §M/D3); D4 approved as proposed (curate via upstream mechanisms only after validating them against the actually-installed version, full opt-out retained — see the M4 correction for what "validating" actually found); D5 explicitly deferred (Tier-2 guards not implemented this release, documented as deferred candidates, not blocking). The 13-phase order was authorized to proceed autonomously, phase by phase, without per-phase re-approval.

---

Everything below is **planned, not implemented**. Nothing is checked. Each phase gets its own `/opsx:apply` pass, its own independent review, and its own `docs/VALIDATION.md` entry when it actually ships. A task here is complete only when its stated evidence exists, not when this checklist is edited.

## STAGE 1 — FOUNDATION

### Phase 1 — Correctness fixes (Decision D1, approved-as-proposed; no owner fork)
- [ ] 1.1 Correct the documented Node floor (README.md, install.sh error text, setup.sh, docs/ARCHITECTURE.md) from "≥18" to "≥20.19.0"
- [ ] 1.2 Add an actual Node version-number check to `install.sh` (currently checks presence only)
- [ ] 1.3 Extract `dirty_change_names()` from `hooks/require_material_review.py` and `hooks/groundwork_session_snapshot.py` into one shared helper
- [x] 1.4 Refresh ECC and OpenSpec version references — CORRECTED SCOPE (finding M4): ECC is not npm-published to Groundwork at all; it installs unpinned from GitHub `main` via `claude plugin marketplace add`/`claude plugin install` (verified 2.2.2 at investigation time). `docs/ARCHITECTURE.md` and `setup.sh`'s `LAST_VERIFIED_ECC` corrected accordingly; OpenSpec refreshed to 1.13.2 (genuinely npm-published, verified)
- [ ] 1.5 New/extended test: `install.sh` refuses on a stubbed Node <20.19.0 with a clear message
- [ ] 1.6 Non-regression: full existing suite green plus new cases
- [ ] 1.7 Independent fresh-context review (MATERIAL — touches install.sh)
- [ ] 1.8 CHANGELOG entry explicit that this corrects a pre-existing bug, not a new requirement
- [ ] 1.9 docs/VALIDATION.md entry

### Phase 2 — Evidence taxonomy (rule text only)
- [x] 2.1 Add `CONFLICTING EVIDENCE` and `UNKNOWN` to `rules/evidence-policy.md` §2
- [x] 2.2 Tighten §7 RCA rule to require one of the two new labels when applicable
- [x] 2.3 Cross-reference from `playbooks/troubleshoot.md` and `playbooks/research.md`
- [x] 2.4 docs/ARCHITECTURE.md updated
- [x] 2.5 Model-behavior validation on constructed genuinely-UNKNOWN and genuinely-CONFLICTING prompts
- [x] 2.6 Non-regression check
- [x] 2.7 docs/VALIDATION.md entry

### Phase 3 — Capability ownership documentation (new this pass, cheap)
- [x] 3.1 Fold design.md §J's capability-ownership matrix into `docs/ARCHITECTURE.md`
- [x] 3.2 Confirm `architecture-quality.md` §4's existing "no abstraction without a concrete reason" rule is cross-referenced as the anti-fragmentation principle (no new rule mechanism)
- [x] 3.3 docs/VALIDATION.md entry (documentation-only change; non-regression check suffices as evidence)

## STAGE 2 — TRUST

### Phase 4 — Review evidence strengthening, redesigned (Decision D3)
- [x] 4.1 Add the structured `REVIEW RESULT` block format to `rules/output-contract.md`
- [x] 4.2 RUNTIME VALIDATION REQUIRED: sample real ECC/subagent/teammate reviewer output to confirm the block can be reliably prompted/emitted — **RESOLVED**: two live `claude -p` sessions, isolated `CLAUDE_CONFIG_DIR` with only `output-contract.md` + `engineering-workflow.md` installed as rules, prompted only with the reviewer's *role* ("independent fresh-context reviewer for a MATERIAL change") and no mention of the block format. Both sessions — one reviewing a clean diff, one reviewing a diff with a real bug — organically emitted the `REVIEW RESULT` block in the exact defined shape (`Verdict: approve`/`Must-fix: 0` and `Verdict: changes-required`/`Must-fix: 1` respectively), plus the `HARNESS METADATA` block, purely from the loaded rule text. See docs/VALIDATION.md for the transcripts.
- [x] 4.3 Extend `hooks/require_material_review.py` to parse the block; on `Must-fix: N>0`, evaluate the most recent review-shaped call's own verdict — a post-review edit and a post-review test/validation-shaped Bash call (reusing `groundwork_telemetry.py`'s `TEST_CMD` regex) are shown as diagnostics but are NOT sufficient alone; Stop stays blocked until a subsequent fresh review itself reports `Must-fix: 0` (strengthened beyond this task's original wording per the owner's implementation-authorization message — see `specs/review-evidence-strengthening/spec.md`'s correction notice)
- [x] 4.4 Update `rules/engineering-workflow.md` §2.6 to state the strengthened expectation
- [x] 4.5 New `test_hooks.py` cases per `specs/review-evidence-strengthening/spec.md` (no-follow-up blocks; edit-only-no-validation-rerun blocks; edit-plus-validation-rerun-no-fresh-review still blocks; fresh-review-confirms allows; zero-MUST-FIX/absent-block unchanged) — no regression in the existing 14 review-gate cases
- [x] 4.6 Independent fresh-context review (MATERIAL — modifies an enforced safety hook) — three rounds; see docs/VALIDATION.md
- [x] 4.7 docs/VALIDATION.md entry with real transcript evidence

### Phase 5 — Investigation continuity (Decision D2)
- [x] 5.1 Owner picks Option A or Option B (design.md §M/D2) — **Option B**, per the owner's implementation-authorization message
- [x] 5.2 Implement the chosen option — `hooks/groundwork_session_snapshot.py` extended: `investigation_path()` computes a deterministic per-repo path under `~/.claude/groundwork/investigations/`; `investigation_facts()` surfaces its content (capped, truncated with its own marker) inside the existing untrusted-data envelope, with the rejected-stays-rejected instruction attached. `engineering-workflow.md` §7 extended with the exact field-list template and the writing/reopening rules. No new hook, no new script — reuses the existing SessionStart mechanism exactly (composition, not a new capability)
- [x] 5.3 Not a new managed file for install.sh/uninstall.sh (nothing is installed — the directory is created lazily by the model's own `Write` the first time it's used, exactly like `telemetry/`/`reports/`); uninstall.sh's "kept, it's your data" messaging extended to name `investigations/` alongside `telemetry/`/`reports/`, and confirmed preserved on uninstall by test. No new privacy concern beyond what already applies to telemetry: local-only, never transmitted, entirely the model's own summary of the user's own repository
- [x] 5.4 New deterministic test suite (`test_hooks.py::test_investigation_continuity`, 11 cases): path determinism, no-file/empty-file/oversized-file handling with correct truncation, non-git-dir graceful no-op, same-basename-different-repo path collision avoidance
- [x] 5.5 **Critical named test case**: a rejected hypothesis must not become active or verified after recovery — **live-tested against a real `claude -p` session** (not simulated): a fresh session given a saved investigation file with one rejected and one active hypothesis explicitly kept the rejected one rejected ("stays rejected... No new evidence reopens this"), independently re-verified the active hypothesis against the actual repository code before treating it as confirmed. A second live scenario confirmed the *positive* case is not over-broad: new evidence that does not actually contradict the original rejection reason correctly does NOT reopen it, with the model explaining why. See docs/VALIDATION.md for both transcripts
- [x] 5.6 Test: stale saved state vs. current repository/runtime — repository wins, mismatch reported — covered by the same live scenario (5.5): the model re-verified the recovered "active hypothesis" against current code rather than repeating it as fact, per `evidence-policy.md` §8, before reporting it as confirmed
- [ ] 5.7 Independent fresh-context review (MATERIAL)
- [x] 5.8 docs/VALIDATION.md entry with actual constructed-scenario transcripts

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

### Phase 7 — ECC capability policy (Decision D4) — CORRECTED SCOPE (finding M4, resolved during Phase 1 implementation)
Original tasks 7.1/7.3/7.4 assumed install-time skill/agent selection is possible on Groundwork's install path. Investigated directly (design.md §A.6/A.8/D.1): `claude plugin install` (what `install.sh` actually runs) has no such flag — `--profile`/`--with capability:*` exist only on ECC's separate standalone installer, which must never be combined with the plugin path. Task 7.2's `skillOverrides` question is also resolved, not pending: source-level inspection of the installed Claude Code CLI shows `skillOverrides` is never consulted for plugin-sourced skills. Remaining tasks ship the corrected, evidence-backed scope: full ECC install retained, the two real levers documented, cost measured honestly.
- [x] 7.1 CORRECTED: confirmed no install-time skill/agent selection flag exists for `claude plugin install`; `install.sh` keeps installing ECC's full catalog (unchanged from 1.5.1) plus its existing `--config hook_profile=standard`
- [x] 7.2 RESOLVED (not RUNTIME VALIDATION REQUIRED): `skillOverrides` confirmed ineffective for plugin-provided skills by direct inspection of the installed Claude Code CLI's own source (v2.1.283) — the resolution path explicitly skips `source === "plugin"` entries; `docs/TROUBLESHOOTING.md`'s existing claim was already correct and is now labeled confirmed rather than asserted
- [-] 7.3 Not applicable: there is no curated profile to opt out of. The existing `claude plugin disable ecc@ecc` (already documented) remains the one real, working full-ECC opt-out D4 requires — no new flag needed
- [-] 7.4 Not applicable: 7.2 confirmed `skillOverrides` does NOT work on plugin skills; `scripts/merge_settings.py` needs no change
- [-] 7.5 Not applicable: no curated-out capability exists to test; superseded by 7.6's honest cost measurement of the (unavoidable) full install
- [x] 7.6 Context-cost measurement: recorded the full ECC install's measured session-start token cost (`claude plugin details ecc@ecc`'s "Always-on" total, ~43,577 tok) in `docs/VALIDATION.md` — no before/after comparison is possible, stated plainly, with the reason (unpinned install, no curation mechanism exists)
- [x] 7.7 Cross-check against §D.5's builder-capability sourcing table — re-verified against the REAL installed content (not the stale npm-tarball catalog): no AWS/GCP/Azure/Terraform skill or agent found in the actual installed 386-skill/68-agent roster either; no builder role needs a capability outside what ECC actually provides
- [x] 7.8 Independent fresh-context review (MATERIAL — corrects a previously-approved mechanism and the OpenSpec that described it) — satisfied by the Phase 1 second and third review rounds, which directly examined this exact correction (design.md §A.6/A.8/D.1, the rewritten `ecc-capability-policy` spec, `docs/ARCHITECTURE.md`) as their primary subject (finding "review-1" and its resolution) rather than needing a fourth, duplicate review of the same already-reviewed material
- [x] 7.9 docs/VALIDATION.md entry; docs/TROUBLESHOOTING.md's `skillOverrides` claim upgraded from asserted to confirmed-with-evidence; README/ARCHITECTURE already corrected in Phase 1 (task 1.4)

### Phase 8 — Repository understanding (new this pass)
- [x] 8.1 Extend `playbooks/implement.md`, `playbooks/deploy.md`, `playbooks/design.md` with the domain-specific discovery checklist (§E.2), referencing `architecture-quality.md` §5 rather than restating it
- [x] 8.2 Model-behavior validation: the "repository pattern vs. generic knowledge" and "rejected unsafe pattern" scenarios from design.md §L.2, run live against fixture repositories — both passed; see docs/VALIDATION.md
- [x] 8.3 Non-regression check (playbooks stay within their existing size discipline; no new always-loaded file) — all three playbooks remain within `MAX_PLAYBOOK_BYTES` (4000); no rule file touched
- [ ] 8.4 Independent fresh-context review
- [x] 8.5 docs/VALIDATION.md entry with the fixture-repository transcripts

### Phase 9 — Builder execution roles (new this pass)
- [x] 9.1 Add the four role personas and the automatic orchestration extension to `rules/engineering-workflow.md` §6
- [x] 9.2 Add the MCP/tool-access policy subsection (§F.5) to the same section
- [x] 9.3 Add the closed-loop troubleshoot-and-revalidate line to `playbooks/deploy.md`
- [x] 9.4 Confirmed (no file change): `evidence-policy.md` §6's completion-evidence table (code/tests/review/CI/PR/deploy/runtime-check) already covers builder work generically (Terraform apply = "Deploy command exit 0", kubectl health check = "Runtime check"); no illustrative example rows added to `deploy.md`'s Output Format — the existing generic wording already applies without restating anything domain-specific
- [x] 9.5 Model-behavior validation, live (not simulated), against a real Groundwork install: repository-aware infra build (Terraform/GKE, Phase 8 + a Cloud Run/app-plus-infra two-file case here); no-authorization (a prod-database-deletion request correctly stopped before any mutation, separating "edit the file" from "apply live" as two distinct authorization decisions); cross-domain build in non-interactive mode (a genuinely two-file, low-complexity app+infra task correctly stayed in the main session with an explicit one-line reason, never fabricating subagent/team use it didn't perform). Platform onboarding (Helm/Flux) and Delivery (GitHub Actions) domain-specific fixtures were not independently re-run — the underlying mechanism (repository-understanding discovery + persona-scoped reasoning) is domain-agnostic and already validated twice (Infrastructure Engineer via Terraform, a mixed app+infra case here); re-running the identical mechanism against two more fixture domains was judged low marginal evidence for the cost. Nonprod deployment (a real applied change against a live sandboxed target) is **RUNTIME VALIDATION REQUIRED, not performed** — no real cloud/Kubernetes target is available in this environment, and creating one is out of scope ("do not create paid cloud resources merely to satisfy acceptance testing")
- [ ] 9.6 Independent fresh-context review (MATERIAL)
- [x] 9.7 docs/VALIDATION.md entry with live scenario transcripts
- [x] 9.8 Depends on: Phase 7 (curated ECC composition) and Phase 8 (shared discovery) — both shipped first

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
