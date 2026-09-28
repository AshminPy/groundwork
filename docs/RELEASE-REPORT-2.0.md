# Groundwork 2.0.0 — release-readiness report

Prepared at the end of the autonomous implementation authorized on 2026-09-28. This is the single consolidated report the owner asked for before installing 2.0 on a work laptop. It duplicates nothing from `docs/VALIDATION.md`, `openspec/changes/groundwork-2-enterprise-sre/design.md`, or `tasks.md` — it points at them — except where a number needed to be re-verified fresh for this report (each such number is marked with the exact command run).

---

## 1. Executive summary

Groundwork 2.0.0 is implemented, tested, independently reviewed, and validated as far as this environment safely allows. All 13 phases of the approved OpenSpec change (`openspec/changes/groundwork-2-enterprise-sre/`) are complete; every task in `tasks.md` is checked (`[x]` done or `[-]` not applicable, with reasoning). Deterministic tests: 16/16 pytest checks, 485/485 standalone checks across 5 files, 0 failed. `openspec validate groundwork-2-enterprise-sre --strict` passes. Clean-install, upgrade-from-1.5.1, rollback, and uninstall were each tested live in an isolated environment, never the session's own active configuration. Every MATERIAL-tier phase received at least one fresh-context independent review; every MUST FIX finding across every round was fixed and re-verified. Two items remain honestly marked **RUNTIME VALIDATION REQUIRED** (§22) because they need infrastructure this environment cannot safely provide (a real cloud/Kubernetes target, and Claude Code's experimental Agent Teams flag in an interactive session) — neither blocks the release; both are pre-existing categories of limitation the design anticipated, not new gaps found late.

Two owner decisions were deferred rather than force-completed: D5's three Tier-2 safety guards (Terraform-prod-guard, kubectl-prod-guard, IAM-mutation-guard) were explicitly declined at implementation authorization, per the owner's own stated reasoning that heuristic production-detection risks false confidence — this was an explicit instruction, not a gap this session introduced, and it does not block the release.

**Release status: merged to `main` and ready for installation.** PR #20 was merged on 2026-09-28 after owner review.

## 2. Scope and status

Tracked entirely in `openspec/changes/groundwork-2-enterprise-sre/`. All 5 stages, 13 phases:

| Stage | Phases | Status |
|---|---|---|
| Foundation | 1 (Node/OpenSpec correctness + dedup), 2 (evidence taxonomy), 3 (capability-ownership docs) | Complete |
| Trust | 4 (review-evidence strengthening, D3), 5 (investigation continuity, D2), 6 (deterministic safety, D5) | Complete (6 = explicit deferral, documented, not blocking) |
| Capability | 7 (ECC capability policy, D4), 8 (repository understanding), 9 (builder execution roles) | Complete |
| Experience | 10 (presentation/output-style), 11 (teach/learn) | Complete |
| Validation | 12 (end-to-end acceptance scenarios), 13 (regression gate + install lifecycle) | Complete |

No second OpenSpec change was created. No implementation deviated from the approved design without an explicit, evidence-backed correction recorded in `design.md` itself (see §19 for the full list of such corrections — this is the "do not blindly implement the design, but never silently change architecture either" instruction, followed both ways).

## 3. Architecture — unchanged ownership model, extended coverage

Groundwork's role does not change in kind: it owns policy (routing, evidence, safety, continuity, completion truth), never execution capability. OpenSpec still owns WHAT/WHY; ECC still owns HOW (agents/skills); Claude Code still owns runtime primitives; MCP/CLI still owns external-system access only. 2.0 adds four policy surfaces on top of the same four owners — repository-understanding policy, builder-role-selection policy, SRE-capability-composition policy (an analysis producing zero new files, not a mechanism), and output-truth/style-separation policy. See `design.md` §C for the full diagram and `docs/ARCHITECTURE.md`'s "Capability ownership (2.0)" section for the pointer table into `design.md` §J.

## 4. Capability ownership matrix

`design.md` §J is the authoritative, comprehensive table (every proposed and existing capability, cross-checked against ECC/OpenSpec/Claude Code natives/existing Groundwork for duplication). The structural proof this held in the actual diff, not just on paper (task 12.2): `git diff --name-status origin/main...HEAD | grep '^A'` shows exactly **one** new production code file across all 13 phases — `hooks/groundwork_shared.py` — and it is itself a deduplication (two pre-existing duplicated helpers consolidated into one shared module). Every other new file is OpenSpec process documentation (design/proposal/tasks/10 capability specs), which the process itself requires. Zero new hooks, scripts, playbooks, rule files, or agent files were created to ship ten capability phases.

## 5. Builder execution roles — dynamic personas, never permanent agent files

