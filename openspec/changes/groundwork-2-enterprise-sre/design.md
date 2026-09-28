# Groundwork 2.0 — Enterprise SRE Upgrade: Audit and Design

**Status: AUDIT / DESIGN phase. Nothing in this document is implemented.** All findings below are labelled VERIFIED (with source and date), INFERENCE, ASSUMPTION, UNVERIFIED, CONFLICTING EVIDENCE, UNKNOWN, or RUNTIME VALIDATION REQUIRED per the evidence taxonomy this document itself proposes extending. Repository inspection was performed directly against this checkout (`/home/user/groundwork`) on 2026-09-28. Upstream facts were verified live against OpenSpec, ECC, and Claude Code's own sources on 2026-09-28 (raw GitHub content, the npm registry, and code.claude.com docs).

**Revision note (this pass, 2026-09-28, later same day)**: this document is extended, not replaced, per an explicit instruction not to open a second OpenSpec change. §§A-D and the original migration/acceptance/decisions/risks sections (now K-N) are the first pass's audit, preserved. §§E-J are new: repository-aware builder roles, SRE capability consolidation, presentation/output-style architecture, teach/learn, and a comprehensive capability-ownership matrix. D3 (review evidence) and D5 (deterministic safety) are substantively redesigned in §M per specific critique that the first pass's proposals were too weak (D3) or needed builder-awareness (D5). Section letters after D have shifted; every cross-reference in this file, `proposal.md`, `tasks.md`, and the `specs/` deltas has been updated to match — see the end-of-document changelog for the exact letter mapping.

---

## A. Current-state audit

### A.1 Method

Every rule file, playbook, hook, script, installer file, test file, and doc was read in full (not summarized from README claims). Hook and script behavior was independently verified by reading the actual Python/shell source, not inferred from `docs/ARCHITECTURE.md`'s own description of itself — in every case checked, the code matched the docs' claims. Upstream claims (Node version, ECC counts, Claude Code mechanisms) were independently re-verified against live sources rather than trusted from Groundwork's own (dated) VALIDATION.md entries — this caught one real, previously-undetected bug (§A.5). This pass additionally verified Claude Code's native output-styles mechanism and presentation/document capability against current official docs (§H), since designing new capabilities without checking what the platform already provides would repeat the exact mistake this audit exists to catch.

### A.2 Component matrix — rules

| Component | Responsibility | Evidence | Decision |
|---|---|---|---|
| `rules/engineering-workflow.md` | Tier classification, execution order, completion facts, autonomy, execution-model selection, continuation procedure | Read in full; cross-checked against `docs/VALIDATION.md` 1.0.0–1.5.1 live evidence | **KEEP + STRENGTHEN** — §7 continuation procedure is strong for OpenSpec-tracked MATERIAL work; gains the continuity decision outcome (D2) and a reference to the extended evidence labels (D1/evidence-taxonomy); §6 gains the four builder-role personas (§F) |
| `rules/architecture-quality.md` | Governing design principle, quality dimensions, pre-MATERIAL questions, variation-point rule | Read in full | **KEEP** — no material gap found; §5 ("follow the project's established conventions first, then vendor guidance") already states the exact "repository pattern wins over generic knowledge" principle this pass's builder roles need — confirmed by re-reading, not assumed |
| `rules/evidence-policy.md` | Evidence priority, labels, DECISION record, validation ladder, completion-evidence table, RCA rule | Read in full; repo-wide grep confirmed `CONFLICTING EVIDENCE` and bare `UNKNOWN` do not appear anywhere in the repo | **KEEP + STRENGTHEN** — add the two missing labels (evidence-taxonomy); tighten §7 RCA rule to require one of them when applicable |
| `rules/task-routing.md` | One category per task, material-ambiguity clarification rule | Read in full; validated live in `docs/VALIDATION.md` 1.2.0 (12/12 correct categorization) | **KEEP** — confirmed in this pass that no new task-routing category is needed for builder work (routes to existing IMPLEMENT/DEPLOY/DESIGN/PLAN) or presentation (routes to existing DOCUMENT); see §F.1 and §H.1 |
| `rules/output-contract.md` | Three-layer progressive-disclosure answer shape (the **truth** layer) | Read in full; validated live across six categories in `docs/VALIDATION.md` 1.2.1–1.2.4 | **KEEP + STRENGTHEN** — gains one new explicit invariant: native output styles (§H) may change tone/format but never override this file's evidence/validation/completion rules |

### A.3 Component matrix — hooks

| Component | Trigger | Enforces or reports | Decision |
|---|---|---|---|
| `hooks/block_protected_push.py` | PreToolUse (Bash) | **Enforces** (`permissionDecision: deny`) | **KEEP** — fail-open, no hardcoded machine-specific values, adversarially tested (VALIDATION.md 1.1.0) |
| `hooks/require_material_review.py` | Stop | **Enforces** presence of a reviewer-shaped call; did **not** enforce MUST FIX resolution | **KEEP + REDESIGNED STRENGTHEN** — see Decision D3 (§M), substantively redesigned this pass |
| `hooks/groundwork_session_snapshot.py` | SessionStart | Reports only | **KEEP + STRENGTHEN** — gains the continuity decision outcome (D2); shares a duplicated `dirty_change_names()` helper with `require_material_review.py` — **CONSOLIDATE** |
| `hooks/groundwork_telemetry.py` | Stop | Reports only, never blocks | **KEEP** — its existing `TEST_CMD`/`DEPLOY_CMD` regex-based command classification and its transcript tail-reading mechanism are **reused, not duplicated**, by the redesigned D3 review-evidence check (§M) — this is a direct instance of "compose an existing primitive instead of building a new one" |

No hardcoded personal usernames, credentials, account IDs, or non-portable machine identity were found in any hook (confirmed by a repo-wide search; every path reference resolves through `$HOME`/`os.path.expanduser`/`$CLAUDE_CONFIG_DIR`).

### A.4 Component matrix — scripts and installer

| Component | Decision | Evidence |
|---|---|---|
| `scripts/merge_settings.py` / `scripts/unmerge_settings.py` | **KEEP** | Atomic writes, idempotent, one documented and tested known limitation |
| `scripts/migrate_legacy_rules.py` | **KEEP** | One-time, symlink-safe, silent no-op when nothing to migrate |
| `scripts/groundwork_report.py` | **KEEP** | Python↔JS metric parity directly tested; atomic writes; privacy-safe |
| `scripts/check_routing.py` | **KEEP** | Correctly self-labelled as non-deterministic, live evidence |
| `install.sh` | **STRENGTHEN** | VERIFIED: checks only that `node` exists on `PATH`, no version-number comparison at all |
| `setup.sh` | **STRENGTHEN** | VERIFIED: `NODE_MIN=18`, hardcoded and wrong (§A.5) |
| `uninstall.sh` | **KEEP** | Symmetric with install.sh |

### A.5 The Node/OpenSpec version bug — VERIFIED with primary sources (2026-09-28)

- `raw.githubusercontent.com/Fission-AI/OpenSpec/main/package.json` (fetched 2026-09-28): `"engines": {"node": ">=20.19.0"}`.
- `registry.npmjs.org/@fission-ai/openspec` version metadata — `engines.node` is `>=20.19.0` for every version back to and including **1.12.0** (published 2026-09-03), the exact version `CHANGELOG.md` recorded as "unchanged" at Groundwork's 2026-09-20 audit. The Node ≥18 claim has been wrong since before Groundwork 1.1.0 shipped.
- ECC's own floor is genuinely 18 (VERIFIED by tarball inspection of `ecc-universal@2.2.1`). **The mismatch is asymmetric**: ECC is fine at Node 18; OpenSpec is not.
- `install.sh` never checks the Node version number at all; only `setup.sh` does, with the wrong number.

### A.6 ECC and OpenSpec version drift — VERIFIED (2026-09-28), CORRECTED (2026-09-28, Phase 1 implementation, independent-review finding "M4")

**Correction notice**: the paragraph originally here asserted that `install.sh` installs ECC from `registry.npmjs.org/ecc-universal` (checksum-confirmed against a tarball) and that this is "what installs." **That premise is false.** It was caught during Phase 1 implementation by independent review and re-investigated directly, evidence below. The audit's error was conflating "a real, published `ecc-universal@2.2.1` npm package exists" (true, and the original checksum work was accurate) with "that package is what Groundwork installs" (false — npm plays no part in installing ECC at all).

- **VERIFIED (direct reproduction against a live, isolated `CLAUDE_CONFIG_DIR`, 2026-09-28)**: `install.sh:65-66` installs ECC with `claude plugin marketplace add affaan-m/ECC` then `claude plugin install ecc@ecc --scope user --config hook_profile=standard`. `claude plugin marketplace add` runs a plain `git clone https://github.com/affaan-m/ECC.git`, checked out on branch `main`. There is **no version pin**: a fresh install, or `claude plugin marketplace update` + `claude plugin update ecc@ecc`, always resolves to whatever commit is HEAD on GitHub `main` at that moment.
- **VERIFIED**: at the moment of this re-investigation, that resolved to plugin version **2.2.2** (HEAD commit `d3b8a3e9`, "chore(deps): bump actions/stale…", 2026-09-27). `claude plugin list`/`claude plugin details ecc@ecc` report the actually-resolved installed inventory: **Skills (386), Agents (68), Hooks (7), MCP servers (1)** — not the npm `ecc-universal@2.2.1` / 286-skill figures §D.2/D.3 were built from.
- **Impact on §D.2/D.3**: that catalog was verified against the wrong artifact and is now a stale, point-in-time snapshot with **no implementation authority**. Its central finding was independently re-checked against the real installed content and **still holds** (§D.4). Any Phase 7 mechanism must enumerate the real roster at build/verify time from the actual install (`claude plugin list` / `claude plugin details ecc@ecc`), never from a hard-coded list taken from this audit.

OpenSpec's own facts are unaffected — OpenSpec genuinely installs from npm (`npm install -g @fission-ai/openspec@latest`, `install.sh:75`), version-pinned only by `@latest` at install time, correctly verified in §A.5. OpenSpec is at `1.13.2` upstream as of 2026-09-28, three releases ahead of Groundwork's last-recorded `1.12.0`.

### A.7 Component matrix — docs, tests, OpenSpec state

| Component | Decision | Notes |
|---|---|---|
| `README.md`, `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`, `docs/TROUBLESHOOTING.md`, `docs/UPGRADE-ROLLBACK.md`, `docs/FUTURE-SCOPE.md`, `CHANGELOG.md`, `CREDITS.md` | **KEEP + STRENGTHEN** | Needs the version refresh (§A.6), corrected Node floor (§A.5), and the new capability-ownership matrix (§J) folded into `ARCHITECTURE.md` |
| `tests/test_hooks.py`, `test_playbooks.py`, `test_report.py`, `test_setup.py`, `test_telemetry.py` | **KEEP + STRENGTHEN** | Zero compaction/fresh-session-recovery tests; zero conflicting-evidence tests; zero Node-version-check tests in `install.sh` |
| `openspec/specs/{task-routing,onboarding,usage-telemetry,health-dashboard}/spec.md` | **KEEP** | Accurate, archived, current baseline |
| `openspec/changes/intelligent-engineering-harness/` | **See Open Question 1, §N** | Substantially shipped; deliberately unarchived pending one blocked task |

### A.8 ECC integration posture — CORRECTED (2026-09-28, Phase 1 implementation, finding "M4")

