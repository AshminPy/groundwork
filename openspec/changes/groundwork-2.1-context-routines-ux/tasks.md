## Phase 0 — OpenSpec scaffold
- [x] 0.1 Write `proposal.md` (why, what changes, what doesn't, impact)
- [x] 0.2 Write `design.md` (§A–§L: context engineering, capability resolution, native-scheduling research, Routines, MCP strategy, curated skills, setup config format, doctor/configure/routines, terminal UX, live-activity deferral, ECC pinning, deliberately-not-built summary)
- [x] 0.3 Write this `tasks.md`
- [x] 0.4 Write delta specs for every capability this change actually adds or modifies (`specs/routines/`, `specs/dependency-pinning/`, plus ADDED requirements folded into the existing `onboarding` and `task-routing` baseline capabilities) — new capability names chosen instead of `MODIFIED` deltas against the still-unarchived `groundwork-2-enterprise-sre` change's own specs (ecc-capability-policy, etc.), since OpenSpec deltas validate against the archived baseline in `openspec/specs/`, not against another open change
- [x] 0.5 Fix a real proposal/design drift found while writing this scaffold: both `proposal.md` item 7 and two lines in `design.md` §D still described the capability-config file as YAML (`config.yaml`), left over from the brief's own illustrative example, after the actual implementation (§G, already built and tested) chose JSON (`config.json`) — corrected both files to match what was actually shipped
- [x] 0.6 `openspec validate groundwork-2.1-context-routines-ux --strict` passes (zero errors, zero warnings)

## Phase 1 — Context-engineering audit
- [x] 1.1 Inventory every current context source (rules, playbooks, session snapshot, investigation-continuity file, ECC, MCP, skills, deferred tools, subagents, telemetry, git state, CLAUDE.md) and classify each as always-loaded / selectively-loaded / lazy-deferred / isolated / persisted / reconstructed / unnecessary-duplicated
- [x] 1.2 Confirm native Claude Code lazy-loading mechanisms directly (not from memory): Tool Search (observed live in this session's own deferred-tool listing), progressive-disclosure skills (description-only until invoked), MCP tool-schema deferral, subagent isolation (only the final report crosses back)
- [x] 1.3 Write `docs/CONTEXT-ENGINEERING.md` with real measured numbers (rule-file line counts, snapshot/investigation-file byte caps, playbook byte range) and an honest "none found" conclusion for unnecessary/duplicated context
- [x] 1.4 Conclusion: no custom context infrastructure needed — every 2.1 capability composes native mechanisms

## Phase 2 — Capability resolution model
- [x] 2.1 Add `## 6a. Capability resolution` to `rules/engineering-workflow.md` — six-step resolution order as judgment guidance, not a hard-coded decision tree, explicitly deferring to §1 (tier), `evidence-policy.md` and §4 (authorization) rather than replacing them
- [x] 2.2 Add `## 4. Five distinct concepts` to `rules/task-routing.md` — Playbook/Routine/Role/Skill/Tool, kept structurally distinct; renumber the old `## 4. Universal output contract` to `## 5.`
- [x] 2.3 Fix the resulting test breakage: `tests/test_playbooks.py`'s literal-string router check (`"## 4. Universal output contract"` → `"## 5. Universal output contract"`), add a new check asserting the Routine/Role/Skill/Tool distinction is present

## Phase 3 — MCP/integration capability matrix
- [x] 3.1 Research current (2026-09-28) official/community MCP servers and CLI/API alternatives for GitHub, Spacelift, AWS, GCP, Kubernetes, Terraform, Jira, Confluence, and common observability systems (Grafana, Datadog, PagerDuty, Sentry, Prometheus)
- [x] 3.2 For each: vendor/maintainer, license, auth model, read/write/destructive capability, tool-count/context impact, lazy-loading support, Claude Code compatibility, whether CLI/API is preferable to an MCP server
- [x] 3.3 Write `docs/INTEGRATIONS.md` as a capability matrix (domain / preferred access / trust level / read-write / auth model / context strategy); explicit note that Slack is deliberately not included, per instruction
- [x] 3.4 Documentation only — no live wiring, no credentials stored or requested; this repository's sandbox has none of these credentials available, consistent with `evidence-policy.md`

## Phase 4 — Curated optional skills evaluation
- [x] 4.1 Evaluate Matt Pocock's `teach` skill (github.com/mattpocock/skills, MIT) — already lazy (`disable-model-invocation: true`, user-invoked via `/teach`); recommend as optional, do not install by default
- [x] 4.2 Evaluate Task Observer (rebelytics/one-skill-to-rule-them-all) — designed near-always-on, conflicts with context-frugality and the brief's own strict privacy requirement (no raw prompts/source/credentials/transcripts); decline, document why
- [x] 4.3 Evaluate `wshobson/agents` (40k★, MIT, native plugin marketplace) — deeper SRE/CloudOps coverage than ECC; per the owner's explicit instruction, document as a candidate only, do not adopt automatically
- [x] 4.4 Confirm security-review/architecture-review/doc-gen/diagram capability already exists (from `groundwork-2-enterprise-sre`'s builder-execution-roles/presentation work) rather than proposing duplicates
- [x] 4.5 Write `## 13. Curated skills and routine candidates` into `docs/FUTURE-SCOPE.md` (renumbering the old `## 13. Summary table` to `## 14.`)

## Phase 5 — Routines subsystem
- [x] 5.1 Confirm no native local (bare CLI) scheduler exists for unattended, repeatable Claude Code invocation (cloud Routines need the hosted product; Desktop scheduled tasks need the separate GUI app; `/loop` needs a live session and self-expires after 7 days) — headless `claude -p` is the documented composition point
- [x] 5.2 Confirm the safe unattended-invocation flag contract via live docs research: never `--dangerously-skip-permissions` (container/VM-restricted, refused under root/sudo), never `--bare` (skips Groundwork's own hooks/skills/MCP config); use `--permission-mode dontAsk` + `--permission-prompts none` + an explicit `--allowedTools` allowlist
- [x] 5.3 Build `scripts/groundwork_config.py` — one profile-driven, human-readable, no-secrets `config.json`; 8 profiles; `show`/`profiles`/`init`/`validate` CLI; `validate_config()` scans for secret-like keys
- [x] 5.4 Build `scripts/groundwork_routines.py` — one generic framework (name + prompt template + `mutates` flag + default schedule), not six bespoke scripts; six concrete routines: `jira_eod` (mutating, dry-run-capable, offline-work folding, verify-after-post), `news` (topic-driven digest, no filler when nothing material), `weekly_status`, `pr_followup`, `work_digest`, `doc_drift` (report-only, never auto-rewrites docs)
- [x] 5.5 Scheduling reuses `scripts/groundwork_report.py`'s exact launchd-plist pattern, parameterized per routine (`com.groundwork.routine.<name>`), with the same macOS-launchd/elsewhere-cron fallback
- [x] 5.6 Telemetry: `~/.claude/groundwork/telemetry/routines.jsonl`, same 0600 owner-only append-only pattern as `groundwork_telemetry.py`; structured fields only (routine, mutates, dry_run, exit_code, status, duration_s, output_chars) — never raw prompt/output text
- [x] 5.7 Off-switches: `GROUNDWORK_ROUTINES=off` (whole subsystem), `GROUNDWORK_ROUTINES_<NAME>=off` (one routine)
- [x] 5.8 Task Observer and the six further routine candidates (cert/PKI expiry, dependency advisories, infra drift, cost anomaly, stale-RCA follow-up, release readiness) scored and recorded as deferred future candidates in `docs/FUTURE-SCOPE.md`, not built this pass
- [x] 5.9 Live-validate against a real `claude` CLI in this sandbox: `work_digest` ran to completion (exit 0, real duration, structured telemetry recorded with 0600 permissions); `jira_eod --dry-run` with an `--offline-work` string also ran to completion

## Phase 6 — Browser/Chrome governed execution policy
- [x] 6.1 Extend `rules/engineering-workflow.md` §6a so browser/Chrome execution is governed by the exact same §4 authorization rule as MCP/CLI mutations — capability availability never implies mutation permission
- [x] 6.2 Add the "read the result back before reporting VERIFIED" rule explicitly for browser-driven mutations (a successful click/submit is not evidence of a successful underlying change)
- [x] 6.3 No new code — this phase is rule text only, reusing the existing authorization model

## Phase 7 — setup.sh capability configurator
- [x] 7.1 Add `choose_capabilities()` — optional (default No), profile-driven (8 profiles), never forced
- [x] 7.2 Add `apply_capabilities()` — writes `config.json` via `groundwork_config.py init`, schedules every enabled routine the same way the dashboard's schedule is applied
- [x] 7.3 Add `--capability-profile VALUE` non-interactive flag
- [x] 7.4 Wire into `run_setup()`'s existing question sequence and post-install sequence
- [x] 7.5 **Bug found and fixed during live end-to-end testing**: `apply_capabilities()`/`verify_capabilities()` called `groundwork_config.py` without `--path`, and `groundwork_config.py`'s `DEFAULT_PATH` was a bare `Path.home()/.claude/...` constant that ignored `CLAUDE_CONFIG_DIR` entirely — every other Groundwork Python file (`groundwork_report.py`, `groundwork_routines.py`, all four hooks) resolves `CLAUDE_CONFIG_DIR` first. Reproduced live: a sandboxed `setup.sh --non-interactive --capability-profile sre-cloudops` run wrote `config.json` into the real `/root/.claude/groundwork/` instead of the target `CLAUDE_CONFIG_DIR`, and setup's own "routines enabled: ..." summary silently reported `none` because it read back from the (correct, but never-written) target path. Fixed at the root: `groundwork_config.py`'s `DEFAULT_PATH` now resolves `CLAUDE_CONFIG_DIR` the same way every other script does. Re-verified live: config.json lands under the target dir, `--doctor`/`--routines` report real enabled routines, no leak to the real home directory. Regression-tested in `tests/test_groundwork_config.py` and `tests/test_setup.py`.

## Phase 8 — groundwork doctor / configure / routines commands
- [x] 8.1 Add `--doctor` / `--configure` / `--routines` modes to `setup.sh`'s existing mode-dispatch pattern
- [x] 8.2 `verify_capabilities()` — additive to `verify_install()`; reports CONFIGURED/AVAILABLE/DISABLED/NOT CONFIGURED, never asserts connectivity it didn't check (cloud/platform rows explicitly say "availability not connectivity-checked here")
- [x] 8.3 `run_configure()` — re-runs capability selection only, no backup, no reinstall
- [x] 8.4 `run_routines()` — lists configured routines and last-run status via `groundwork_routines.py list`
- [x] 8.5 **Bug found and fixed during live testing**: `run_doctor()` called `verify_install()` unguarded; under `set -euo pipefail`, a non-zero return (any core check failing) terminated the function immediately, silently skipping the entire Capabilities/Routines section — exactly the moment a doctor command's full diagnostic picture matters most. Fixed: `verify_install() || core_ok=1`, capabilities section always runs, overall exit code still reflects core health. Regression-tested in `tests/test_setup.py`.

## Phase 9 — ECC pinning
- [x] 9.1 Confirm `claude plugin marketplace add owner/repo#ref` version-pinning support (live docs research, 2026-09-28)
- [x] 9.2 Pin `install.sh`'s ECC install to `v2.2.1` via `#ref`, override via `GROUNDWORK_ECC_REF`
- [x] 9.3 Update `setup.sh`'s `verify_install()` ECC row: rename `LAST_VERIFIED_ECC`/its "drifting is normal, not a bug" messaging (stale after pinning) to `ECC_REF`-based pinned/differs-from-pin messaging
- [x] 9.4 Update `tests/test_setup.py`'s ECC-version tests to match the new pinned messaging (was still asserting the old drift-note text)
- [x] 9.5 Live-validate: fresh non-interactive install with the pinned ECC ref, `--doctor` reports `plugin ecc@ecc 2.2.1 (pinned to v2.2.1)`
- [x] 9.6 Live-validate uninstall after a capability-configured, pinned install: `config.json` removed, every scheduled routine plist unscheduled (via the new `tests/test_setup.py` capability/routines test's uninstall coverage)
- [-] 9.7 Upgrade-cycle re-proof (`claude plugin update ecc@ecc` against the pinned ref) — not exercisable in this sandbox (no real plugin-marketplace network access); documented as a known gap in `docs/RELEASE-REPORT-2.1.md` §12 rather than claimed as tested

## Phase 10 — Testing
- [x] 10.1 `tests/test_groundwork_config.py` (new, 112 checks) — default_config/validate_config per profile, load/save round-trip, fail-open on missing/corrupt files, CLI (init/show/profiles/validate, --force semantics), secret-key detection, and the CLAUDE_CONFIG_DIR regression test for the Phase 7 bug
- [x] 10.2 `tests/test_groundwork_routines.py` (new, 115 checks after the independent-review addition — a direct `JIRA_LIVE_TOOLS == READ_ONLY_TOOLS` pin) — ROUTINES registry shape, build_command's safety contract (never --dangerously-skip-permissions/--bare, correct --permission-mode/--permission-prompts/--allowedTools) for all six routines × dry-run states, off-switches, real subprocess run against a stub `claude` (success/failure/timeout paths), telemetry format and 0600 permissions, schedule_routine's plist generation and macOS/non-macOS branching, CLI `list`
- [x] 10.3 `tests/test_setup.py` — extended `test_verify_reports_ecc_version` for the new pin-based messaging; new `test_capabilities_and_routines` (23 checks after the independent-review addition — 3 for the corrupt-config.json regression) covering --capability-profile end-to-end, --doctor (including the Phase 8 regression and the independent-review MUST FIX regression), --configure (explicit profile and declined-prompt paths), --routines, no-profile-chosen NOT CONFIGURED path, and uninstall cleanup
- [x] 10.4 `tests/test_playbooks.py` — router renumbering fix plus the new Routine/Role/Skill/Tool distinction check (Phase 2.3)
- [x] 10.5 Full regression: `python3 -m pytest tests -q` — 28 test functions, all passing, after every change in this pass (743 total deterministic checks across 7 files)
- [-] 10.6 Additional coverage the brief's own checklist calls for but this pass leaves to Phase 11's live validation rather than new unit tests: news-topic deduplication/materiality filtering and TUI/doctor's "never invent unobservable data" property are behavioral properties of an LLM-driven routine prompt, not of the Python framework — verified by reading the actual runtime output in Phase 11, not asserted by a deterministic unit test

## Phase 11 — Live validation
- [x] 11.1 Formalize the Phase 5.9 / 7.5 / 8.5 / 9.5–9.6 manual sandbox runs into a dated `docs/VALIDATION.md` "Groundwork 2.1.0" entry with full command + result evidence
- [x] 11.2 Fresh install → capability profile selection (`sre-cloudops` exercised end-to-end; the remaining 7 profiles share the same `groundwork_config.py`/`apply_capabilities()` code path and are covered structurally by `tests/test_groundwork_config.py`'s per-profile `validate_config()` checks, not re-run live individually) → doctor → configure → routines → uninstall, full cycle — live-verified via `tests/test_setup.py::test_capabilities_and_routines` plus the standalone sandbox reproductions in `docs/VALIDATION.md`
- [x] 11.3 Live routine run: `work_digest` (mutates=false) against the real `claude` CLI in this sandbox, and `jira_eod --dry-run` (from the pre-compaction portion of this session) — both recorded in `docs/VALIDATION.md`. Not independently re-run live per routine class this pass: `news`/`weekly_status`/`pr_followup`/`doc_drift` share `work_digest`'s exact invocation path (`build_command()`/`run_routine()`), differing only in prompt text, which is not what this phase's live-validation claim is about (prompt-content quality is a model-behavior property, not a framework-mechanism one)
- [x] 11.4 Version-bump sanity check: fresh install after the CHANGELOG 2.1.0 entry was added reports `Groundwork 2.1.0 installed successfully` and stamps `VERSION` as `2.1.0` (was `2.0.0` through Phase 9's live tests, confirming `install.sh`'s CHANGELOG-derived version stamping works end-to-end with the new entry)

## Phase 12 — Independent review loop, documentation, final release-candidate report
- [x] 12.1 Write `docs/ROUTINES.md` (referenced by `rules/task-routing.md` §4 but not created until this phase)
- [x] 12.2 Update `README.md`'s repo-layout tree and a new "Capabilities, profiles and Routines" section, `docs/ARCHITECTURE.md`'s capability-ownership table (5 new rows), `CHANGELOG.md` (2.1.0 entry added, version heading bumped — confirmed live in 11.4 above)
- [x] 12.3a First independent review round: dispatched a fresh-context reviewer (background subagent, no access to this session's own reasoning) against the full working-tree diff vs `origin/main`. Returned `changes-required`, 2 MUST FIX: (1) the Phase 7/8 doctor fix was incomplete — `verify_capabilities()`'s own inline Python had no fail-open guard, so a corrupt `config.json` crashed the entire `--doctor` command silently under `set -e`, worse than the bug it was meant to fix; (2) `docs/ARCHITECTURE.md`/`README.md` still asserted ECC "installs unpinned from main" elsewhere in files this change otherwise edits, self-contradicting the new pinning content. Both fixed at the root and re-verified by live reproduction of the exact scenario the reviewer used; 3 NICE TO HAVE findings also fixed (`uninstall.sh` routine-name list now derived from the `ROUTINES` registry instead of hardcoded; `JIRA_LIVE_TOOLS == READ_ONLY_TOOLS` pinned by a direct test; the "config.json never contains credentials" claim reworded from an unconditional guarantee to what's actually true). Full detail: `docs/VALIDATION.md`'s "Independent review" subsection. Re-ran full suite (28 passed) and `openspec validate --changes` (3 valid) after every fix.
- [x] 12.3b Second, narrowly-scoped independent review confirming both MUST FIX fixes by direct old-vs-new reproduction (extracted the pre-fix `setup.sh` via `git show HEAD^:setup.sh`, ran both old and new against the identical corrupted-`config.json` scenario, confirmed the old script dies silently while the new one degrades to `Capabilities INVALID` and continues; grepped `docs/ARCHITECTURE.md`/`README.md` for every remaining "unpinned" hit and confirmed each is inside the clearly-dated historical clause, not a live claim). All 3 nice-to-haves spot-checked and confirmed present. Full regression re-run independently (28 passed, `openspec validate --strict` valid). **Verdict: approve, Must-fix: 0.**
- [x] 12.4 Write the final release-candidate report per the brief's required structure — `docs/RELEASE-REPORT-2.1.md` (release identity, architecture, context engineering, skills, MCP/integrations, routines, UX, tests, runtime validation, independent review, known limitations, deferred items, acceptance-standard walkthroughs)
- [-] 12.5 Never merge to main, never tag, never publish a release without explicit owner authorization — a standing constraint honored throughout the entire autonomous implementation and all four independent-review rounds (Phase 12 and Phase 13 below). The owner subsequently reviewed the final, fully-approved PR #22 and explicitly instructed the merge; PR #22 was merged to `main` (merge commit `e3d4b4f`) on that explicit instruction. Tagging and publishing a GitHub release remain un-authorized and undone.

## Phase 13 — Routine configuration contract (owner requirement, raised during PR #22 review)

The owner reviewed the shipped Routines subsystem and found it did not satisfy "configure once, run
automatically": (1) `READ_ONLY_TOOLS`/`JIRA_LIVE_TOOLS` were byte-identical, so a routine could never
actually reach Jira or GitHub regardless of configuration; (2) no identity/scope/access was ever
collected or persisted, so nothing could actually be configured once. This phase fixes both at the
root, incorporated into the existing Routines/onboarding capabilities rather than a new OpenSpec
change. Full design: `design.md` §D.2. Prior review history (§12.3a/12.3b) is preserved above, not
erased — this phase's own independent review is separate and additional.

- [x] 13.1 Redesign `config.json`'s per-routine schema (`scripts/groundwork_config.py`): `jira_eod`
  gains site/identity/access/mcp_server/scope/posting; `pr_followup` gains identity/access/scope
  (repositories + 5 filter booleans); `news` keeps topics; `weekly_status`/`work_digest`/`doc_drift`
  gain repository/integration scope fields; every routine's `schedule` becomes
  `{frequency, time}` (was a bare string). New `get`/`set` CLI subcommands (dotted-path,
  JSON-or-string values, validated before every write — an invalid value never corrupts the
  saved file). Per-routine field validation added to `validate_config()` (known access/posting/
  scope-type enums, HH:MM schedule-time format).
- [x] 13.2 Rebuild capability grants (`scripts/groundwork_routines.py` `_capabilities_for()`) from
  routine + configured access + configured scope + configured mutation permission — never one
  flat global allowlist. `pr_followup` gets exact real `gh` subcommands or session-confirmed real
  `mcp__github__*` read tool names, never a write-shaped one (it never mutates). `jira_eod` gets
  its configured MCP server's tools at the server level (exact per-tool read/write enumeration
  isn't knowable for an arbitrary user-configured server — documented as an honest limit, not
  hidden); BLOCKED if the server name is empty. `weekly_status`/`work_digest` reuse
  `jira_eod`/`pr_followup`'s own already-configured access rather than asking again.
- [x] 13.3 BLOCKED-before-invocation: `build_command()` returns `(None, reason)` when required
  access is unconfigured; `run_routine()` never calls `subprocess.run` in that case. Live-verified:
  `jira_eod` with `access=unconfigured` and `claude` deliberately unreachable on `PATH` returns
  `status: blocked`, never a crash from the missing binary.
- [x] 13.4 Semantic status: every routine prompt now requires a `ROUTINE RESULT` block (same
  shape/tolerance as `require_material_review.py`'s `REVIEW RESULT` parser). Exit 0 alone is never
  `COMPLETE`: a missing/malformed block is `FAILED`; a block reporting `BLOCKED`/`PARTIAL` is
  recorded as exactly that. Live-verified with stub `claude` binaries for all four cases
  (COMPLETE/BLOCKED/PARTIAL-via-block, and missing-block-is-FAILED).
- [x] 13.5 Result storage separate from telemetry: `~/.claude/groundwork/routines/results/<name>/
  run-<ts>.json` (0600/0700, retained to the 10 most recent runs, auto-pruned), holding the
  routine's actual output text. `routines.jsonl` telemetry confirmed to never contain a `content`
  field or the routine's real output text (direct inspection). `groundwork_routines.py latest
  <name>` / `setup.sh --routines NAME` retrieves it.
- [x] 13.6 `setup.sh` progressive per-routine wizard: `configure_routine_{jira_eod,pr_followup,
  news,weekly_status,work_digest,doc_drift}()`, only asked for routines actually enabled. Jira:
  site/identity/access(+MCP server name)/ticket scope/posting/schedule. PR follow-up: identity
  (with safe `gh auth status`-based auto-detect suggestion)/access/repository scope/schedule.
  News: topics (arbitrary custom allowed)/schedule. The other three: minimal — schedule (+
  period/paths where relevant), matching "reasonable defaults, no unnecessary questions."
- [x] 13.7 `--configure` reconfiguration menu: change profile / reconfigure one routine / cancel —
  any single routine's fields revisitable without reinstalling Groundwork or touching any other
  routine's saved configuration.
- [x] 13.8 `--doctor` extended with real per-routine detail (`groundwork_routines.py doctor`,
  formatting centralized in `format_doctor_text()` for testability): configuration/site/identity/
  access/connectivity/scope/posting/topics/schedule/last-run, CONFIGURED ≠ AVAILABLE ≠ CONNECTED ≠
  VERIFIED distinctions via best-effort safe checks (`gh auth status`, `claude mcp list`), never
  asserting CONNECTED without actually checking — "RUNTIME VALIDATION REQUIRED" stated plainly
  when it can't be checked from here.
- [x] 13.9 Tests: `tests/test_groundwork_config.py` extended (+35 checks: per-routine defaults,
  get/set CLI round-trip incl. rejection-leaves-file-unchanged, disabling needs no other fields).
  `tests/test_groundwork_routines.py` substantially rewritten (89 checks: capability-building
  least-privilege per routine, BLOCKED-before-subprocess, semantic-status from real stub-`claude`
  runs, result storage/retention/telemetry-separation, `check_access()` never-guesses-CONNECTED,
  doctor formatting, prompt-content scope-references, reschedule-without-duplication).
  `tests/test_setup.py` gained `test_routine_configuration_wizard` (55 checks: the full interactive
  wizard for Jira/PR-followup/News/disable-a-routine, end to end through `--doctor`); existing
  `--configure`/`--doctor` assertions updated for the new menu/output format. Full suite: 43 test
  functions, 0 failed. (Superseded by 13.12a below: this round's tests all shared one blind spot —
  every routine-wizard test drove `--configure`'s "reconfigure one routine" menu, never the
  profile-driven trigger — and `test_work_digest_cross_references_jira_and_github_access` only
  exercised `use_github`, never `use_jira`/`jira_projects`. Both gaps are closed in 13.12a.)
- [x] 13.10 Re-reviewed all six routines individually against configuration/identity/scope/
  capabilities/authorization/schedule/execution/result-delivery/semantic-status/verification/
  failure-behavior — `design.md` §D.2's "Per-routine review" paragraph; confirmed genuinely
  distinct capability-building logic per routine, not six prompts sharing one undifferentiated path.
- [x] 13.11 Updated `docs/ROUTINES.md` (substantially rewritten: configuration contract, per-routine
  schema, capability grants table, semantic status, telemetry-vs-results) and `docs/VALIDATION.md`
  (new "Routine configuration contract" subsection with deterministic + live evidence), plus
  `README.md`'s Routines paragraph. `docs/RELEASE-REPORT-2.1.md`'s release-identity and
  independent-review sections are deliberately updated once at 13.13, after the final commit SHA
  and this phase's own review verdict are both known — updating them now would mean rewriting
  twice. Recorded honestly throughout that this was found during owner review of PR #22, without
  erasing the Phase 12.3a/12.3b review history.
- [x] 13.12a A NEW adversarial independent reviewer, dispatched specifically against the Routine
  Configuration Contract (13.1-13.11) with instructions to live-reproduce rather than infer,
  returned `changes-required`, 3 MUST FIX (2 underlying bugs + their direct documentation
  consequence) — recorded, not erased: (1) `setup.sh` compared `cfg_get`'s lowercase JSON boolean
  output against the capitalized string `"True"` in 12 places, making `configure_routines_interactive()`
  a silent no-op on both the places it's actually invoked from (first-time interactive install and
  `--configure`'s "change profile" branch) — every prior test happened to drive the wizard through
  the *other* menu path ("reconfigure one routine"), which bypasses the bug entirely. Fixed with a
  new `cfg_get_bool()` helper normalizing the comparison; re-verified live (fresh interactive
  install and `--configure` → "1", full piped wizard answers, `config.json` inspected directly —
  every field landed). (2) `_capabilities_for()`'s `weekly_status`/`work_digest` Jira cross-reference
  path granted the same unrestricted `mcp__<server>__*` wildcard `jira_eod` itself gets for live
  posting, to routines declared `mutates: False` — violating this same phase's own `specs/routines/
  spec.md` SHALL. Fixed by granting no live Jira tool at all for the reuse case (no mechanism can be
  safely narrowed to read-only); `weekly_status`/`work_digest` now read `jira_eod`'s own stored
  result file instead (zero additional capability — `Read`/`Glob` already granted). (3) `docs/
  ROUTINES.md`/`design.md`'s claims were falsified by (1) and (2); corrected to match the fixed
  code, not weakened to match the bug. Both bugs fixed at the code; `specs/routines/spec.md` gained
  two new scenarios; two new regression tests added targeting exactly the blind spots that let them
  ship (`tests/test_setup.py::test_profile_driven_wizard_fires_on_both_entry_points`, `tests/
  test_groundwork_routines.py::test_non_mutating_routines_never_inherit_jiras_write_capable_wildcard`)
  — both independently confirmed, by temporarily reverting the fix, to actually fail against the
  pre-fix code. Full suite after fixes: 45 test functions, 0 failed. `openspec validate --strict`:
  valid. Full detail: `docs/VALIDATION.md`'s "Two more bugs found by a fresh adversarial reviewer"
  entry.
- [x] 13.12b A fresh confirmation reviewer (no access to the fixing session's own reasoning)
  independently re-reproduced both 13.12a fixes live — a differential test against the pre-fix
  commit confirmed the two new regression tests genuinely fail on the old code, not vacuously; a
  repo-wide grep confirmed no stale reference to the old wildcard-granting pattern remains;
  `_jira_evidence_note()`'s referenced path was confirmed to match exactly where `_store_result()`
  writes. **Verdict: approve, Must-fix: 0.** 3 NICE TO HAVE findings, all closed in the same pass:
  `weekly_status.jira_projects` was reachable only by hand-editing `config.json` (undisclosed,
  unlike the analogous `pr_followup` gap) — now disclosed in `design.md` §D.2; `_jira_evidence_note()`'s
  dead `indent` parameter removed; the cosmetic stray blank line in `_weekly_status_prompt()`/
  `_work_digest_prompt()` when no Jira cross-reference is configured fixed by building each
  prompt's body from filtered non-empty parts instead of an always-present template slot. Full
  detail: `docs/VALIDATION.md`'s "Fresh confirmation review of the Bug 3/Bug 4 fixes" entry.
- [x] 13.13 PR #22 updated (commit + push to the existing branch, commits `14f53ad` then `ae1fa1d`)
  and its description refreshed to reflect this phase (§7a of `docs/RELEASE-REPORT-2.1.md`, updated
  with the real HEAD/commit-list/file-count/test-count and both new independent-review rounds).
  Subsequently merged to `main` on explicit owner instruction (merge commit `e3d4b4f`, PR head
  `ae1fa1d`) — still untagged, unpublished as a GitHub release.
