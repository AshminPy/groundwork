## Conventions

- **Group** = a numbered section below. Mapping to the design's D7 order: group 1 is D7 step 2; groups 2-6 are step 3; group 7 is step 4; group 8 is steps 5-6.
- **Red first** means a new test fails before the change in this branch and passes after it.
- **Bench environment** means this prefix on every bench command:
  `CLAUDE_CONFIG_DIR=<bench dir> GROUNDWORK_NO_LAUNCHCTL=1 GROUNDWORK_LAUNCH_AGENTS_DIR=$S/launch GROUNDWORK_BACKUP_DIR=$S/backups`
  where `$S` is a scratch folder.
- **Real-state hash** means `shasum -a 256 ~/.claude/settings.json ~/.claude/plugins/installed_plugins.json ~/.zshrc ~/.bashrc ~/.profile ~/Library/LaunchAgents/com.groundwork.* 2>/dev/null`, saved before and compared after.
- **Bench runner** means `cd <checkout of bench/vanilla-vs-groundwork @ cb0d3f4>/orchestrator && NODE_USE_SYSTEM_CA=0 GW_BENCH_GROUNDWORK=<bench dir> <python with the bench requirements> -m bench.run --runs-dir ~/gw-bench/runs --arms V,G --repeats 3 --run-id <id>`.

## File scope

| File | Action | Group |
|---|---|---|
| `scripts/bench_prep.py` | Create: copy a bench dir, rewrite its absolute paths, check | 1 |
| `bench/edit-guard/` (scenarios, runner, README) | Create | 1 |
| `docs/designs/ecc-removal-baseline.md` | Create | 1, 7, 8 |
| `hooks/block_protected_push.py` | Modify: `_bypasses_hooks`, fail-closed paths, docstring | 2 |
| `hooks/groundwork_task_gate.py` | Modify: config-protection in `check_file`; `git config core.hooksPath` ask | 2 |
| `agents/groundwork-code-reviewer.md` | Create | 3 |
| `THIRD_PARTY_NOTICES.md` | Create | 3 |
| `CREDITS.md` | Modify (line 12 says no ECC content is copied) | 3 |
| `hooks/groundwork_telemetry.py` | Modify: `tokens` | 4 |
| `scripts/groundwork_report.py` | Modify: `normalise()`, percentile helper, token section | 4 |
| `setup.sh` | Modify: `--backup` mode; `--verify` reads `hook-manifest.json`; ECC row; remove `ECC_REF` (86) and ECC text (14, 83, 710); `VERIFY_FAILS` no longer counts ECC (664) | 5 |
| `scripts/migrate_off_ecc.py` | Create | 5 |
| `install.sh` | Modify: remove ECC install (5-7, 43-44, 56, 59-72); install agent; write `hook-manifest.json`; call the migration at start and end | 5 |
| `uninstall.sh` | Modify: remove marked agent, `hook-manifest.json`; text at 26, 139 | 5 |
| `scripts/merge_settings.py` | Modify: delete 299-303; move `GATEGUARD_EXEMPT_GLOBS` to a legacy list; text at 19, 24 | 5 |
| `scripts/unmerge_settings.py` | Modify: keep removing legacy `hook_profile` and `GATEGUARD_EXEMPT_GLOBS` | 5 |
| `scripts/groundwork_update.py` | No code change; new test that update runs the migration | 5 |
| `rules/engineering-workflow.md` (3, 15, 20-22, 25, 60, 66, 68, 78, 92), `rules/evidence-policy.md` (35) | Modify | 6 |
| `hooks/require_material_review.py` (8, 18, 310-311), `hooks/groundwork_session_snapshot.py` (6-7), `hooks/groundwork_telemetry.py` (108 comment), `hooks/block_protected_push.py` (4), `scripts/check_routing.py` (14) | Modify text | 6 |
| `README.md`, `docs/ARCHITECTURE.md`, `docs/TROUBLESHOOTING.md`, `docs/UPGRADE-ROLLBACK.md`, `docs/VALIDATION.md`, `docs/MACOS-SMOKE-TEST.md`, `docs/CONTEXT-ENGINEERING.md`, `docs/FUTURE-SCOPE.md`, `CHANGELOG.md` | Modify | 6 |
| `openspec/changes/groundwork-2-enterprise-sre/specs/ecc-capability-policy/spec.md` | Modify: superseded notice at the top | 6 |
| Tests: `test_hooks.py`, `test_task_lifecycle.py`, `test_telemetry.py`, `test_report.py`, `test_setup.py`, `test_playbooks.py`, `test_groundwork_cli.py`, `test_groundwork_update.py` | Modify | 2-6 |

## 0. Prerequisites

