# Implementation Readiness Report (EGM Stage 9)

**Target design:** `openspec/changes/replace-ecc-with-groundwork-core/design.md`
**Implementation plan judged:** `openspec/changes/replace-ecc-with-groundwork-core/tasks.md` (all)
**Reviewers (fresh context, read-only):** implementation-readiness, codebase-details, style
**Standard:** `implementation-readiness-standard.md`

## Verdict

Not ready to implement. An implementer would have to make design decisions in at least six places. The inventory, the ECC baseline numbers and most file:line citations are accurate. The weak parts are the migration, the rollback, the benchmark mechanics, the no-verify guard, and the ECC-text cleanup.

Counts: 6 Blocker, 14 Major, 14 Nit (after deduplication).

Limits: no reviewer could run shell commands. The following are not verified: `claude plugin uninstall --keep-data` exists and what its default is; `claude plugin list --json` exists; branch `fix/gate-plugin-dir-false-ask` exists; the "5 Gateguard blocks" and 7.5 s timing; `CLAUDE_CONFIG_DIR` is honoured by `claude plugin` commands.

---

## Blockers

### B1. The migration depends on a backup and key removal that `merge_settings.py` does not have
- **Lenses:** implementation-readiness, codebase-details
- **Scope:** design D6 step 3; tasks 6.1, 6.2, 6.3; spec `ecc-independence` ("timestamped settings backup")
- **Problem:** D6 says "Remove the three settings keys through `merge_settings.py`, which backs up first."
  - `scripts/merge_settings.py` has no backup code. `main()` (lines 316-342) reads, calls `merge()`, writes with `write_atomic` (lines 111-128).
  - `merge()` (lines 222-313) only adds keys. It never touches `enabledPlugins` or `extraKnownMarketplaces`; lines 299-303 touch only `pluginConfigs["ecc@ecc"].options.hook_profile`.
  - `unmerge_settings.py:125-133` removes only `hook_profile`.
  - The only backup is `setup.sh make_backup` (`setup.sh:239-254`, called at 764). It runs before `install.sh` (769). A direct `./install.sh` or `groundwork update` gets no backup.
  - Task 6.3 deletes the `hook_profile` code and adds no removal code.
- **Fix:** State that the backup and the key removal are new code. Name the program and flag (for example `merge_settings.py --remove-ecc` or `scripts/migrate_ecc.py`), the backup path pattern (for example `settings.json.pre-ecc-removal.<UTC ts>`), where the backup is taken when `install.sh` runs without `setup.sh`, which keys `claude plugin uninstall` removes versus which the script removes (and order), and what happens to emptied parents such as `pluginConfigs: {}` (the "second run changes nothing" requirement depends on it). Add tasks and tests for each.

### B2. Rollback and opt-out are left as an either/or, and conflict with task 6.3
- **Lenses:** implementation-readiness, codebase-details, style
- **Scope:** design D6 rollback step 2; tasks 6.2, 6.3, 6.5; `merge_settings.py:100-105, 299-303`
- **Problem:** D6 says `merge_settings.py --ecc` re-adds the key, "or the restored settings backup does the same". No task builds the flag. Task 6.3 removes ECC handling from the same script. Task 6.5 verifies only the backup route.
  - Under `GROUNDWORK_KEEP_ECC=1` on a fresh machine, with `hook_profile` handling removed, ECC would run at its own default profile. This is a silent change for opt-out users.
  - `merge_settings.py:100-105` sets `env.GATEGUARD_EXEMPT_GLOBS`, which matters only to ECC. It is in no inventory, decision or task. Unclear if migration and `unmerge_settings.py` should strip it.
- **Fix:** Pick one rollback route. Recommended: restored backup only, and delete the flag from D6. Write the exact command `install.sh` prints. State whether `KEEP_ECC=1` still writes `hook_profile` and what happens to `GATEGUARD_EXEMPT_GLOBS`. If the flag stays, add a task and a test.