Four role personas (Infrastructure/Platform/Delivery/Application Engineer) added to `rules/engineering-workflow.md` §6 as `Agent`-call personas selected per task, plus the MCP/tool-access policy (§F.5) folded into the same section. Explicitly and repeatedly confirmed, not just asserted: a direct repo-wide `find` for `.claude/agents/*.md`-style files returns nothing (re-confirmed by the Phase 8-11 independent review, §19). The section reads as scope/evidence-source prose in the same format as the pre-existing subagent-selection text immediately above it — no YAML frontmatter, no system-prompt framing, structurally incapable of being mistaken for a persistent agent definition. Live-validated: repository-aware infra build (Terraform/GKE), cross-domain build correctly staying in the main session with a stated reason, no-authorization correctly stopping a destructive production request before mutation. See `docs/VALIDATION.md`'s Phase 9 entry for transcripts.

## 6. ECC capability policy (Decision D4) — corrected mid-implementation

The original design assumed ECC installs pinned from npm with an install-time skill/agent selection flag. Both assumptions were wrong, found by direct reproduction against a live, isolated install (`claude plugin marketplace add affaan-m/ECC` + `claude plugin install ecc@ecc`): ECC installs **unpinned from GitHub `main`**, and `claude plugin install` has no selection flag (`--profile`/`--with capability:*` exist only on ECC's separate standalone installer, which must never be combined with the plugin path Groundwork actually uses). Also resolved by source-level inspection of the installed Claude Code CLI itself (not assumed): `skillOverrides` is never consulted for plugin-sourced skills (`source === "plugin"` explicit early-return in the CLI's own resolution code). **What ships**: ECC's full, unpinned install (unchanged in kind from 1.5.1), governed only by the already-used `hook_profile` config and the already-documented whole-plugin `claude plugin disable ecc@ecc` opt-out. The limitation (no curation mechanism exists) is documented plainly rather than a nonexistent mechanism being built. Measured context cost, live: `claude plugin details ecc@ecc` → "Always-on: ~43,577 tok added to every session" (version 2.2.2 at measurement time; moves independently of Groundwork releases since the install is unpinned). Full evidence trail, including the corrected `design.md` §A.6/A.8/D.1 and the rewritten `ecc-capability-policy` spec: `docs/VALIDATION.md`'s Phase 1 entry ("M4" finding).

## 7. Evidence taxonomy — CONFLICTING EVIDENCE and UNKNOWN

`rules/evidence-policy.md` §2 now has 7 labels: VERIFIED, UNVERIFIED, ASSUMPTION, INFERENCE, **CONFLICTING EVIDENCE** (new), **UNKNOWN** (new), RUNTIME VALIDATION REQUIRED. §7's RCA rule requires one of the two new labels when the evidence genuinely doesn't support a conclusion, rather than a softened guess. Live-validated with two constructed scenarios (two config files disagreeing on a timeout value with neither marked authoritative; a trivial function with zero platform signal) — both correctly produced the exact label names, unprompted beyond "follow your loaded rules." See `docs/VALIDATION.md`'s Phase 1/2/4 combined entry, task 2.5.

## 8. Investigation continuity (Decision D2, Option B — the owner's selected option)

A small, capped, per-repository investigation-state file at a deterministic path (`~/.claude/groundwork/investigations/<slug>-<sha256[:10]>.md`, computed from `git rev-parse --show-toplevel`), surfaced at every SessionStart via `hooks/groundwork_session_snapshot.py`. Exact field list (per the owner's D2 authorization, verbatim): objective, proven facts, evidence references, decisions, rejected hypotheses with reason, active hypotheses, files changed, validation results, blockers, uncertainty, remaining tasks, next action — no chain-of-thought, ever. No new hook, no new install-managed file (the directory is created lazily by the model's own `Write`, exactly like `telemetry/`/`reports/`; confirmed preserved on uninstall by test).

**The critical acceptance test — rejected hypothesis survives recovery — is live-validated, not simulated.** A real `claude -p` session given a saved file with one rejected and one active hypothesis kept the rejected one rejected and independently re-verified the active one against actual repository code before reporting it confirmed (satisfying both "rejected stays rejected" and "current evidence outranks saved state" in the same transcript). A second run confirmed the positive case isn't over-broad: engineered "new evidence" that didn't actually contradict the rejection reason correctly did not reopen it. Two independent review rounds on this mechanism found and closed 2 MUST FIX + 5 of 6 NICE TO HAVE findings (the sixth — a narrow fenced-code-block false-match side channel — is a documented, not fixed, known limitation; §20). Full transcripts and both review rounds: `docs/VALIDATION.md`'s Phase 5 entry.