**Correction notice**: the paragraph originally here claimed ECC's own installer flags (`--profile`, `--skills`, `--with capability:*`) are usable to curate Groundwork's install. **False for the path Groundwork actually uses.** Those flags exist only on ECC's separate, standalone installer (`./install.sh` / `npx ecc-universal install`, confirmed present in the cloned `main` checkout) — which ECC's own README and Groundwork's `install.sh` comment both say must never be combined with the plugin-marketplace path ("pick one path only"). `claude plugin install --help` (Claude Code 2.1.283, the version in this environment) confirms the command Groundwork actually runs supports only `--config <key>=<value>` against the plugin manifest's declared `userConfig` schema — for ECC exactly two keys, `hooks_enabled` (bool) and `hook_profile` (`minimal`/`standard`/`strict`). No skill- or agent-subset selection flag exists on this path.

Separately, **VERIFIED by direct inspection of the installed Claude Code CLI's own source** (`/opt/claude-code/bin/claude`, v2.1.283): the function resolving a `skillOverrides` entry short-circuits with `if (e.source === "plugin") return` before consulting the override table — `skillOverrides` is, by design, never consulted for plugin-sourced skills. This confirms, at the source level rather than by assertion, Groundwork's own pre-existing `docs/TROUBLESHOOTING.md`/`docs/VALIDATION.md` claim ("`skillOverrides` does not affect plugin skills").

**Conclusion**: on Groundwork's actual install path there is currently no upstream-supported mechanism to install or restrict ECC to a skill/agent subset. The only real levers are the plugin's own `hook_profile`/`hooks_enabled` config (hook behavior only, already used by `install.sh`) and whole-plugin enable/disable (`claude plugin disable ecc@ecc`, already documented as the full opt-out). This does not violate Decision D4 ("use upstream-supported selection/scoping mechanisms only after validating them against the actually installed version; retain an explicit full-ECC opt-out/override") — it satisfies it: validation now conclusively shows no curation mechanism exists, so Groundwork 2.0 ships ECC's full install (matching 1.5.1's actual behavior), with the limitation documented rather than worked around by forking or vendoring ECC (explicitly forbidden by D4). The corrected `ecc-capability-policy` spec reflects this.

---

## B. Gap analysis against the 22 non-negotiable acceptance criteria (unchanged from the first pass)

| # | Criterion | State | Evidence |
|---|---|---|---|
| 1 | Evidence-backed factual claims | **MET** | `evidence-policy.md` §1-2, 4 |
| 2 | Unsupported RCA conclusions prevented | **MOSTLY MET** | §7 RCA rule; strengthened by evidence-taxonomy |
| 3 | UNKNOWN is a valid outcome | **PARTIAL** | No bare `UNKNOWN` evidence label today |
| 4 | Conflicting evidence surfaced | **NOT MET** | No label, no rule text, no test |
| 5 | Repository/runtime outranks saved memory | **MET** | `evidence-policy.md` §8 |
| 6 | False completion claims prevented | **MET, strong** | §3 hard rules, §6 evidence table |
| 7 | MATERIAL work receives meaningful independent review | **PARTIAL → addressed by redesigned D3** | Presence enforced; outcome/resolution was not — see §M |
| 8 | Critical state survives context compaction | **PARTIAL, untested** | Strong for OpenSpec-tracked work only |
| 9 | Fresh sessions accurately recover unfinished work | **MOSTLY MET for MATERIAL work** | Weaker for non-OpenSpec-tracked work |
| 10 | Rejected hypotheses remain rejected after recovery | **NOT MET, NOT TESTED** | No mechanism |
| 11 | Main/subagent/team execution selected automatically | **MET** | §6, live-validated; extended this pass to include builder-role selection (§F) |
| 12 | Unnecessary context minimized | **PARTIAL** | ECC's ~20K-token cost has no curation |
| 13 | ECC exposure curated for SRE/CloudOps | **NOT MET** | See §D |
| 14 | OpenSpec used only when justified by materiality | **MET** | §1 tier table |
| 15 | Safety-critical controls deterministic where practical | **PARTIAL → sharpened by redesigned D5** | See §M |
| 16 | Install/update/rollback/uninstall are safe | **MET, exceptionally well validated** | Minor strengthen: Node check |
| 17 | No personal credentials/hardcoded identity | **MET** | Confirmed by repo-wide search |
| 18 | External work updates based on evidence | **OUT OF SCOPE for this phase** | Automation is explicitly deferred |
| 19 | Telemetry useful without leaking sensitive content | **MET, thoroughly tested** | |
| 20 | Existing intended behavior has not regressed | **Process requirement** | Migration plan's non-regression gate |
| 21 | System remains understandable and maintainable | **MET**, one small wart | Duplicated helper function |
| 22 | Usable without understanding internals | **MET** | "Continue this project." live-validated |

This pass's new capabilities (§E-J) are evaluated against the requesting brief's own non-negotiable design principles restated for this pass (evidence-first, repository-aware, runtime-aware, safe, small, composable, maintainable, shareable, enterprise-ready, SRE/CloudOps-focused) rather than against the original 22-item list, since builders/SRE-consolidation/presentation/teach-learn are new scope, not gaps in the original 22. §L's acceptance matrix now covers both.

---

## C. Target architecture and ownership boundaries (updated)

```
OpenSpec    → WHAT / WHY / acceptance criteria (unchanged)
ECC         → HOW: curated specialist agents/skills (unchanged in kind; curated selection — §D)
Claude Code → runtime primitives: subagents, Agent Teams, hooks, permissions,
              skillOverrides/Skill() rules, memory, native output styles,
              native document-generation plugin marketplace (§H)
MCP/CLI     → external-system access: cloud provider CLIs/APIs, kubectl, Terraform,
              GitHub, Jira, etc. — access only, never workflow or policy (§I)
Groundwork  → governance: policy, routing, safety, evidence integrity, validation,
              continuity, completion truth (unchanged role) — PLUS, this pass:
              repository-understanding policy (§E), builder-role selection
              policy (§F), SRE-capability composition policy (§G),
              output-truth/style separation policy (§H)
```

Groundwork's role does not change in kind anywhere in this pass: it still owns *policy*, never *execution capability*. Every new thing in §E-J is either rule text (a policy surface) or, where a genuinely new behavioral contract exists, a small OpenSpec capability spec — never a new permanent agent, never a new always-on daemon, never a duplicate of something Claude Code, ECC, or OpenSpec already does.

Updated capability-attachment table (full ownership matrix is §J; this is the architectural summary):