### B3. The benchmark steps cannot be run as written
- **Lenses:** implementation-readiness, codebase-details, style
- **Scope:** tasks 1.1, 1.2, 5.1, 5.2, 6.5; design Validation (line ~177) and line 55
- **Problem:**
  - `bench.run` lives in `orchestrator/bench` on the parked branch `feat/m2-question-evidence`. No task checks it out or says which directory to run from. A search under `~/projects/ai-projects` finds no `bench/run.py`. The location of the `vg-2.5.0-r1b` baseline data is also not given.
  - 5.2 says "with G pointed at the bench copy" without naming the flag or environment variable.
  - Nothing says how `claude` or `claude plugin` is aimed at `~/gw-bench/groundwork-ecc-off` (`CLAUDE_CONFIG_DIR`? plugin cache location?). Sections 5 and 6.5 depend on this, and no evidence supports it.
  - "Bench copy" means both a config directory and the repo in different places. Task 1.1 does not say which `~/gw-bench/groundwork` is.
  - Task 5.2 requires "Evidence-section rate >= baseline", but section 1 never records that rate.
  - "Input tokens" is undefined (with or without cache read and cache creation tokens), and the pass limit 79,133 depends on it.
  - The hook-timing baseline has two sources: design table (p90 7,531 ms from "this session's transcript") and task 1.2 (benchmark transcripts). No extraction command is given.
- **Fix:** Add a prerequisite task to check out or cherry-pick the bench code and name the run directory. Write the exact shell commands for 1.1, 5.1, 5.2 and 6.5 with environment variables set. Verify `CLAUDE_CONFIG_DIR` behaviour first and record it. Add a baseline step that stores the Evidence-section rate. Define "input tokens per answer" once, with fields. Say the design table is provisional and that 1.2 figures replace it, and cite the transcript path.

### B4. Task order contradicts the design: the migration is used before it is built
- **Lens:** style
- **Scope:** `tasks.md:33` (5.1), `tasks.md:40` (6.2), `design.md:154` (D7 step 3)
- **Problem:** 5.1 says "migrate ECC off there only" but the migration is built in 6.2. D7 step 3 says "uninstall ECC there only" (a manual uninstall). The two documents describe different procedures.
- **Fix:** In 5.1 say "run `claude plugin uninstall ecc@ecc` manually in the bench copy" and align D7 step 3, or move 6.1-6.3 ahead of section 5.

### B5. The no-verify guard is outlined, not specified
- **Lenses:** implementation-readiness, codebase-details
- **Scope:** design D2; tasks 2.1, 2.2; `hooks/block_protected_push.py`; spec `git-integrity-guards`
- **Problem:** Reusing `_git_invocation` (lines 694-735), `GIT_VALUE_OPTIONS` (76) and `FORCE_CLUSTER_RE` (71) is fine, but:
  - After the `git` branch, `inspect_command` treats non-push subcommands as branch changes and does `continue` (lines 947-957). The new check must run before that. The plan does not say where.
  - Fail-closed paths (lines 864-866, 875-877, 1005-1010) key off `_mentions_push`. The spec requires deny-on-unparseable for any command with `--no-verify` or `core.hooksPath`. No task changes this. The early `sys.exit(0)` on bad input also needs review.
  - `commit -n` in short-flag clusters needs flag parsing that does not exist. Value-taking flags (`-m -F -C -c --author -t`) must be skipped so `commit -m -n` and `commit -F -n` do not trigger. Missing from the tests: `commit -nm x`, `commit -m"-n"`, `--message=--no-verify`, `-n` after `--`, `commit --amend -n`, `commit -C <rev>`.
  - `-n` is a commit-only shortcut. `git push -n` is a dry run and must pass. `git log -n 5` is in the tests, but this is not stated.
  - No decision for: aliases (`-c alias.x='commit --no-verify' x`), `GIT_CONFIG_*` environment variables, `git config core.hooksPath`, `bash -c` or `eval` nesting.
  - Module docstring says the hook is push-only and must be rewritten.
- **Fix:** Add the function signature and placement, the value-taking flag list, the subcommand list, an explicit allow or deny decision per case above, and tests for each. Update the docstring.

