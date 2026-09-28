# Groundwork 2.1.0 — release report (merged to main)

Originally prepared, as a release-candidate report, at the end of the autonomous implementation authorized by the "Groundwork 2.1 — Context, Capabilities, Routines & UX" brief, for owner review before any merge decision. That review is now complete and the owner has made the merge decision described below; the rest of this report is kept as the historical record of what was reviewed, not rewritten. It duplicates nothing from `docs/VALIDATION.md`, `openspec/changes/groundwork-2.1-context-routines-ux/design.md`, or that change's `tasks.md` — it points at them — except where a number needed to be re-verified fresh for this report (each such number is marked with the exact command run). Structure follows the brief's own required sections.

**Release status: MERGED to `main`** via PR [#22](https://github.com/AshminPy/groundwork/pull/22) (merge commit `e3d4b4f40564c828ad7416458038858c40fbf1f7`), by explicit owner decision after 4 rounds of independent review (§11), Must-fix: 0. **Still NOT tagged and NOT published as a GitHub release** — that narrower constraint remains in force; only the "never merge to main" constraint has been explicitly lifted by the owner.

---

## 1. Release identity

- **Branch**: `claude/groundwork-2.1-context-routines-ux` (merged; `main` is now at the merge commit below)
- **PR head (final, merged)**: `ae1fa1d249789d2f607685aed6afe4ba8e0d1739`
- **Merge commit on `main`**: `e3d4b4f40564c828ad7416458038858c40fbf1f7`
- **Base**: `origin/main` at `73d5d13ffaa0c5a5755b77f88f7f2cb0b07e798c` (the already-merged Groundwork 2.0.0)
- **Commits on top of base**: 6 — `6913008` (the full 2.1 implementation), `b7a80a3` (round-1 independent-review fixes), `cae2553` (release-candidate report + tasks.md close-out), `83295b7` (Phase 13: the Routine Configuration Contract, an owner requirement raised during PR #22 review — see §7a below), `14f53ad` (round-3 independent-review fixes for Phase 13), `ae1fa1d` (round-4 nice-to-have fixes + this report's own finalization)
- **Files changed vs the pre-2.1 base**: 28 (`git diff --name-only 73d5d13..ae1fa1d | wc -l`), 15 newly added
- **Diff summary**: `git diff --stat 73d5d13..ae1fa1d` → 28 files changed, 4215 insertions(+), 42 deletions(-)
- **PR**: [#22](https://github.com/AshminPy/groundwork/pull/22), **merged** (closed, merged: true) — **still not tagged, not published as a GitHub release**
- **OpenSpec change**: `openspec/changes/groundwork-2.1-context-routines-ux/` — `proposal.md`, `design.md` (§A–§L plus §D.2, added for Phase 13), `tasks.md` (78/78 tasks checked `[x]`), 4 capability spec deltas (`routines`, `dependency-pinning`, plus `ADDED` requirements folded into the existing `onboarding` and `task-routing` baseline capabilities)
- PR #21 (a separate, unrelated documentation-only change, on a different branch) was never touched by any of this work, per the owner's standing instruction.

## 2. Scope and status

All 13 phases in `tasks.md` are complete or explicitly, honestly deferred:

| Phase | What | Status |
|---|---|---|
| 0 | OpenSpec scaffold | Complete |
| 1 | Context-engineering audit | Complete |
| 2 | Capability resolution model | Complete |
| 3 | MCP/integration capability matrix | Complete |
| 4 | Curated optional skills evaluation | Complete |
| 5 | Routines subsystem | Complete |
| 6 | Browser/Chrome governed execution policy | Complete |
| 7 | `setup.sh` capability configurator | Complete (1 real bug found+fixed, see §9) |
| 8 | `groundwork doctor`/`configure`/`routines` commands | Complete (1 real bug found+fixed, see §9) |
| 9 | ECC pinning | Complete except upgrade-cycle re-proof (§12, known gap) |
| 10 | Testing | Complete |
| 11 | Live validation | Complete |
| 12 | Independent review + docs + this report | Complete |
| 13 | Routine configuration contract (owner requirement, raised during PR #22 review) | Complete — 2 real MUST FIX bugs found and fixed across two further independent-review rounds, see §7a and §11 |

## 3. Architecture — what changed, what didn't

Groundwork's ownership model is unchanged in kind: Groundwork owns policy (routing, evidence, safety, continuity, completion truth), never execution capability. OpenSpec still owns WHAT/WHY; ECC still owns HOW (agents/skills); Claude Code still owns runtime primitives; the task's own environment still owns MCP/CLI/credentials. **Unchanged, verbatim**: 10 playbooks, 4 dynamic builder personas (still dynamic, no permanent agent files), automatic main/subagent/Agent-Team selection, the session-snapshot/investigation-continuity mechanism, the independent-review gate, the push guard, telemetry's schema and privacy discipline, the evidence taxonomy, OpenSpec's and ECC's roles.

**What 2.1 adds** — four new policy/mechanism surfaces, each with exactly one owner (`docs/ARCHITECTURE.md`'s capability-ownership table, extended with 5 new rows):
1. **Capability resolution** (`rules/engineering-workflow.md` §6a) — judgment guidance for *which tool* serves a task, layered on top of (never replacing) the existing tier/evidence/authorization rules.
2. **Routines** (`scripts/groundwork_routines.py`) — a new execution mode (scheduled, headless, non-interactive) for the same governance the interactive session already has, not a second rule system.
3. **Capability configuration** (`scripts/groundwork_config.py`) — one small, human-readable, no-secrets config file.
4. **Dependency pinning** (`install.sh`) — ECC now installs pinned rather than floating `main`.

No new hooks, no new playbooks, no new rule files beyond the two extended, no new persistent daemon, no new third-party dependency (Groundwork remains 100% Python-stdlib across every script — confirmed by grep, no `requirements.txt`/`pyproject.toml` anywhere in the repo).

## 4. Context engineering

Full detail: `docs/CONTEXT-ENGINEERING.md` (new). Summary of the classification every context source received:

| Class | Examples | Notes |
|---|---|---|
| Always-loaded | 5 rule files (~290 lines total, +21 lines this pass for §6a and task-routing §4) | Unchanged budget discipline |
| Selectively-loaded | 10 playbooks (1838–3589 bytes each, capped at 4000) | Unchanged |
| Lazy-deferred | MCP tool schemas (native Tool Search, observed live in this session's own deferred-tool listing), skill bodies (progressive disclosure — description-only until invoked) | Native mechanism, nothing built |
| Isolated | Subagent transcripts (only the final report crosses back — directly exercised by this very report's two independent-review dispatches) | Unchanged, and the mechanism this report's own evidence trail depends on |
| Persisted | Session snapshot (≤2500 chars), investigation-continuity file (≤800 chars display), Routines' own telemetry (`routines.jsonl`, structured fields only) | Routines telemetry is new, same discipline |
| Reconstructed | Git/OpenSpec state at session start, re-derived every session | Unchanged |
| Unnecessary/duplicated | None found (§ of `CONTEXT-ENGINEERING.md` states this explicitly, not silently omitted) | |

**Conclusion, unchanged from the audit**: every 2.1 capability composes native Claude Code mechanisms (Tool Search, progressive-disclosure skills, subagent isolation, headless `claude -p`) rather than building custom context infrastructure. No token-usage number in this report or its linked docs is fabricated — where the platform doesn't expose reliable measurement (e.g., a live activity view), that's stated as a limitation (§12), not worked around with an invented number.

## 5. Skills

No new skill was installed or bundled by this change. Evaluated per the brief's own instruction (full detail: `docs/FUTURE-SCOPE.md` §13):

| Skill | Source | Trust | Decision | Why |
|---|---|---|---|---|
| `teach` | github.com/mattpocock/skills, MIT | Community, small, single-purpose | Recommended, optional | Already lazy (`disable-model-invocation: true`, user-invoked via `/teach`); no context cost unless explicitly summoned; owns *technique*, Groundwork still owns routing/evidence |
| Task Observer | rebelytics/one-skill-to-rule-them-all, CC BY 4.0 | Community | Declined | Every credible implementation is near-always-on; conflicts with the brief's own strict no-raw-capture privacy requirement (no raw prompts/source/credentials/transcripts) |
| `wshobson/agents` | 40k★, MIT, native plugin marketplace | Community, large | Documented candidate only, **not adopted** | Per the owner's explicit instruction; deeper SRE/CloudOps coverage than ECC but a real supply-chain decision requiring its own evaluation, not bundled into this pass |
| security-review, architecture-review, doc-gen, diagram | Existing (from `groundwork-2-enterprise-sre`) | N/A | Confirmed already present, not duplicated | This pass checked for overlap before proposing anything new — none found needing a new capability |

## 6. MCP/integrations

Documentation only — `docs/INTEGRATIONS.md` (new). No MCP server, CLI tool, or credential was installed, configured, or wired by this change; this sandbox has no credentials for any of these systems to wire even if it wanted to. The capability matrix (Domain / Preferred access / Trust level / Read-Write / Auth model / Context strategy) covers GitHub, Spacelift, Jira, Confluence, AWS, GCP, Kubernetes, Terraform, and observability (Grafana/Datadog/PagerDuty/Sentry/Prometheus) — each researched live (2026-09-28) against current vendor/official sources, not assumed from training data. **Slack is deliberately excluded**, per explicit instruction. Validation status for every row: **NOT WIRED — documentation only**, stated as such, not implied otherwise.

## 7. Routines

Full detail: `docs/ROUTINES.md` (new). Framework: `scripts/groundwork_routines.py`, one generic mechanism (name + prompt-template function + `mutates` flag + default schedule), not six bespoke scripts.

| Routine | Mutates | Schedule | Inputs | Evidence sources | Safety | Failure behavior | Validation status |
|---|---|---|---|---|---|---|---|
| `jira_eod` | Yes | daily | offline-work text (optional) | git/PR/OpenSpec/investigation-continuity/tests | dry-run default, read-back-before-VERIFIED, never widens Jira write access beyond what's already configured | Reports `failed`/`BLOCKED` with reason, never invents a post | **Live-verified** (dry-run, this session) |
| `news` | No | daily | topic list | web search (authoritative sources only) | N/A (read-only) | No filler when nothing material | **Live-verified** (§11) via `work_digest`'s identical mechanism — not independently re-run for `news` specifically this pass |
| `weekly_status` | No | weekly | none | git/PR/OpenSpec/tests/reviews | N/A | States unknown rather than guessing | Mechanism-verified, not separately live-run |
| `pr_followup` | No | daily | none | `gh`/repo equivalent | N/A | Merged ≠ deployed, stated explicitly in the prompt | Mechanism-verified, not separately live-run |
| `work_digest` | No | daily | none | git/PR/OpenSpec/investigation state | N/A | No task from a weak signal | **Live-verified** — real `claude -p` run, exit 0, 15.8s, structured telemetry recorded (0600, no raw output) |
| `doc_drift` | No | weekly | none | code vs docs | Never auto-rewrites docs | Reports drift, doesn't fix it | Mechanism-verified, not separately live-run |

Every routine shares the same safety contract (`build_command()`, tested for all 6 × both dry-run states): never `--dangerously-skip-permissions`, never `--bare`, always `--permission-mode dontAsk --permission-prompts none` plus an explicit `--allowedTools` allowlist. Scheduling reuses `groundwork_report.py`'s existing launchd/cron pattern — confirmed by direct code reading, not a new scheduler. Off-switches (`GROUNDWORK_ROUTINES[_<NAME>]=off`) confirmed to prevent any subprocess spawn, even with `claude` unreachable on `PATH`.

## 7a. Routine configuration contract — an owner requirement raised during PR #22 review

After the table above shipped as the initial release candidate (commit `6913008`, reviewed and fixed at `b7a80a3`), the owner reviewed the PR again and found it did not actually satisfy "configure once, run automatically": the framework ran, but `READ_ONLY_TOOLS`/`JIRA_LIVE_TOOLS` were byte-identical (so `pr_followup` could never reach `gh`/GitHub MCP and a "live" `jira_eod` could never actually post), and no identity/scope/access was ever collected or persisted, so a routine would have had to re-derive "which Jira," "whose PRs," "which repositories" from nothing on every run. This was incorporated into the *same* OpenSpec change (`tasks.md` Phase 13), not a separate one, per the owner's explicit instruction not to create another one.

**What shipped** (full detail: `design.md` §D.2, `docs/ROUTINES.md`, `docs/VALIDATION.md`'s "Routine configuration contract" entry): `config.json`'s `routines` entries grew from `{enabled, schedule}` to a full per-routine schema (site/identity/access/scope/posting for `jira_eod`; identity/access/scope-filters for `pr_followup`; topics for `news`; repository/integration scope for `weekly_status`/`work_digest`/`doc_drift`), collected once by a progressive `setup.sh` wizard that only asks about routines actually enabled. `_capabilities_for()` now builds each routine's real `--allowedTools` list from routine + configured access mechanism + configured scope + configured mutation permission — never a flat global set. A routine with unconfigured required access is `BLOCKED` before any `claude` subprocess is spawned. Every routine prompt now ends with a required, semantic `ROUTINE RESULT` block (`COMPLETE|PARTIAL|BLOCKED|FAILED|SKIPPED`) — a clean exit code is never alone treated as success. The routine's actual useful output (digest/report/status) is now stored separately from telemetry, under `~/.claude/groundwork/routines/results/<name>/`, retrievable via `groundwork_routines.py latest <name>` / `setup.sh --routines <name>`, bounded to the 10 most recent runs.

**Two real MUST FIX bugs found and fixed across this sub-phase's own two further independent-review rounds** (full detail: §11 below, and `docs/VALIDATION.md`): (1) a `"True"` vs `"true"` string-comparison mismatch silently defeated the profile-driven wizard trigger on both places it's actually invoked from, so a freshly profile-configured install left every routine unconfigured despite being marked enabled; (2) `weekly_status`/`work_digest`'s Jira cross-reference path could inherit `jira_eod`'s own write-capable Jira wildcard despite being declared `mutates: False`, violating this same phase's own least-privilege requirement. Both fixed at the code (not papered over in docs), covered by new regression tests independently confirmed to fail against the pre-fix code, and independently re-confirmed fixed by a fourth review round. **Final verdict for this sub-phase: `approve`, `Must-fix: 0`.**

**Known, honestly disclosed simplifications** (not fixed this pass, no security impact): `pr_followup`'s five scope filters default to all-true and are hand-editable in `config.json` but not individually toggleable in the wizard; `weekly_status.jira_projects` is a real, coded, documented field that the wizard never actually collects — reachable only by hand-editing `config.json` (found by the fourth review round, disclosed in `design.md` §D.2 immediately rather than left for a future reader to rediscover).

## 8. UX — setup, profiles, config, doctor

`setup.sh` gained one optional fourth question (capability/Routines selection, default **skip** — the unmodified `./setup.sh` one-command path installs exactly the same core as before) and three new read-only/low-risk modes:
- `--doctor` — extends `--verify` with Capabilities/Routines status; now degrades gracefully (INVALID row, not a crash) on a corrupted `config.json` (§9).
- `--configure` — revisit selection only, no backup, no reinstall.
- `--routines` — list configured Routines and last-run status.

8 profiles (SRE/CloudOps, Platform Engineering, DevOps, Software Engineering, Cloud Architecture, Security Engineering, Minimal, Custom) — a starting point, never a forced install; every capability and Routine stays individually toggleable in `config.json`. **No new terminal-UI dependency**: Groundwork stays stdlib-only; the existing HTML dashboard is unchanged and remains the presentation layer. A live activity view was researched and deferred (§12) rather than faked.

## 9. Tests — exact commands and results

```
$ python3 -m pytest tests -q
.............................................                            [100%]
45 passed in 47.96s

$ python3 tests/test_hooks.py               → 131 passed, 0 failed
$ python3 tests/test_playbooks.py           → 143 passed, 0 failed
$ python3 tests/test_report.py              → 67 passed, 0 failed
$ python3 tests/test_setup.py               → 146 passed, 0 failed
$ python3 tests/test_telemetry.py           → 81 passed, 0 failed
$ python3 tests/test_groundwork_config.py   → 147 passed, 0 failed   (new in this pass)
$ python3 tests/test_groundwork_routines.py → 98 passed, 0 failed    (new in this pass)

$ openspec validate groundwork-2.1-context-routines-ux --strict
Change 'groundwork-2.1-context-routines-ux' is valid

$ openspec validate --changes
✓ change/groundwork-2-enterprise-sre
✓ change/groundwork-2.1-context-routines-ux
✓ change/intelligent-engineering-harness
Totals: 3 passed, 0 failed (3 items)

$ bash -n setup.sh && bash -n install.sh && bash -n uninstall.sh
(all clean)
```

813 total deterministic checks across 7 files (131+143+67+146+81+147+98), 0 failed, 45 test functions. Two new test files added this pass (`test_groundwork_config.py`, `test_groundwork_routines.py`); every existing file extended, not rewritten; the full pre-2.1 suite (16 test functions, 485+ checks) still passes unmodified in kind. `test_setup.py` and `test_groundwork_routines.py` each grew again during the Routine Configuration Contract sub-phase (§7a): two new regression tests (`test_profile_driven_wizard_fires_on_both_entry_points`, `test_non_mutating_routines_never_inherit_jiras_write_capable_wildcard`) target exactly the blind spots that let those two bugs ship, and both were independently confirmed — by temporarily reverting the fix and re-running — to actually fail against the pre-fix code, not just pass trivially against the fix.

## 10. Runtime validation — exact scenarios and results

All performed live in this sandbox against the real, installed Claude Code CLI (2.1.284) and real `bash`/`python3` — never simulated. Full detail and exact commands: `docs/VALIDATION.md`'s "Groundwork 2.1.0" entry.

1. **Fresh non-interactive install with `--capability-profile sre-cloudops`** → `config.json` written correctly under the target `CLAUDE_CONFIG_DIR`, `jira_eod`/`news`/`pr_followup`/`weekly_status`/`work_digest` all enabled, `--doctor` reports them all correctly.
2. **`--doctor` against a deliberately broken core install** (playbooks dir removed) → Capabilities/Routines section still prints (this was Bug 2, fixed and confirmed by a second independent reviewer's old-vs-new reproduction, §11).
3. **`--doctor` against a hand-corrupted `config.json`** → degrades to one `Capabilities INVALID` row, still reaches `-- Routines --`, exits 0 (this was independent-review MUST FIX 1, fixed and confirmed).
4. **Live routine execution**: `work_digest` via real `claude -p` → exit 0, 15.8s, structured telemetry recorded with `0600` permissions, zero raw output persisted (confirmed by reading the file directly). `jira_eod --dry-run --offline-work "..."` → exit 0, ~15.0s, dry-run and offline-work-folding paths both exercised.
5. **ECC pinning**: `--doctor` reports `plugin ecc@ecc 2.2.1 (pinned to v2.2.1)` on a matching stub, and the differs-from-pin message on a mismatched one.
6. **Uninstall after a pinned, capability-configured install**: `config.json` removed, every scheduled routine plist unscheduled — confirmed via a real launchd-plist write/read cycle in a test-scoped `LaunchAgents` directory.
7. **Version-bump sanity check**: fresh install after the CHANGELOG 2.1.0 entry stamps `VERSION` as `2.1.0` (was `2.0.0` through earlier tests in this same session, confirming `install.sh`'s CHANGELOG-derived version stamping works end-to-end).
8. **Profile-driven routine wizard, live, both entry points** (Routine Configuration Contract sub-phase, §7a): a fresh, fully interactive first-time install piping profile/teams/schedule answers plus "yes, pick a profile" → sre-cloudops → full wizard answers for `jira_eod`/`pr_followup`/`news`/`weekly_status`/`work_digest`, and separately `--configure` → "Change capability profile" on an already-installed box with no profile yet — both inspected via the actual `config.json` file contents afterward (not the non-echoing piped-stdin transcript): every field (Jira site/identity/access/MCP server/schedule, GitHub identity/access, news topics, schedule times, `work_digest`'s auto-derived `use_github`/`use_jira`) landed exactly as entered on both paths.
9. **Non-mutating routines' capability set, live, against a real live-posting `jira_eod` configuration**: with `jira_eod` configured `access=jira_mcp, posting=automatic` (the routine legitimately entitled to the Jira wildcard), `_capabilities_for()` was invoked directly for `weekly_status`/`work_digest` with Jira cross-referencing enabled — the returned tool list contained no Jira-shaped tool at all (no `mcp__atlassian__*`, no `Bash(jira *)`, no browser tool) across all three Jira access mechanisms, while `jira_eod` itself, same config, correctly still received `mcp__atlassian__*`.

## 11. Independent review — full history

Two rounds, both fresh-context background subagents with no access to this session's own reasoning, per the project's "do not self-certify" convention.

**Round 1** — full adversarial review of the entire diff vs `origin/main`. Returned `changes-required`, 2 MUST FIX:
1. The doctor fix in Phase 8 was incomplete: `verify_capabilities()`'s inline Python had no fail-open guard, so a corrupt `config.json` crashed the *entire* `--doctor` command under `set -euo pipefail` — worse than the bug it was meant to fix (silence, not just a dropped section).
2. `docs/ARCHITECTURE.md`/`README.md` still asserted ECC "installs unpinned from GitHub `main`" elsewhere in files this change otherwise edits, self-contradicting the new pinning content.

Plus 3 NICE TO HAVE findings (all fixed): `uninstall.sh`'s hardcoded routine-name list (now derived from the `ROUTINES` registry), an unpinned `JIRA_LIVE_TOOLS == READ_ONLY_TOOLS` safety claim (now a direct test), and an overstated "never contains credentials" guarantee (reworded to what's actually true).

Both MUST FIX findings were fixed at the root (not worked around) and committed as `b7a80a3`.

**Round 2** — narrowly-scoped confirmation review, per the same project convention already used once in 2.0 (Phase 4/5: "a second, narrowly-scoped independent review verified both MUST FIX fixes by direct old-vs-new reproduction"). Extracted the actual pre-fix `setup.sh` via `git show HEAD^:setup.sh`, ran both old and new against the identical corrupted-`config.json` scenario side by side, confirmed the old script dies silently while the new one degrades correctly; grepped both doc files for every remaining "unpinned" occurrence and confirmed each is inside a clearly-dated historical clause, not a live claim. Independently re-ran the full test suite and `openspec validate --strict`.

**Verdict after round 2: `approve`, `Must-fix: 0`.** This closed out the initial release candidate (commit `b7a80a3`) — the Routine Configuration Contract sub-phase below (§7a) was raised in a *separate*, later owner review of that already-approved candidate, not a continuation of rounds 1-2.

**Round 3** — a fresh adversarial reviewer dispatched specifically against the Routine Configuration Contract sub-phase (§7a, commit `83295b7`), with instructions to live-reproduce rather than infer from reading. Returned `changes-required`, 3 MUST FIX (one a direct documentation consequence of the other two, so two underlying bugs): (1) `setup.sh` compared `cfg_get`'s lowercase JSON boolean output against the capitalized string `"True"` in 12 places, silently defeating the profile-driven per-routine wizard trigger on both paths that call it — live-reproduced by piping a full profile-selection-plus-answers sequence into `--configure` and finding zero questions actually took effect; (2) `_capabilities_for()`'s `weekly_status`/`work_digest` branch could grant the same unrestricted Jira MCP wildcard `jira_eod` gets for live posting to routines declared `mutates: False`, violating this sub-phase's own least-privilege SHALL requirement; (3) `docs/ROUTINES.md`/`design.md` claims falsified by (1) and (2). Both underlying bugs were fixed at the code (a new `cfg_get_bool()` helper; removing the Jira-tool grant from the non-mutating reuse path entirely, in favor of reading `jira_eod`'s own stored result file), backed by two new regression tests, and committed as `14f53ad`.

**Round 4** — a second fresh reviewer, with no access to the fixing session's own reasoning, dispatched specifically to confirm the round-3 fixes rather than trust the commit's own claims. Independently re-derived the root cause of bug (1) by reading `groundwork_config.py`'s `get` CLI directly; live-reproduced both fixed entry points itself in an independently-built sandbox; ran a differential test (checked out the pre-fix commit into a worktree, copied over only the two new test files, confirmed both fail hard and specifically against the old code — not vacuous tests); independently invoked `_capabilities_for()` across all three Jira access mechanisms for both non-mutating routines and confirmed no Jira-shaped tool is ever granted; grepped the whole repository for any stale reference to the old grant pattern (none found); independently re-ran the full suite (45 passed) and `openspec validate --strict` (valid). **Verdict: `approve`, `Must-fix: 0`.** 3 NICE TO HAVE findings, all closed in the same pass (not deferred): an undisclosed `weekly_status.jira_projects` wizard gap (now disclosed in `design.md` §D.2), a dead `indent` parameter on `_jira_evidence_note()` (removed), and a cosmetic stray blank line in two routine prompts when no Jira cross-reference is configured (fixed).

**Overall final verdict across all four rounds: `approve`, `Must-fix: 0`.**

Full transcripts of all four rounds' findings: `docs/VALIDATION.md`'s "Independent review" and "Fresh confirmation review of the Bug 3/Bug 4 fixes" subsections.

## 12. Known limitations and deferred items (honestly carried forward, not fixed)

**Known limitations:**
- **ECC upgrade-cycle re-proof not exercisable** (`tasks.md` 9.7) — confirming `claude plugin update ecc@ecc` stays within the pinned ref rather than jumping to a newer, untested version needs live network access to the real plugin marketplace, unavailable in this sandbox. Documented, not claimed as tested.
- **No live activity view** (§13 of `design.md`) — no reliable Claude Code lifecycle-event source was found to build one on honestly; not faked.
- **Prompt-content quality for `news`/`weekly_status`/`pr_followup`/`doc_drift`** was mechanism-verified (same `build_command()`/`run_routine()` path as the live-run `work_digest`) but not independently live-run per routine this pass — a model-behavior property of the prompt text, not the framework, and each shares the identical, already-tested invocation mechanism.
- **MCP/CLI integrations are documentation only** — `docs/INTEGRATIONS.md` is researched guidance, not a wired, credentialed, validated connection to any of the systems it covers.
- **`weekly_status.jira_projects` is not collected by the interactive wizard** (found by round 4, §11) — the field is real, coded, and documented, but only reachable by hand-editing `config.json`; `work_digest.use_jira` (the analogous field on the other routine) *is* auto-derived by the wizard. No security impact — the gap only means the routine's prompt never mentions Jira project scoping, never a broader capability grant.

**Deferred items, with reasons** (all in `docs/FUTURE-SCOPE.md` §13 and `design.md`):
- Task Observer — privacy-requirement conflict (near-always-on implementations vs. the brief's own strict no-raw-capture rule).
- Six further routine candidates (cert/PKI expiry, dependency advisories, infra drift, cost anomaly, stale-RCA follow-up, release readiness) — scored, not built; six real, tested routines was the right scope for one release.
- `wshobson/agents` adoption — candidate only, per explicit instruction not to auto-adopt.
- A new terminal-UI dependency — Groundwork stays stdlib-only; no evidence justified the first-ever third-party dependency.

## 13. Acceptance-standard walkthroughs

The brief's own two end-to-end UX examples, walked through against what actually shipped:

**"Investigate why this GKE deployment is failing and fix it."** Capability resolution (§6a) routes this through the existing TROUBLESHOOT playbook unchanged — repository-understanding discovery, evidence-first investigation, then the resolution order: repo's own tooling first (e.g. a `Makefile`/deploy script), then Claude Code native (Bash/kubectl if configured), then a trusted already-installed skill, then a trusted already-configured MCP/CLI for GKE/Kubernetes (per `docs/INTEGRATIONS.md`'s guidance — nothing auto-installed), then browser only if nothing structured exists. The user never names a playbook, a persona, or an MCP — routing, evidence discipline, and capability choice all resolve from the request itself, exactly as before 2.1; 2.1 only made the *tool-choice* step (repo → native → skill → MCP/CLI → browser → user) into explicit rule text instead of implicit judgment.

**"Teach me how this Terraform module works."** Routes through EXPLAIN's existing teach/learn capability (from 2.0); the optional `teach` skill (§5 above), if the user has it installed, adds pedagogical technique without taking over routing or evidence — Groundwork still owns *what* gets explained and from what evidence, the skill only owns *how* it's taught. No change to this flow was required by 2.1; it was already the target architecture, and this pass's capability-resolution rule text formalizes the "does a skill already installed" check as an explicit early step rather than an implicit one.

Neither flow requires the user to know a playbook name, a persona name, a skill name, an MCP name, an OpenSpec command, or when review/validation fires — consistent with the brief's own stated goal.

---

*Every figure in this report was re-verified by running the underlying command at report time (§9–§10), not recalled from memory. See `docs/VALIDATION.md`, `openspec/changes/groundwork-2.1-context-routines-ux/design.md` and `tasks.md` for full supporting detail.*
