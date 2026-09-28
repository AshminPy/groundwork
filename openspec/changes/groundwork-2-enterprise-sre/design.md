# Groundwork 2.0 — Enterprise SRE Upgrade: Audit and Design

**Status: AUDIT / DESIGN phase. Nothing in this document is implemented.** All findings below are labelled VERIFIED (with source and date), INFERENCE, ASSUMPTION, UNVERIFIED, CONFLICTING EVIDENCE, UNKNOWN, or RUNTIME VALIDATION REQUIRED per the evidence taxonomy this document itself proposes extending. Repository inspection was performed directly against this checkout (`/home/user/groundwork`, branch `claude/groundwork-2-enterprise-upgrade-zx62y6`, HEAD `d40523a`) on 2026-09-28. Upstream facts were verified live against OpenSpec, ECC, and Claude Code's own sources on 2026-09-28 (raw GitHub content, the npm registry, and code.claude.com docs — full source list in §A.5).

---

## A. Current-state audit

### A.1 Method

Every rule file, playbook, hook, script, installer file, test file, and doc was read in full (not summarized from README claims). Hook and script behavior was independently verified by reading the actual Python/shell source, not inferred from `docs/ARCHITECTURE.md`'s own description of itself — in every case checked, the code matched the docs' claims (this is itself evidence of the repo's evidence-first discipline holding up under audit, not just being asserted). Upstream claims (Node version, ECC counts, Claude Code mechanisms) were independently re-verified against live sources rather than trusted from Groundwork's own (dated) VALIDATION.md entries — this caught one real, previously-undetected bug (§A.4, row on `installer-upstream-compatibility`).

### A.2 Component matrix — rules

| Component | Responsibility | Evidence | Decision |
|---|---|---|---|
| `rules/engineering-workflow.md` | Tier classification, execution order, completion facts, autonomy, execution-model selection, continuation procedure | Read in full; cross-checked against `docs/VALIDATION.md` 1.0.0–1.5.1 live evidence | **KEEP + STRENGTHEN** — §7 continuation procedure is strong for OpenSpec-tracked MATERIAL work; gains the continuity decision outcome (D2) and a reference to the extended evidence labels (D1/evidence-taxonomy) |
| `rules/architecture-quality.md` | Governing design principle, quality dimensions, pre-MATERIAL questions, variation-point rule | Read in full | **KEEP** — no material gap found against any Groundwork 2.0 acceptance criterion |
| `rules/evidence-policy.md` | Evidence priority, labels, DECISION record, validation ladder, completion-evidence table, RCA rule | Read in full; repo-wide grep confirmed `CONFLICTING EVIDENCE` and bare `UNKNOWN` do not appear anywhere in the repo | **KEEP + STRENGTHEN** — add the two missing labels (evidence-taxonomy); tighten §7 RCA rule to require one of them when applicable |
| `rules/task-routing.md` | One category per task, material-ambiguity clarification rule | Read in full; validated live in `docs/VALIDATION.md` 1.2.0 (12/12 correct categorization) | **KEEP** |
| `rules/output-contract.md` | Three-layer progressive-disclosure answer shape | Read in full; validated live across six categories in `docs/VALIDATION.md` 1.2.1–1.2.4 | **KEEP** |

### A.3 Component matrix — hooks

All four hooks were read in full by an independent code-audit pass (not just this document's author) that cross-checked every behavioral claim against actual line numbers.

| Component | Trigger | Enforces or reports | Decision |
|---|---|---|---|
| `hooks/block_protected_push.py` | PreToolUse (Bash) | **Enforces** (`permissionDecision: deny`) | **KEEP** — fail-open by explicit design, no hardcoded machine-specific values, documented known limitations (non-exact branch names, unparsed wrapper commands), adversarially tested (VALIDATION.md 1.1.0 security-reviewer pass reproduced and fixed 4 real bypasses) |
| `hooks/require_material_review.py` | Stop | **Enforces** presence of a reviewer-shaped call; does **not** enforce MUST FIX resolution | **KEEP + STRENGTHEN** — see Decision D3 |
| `hooks/groundwork_session_snapshot.py` | SessionStart | Reports only (injects `additionalContext`) | **KEEP + STRENGTHEN** — gains the continuity decision outcome (D2) if extension is chosen; shares a byte-for-byte-duplicated `dirty_change_names()` helper with `require_material_review.py` (confirmed by direct code read) — **CONSOLIDATE** the helper regardless of any other decision (trivial, no behavior change, pure maintainability fix) |
| `hooks/groundwork_telemetry.py` | Stop | Reports only, never blocks | **KEEP** — privacy filtering (token/path/secret redaction) is directly and explicitly tested (`tests/test_telemetry.py` lines 224-234, confirmed by direct code+test read); no material gap |

No hardcoded personal usernames, credentials, account IDs, or non-portable machine identity were found in any hook (independently confirmed by a repo-wide search covering `rules/`, `hooks/`, `scripts/`, `install.sh`, `uninstall.sh`, `setup.sh` — every path reference resolves through `$HOME`/`os.path.expanduser`/`$CLAUDE_CONFIG_DIR`). The only literal machine-specific-looking content found anywhere is inside `docs/VALIDATION.md`, which is *evidence of real test runs on the maintainer's machine* (e.g. real backup timestamps, a real project path used as a live-test `cwd`) — correctly out of scope for portability, since none of it is copied to `~/.claude` by the installer. This satisfies acceptance criterion 17 (no personal credentials/hardcoded identity) **without any change needed.**

### A.4 Component matrix — scripts and installer

| Component | Decision | Evidence |
|---|---|---|
| `scripts/merge_settings.py` / `scripts/unmerge_settings.py` | **KEEP** | Atomic writes (`write_atomic`: temp file + `os.replace`), idempotent (matched by exact command string), one documented and tested known limitation (a user value equal to a Groundwork default is indistinguishable on unmerge) — this is an accepted, honestly-documented tradeoff, not a gap |
| `scripts/migrate_legacy_rules.py` | **KEEP** | One-time, symlink-safe, silent no-op when nothing to migrate |
| `scripts/groundwork_report.py` | **KEEP** | Python↔JS metric parity is directly tested under Node; atomic writes; privacy-safe (aggregated counters only, no session IDs/paths in output) |
| `scripts/check_routing.py` | **KEEP** | Correctly and honestly self-labelled as non-deterministic, live, cost-real-money evidence — not a unit test, does not claim to be one |
| `install.sh` | **STRENGTHEN** | VERIFIED (direct read, `install.sh:43`): checks only that `node` exists on `PATH`, performs **no version-number comparison at all** — the printed error text claims "Node >=18" but nothing enforces even that number, let alone the correct one |
| `setup.sh` | **STRENGTHEN** | VERIFIED (direct read, `setup.sh:69`): `NODE_MIN=18`, hardcoded and — per §A.5 below — wrong |
| `uninstall.sh` | **KEEP** | Symmetric with install.sh, correctly preserves user data (telemetry/reports), no backup needed because it is non-destructive of user-authored files by construction |

### A.5 The Node/OpenSpec version bug — VERIFIED with primary sources (2026-09-28)

This is the one clear-cut defect found in this audit, not a design tradeoff:

- `raw.githubusercontent.com/Fission-AI/OpenSpec/main/package.json` (fetched 2026-09-28): `"engines": {"node": ">=20.19.0"}`.
- `raw.githubusercontent.com/Fission-AI/OpenSpec/main/README.md` (fetched 2026-09-28), line 125: "**Requires Node.js 20.19.0 or higher.**"
- `registry.npmjs.org/@fission-ai/openspec` version metadata (fetched 2026-09-28) — `engines.node` is `>=20.19.0` for **every** version checked back to and including **1.12.0** (published 2026-09-03) — the exact version Groundwork's own `CHANGELOG.md` (line 138) recorded as "unchanged" at its 2026-09-20 audit. **This means the Node ≥18 claim in `README.md`, `install.sh`, and `setup.sh` has been wrong since before Groundwork 1.1.0 shipped — this predates the 2026-09-20 audit, it did not drift afterward.**
- By contrast, ECC's own floor is genuinely 18: VERIFIED by downloading and inspecting the actual npm tarball `ecc-universal@2.2.1` (the version `install.sh` actually installs) — `package.json`: `"engines": {"node": ">=18"}`. **The mismatch is asymmetric**: ECC is fine at Node 18; OpenSpec is not, and Groundwork's current single combined floor silently favors the wrong (lower) requirement.
- OpenSpec has also released three further versions since Groundwork's last audit (1.12.0 → 1.13.0 → 1.13.1 → 1.13.2, the current `latest` as of 2026-09-28, published 2026-09-23) — `openspec list --json` / `openspec status --all --json`, the two commands Groundwork's continuation design depends on, are VERIFIED still present and referenced as current in OpenSpec's own changelog through 1.13.2.

**Consequence, VERIFIED by direct code read**: because `install.sh` never checks the Node version number and only `setup.sh` does (with the wrong number), an engineer who runs `install.sh` directly against Node 18 or 19 gets no warning at install time; the OpenSpec CLI call inside `openspec init`/`/opsx:*` fails downstream with whatever error Node itself produces, not a clear Groundwork message. Anyone who *did* successfully use OpenSpec through Groundwork today was, necessarily, already running Node ≥20.19 for unrelated reasons — so this is not a claim that OpenSpec use is currently broken for existing users, only that the stated and enforced floor cannot be trusted and the failure mode for a Node 18/19 user is currently silent-until-cryptic rather than fast and clear.

### A.6 ECC and OpenSpec version drift — VERIFIED (2026-09-28)

- ECC's GitHub `main` branch (`affaan-m/ECC`) is at `2.2.2` (CHANGELOG dated 2026-09-15) with README-claimed "68 agents, 292 skills" — but **npm has not published 2.2.2**; `registry.npmjs.org/ecc-universal` `dist-tags.latest` is still `2.2.1` (published 2026-09-08), which is what `install.sh` actually installs (`claude plugin install ecc@ecc`, using whatever the marketplace resolves — VERIFIED to currently resolve to the npm-published 2.2.1 content by direct tarball inspection: `ls agents | wc -l` → 68, `ls skills | wc -l` → 286, matching Groundwork's own documented claim exactly).
- **This is CONFLICTING EVIDENCE that resolves cleanly once the two sources are distinguished**: GitHub `main` is a preview of unreleased work; npm is the actual install source. Groundwork's "68 agents, 286 skills" claim is **VERIFIED accurate for what installs today**, but the design should note the claim is pinned to an npm dist-tag, not to GitHub — if ECC's 2.2.2 is ever published, or if a future install path switches to a GitHub checkout, the counts (and any capability matrix built on them, §D) go stale silently.
- OpenSpec's version (§A.5) and ECC's version are both more current upstream than Groundwork's `CHANGELOG.md`/`docs/ARCHITECTURE.md` record. Recommended fix: a documentation refresh (Phase 1, §E) plus a **non-network** "last verified against" marker that `setup.sh --verify` can compare the *installed* version against, so drift is visible without adding a live network dependency to every install run (consistent with the existing no-network design of `groundwork_report.py` and the general "don't over-pin, verify lightly" guidance).

### A.7 Component matrix — docs, tests, OpenSpec state

| Component | Decision | Notes |
|---|---|---|
| `README.md`, `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`, `docs/TROUBLESHOOTING.md`, `docs/UPGRADE-ROLLBACK.md`, `docs/FUTURE-SCOPE.md`, `CHANGELOG.md`, `CREDITS.md` | **KEEP + STRENGTHEN** | Exceptionally well-maintained and evidence-backed already; needs the version-number refresh in §A.6 and a corrected Node floor in §A.5 |
| `tests/test_hooks.py`, `test_playbooks.py`, `test_report.py`, `test_setup.py`, `test_telemetry.py` | **KEEP + STRENGTHEN** | Confirmed by independent code-audit read: zero compaction/fresh-session-recovery tests exist anywhere in the suite; zero "conflicting evidence" tests exist (the suite's "unknown" handling is tested only as *absent-or-unparseable-degrades-gracefully*, not as *genuinely conflicting sources reconciled*); zero tests enforce a Node version check in `install.sh` (because none exists to test) |
| `openspec/specs/{task-routing,onboarding,usage-telemetry,health-dashboard}/spec.md` | **KEEP** | Accurate, archived, current baseline |
| `openspec/changes/intelligent-engineering-harness/` | **See Open Question 1, §H** | Substantially shipped (all rule/hook/installer/test tasks checked, code matches design); deliberately left unarchived because task 6.4 (a live fresh-session `claude -p` proof) is genuinely blocked on `claude auth login` on the machine it was built on — this is the repo's evidence discipline working correctly, not a defect. It is a real dependency for this change: `project-continuation`, `validation-and-review-evidence`, and `harness-installation` are capabilities this proposal modifies, and they currently exist only as *delta* specs inside this unarchived change, not yet in `openspec/specs/` |

### A.8 ECC integration posture

| Component | Decision | Notes |
|---|---|---|
| ECC install (`install.sh:52-60`, `claude plugin marketplace add affaan-m/ECC` + `claude plugin install ecc@ecc --scope user --config hook_profile=standard`) | **STRENGTHEN via new policy, not REPLACE** | Currently installs all 68 agents/286 skills unconditionally. VERIFIED (§D): ECC's own installer supports `--profile`, `--skills`, `--with capability:*` at install time, and Claude Code itself now has `skillOverrides`/`Skill()` permission rules and a `paths` skill-scoping field that did not factor into the original 1.0.0 "nothing exists to curate this" conclusion recorded in `docs/TROUBLESHOOTING.md`. Groundwork does not fork or vendor ECC content either way — it only chooses which of ECC's own capabilities to select, which is squarely Groundwork's "policy" ownership role (§C) |

---

## B. Gap analysis against the 22 non-negotiable acceptance criteria

Each criterion below is the corresponding numbered item from the requesting brief §28, checked directly against repository evidence (not against what the docs claim about themselves).

| # | Criterion | State | Evidence |
|---|---|---|---|
| 1 | Evidence-backed factual claims | **MET** | `evidence-policy.md` §1-2, 4; enforced structurally by `output-contract.md`; validated live repeatedly in VALIDATION.md |
| 2 | Unsupported RCA conclusions prevented | **MOSTLY MET** | `evidence-policy.md` §7 + TROUBLESHOOT playbook steps 4-6 already refuse to promote a symptom to a root cause; strengthened by evidence-taxonomy (adds explicit labels for the "can't tell" case) |
| 3 | UNKNOWN is a valid outcome | **PARTIAL** | Telemetry has an `unknown` outcome/validation bucket (tested); `evidence-policy.md`'s label set has no bare `UNKNOWN` — closest is `RUNTIME VALIDATION REQUIRED` (execution-gated) and `UNVERIFIED` (not-yet-checked), neither of which means "cannot be determined at all" |
| 4 | Conflicting evidence surfaced | **NOT MET** | Confirmed absent repo-wide; no label, no rule text, no test |
| 5 | Repository/runtime outranks saved memory | **MET** | `evidence-policy.md` §8, `engineering-workflow.md` §7 step 6 |
| 6 | False completion claims prevented | **MET, strong** | `engineering-workflow.md` §3 hard rules, `evidence-policy.md` §6 completion-evidence table, telemetry's declared-vs-observed reconciliation (tested, `test_telemetry.py`) |
| 7 | MATERIAL work receives meaningful independent review | **PARTIAL** | Presence is enforced deterministically (`require_material_review.py`); outcome/MUST-FIX-resolution is not — see Decision D3 |
| 8 | Critical state survives context compaction | **PARTIAL, untested** | Strong for OpenSpec-tracked MATERIAL work; no mechanism or test exists for TRIVIAL/STANDARD/RCA work, which is most troubleshooting |
| 9 | Fresh sessions accurately recover unfinished work | **MOSTLY MET for MATERIAL work** | `engineering-workflow.md` §7 + snapshot hook, live-validated in VALIDATION.md 1.1.0 (session-1 continuation proof); weaker for non-OpenSpec-tracked work (same gap as #8) |
| 10 | Rejected hypotheses remain rejected after recovery | **NOT MET, NOT TESTED** | No mechanism; confirmed zero tests of this scenario anywhere |
| 11 | Main/subagent/team execution selected automatically | **MET** | `engineering-workflow.md` §6, live-validated |
| 12 | Unnecessary context minimized | **PARTIAL** | Playbook progressive disclosure works well; ECC's ~20K-token always-on cost (VALIDATION.md 1.0.0: roughly doubles trivial-task cost) is the largest unaddressed context cost and has no curation today |
| 13 | ECC exposure curated for SRE/CloudOps | **NOT MET** | Confirmed: full, uncurated install; see §D |
| 14 | OpenSpec used only when justified by materiality | **MET** | `engineering-workflow.md` §1 tier table, `FUTURE-SCOPE.md` §4 |
| 15 | Safety-critical controls deterministic where practical | **PARTIAL** | Git-push guard + ECC's GateGuard/`block-no-verify` cover their scope well; cloud/IaC/IAM/destructive-IaC-apply is explicitly advisory-only today (`FUTURE-SCOPE.md` §10) — see Decision D5 |
| 16 | Install/update/rollback/uninstall are safe | **MET, exceptionally well validated** | Minor strengthen: Node version enforcement gap (§A.5) |
| 17 | No personal credentials/hardcoded identity | **MET** | Confirmed by direct repo-wide search (§A.3) |
| 18 | External work updates based on evidence | **OUT OF SCOPE for this phase** | Per the requesting brief §21, automation is explicitly Phase 2, only after 2.0's core stabilizes; not designed here |
| 19 | Telemetry useful without leaking sensitive content | **MET, thoroughly tested** | `test_telemetry.py` lines 224-234 directly test secret/path/token redaction |
| 20 | Existing intended behavior has not regressed | **Process requirement, not a component** | Addressed by the migration plan's non-regression gate (§E) |
| 21 | System remains understandable and maintainable | **MET**, one small wart | Exceptional documentation discipline; one duplicated helper function (§A.3) |
| 22 | Usable without understanding internals | **MET** | "Continue this project." live-validated; natural-language routing 12/12 in VALIDATION.md |

**Net finding: 13 of 22 criteria are already met, 7 are partially met with a specific, evidence-identified cause, 1 (RCA rejected-hypothesis survival) is fully unmet, and 1 (external work automation) is explicitly out of scope for this phase.** This is a narrow, well-bounded gap set — consistent with "this is not a rewrite."

---

## C. Target architecture and ownership boundaries

The existing responsibility split (`docs/ARCHITECTURE.md`) is correct and is **not changed** by this proposal:

```
OpenSpec   → WHAT / WHY / acceptance criteria (unchanged)
ECC        → HOW: specialist agents/skills (unchanged in kind; curated in SELECTION — see D4)
Claude Code → runtime primitives: subagents, Agent Teams, hooks, permissions,
              skillOverrides/Skill() rules, memory (unchanged; two more of its
              existing primitives — skillOverrides, paths-scoping — are newly
              put to use by Groundwork's own policy)
Groundwork → governance: policy, routing, safety, evidence integrity,
             validation, continuity, completion truth (unchanged role;
             gains two new small policy surfaces — evidence-taxonomy and
             ecc-capability-policy — and, pending Decisions D2/D5, at most
             one new hook and one new small state artifact)
```

Where each proposed capability attaches:

| Capability | Owner file(s) | New surface? |
|---|---|---|
| `evidence-taxonomy` | `rules/evidence-policy.md` §2, §7 | Rule text only — no new hook, no new file |
| `installer-upstream-compatibility` | `install.sh`, `setup.sh`, `README.md` | Corrects existing checks; no new file |
| `review-evidence-strengthening` | `rules/engineering-workflow.md` §2.6, `hooks/require_material_review.py` | Extends the existing hook; no new hook |
| `ecc-capability-policy` | `install.sh` (ECC install command flags), new short `rules/ecc-capability-policy.md` OR a section inside `engineering-workflow.md` (open question — see D4), `scripts/merge_settings.py` (only if `skillOverrides` is confirmed to apply to plugin skills) | One new small rule surface; no new hook |
| `investigation-continuity` (D2) | Either an extension of `engineering-workflow.md` §7 + `groundwork_session_snapshot.py` (Option A) or those plus one new small, capped state file (Option B) | Zero or one new file, decision-pending |
| `deterministic-safety-expansion` (D5) | One new hook, narrowly scoped, only if approved | Zero or one new hook, decision-pending |

No component changes ownership. No responsibility moves from OpenSpec to Groundwork or vice versa. ECC's role does not change in *kind* (still "HOW: specialist agents/skills") — only Groundwork's *selection policy* over it is new, which is exactly the "Groundwork = policy" row in the requesting brief's own target ownership table (§12).

---

## D. ECC capability matrix

**Verification basis**: counts, install-time selection mechanisms, and the full real name-level listing are all VERIFIED against the actual published `ecc-universal@2.2.1` npm tarball (the version `install.sh` installs today), downloaded directly from the npm registry and checksum-confirmed against the registry's own published SHA1 (`04845ca88b9cadb303b4e9a4d519f90429f8b49e`) — not GitHub `main`, not inferred from README prose. Every category below is grouped from the real 68 agent filenames and 286 skill directory names (both counted directly off the extracted filesystem, both sums independently verified to add up to the published totals). Fetched/verified 2026-09-28.

### D.1 Selection mechanisms available today (this is the key finding — none of this existed when Groundwork's "no config lever" conclusion in `docs/TROUBLESHOOTING.md` was written, or it existed and was not re-checked)

- **ECC's own install-time filters** (VERIFIED, ECC 2.2.1 README): `--profile minimal|core|full`, `--without baseline:hooks`, `--no-hooks`, explicit `--skills a,b,c`, and capability-tag selection `--with capability:machine-learning`.
- **Claude Code's `skillOverrides`** (VERIFIED, code.claude.com/docs/en/skills, fetched 2026-09-28): four states (`on`/`name-only`/`user-invocable-only`/`off`) settable in `.claude/settings.json`, editable via `/skills`. **RUNTIME VALIDATION REQUIRED**: Groundwork's own `docs/TROUBLESHOOTING.md` currently states "`skillOverrides` does not affect plugin-provided skills" — this was true or believed true as of an earlier test, but was not re-verified in this audit against the current Claude Code version, and the docs fetched today describe `skillOverrides` generally without confirming plugin-skill scope specifically. This must be tested live before `ecc-capability-policy` can rely on it (see Decision D4 and the acceptance matrix, §F).
- **`Skill(name)` / `Skill(name *)` permission rules and `disableBundledSkills`** (VERIFIED, same source) — a coarser, permission-level on/off.
- **Whole-plugin disable** (`claude plugin disable ecc@ecc`) — already known and documented (`docs/TROUBLESHOOTING.md`); too coarse for per-capability curation, useful only as an escape hatch.
- **`ECC_DISABLED_MCPS`** — VERIFIED to be an ECC install/sync-time filter, not a live runtime toggle (ECC's own docs, quoted verbatim by the verification pass) — not usable for the curation goal.

### D.2 Skill matrix (286 total, real names, grouped by ECC's own directory-naming convention — sums independently verified to equal 286)

| Category | Count | Representative names | SRE/CloudOps relevance | Recommended default |
|---|---|---|---|---|
| `infra_sre` — deployment, containers/orchestration, CI/git ops, network diagnostics | 26 | `docker-patterns`, `kubernetes-patterns`, `canary-watch`, `deployment-patterns`, `production-audit`, `production-scheduling`, `github-ops`, `git-workflow`, `network-bgp-diagnostics`, `network-config-validation` | **CORE SRE** — the single most directly relevant category. **Important caveat, VERIFIED**: no `aws-*`, `gcp-*`, `azure-*`, or `terraform-*` skill exists anywhere in the published 286 (checked directly, zero matches); several of this category's own skills (`homelab-vlan-segmentation`, `homelab-wireguard-vpn`, `cisco-ios-patterns`, `netmiko-ssh-automation`) are home-lab/on-prem-network-hardware scoped, not hyperscaler-cloud scoped | Enabled by default, **minus** the home-lab/on-prem-hardware subset (out of place for an enterprise default, not unsafe — just off-topic) |
| `database` — schema/query/migration patterns | 7 | `postgres-patterns`, `mysql-patterns`, `redis-patterns`, `database-migrations`, `clickhouse-io` | **CORE SRE** — production data-layer operations, written from an app-dev rather than DBA/ops angle but directly useful | Enabled by default |
| `testing_qa` — TDD, e2e, verification gates per stack | 25 | `tdd-workflow`, `e2e-testing`, `verification-loop`, `browser-qa`, `ai-regression-testing` | **OPTIONAL SRE** — reliability-adjacent (shift-left), not itself production-ops | Enabled by default, narrow |
| `security` — security review/scanning/compliance | 13 | `security-review`, `security-scan`, `security-bounty-hunter`, `hipaa-compliance`, `django-security` | **OPTIONAL SRE, mixed** — VERIFIED: dominated by app-layer/framework and vertical-compliance security (healthcare PHI, DeFi); **no IAM, secrets-management, or cloud-security-posture skill found in the set** — a real gap in ECC itself, not something Groundwork curation can manufacture | Enable the general `security-review`/`security-scan` items by default; the vertical-compliance items (healthcare, DeFi) on demand only |
| `agent_meta` — Claude Code/ECC harness engineering itself (orchestration, evals, cost/context budgeting) | 69 | `agent-eval`, `context-budget`, `team-agent-orchestration`, `gateguard`, `token-budget-advisor` | **NOT RELEVANT TO GROUNDWORK DEFAULT** — this is the single largest skill category (69, 24% of all 286) and it is meta-tooling for operating AI agents, not infrastructure/production engineering | Disabled by default; on demand only |
| `business_ops` — marketing, sales, finance, supply chain | 41 | `customer-billing-ops`, `investor-outreach`, `market-research`, `seo`, `logistics-exception-management` | **NOT RELEVANT TO GROUNDWORK DEFAULT** — second-largest category (41, 14%), clearly non-engineering | Disabled by default |
| `lang_framework` — single-language/framework coding idioms | 40 | `android-clean-architecture`, `django-patterns`, `nextjs-turbopack`, `rust-patterns`, `swiftui-patterns` | **LANGUAGE/PROJECT-SPECIFIC** | Disabled by default; enabled on demand to match a project's actual stack |
| `architecture_quality` — general architecture/code-quality practice | 18 | `api-design`, `architecture-decision-records`, `hexagonal-architecture`, `error-handling` | **OPTIONAL SRE** — `error-handling` and `mcp-server-patterns` have production-reliability relevance; the rest is general SWE discipline already covered by Groundwork's own `architecture-quality.md` | On demand |
| `datasci_ml` — ML/AI research, literature, retrieval | 22 | `deep-research`, `iterative-retrieval`, `mle-workflow`, `scientific-thinking-literature-review` | **NOT RELEVANT TO GROUNDWORK DEFAULT** | Disabled by default |
| `design_ux` — accessibility, frontend design systems | 14 | `accessibility`, `design-system`, `frontend-a11y`, `motion-ui` | **NOT RELEVANT TO GROUNDWORK DEFAULT** | Disabled by default |
| `media_creative` — video/image/3D generation | 8 | `manim-video`, `remotion-video-creation`, `blender-motion-state-inspection` | **NOT RELEVANT TO GROUNDWORK DEFAULT** | Disabled by default |
| `docs`, `crypto` (small) | 3 | `code-tour`, `documentation-lookup`, `evm-token-decimals` | Mixed/negligible | On demand |

### D.3 Agent matrix (68 total, real filenames — sums independently verified to equal 68)

| Category | Count | Representative names | SRE/CloudOps relevance | Recommended default |
|---|---|---|---|---|
| `infra_network` | 3 | `network-architect`, `network-troubleshooter`, `homelab-architect` | **CORE SRE**, but small and, per the `homelab-` naming, home-lab-scale rather than enterprise-cloud-scale | Enabled by default |
| `engineering_meta` — planning, code quality, process | 22 | `architect`, `planner`, `code-explorer`, `code-reviewer`, `performance-optimizer`, `silent-failure-hunter`, `tdd-guide` | **CORE SRE for the subset already named in `engineering-workflow.md` today** (`code-explorer`, `planner`, `code-reviewer`, `security-reviewer` — confirmed these are real agent names, not aspirational); `performance-optimizer` and `silent-failure-hunter` add production-reliability value | Enable the subset Groundwork's rules already reference by name, plus `performance-optimizer`/`silent-failure-hunter`; rest on demand |
| `code_reviewers` — language/domain-specific review | 23 | `python-reviewer`, `security-reviewer`, `database-reviewer`, `network-config-reviewer`, `rust-reviewer` | **CORE SRE for 3** (`security-reviewer`, `database-reviewer`, `network-config-reviewer`); **LANGUAGE-SPECIFIC for the rest** (20 language reviewers) | The 3 infra-relevant reviewers by default; language reviewers on demand to match project stack |
| `build_resolvers` — per-language build/compile-error fixers | 12 | `go-build-resolver`, `rust-build-resolver`, `pytorch-build-resolver` | **LANGUAGE/PROJECT-SPECIFIC** | On demand |
| `gan_ml`, `opensource_pipeline`, `business_marketing` | 8 | `gan-evaluator`, `opensource-packager`, `marketing-agent` | **NOT RELEVANT TO GROUNDWORK DEFAULT** | Disabled by default |

### D.4 The single most important finding in this matrix

**VERIFIED**: across all 286 skills and 68 agents, **there is no AWS, GCP, Azure, or Terraform skill or agent at all**, and the infrastructure skills that do exist skew materially toward home-lab/on-prem network hardware (Cisco IOS, Netmiko SSH, WireGuard, VLAN segmentation) rather than enterprise/hyperscaler cloud operations. Roughly **33 of 286 skills** (`infra_sre` 26 + `database` 7) are squarely infra/platform-relevant, plus **13** security skills with partial (mostly app-layer, not infra-security) relevance and **25** testing/QA skills with reliability-adjacent relevance — against **69** agent-operations/harness-meta skills and **41** business-operations skills, together over a third of the entire catalog, that are not software-engineering skills at all. **This means ECC curation for SRE/CloudOps is not just a context-cost optimization — it materially corrects what the default experience looks like**, because more than a third of what installs today by default has nothing to do with engineering, and the infra-relevant fraction that remains has a real, evidence-confirmed coverage gap (no cloud-provider or IaC-tool skill) that Groundwork's curation cannot manufacture — it can only make the absence visible instead of silently diluted among 286 mostly-irrelevant entries. This gap (no AWS/GCP/Azure/Terraform coverage in ECC) is worth reporting upstream to ECC's maintainer; it is not something Groundwork can or should fork ECC to fix.

---

## E. Migration plan — smallest safe changes first

Every phase below is independently mergeable, independently testable, and independently revertable. No phase depends on Decision D2 or D5 being resolved a particular way — each names what changes for either outcome.

### Phase 1 — Correctness fixes (no design decisions required, lowest risk)
- **Objective**: fix the Node/OpenSpec version bug (§A.5); refresh ECC/OpenSpec version references (§A.6); consolidate the duplicated `dirty_change_names()` helper (§A.3).
- **Files**: `install.sh`, `setup.sh`, `README.md`, `docs/ARCHITECTURE.md`, `docs/UPGRADE-ROLLBACK.md`, `CHANGELOG.md`; new small shared helper module imported by `require_material_review.py` and `groundwork_session_snapshot.py`.
- **Behavior change**: `install.sh` gains a real Node version check (currently has none); the enforced floor changes from 18 to 20.19.0 in both `install.sh` and `setup.sh`.
- **Compatibility risk**: **breaking for Node 18/19 environments** — by design (see proposal.md Impact). Must be called out prominently in `CHANGELOG.md` as a corrected requirement, not a new one.
- **Tests**: extend `tests/test_setup.py`/a new install-focused test for the corrected version check; non-regression SHA-256 baseline re-run on all currently-protected files.
- **Rollback**: trivial — pure `git revert`, no state migration involved.

### Phase 2 — Evidence taxonomy and RCA strengthening (rule text only)
- **Objective**: add `CONFLICTING EVIDENCE` and `UNKNOWN` labels (§B item 3-4); tighten the RCA rule.
- **Files**: `rules/evidence-policy.md`, `playbooks/troubleshoot.md` (cross-reference only, no structural change), `docs/ARCHITECTURE.md`.
- **Behavior change**: none deterministic (rule text is advisory, per the existing enforced-vs-advisory table in `docs/ARCHITECTURE.md`) — this is a **KEEP + STRENGTHEN** of an advisory mechanism, consistent with how every other evidence-policy addition has shipped historically.
- **Compatibility risk**: none — additive to a rule file.
- **Tests**: new classifier-style test cases (model-behavior observation, not a hook unit test, matching how `evidence-policy.md` additions have always been validated in `docs/VALIDATION.md`).
- **Rollback**: trivial.

### Phase 3 — Review evidence strengthening (Decision D3, see below)
- **Objective**: implement whichever option D3 selects.
- **Files**: `rules/engineering-workflow.md` §2.6, `hooks/require_material_review.py`.
- **Tests**: new `test_hooks.py` cases for the strengthened check; must not regress any of the 14 existing review-gate sub-cases.
- **Rollback**: hook change is isolated and independently revertable from Phase 1/2.

### Phase 4 — ECC capability policy (Decision D4, see below)
- **Objective**: implement the curated default install profile using §D.2/D.3's now-populated real data, once the `skillOverrides`-on-plugin-skills question is runtime-validated.
- **Files**: `install.sh` (ECC install command), new small rule surface (file TBD by D4), `scripts/merge_settings.py` if `skillOverrides` entries are needed.
- **Compatibility risk**: **medium** — this changes what capabilities are available by default to every existing installation that re-runs `install.sh`. Must be additive-safe (existing installs should not lose a capability they were relying on without a clear upgrade note) and must offer an escape hatch (`--ecc-profile full` or equivalent) back to today's wholesale install.
- **Tests**: install-layout tests verifying the profile flag reaches ECC's installer correctly; a runtime-validation test (live, not unit) confirming a disabled skill is actually not auto-invoked.
- **Rollback**: `--ecc-profile full` flag, or `uninstall.sh`/reinstall.

### Phase 5 — Investigation continuity (Decision D2, see below)
- **Objective**: implement whichever option D2 selects; add the compaction/fresh-session-recovery test suite (rejected-hypothesis-stays-rejected as an explicit, named test case) regardless of which option is chosen — Option A needs it to prove the existing git/OpenSpec model actually holds up under a constructed compaction scenario; Option B needs it to prove the new artifact does.
- **Files**: depends on D2's outcome (§C table).
- **Compatibility risk**: low if Option A (no new file, tests only); low-medium if Option B (one small new file, must be added to `install.sh`/`uninstall.sh`'s managed-file list and to the portability/telemetry-privacy review).
- **Tests**: the deterministic compaction/fresh-session scenarios required by the requesting brief §9-10 — this is the one acceptance criterion (#10) currently fully unmet, so this phase is what actually closes it.
- **Rollback**: Option A is test-only (trivially revertable); Option B needs an uninstall-path addition, itself tested per the existing installer-safety pattern.

### Phase 6 — Deterministic safety expansion (Decision D5, see below) — lowest priority, most caution
- **Objective**: implement only if D5 is approved, and only the narrow scope D5 recommends.
- **Files**: one new hook, mirroring `block_protected_push.py`'s structure (fail-open, pattern-matched, depth-limited shell parsing).
- **Compatibility risk**: **highest of any phase** — a new PreToolUse deny hook can block legitimate work if over-scoped. Must go through the same adversarial-review process `block_protected_push.py` went through (a security-reviewer pass explicitly trying to find both bypasses *and* false-positive legitimate commands it would wrongly block).
- **Tests**: adversarial bypass tests (mirroring the 19 push-guard test cases) plus false-positive tests (commands that must NOT be blocked).
- **Rollback**: hook removal from `settings.json`, or `GROUNDWORK_<HOOK>=off` env escape hatch (matching the existing pattern for the snapshot and telemetry hooks).

**Order rationale**: Phase 1 fixes a real, live bug and should not wait on any design decision. Phases 2-3 strengthen existing advisory/enforced mechanisms with no new surface area. Phase 4 delivers the largest context/cost win (ECC curation directly addresses acceptance criteria 12-13) but needs the §D.2 data gap closed first. Phase 5 closes the one fully-unmet acceptance criterion (#10) but is explicitly a "genuine owner decision" per Groundwork's own autonomy rule (`engineering-workflow.md` §4) — multiple valid architectures, no repository evidence alone picks one. Phase 6 is last because it is the only phase that adds new deterministic *blocking* surface with real false-positive risk, and the repo's own validation-driven-evolution principle (`FUTURE-SCOPE.md` §12: "a real task exposed a gap" before a mechanism is added) is the weakest match for exactly this item — no incident has yet demonstrated the advisory rule (§10 of the requesting brief's own safety section, currently `evidence-policy.md`/`architecture-quality.md` advisory text) was insufficient.

---

## F. Acceptance matrix — every Groundwork 2.0 requirement mapped to a concrete validation method

This maps each proposed capability's core requirement to (a) the acceptance criterion it closes from §B, and (b) the concrete, named method that will demonstrate it — not just "tests pass." Full scenario-level detail lives in each capability's `specs/*/spec.md`; this table is the traceability summary.

| Capability / requirement | Closes acceptance criterion (§B #) | Validation method |
|---|---|---|
| `evidence-taxonomy`: `UNKNOWN`/`CONFLICTING EVIDENCE` labels exist and are used correctly | #3, #4 | Model-behavior observation on constructed RESEARCH/TROUBLESHOOT prompts engineered to have no answer or two conflicting sources, matching the validation style already used for every prior rule-text-only Groundwork change (`docs/VALIDATION.md`) |
| `evidence-taxonomy`: RCA rule requires an honest label, never a promoted guess | #2 | Same as above, applied to TROUBLESHOOT playbook scenarios specifically; non-regression via SHA-256 baseline on unrelated files |
| `installer-upstream-compatibility`: correct, enforced Node floor | #16 | `tests/test_setup.py`-style fixture with a stubbed sub-20.19 Node on PATH, asserting refusal with a clear message, mirroring the existing old-Node test pattern already in the suite |
| `installer-upstream-compatibility`: `install.sh` checks the version, not just presence | #16 | Same fixture run directly against `install.sh`, not only `setup.sh` |
| `review-evidence-strengthening`: MUST-FIX review requires follow-up work before Stop | #7 | New `test_hooks.py` cases (constructed transcripts: MUST-FIX-then-Stop blocks, MUST-FIX-then-edit-then-Stop allows) plus the existing 14 review-gate cases re-run unchanged |
| `ecc-capability-policy`: curated default excludes NOT-RELEVANT categories | #12, #13 | Install-layout test asserting the ECC install command carries the curated profile flags; a live fresh-session check that a curated-out skill is not offered |
| `ecc-capability-policy`: `skillOverrides` only used if confirmed effective on plugin skills | #12, #13 | One live runtime test (§D.1) — this is RUNTIME VALIDATION REQUIRED and must run before Phase 4 ships, not be assumed either way |
| `ecc-capability-policy`: measured context-cost reduction | #12 | Direct token-count comparison, curated vs. full install, at session start — matching the measurement rigor of the original ECC cost evidence in `docs/VALIDATION.md` 1.0.0 |
| `investigation-continuity`: rejected hypothesis never resurfaces as active/verified after recovery | #10 | The explicit named test case required by the requesting brief §9 — a constructed long investigation with rejected hypotheses, simulated compaction, and a fresh-session handoff, asserting the rejected status survives |
| `investigation-continuity`: recovered state revalidated against current repo/runtime | #5 (extended to the new mechanism) | Test: recovered state contradicted by current evidence is reported and overruled, not trusted |
| `investigation-continuity`: no chain-of-thought persisted | requesting brief §8 (not separately numbered in §B, carried by #8/#9) | Direct inspection of the persisted content's schema/fields against the allowed list |
| `deterministic-safety-expansion` (if approved): bypass resistance | #15 | Adversarial test pass reproducing the approved scope's known bypass classes, mirroring the push guard's own 19-case suite |
| `deterministic-safety-expansion` (if approved): no false positives on legitimate commands | #15, and the requesting brief's own "not excessive confirmations" caution (§17) | A security-reviewer pass specifically hunting for legitimate commands the guard would wrongly block, before ship |
| Cross-cutting: no completion claim exceeds its evidence | #6, #20 | Existing completion-facts hard rules (`engineering-workflow.md` §3) applied unchanged to every phase's own `docs/VALIDATION.md` entry; this document's own tasks.md leaves every implementation task unchecked until its evidence exists |
| Cross-cutting: no personal/hardcoded identity introduced by any phase | #17 | Repeat the repo-wide portability search (§A.3 method) after each phase, before merge |
| Cross-cutting: install/upgrade/rollback/uninstall stay safe through all phases | #16 | Full `tests/test_setup.py` re-run plus a live upgrade-from-1.5.1 rehearsal (tasks.md §7) |

## G. Decisions requiring owner input before implementation

These follow the repo's own DECISION record format (`evidence-policy.md` §3) and are presented, not resolved — per the requesting brief's explicit instruction that Groundwork must not silently upgrade an inference into a decision.

### D1 — Node/OpenSpec version fix
DECISION: correct the documented and enforced Node floor to ≥20.19.0 (matching OpenSpec's real, verified requirement) and add the missing check to `install.sh`.
EVIDENCE: §A.5 — primary-sourced against OpenSpec's own `package.json`/README/npm registry, fetched 2026-09-28.
WHY: the current floor is factually wrong and only half-enforced; this is a correctness fix, not a design choice.
TRADEOFFS: breaking for any Node 18/19 environment (which, per §A.5, was almost certainly already non-functional for OpenSpec use — this only surfaces the failure earlier and more clearly).
VALIDATION METHOD: `tests/test_setup.py`-style fixture with a stubbed old-Node binary on PATH, asserting `install.sh` now refuses with a clear message.
UNCERTAINTY: none material — this is the one item in this document with no live open question.
**Recommendation: approve as-is; this should ship in Phase 1 regardless of any other decision.**

### D2 — Investigation continuity for non-OpenSpec-tracked work
**Option A — Extend, don't add a file.** Teach `groundwork_session_snapshot.py` and `engineering-workflow.md` §7 to also look for and surface *whatever the current session already leaves behind* (a scratch file, a comment block, a `TODO`/`INVESTIGATING` marker convention) with no new managed state artifact. EVIDENCE: matches Decision D4 in the predecessor change (`intelligent-engineering-harness/design.md`) — "a Groundwork state file would be a second source of truth that drifts" — and FUTURE-SCOPE.md §7's explicit stance. WHY: keeps the "no state file, no database" principle intact; smallest possible change. TRADEOFFS: does not, by itself, guarantee a rejected hypothesis is captured anywhere durable if the session ends mid-investigation without the engineer writing it down — the mechanism is advisory, not structural. VALIDATION METHOD: construct a compaction/fresh-session test where the *convention* was followed and confirm recovery; document (do not hide) the case where it was not followed and recovery fails.

**Option B — One small, capped, opt-in investigation-state file.** A single append-only or overwrite file (e.g. `~/.claude/groundwork/investigation.md` or per-repo `.groundwork/investigation-state.md`), written only during TROUBLESHOOT/AUDIT-tier work, capped in size (matching the 2,500-char discipline already used by the snapshot hook), holding only: objective, established facts, rejected hypotheses with why, open hypotheses, evidence references, next action — explicitly never chain-of-thought, matching the requesting brief §8's own instruction. EVIDENCE: this is the only way to make acceptance criterion #10 (rejected hypotheses stay rejected) deterministically testable rather than convention-dependent. WHY: RCA work is usually TRIVIAL/STANDARD tier and therefore has no OpenSpec `tasks.md` to anchor to — today's continuity design structurally excludes exactly this class of work. TRADEOFFS: is a second source of truth that can drift from the repository/runtime (mitigated by the existing rule "repository/runtime always outranks saved memory," which would apply to this file too — a stale rejected-hypothesis note that current evidence contradicts must be reported and overruled, never trusted blindly); adds one more file to the installer's managed set, to `uninstall.sh`, and to the telemetry-privacy review (must never contain secrets, matching the existing snapshot-hook clipping/data-boundary pattern). VALIDATION METHOD: the compaction/fresh-session test suite required by the requesting brief §9-10, run directly against this file.

**Recommendation**: Option B is the only option that makes acceptance criterion #10 more than advisory, and the requesting brief is explicit that this criterion is non-negotiable ("A rejected hypothesis must not become an active or verified hypothesis after recovery... Test this explicitly"). Option A is closer to the existing architecture's stated philosophy and should be the fallback if the owner judges the second-source-of-truth risk to outweigh the guarantee. **This is presented as a genuine architecture fork per `engineering-workflow.md`'s own §4 criteria (multiple materially different valid approaches, no repository evidence alone picks one) — owner decision required.**

### D3 — Review evidence strengthening
DECISION (proposed, narrow): keep `require_material_review.py`'s presence-based gate exactly as-is (it is well-tested and its known limitation — "a call merely named '…review…' satisfies the gate" — is an accepted, documented tradeoff, not a defect to re-litigate); add one additional, narrowly-scoped rule-text requirement to `engineering-workflow.md` §2.6 that a MUST-FIX-bearing review must be followed by demonstrable further work (a file edit, a re-run test) before the Stop hook is satisfied a second time in the same session — this is checkable by the *existing* hook's own transcript-scanning mechanism with a small extension (has a review call happened, AND if the review's own output can be found to contain "MUST FIX", has any tool call happened after it), without building a findings-parsing/tracking system.
EVIDENCE: requesting brief §15 explicitly warns against "a workflow engine just for review tracking" and asks for "enough deterministic evidence" — not full structured findings storage.
WHY: smallest sound approach; avoids the fragility of parsing free-text review verdicts for MUST FIX counts (reviewers do not use a fixed vocabulary today, and inventing one would require every reviewer type — ECC's, a subagent's, a teammate's — to comply, which Groundwork cannot enforce upstream).
TRADEOFFS: still gameable by a reviewer call that does no real work and a session that stops without any further tool use anyway (rare but possible); does not capture *what* the review found, only that work continued after it.
VALIDATION METHOD: new `test_hooks.py` cases constructing a transcript with a MUST-FIX-bearing review followed immediately by Stop (should still block) vs. followed by an edit then Stop (should allow).
UNCERTAINTY: whether "MUST FIX" text-matching in review output is reliable enough not to false-block on a review that used different wording — needs a small sample of real ECC/subagent reviewer outputs to check vocabulary consistency before implementation (RUNTIME VALIDATION REQUIRED, Phase 3).
**Recommendation: approve the narrow version; do not build a structured findings database.**

### D4 — ECC capability policy mechanism
DECISION (two-part, proposed): (1) use ECC's own `--profile`/`--with capability:*` install-time flags in `install.sh` to select a curated default set, with `--ecc-profile full` as an explicit opt-out back to today's behavior; (2) **only if runtime validation confirms `skillOverrides` actually suppresses plugin-provided skill auto-invocation** (currently UNVERIFIED — Groundwork's own docs assert the opposite, not re-checked against the current Claude Code version in this audit), also add `skillOverrides` entries via `merge_settings.py` for finer-grained control than ECC's own install-time categories offer.
EVIDENCE: §D.1 — all mechanisms VERIFIED to exist; the specific plugin-skill-scope question is the one open runtime-validation item.
WHY: uses only native, already-existing mechanisms from ECC and Claude Code — no fork, no vendored content, matches the requesting brief §11-12 exactly ("Groundwork capability policy... ECC upstream → Groundwork capability policy → relevant capabilities exposed on demand").
TRADEOFFS: part (2) may turn out to be a no-op if the runtime validation fails — the design must not depend on it; part (1) alone (ECC's own install-time selection) is sufficient to deliver most of the context-cost win even if part (2) doesn't pan out.
VALIDATION METHOD: a live test — install ECC with a `skillOverrides` entry disabling one specific plugin skill, then confirm in a fresh session whether Claude still auto-invokes it. §D.2/D.3's category data is now VERIFIED (real names, checksummed source) and no longer blocks this decision.
UNCERTAINTY: only the `skillOverrides`-on-plugin-skills question remains (RUNTIME VALIDATION REQUIRED) — this is now the sole blocker for part (2); part (1) (ECC's own install-time `--profile`/`--with capability:*` selection) has no remaining unknowns and could proceed independently.
**Recommendation: approve the two-part approach; treat part (2) as conditional on its own validation, not a blocking dependency for part (1).**

### D5 — Deterministic safety expansion beyond Git
DECISION (proposed): **defer broad cloud/IaC/production blocking; approve only a narrow, evidence-matched candidate if the owner wants any Phase 6 work at all** — specifically, pattern-detect the smallest, clearest bypass class analogous to what `block_protected_push.py` already does for Git (e.g., a `terraform apply`/`destroy` invocation with no preceding `terraform plan`-generated plan file referenced, or a small, explicit list of unambiguously destructive cloud-CLI verb+resource-type combinations), fail-open, adversarially tested exactly like the push guard was.
EVIDENCE: `FUTURE-SCOPE.md` §10 (the repo's own prior conclusion, written under the same evidence-first discipline this audit is applying) explicitly defers this pending "a real task" showing the advisory rule insufficient — no such task has occurred yet, per the repository's own record. Counter-evidence: the requesting brief §17 explicitly asks Groundwork 2.0 to "preserve or strengthen deterministic protections" for "destructive cloud operations, production changes, IAM/security changes."
WHY: this is a genuine tension between the requesting brief's enterprise-readiness goal and the repository's own validated principle of not adding enforcement mechanisms ahead of evidence. Resolving it silently in either direction would violate the audit's own instructions (not to silently remove/keep based on assumption, and not to add mechanisms without a demonstrated gap).
TRADEOFFS: broad blocking risks false positives that make Groundwork "unusable with excessive confirmations" (requesting brief §17's own caution); no blocking at all leaves acceptance criterion #15 partially unmet indefinitely.
VALIDATION METHOD: if approved, the same adversarial-review process `block_protected_push.py` went through — a security-reviewer pass explicitly trying both bypasses and false-positive legitimate commands.
UNCERTAINTY: whether "enterprise-readiness" as stated in the request should override the repo's own wait-for-a-real-gap principle is precisely the kind of business-intent ambiguity `engineering-workflow.md` §4 itself says is a genuine owner decision, not something to infer.
**Recommendation: owner decides scope (none / narrow-IaC-only / broader); do not approve a broad "block risky cloud commands" hook without a specific, named, real incident or task to scope it against — this is the one place in this design where over-engineering risk is highest.**

---

## H. Risks and unresolved questions (material items only)

1. **`openspec/changes/intelligent-engineering-harness` is unarchived with one blocked task (6.4, `claude -p` fresh-session proof, blocked on `claude auth login`).** This change is the source of the `project-continuation`, `validation-and-review-evidence`, and `harness-installation` capabilities that this proposal modifies. Until it is archived (or task 6.4 is otherwise resolved/waived by the owner), those three capabilities exist only as delta specs inside an open change, not in `openspec/specs/`, which is a minor OpenSpec-hygiene ambiguity for tooling that expects modified capabilities to have an archived baseline. **Does not block this audit**, but should be resolved (either by running `claude login` and completing 6.4, or by an explicit owner decision to archive with the caveat documented) before or during Phase 1.
2. **Resolved during this audit**: §D.2/D.3's ECC category tables are now populated with real, checksum-verified agent/skill names (not inferred) — task 0.10 is complete. The one open item this surfaced (§D.4): ECC has no AWS/GCP/Azure/Terraform coverage at all, which Phase 4 cannot fix by curation alone — worth a note to the user about reporting it upstream to ECC, and worth factoring into whether MCP servers (cloud-provider CLIs/APIs, `FUTURE-SCOPE.md` §9) become a nearer-term priority than this document currently scopes them.
3. **The `skillOverrides`-on-plugin-skills question (D4) is unresolved** and Groundwork's own existing documentation (`docs/TROUBLESHOOTING.md`) may itself be stale on this exact point — it should be re-tested live, not assumed either way, before part (2) of D4 is built.
4. **D5 is a genuine values tension**, not a technical unknown — see D5 above. Recommend explicit owner sign-off on scope before any Phase 6 work starts.
5. **Node version fix (D1) is a breaking change for a currently-silent-failure population.** No telemetry exists to estimate how many real installs are on Node 18/19 today (Groundwork's telemetry does not and should not capture Node version — this is an acceptable gap, not a telemetry defect). Recommend the CHANGELOG entry be explicit that this corrects a pre-existing bug, not a new requirement, to set expectations correctly.
6. **This document itself should go through the same independent-review gate it describes** (requesting brief §15/§26's own spirit) before any phase begins implementation — once a phase is approved, `/opsx:apply` should route it through the existing MATERIAL-tier review gate like any other Groundwork change.

---

## Next step

Per the requesting brief's explicit instruction (§27, STOP POINT): **implementation does not begin from this document.** The owner reviews `proposal.md`, this file, and `tasks.md`, approves or amends each Decision (D1-D5) and each Phase (1-6) independently, and only then does a phase get its own `/opsx:apply` pass with its own tests, its own independent review, and its own entry in `docs/VALIDATION.md` — matching exactly how every prior Groundwork capability has shipped.