### B6. Task 7.1 verification cannot pass, and the ECC-text edit list is incomplete
- **Lenses:** codebase-details, implementation-readiness
- **Scope:** task 7.1, 7.2; design "No ECC text" row and line ~51; `rules/engineering-workflow.md`; `hooks/groundwork_telemetry.py:108`
- **Problem:** `grep -rn 'ecc:' rules hooks playbooks` still matches `hooks/groundwork_telemetry.py:108` ("ecc:code-reviewer") and `rules/engineering-workflow.md:15` (`ecc:code-explorer`). Neither is in the list (3, 20, 21, 22, 25, 78, 92). Lines 60, 66 and 68 also name ECC agents and skills as things to use, which breaks the `ecc-independence` requirement even though the grep misses them. Other ECC text not in the plan: `hooks/require_material_review.py:8,18`, `scripts/check_routing.py:14`, `uninstall.sh:26,139`, `CREDITS.md:12` (claims Groundwork does not vendor or copy ECC source, which task 3.2 contradicts), `docs/VALIDATION.md` (6 hits), `setup.sh:14,86` and `install.sh:5-7,44,56`.
  - The replacement for `ecc:planner`, `ecc:tdd-guide`, `/ecc:save-session`, `/ecc:resume-session` is "Groundwork's reviewer and the task brief", which is not a planner or a TDD guide.
  - The grep runs on the repo layout; the installed layout differs (`rules/groundwork`, `groundwork/playbooks`). The pattern also misses `ecc@ecc`, `ECC`, `/ecc`.
- **Fix:** List every affected line with exact replacement text. Widen the grep pattern (`ecc[:@/]|\bECC\b`), state which tree, and decide the allowed exceptions (migration code, notices file).

---

## Major

### M1. Token totals: design does not match how the hook works, and double-counting is likely
- **Lenses:** implementation-readiness, codebase-details, style
- **Scope:** design D5; tasks 4.1, 4.2; spec `usage-telemetry`; `hooks/groundwork_telemetry.py`
- **Problem:**
  - D5 reads usage "after the turn's prompt marker (`groundwork_shared.mark_turn_start`)". The telemetry hook does not use that marker. It finds the turn through `current_turn()` (lines 236-277). `mark_turn_start` is called only from `groundwork_reply_check.py:146-148`, and stores a whole-second string (`groundwork_shared.py:79-87`).
  - Claude Code writes one transcript line per content block with the same `message.id`. The codebase reviewer confirmed this in a subagent transcript (repeated ids at lines 98-99, 125-126, 139-140). A plain sum overcounts, and the spec scenario ("three assistant messages = 75,000") would pass only on synthetic data.
  - Not decided: whether sidechain or subagent usage counts (separate files under `subagents/`); how `requests` is defined; the placement of fields in the schema-2 record (`observed` or top level) and whether the schema number changes (`groundwork_report.py:102-114` branches on shape); turns with no metadata and no tools return `{}` from `build_record`, so get no tokens; a turn above `TAIL_CAP` (32 MB) gives a lower bound; the spec says the hook reads "only usage and timestamp fields" while the hook already reads tool inputs (`turn_facts`, 293-311).
- **Fix:** Use `current_turn()`. Deduplicate by `message.id` (last line wins). State the subagent rule, field placement, schema number and the empty-turn behaviour. Add a repeated-id fixture to 4.1.

### M2. Task 4.3 points at the wrong report command
- **Lenses:** implementation-readiness, codebase-details, style
- **Scope:** task 4.3; spec "Token report"; design D5
- **Problem:** `groundwork usage` is `cmd_usage` (`scripts/groundwork_cli.py:151-158`) which forwards to `groundwork_statusline.py usage`. That reads `usage.jsonl` (cost growth, 8-day retention, `USAGE_KEEP_S` line 76), not `events.jsonl`. `tests/test_usage.py` covers that command. `events.jsonl` is read by `scripts/groundwork_report.py`. The statusline already records `cost_usd` and context percent (`groundwork_statusline.py:534-549`), which the "records no tokens today" claim ignores. The spec's "7 days before and after" comparison may fail against the retention.
- **Fix:** Name the script, subcommand, period flag, the median and p90 function, the output text, the file read and its retention.