- [x] 0.1 Task-gate false-prompt fix merged (https://github.com/AshminPy/groundwork/pull/73)
- [ ] 0.2 Portable install (change `portable-install`, its own PR, per design D7 P2) merged and installed; verify a bench dir's `settings.json` hook commands contain `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` and no `~/.claude/hooks` literal

## 1. Baselines (no product change)

- [ ] 1.1 Write `scripts/bench_prep.py <source> <dest>` (copy with `cp -Rc`, rewrite the source path to dest in `settings.json`, `plugins/installed_plugins.json`, `plugins/known_marketplaces.json`); verify by test that `grep -r <source>` over those files in dest prints nothing
- [ ] 1.2 Create `~/gw-bench/g-ecc-on` and `~/gw-bench/g-ecc-off` with `bench_prep.py` from `~/gw-bench/groundwork`; verify `CLAUDE_CONFIG_DIR=<each> claude plugin list --json` lists `ecc@ecc` with an `installPath` under that dir
- [ ] 1.3 Save the real-state hash to `$S/real-state.before`
- [ ] 1.4 Run `CLAUDE_CONFIG_DIR=~/gw-bench/g-ecc-on claude -p /context` 3 times; record total and custom-agent figures in `docs/designs/ecc-removal-baseline.md`
- [ ] 1.5 Write `bench/edit-guard/` (6 scenarios from the design Validation table; each run in a fresh throwaway git repo with a failing pre-commit hook and a `ruff.toml`; runner command `python3 bench/edit-guard/run.py --config-dir <dir> --repeats 3 --out <file>`; it records transcript path, read-before-edit rate, commit created yes/no, `ruff.toml` changed yes/no, reviewer call with `REVIEW RESULT` yes/no); verify one scenario end to end on `g-ecc-on`
- [ ] 1.6 Record the hook-wait baseline: PreToolUse `durationMs` p50/p90 by source (ECC versus Groundwork) from the 5 newest desktop transcripts in `~/.claude/projects/`; verify p90 ≥ 5 s, or record that the slow path did not reproduce and use the bench comparison only

## 2. Git integrity guards (red first)

- [ ] 2.1 Add a test per row of the design D2 no-verify table and per `git-integrity-guards` spec scenario to `tests/test_hooks.py`, including `--no-verif`, `am -n`, `pull --no-verify`, `HUSKY=0 git commit`, `merge --no-verify-signatures` (allowed); verify the deny rows are red
- [ ] 2.2 Add one test per fail-closed path (`block_protected_push.py:864-866`, `871-873`, `876-877`, `1005-1010`, and parse failure) with a command that mentions `--no-verify`; verify they are red
- [ ] 2.3 Implement `_bypasses_hooks` and the fail-closed rule in `hooks/block_protected_push.py`; update the docstring; verify 2.1, 2.2 and all existing `test_hooks.py` git-guard tests pass
- [ ] 2.4 Add config-protection tests to `tests/test_task_lifecycle.py` (each of the 32 names; mixed case; existing, missing, dangling symlink; Edit, Write, MultiEdit, NotebookEdit; `pyproject.toml` and `.markdownlint-cli2.yaml` not asked) and `git config core.hooksPath` tests; verify red
- [ ] 2.5 Implement both in `hooks/groundwork_task_gate.py`; verify 2.4 and the full `tests/test_task_lifecycle.py` pass
- [ ] 2.6 Add the timing and import test from the design Validation "Guards" row; verify it passes

## 3. Reviewer agent

- [ ] 3.1 Write `agents/groundwork-code-reviewer.md` per design D3 (frontmatter with marker; untrusted-data rule; confidence, pre-report and proof rules; false positives; Python section; security section; severity table; literal `REVIEW RESULT` block; MIT header pointing to `THIRD_PARTY_NOTICES.md`)
- [ ] 3.2 Add `tests/test_setup.py::test_reviewer_agent_content`, which asserts each element listed in 3.1 by a fixed string; verify it passes
- [ ] 3.3 Create `THIRD_PARTY_NOTICES.md` from `~/.claude/plugins/cache/ecc/ecc/2.2.1/LICENSE` and fix `CREDITS.md:12`; verify `grep -c "Copyright (c) 2026 Affaan Mustafa" THIRD_PARTY_NOTICES.md` prints 1
- [ ] 3.4 Add regression tests to `tests/test_hooks.py` for the review gate with a `groundwork-code-reviewer` result ending `Must-fix:  0` (turn may end) and `Must-fix:  2` (blocked); these pass without code change and guard against future gate changes

## 4. Token totals (red first)

- [ ] 4.1 Add tests to `tests/test_telemetry.py` for each `usage-telemetry` scenario plus: `isSidechain` lines skipped, `<synthetic>` replies not counted, a subagent file with lines before the turn start, the 50-file and 8 MB caps, and a turn longer than `TAIL_CAP`; verify red
- [ ] 4.2 Implement `tokens` in `hooks/groundwork_telemetry.py` per design D5; verify 4.1 and the existing `tests/test_telemetry.py` pass
- [ ] 4.3 Add the report token section (`normalise()`, percentile helper, Markdown and HTML) to `scripts/groundwork_report.py`; verify with a fixture in `tests/test_report.py` holding records with and without `tokens`

## 5. Migration, installer and health check (one group; the suite is green at its end)

- [ ] 5.1 Add `setup.sh --backup` (runs `make_backup`, prints the path); verify by test, plus the existing backup and rollback tests unchanged
- [ ] 5.2 Make the `claude` stubs in `tests/test_setup.py` (103, 306), `tests/test_playbooks.py` (112, 186, 265) and `tests/test_groundwork_cli.py` (57) stateful per subcommand (`plugin list --json`, `plugin uninstall`, `plugin marketplace remove`); verify the existing tests still pass
- [ ] 5.3 Add stub tests for S0-S9 and each `ecc-independence` scenario that does not need the real CLI (including the S2 foreign-`installPath` refusal, `GROUNDWORK_BACKUP_PATH` reuse and `groundwork update`); verify red
- [ ] 5.4 Implement `scripts/migrate_off_ecc.py` and the `install.sh` changes (no ECC install; agent with marker rule; `hook-manifest.json`; migration at start and end); verify 5.3 passes
- [ ] 5.5 Change `setup.sh --verify/--doctor` (manifest-based hook check, agent check, ECC row text, no `ECC_REF`); update the tests that expect the ECC row (`tests/test_setup.py:161` and `381-426`); verify they pass
- [ ] 5.6 Change `scripts/merge_settings.py` and `scripts/unmerge_settings.py`; update `tests/test_hooks.py:1712-1721`; add a test that uninstall still removes legacy `hook_profile` and `GATEGUARD_EXEMPT_GLOBS`; verify it passes
- [ ] 5.7 Run `python3 -m pytest tests -q`; verify 0 failures

## 6. Text and docs

- [ ] 6.1 Replace ECC references in the group-6 files of the file scope, using this mapping:
  - `ecc:planner`, `ecc:architect` → built-in `Plan` agent or an inline plan
  - `ecc:tdd-guide` → "write the failing test first"
  - `ecc:code-explorer` → built-in `Explore` agent
  - `ecc:code-reviewer`, `ecc:python-reviewer`, `ecc:security-reviewer` → `groundwork-code-reviewer`
  - `/ecc:save-session`, `/ecc:resume-session` → the task brief
- [ ] 6.2 Update the docs (removal, rollback with `./setup.sh --rollback`, AgentShield pinned to the version `npm view ecc-agentshield version` prints that day); add the superseded notice to `ecc-capability-policy`
- [ ] 6.3 Run both text checks from the design Validation section, verbatim; verify check 1 prints nothing and every file from check 2 is in the allow-list; run `openspec validate --all --strict` and verify it passes

## 7. Measure without ECC (bench dirs only)

- [ ] 7.1 Save the real-state hash; run `install.sh` from this branch with the bench environment for `~/gw-bench/g-ecc-off`; verify `claude plugin list --json` there has no `ecc@ecc`, `g-ecc-on` still has it, and the real-state hash is unchanged
- [ ] 7.2 Run `CLAUDE_CONFIG_DIR=~/gw-bench/g-ecc-off ./setup.sh --rollback <backup printed in 7.1>`; verify `ecc@ecc` is listed again and `cmp` of `settings.json` with the backup copy prints nothing; then repeat 7.1
- [ ] 7.3 Run `claude -p /context` 3 times on each of `g-ecc-off` and `g-ecc-on` (same day); verify the Validation "Tokens per request" rule
- [ ] 7.4 Run the bench runner with `--run-id ecc-on-r3` (`GW_BENCH_GROUNDWORK=~/gw-bench/g-ecc-on`) and `--run-id ecc-off-r3` (`g-ecc-off`), and the edit-guard runner on both; verify every Validation "Accuracy", "Token cost" and "Edit and guard set" rule, and record all figures in the baseline file
- [ ] 7.5 If any rule in 7.3-7.4 fails: stop; record the failing case, transcript path and cause in the baseline file; continue only after it is fixed, or after the design records it as accepted with the reason

## 8. Review, merge, deploy, live check

- [ ] 8.1 Run `python3 -m pytest tests -q` and `openspec validate replace-ecc-with-groundwork-core --strict`; verify 0 failures and "is valid"
- [ ] 8.2 Independent fresh-context review of the full diff by `groundwork-code-reviewer` (as installed in `g-ecc-off`); fix every must-fix and re-review until `Must-fix: 0`
- [ ] 8.3 Open the PR; merge after review; run `./install.sh` on this Mac; verify a backup path is printed, `claude plugin list --json` has no `ecc@ecc`, `./setup.sh --verify` passes, and `claude -p /context` is within 1k of the `g-ecc-off` mean from 7.3
- [ ] 8.4 After restarting the desktop app, over the next 5 sessions: verify PreToolUse p90 ≤ 500 ms (same command as 1.6), no "Fact-Forcing Gate" text in new transcripts, and `tokens` in new `events.jsonl` records; record them in the baseline file
- [ ] 8.5 Report to the owner: the ECC data removal command printed by the migration, and the two owner follow-ups in the design
