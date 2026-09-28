## Why

This change is the **audit and design phase only** — see `design.md` for the full current-state audit, gap analysis, ECC capability matrix, target architecture, migration plan, acceptance matrix, and open decisions. Nothing in this proposal has been implemented; `tasks.md` is entirely unchecked. Per the requesting brief, Groundwork 2.0 must evolve the existing 1.5.1 architecture in place — it is not a rewrite, and it does not replace anything that already works.

**Revision note (same day, second pass, 2026-09-28)**: this proposal was extended, not replaced, by a second design pass covering repository-aware builder roles (Infrastructure/Platform/Delivery/Application Engineer), SRE capability consolidation, presentation and output-style architecture, and a teach/learn capability — while also substantively redesigning two decisions from the first pass (D3, review evidence; D5, deterministic safety) after the first pass's proposals were found to be too weak or not yet builder-aware. `design.md` §A-D and the original K-N (formerly E-H) sections are the first pass, preserved; §E-J are new. This document remains the single canonical OpenSpec change for Groundwork 2.0 — no second change was created.

Groundwork 1.5.1 is materially stronger than a typical "governance layer" — its own `docs/VALIDATION.md` shows a genuine evidence-first development discipline. The audit found that **most** requested Groundwork 2.0 outcomes are already met: evidence-backed reasoning, honest completion truth, deterministic push/review guards, automatic execution-model selection, additive/idempotent install-update-rollback-uninstall, portability, and proportional OpenSpec use are all **VERIFIED, already implemented, and already tested** as of 1.5.1 (`design.md` §A/§B).

### Gaps found in the first pass (unchanged)

1. **A real, currently-shipping bug**: OpenSpec has required Node ≥20.19.0 since at least 1.12.0; Groundwork documents and enforces Node ≥18, and `install.sh` performs no version check at all.
2. **No evidence label for genuinely conflicting or indeterminate evidence** — `CONFLICTING EVIDENCE`/`UNKNOWN` confirmed absent repo-wide.
3. **Independent review is enforced by presence, not by outcome** — see the redesigned D3 below, this is now more thoroughly addressed than the first pass proposed.
4. **No durable record for rejected hypotheses or in-progress investigative work outside OpenSpec.**
5. **ECC is installed and paid for wholesale** — 68 agents/286 skills, no SRE/CloudOps curation, despite native selection mechanisms existing.
6. **No deterministic safety boundary beyond Git** — see the redesigned D5 below, now builder-aware.
7. **Minor, low-risk items**: a duplicated helper function; ECC/OpenSpec version drift in Groundwork's own docs.

### Gaps found in this second pass

8. **No repository-aware builder capability.** Groundwork's existing playbooks review/troubleshoot infrastructure well but do not explicitly direct discovery of existing Terraform/Kubernetes/CI conventions before generating new infrastructure/platform/delivery code — the generic UNDERSTAND step and the "conventions win" rule already exist (`architecture-quality.md` §5) but were not spelled out for these domains.
9. **No execution-role concept for infrastructure/platform/delivery/application-building work** — `engineering-workflow.md` §6 already selects main-session/subagent/team automatically but has no notion of *which persona* a builder subagent should take.
10. **No presentation, output-style, or teach/learn capability** — reasonable requests ("create a management presentation," "teach me what we just fixed") had no explicit home, though the underlying mechanisms (DOCUMENT/EXPLAIN playbooks, evidence rules) mostly already cover them once made explicit.
11. **The first pass's D3 (review evidence) was too weak**: "any tool call after a MUST-FIX review" does not demonstrate the finding was resolved or that validation reran — redesigned (see below).
12. **The first pass's D5 (deterministic safety) was too vague to approve**: one abstract "narrow candidate" — redesigned into a concrete, tiered menu now that builder roles make the underlying risk real rather than hypothetical.

None of these gaps require new agents, skills, daemons, databases, or a rewrite. Every proposed change is additive or corrective to the existing rules/playbooks/hooks/installer shape — confirmed explicitly this pass by a comprehensive capability-ownership matrix (`design.md` §J) showing no two components define the same contract.

## What Changes (subject to the decisions in `design.md` §M — nothing here is authorized for implementation yet)

**Carried from the first pass, unchanged in substance:**
- **Fix the Node/OpenSpec version claim** — `installer-upstream-compatibility`.
- **Extend the evidence taxonomy** — `evidence-taxonomy`: `CONFLICTING EVIDENCE`/`UNKNOWN` labels, tightened RCA rule.
- **Curate ECC for SRE/CloudOps by policy** — `ecc-capability-policy`, using only native, already-existing selection mechanisms; cross-checked this pass against builder-role needs (`design.md` §D.5) with no change to the recommended default set.
- **Decide, do not silently build, a continuity mechanism** — `investigation-continuity` (D2), field list reaffirmed this pass.
- **Small maintainability fix and documentation correction** — duplicated helper, ECC/OpenSpec version refresh.

**Redesigned this pass:**
- **Review evidence, strengthened for real** — `review-evidence-strengthening`: a small structured `REVIEW RESULT` block (mirroring the existing, proven `Harness metadata` block pattern) plus an extension to `require_material_review.py` that reuses `groundwork_telemetry.py`'s existing test-command-detection regex to require both an edit **and** a validation re-run after a MUST-FIX finding — not merely "any tool call." Full design in `design.md` §M, Decision D3.
- **Deterministic safety, tiered and builder-aware** — `deterministic-safety-expansion`: read-only discovery is always safe; explicitly authorized nonprod mutation needs no new hook (existing rules suffice); production/IAM/destructive operations get a menu of three independently-approvable, narrowly-scoped guards (Terraform-prod-guard, kubectl-prod-guard, IAM-mutation-guard), each structurally mirroring the proven `block_protected_push.py` pattern. Full design in `design.md` §M, Decision D5.