### M3. Config-protection ask has open choices and conflicts with the gate
- **Lenses:** implementation-readiness, codebase-details
- **Scope:** design D2; tasks 2.3, 2.4; spec `git-integrity-guards`; `hooks/groundwork_task_gate.py:1165-1178, 1339-1353, 1443`
- **Problem:** The spec lists file names only "for example" (globs such as `.markdownlint*`, `eslint.config.*` have no matching rule). Tests cover only `ruff.toml` and `pyproject.toml`. "Existing" is not defined (symlinks, relative paths, `NotebookEdit`, `MultiEdit`). `on_pre` turns any internal error into `ask` (lines 1352-1353), but the spec says fail open "and record the error". No hook error log exists in `hooks/`, `scripts/` or `docs/`. `GROUNDWORK_TASK_GATE=off` (line 1443) disables the new ask too; not mentioned.
- **Fix:** Put the exact list and matching rule (basename or path, case) in the design. Add one test per pattern family and one for MultiEdit. Either create the error log (file, format, writer) or remove it from the spec. Document the kill-switch.

### M4. Reviewer agent content is undecided
- **Lenses:** implementation-readiness, codebase-details, style
- **Scope:** design D3; tasks 3.1, 3.3, 3.4; spec `code-review-agent`; `hooks/require_material_review.py:83, 93-96, 171-179`
- **Problem:**
  - The Groundwork marker string is never given, but install, uninstall and the conflict test depend on it. Whether Claude Code accepts an unknown frontmatter key is not checked.
  - The literal `REVIEW RESULT` block is not given. The gate needs a standalone heading, then `Verdict:` and `Must-fix: N`.
  - "One severity model" is never defined. The design says "proof rule for HIGH", 3.1 says "HIGH/CRITICAL", the gate reads `Must-fix`. ECC reviewers differ: `code-reviewer.md:290-295` warns on HIGH, `python-reviewer.md:91-93` blocks on CRITICAL or HIGH.
  - The 6 KB cap has no evidence it fits. ECC's `code-reviewer.md` is 324 lines, and a Python section, MIT header, source version and marker must also fit. The sections kept are not listed. The "Prompt Defense Baseline" (lines 8-15) is dropped without a decision.
  - "Contains each required element" (3.1) has no assertions. Overwrite-if-marked on reinstall is unspecified (only skip-if-unmarked is). Install lines (`install.sh:89-102` use hard-coded `cp`, plus `mkdir -p "$CLAUDE_DIR/agents"`), conflict message wording and `uninstall.sh` removal are unspecified. The design says the header "records the source version"; 3.1 does not require it.
  - Task 3.4 tests would pass today (`REVIEW_PATTERN` already matches "groundwork-code-reviewer"), so they are not red-first. Task 3.2 does not say where the exact MIT copyright line comes from.
- **Fix:** Give the marker, the exact result block, a severity table mapped to `Must-fix`, the section list, required strings per test, the overwrite rule, install and uninstall lines. Drop or justify the 6 KB figure. Fetch the copyright line from ECC's `LICENSE`.

### M5. Migration failure handling is missing
- **Lenses:** implementation-readiness, style
- **Scope:** design D6 step 1; task 6.2
- **Problem:** Not stated: `claude` not on PATH; `claude plugin uninstall` fails (offline, wrong scope); marketplace already absent; whether settings keys are still removed after a failed uninstall; scope (installed with `--scope user`, maybe also project scope); `GROUNDWORK_KEEP_ECC=1` on a machine without ECC. "Its persistent data dir is kept by default: we pass `--keep-data`" contradicts itself, and the flag is unverified.
- **Fix:** Run `claude plugin uninstall --help` and record it. Write the step list with exit-code handling and idempotent re-run behaviour. Say whether the default deletes data, then keep or drop the flag.