## 9. Review-evidence strengthening (Decision D3 — approved with strengthening)

Shipped strictly stronger than the design document's own second draft, per the owner's explicit instruction at authorization: *"MUST FIX → Edit → Test alone is NOT sufficient evidence of resolution. The resulting change must receive fresh independent review after the fix."* Mechanism: a structured `REVIEW RESULT` block (`Verdict:`/`Must-fix:`/`Findings:`) defined in `rules/output-contract.md`, reusing the same pattern already proven by the existing `Harness metadata` block; `hooks/require_material_review.py` extended to evaluate the **most recent** review-shaped call's own verdict — an edit and a test/validation-shaped Bash call afterward are shown as diagnostics but are not sufficient; Stop stays blocked until a subsequent, fresh review itself reports `Must-fix: 0`. Confirmed to work in practice, not just in unit tests: two live `claude -p` sessions, given only the rule text (no format instructions), organically emitted the exact block shape for both a clean diff and a diff with a real bug. This exact mechanism has now been exercised by 3+ independent review rounds across Phases 1, 4, and 5 (it is, self-referentially, the mechanism that gated its own phases' completion). See `docs/VALIDATION.md`'s Phase 1/2/4 entry, task 4.2.

## 10. Deterministic safety model, and the D5 deferral

Ships unchanged from 1.5.1 plus one extension: the existing protected-Git push guard (`block_protected_push.py`), the existing risk/autonomy rule (`engineering-workflow.md` §4 — production/IAM/data/paid-resource changes require explicit authorization), and native Claude Code permissions — now explicitly extended to builder-role work (§F.5/Phase 9). **The three Tier-2 candidates from the design (Terraform-prod-guard, kubectl-prod-guard, IAM-mutation-guard) are explicitly deferred, not implemented**, per the owner's own words at authorization: *"Do NOT implement [them] merely to complete the checklist, because production-vs-nonprod detection depending on heuristic naming risks false confidence... This deferral MUST NOT block the Groundwork 2.0 release."* Tier 0 (read-only discovery) and Tier 1 (nonprod mutation, task-authorized) needed no new hook and are unaffected. Live-tested backstop: a request to delete a production database and apply it live was stopped before either action, with "edit the file" and "apply to production" separated as two distinct authorization decisions — zero Tier-2 code involved, matching the design's own claim that Tier 0/1 plus existing rules remain sufficient without Tier 2. The three deferred candidates remain documented as live future options in `docs/FUTURE-SCOPE.md` §10, not silently dropped and not expanded into scope without a future owner decision.

## 11. Repository-understanding — shared discovery capability

One discovery procedure, not four duplicated variants. `playbooks/implement.md`, `deploy.md`, `design.md` each reference the same 8-item domain-scoped checklist (module/pipeline structure, naming/variable/label conventions, environment/workspace organization, IAM/networking patterns, state/backend patterns, CI/CD and delivery conventions, testing and validation conventions, closest analogous implementation) under their existing "inspect before writing" step, proportional to the task, citing `architecture-quality.md` §5's existing convention-wins rule rather than restating it. Live-validated on two named scenarios (a Terraform repo with a non-generic thin-wrapper convention correctly reproduced; a repo with a hardcoded-secret pattern correctly flagged and deviated from, with the reason stated) — neither prompt used the words "convention," "pattern," or "unsafe." See `docs/VALIDATION.md`'s Phase 8 entry.

**Correction applied this session** (§19, finding from the Phase 8-11 independent review): the three playbooks' checklists had drifted from each other in wording and item count. Re-aligned to identical item wording across all three, byte-verified.

## 12. Presentation and output-style architecture

`rules/output-contract.md` gained one invariant: a native Claude Code output style may change tone/format/audience framing, never the evidence, validation, or completion-status rules this file owns. `playbooks/document.md` gained a presentation branch: Markdown/Mermaid is the default (portable, git-diffable, no plan/tool gate); an installed `document-skills` plugin is used for `.pptx`/`.docx` only when the user wants a bundled file and the plugin is actually present. No rendering engine was built — presentation composes existing native mechanisms. RESOLVED before this shipped (§H.2, a named RUNTIME VALIDATION REQUIRED item from the design): live-tested confirmation that selecting a non-Default output style does not affect `~/.claude/rules/**/*.md` loading — rules and styles are separate pipelines. Live-validated: the same underlying facts rendered once under default style and once under a custom executive style produced the same three facts (built, tested, not deployed) with only tone/detail differing. See `docs/VALIDATION.md`'s Phase 10 entry.

**Correction applied this session** (§19): the shipped sentence had dropped the design's explicit instruction to *say so* when no document-generation plugin is detected, covering only "never assume/never degrade." Restored: "...if it is not [present], say so and produce Markdown/Mermaid instead of assuming it or silently degrading quality."