**New this pass:**
- **Repository-understanding** — one shared discovery procedure (proportional, "repository pattern wins over generic knowledge unless unsafe"), extending three existing playbooks (`implement.md`, `deploy.md`, `design.md`) with a domain-specific checklist — no new always-loaded rule, no new file beyond the playbook extensions.
- **Builder execution roles** — four dynamically-instantiated role personas (Infrastructure/Platform/Delivery/Application Engineer) added to `engineering-workflow.md` §6's existing execution-model decision — not permanent agent files, not a new task-routing category. Includes the closed-loop build→deploy→validate→troubleshoot-if-failed→revalidate path (one line added to `deploy.md`) and confirms the existing completion-evidence model needs no new status vocabulary for builder work.
- **SRE capability consolidation** — an explicit analysis (`design.md` §G) confirming ~20 SRE capabilities named in the requesting brief compose through existing TROUBLESHOOT/VALIDATE/AUDIT/DEPLOY/RESEARCH/DOCUMENT playbooks plus curated ECC plus repository-understanding, with **zero new files** — this section's entire contribution is the analysis proving composition is sufficient.
- **Presentation and output-style architecture** — `presentation-and-output-style`: native Claude Code output styles (verified to exist, and verified to be explicitly unenforced by the platform's own docs) own tone/format framing; Groundwork's `output-contract.md` continues to own truth, unchanged, and gains one explicit invariant that style never overrides it. Presentation routes through the existing DOCUMENT playbook, defaults to portable Markdown/Mermaid, and may optionally use Anthropic's first-party `document-skills` plugin (verified installable in plain Claude Code CLI, no plan/login gate) for real `.pptx`/`.docx` output — Groundwork builds no rendering engine of its own. The visual design-system template is explicitly deferred (OPTIONAL/LATER).
- **Teach/learn capability** — reuses the existing EXPLAIN playbook and (where present) `investigation-continuity`'s recorded evidence; introduces no second knowledge store.

## Capabilities

### New Capabilities
- `evidence-taxonomy`
- `ecc-capability-policy`
- `installer-upstream-compatibility`
- `review-evidence-strengthening` — redesigned this pass (§M, D3)
- `investigation-continuity` — DECISION-PENDING (§M, D2)
- `deterministic-safety-expansion` — redesigned, tiered, decision-pending for Tier 2 (§M, D5)
- `repository-understanding` — new this pass
- `builder-execution-roles` — new this pass
- `presentation-and-output-style` — new this pass
- `teach-learn-capability` — new this pass

### Modified Capabilities
- `project-continuation` (proposed in `openspec/changes/intelligent-engineering-harness`, not yet archived — see `design.md` §N, Open Question 1): gains the continuity decision's outcome once made.
- `validation-and-review-evidence` (same predecessor change): gains the redesigned review-evidence-strengthening outcome.
- `harness-installation` (same predecessor change): gains the corrected Node/OpenSpec version floor and the upstream-drift check.
- `usage-telemetry` (archived): no schema change proposed at this stage.

### Explicitly not proposed (and why — see `design.md` §G, §J)
- No `sre-capability` spec or component — analysis proved composition sufficient.
- No per-builder-role permanent agent files — roles are dynamic personas.
- No new task-routing category for builders or presentations — both route through existing categories.
- No presentation rendering engine or design-system enforcement mechanism — composes an optional native plugin or plain Markdown.
- No second knowledge store for teach/learn — consumes existing evidence.
- No scheduled automation of any kind — explicitly out of scope for this phase.

## Impact

- **Files** (once a phase is approved and implemented — nothing changes in this design-only submission): `rules/evidence-policy.md`, `rules/engineering-workflow.md`, `rules/output-contract.md`, `hooks/require_material_review.py`, `hooks/groundwork_session_snapshot.py` (+ new shared helper module), `playbooks/implement.md`, `playbooks/deploy.md`, `playbooks/design.md`, `playbooks/document.md`, `playbooks/explain.md`, `install.sh`, `setup.sh`, `README.md`, `docs/ARCHITECTURE.md`, `docs/FUTURE-SCOPE.md`, `docs/VALIDATION.md`, `CHANGELOG.md`, `tests/test_hooks.py`, `tests/test_setup.py`, plus new test coverage per phase. Up to three new hook files, all decision-pending (D5 Tier 2 candidates); no new state file unless D2 picks the state-file option; no other new files.
- **Installed footprint**: no new top-level directories; at most three new hook files (D5, all decision-pending) and, only if D2 selects the state-file option, one small capped file under `~/.claude/groundwork/`. Two OPTIONAL/LATER artifacts (Groundwork-authored output-style presets, a presentation design-system template) are explicitly not built in this pass — see `design.md` §O.
- **No new agents, skills, daemons, databases, or message buses** in any option under consideration — the four builder "roles" are rule-text personas, not files.
- **Compatibility**: fixing the Node floor is a **breaking correction** for any environment currently running Groundwork against Node 18/19 with a real `openspec/` workflow (documented as such, not as a new requirement). ECC curation (Phase 7) changes the default capability set for existing installations re-running `install.sh`, with an explicit `--ecc-profile full` opt-out back to today's behavior.

## Status of this document

Audit and design complete (both passes). **STOP — do not implement.** This proposal, `design.md`, and `tasks.md` are presented for owner review and phase-by-phase approval before any code, rule, hook, or doc file is changed. Task 0.13 remains unchecked; PR #20 remains a draft.