### M6. The three settings keys are never named
- **Lens:** style
- **Scope:** `design.md:143`, `tasks.md:39-40`
- **Problem:** "Three settings keys" appears without a list. The codebase reviewer found them at `~/.claude/settings.json:373,382,393`; probably `enabledPlugins`, `extraKnownMarketplaces`, `pluginConfigs`, but the docs do not say.
- **Fix:** List them in D6 and in spec and tests.

### M7. `--verify` and `--doctor` have no source list
- **Lenses:** implementation-readiness, codebase-details, style
- **Scope:** task 6.4; spec `ecc-independence`; `setup.sh:615, 642-644, 664`
- **Problem:** "Every registered hook entry" has no target. `setup.sh:642` checks six hook files; `install.sh:95-102` makes eight executable (adds `groundwork_reply_check`, `groundwork_brief`). Counts cover four events and ignore `PostToolUse` and `PostToolUseFailure`. `merge_settings.py:9-14` registers 15 entries. Row text and state for "ECC reported as not used" are not given. The advisory `--doctor` message for a missing security reviewer (design Risks, line 164) is not in 6.4. The pinned AgentShield version (`design.md:103`) is never chosen, and 7.2 does not assign it.
- **Fix:** State the check reads hook commands from `settings.json` against one expected list and name where it lives. Give the row text. Add the doctor advisory and the AgentShield pin to tasks.

### M8. Sections 6 and 7 are not stable phases, and the tests that will break are not planned
- **Lens:** codebase-details
- **Scope:** tasks 6.2-6.4, 7.x
- **Problem:** After 6.2, `setup.sh --verify` still counts "ECC NOT CONFIGURED" as a failure (`setup.sh:664`), so `tests/test_setup.py:161, 382-426` fail. After 6.3, `tests/test_hooks.py:1712-1721` still asserts `hook_profile` handling. The `claude` stubs in `test_setup.py:103, 306`, `test_playbooks.py:112, 186, 265`, `test_groundwork_cli.py:57` print `ecc@ecc` for every `plugin` subcommand, so a post-migration check will see ECC present. `test_hooks.py:166` and `test_task_lifecycle.py:111` use `ecc:` names as data.
- **Fix:** Merge 6.2-6.4 into one passing phase or reorder. Add explicit steps to update or delete the ECC test rows and stubs.

### M9. No consolidated file scope
- **Lens:** codebase-details
- **Scope:** `tasks.md` as a whole
- **Problem:** Files appear only in prose. No Create/Modify/Delete list. Missed from tasks: `uninstall.sh` (lines 26, 139 say ECC untouched; plus agent removal), `CREDITS.md`, `docs/VALIDATION.md`, `setup.sh` beyond verify/doctor (design lines 48-50 list `setup.sh:86,646-665`, `unmerge_settings.py`), and the test files in M8. The proposal Impact lists `groundwork_task_gate.py` "or" `block_protected_push.py` while D2 chose both.
- **Fix:** Add a file table with action per file, and align the proposal wording.

### M10. Design and tasks disagree on criteria
- **Lens:** style
- **Scope:** `tasks.md:16` (2.5), `tasks.md:20-21` (3.1, 3.2), `design.md:165`
- **Problem:** Tasks add numbers and decisions not in the design (guards p90 <= 300 ms, 6 KB, tool list, MIT header, licence file). "No socket import" is a weak proxy for "no network access" and is not testable as written. Task 2.5 does not name the 200 sample commands or how p90 is measured.
- **Fix:** Move the figures and the licence decision into D2, D3 or the Validation table. Replace "no socket import" with a testable check.

### M11. Goals contradict the Gateguard drop
- **Lens:** style
- **Scope:** `design.md:60` vs `80`, `127-132`
- **Problem:** The goal "lose no protection that only ECC provides" conflicts with dropping Gateguard, and D4 itself accepts a quality drop.
- **Fix:** Narrow the goal to safety controls with no other equivalent, and name Gateguard as the accepted exception.