## 13. Teach/learn capability

One branch added to `playbooks/explain.md`: teaching from work this session (or a recoverable investigation-continuity file) established draws only on that evidence, never invents or embellishes; when the evidence trail is unavailable, states plainly what is reconstructed from artifacts versus recalled with confidence. No new storage — reuses session evidence, git history, and investigation-continuity's existing state (confirmed by diff: touches exactly one file). Live-validated on three scenarios: complete evidence available (correctly explained a real fix from `git log -p`); evidence trail genuinely absent (a commit message claiming a fix whose diff was unrelated — the session refused to invent a plausible story and asked for the real source); partial evidence (code-verifiable parts explained with confidence, an external incident narrative correctly labeled UNKNOWN rather than guessed). See `docs/VALIDATION.md`'s Phase 11 entry.

## 14. SRE capability consolidation — analysis, not a mechanism

`design.md` §G is the deliverable itself: ~20 named SRE capabilities from the brief mapped onto existing playbooks (TROUBLESHOOT/VALIDATE/AUDIT/DEPLOY/RESEARCH/DOCUMENT) plus curated ECC composition plus repository-understanding plus MCP tool access. Zero new files. Two named sub-capabilities (SLO/error-budget analysis, IAM/cloud-security-posture) have no matching ECC skill — documented plainly as relying more heavily on native reasoning, not silently claimed as covered.

## 15. Deterministic test suite — inventory

| File | Checks | What it covers |
|---|---|---|
| `tests/test_hooks.py` | 131 | All 4 hooks: push guard, review gate (incl. D3 strengthening, non-dict-JSON crash guards), session snapshot (incl. investigation continuity, control-char stripping), telemetry |
| `tests/test_playbooks.py` | 142 | Playbook size discipline, Node version checks (install.sh/setup.sh), ECC version reporting, uninstall preservation |
| `tests/test_report.py` | 67 | Dashboard/report generation |
| `tests/test_setup.py` | 64 | setup.sh flows, backup/rollback, prerequisite detection |
| `tests/test_telemetry.py` | 81 | Telemetry recording and privacy |
| **Total** | **485** | |

