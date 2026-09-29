# Changelog

## 2.1.0 — 2026-09-28

Context engineering, capability resolution, Routines, and a setup-time capability configurator. Tracked in `openspec/changes/groundwork-2.1-context-routines-ux/`; see that change's `tasks.md` for exact phase-by-phase status and `docs/VALIDATION.md` for evidence. Merged to `main` via PR [#22](https://github.com/AshminPy/groundwork/pull/22) (merge commit `e3d4b4f`), after 4 rounds of independent review, Must-fix: 0. Not tagged, not published as a GitHub release.

- **Capability resolution** (`rules/engineering-workflow.md` §6a, new): judgment guidance for which tool serves a task — existing repo tooling → Claude Code native → a trusted already-installed skill → a trusted already-configured MCP/CLI → browser/Chrome → the user for a genuine decision — never overriding tier, evidence, or authorization, which stay governed by the existing rules unchanged. Browser-driven mutations now follow the same authorization rule as MCP/CLI, and require reading the result back before reporting VERIFIED.
- **Five distinct concepts** (`rules/task-routing.md` §4, new): Playbook, Routine, Role, Skill, Tool, kept structurally distinct; the old `## 4. Universal output contract` renumbered to `## 5.`.
- **Routines** (`scripts/groundwork_routines.py`, new): recurring/scheduled automation that runs without an active session, via safe unattended `claude -p` (`--permission-mode dontAsk --permission-prompts none --allowedTools <scoped>`, never `--dangerously-skip-permissions`/`--bare`). Six ship: `jira_eod` (mutating, dry-run-capable), `news`, `weekly_status`, `pr_followup`, `work_digest`, `doc_drift`. Scheduling reuses `groundwork_report.py`'s existing launchd/cron pattern; telemetry follows `groundwork_telemetry.py`'s exact 0600 owner-only, structured-fields-only, no-raw-output discipline. Off-switches: `GROUNDWORK_ROUTINES=off`, `GROUNDWORK_ROUTINES_<NAME>=off`. Full detail: `docs/ROUTINES.md`.
- **Capability configuration** (`scripts/groundwork_config.py`, new): one profile-driven, human-readable, no-secrets `config.json` (8 profiles: SRE/CloudOps, Platform Engineering, DevOps, Software Engineering, Cloud Architecture, Security Engineering, Minimal, Custom); `validate_config()` actively flags anything that looks like a stored credential.
- **`setup.sh`**: optional fourth setup question (capability/Routines selection, defaults to skip; `--capability-profile NAME` non-interactively); three new modes, `--doctor` (extends `--verify` with capability/Routine status, still read-only), `--configure` (revisit selection, no reinstall), `--routines` (list configured Routines and last-run status). `uninstall.sh` removes `config.json` and unschedules every Routine.
- **ECC pinning** (`install.sh`): ECC now installs pinned to a tested ref (`v2.2.1` via `#ref`, not floating `main`), overridable via `GROUNDWORK_ECC_REF`; `setup.sh`'s verification names the pin and whether the installed version matches it.
- **Documentation**: `docs/CONTEXT-ENGINEERING.md` (new — context-source inventory, always/selective/lazy/isolated/persisted/reconstructed), `docs/INTEGRATIONS.md` (new — MCP/CLI capability matrix per external system, documentation only, nothing installed or wired), `docs/ROUTINES.md` (new), `docs/FUTURE-SCOPE.md` extended (curated-skills evaluation, deferred routine candidates), `docs/ARCHITECTURE.md`'s capability-ownership table and `README.md` extended for all of the above.
- **Two real bugs found and fixed during live end-to-end testing** (both invisible to any test written before the live run — see `docs/VALIDATION.md`'s 2.1.0 entry for full reproduction detail): `groundwork_config.py`'s `DEFAULT_PATH` ignored `CLAUDE_CONFIG_DIR` entirely, silently writing `config.json` outside the target config directory; `setup.sh --doctor` silently dropped its own Capabilities/Routines section whenever any core check failed, because an unguarded `verify_install()` call tripped `set -e` before the rest of the function ran. Both fixed at the root and regression-tested.
- Tests: `tests/test_groundwork_config.py` (new, 112 checks), `tests/test_groundwork_routines.py` (new, 114 checks), `tests/test_setup.py` extended (capability/doctor/configure/routines coverage, updated ECC-pin messaging assertions), `tests/test_playbooks.py` extended (Routine/Role/Skill/Tool distinction check). Full suite: `python3 -m pytest tests -q` → 28 test functions, 0 failed.
- **Deliberately not built this pass** (reasoning in `openspec/changes/groundwork-2.1-context-routines-ux/design.md`): Task Observer (privacy-requirement conflict), six further routine candidates (scored, recorded as future candidates), a new terminal-UI dependency (Groundwork stays stdlib-only; the existing HTML dashboard is unchanged), a live activity view (no reliable Claude Code lifecycle-event source found), live MCP/CLI wiring (documentation only — no credentials in scope to wire or verify against).

## 2.0.0 — 2026-09-28

Enterprise SRE/CloudOps upgrade. Tracked in `openspec/changes/groundwork-2-enterprise-sre/`; see that change's `tasks.md` for exact phase-by-phase status and `docs/VALIDATION.md` for evidence. This entry is updated as phases land, not written once at the end.

**Phase 1 — Node/OpenSpec version correctness (Decision D1) + hook dedup:**
- `install.sh` now checks Node's actual version (previously presence-only); both `install.sh` and `setup.sh` correct the documented floor from ≥18 to ≥20.19.0 — OpenSpec's real `engines.node` requirement, not ECC's lower one.
- `setup.sh` distinguishes a Node still too old after an OS package manager "install" (common — distro packages lag upstream) from one still genuinely absent, with accurate guidance either way; `--verify` now reports the actually-installed ECC plugin version (`claude plugin list`), not only the version last checked against.
- `dirty_change_names()` (previously duplicated in two hooks) and the `TEST_CMD` regex (previously duplicated in a third) consolidated into new `hooks/groundwork_shared.py`, imported defensively by each caller so a broken/partial shared module degrades one capability at a time, never crashes a hook.
- **Corrected finding**: ECC installs unpinned from its GitHub `main` branch via `claude plugin marketplace add`/`claude plugin install` — not from npm, as an earlier design draft assumed. No upstream-supported mechanism exists to install a curated ECC skill/agent subset on this path (verified directly, including that Claude Code's `skillOverrides` is never consulted for plugin-sourced skills). `docs/ARCHITECTURE.md` and the `ecc-capability-policy` OpenSpec capability corrected accordingly; see that spec's Purpose section for the full evidence trail.
- Tests: `tests/test_playbooks.py`, `tests/test_setup.py` extended (Node-floor checks at both installer layers, the still-too-old-after-install message, ECC version reporting and its drift-tolerant comparison); a test-suite PATH-isolation gap that let a real host's `node`/`apt-get`/`claude`/`openspec` leak into "should be absent" test fixtures closed (`filtered_sysbin`, both here and in `test_setup.py`).

**Phase 2 — Evidence taxonomy (extends `evidence-policy.md`):**
- `CONFLICTING EVIDENCE` and `UNKNOWN` added as first-class labels alongside VERIFIED/UNVERIFIED/ASSUMPTION/INFERENCE; the root-cause-analysis rule and the troubleshoot/research playbooks now require one of these labels rather than a softened guess when the evidence chain does not support a conclusion.

**Phase 3 — Capability ownership documentation:**
- `design.md` §J's capability-ownership matrix folded into a new `docs/ARCHITECTURE.md` "Capability ownership (2.0)" section — a pointer table, not a duplicate (full detail stays in `design.md` §J to avoid drift), cross-referenced against `architecture-quality.md` §4's existing "no abstraction without a concrete reason" rule as the anti-fragmentation principle. Documentation-only; no rule mechanism or code changed.

**Phase 4 — Review-evidence strengthening (Decision D3):**
- `hooks/require_material_review.py` rewritten: the gate previously only detected that *some* reviewer-shaped tool call happened after a MUST-FIX finding; an edit and a re-run of validation counted as resolution with no check that a fresh review actually confirmed it. Now parses a structured `REVIEW RESULT` block (documented in `output-contract.md`) and evaluates the *most recent* review's own verdict — MUST FIX → fix → revalidate → fresh independent re-review is enforced, not just any tool call. Falls back to the old presence-only check when a reviewer omits the block (never stricter without the reviewer's cooperation).
- 9 new test cases, including the key strengthening case: edit + test alone, with no fresh review, still blocks.
- A second independent review of the combined Phase 1/2/4 diff found and fixed 5 further issues: two real hook fail-open gaps (a crash on non-dict JSON hook input; a later malformed transcript line silently discarding an already-parsed, unresolved MUST-FIX finding and defaulting to allow — both now covered by regression tests confirmed to fail pre-fix and pass post-fix), an OpenSpec spec/implementation drift (the review-evidence-strengthening spec still described the first-pass contract, not the further-strengthened one actually shipped), an evidence citation pointing at a record that didn't yet exist (the figure itself was real, now recorded), and stale ECC catalog figures left in two files the ECC-install-source correction didn't touch. See `docs/VALIDATION.md` for the full evidence.
- A third independent review found the identical non-dict-JSON crash-bug class in `hooks/block_protected_push.py` (checked specifically because the same bug had just been fixed elsewhere) — fixed with the same `isinstance(data, dict)` guard.

**Phase 5 — Investigation continuity (Decision D2, Option B):**
- `hooks/groundwork_session_snapshot.py` extended with `investigation_path()`/`investigation_facts()`: a small, capped, per-repository investigation-state file at a deterministic path (`~/.claude/groundwork/investigations/<slug>-<sha256[:10]>.md`), surfaced at every SessionStart. `engineering-workflow.md` §7 documents the exact field list the owner specified (objective, proven facts, evidence references, decisions, rejected hypotheses with reason, active hypotheses, files changed, validation results, blockers, uncertainty, remaining tasks, next action) — chain-of-thought is never persisted. No new install-managed file; the directory is created lazily by the model's own write, exactly like `telemetry/`/`reports/`, and is preserved on uninstall.
- Critical acceptance test, live-validated: a rejected hypothesis stays rejected after session recovery, and the saved "active" hypothesis is independently re-verified against current repository code before being reported confirmed — current evidence outranks saved state.
- Two independent review rounds found and fixed 2 MUST FIX defects (truncation could silently drop the "Rejected hypotheses" section; a busy repository's git/OpenSpec activity could crowd the whole investigation section out of the snapshot's character cap) plus 5 of 6 NICE TO HAVE, including a `\r` off-by-one in the control-character-stripping regex. One narrow fenced-code-block false-match side channel is documented as a known limitation, not fixed. See `docs/VALIDATION.md`.

**Phase 6 — Deterministic safety expansion (Decision D5) — Tier-2 guards explicitly deferred:**
- The three Tier-2 candidates designed this pass (Terraform-prod-guard, kubectl-prod-guard, IAM-mutation-guard) were explicitly declined by the owner at implementation authorization: production-vs-nonprod detection by heuristic naming risks false confidence. None implemented. This deferral does not block the 2.0 release — Tier 0 (read-only discovery) and Tier 1 (nonprod mutation, task-authorized) needed no new hook and ship unaffected, backed by the existing push guard, the existing risk/autonomy rule, and native Claude Code permissions. Full tiered design preserved as a future option in `design.md` §M/D5 and `docs/FUTURE-SCOPE.md` §10.

**Phase 7 — ECC capability policy (Decision D4) — corrected scope:**
- The original design assumed install-time ECC skill/agent selection was possible. Investigated directly: `claude plugin install` (what `install.sh` actually runs) has no such flag — `--profile`/`--with capability:*` exist only on ECC's separate standalone installer, which must never be combined with the plugin path Groundwork uses. `skillOverrides` confirmed, by source-level inspection of the installed Claude Code CLI, to never apply to plugin-sourced skills. Ships ECC's full, unpinned install unchanged in kind from 1.5.1, governed only by the existing `hook_profile` config and the existing whole-plugin `claude plugin disable ecc@ecc` opt-out — the limitation (no curation mechanism exists on this path) is documented plainly rather than a nonexistent mechanism being built. Context cost measured live: `claude plugin details ecc@ecc` reports ~43,577 tokens always-on.

**Phase 8 — Repository understanding (new capability):**
- `playbooks/implement.md`, `deploy.md`, `design.md` each extended with the same 8-item domain-scoped discovery checklist (module/pipeline structure, naming/variable/label conventions, environment/workspace organization, IAM/networking patterns, state/backend patterns, CI/CD and delivery conventions, testing and validation conventions, closest analogous implementation) under their existing "inspect before writing" step, referencing `architecture-quality.md` §5 rather than restating it. No new rule file. Live-validated: a fixture repo's non-generic Terraform convention correctly reproduced for an analogous resource; a fixture repo's hardcoded-secret pattern correctly flagged and deviated from, with the reason stated, without being told the words "convention" or "unsafe."

**Phase 9 — Builder execution roles (new capability):**
- Four role personas (Infrastructure/Platform/Delivery/Application Engineer) added to `engineering-workflow.md` §6 as dynamic `Agent`-call personas selected per task — explicitly never permanent `.claude/agents/*.md` files; an MCP/tool-access policy subsection folded into the same section. `deploy.md` gained a closed-loop line: a failed runtime validation routes to `troubleshoot.md`'s RCA, fixes, and re-validates before any completion claim. Live-validated: a repository-aware Terraform/GKE build; a destructive production-database request correctly stopped before any mutation, with "edit the file" and "apply to production" separated as two distinct authorization decisions; a cross-domain app+infra build correctly staying in the main session with a stated reason rather than reflexively spawning subagents.

**Phase 10 — Output-style and presentation architecture (new capability):**
- `rules/output-contract.md` gained one invariant: a native Claude Code output style may change tone, format, or audience framing, never the evidence, validation, or completion-status rules this file owns. `playbooks/document.md` gained a presentation branch: Markdown/Mermaid is the default; an installed `document-skills` plugin is used for `.pptx`/`.docx` only when the user wants a bundled file and the plugin is actually present — if not, Groundwork says so and produces Markdown instead of assuming the plugin or silently degrading quality. No rendering engine was built. Live-tested: selecting a non-Default output style does not affect `~/.claude/rules/**/*.md` loading; the same underlying facts rendered under two different output styles produced the same factual content, only tone/detail differing.

**Phase 11 — Teach/learn capability (new capability):**
- `playbooks/explain.md` gained a teach-from-verified-work branch: teaching draws only on evidence this session (or a recoverable investigation-continuity file) established, never invents or embellishes; when the evidence trail is unavailable, states plainly what is reconstructed from artifacts versus recalled with confidence. No new storage — reuses session evidence, git history, and investigation-continuity's existing state.

**Phase 12 — End-to-end acceptance scenarios:**
- All 15 named scenarios from `design.md` §L.2 run as live model-behavior evidence, not simulated: 13 VERIFIED, 2 honestly marked RUNTIME VALIDATION REQUIRED (an actually-applied nonprod deployment; a genuinely parallel Agent Team run) because this environment cannot safely provide the infrastructure either needs. Deduplication check: across all 13 phases, exactly one new production code file exists (`hooks/groundwork_shared.py`), and it is itself a deduplication of two pre-existing duplicated helpers.

**Phase 13 — Cross-phase regression gate + clean-install/upgrade/rollback/uninstall:**
- Full test suite green in one run: `pytest -q` 16 passed; 485 standalone checks across 5 files, 0 failed. `openspec validate groundwork-2-enterprise-sre --strict` passes.
- Clean install, upgrade from a real 1.5.1 baseline (a `git worktree` at the true pre-2.0 commit), rollback, and uninstall each tested live in an isolated throwaway `$HOME` — never this session's own active Claude configuration. Found and fixed a real bug during upgrade testing: `VERSION` stayed `1.5.1` after a genuine 2.0.0 upgrade because `install.sh` derives it from `CHANGELOG.md`'s first real numeric heading, and this file's newest heading read "Unreleased" — fixed by giving this release its actual `## 2.0.0` heading.

**Release status**: merged to `main` via PR #20 on 2026-09-28, after owner review and a fresh-context independent review of every MATERIAL-tier phase. Full detail, exact test/task/acceptance-criteria status, and install/verify commands: `docs/RELEASE-REPORT-2.0.md`.

## 1.5.1 — 2026-09-21

- `setup.sh` detects the OS and offers to install the missing prerequisites other than Claude Code — git, Node 18+ with npm, Python 3.10+ — with the official packages: Homebrew on macOS, apt / dnf / apk on Linux. Opt-in (`y` at the prompt or `--install-prereqs`; `--no-install-prereqs` never installs; `--non-interactive` never installs without the flag). Claude Code must already be installed (official link printed otherwise); Homebrew itself is never installed (official command printed); an existing Node older than 18 is left to the user's version manager. Ten new tests with stub package managers.

## 1.5.0 — 2026-09-21

One-click onboarding. `install.sh`, `uninstall.sh`, hooks, rules, playbooks, telemetry and reporting unchanged.

- **`setup.sh`** (new, thin wrapper): prerequisites (claude, node, npm, git, python3 ≥ 3.10) → complete backup of the Claude config dir to `~/.claude-backups/groundwork-YYYYMMDD-HHMMSS/` (owner-only, never overwritten, `BACKUP-INFO.txt` marker) → profile / Agent Teams / dashboard-schedule questions (or `--non-interactive --profile … --agent-teams|--no-agent-teams --schedule …`) → `install.sh` → `merge_settings.py --profile` → `groundwork_report.py schedule` → first dashboard → read-only verification (+ `tests/test_hooks.py` and `tests/test_telemetry.py` unless `GROUNDWORK_SETUP_SKIP_TESTS=1`) → summary. Modes: `--verify` (read-only PASS / FAIL / NOT CONFIGURED), `--rollback [DIR]` (moves the current config dir to `<dir>-groundwork-disabled-<ts>` first, restores only an unambiguous latest setup.sh backup from the same source dir, removes the launchd job, verifies readability), `--uninstall` (delegates). Failure after the backup prints the backup path and the rollback command.
- `scripts/merge_settings.py --profile NAME` sets `env.GROUNDWORK_PROFILE` additively; `unmerge_settings.py` removes it.
- README Quick start is now `git clone … && ./setup.sh`; `install.sh` documented under manual/advanced.
- Tests: `tests/test_setup.py` (45 checks).

## 1.4.1 — 2026-09-21

- `schedule` on a non-macOS host records the config and says to run `generate --snapshot` manually or from cron instead of pretending a launchd job exists; installer message matches.

## 1.4.0 — 2026-09-21

Local health dashboard from telemetry — no server, no LLM, no network.

- `scripts/groundwork_report.py` → `~/.claude/groundwork/bin/`: `generate` (dashboard.html, `--snapshot` for dated HTML + Markdown), `schedule disabled|daily|weekly|monthly|yearly` (macOS launchd, one job, replaced in place), `status`.
- Dashboard: summary cards with numerator/denominator, trends vs the previous equivalent period (only with ≥5 known outcomes in both), weekly health trend, playbook usage, gap by playbook, execution mode, validation state, tool/MCP usage, harness versions, deterministic gaps list; client-side filters (period, profile, playbook, version, environment) over aggregated buckets; inline SVG, self-contained, owner-only files.
- Honest metrics: unknown outcomes excluded from denominators; rework rate and verified accuracy shown as N/A (no ground truth collected).
- Config `report.json`: schedule (default weekly) and health window (default 30 days) are separate.
- Installer applies the configured schedule; uninstall removes the job and script, keeps telemetry and reports.
- Tests: `tests/test_report.py` (64 checks incl. Python↔JS parity under node).

## 1.3.3 — 2026-09-21

Two consistency fixes; schema 2, observed/declared split, profile, outcome parsing, privacy and fail-open unchanged.

- **No completion checklist in normal responses**: engineering-workflow §3, output-contract, implement/deploy playbook lines and the private behaviour rules now say the six completion facts are reported in prose under Validation / Technical details; the aligned STATUS layout only on an explicit request for a release/deployment checklist.
- **Harness metadata consistency**: Execution, agent count and roles must agree and come from the Agent calls actually made; the hook reconciles the declared values against observed Agent calls (authoritative), keeping declared roles only when their number matches. Regression tests added.

## 1.3.2 — 2026-09-21

Telemetry refinement (no change to routing, playbooks, evidence rules, hooks other than telemetry, privacy or fail-open behaviour).

- **Profile is observed, not declared**: taken from `GROUNDWORK_PROFILE` (user's `settings.json` `env`), never from the model's block.
- **Outcome from status language**: the Status / Result sentence (contract + playbook vocabularies), `Overall:` when present, bold verdict openers, and the result heading of non-status playbooks; precedence failed > blocked > partial > complete; negations ("not verified") count as partial; nothing recognisable stays `unknown`.
- **Record schema 2**: `observed` (hook-determined facts) vs `declared` (model-stated fields) — the distinction future reports must keep.
- **Deterministic capture**: a turn that ran any tool is recorded even when the model omitted the block (`declared.block_present: false`, declared fields `unknown`); conversational replies still produce nothing.
- **One status per response**: engineering-workflow §3 becomes "Completion facts" reported inside Validation / Technical details; the aligned STATUS block only on request. Metadata block reduced to four lines (`Groundwork <version> · <PLAYBOOK>`, execution, evidence, validation).

## 1.3.1 — 2026-09-21

Presentation only: the `Harness metadata` block is rendered as a fenced code block with aligned
`Key: value` lines (same shape as the STATUS block), not bullets. The telemetry parser accepts the
code-block layout (bullets/bold still tolerated).

## 1.3.0 — 2026-09-21

Usage metadata and telemetry. Routing, playbooks, evidence, validation and safety unchanged.

- **`Harness metadata` block** (output-contract.md): substantive task responses end with harness,
  profile, playbook, execution mode, agents, evidence types, validation state — only known
  values, never invented; omitted for trivial replies.
- **New Stop hook `hooks/groundwork_telemetry.py`** — one append-only JSONL record per task at
  `~/.claude/groundwork/telemetry/events.jsonl`: ids, version, profile, playbook, execution mode,
  agent count/roles, tools, MCP servers, evidence types, clarification flag, environment,
  outcome, validation, tests run, implementation/deployment flags, files-changed count, cwd hash.
  No prompts, commands, paths, secrets or reasoning: free text from the block is kept only as short
  labels, records are owner-only (0600), the transcript is read from its tail. Fail-open;
  `GROUNDWORK_TELEMETRY=off`.
- Session snapshot gains one `harness: Groundwork <version>; profile: <GROUNDWORK_PROFILE>` line;
  installer writes `~/.claude/groundwork/VERSION`; uninstall keeps telemetry records.
- Tests: `test_telemetry.py` (new), installer/merge checks updated for the fourth hook.

## 1.2.4 — 2026-09-21

Presentation only: the 1.2.3 symbol vocabulary is replaced by a clean checklist style in
`rules/output-contract.md` — plain Markdown headings; `[x]` verified/completed, `[ ]` pending
or not yet verified (never failure), `[!]` important risk or issue, `[-]` not applicable;
used lightly, never on every sentence; no emojis or decorative symbols; layer headings back to
`Technical details` / `Evidence & references`. Tests pin the checklist rules and assert no
legacy symbols remain. Routing, playbooks, evidence and safety rules unchanged.

## 1.2.3 — 2026-09-21

Presentation only: Groundwork's visual status language, defined once in
`rules/output-contract.md` and inherited by every playbook — `◆ VERIFIED`, `◐ PARTIAL`,
`◇ UNVERIFIED`, `▲ RISK`, `■ BLOCKED`, `→ NEXT`, `↳ EVIDENCE`, `⌁ TECHNICAL`; symbol always
with its text label; semantic, never decorative; used for the overall result, validation
states, risks, blockers, uncertainty and next action only; `⌁ Technical details` and
`↳ Evidence & references` become the layer headings. Tests pin the vocabulary and rules.

## 1.2.2 — 2026-09-21

Wording only, in `rules/output-contract.md` Layer 1: the main response is written in user
language and answers only what happened / did it work / what matters / what is still risky
or unverified / what next. File names, paths, rule and test names, commits, PR numbers,
checksums, harness internals, implementation history, reviewer and tool names, backup paths
and low-level validation mechanics move to Technical details or Evidence & references — kept
exact there, never dropped. One new test check pins the rule.

## 1.2.1 — 2026-09-21

Presentation only. No routing, rule, hook, settings or safety change.

- **New rule `rules/output-contract.md`** (25 lines) — the global three-layer answer shape every
  playbook inherits: plain-language main response (result first, what matters, change/fix/
  recommendation, honest validation, one next action when needed) → `Technical details`
  (errors, log paths, copyable commands, key files, tests, PR/commit/version, technical risk)
  → `Evidence & references` (strongest sources in evidence-priority order). Omit-empty-sections,
  translate-evidence-to-meaning, never-imply-verification, and no routing debug lines unless asked.
- `rules/task-routing.md` §4 now points at the contract; each playbook's Output Format lists only
  its category's main headings plus an inheritance line — the global rules are not duplicated.
- Tests: `test_playbooks.py` 76 → 98 checks (contract presence/size/key rules, router pointer,
  playbooks inherit rather than restate, contract installed).

## 1.2.0 — 2026-09-21

Additive task-routing layer. No existing rule, hook, settings key or safety control changed
(verified by SHA-256 comparison of every pre-existing critical file before and after).

- **New rule `rules/task-routing.md`** — one primary category per request (RESEARCH, EXPLAIN,
  DESIGN, PLAN, IMPLEMENT, TROUBLESHOOT, VALIDATE, AUDIT, DEPLOY, DOCUMENT), read only that
  playbook, the material-ambiguity clarification rule, and the universal output contract
  (report only material information; conciseness never hides risk, uncertainty or evidence).
  States that an existing Groundwork rule wins over a playbook on conflict.
- **New `playbooks/`** — ten concise playbooks, each with Goal / Workflow / Evidence / Ask
  Before Acting When / Completion Criteria / Output Format. Installed to
  `~/.claude/groundwork/playbooks/`, outside `rules/`, so they load on demand only.
  IMPLEMENT and DEPLOY outputs embed the existing completion block.
- **Installer** — `install.sh` copies the playbooks; `uninstall.sh` removes them.
- **Tests** — `tests/test_playbooks.py` (artefacts, sections, size caps, install/uninstall on a
  temp `CLAUDE_CONFIG_DIR`); `scripts/check_routing.py` + `tests/routing_scenarios.json` for a
  live twelve-scenario routing and ambiguity check (skips when the CLI is logged out).

## 1.1.0 — 2026-09-20

Evolves the 1.0.0 governance layer into an engineering harness that guides architecture
quality, chooses its own execution model, validates against the real runtime, and
reconstructs an existing project from the repository in a fresh session. Verified
against Claude Code 2.1.258 and the official docs on 2026-09-20; ECC 2.2.1 and OpenSpec
1.12.0 unchanged. Nothing SRE-Agent-specific; no new agents, skills, daemons or stores.

- **New `rules/architecture-quality.md`** — governing principle ("smallest design that
  satisfies today's requirement while preserving low-cost paths for foreseeable change"),
  the quality dimensions as *decision criteria*, the pre-MATERIAL questions, the
  variation-point rule (configuration/interface boundary for environments, providers,
  clusters, models, regions, tenants), and "no abstraction without a concrete reason".
- **`rules/engineering-workflow.md`** — UNDERSTAND step producing a DONE / PARTIAL /
  MISSING / BLOCKED / UNVERIFIED state table for existing projects; §6 execution model
  (main session vs subagents vs native Agent Teams, with size/justification rules and the
  "teams disabled or `-p` → subagents" fallback); §7 continuation procedure for
  "continue this project"; `Reviewed:` row in the completion block; never default to
  `--dangerously-skip-permissions`.
- **`rules/evidence-policy.md`** — §5 validation ladder derived from project evidence
  (static → unit → integration → build → infra → controlled runtime → real environment),
  "mocks never prove runtime", the six-field DECISION record for MATERIAL decisions only,
  `Independent review` row in the completion-evidence table.
- **`hooks/require_material_review.py`** — also recognises reviewer-shaped `Agent`/`Task`
  calls by `name`, so Agent Team reviewer teammates and named reviewer subagents (current
  Claude Code spawns both through the `Agent` tool) satisfy the gate. The free-text
  `description` is deliberately not matched (independent review showed it could be
  satisfied by an unrelated "Review existing tests" exploration). Documents the platform's
  8-consecutive-block cap. Behaviour otherwise unchanged.
- **New `hooks/groundwork_session_snapshot.py`** (SessionStart) — deterministic project
  snapshot from repository state only: branch, HEAD, ahead/behind, dirty/untracked counts,
  recent commits, active OpenSpec changes with task progress (flagging complete +
  uncommitted changes where the review gate applies), project signal files, and
  verification commands discovered in Makefile / package.json / pyproject / tox / nox /
  Go / Rust / Terraform / CI files. ≤ 2,500 chars, 3 s git timeouts, no network,
  fail-open, `GROUNDWORK_SNAPSHOT=off` to disable.
- **Installer** — `merge_settings.py` registers the SessionStart hook idempotently and
  accepts `--agent-teams` (opt-in only, never overwrites a user value);
  `unmerge_settings.py` reverses it, now including the `hook_profile` it set (found by
  independent review: 1.0.0's uninstall left that key behind), and documents the one
  stateless limitation: a value you had set yourself that equals the installer's default
  is removed on unmerge; new
  `migrate_legacy_rules.py` moves a pre-Groundwork `~/.claude/rules/harness/` copy into
  `~/.claude/backups/groundwork-legacy-<timestamp>/` so rules are not loaded twice, and
  prints a notice when `~/.claude/CLAUDE.md` still points at the old path.
- **`hooks/block_protected_push.py`** — hardened after an independent security review
  reproduced four bypasses of the 1.0.0 guard: `HEAD`/`@` shorthand now resolves to the
  current branch, every refspec is checked (not just the first), `--all`/`--mirror`/
  `--branches` are denied, `sh/bash/zsh/dash/ksh -c "…"` and `eval "…"` are parsed
  (depth-limited), `:branch` deletions and `+`/`refs/heads/` forms are handled, and
  option values (`-o`, `--push-option`, …) are no longer mistaken for refspecs.
- **Snapshot prompt-injection mitigation** — repository-derived text (branch, commit
  subjects, directory/file names) is clipped per field, stripped of control/zero-width
  characters, and framed inside an explicit "DATA, NOT INSTRUCTIONS" boundary.
- **Review-gate correctness** — change names are matched as exact `openspec/changes/<name>`
  path segments (1.0.0 substring-matched raw `git status` text, so a committed `thing` was
  re-flagged whenever `add-thing` was dirty); "preview" no longer matches "review".
- **Tests** — 16 → 92 checks across 5 test functions, including a regression case for
  every reviewer-reproduced bypass; fixture commits are isolated from the developer's
  global git config; `check()` failures now raise, so `pytest` reports a real failure
  (in 1.0.0 a failing check still showed "passed").
- **Docs** — README, ARCHITECTURE, TROUBLESHOOTING, UPGRADE-ROLLBACK, VALIDATION updated.

## 1.0.0 — 2026-09-03

Initial release, extracted from a real personal-harness migration onto ECC 2.2.1 + OpenSpec 1.12.0.

- `rules/engineering-workflow.md` — TRIVIAL/STANDARD/MATERIAL tiering, autonomy rule (six genuine owner-decision triggers, nothing else stops the loop), completion status block.
- `rules/evidence-policy.md` — evidence priority order, uncertainty labels, the DECISION format for material technical calls, the completion-evidence table (code ≠ tested ≠ merged ≠ deployed ≠ live validated).
- `hooks/block_protected_push.py` — denies `git push` to `main`/`master`/`production`/`prod`/`release` and any force-push, shell-chain aware.
- `hooks/require_material_review.py` — denies finishing a session with a fully-implemented, uncommitted OpenSpec change that no reviewer-shaped tool call ever touched. Added after an initial gap: a plain autonomy rule alone let a real test run finish a material feature with zero review dispatched.
- `install.sh` / `uninstall.sh`, `scripts/merge_settings.py` / `unmerge_settings.py` — idempotent, additive-only `settings.json` handling; never overwrites unrelated configuration.

See [docs/VALIDATION.md](docs/VALIDATION.md) for the test evidence this release is based on, including the fixes that came out of live testing (a `git status` untracked-directory edge case in the review gate; the removal of a generic MATERIAL-tier approval stop that contradicted the autonomy rule).