| Capability | Owner file(s) | New surface? |
|---|---|---|
| `evidence-taxonomy` | `rules/evidence-policy.md` §2, §7 | Rule text only |
| `installer-upstream-compatibility` | `install.sh`, `setup.sh`, `README.md` | Corrects existing checks |
| `review-evidence-strengthening` (redesigned, §M/D3) | `rules/output-contract.md` (new structured block), `hooks/require_material_review.py` (extended parser reusing telemetry's command-classification regex) | Extends two existing files; no new hook |
| `ecc-capability-policy` | `install.sh`, `scripts/merge_settings.py` (conditional) | One new small rule surface |
| `investigation-continuity` (D2, decision-pending) | `engineering-workflow.md` §7 + `groundwork_session_snapshot.py`, ± one new small state file | Zero or one new file |
| `deterministic-safety-expansion` (redesigned, §M/D5) | Up to three narrow, independently-approvable new hooks | Zero to three new hooks, all decision-pending |
| `repository-understanding` (§E) | `playbooks/implement.md`, `playbooks/deploy.md`, `playbooks/design.md` (extended), `architecture-quality.md` §5 (cross-referenced, unchanged) | Extends three existing playbooks; no new file |
| `builder-execution-roles` (§F) | `rules/engineering-workflow.md` §6 (extended with 4 role personas), `playbooks/deploy.md` (closed-loop cross-reference) | Extends one rule file and one playbook; no new agent files |
| SRE capability consolidation (§G) | No new owner — explicitly composes `TROUBLESHOOT`/`VALIDATE`/`AUDIT`/`DEPLOY`/`RESEARCH`/`DOCUMENT` playbooks + `ecc-capability-policy` + `repository-understanding` + MCP tool access | **No new surface at all** — this is the point |
| `presentation-and-output-style` (§H) | `rules/output-contract.md` (truth/style invariant), `playbooks/document.md` (presentation branch) | Extends two existing files; the design-system template artifact is OPTIONAL/LATER (§O) |
| `teach-learn-capability` (§I) | `playbooks/explain.md` (extended) | Extends one existing file |
| MCP/tool-access policy (§I of the brief, folded into §F.5) | `rules/engineering-workflow.md` §6 (one short subsection) | Rule text only |

---

## D. ECC capability matrix

**Verification basis (ORIGINAL, first-pass audit)**: counts, install-time selection mechanisms, and the full real name-level listing were VERIFIED against the published `ecc-universal@2.2.1` npm tarball, checksum-confirmed against the registry's published SHA1. Fetched/verified 2026-09-28.

**CORRECTED (2026-09-28, Phase 1 implementation, finding "M4" — see §A.6/A.8 for full evidence)**: that npm tarball is not what Groundwork's `install.sh` installs. The real install is ECC's GitHub `main` via `claude plugin marketplace add`/`claude plugin install` — currently version 2.2.2, Skills (386)/Agents (68)/Hooks (7)/MCP servers (1) per `claude plugin details ecc@ecc`, with no version pin. §D.2/D.3 below are therefore a **stale snapshot of the wrong artifact** — kept for institutional record, not implementation authority. §D.1's "selection mechanisms" list is corrected below to match what is actually usable on Groundwork's install path; §D.4's central finding was independently re-checked against the real installed content and still holds.

### D.1 Selection mechanisms available today — CORRECTED

- ~~ECC's own install-time filters (`--profile`, `--skills`, `--with capability:*`)~~ — **VERIFIED NOT APPLICABLE**: those flags belong to ECC's separate standalone installer, not the `claude plugin install` command Groundwork actually runs (which ECC's own README says must never be combined with the plugin path). `claude plugin install --help` confirms only `--config <key>=<value>` is available, against the plugin's own `userConfig` schema (`hooks_enabled`, `hook_profile` — hook behavior only).
- ~~Claude Code's `skillOverrides` for plugin-skill curation~~ — **VERIFIED INEFFECTIVE**: direct inspection of the installed Claude Code CLI's own source shows the `skillOverrides` resolution path explicitly skips any entry whose skill `source === "plugin"`. Not usable for ECC.
- **Whole-plugin disable** (`claude plugin disable ecc@ecc` / `enable`) — VERIFIED present and working (already documented in `docs/TROUBLESHOOTING.md`); coarse, but it is the genuine, working full opt-out D4 requires.
- **The plugin's own `hook_profile`/`hooks_enabled` config** (VERIFIED, already used by `install.sh`) — the only real install-time customization on this path; governs ECC's *hook* automation only, not its skill/agent catalog.

### D.2 Skill matrix (286 total, real names — sums verified to equal 286)

| Category | Count | SRE/CloudOps relevance | Recommended default |
|---|---|---|---|
| `infra_sre` — deployment, containers, CI/git ops, network diagnostics | 26 | **CORE SRE**, but no `aws-*`/`gcp-*`/`azure-*`/`terraform-*` skill exists at all; several skills are home-lab/on-prem-hardware scoped | Enabled by default, minus the home-lab subset |
| `database` | 7 | **CORE SRE** | Enabled by default |
| `testing_qa` | 25 | **OPTIONAL SRE** | Enabled by default, narrow |
| `security` | 13 | **OPTIONAL SRE, mixed** — no IAM/secrets/cloud-security-posture skill found | General items by default; vertical-compliance items on demand |
| `agent_meta` (Claude Code/ECC harness operations) | 69 | **NOT RELEVANT TO GROUNDWORK DEFAULT** — largest category (24%) | Disabled by default |
| `business_ops` | 41 | **NOT RELEVANT** — second-largest (14%) | Disabled by default |
| `lang_framework` | 40 | **LANGUAGE/PROJECT-SPECIFIC** | On demand, matched to project stack |
| `architecture_quality` | 18 | **OPTIONAL SRE**, mostly redundant with `architecture-quality.md` | On demand |
| `datasci_ml`, `design_ux`, `media_creative`, `docs`, `crypto` | 22+14+8+3 | **NOT RELEVANT** | Disabled by default |

### D.3 Agent matrix (68 total, real filenames — sums verified to equal 68)

| Category | Count | SRE/CloudOps relevance | Recommended default |
|---|---|---|---|
| `infra_network` | 3 | **CORE SRE**, small, home-lab-scale naming | Enabled by default |
| `engineering_meta` | 22 | **CORE for the subset already used by name in `engineering-workflow.md`** (`code-explorer`, `planner`, `code-reviewer`, `security-reviewer`), plus `performance-optimizer`/`silent-failure-hunter` | That subset by default; rest on demand |
| `code_reviewers` | 23 | **CORE for 3** (`security-reviewer`, `database-reviewer`, `network-config-reviewer`); **LANGUAGE-SPECIFIC for 20** | The 3 by default; rest on demand |
| `build_resolvers` | 12 | **LANGUAGE-SPECIFIC** | On demand |
| `gan_ml`, `opensource_pipeline`, `business_marketing` | 8 | **NOT RELEVANT** | Disabled by default |

### D.4 The single most important finding in this matrix

**VERIFIED (original, against the npm tarball)**: there is no AWS, GCP, Azure, or Terraform skill or agent anywhere in ECC. Roughly a third of the entire 286-skill catalog (`agent_meta` + `business_ops`) is not a software-engineering capability at all.

**RE-VERIFIED (2026-09-28, Phase 1 implementation, against the real installed content)**: searched the actual installed plugin's full component inventory (`claude plugin details ecc@ecc` — 386 skills, 68 agents) for `aws`/`gcp`/`azure`/`terraform`/`cloud` — **still zero matches**. The central finding holds against the real artifact, not only the stale one: ECC provides no cloud-provider or IaC-tool capability, on either catalog. §D.5's builder-capability-sourcing conclusion (Groundwork's builder roles, not ECC, must supply this) is unaffected by the M4 correction. The exact "roughly a third… agent_meta + business_ops" proportion is unverified against the real 386-skill catalog and should not be quoted as current without re-measuring it in Phase 7.

### D.5 Builder capability sourcing — where does each new builder role's actual capability come from? (new this pass)

The requesting brief is explicit: "Do not assume ECC provides Terraform/AWS/GCP capability — your audit already found it does not." This table answers, for each builder role (§F), what actually provides the capability:

| Builder role's needed capability | Source | Verification |
|---|---|---|
| Terraform/Ansible authoring, HCL syntax, module structure | **Native Claude reasoning + code generation** (Claude's own training, no tool needed to *write* HCL/YAML) | No ECC skill exists for this (§D.4); this is plain code generation, same category as writing Python or Go |
| Terraform plan/apply/validate execution | **MCP/CLI** — the `terraform` binary via Bash, or a Terraform MCP server if the project has one configured | Groundwork requires no specific MCP; it uses whatever the repository/environment already provides (§I) |
| Cloud resource state (GCP/AWS/Azure) | **MCP/CLI** — `gcloud`/`aws`/`az` CLI via Bash, or a cloud-provider MCP server | Same — task-driven, not installed by Groundwork |
| Kubernetes manifest/Helm/Flux authoring | **Native Claude reasoning** for authoring; `kubernetes-patterns`/`docker-patterns`/`deployment-patterns` (VERIFIED ECC skills, `infra_sre` category) for patterns/conventions | Composes curated ECC (§D.2) |
| Kubernetes cluster interaction (`kubectl`, `helm`, `flux`) | **MCP/CLI** | Task-driven |
| CI/CD pipeline authoring (GitHub Actions, Spacelift config) | **Native Claude reasoning**; `github-ops`/`git-workflow`/`delivery-gate` (VERIFIED ECC skills) for conventions | Composes curated ECC |
| Repository pattern discovery (existing modules, naming, conventions) | **`repository-understanding`** (§E, new Groundwork policy) | New this pass |
| Independent review of generated infra/platform/delivery code | **Curated ECC reviewers** (`security-reviewer`, `database-reviewer`, `network-config-reviewer`, language reviewers) + `require_material_review.py` (existing, redesigned §M) | Composes existing + curated ECC |
| Application/service code (Python, Go, APIs) | **Native Claude reasoning** + curated `lang_framework`/`testing_qa` ECC skills on demand | Composes curated ECC, matched to the project's actual stack |
| Production-safety judgment (is this destructive, is this prod) | **Groundwork policy** — `engineering-workflow.md` §4 autonomy rule (existing) + redesigned D5 (§M) | Existing + this pass |

**Conclusion**: no builder role requires a new agent, skill, or MCP server that Groundwork itself installs or maintains. Every role is a composition of (native Claude reasoning) + (curated existing ECC agents/skills) + (whatever MCP/CLI the task's own repository/environment already provides) + (Groundwork's own policy for discovery and safety). This is the direct evidence answer to the brief's own required question for every new component: "what exact capability is missing, what's closest, why can't it be reused" — for builder roles specifically, nothing is missing except the *policy* of when/how to compose these, which is what §F actually adds.

---

## E. Repository-understanding design (shared capability)

### E.1 What already exists (do not duplicate this)

`engineering-workflow.md` §2 step 1 (UNDERSTAND) **already** requires reading "the actual code, config, tests, git log... repository structure, README, CLAUDE.md, project rules/config, architecture docs, OpenSpec artifacts, tests, CI/CD, deployment/IaC, configuration, runtime/tooling/MCP setup" and building a DONE/PARTIAL/MISSING/BLOCKED/UNVERIFIED table before touching anything. `architecture-quality.md` §5 **already** states "follow the project's established conventions first, then the vendor's current official guidance... where they conflict, say which you followed and why." `evidence-policy.md` §5 **already** states "derive verification commands from the project's own evidence... never invent them," and its speed rule (§5 of engineering-workflow.md) already makes research depth proportional to risk. `groundwork_session_snapshot.py` **already** discovers verification commands (Makefile/package.json/pyproject/CI) at session start.

**This means "repository-aware building" is not a new principle for Groundwork — it is the existing UNDERSTAND step and the existing conventions-win rule, applied to infrastructure/platform/delivery domains specifically, where they were not previously spelled out in enough domain-specific detail for an engineer to know exactly what to look for.** The gap is narrow: the existing playbooks (`implement.md`, `deploy.md`, `design.md`) say "inspect the existing implementation... before writing anything" in one line, with no domain-specific checklist for IaC/platform/delivery work.

### E.2 What's added (small, on-demand, no new always-loaded content)

Each of `playbooks/implement.md`, `playbooks/deploy.md`, `playbooks/design.md` gains a short, explicitly domain-scoped bullet list under their existing "inspect before writing" step, read only when a task is infrastructure/platform/delivery-shaped (these playbooks are already read on demand per `task-routing.md`, so this costs nothing for a pure application-code task):

- Existing Terraform/Ansible/Helm/Flux structure and module organization
- Naming, variable, label/tag conventions
- Environment/workspace organization (how nonprod vs. prod is distinguished — this is also load-bearing for §M/D5's production-detection problem)
- IAM and networking patterns already in use
- State/backend patterns (Terraform backend config, Spacelift stack layout)
- CI/CD and delivery patterns already in use
- Testing and validation conventions already in use (what `terraform validate`/`helm lint`/CI already runs)
- **The closest analogous existing implementation** — the single highest-value discovery, since "create another nonprod GKE cluster like our existing cluster" is only answerable by finding that existing cluster's definition first

### E.3 The core behavioral contract (this is what needs a spec)

1. **Proportional, not exhaustive**: matching the existing speed rule, discovery scope is proportional to the task — "add a variable to this module" does not need a whole-repository scan; "create a new environment" does.
2. **Repository pattern wins over generic knowledge**, unless the repository pattern is unsafe, broken, deprecated, or incompatible with the requirement — and when deviating, Claude states why. This is `architecture-quality.md` §5's existing rule, made explicit and testable for builder work specifically (see the acceptance scenario in §L).
3. **One shared capability, not four separate implementations.** All four builder roles (§F) and the existing DESIGN/IMPLEMENT/DEPLOY/AUDIT playbooks use the same discovery procedure and the same "pattern wins, justify deviation" rule — there is exactly one place this contract is defined (this section + the playbook extensions), referenced everywhere it's used, never restated.

New spec: `specs/repository-understanding/spec.md`.

---

## F. Builder execution roles

### F.1 Why these are not new task-routing categories

"Build the Terraform for this service" routes to **IMPLEMENT** today (writing code/config) and then **DEPLOY** (applying it) — both existing categories, unchanged. "Onboard this application to our GKE platform" is also IMPLEMENT+DEPLOY. Builder roles are not a new axis on *what kind of task this is* — they are a new axis on *who executes it*, sitting inside the **existing** `engineering-workflow.md` §6 execution-model decision (main session / subagent / Agent Team), exactly where "reuse subagent definitions where they fit" already lives.

### F.2 Why these are not permanent agent files

Per the brief's own instruction ("prefer native/dynamic execution over maintaining permanent custom agent files") and per what's already decided in Groundwork's execution model: Claude Code's `Agent` tool spawns a subagent or Agent Team teammate dynamically via a `name` + prompt at call time — no persisted `.claude/agents/*.md` file is required for this to work, and `engineering-workflow.md` §6 already says specialists are "derived from the actual project and task, reusing subagent definitions where they fit — never a fixed technology-specific roster." **The four builder roles are role *personas* — short, rule-text-defined descriptions of scope and evidence sources — instantiated as the `name`/prompt of a dynamically-spawned subagent or teammate, not as four new permanent agent definition files.** This is the direct application of "native dynamic subagent role" from the brief's own menu of options, and it is the option that adds the least permanent surface area.

### F.3 The four role personas (added to `engineering-workflow.md` §6, ~4 lines each)

| Role | Scope | Primary evidence sources (via `repository-understanding`, §E) | Primary composed capability |
|---|---|---|---|
| **Infrastructure Engineer** | Terraform, Ansible, cloud infra (GCP/AWS/networking/IAM/DNS/LB/storage/VMs), IaC validation | Terraform/Ansible structure, modules, environment org, state/backend, IAM/networking patterns, CI/Spacelift patterns | Native reasoning for HCL/YAML authoring; `terraform`/cloud CLIs via MCP/Bash for execution (§D.5); curated ECC reviewers for review |
| **Platform Engineer** | Kubernetes/GKE/EKS runtime config, Helm, Flux/GitOps, namespaces, RBAC, workload identity, ingress, autoscaling, observability integration, app onboarding | Existing application/platform patterns, chart structure, namespace/RBAC conventions | Native reasoning + `kubernetes-patterns`/`docker-patterns`/`deployment-patterns` (curated ECC); `kubectl`/`helm`/`flux` via MCP/Bash |
| **Delivery Engineer** | CI/CD, GitHub Actions, Spacelift, build pipelines, Docker/image builds, release/promotion workflows, rollback, post-deploy verification | Existing delivery architecture, pipeline conventions | `github-ops`/`git-workflow`/`delivery-gate` (curated ECC); native reasoning for pipeline authoring |
| **Application Engineer** | Application/service code supporting an infra/platform/delivery outcome — APIs, workers, cloud integrations, health/readiness checks, telemetry, Docker/Kubernetes-aware app changes | Existing app conventions, language/framework in use | Native reasoning + curated `lang_framework`/`testing_qa` ECC skills matched to the project's actual stack — **explicitly not a general-purpose software-development framework**; scoped to supporting infra/platform/delivery outcomes, per the brief's own instruction |

Each persona description in the rule text is a *scope and evidence-source* statement, not a system prompt to memorize — the actual instantiation still goes through the full existing `engineering-workflow.md` §2 execution order (UNDERSTAND→DESIGN→IMPLEMENT→TEST→INDEPENDENT REVIEW→FIX MUST FIX→VERIFY→RUNTIME VALIDATE→REPORT), unchanged.

### F.4 Automatic orchestration (extends the existing §6 decision, no new mechanism)

The existing main-session/subagent/Agent-Team decision in `engineering-workflow.md` §6 gains one more input: *if the task is infrastructure/platform/delivery/application-domain-shaped, the persona used for a subagent or teammate call is drawn from §F.3; otherwise unchanged from today.* Examples, matching the brief's own:

- "Add another variable to this Terraform module" → main session (simple, sequential) — **no role needed**, matching today's behavior for small changes.
- "Build the Terraform for this infrastructure" → **Infrastructure Engineer** subagent (focused, isolated) → independent review (curated ECC reviewer).
- "Build and deploy a new service to nonprod GKE" → potentially genuinely independent workstreams (Application + Infrastructure + Platform + Delivery) → **Agent Team only if the existing §6 team-justification criteria are met** (2+ genuinely independent workstreams, separate file ownership, one-line justification) — never automatically just because four roles exist, matching the brief's explicit caution. If teams are disabled or the session is non-interactive, the same decomposition runs on subagents, exactly as §6 already specifies for every other case.

**No new orchestration code.** This is a rule-text extension of a decision procedure Claude Code's own platform already executes (Agent tool, `name`-based team formation) — Groundwork adds no scheduler, no team manager, no state machine, matching the existing "Groundwork adds no orchestration code of its own" principle, now explicitly extended to cover builder-role selection.

### F.5 MCP/tool-access policy for builders (small, folded into §6, not a separate phase)

- Groundwork does not install or configure cloud/Kubernetes/CI MCP servers itself — it uses whatever the task's environment already provides, matching the brief's explicit instruction and `FUTURE-SCOPE.md` §9's existing "MCP servers are optional capabilities, never mandatory Groundwork dependencies" principle (unchanged, just now explicitly extended to builder work).
- Read-only discovery (`terraform plan`, `kubectl get/describe`, `gcloud/aws/az ... list/describe`) is safe by default, matching the brief's own instruction and the existing autonomy rule's silence on read-only operations (nothing in §4 requires asking before a read).
- Mutating operations follow the existing `engineering-workflow.md` §4 autonomy rule (already requires authorization for "an irreversible or destructive operation... production apply/deploy, IAM changes, paid resources") **plus** the redesigned D5 tiers (§M) for the narrow set where deterministic enforcement is warranted.
- Groundwork never requires or stores static cloud credentials — credential handling is entirely the user's/environment's MCP or CLI configuration, outside Groundwork's scope, matching its existing zero-credential design (confirmed in the first-pass portability audit, §A.3).

### F.6 The closed-loop build→deploy→validate path (mostly already exists — one real gap closed)

`engineering-workflow.md` §2 (UNDERSTAND→...→RUNTIME VALIDATE→REPORT) and `playbooks/deploy.md` (preview→apply→validate→rollback-ready) **already** cover most of the brief's requested closed loop. The one genuine gap: neither explicitly states that a **failed** runtime validation routes back into the existing TROUBLESHOOT workflow, fixes the cause, and **re-runs the same validation** before any completion claim — today this is implied but not stated. `playbooks/deploy.md`'s workflow gains one explicit line: *"If runtime validation fails: apply `troubleshoot.md`'s evidence-first RCA to the failure, fix the smallest safe verified cause, and re-run the same validation — never report DEPLOYED or COMPLETE without a successful re-validation."* This closes the loop with a one-line addition to an existing file, not a new mechanism.

### F.7 Completion truth for builders (no new status system — confirmed unnecessary)

The existing completion-evidence table (`evidence-policy.md` §6: Code/Tests/Reviewed/Merged/Deployed/Live-validated, PARTIAL/COMPLETE/BLOCKED/FAILED) **already** produces exactly the examples the brief gives:

- Terraform code exists, plan not run → `Tests: ❌` (or N/A if genuinely out of scope) → `Overall: PARTIAL` — already the rule (§3 hard rules: "code written ≠ done").
- Plan passes, apply not performed → `Deployed: ❌` → `Overall: PARTIAL` — already the rule ("tested ≠ deployed").
- Apply performed, runtime validation unavailable → `Live validated: ❌, RUNTIME VALIDATION REQUIRED` → `Overall: PARTIAL` — already the rule ("deployed ≠ live validated").
- Runtime verified → all rows ✅ → `Overall: COMPLETE` (or `VERIFIED` when the user asked a VALIDATE-shaped question) — already the rule.

**No new status system is introduced.** This section exists to confirm, not to design — the brief's own instruction ("use existing Groundwork completion terminology where possible rather than inventing a second status system") is fully satisfiable with zero changes to `evidence-policy.md` §6; at most, the DEPLOY playbook's Output Format example gains one or two infra-specific illustrative lines.

New spec: `specs/builder-execution-roles/spec.md` (covers §F.2-F.7's behavioral contract with the acceptance scenarios in §L).

---

## G. SRE capability consolidation — analysis, not a new component

The brief lists ~20 SRE capabilities (incident investigation, RCA, drift detection, capacity analysis, SLO/error-budget analysis, postmortem generation, etc.) and asks whether each needs a new agent/skill or can compose through existing workflows. This section is the answer, and the answer is: **compose, with one confirmed real gap.**

| Capability | Composes through | Confirmed available? |
|---|---|---|
| Incident investigation, RCA, evidence collection | `TROUBLESHOOT` playbook + `evidence-policy.md` §7 (strengthened by evidence-taxonomy) | **VERIFIED existing, strengthened this pass** |
| Terraform/IaC plan intelligence | `VALIDATE`/`DEPLOY` playbook + Infrastructure Engineer role (§F) | **VERIFIED existing + this pass's builder roles** |
| Environment comparison, desired-vs-actual drift detection | `AUDIT` playbook + repository-understanding (§E) + runtime evidence (`terraform plan`, `kubectl diff`) | **VERIFIED existing playbook + this pass's shared discovery** |
| Change correlation, change timeline construction | `TROUBLESHOOT` playbook step 3 ("gather evidence: logs, events, config, recent changes (`git log`)") | **VERIFIED existing, unchanged** |
| Capacity/resource analysis, CPU/memory/storage, Kubernetes requests/limits, autoscaling | `AUDIT`/`TROUBLESHOOT` + curated ECC `infra_sre` skills (`production-audit`, `latency-critical-systems`, `data-throughput-accelerator`) + runtime evidence (`kubectl top`, metrics) | **VERIFIED existing playbooks + curated ECC** |
| SLO/error-budget analysis, availability/reliability analysis | `AUDIT`/`VALIDATE` + runtime evidence | **Composes, but no ECC skill by that name was confirmed among the representative names surfaced** — UNVERIFIED whether any of the `infra_sre` category's remaining ~5 unnamed skills cover this; not a blocker (native reasoning + runtime metrics evidence is sufficient), but flagged honestly rather than asserted |
| Dependency/upgrade analysis | `AUDIT`/`RESEARCH` + repository-understanding | **VERIFIED existing** |
| Cloud cost impact | `AUDIT`/`DESIGN` + runtime evidence (billing API via MCP if configured) | **Composes; Groundwork installs no cost-specific tooling** — task-driven, per §F.5 |
| Runbook execution | `DEPLOY`/`TROUBLESHOOT` + repository's own runbook docs (read as evidence, per `DOCUMENT` playbook's existing "reuse an existing template" rule) | **VERIFIED existing** |
| Post-deployment validation | `DEPLOY` playbook step 6, extended (§F.6) | **VERIFIED existing, one gap closed this pass** |
| Postmortem generation | `DOCUMENT` playbook (existing "incident write-up" format) + `teach-learn-capability` (§I) for the learning angle | **VERIFIED existing, composes with this pass's addition** |
| Security/IAM investigation | `AUDIT` playbook + curated `security-reviewer`/`database-reviewer`/`network-config-reviewer` (ECC) | **VERIFIED existing + curated ECC**, though §D.2 confirms ECC itself has no dedicated IAM/cloud-security-posture skill — a gap in the upstream toolbox, not in Groundwork's composition |
| Learning from completed incidents/changes | `teach-learn-capability` (§I) | **New this pass, small** |

**Explicit non-fragmentation rule** (the direct answer to §7 of the brief, and the reason no `specs/sre-capability/spec.md` file exists): Groundwork SHALL NOT introduce a separate agent, skill, or playbook per SRE sub-capability listed above. This is not a new rule to write — it is `architecture-quality.md` §4's existing principle ("no abstraction, layer, plugin point, framework, or option without a concrete reason") applied here, plus `task-routing.md`'s existing "exactly one category per task" rule, both unchanged. This section is deliberately **analysis only, producing zero new files** — which is itself the correct, evidence-backed answer to "should this be consolidated," matching the brief's own instruction not to add a component "merely because it sounds useful."

---

## H. Presentation, output-style, and design-system architecture

### H.1 What Claude Code already provides — VERIFIED this pass, corrects one prior assumption

- **Native output styles** (VERIFIED, `code.claude.com/docs/en/output-styles`, fetched 2026-09-28): a Markdown file at `.claude/output-styles/` (project) or `~/.claude/output-styles/` (user), selected via `/output-style <name>` or the `outputStyle` settings.json key (already a pre-existing key Groundwork's own installer tests were built to preserve, confirming this mechanism was already indirectly known to exist). A custom style **replaces** Claude's default system-prompt instructions unless it opts in to `keep-coding-instructions: true`. Multiple named styles coexist and are switchable. **The docs state explicitly: "an output style is an instruction Claude follows... nothing enforces it... use a hook for anything that has to happen without fail."**
- **Native Artifacts** exist in Claude Code CLI (VERIFIED, `code.claude.com/docs/en/artifacts`) — this corrects an initial assumption in this pass's research that Artifacts were claude.ai/Cowork-only. However, Artifacts require ALL of: a Pro/Max/Team/Enterprise plan, `/login` with a claude.ai account, the direct Anthropic API (not Bedrock/Vertex/Foundry), and no CMEK/HIPAA/ZDR org policy — an enterprise engineer using an API key or a Bedrock/Vertex-backed deployment (a plausible, even likely, configuration for the enterprise audience this brief targets) does not get Artifacts. **Groundwork cannot assume Artifacts are available.**
- **A first-party, plan/login-independent document-generation plugin** (VERIFIED, `code.claude.com/docs/en/plugins/anthropic-marketplaces` + `github.com/anthropics/skills`): `/plugin marketplace add anthropics/skills` then `/plugin install document-skills@anthropic-agent-skills` installs docx/pdf/pptx/xlsx generation skills, with no plan-tier or claude.ai-login gate described anywhere in the docs (unlike Artifacts). This is the mechanism, if the engineer chooses to install it, for real pptx/docx output.
- **Markdown/HTML/Mermaid via ordinary Write+Bash** — VERIFIED, no gate of any kind, available in every plain Claude Code CLI session regardless of plan or auth state. Anthropic's own output-styles documentation uses a Mermaid-diagram-first custom style as its own worked example, treating this as an ordinary, expected capability.

### H.2 The ownership decision this evidence settles (not an owner decision — the evidence is clear)

**Groundwork's `output-contract.md` (truth: evidence, validation, completion status) stays exactly where it is — rule text, always loaded, enforced by nothing but honesty and (for the one enforced piece, independent review) a hook.** It is never reimplemented as a native output style, because the platform's own documentation says output styles are unenforced instructions, and Groundwork's entire reason for existing is that unenforced instructions are not enough for the things that must be true. This directly matches the brief's own conceptual diagram (`AUTHORITATIVE EVIDENCE → GROUNDWORK OUTPUT CONTRACT → STYLE`).

**Native output styles, where the owner chooses to use them, own tone/audience/format framing (concise/technical/executive/incident/architecture/presentation) — a set of *optional*, Groundwork-authored custom style files is the smallest-maintainable way to offer this, not a new Groundwork mechanism.** Each such style file, if and when authored, must state in its own instructions that Groundwork's evidence/validation/completion rules (loaded separately, via `~/.claude/rules/`) remain in force regardless of style — this is a one-sentence requirement per style file, not new machinery.

**RUNTIME VALIDATION REQUIRED item — RESOLVED (2026-09-28, Phase 1 implementation)**: whether selecting a non-Default output style has any effect on whether `~/.claude/rules/**/*.md` (including Groundwork's own rules) still load. **VERIFIED by direct live test**: an isolated `CLAUDE_CONFIG_DIR` with a rule file containing a distinctive exact-string instruction and a custom output style (not opting into `keep-coding-instructions`, the strongest replacement case) — the rule's instruction was honored identically with the custom style selected and with the default style, while the custom style's own tone instruction (terse, few words) was independently confirmed active (a control prompt produced a visibly longer, more explanatory answer under the default style and a markedly shorter one under the custom style on the same question). Confirms the docs' own INFERENCE was correct: rules/ and output-styles are separate loading pipelines. No workaround or extra machinery is needed in Phase 11 for this; a Groundwork-authored output style file can be shipped without risk of it silently suppressing `output-contract.md`/`evidence-policy.md` enforcement.

### H.3 Presentation capability (§9 of the brief)

Routes through the **existing `DOCUMENT` category and playbook** (`task-routing.md`'s DOCUMENT row already covers "report, summary... executive summary" — a presentation is one more format under the same umbrella; no new task-routing category). `playbooks/document.md` gains a short branch for when the requested format is a presentation/deck:

- Source of truth is the same as every other DOCUMENT output: "gather the source of truth before writing: the repository, configuration, tests, CI, runtime evidence, or the findings being reported" (existing rule, unchanged) — for a presentation this means the same verified evidence a completed task already produced (completion facts, validation results, architecture as it actually is), never invented numbers or fabricated architecture to make a slide look better. This is the brief's own "critical rule" (§9), and it is enforced by nothing new — it is `output-contract.md`'s existing "never imply verification that did not happen" rule, applied to slide content.
- Default output format: **Markdown/Mermaid** (portable, no plan/auth gate, git-diffable) — matching the "smallest maintainable" instruction and the fact that this format works identically regardless of the engineer's plan tier or model provider.
- Optional enhancement, never assumed: if `document-skills@anthropic-agent-skills` is installed, use it for real `.pptx`/`.docx` output; if not, produce Markdown and say so, never fail or degrade quality by assuming a tool that may not be present.

### H.4 Design system (§10 of the brief) — smallest maintainable form, OPTIONAL/LATER

A "concise design-system artifact plus templates," as the brief itself suggests as the ceiling, not a design framework. Concretely, if and when built: one small reference file capturing slide-structure conventions (title/section/architecture-diagram/KPI/closing slide patterns), Mermaid diagram conventions for architecture/workflow diagrams, and a note on how it composes with `document-skills`' own theming if that plugin is installed. **This artifact is explicitly OPTIONAL/LATER in this pass (§O)** — it is a template library, not a governance capability, has no deterministic acceptance criterion suited to Groundwork's test discipline, and building it now would be exactly the "add a component merely because it sounds useful" the brief warns against before a real presentation task has exposed what the template actually needs to contain. The **architecture decision** (native styles + DOCUMENT playbook + Markdown-first + evidence-truth-never-changes) is decided now; the **artifact** is deferred.

New spec: `specs/presentation-and-output-style/spec.md` (covers the truth/style separation invariant and the presentation-truth rule — the two genuinely new, testable contracts from §H.2-H.3; the design system itself has no spec since it doesn't exist yet).

---

## I. Teach/learn capability

"Teach me what we just fixed" already routes to **EXPLAIN** today (`task-routing.md`'s EXPLAIN row: "explain or teach something, answer a technical question"). `playbooks/explain.md` gains a short "teach from verified work" branch:

- **Source is the session's own established evidence** — completion facts, evidence chain, and (where `investigation-continuity`, §M/D2, is in play) the rejected hypotheses and decisions it recorded. This is a direct, deliberate reuse of `investigation-continuity`'s data, not a second knowledge store — the brief's own instruction ("do not create a second knowledge database") is satisfied by consuming, not duplicating, the D2 mechanism's output.
- **Never rewrite or reinterpret facts beyond the evidence** — if teaching about work from an unavailable prior session, state plainly what is being reconstructed from artifacts (commits, docs, tickets) versus recalled directly, matching `evidence-policy.md` §8's existing "repository/runtime wins over memory, mismatch is reported" rule.
- Output covers, only when the evidence actually supports each: what happened, architecture involved, why it failed, how it was diagnosed, evidence used, commands/tools involved, rejected hypotheses, final cause, remediation, prevention, concepts worth learning, and an optional short quiz — reusing `output-contract.md`'s existing three-layer shape (plain explanation first, technical detail on demand), not a new response format.

New spec: `specs/teach-learn-capability/spec.md` (small — the one real contract is "never exceeds the session's own verified evidence").

---

## J. Capability ownership matrix (comprehensive, cross-cutting)

| Capability | Current owner | Proposed owner | Native Claude overlap | ECC overlap | OpenSpec overlap | External tool overlap | Decision | Reason |
|---|---|---|---|---|---|---|---|---|
| Evidence policy / labels | Groundwork | Groundwork | None | None | None | None | KEEP | Groundwork's core reason to exist |
| Material requirements / acceptance criteria | OpenSpec | OpenSpec | None | None | Owns it | None | KEEP | Unchanged — brief §13 reaffirmed |
| Agent/subagent/team execution primitive | Claude Code | Claude Code | Owns it | Consumes it | None | None | KEEP | Groundwork adds no orchestration code |
| Task routing (10 categories) | Groundwork | Groundwork | None | None | None | None | KEEP | No new category needed for builders/presentation |
| Output truth (evidence, validation, completion) | Groundwork | Groundwork | Explicitly NOT owned by native output styles (§H.2, docs' own words) | None | None | None | KEEP | The one thing that must survive any style |
| Output style (tone/format framing) | — (did not exist) | **Native Claude output-styles**, Groundwork authors optional presets | Owns the mechanism | None | None | None | NEW, native-owned | Docs explicitly recommend this split |
| Independent review gate (presence) | Groundwork hook | Groundwork hook | Subagent/teammate spawn mechanism (fresh context, free) | Provides reviewer personas | None | None | KEEP | Working, tested |
| Independent review evidence (MUST-FIX resolution) | — (did not exist) | Groundwork hook, extended | Reuses telemetry's existing command-classification regex | Reviewer output format | None | None | NEW, redesigned D3 | See §M |
| Protected-branch/push safety | Groundwork hook | Groundwork hook | Bash permission model is the backstop | None | None | None | KEEP | Working, tested |
| Cloud/IaC/production mutation safety | — (advisory only) | Groundwork policy + up to 3 narrow new hooks | Bash permission prompts (Tier 1) | None | None | The actual `terraform`/`kubectl`/cloud CLI | Decision-pending, redesigned D5 | See §M |
| Session-start continuity snapshot | Groundwork hook | Groundwork hook | SessionStart hook mechanism | None | Consumes `openspec status` | None | KEEP | Working, tested |
| Investigation continuity (rejected hypotheses) | — (did not exist) | Decision-pending (D2) | None | None | None | None | Decision-pending | See §M |
| Telemetry | Groundwork hook | Groundwork hook | Stop hook mechanism | None | None | None | KEEP | Thoroughly tested |
| Health dashboard | Groundwork script | Groundwork script | None | None | None | None | KEEP | No gap found |
| Installer / upgrade / rollback | Groundwork | Groundwork | None | Installs ECC | Installs OpenSpec CLI | None | STRENGTHEN | Node version bug |
| ECC capability selection | — (wholesale install) | Groundwork policy — CORRECTED (M4): no curation mechanism exists on the plugin-install path; `hook_profile` config + whole-plugin disable only | `skillOverrides` confirmed NOT applicable to plugin skills (source-verified) | Owns the capabilities themselves | None | None | Documented limitation, not a new policy | §D |
| Repository understanding (discovery procedure) | Partially exists (generic UNDERSTAND step) | Groundwork policy, extended for builder domains | None | None | None | None | STRENGTHEN | §E — extends 3 existing playbooks, no new file |
| Infrastructure/Platform/Delivery/Application builder roles | — (did not exist) | Groundwork policy (role personas) + native dynamic subagent/team instantiation | Owns the instantiation mechanism | Provides component skills (curated) | Governs MATERIAL builder changes | `terraform`/`kubectl`/cloud CLIs via MCP | NEW policy, no new files beyond rule text | §F |
| Terraform/Ansible/cloud execution | — | Task-driven MCP/CLI | None | **Confirmed absent from ECC** | None | Owns it | Composed, not built | §D.5, §D.4 |
| Kubernetes/Helm/Flux execution | — | Task-driven MCP/CLI | None | Provides pattern-guidance skills only | None | Owns execution | Composed | §D.5 |
| SRE incident/RCA/capacity/drift capabilities | Fragmented across brief's own list | Composed via existing TROUBLESHOOT/VALIDATE/AUDIT + curated ECC + repository-understanding | None new | Partial coverage, gaps noted | None | Runtime evidence via MCP/CLI | **No new component** | §G — explicit anti-fragmentation finding |
| Presentation generation | — (did not exist) | DOCUMENT playbook (policy) + optional `document-skills` plugin (capability) | Artifacts exist but plan/auth-gated, not assumed; `document-skills` plugin is the portable answer | None | None | `document-skills` (Anthropic first-party plugin, not ECC) | NEW policy + optional external plugin | §H — Groundwork builds no rendering engine |
| Design system (visual templates) | — (did not exist) | OPTIONAL/LATER Groundwork template artifact | None | None | None | Composes `document-skills`' theming if installed | DEFERRED | §H.4 |
| Teach/learn | — (did not exist, implicitly EXPLAIN) | EXPLAIN playbook, extended | None | None | None | None | NEW policy, tiny | §I |
| Documentation (README/runbooks/ADRs) | Groundwork (DOCUMENT playbook) | Groundwork (DOCUMENT playbook) | None | `docs` category (2 skills) exists but unused, redundant with existing DOCUMENT rules | None | None | KEEP | No gap found |
| MCP/external tool access | — (implicit) | Groundwork policy: task-driven, least-privilege, no installed-by-default set | Owns the MCP protocol/runtime | N/A | N/A | Owns the actual access | Policy only, no installs | §F.5 |
| Credential handling | — (never Groundwork's) | Unchanged — never Groundwork | N/A | N/A | N/A | Owns it (user's own MCP/CLI config) | KEEP | Confirmed zero-credential design, §A.3 |
| Scheduled automation (Jira/EOD/briefings) | — (does not exist) | Explicitly out of scope this phase | N/A | N/A | N/A | Future MCP need | DEFERRED | Brief §20; `FUTURE-SCOPE.md` §9 already says the same |

No two rows in this table define the same contract independently — every capability has exactly one row, exactly one proposed owner, and an explicit note where an overlap was checked and found not to be a duplication (e.g., `document-skills` vs. Artifacts — different gating, not competing implementations of the same thing; ECC's `docs` skills vs. Groundwork's DOCUMENT playbook — ECC's are unused/redundant, not adopted, so no duplication is introduced by leaving DOCUMENT as-is).

---

## K. Migration plan — re-evaluated, dependency-ordered (supersedes the first pass's flat 6-phase list; content is preserved and merged, not duplicated)

Grouped into the five stages the brief itself proposes, reordered only where repository evidence changed the dependency picture (builder roles depend on repository-understanding and ECC curation; presentation/teach-learn depend on nothing new and could ship earlier, but are sequenced last because they are lowest-priority "experience" work, matching the brief's own stage naming).

### STAGE 1 — FOUNDATION
- **Phase 1 — Correctness fixes**: Node/OpenSpec version bug, version-reference refresh, `dirty_change_names()` consolidation. *(Unchanged from the first pass.)*
- **Phase 2 — Evidence taxonomy**: `CONFLICTING EVIDENCE`/`UNKNOWN` labels, RCA tightening. *(Unchanged.)*
- **Phase 3 — Capability ownership documentation** *(new, cheap)*: fold §J's matrix into `docs/ARCHITECTURE.md`; no new rule mechanism — `architecture-quality.md` §4's existing "no abstraction without a concrete reason" already provides the anti-fragmentation enforcement (advisory, as it already is for everything else in that file); this phase makes the *specific* ownership decisions visible in docs, it does not add new policy machinery.

### STAGE 2 — TRUST
- **Phase 4 — Review evidence strengthening, redesigned**: implement the new D3 (§M) — a structured `REVIEW RESULT` block (rule text, `output-contract.md`) + extended `require_material_review.py` parser that reuses `groundwork_telemetry.py`'s existing test-command-detection regex to require a validation re-run after a MUST-FIX finding, not merely "any tool call."
- **Phase 5 — Investigation continuity**: implement whichever D2 option the owner selects; the critical rejected-hypothesis-survives-recovery test (§L) ships in this phase regardless of option.
- **Phase 6 — Deterministic safety, redesigned**: implement whichever of D5's three narrow candidates (Terraform-prod-guard / kubectl-prod-guard / IAM-mutation-guard) the owner approves, independently shippable, none mandatory.

### STAGE 3 — CAPABILITY
- **Phase 7 — ECC capability policy**: curated install profile (unchanged mechanism from the first pass); cross-checked this pass against builder-role needs (§D.5) — no change to the recommended default set, the builder analysis confirms it rather than expanding it.
- **Phase 8 — Repository understanding**: extend `implement.md`/`deploy.md`/`design.md` with the builder-domain discovery checklist (§E.2); new spec.
- **Phase 9 — Builder execution roles**: extend `engineering-workflow.md` §6 with the four role personas and the MCP/tool-access policy (§F.3-F.5); extend `deploy.md` with the closed-loop troubleshoot-and-revalidate line (§F.6); new spec. Depends on Phase 7 (curated ECC composition) and Phase 8 (shared discovery).

### STAGE 4 — EXPERIENCE
- **Phase 10 — Output-style/presentation architecture**: extend `output-contract.md` with the truth/style separation invariant; extend `document.md` with the presentation branch; new spec. Includes the one RUNTIME VALIDATION REQUIRED check (§H.2: does an output style affect rules/ loading) before any Groundwork-authored style file ships. The design-system template artifact itself is explicitly **not** built in this phase (§O).
- **Phase 11 — Teach/learn**: extend `explain.md`; new small spec.

### STAGE 5 — VALIDATION
- **Phase 12 — End-to-end acceptance scenarios**: the full §L scenario set run as live/model-behavior evidence (matching `docs/VALIDATION.md`'s existing discipline — real transcripts, not just unit-test pass counts), covering every new capability from Phases 4-11.
- **Phase 13 — Cross-phase regression gate**: SHA-256/behavior non-regression on every unchanged file, full existing test suite plus all new tests green in one run, a real upgrade-from-1.5.1 rehearsal, rollback tested, uninstall tested, documentation matches shipped behavior, no completion claim in any phase's VALIDATION.md entry exceeds its evidence, `openspec validate --strict`. *(This is the first pass's old Phase 7, renumbered, content unchanged.)*

**Ordering rationale, restated**: FOUNDATION ships regardless of any decision (D1 is settled; evidence-taxonomy and ownership docs are pure additions). TRUST ships before CAPABILITY because builder roles (Stage 3) will genuinely run `terraform apply`/`kubectl` mutations once shipped, which makes the safety and review-evidence work in Stage 2 a real prerequisite, not a nice-to-have — this is a materially stronger dependency argument than the first pass had, precisely because builder roles now exist in the design. CAPABILITY ships before EXPERIENCE because presentation/teach-learn are lowest-priority "quality of life" work that depends on nothing else and can safely wait. VALIDATION is last because it validates everything that shipped, not a specific new mechanism.

---

## L. Acceptance matrix — every Groundwork 2.0 requirement mapped to a concrete validation method (extended)

### L.1 Carried over from the first pass (unchanged validation methods)

| Capability / requirement | Closes | Validation method |
|---|---|---|
| `evidence-taxonomy` labels exist and are used correctly | §B #3, #4 | Model-behavior observation on constructed prompts |
| Installer Node floor corrected and enforced in `install.sh` itself | §B #16 | Stubbed old-Node fixture test |
| ECC curated default excludes NOT-RELEVANT categories | §B #12, #13 | **CORRECTED (M4): infeasible on the actual install path — no curation mechanism exists.** Full install retained; limitation documented (`ecc-capability-policy` spec) |
| `skillOverrides` only used if confirmed effective on plugin skills | §B #12, #13 | **RESOLVED (M4)**: source-level inspection of the installed Claude Code CLI confirms it is never consulted for plugin-sourced skills — confirmed ineffective, not used |
| Rejected hypothesis never resurfaces after recovery | §B #10 | The named compaction/fresh-session test |
| Recovered state revalidated against current repo/runtime | §B #5 | Stale-vs-current test |
| No chain-of-thought persisted (continuity) | brief §8 | Schema/field inspection |
| Cross-cutting: no completion claim exceeds evidence | §B #6, #20 | Existing hard rules, unchanged |
| Cross-cutting: no hardcoded identity introduced by any phase | §B #17 | Repeat the portability search after each phase |

### L.2 New this pass — the exact scenarios the brief requested (§25), plus their validation method

| Scenario | Requirement it tests | Validation method |
|---|---|---|
| **Repository-aware infra build** — given an existing Terraform pattern, asked for analogous infra, Groundwork reuses it, generated code follows conventions, validation runs, deployment status is not fabricated | `repository-understanding` + `builder-execution-roles` | Live scenario: construct a small fixture Terraform repo with a real module/naming convention, ask for an analogous resource, verify the generated code follows the fixture's convention and that no "DEPLOYED" claim appears without an actual apply |
| **Platform onboarding** — given existing K8s/Helm/Flux patterns, onboarding uses them, rendered config is validated, runtime success is not claimed without runtime evidence | `repository-understanding` + `builder-execution-roles` (Platform Engineer) | Live scenario, same method, Helm/Flux fixture |
| **Delivery** — given existing CI/CD, adding automation modifies it rather than inventing a parallel pipeline without justification | `repository-understanding` + `builder-execution-roles` (Delivery Engineer) | Live scenario, GitHub Actions fixture |
| **Cross-domain build** — genuinely independent workstreams may use an Agent Team; otherwise the simpler model | `engineering-workflow.md` §6 extension (§F.4) | Reuses the existing team-vs-subagent unit-test-on-constructed-transcripts method from the predecessor change (`intelligent-engineering-harness`), extended with a builder-persona case |
| **Repository pattern vs. generic knowledge** — repository conventions win when safe/compatible | `repository-understanding` §E.3 rule 2 | Live scenario: fixture repo convention deliberately differs from the generic/textbook approach; assert the fixture convention is followed |
| **Rejected unsafe pattern** — an existing but unsafe/deprecated pattern is not blindly copied, and the deviation is explained | `repository-understanding` §E.3 rule 2 | Live scenario: fixture repo contains a demonstrably unsafe pattern (e.g. a hardcoded secret in a `.tfvars` example); assert Groundwork does not replicate it and states why |
| **Nonprod deployment** — given explicit authorization, implementation/review/plan pass, Groundwork may deploy through the established mechanism and validates runtime state afterward | `builder-execution-roles` §F.6, existing DEPLOY playbook | Live scenario against a real (sandboxed) nonprod target, matching the rigor of the existing DEPLOY playbook validation already in `docs/VALIDATION.md`'s style |
| **No authorization** — a mutating operation requiring authorization, absent, stops before mutation, preserves completed evidence/work | `engineering-workflow.md` §4 (existing) + redesigned D5 tiers | Unit test on the relevant D5 hook (if one ships) + live scenario for the advisory (§4) path |
| **Presentation truth** — slides use only supported architecture/results/metrics/status; visual/storytelling transformations do not change factual meaning | `presentation-and-output-style` §H.3 | Live scenario: generate a presentation from a known evidence set, assert every factual claim in the deck traces to that evidence set with nothing added |
| **Output style invariance** — one evidence package rendered as technical/executive/presentation output yields equivalent factual claims and completion status | `presentation-and-output-style` §H.2 | Live scenario: same completed task, three output styles, diff the factual content (not the prose) |
| **D3 MUST FIX** — a MATERIAL change with a MUST FIX finding is not complete until a fresh independent review confirms it was resolved, not just that an edit and a validation re-run followed it | Redesigned D3 (§M), further strengthened at implementation authorization | `test_hooks.py::test_review_gate_must_fix_strengthening`: MUST-FIX-no-follow-up (block); edit-only (block); edit+test-rerun-but-no-fresh-review (**still block** — this is the strengthening); edit+test+fresh-clean-review (allow); fresh review still finding fewer-but-nonzero (block, updated count); no-MUST-FIX (unchanged/allow) |
| **Continuity** (compaction, fresh-session, rejected hypothesis) | D2 | Retained unchanged from L.1 — this is the same critical test, not a new one |
| **Deduplication** — a proposed capability already adequately provided by native Claude/ECC/OpenSpec/existing Groundwork is composed, not reimplemented | §G, §J | This document's own §D.5, §G, and §J tables **are** the evidence for this scenario at design time; at implementation time, each phase's independent review explicitly checks its diff against §J before approval |

---

## M. Decisions requiring owner input before implementation

### D1 — Node/OpenSpec version fix (unchanged, settled)
**Recommendation: approve as-is.** No material uncertainty remains. *(Full record unchanged from the first pass.)*

### D2 — Investigation continuity for non-OpenSpec-tracked work (unchanged options, reaffirmed field list)
Same two options as the first pass (A: extend the existing convention-based model with no new file; B: one small, capped, opt-in investigation-state artifact). **Reaffirmed per this pass's explicit instruction**: whichever option is selected must preserve exactly these fields — objective, proven facts, evidence references, decisions, rejected hypotheses with reason, active hypotheses, files changed, validation results, blockers, uncertainty, remaining tasks, next action — and must never persist chain-of-thought. The critical test is unchanged: a rejected hypothesis must not become active or verified after compaction or fresh-session recovery unless new evidence explicitly reopens it, and current repository/runtime evidence always outranks saved state. **No change to the recommendation** (Option B is the only option that makes acceptance criterion #10 more than advisory; Option A is the fallback if the owner judges the second-source-of-truth risk to outweigh the guarantee) — this remains a genuine owner decision.

### D3 — Review evidence strengthening — **REDESIGNED this pass, STRENGTHENED AGAIN at implementation authorization (2026-09-28), shipped as the strengthened version**

**Correction notice (independent-review finding "review-1", Phase 4 implementation)**: the "DECISION (proposed)" text immediately below describes this pass's second-draft design — "an edit and a validation re-run" as sufficient to clear a MUST-FIX finding. Before implementation began, the owner's authorization message went further, verbatim: *"MUST FIX → Edit → Test alone is NOT sufficient evidence of resolution. The resulting change must receive fresh independent review after the fix."* This is what was actually built (`hooks/require_material_review.py` evaluates the most recent review-shaped call's own verdict, not just edit+test presence) and tested (`tests/test_hooks.py`'s MUST-FIX strengthening cases include "edit + test, no fresh review → still block"). The "What is deliberately not built" paragraph below, which says "no requirement that a second review confirm the fix," is superseded by this same authorization and is **no longer accurate** — a second, fresh review confirming `Must-fix: 0` is exactly what is now required. See `specs/review-evidence-strengthening/spec.md` for the corrected requirements and scenarios that match the shipped code.

The first pass's proposal ("any tool call after a MUST-FIX review satisfies the gate") was correctly rejected as too weak: it does not demonstrate the finding was addressed or that affected validation reran. Redesigned contract (this pass's second draft, further strengthened as noted above before implementation):

```
IMPLEMENTATION → INDEPENDENT FRESH-CONTEXT REVIEW → STRUCTURED REVIEW RESULT
  → MUST FIX? YES → resolve finding → rerun affected validation → verify resolution
             NO  → continue
  → completion gate
```

**DECISION (proposed)**: two small, composable additions, both reusing existing Groundwork mechanisms rather than building new infrastructure:

1. **A structured `REVIEW RESULT` block**, defined in `output-contract.md`, that any reviewer-shaped call (ECC reviewer, subagent, or teammate) is asked to emit at the end of its own response — the exact same pattern already proven by the existing `Harness metadata` block (a short, fenced, label-shaped block that `groundwork_telemetry.py` already parses deterministically from free text). Minimal shape: `Verdict: approve | changes-required`, `Must-fix: <N>`, `Findings: <short labels>`.
2. **`require_material_review.py` is extended** (not replaced) — **AS SHIPPED** (corrected from this pass's original (c) below, per the strengthening in the correction notice above): (a) locate this block in the reviewer's own transcript output when present, (b) if `Must-fix: 0` or the block is absent, behave exactly as today (presence-only gate, unchanged); (c) if `Must-fix: N>0`, the hook evaluates the **most recent** review-shaped call's own verdict — an edit and a test/validation-shaped Bash call observed after the review are necessary but not sufficient; Stop stays blocked until a **subsequent, fresh** review-shaped call itself reports `Must-fix: 0`. Still reuses, not reimplements, `groundwork_telemetry.py`'s already-tested `TEST_CMD` regex classification for the edit/test-observed diagnostics shown in the block message. *(This pass's original (c), superseded: "additionally require, before allowing Stop, both a file-editing tool call and a test/validation-shaped Bash call observed in the transcript after the review" — i.e. edit+test alone, with no fresh review, was originally proposed as sufficient. Kept here, struck through in spirit not text, for the decision's own audit trail.)*

**What is deliberately not built**: no persistent findings database, no workflow-tracking engine — *(corrected: a fresh review confirming the fix IS now required, per the correction notice above; what remains not built is only a structured, separately-tracked record of that requirement — the requirement itself is enforced purely by re-evaluating the same transcript scan against whichever review-shaped call is most recent, exactly the "smallest deterministic mechanism" discipline this document asks for, not a database)*. Everything still lives in the existing session transcript, already retained by Claude Code, read once at Stop time. "What diff was reviewed" and "reviewer independence" are not separately tracked: independence is a structural guarantee of the subagent/teammate spawn mechanism itself (fresh context is definitionally true for any `Agent` call, confirmed by the predecessor change's own verified research), and diff-identity is implicit in the existing precondition (the hook only fires when a complete-and-uncommitted OpenSpec change exists) — adding explicit diff-hash tracking was considered and rejected as unneeded machinery for a gap this narrow.

EVIDENCE: the `Harness metadata` block pattern and `groundwork_telemetry.py`'s `TEST_CMD` regex are both existing, tested Groundwork mechanisms (confirmed by the first pass's independent code audit) — this redesign composes them rather than inventing a new mechanism, directly satisfying "investigate the smallest deterministic representation... do not create a database/workflow engine unless no smaller mechanism can satisfy the contract."
WHY: a structured, short, label-shaped block is exactly as fragile/robust as the existing Harness metadata block already proven in production telemetry parsing — reusing a validated pattern beats inventing a new one.
TRADEOFFS: a reviewer that does not emit the structured block degrades gracefully to today's presence-only behavior (never worse than the current gate, never silently stricter without the reviewer's cooperation) — this means the strengthened check only engages once reviewer prompts/personas are updated to know about the block, which is a rollout dependency, not a design flaw; a reviewer or the model could still fabricate `Must-fix: 0` when there was a real finding — this is the same class of residual gameability the existing gate already accepts ("enforces that review happened, not its quality").
VALIDATION METHOD: new `test_hooks.py` cases (§L.2).
UNCERTAINTY: whether real ECC/subagent/teammate reviewers can be reliably prompted to emit the block consistently — RUNTIME VALIDATION REQUIRED, a small sample check before Phase 4 ships (same caution the first pass already flagged, now sharpened: the sample check should specifically verify the block appears, not just check MUST-FIX vocabulary generally).
**Recommendation: approve this redesigned, two-part mechanism — it is the smallest deterministic representation found that actually satisfies the brief's stronger contract.**

### D4 — ECC capability policy mechanism — **CORRECTED during Phase 1 implementation (finding "M4"), see §A.6/A.8/D.1**
The two-part mechanism this section originally described (ECC install-time flags + conditional `skillOverrides`) is **not implementable**: neither lever is available on the install path Groundwork actually uses (verified at the source/behavior level, not assumed). §D.5's builder-capability sourcing analysis still confirms no builder role needs a capability outside ECC's default install — that conclusion is unaffected. **Recommendation, corrected: ship ECC's full install (matching 1.5.1's actual behavior), governed only by the already-used `hook_profile` config and the already-documented whole-plugin disable; document the limitation plainly rather than building a curation mechanism that does not exist.** This still satisfies D4 as approved — D4 required validating the mechanism before relying on it, not that curation succeed.

### D5 — Deterministic safety expansion beyond Git — **REDESIGNED this pass, DEFERRED at implementation authorization (2026-09-28)**

**Deferral notice**: the tiered menu below (Tier 0/1/2) was approved as a *design*, but the owner's implementation-authorization message explicitly deferred all of Tier 2 rather than approving any specific candidate: *"Do NOT implement Terraform-prod-guard, kubectl-prod-guard, or IAM-mutation-guard merely to complete the checklist, because production-vs-nonprod detection depending on heuristic naming risks false confidence."* None of the three Tier-2 candidates are implemented in Groundwork 2.0. This is **not a gap that blocks the 2.0 release** — the owner's own words: *"This deferral MUST NOT block the Groundwork 2.0 release."* Tier 0 (read-only, always allowed) and Tier 1 (nonprod mutation, authorized by the task, covered by existing Claude Code permissions + `engineering-workflow.md` §4) both remain exactly as designed below and required no new hook — they were never Tier-2's concern. What ships in 2.0 for safety beyond Tier 0/1: the existing protected-Git hook (`block_protected_push.py`, unchanged), the existing risk/autonomy rule (§4, unchanged, extended to builder-role work in §F.5/Phase 9), and native Claude Code permissions (unchanged) — all live-tested in Phase 9's "no authorization" scenario (`docs/VALIDATION.md`), which stopped a destructive production operation before mutation with none of Tier 2 involved. If a deterministic, non-heuristic, provably-portable production-target-identification mechanism is found in the future, it is a candidate for a later release, documented here rather than expanding this release's scope without approval — see `docs/FUTURE-SCOPE.md`.

The first pass deferred to a single vague "narrow candidate, owner decides." This pass's builder roles (§F) mean Groundwork will, if approved, genuinely execute `terraform apply`, `kubectl` mutations, and similar — this materially strengthens the case that *some* deterministic guard is warranted (the "a real task exposed the gap" trigger `FUTURE-SCOPE.md` §12 requires is now much closer to true, because the task now genuinely exists in the design, not hypothetically). Redesigned into a **tiered, menu-based model** instead of one abstract candidate — this design remains the reference for any future revisit of the deferral, unchanged by the deferral itself:

**Tier 0 — read-only discovery.** `terraform plan`, `kubectl get/describe`, `gcloud/aws/az ... list/describe`. Always allowed, no gate — matches the brief's own "read-only discovery should generally be safe/default."

**Tier 1 — nonprod mutation, explicitly authorized by the task.** `terraform apply` against a dev/nonprod workspace, `kubectl apply` to a non-prod namespace/context, when the user's own request named the action (e.g. "deploy this to our dev GKE cluster"). **Needs no new hook** — already covered by (a) Claude Code's own Bash permission prompts (unchanged, existing backstop) and (b) `engineering-workflow.md` §4's existing autonomy rule, which already lists only production/IAM/data/paid-resource changes as requiring authorization, implicitly leaving nonprod mutation unblocked when the task itself authorized it. Confirmed by re-reading §4, not assumed.

**Tier 2 — production / IAM / data-destructive / paid-resource-creation.** This is where a deterministic hook adds real value beyond a prompt (the same reason `block_protected_push.py` exists at all — a hook cannot be argued around the way a permission prompt sometimes can). Three independently-approvable, narrowly-scoped candidates, each structurally mirroring `block_protected_push.py` (fail-open, pattern-matched, depth-limited shell/eval parsing, adversarially tested for both bypass **and** false-positive):

1. **Terraform-prod-guard**: deny `terraform apply`/`destroy` with no preceding `terraform plan`-generated plan file referenced, or targeting a workspace/state-backend matching a production-naming pattern discoverable via `repository-understanding` (§E.2's environment-organization discovery step) — **highest priority of the three**, closest in shape and risk profile to the already-proven push guard.
2. **kubectl-prod-guard**: deny mutating verbs (`apply`/`delete`/`patch`/`scale`/`rollout`) against a context/namespace matching a production-naming pattern.
3. **IAM-mutation-guard**: deny a short, explicit list of IAM-mutating cloud-CLI commands (`aws iam`, `gcloud iam`, `az role` create/attach/delete forms) outright, mirroring how the push guard denies force-flags outright rather than pattern-matching them.

Each is independently shippable, independently revertable, and none is mandatory — the owner may approve zero, one, two, or all three.

**The known, honestly-stated limitation carried into every one of these**: production-vs-nonprod detection by naming convention is heuristic and repository-specific (same class of limitation as the push guard's own documented "non-exact branch names" gap) — the guard's accuracy depends on `repository-understanding` correctly surfacing the repo's actual environment-naming convention, and a repository with no consistent naming convention degrades these guards to the explicit-list case only (IAM-mutation-guard) or to relying on the Tier 1 authorization-in-the-request signal alone.

EVIDENCE: `FUTURE-SCOPE.md` §10's original deferral, now counter-weighted by this pass's builder roles making the "real task" trigger concrete rather than hypothetical; the brief's explicit instruction to "avoid false positives... prefer risk-aware authorization... nonprod mutation may be allowed when explicitly authorized."
WHY: a tiered menu resolves the first pass's "too vague to approve" problem without pre-committing to a broad, false-positive-prone mechanism — each tier's boundary is drawn from evidence already established elsewhere in this document (§F.5's Tier 1 reasoning, the push guard's own proven pattern for Tier 2).
TRADEOFFS: three hooks is more surface area than one — mitigated by each being independently approvable and structurally identical to a hook already shipped, tested, and validated; the production-naming-heuristic limitation is real and stated, not hidden.
VALIDATION METHOD: adversarial bypass **and** false-positive testing for each approved candidate, mirroring the push guard's own 19-case suite, per candidate.
UNCERTAINTY: none of the three candidates has been built or tested yet — this is a design proposal, not implemented evidence; the production-naming-detection accuracy specifically needs real-repository validation before any candidate ships.
**Recommendation as designed (superseded by the deferral above): approve Terraform-prod-guard at minimum (closest to proven pattern, highest-value target given builder roles will genuinely run `terraform apply`); kubectl-prod-guard and IAM-mutation-guard are owner's call based on which mutation surface the owner's actual environments expose most.** The owner's actual decision deferred all three — this recommendation is kept as the reference point for a future revisit, not as what shipped.

---

## N. Risks and unresolved questions (material items only, extended)

1. **`openspec/changes/intelligent-engineering-harness` is unarchived with one blocked task.** *(Unchanged from the first pass.)*
2. **§D.2/D.3's ECC category tables are checksum-verified data — against the wrong artifact.** **CORRECTED (M4, Phase 1 implementation)**: install.sh does not install the npm tarball these tables were built from; it installs ECC's GitHub `main` via the plugin marketplace, unpinned. The tables are a stale snapshot kept for institutional record; §D.4's central finding was independently re-checked against the real installed content and still holds. See §A.6.
3. **The `skillOverrides`-on-plugin-skills question (D4) is resolved.** **CORRECTED (M4, Phase 1 implementation)**: source-level inspection of the installed Claude Code CLI confirms `skillOverrides` is never consulted for plugin-sourced skills — confirmed ineffective for ECC, not a pending question. See §A.8/D.1.
4. **D5 is now a stronger case for approving at least the Terraform-prod-guard**, but is still fundamentally an owner risk-appetite call — see D5 above.
5. **Node version fix (D1) is a breaking change for a currently-silent-failure population.** *(Unchanged.)*
6. **This document itself should go through the same independent-review gate it describes** before any phase begins implementation.
7. **RESOLVED (2026-09-28)**: the output-style/rules-loading interaction (§H.2) — VERIFIED by direct live test that rules/ still load and are honored regardless of output-style selection. See §H.2 for the evidence.
8. **NEW this pass: SRE capability consolidation (§G) found several capabilities (SLO/error-budget analysis, IAM/cloud-security-posture) where ECC itself has no matching skill**, mirroring the Terraform/cloud-provider gap found in the first pass. Groundwork's composition model handles this correctly (native reasoning + runtime evidence fills the gap; Groundwork does not need to build a replacement skill) but the owner should be aware these specific SRE sub-capabilities will rely more heavily on native reasoning and less on a curated, pre-built ECC skill than capabilities like Kubernetes/container patterns do.
9. **NEW this pass: the production-naming-detection heuristic underlying all three D5 Tier-2 candidates depends on `repository-understanding` correctly surfacing a repo's actual environment convention** — repositories with inconsistent or absent naming conventions will get materially weaker protection from these guards; this is a real, stated limitation, not a hidden one, and is the single biggest technical risk in the D5 redesign.
10. **NEW this pass: the presentation capability's dependence on an optional, user-installed plugin (`document-skills`) means presentation quality/format genuinely varies by what the engineer has installed** — this is by design (Groundwork does not force a dependency), but should be stated plainly in user-facing docs so it is not mistaken for a bug when an engineer without the plugin gets Markdown instead of a `.pptx`.

---

## O. Proposed Groundwork 2.0 file tree after deduplication

Every artifact below answers "what concrete responsibility requires this," per the brief's own instruction not to force a file tree. Nothing is listed that this document did not derive a specific need for.

```
groundwork/
├── setup.sh                                    EXISTING, MODIFIED (Phase 1: corrected Node floor)
├── install.sh / uninstall.sh                    EXISTING, MODIFIED (Phase 1: Node version check added to install.sh;
│                                                  Phase 7: curated ECC profile flags)
├── rules/
│   ├── engineering-workflow.md                  EXISTING, MODIFIED (Phase 5 D2 outcome; Phase 9: four builder-role
│   │                                              personas + orchestration + MCP/tool-access policy in §6)
│   ├── architecture-quality.md                  EXISTING, UNCHANGED
│   ├── evidence-policy.md                       EXISTING, MODIFIED (Phase 2: CONFLICTING EVIDENCE/UNKNOWN labels)
│   ├── task-routing.md                          EXISTING, UNCHANGED (confirmed no new category needed)
│   └── output-contract.md                       EXISTING, MODIFIED (Phase 4: structured REVIEW RESULT block;
│                                                  Phase 10: truth/style separation invariant)
├── playbooks/
│   ├── implement.md                             EXISTING, MODIFIED (Phase 8: builder-domain discovery checklist)
│   ├── deploy.md                                EXISTING, MODIFIED (Phase 8: discovery checklist; Phase 9: closed-loop
│   │                                              troubleshoot-and-revalidate line)
│   ├── design.md                                EXISTING, MODIFIED (Phase 8: discovery checklist)
│   ├── document.md                              EXISTING, MODIFIED (Phase 10: presentation branch)
│   ├── explain.md                                EXISTING, MODIFIED (Phase 11: teach-from-verified-work branch)
│   ├── troubleshoot.md, audit.md, validate.md,   EXISTING, UNCHANGED (composed by, not modified for, SRE consolidation
│   │   research.md, plan.md                       — §G's explicit finding)
├── hooks/
│   ├── block_protected_push.py                  EXISTING, UNCHANGED
│   ├── require_material_review.py                EXISTING, MODIFIED (Phase 4: redesigned D3 structured-block parser,
│   │                                              reusing telemetry's TEST_CMD regex)
│   ├── groundwork_session_snapshot.py             EXISTING, MODIFIED (Phase 5: D2 outcome; consolidated
│   │                                              dirty_change_names() helper)
│   ├── groundwork_telemetry.py                    EXISTING, UNCHANGED (its TEST_CMD regex is reused, not modified)
│   ├── _shared.py (or similar)                    NEW, Phase 1 — the consolidated dirty_change_names() helper;
│   │                                              the only new hook-adjacent file with zero decision-dependency
│   ├── block_terraform_prod_apply.py              NEW, Phase 6, DECISION-PENDING (D5 Tier 2, candidate 1)
│   ├── block_kubectl_prod_mutation.py             NEW, Phase 6, DECISION-PENDING (D5 Tier 2, candidate 2)
│   └── block_iam_mutation.py                      NEW, Phase 6, DECISION-PENDING (D5 Tier 2, candidate 3)
├── scripts/                                      EXISTING, UNCHANGED — merge_settings.py needs no skillOverrides
│                                                  change (M4: confirmed ineffective on plugin skills, not shipped)
├── tests/                                        EXISTING, MODIFIED across every phase that ships (new cases only,
│                                                  no restructuring)
├── openspec/
│   ├── changes/groundwork-2-enterprise-sre/       THIS document (self)
│   └── changes/intelligent-engineering-harness/   EXISTING, unarchived (§N item 1)
├── docs/
│   ├── ARCHITECTURE.md                            EXISTING, MODIFIED (Phase 3: capability ownership matrix folded in)
│   └── (VALIDATION/TROUBLESHOOTING/UPGRADE-ROLLBACK/FUTURE-SCOPE/CHANGELOG)  EXISTING, MODIFIED per-phase as each ships
└── ~/.claude/output-styles/*.md (installed location, not in this repo's tree)  OPTIONAL/LATER, Phase 10 —
    Groundwork-authored preset style files (concise/technical/executive/incident/architecture/presentation);
    NOT built this pass (§H.4); depends on the RUNTIME VALIDATION REQUIRED rules-loading check (§H.2, §N item 7)
    presentation-design-system reference (template/conventions)                OPTIONAL/LATER, no committed location yet
```

**Explicitly NOT created, and why**: no `agents/infrastructure-engineer.md` or equivalent per-role permanent agent file (§F.2 — roles are dynamic personas in rule text, not files); no `rules/sre-capability.md` (§G — explicit non-fragmentation finding, zero new files); no `rules/repository-understanding.md` as a fifth always-loaded rule (§E.2 — folded into three existing on-demand playbooks instead, to avoid always-loaded cost for non-builder tasks); no `hooks/presentation_generator.py` or any custom rendering engine (§H — composes the native `document-skills` plugin or plain Markdown, builds nothing); no second telemetry/evidence database for teach/learn (§I — consumes existing evidence, does not store new state); no scheduled-automation files of any kind (brief §20, explicitly deferred).

---

## Letter-mapping changelog (for anyone diffing against the first pass)

First pass → this pass: A→A, B→B, C→C (updated), D→D (extended with D.5), [new] →E,F,G,H,I,J, old E (Migration)→K, old F (Acceptance matrix)→L, old G (Decisions)→M, old H (Risks)→N, [new]→O. Every in-document cross-reference and every cross-reference in `proposal.md`, `tasks.md`, and `specs/*/spec.md` has been updated to match this mapping.

## Next step

Per the requesting brief's explicit instruction, repeated in this pass (§28, STOP POINT again): **implementation does not begin from this document.** Task 0.13 (owner sign-off) remains unchecked. PR #20 remains a draft, not merged. No implementation file, hook, rule, script, or user-global Claude configuration has been touched by this pass — only this OpenSpec change's own design artifacts.