Plus `pytest tests -q` (16 module-level checks, one per test file's `main()`, run as the canonical single command).

## 16. Deterministic test results — exact, re-run for this report

```
$ python3 -m pytest tests -q
................                                                         [100%]
16 passed in 27.75s

$ python3 tests/test_hooks.py       → 131 passed, 0 failed
$ python3 tests/test_playbooks.py   → 142 passed, 0 failed
$ python3 tests/test_report.py      → 67 passed, 0 failed
$ python3 tests/test_setup.py       → 64 passed, 0 failed
$ python3 tests/test_telemetry.py   → 81 passed, 0 failed

$ openspec validate groundwork-2-enterprise-sre --strict
Change 'groundwork-2-enterprise-sre' is valid
```

0 failures across all 501 total checks (16 + 485). Every new test added this implementation was individually verified to fail before its corresponding fix and pass after, not just written and left green (the discipline used for every MUST FIX finding in §19).

## 17. Model-behavior / live validation evidence — summary

Every capability with a behavioral claim was validated against a real, isolated Groundwork install (`install.sh` against a throwaway `$HOME`, real ECC, real OpenSpec) and real `claude -p` headless sessions against small fixture repositories — never simulated, never asserted without a transcript. Full transcripts and quotes: `docs/VALIDATION.md`. Consolidated scenario table: `docs/VALIDATION.md`'s Phase 12 entry, reproduced in §24 below. Summary: 13 of 15 named acceptance scenarios VERIFIED live; 2 are RUNTIME VALIDATION REQUIRED (§22) for infrastructure reasons, not because the mechanism is unbuilt or untested in principle.

## 18. Clean-install / upgrade / rollback / uninstall results

All four tested live, in a throwaway `$HOME` under this session's own scratch directory, real `claude`/ECC/OpenSpec binaries — **never the session's own active Claude configuration**, per the explicit constraint against repeating that historical mistake. A `git worktree` checked out the true pre-2.0 baseline (`main` @ `d40523a`) so the upgrade test installed genuinely old code, not a relabeled copy of the new code.

1. **Clean install (1.5.1 baseline)**: fresh `$HOME`, installed cleanly — `VERSION` 1.5.1, 5 rule files, the 4 pre-2.0 hooks, 4 hook entries in `settings.json`.
2. **Simulated real usage on 1.5.1**: telemetry record, a user-owned file, a user-owned `settings.json` customization added — state an upgrade must never touch.
3. **Upgrade (1.5.1 → 2.0.0)**: succeeded; `VERSION` correctly became `2.0.0`; `hooks/` gained `groundwork_shared.py` and the other four hooks updated; `engineering-workflow.md` gained §7; `output-contract.md` gained the `REVIEW RESULT` block. User's telemetry/file/settings byte-identical afterward. **A real bug was found and fixed here**: `VERSION` initially stayed `1.5.1` post-upgrade because `install.sh` derives it from `CHANGELOG.md`'s first `^## [0-9]+\.[0-9]+\.[0-9]+` heading, and the newest heading read `## Unreleased — Groundwork 2.0 (in progress)` — correctly skipped as not a version number, falling through to `## 1.5.1`. Fixed by giving the release its real `## 2.0.0 — 2026-09-28` heading; re-verified.
4. **Idempotent re-run**: second `install.sh` run reported "already has all Groundwork entries — nothing to do," no duplicate hook entries; `setup.sh --verify` reported all rows PASS including `Groundwork version 2.0.0`.
5. **Rollback**: `./setup.sh --rollback` reverted `VERSION` to 1.5.1, removed 2.0.0 hooks/rules, preserved user data, moved the pre-rollback state aside intact (never deleted).
6. **Uninstall**: `./uninstall.sh` removed all 5 hook files, `rules/groundwork/`, `VERSION`, every Groundwork `settings.json` key; kept `telemetry/`, `reports/`, `investigations/`; left ECC/OpenSpec installed and enabled.
7. **Final fully-independent clean install**: fresh `$HOME`, `setup.sh --non-interactive --profile work --schedule weekly` — all `--verify` rows PASS, then a live `claude -p` smoke test correctly listed all 7 evidence-policy labels including both 2.0 additions — confirming the installed rules genuinely load and function end-to-end on a clean machine.

Full detail: `docs/VALIDATION.md`'s Phase 13 entry.

## 19. Independent review — full history across all phases

Every MATERIAL-tier phase received at least one fresh-context independent review (a background `Agent` call with no access to this session's own reasoning). Every MUST FIX finding was fixed, re-verified by direct before/after reproduction (not by trusting the fix commit's own claim), and — per the strengthened D3 contract this same mechanism enforces on itself — a fresh review confirmed the fix before the phase was considered complete.

| Phase(s) reviewed | Round | MUST FIX found | Outcome |
|---|---|---|---|
| Phase 1 (Node/OpenSpec correctness, dedup) | 1st | 5 (M1 `setup.sh --verify` pipefail crash; M2 misleading post-install message; M4 wrong ECC install-source assumption — most significant; M5 `--verify` not reporting live ECC version; a 5th minor fix) | All 5 fixed + 5 of 11 NICE TO HAVE; re-verified by 2nd round |
| Phase 1/2/4 combined | 2nd | Confirmed prior fixes; found the non-dict-JSON crash bug in `require_material_review.py` | Fixed (`isinstance(data, dict)` guard); also found the same bug class in `scan_transcript()`'s per-line loop discarding evidence on one anomalous line — fixed |
| Phase 1/4 | 3rd | Same crash-bug class found in `block_protected_push.py` (sibling file, checked specifically because the bug had just been fixed elsewhere) | Fixed, identical guard |
| Phase 5 (investigation continuity) | 1st | 2 (truncation could silently drop "Rejected hypotheses"; a busy repo could crowd the whole investigation section out of the snapshot cap) | Both fixed — section reordering + `_prioritize_rejected()`; 3 NICE TO HAVE, all fixed |
| Phase 5 | 2nd (narrow, verification-only) | 0 — verified both fixes CONFIRMED FIXED by direct reproduction | 3 more NICE TO HAVE: 2 fixed (a `\r` off-by-one in the control-char regex; stale doc text); 1 documented as a known limitation, not fixed (§20) |
| Phases 8-11 (repository understanding, builder roles, presentation, teach/learn) | Combined, 1 round | 0 | APPROVE WITH NICE-TO-HAVES: 2 textual gaps (checklist wording drift across 3 playbooks; dropped "say so" instruction in `document.md`) — both fixed and re-verified this session; Phases 9 and 11 individually APPROVE (clean) |

No phase was ever self-declared complete without either a fresh review or an explicit, evidence-backed reason the phase's own risk level didn't warrant one (Phase 11, confirmed by the Phase 8-11 review itself as a defensible non-MATERIAL scoping call — `tasks.md` 11.5).

## 20. Known limitations (honestly carried forward, not fixed)

1. **Investigation-continuity fenced-code-block false match**: a `##`-prefixed line quoted inside a fenced code block *before* the real "## Rejected hypotheses" section (e.g. a model echoing the template verbatim for illustration) can be mismatched by `_extract_section()`'s line-start regex, reproducing the original truncation bug via a different path. Judged narrow (the template instructs "in this shape, and nothing else") and left for a future pass rather than fixed now. `docs/VALIDATION.md`, Phase 5 entry.
2. **Headless (`-p`) mode cannot `Write` directly to the investigation file's path** (outside the working directory) without an interactive permission grant — a general Claude Code headless-permission characteristic, not specific to this mechanism; does not affect normal interactive usage.
3. **ECC's install is unpinned** (GitHub `main`, no version tag) — its content, agent/skill count, and context cost move independently of Groundwork releases, with no Groundwork-side curation lever. Documented in `ecc-capability-policy`, not hidden.
4. **D5's production-naming heuristic** (relevant only if the deferred Tier-2 guards are ever revisited) depends on `repository-understanding` correctly surfacing a repo's actual environment-naming convention; a repository with no consistent convention would get materially weaker protection from such a guard. This is a property of the *deferred design*, not of anything shipped in 2.0.
5. **Presentation quality genuinely varies by whether the optional `document-skills` plugin is installed** — by design (no forced dependency), not a bug; stated in user-facing docs (`playbooks/document.md`) so it isn't mistaken for one.

## 21. Deferred items (explicit, documented, not blocking)

1. **D5 Tier-2 guards** (Terraform-prod-guard, kubectl-prod-guard, IAM-mutation-guard) — explicitly declined by the owner at authorization; full design preserved in `design.md` §M/D5 and `docs/FUTURE-SCOPE.md` §10 as a live future option, revisit trigger stated (a real incident/task exposing the gap concretely, or a non-heuristic production-identification mechanism being found).
2. **Groundwork-authored output-style presets and the presentation design-system template** (§H.4/task 10.7) — OPTIONAL/LATER per the design's own deferral condition; not built because no real presentation task in this implementation exposed a concrete need for one.
3. **Platform Engineer (Helm/Flux) and Delivery Engineer (GitHub Actions) domain-specific live re-validation for Phase 9 specifically** — the underlying discovery mechanism is domain-agnostic and already validated twice under other personas (Phase 8's Terraform scenario, Phase 9's Cloud Run scenario); re-running the identical mechanism against two more fixture domains was judged low marginal value. (Both domains *are* separately live-validated under Phase 12's own scenario set — §24.)

## 22. RUNTIME VALIDATION REQUIRED items (open, honestly stated)

Two items remain open because this environment cannot safely provide what they need — neither is a mechanism left unbuilt or untested in principle:

1. **Nonprod deployment — an actually-applied change against a live sandboxed target, with runtime validation.** No real cloud/Kubernetes target exists in this environment, and provisioning one is explicitly out of scope ("do not create paid cloud resources merely to satisfy acceptance testing," per the binding constraint this session operated under). The mechanism itself (DEPLOY playbook, builder-role execution, closed-loop revalidate-on-failure) is otherwise fully exercised — see `docs/VALIDATION.md`'s Phase 9 entry for what *was* run.
2. **Cross-domain build via a genuinely parallel Agent Team.** Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` *and* an interactive session; not testable via headless `claude -p` in this environment. The fallback path — never claiming a team that didn't run, staying in the main session with a stated reason when parallelism wouldn't add evidence — is itself VERIFIED live (§24).

**First recommended real-world action for both**: run each once, deliberately, in a normal interactive Claude Code session against a real (ideally a disposable/sandboxed) target, per §29's smoke-test suggestion.

## 23. Acceptance-criteria status — the original 22 non-negotiable criteria

Full table with evidence pointers: `design.md` §B. Status as of this report (unchanged from the design's own assessment except where 2.0's new phases closed a gap the original 22 flagged):

| # | Criterion | State |
|---|---|---|
| 1 | Evidence-backed factual claims | MET |
| 2 | Unsupported RCA conclusions prevented | MET (strengthened by evidence taxonomy, Phase 2) |
| 3 | UNKNOWN is a valid outcome | **MET** (was PARTIAL pre-2.0 — Phase 2 closed this) |
| 4 | Conflicting evidence surfaced | **MET** (was NOT MET pre-2.0 — Phase 2 closed this) |
| 5 | Repository/runtime outranks saved memory | MET |
| 6 | False completion claims prevented | MET, strong |
| 7 | MATERIAL work receives meaningful independent review | **MET** (was PARTIAL — Phase 4's strengthened D3 closed this) |
| 8 | Critical state survives context compaction | **MET** for OpenSpec-tracked work; **MOSTLY MET** for non-OpenSpec-tracked work (Phase 5's Option B — a live-validated but not exhaustively adversarial mechanism, §20 item 1) |
| 9 | Fresh sessions accurately recover unfinished work | MET |
| 10 | Rejected hypotheses remain rejected after recovery | **MET** (was NOT MET/NOT TESTED — Phase 5 closed this, live-validated) |
| 11 | Main/subagent/team execution selected automatically | MET, extended to builder-role selection (Phase 9) |
| 12 | Unnecessary context minimized | **PARTIAL, unchanged** — ECC's ~43,577-tok cost has no curation mechanism (§6/M4); documented, not hidden |
| 13 | ECC exposure curated for SRE/CloudOps | **NOT MET, unchanged, now with a corrected reason** — no curation mechanism exists on the real install path (§6); §D.5's analysis confirms no builder role needs a capability outside ECC's default set regardless |
| 14 | OpenSpec used only when justified by materiality | MET |
| 15 | Safety-critical controls deterministic where practical | **PARTIAL, by explicit owner deferral** — Tier 2 declined (§10/§21); Tier 0/1 plus existing rules cover the live-tested scenario |
| 16 | Install/update/rollback/uninstall are safe | MET, exceptionally well validated (§18) |
| 17 | No personal credentials/hardcoded identity | MET |
| 18 | External work updates based on evidence | OUT OF SCOPE for this release (unchanged) |
| 19 | Telemetry useful without leaking sensitive content | MET |
| 20 | Existing intended behavior has not regressed | MET — Phase 13's regression gate |
| 21 | System remains understandable and maintainable | MET — the one pre-existing duplicated-helper wart was fixed in Phase 1 |
| 22 | Usable without understanding internals | MET |

Net effect of 2.0: criteria 3, 4, 7, 10 move from PARTIAL/NOT MET to MET. Criteria 12, 13, 15 remain their pre-2.0 status, each for an explicit, evidence-backed, owner-endorsed reason (no mechanism exists / owner declined false-confidence risk) rather than an oversight.

## 24. Acceptance-criteria status — the 15 new §L.2 scenarios (this pass's own brief)

| Scenario | Status | Evidence |
|---|---|---|
| Repository-aware infra build (Terraform) | VERIFIED | `docs/VALIDATION.md`, Phase 8 |
| Platform onboarding (Helm/Flux) | VERIFIED | `docs/VALIDATION.md`, Phase 12 |
| Delivery (GitHub Actions) | VERIFIED | `docs/VALIDATION.md`, Phase 12 |
| Cross-domain build (subagent/main-session choice) | VERIFIED | `docs/VALIDATION.md`, Phase 9 |
| Cross-domain build (Agent Team, genuinely parallel) | **RUNTIME VALIDATION REQUIRED** | §22 item 2 — fallback path itself VERIFIED |
| Repository pattern vs. generic knowledge | VERIFIED | `docs/VALIDATION.md`, Phase 8 |
| Rejected unsafe pattern | VERIFIED | `docs/VALIDATION.md`, Phase 8 |
| Nonprod deployment (real apply + runtime validation) | **RUNTIME VALIDATION REQUIRED** | §22 item 1 |
| No authorization | VERIFIED | `docs/VALIDATION.md`, Phase 9 |
| Presentation truth | VERIFIED | `docs/VALIDATION.md`, Phase 10 |
| Output style invariance | VERIFIED | `docs/VALIDATION.md`, Phase 10 |
| D3 MUST FIX (fresh re-review required) | VERIFIED | `docs/VALIDATION.md`, Phase 4 + 3 independent-review rounds of this exact mechanism |
| Rejected hypothesis continuity | VERIFIED | `docs/VALIDATION.md`, Phase 5 (2 review rounds) |
| UNKNOWN / CONFLICTING EVIDENCE labeling | VERIFIED | `docs/VALIDATION.md`, Phase 1/2/4 |
| Teach-from-verified-work | VERIFIED | `docs/VALIDATION.md`, Phase 11 |

13 of 15 VERIFIED live. 2 RUNTIME VALIDATION REQUIRED, both for infrastructure reasons stated in §22, not fabricated or silently skipped.

## 25. Exact OpenSpec task status

`openspec/changes/groundwork-2-enterprise-sre/tasks.md`: every task across §0 (audit/design, both passes) and Phases 1-13 is closed — `[x]` (done, with an evidence pointer in the task text itself) or `[-]` (explicitly not applicable, with the reasoning inline — e.g. Phase 6's Tier-2 subtasks after the deferral, Phase 7's original curation subtasks after the M4 correction). Zero tasks remain `[ ]` unchecked:

```
$ grep -c '^\- \[ \]' openspec/changes/groundwork-2-enterprise-sre/tasks.md
0
$ openspec validate groundwork-2-enterprise-sre --strict
Change 'groundwork-2-enterprise-sre' is valid
```

Task 0.25 (owner sign-off) records the exact authorization this implementation proceeded under, including each of D1-D5's specific approval/strengthening/deferral, verbatim where it matters.

## 26. Commit and PR state

- **PR**: #20, merged into `main` on 2026-09-28.
- **Release branch**: `main`. Working branch `claude/groundwork-2-enterprise-upgrade-zx62y6` carried 22 commits (2 audit/design, 20 implementation/fix/docs) up to the merge, none force-pushed, none rewriting history.
- **Diff merged**: 44 files changed, 2766 insertions(+), 156 deletions(-) (measured pre-merge as `git diff --shortstat origin/main...HEAD`).
- **Merge commit**: `ddeb432d584dde920770ca646888355588cd7aa5`.
- **Post-merge follow-up**: two small documentation-only passes landed directly on `main` after the merge — `73d5d13` (release-report finalization) and this session's own CHANGELOG-completion and stale-marker-correction commit (see the git history for its hash).
- PR #20's description contains the final implementation/test summary and is retained as release history.

## 27. Installation instructions — exact commands

**This is a new machine (no prior Groundwork):**
```bash
git clone https://github.com/AshminPy/groundwork.git
cd groundwork
git checkout main
git pull --ff-only
./setup.sh
```
Requirements checked automatically: Claude Code ≥ 2.1 (must already be installed and signed in — not installed for you), Node ≥ 20.19.0, npm, Python 3.10+, git. Missing prerequisites are listed with the exact official command per OS and installed only after you answer **y** (or with `--install-prereqs`). `setup.sh` backs up your complete `~/.claude` first, asks three questions (profile, Agent Teams, dashboard schedule), then runs `install.sh`, applies the schedule, verifies, and prints a summary.

Scripted, non-interactive equivalent:
```bash
./setup.sh --non-interactive --profile work --no-agent-teams --schedule weekly
```

**This machine already has Groundwork 1.5.1 (the realistic work-laptop case, and the exact path this session live-tested in §18):**
```bash
cd groundwork && git pull
git checkout main
git pull --ff-only
./setup.sh                   # re-backs-up ~/.claude, re-installs, re-verifies; answers to the 3 questions are idempotent
```

## 28. Post-install verification — exact commands

```bash
./setup.sh --verify
```
Read-only; reports PASS/FAIL/NOT CONFIGURED for: Groundwork version (expect `2.0.0`), the 5 rule files, the 10 playbooks, the 4 hook files and their `settings.json` registration, ECC's installed plugin and version (`claude plugin details ecc@ecc`), OpenSpec's installed version, telemetry, the dashboard, and the reporting schedule.

Then, to confirm the rules genuinely load and function (not just that the files are present):
```bash
claude -p "List the evidence-policy.md labels you use to mark a factual claim's confidence, exactly as named in your loaded rules."
```
Expect all 7 labels, including `CONFLICTING EVIDENCE` and `UNKNOWN`. This is the exact check this session's own final clean-install test used to confirm end-to-end function on a genuinely fresh machine (§18, step 7).

If rolling back is ever needed: `./setup.sh --rollback` (moves the current `~/.claude` aside, never deletes it, restores the last backup — see `docs/UPGRADE-ROLLBACK.md`).

## 29. First recommended smoke-test task

Give Claude Code a small, real, low-risk task in an actual project that exercises the mechanisms this report leans on most heavily — repository-understanding plus a builder persona plus the review gate — for example:

> "In [a real nonprod Terraform-managed repo you have], add a new nonprod resource that follows the pattern of an existing similar one. Don't apply it — just implement, test/validate, and get it independently reviewed."

What to check in the response: (1) it inspects the existing analogous resource and repository convention before writing anything (§11); (2) it does not apply or claim anything is deployed without being told to (§10's authorization boundary); (3) if the change is MATERIAL-tier, a `REVIEW RESULT` block appears from a genuinely independent call, and if it finds anything, the session doesn't end until a fresh follow-up review reports `Must-fix: 0` (§9); (4) the final report's completion facts are commands-and-results, not a bare checklist. This single task touches repository-understanding, builder-role selection, the review gate, and completion-evidence reporting — the four mechanisms this release adds or strengthens the most — in one realistic pass, without needing a live cloud/Kubernetes target (which §22 already covers separately when you're ready to test that).

---

*Generated as part of the Groundwork 2.0.0 implementation in PR #20 and updated after merge to `main`. Every claim above traces to `docs/VALIDATION.md`, `openspec/changes/groundwork-2-enterprise-sre/{design.md,tasks.md}`, or a command re-run at report time (§16, §25). Nothing in this report was asserted without one of those three sources.*