### M12. Evidence for the Gateguard drop is not checkable
- **Lenses:** style, codebase-details
- **Scope:** `design.md:80`, `design.md` gateguard citation `gateguard-fact-force.js:1264-1274`
- **Problem:** "Blocked this session 5 times" and "2 self-run tasks" have no source. The cited lines are only the destructive-command branch; the routine Bash gate (1284-1292) and the edit gate are separate. Not verified by any reviewer.
- **Fix:** Cite the transcript path or ID, and cite all three branches.

### M13. ECC inventory numbers are inconsistent
- **Lens:** style, codebase-details
- **Scope:** `design.md:12-13, 107-108`, inventory rows
- **Problem:** 369 skills with 3 used gives about 366 unused, not "280+". Commands are "0 calls in 90 days" at line 108 but `/ecc:terminal-opener` typed twice is recorded at line 107. Inventory errors: `pre:governance-capture` is off because it needs `ECC_GOVERNANCE_CAPTURE=1` (`hooks.json:56-60`), not because of the profile; `post:skill:track` sits under `PostToolUseFailure` and logs failures only (`hooks.json:176-184`); `pre:config-protection` and `pre:edit-write:gateguard-fact-force` are standalone entries, not sub-hooks of the "three dispatchers".
- **Fix:** Correct the counts and rows.

### M14. Migration Plan numbering is ambiguous
- **Lens:** style
- **Scope:** `design.md:161, 169`
- **Problem:** "Steps 1 and 2", "Step 4's migration" use D7 numbering while D6 also has steps. "Rollback is one command" but D6 gives a chained marketplace add, plugin install and settings restore.
- **Fix:** Write "D7 step 1" and so on, and say "one chained command plus the settings restore".

---

## Nit

1. Task 2.5 / N2: p90 hook timing method and extraction command are not given (`hook_success.durationMs`).
2. Task 7.1 / design: `rules/engineering-workflow.md` replacement text is not written (see B6).
3. Task 0.1: prerequisite "merge the gate false-prompt fix first" is on a branch no reviewer could see; "16 review-found bypasses" not shown covered by tests.
4. Design line 112: "Start Node 2-3 times per tool call" has no source.
5. Token margin: 65.1k - 6.2k - 0.34k = about 58.6k against a <= 59k limit. The new reviewer description uses most of the 400-token margin. State the margin.
6. Mixed terms: "owner"/"user"; "brief"/"task brief"/"per-branch brief"; "gate"/"task gate"/"review gate"/"material review"; "bench copy"/`groundwork-ecc-off`. Pick one term each, add a glossary line.
7. Undefined terms: "dispatchers" (line 74), "fix 1 (PR #72)" (137), "the screenshot command" (tasks 4), "rebuild 4 parts" (111, never listed).
8. Filler and absolutes: "What it really does" (76), "Rare, so prompts stay rare" (79), "in case" (67), "Same as above" (84), "No value for this harness" (92), "Only control that stops it" (78).
9. "UNKNOWN" in capitals (lines 45, 163): use plain words.
10. The v2.2.3 detail (line 5) is not used by any decision.
11. Validation command (line 177) omits `--runs-dir ~/gw-bench/runs`, which tasks.md:34 includes.
12. Task 3.4 tests are not red-first (see M4).
13. Task 5.2 PreToolUse hook p90 <= 500 ms has no computation method.
14. Bench copy assumption that `claude plugin` honours `CLAUDE_CONFIG_DIR` has no evidence (see B3; listed here as a reminder to record it).

---

## Checked and correct
- Citations verified: `install.sh:59-72`, `setup.sh:86,646-665`, `merge_settings.py:24,300-303`, `unmerge_settings.py:14,125-133`, `require_material_review.py:83,310-311`, `groundwork_session_snapshot.py:6-7`, `mcp-health-check.js:19`, `code-reviewer.md:5,29-111`.
- ECC reviewer pins `model: sonnet` and tools `Read, Grep, Glob, Bash` (`code-reviewer.md:4-5`).
- `REVIEW_PATTERN` already matches `groundwork-code-reviewer`; the gate needs no change.
- `check_file` (`groundwork_task_gate.py:1165-1178`) is a suitable place for the config-protection ask.
- The 17 personal agents exist; spot-checked ECC hook ids exist in `hooks.json`.
