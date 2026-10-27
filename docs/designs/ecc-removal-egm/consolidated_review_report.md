# Consolidated Review Report: replace-ecc-with-groundwork-core

**Target:** `openspec/changes/replace-ecc-with-groundwork-core/design.md` (185 lines). Implementation plan: `tasks.md` in the same folder.
**Stages merged:** 5 Zoom Out, 6 Comprehension, 7 Critic, 8 Intermediate Zoom Out, 9 Implementation Readiness. Reports sit in this folder.

## Verdict

- **Architecture: GO.** Removing ECC entirely is the right call. No stage found evidence against it. The agent and skill lists cost about 6.5k tokens per request. The `.*` hooks start Node on every tool call. Measured use is about 100 calls in 90 days, almost all `code-reviewer`.
- **Design and plan as written: NO-GO.** All Blockers are about execution, not direction. The migration cannot be run in the order written, rollback is unclear, the validation cannot detect a quality drop, and several guards are outlines.
- **Count after cross-stage merge:** 8 Blockers, 17 Majors, about 15 Nits.
- **Limit:** No reviewer could run shell commands. Claims about the `claude plugin` CLI, hook timings and the benchmark data are unverified. See "Unverified" at the end.

## Actions by priority

### Blockers (fix before any implementation)

| ID | Action | Why | Source findings |
|----|--------|-----|-----------------|
| A1 | **Make the backup step 0 and make it complete.** Back up `settings.json` and also `plugins/cache/ecc` and the marketplace clone, before any removal. State that backup and key removal are new code, name the script and flag, and name the three keys: `enabledPlugins["ecc@ecc"]`, `extraKnownMarketplaces.ecc`, `pluginConfigs["ecc@ecc"]`. | D6 says `merge_settings.py` "backs up first". It has no backup code (`merge_settings.py:316-342`) and only adds keys. The only backup is `setup.sh:239-254` and it runs before `install.sh`. Today the backup would be taken after ECC is already removed. | ZO3, CMP1, CR-B1, IZ-A, IR-B1, IR-M6 |
| A2 | **Pick one rollback and make it work offline.** Prefer a restored backup (A1). Drop `merge_settings.py --ecc` if the restore covers it. Fix D6/Migration line 169: `GROUNDWORK_KEEP_ECC=1` leaves ECC alone and cannot reinstall it. Fix "one command" (it is two plus a settings step). Define `--keep-data` (default or flag, and if it exists). Say what `GROUNDWORK_KEEP_ECC=1` does to `hook_profile`, `GATEGUARD_EXEMPT_GLOBS` (`merge_settings.py:100-105`), `--verify` and tests. Define `groundwork update` or remove it from the spec. | Rollback needs GitHub and an unmoved tag, while uninstall deletes the local cache. Task 6.3 deletes the code the flag would need. | ZO2, ZO3, ZO14, CMP2, CR-M1, CR-M2, IZ-A, IR-B2, IR-M5 |
| A3 | **Reorder the phases so the migration is built before it is measured.** Either move 6.1-6.3 ahead of section 5, or say 5.1 is a manual `claude plugin uninstall` and add a later check that the real migration reaches the same end state. Order inside the migration: backup, install guards and reviewer, `setup.sh --verify`, then remove ECC. Prove how `claude` and `install.sh` are aimed at the bench config dir (`CLAUDE_CONFIG_DIR`?) before any uninstall runs, or the test may uninstall ECC from the real machine. | D7 step 3 measures a migration that task 6.2 builds later. Sections 6.2-6.4 also leave the test suite red between steps (see A8-M). | CMP4, IZ-B, IR-B4, IR-M8, ZO3 |
| A4 | **Replace the accuracy and hook-wait validation.** At least 3 repeats on both arms, with a stated tolerance (for example tokens up by at most 2%, Evidence rate down by at most one case). Add an edit-and-guard scenario set: edit without reading, `--no-verify`, config change, a reviewer round trip, and a read-before-edit measure. Merge or pin the benchmark code (it sits on parked branch `feat/m2-question-evidence`, no task checks it out). Define "input tokens" (with or without cache reads) and the "Evidence rate" once, and record the baseline Evidence rate (never recorded). Show that ECC-on reproduces the slow 7.5 s baseline in the same environment (`NODE_USE_SYSTEM_CA=1` may not be set in the bench). Record all baselines in one place. | The gate is 20 fixed question-answering cases at 20/20 with `--repeats 1`. At the ceiling, noise decides. D4 names this benchmark as the mitigation for the risk it misses. | ZO1, ZO4, CMP6, CR-B2, CR-M7, IZ-C, IR-B3 |
| A5 | **Specify the no-verify guard.** Give the function, its placement and the early exits in `block_protected_push.py` (non-push git commands hit `continue` at lines 947-957; fail-closed paths key off `_mentions_push`, lines 864-877, 1005-1010). Add a table: git subcommand x flag form, deny or allow. Cover `commit -n`, `-nm`, `-an`, value-taking flags (`-m -F -C -c --author -t`), `push -n` (a dry run, must pass), `merge -n`, `am -n`, `--no-verify=...`, `core.hooksPath` (case-insensitive), `GIT_CONFIG_*`, aliases, `bash -c`/`eval`. Put the spec's fail-closed rule into the design, define "cannot parse", and keep `git commit -m "fix: no-verify docs"` allowed. Give the exact deny text. Update the module docstring (push-only). | The design says "reuse the parser" and stops. | ZO6, CMP3, CR-M5, IZ-F, IR-B5 |
| A6 | **Widen the ECC-text cleanup and make the check pass.** Replace the hand-built line list with `grep -rniE 'ecc[:@/]\|\bECC\b'` over the repo trees and the installed trees, with an allow-list (CHANGELOG, CREDITS/THIRD_PARTY_NOTICES, migration code). Add missing lines: `rules/engineering-workflow.md` 15, 60, 66, 68; `hooks/groundwork_telemetry.py:108`; `hooks/require_material_review.py:8,18`; `hooks/block_protected_push.py:4`; `scripts/check_routing.py:14`; `install.sh:5-7,43,56`; `uninstall.sh:26,139`; `setup.sh:14,83,86`; `CREDITS.md:12` (contradicts task 3.2); `docs/VALIDATION.md`. Name the replacement for `ecc:planner`, `ecc:tdd-guide`, `/ecc:save-session`, `/ecc:resume-session`. List owner-level follow-ups (`~/.claude/CLAUDE.md:9`, `rules/behavior.md:157`). | Task 7.1's own grep still matches `groundwork_telemetry.py:108` and `engineering-workflow.md:15`, so it cannot pass. A case-sensitive `ecc:` grep also misses "ECC reviewers" prose. | ZO9, CMP10, CR-M4, IZ-E, IR-B6 |
| A7 | **Specify the token-total design (D5).** Reuse `current_turn()` from `groundwork_telemetry.py` (not `mark_turn_start`, which only `groundwork_reply_check.py` uses). De-duplicate by `message.id` (last line wins); the "3 messages = 75,000" spec scenario passes only on synthetic data. State the subagent/sidechain rule (likely the largest cost), the definition of `requests`, field placement (`observed` or top level) and schema version, the behavior for turns where `build_record` returns `{}`, and the 32 MB `TAIL_CAP` lower bound. Scope "only usage and timestamp fields" to the new code. Add a repeated-id fixture. | The current design would over-count and does not match the code. | ZO10, CMP5, CR-M6, IZ-H, IR-M1 |
| A8 | **Define the reviewer agent contract.** Give the marker key and text, and check Claude Code accepts an unknown frontmatter key. Include the literal `REVIEW RESULT` block (heading, `Verdict:`, `Must-fix: N`; `rules/output-contract.md:46-51`, `require_material_review.py:93`). Give a severity table mapped to `Must-fix`. State that HIGH becoming must-fix is deliberate (ECC warns only on HIGH, `code-reviewer.md:290-295`). List the kept and dropped sections. Decide on the Prompt Defense Baseline (`code-reviewer.md:8-15`; the new reviewer has Bash and reads untrusted diffs). Justify or drop the 6 KB cap. Fix "read-only" for a Bash-enabled agent. State the overwrite-if-marked rule and the install and uninstall lines. Fetch the MIT copyright line from ECC's `LICENSE`. | Install, uninstall, tests and the gate depend on facts not given. Task 3.4's tests already pass today, so they are not red-first. | ZO8, CMP8, CR-M5, IZ-I, IR-M4 |

### Majors (fix before or during the first implementation phase)

| ID | Action | Source findings |
|----|--------|-----------------|
| M-1 | **Security reviewer.** Design D3 rejects personal agents because a fresh laptop has none, then drops `security-reviewer` on that exact reliance. Either ship a security mode in the new reviewer or accept the gap, and fix task 8.2 ("security reviewer plus code reviewer"). Add the `--doctor` advisory to a spec and a task, or delete the promise. | CMP12, CR-M9, IZ-J |
| M-2 | **Config-protection (D2).** Give a closed file list that is a superset of ECC's `PROTECTED_FILES` (`config-protection.js:22-96`), with matching rule, case and dangling-symlink behavior (ECC: lines 97-112), `MultiEdit`/`NotebookEdit`, and tests per pattern family. State what `ask` does headless (it becomes a denial, `groundwork_task_gate.py:1096-1099`). Accept the Bash gap (`sed -i`). Document that `GROUNDWORK_TASK_GATE=off` disables it. Create the promised hook error log or remove it from the spec (`on_pre` turns errors into `ask`, lines 1352-1353). | ZO7, CMP7, CR-M5, IZ-G, IR-M3 |
| M-3 | **Migration failure handling.** Write a numbered state machine: `claude` not on PATH, uninstall fails, marketplace already absent, settings edit fails after uninstall, idempotent re-run (emptied parents such as `pluginConfigs: {}`), project-scope installs, a custom `CLAUDE_DIR`, open sessions (print a restart notice), a sweep of `settings.json` for other `ecc` paths (for example the statusline script), and `KEEP_ECC=1` on a machine without ECC. Run `claude plugin uninstall --help` and record the output. | ZO3, ZO11, CMP11, CR-M3, IZ-K, IR-M5 |
| M-4 | **Re-test the "no partial install" premise** (D1) on the current CLI: `skillOverrides` and `Agent(name)` deny rules, with version and output. The premise comes from a September spec. Removal likely still wins because of the hooks. | ZO12, IZ-D |
| M-5 | **Fix the inventory.** Add `post:governance-capture`; correct `pre:governance-capture` (off because it needs `ECC_GOVERNANCE_CAPTURE=1`); `post:skill:track` is under `PostToolUseFailure`; `pre:config-protection` and `pre:edit-write:gateguard-fact-force` are standalone entries; name the dispatchers (`pre:bash:dispatcher`, `post:dispatcher:sync`, `post:dispatcher:async`); add the command that produced the table. Add a table mapping each destructive class of Gateguard (`gateguard-fact-force.js:56`: `drop table`, `delete from`, `truncate`, `dd if=`; `rm`) to the Groundwork check that covers it, or mark it an accepted loss. | ZO5, CMP9, CR-M5, IR-M13 |
| M-6 | **Fix numbers and sources.** Skill count (369 vs "280+"), commands "0 calls" vs `/ecc:terminal-opener` typed twice, the "~340 tokens for 369 skill names" figure, "Node 2-3 times per tool call", transcript retention behind "90 days" (record the earliest transcript date; define "used" per component kind), "blocked this session 5/6 times" (cite the transcript), the v2.2.3 claims, and name the "4 parts" once. | ZO13, ZO15, CMP14, CMP16, CR-M7, CR-M8, CR-M13, IR-M12, IR-M13 |
| M-7 | **Token target margin.** 65.1k - 6,195 - ~340 is about 58.6k against a 59k limit, with the new agent description unbudgeted. Measure run-to-run variance over 3 baseline runs, or use a delta rule. | ZO13, CR-M10, IR-nit |
| M-8 | **Wrong report command (task 4.3).** `groundwork usage` is `cmd_usage` (`scripts/groundwork_cli.py:151-158`), reads `usage.jsonl` with 8-day retention (`groundwork_statusline.py:76`), not `events.jsonl`. Name the script, subcommand, period flag, file and retention. The spec's "7 days before and after" may exceed retention. | CMP5, IR-M2 |
| M-9 | **Phase stability and tests that will break.** After 6.2, `setup.sh:664` still fails "ECC NOT CONFIGURED" and `tests/test_setup.py:161, 382-426` fail. After 6.3, `tests/test_hooks.py:1712-1721` fail. The `claude` stubs in `test_setup.py:103,306`, `test_playbooks.py:112,186,265`, `test_groundwork_cli.py:57` print `ecc@ecc` for every `plugin` subcommand. Merge 6.2-6.4 into one phase or add explicit test-update steps. | IR-M8 |
| M-10 | **File scope table.** Add Create/Modify/Delete per file: `uninstall.sh`, `CREDITS.md`, `docs/VALIDATION.md`, `setup.sh`, `unmerge_settings.py` (needs a test to keep cleaning old keys), and the test files above. Align the proposal ("or") with D2 (both files). Name where the expected hook list for `--verify` lives (`setup.sh:642` checks six files; `install.sh:95-102` makes eight; `merge_settings.py:9-14` registers 15 entries). | CMP21, IZ-14, IR-M7, IR-M9 |
| M-11 | **Design and tasks disagree.** Move task-only figures (p90 <= 300 ms guards, 6 KB, tool list, MIT header, licence file) into the design or Validation table. Replace "no socket import" with a testable check. Name the 200 sample commands and how p90 is measured (`hook_success.durationMs`). | IR-M10 |
| M-12 | **Narrow the goal** "lose no protection that only ECC provides": Gateguard is an accepted exception (D4). Restate as "every inventory row marked KEEP has a Groundwork test". | CMP18, IR-M11 |
| M-13 | **Promised work with no task:** the review-rule mode note, the pass^k metric, the pinned AgentShield version (`<pinned version>` is a placeholder), the "two-reviewer loop", `ecc-capability-policy` "superseded" (how?), `CREDITS.md`/`THIRD_PARTY_NOTICES.md` handling. Add tasks or cut. | CMP13, CR-N3, IZ-L, IR-M7 |
| M-14 | **Missing structure for the standard.** No Alternatives table covering D4, D5, D7. No Proposed Architecture or Problem Statement. No H1. Risks have no severity or mitigation owner. | CR-M11, CR-N1 |
| M-15 | **Plain language and glossary.** Add a glossary at the top: ECC, MATERIAL/STANDARD, REVIEW RESULT, task brief, Evidence section, bench copy, arms V and G, dispatchers, pass^k, PreToolUse/Stop. Use one term per concept (owner/user; gate/task gate; brief/task brief). Separate owner-machine observations (with date and command) from requirements. | CMP14, CMP15, CR-M12, IR-nit |
| M-16 | **Prerequisite 0.1.** Branch `fix/gate-plugin-dir-false-ask` may touch `groundwork_task_gate.py`, which task 2.4 also edits. Say why it must come first, and show its 16 bypasses are covered by tests. | CMP4, IR-nit |
| M-17 | **Altitude.** Move low-level numbers (6 KB cap, marker line, 200-call sample) from the design to `tasks.md`. | ZO16, IZ-L |

### Nits (batch into one edit pass)

- Replace informal wording ("the good parts", "Nobody used 'in case'", "UNKNOWN" in capitals, "fix 1 (PR #72)", "—" cell, "What it really does", "Same as above"). CR-N6, IR-nit 8-9.
- Number or demote headings consistently; prefix steps (D6.3, D7.4) to remove numbering clashes. CMP19, CR-N1, IR-M14.
- Align "disables and uninstalls" (proposal) with D6. CR-N2.
- Wrong citation: "never stores commands" comes from a comment in `groundwork_telemetry.py` (~line 78), not the usage-telemetry spec. CMP17.
- Use exact ranges: `merge_settings.py:300-303`; `gateguard-fact-force.js:1264-1274` with a full path. CMP24.
- Guard latency budget 300 ms is looser than the 164 ms baseline. CR-N4.
- `GIT_VALUE_OPTIONS` is already duplicated in `groundwork_task_gate.py:807` and `block_protected_push.py:76`. Mention it. CR-N5.
- Add a D7-step to task-number mapping. State `openspec validate --strict` slows under `NODE_USE_SYSTEM_CA=1`. CMP20.
- Align "per-session" (proposal) vs "per-turn" (spec); the `ADDED Requirements` header for a modified capability. CMP22, CMP23.
- Validation command (design line 177) omits `--runs-dir` that task 5.2 uses. IR-nit 11.
- The v2.2.3 detail (line 5) is not used by any decision; drop or verify. IR-nit 10.

## Items confirmed correct (do not re-check)

`install.sh:59-72`; `merge_settings.py:24,300-303`; `setup.sh:86,646-665`; `unmerge_settings.py:14,125-133`; `require_material_review.py:83,310-311` (`REVIEW_PATTERN` already matches `groundwork-code-reviewer`, so the gate needs no change); `groundwork_session_snapshot.py:6-7`; `mcp-health-check.js:19` loads `https`; `code-reviewer.md:4-5,29-111` (`model: sonnet`, tools `Read, Grep, Glob, Bash`); `groundwork_task_gate.py` `check_file` at 1165-1178 is a suitable place for the config ask; token arithmetic 6,195 + 1,812 = 8,007; 68 ECC agents; the 17 personal agents exist.

## Unverified (no stage could run commands)

- `claude plugin uninstall --keep-data` exists, and its default.
- `claude plugin list --json` exists.
- `claude plugin` commands honor `CLAUDE_CONFIG_DIR`.
- ECC `standard` profile enables each hook as listed.
- The benchmark numbers (20/20, 79,133 tokens, 7,531 ms), the Gateguard block counts, and the location of the `vg-2.5.0-r1b` baseline data.
- Branch `fix/gate-plugin-dir-false-ask` exists as described.
- Default transcript retention (affects the 90-day usage claim).

Cheapest way to close these: one session runs `claude plugin uninstall --help`, `claude plugin list --json`, and a throwaway `CLAUDE_CONFIG_DIR` test, and records the output in the design.

## Traceability matrix

Key: ZO = zoom_out_report, CMP = comprehension_report, CR = critic_report (B/M/N), IZ = intermediate_zoom_out_report (A-L), IR = implementation_readiness_report (B/M/nit).

| Consolidated | ZO | CMP | CR | IZ | IR |
|---|---|---|---|---|---|
| A1 backup and key removal | 3 | 1 | B1, M3 | A | B1, M6 |
| A2 rollback, opt-out | 2, 3, 14 | 2 | M1, M2 | A | B2, M5 |
| A3 phase order, config-dir isolation | 3 | 4 | M3 | B | B4, M8 |
| A4 validation plan | 1, 4 | 6 | B2, M7 | C | B3 |
| A5 no-verify guard | 6 | 3 | M5 | F | B5 |
| A6 ECC-text cleanup | 9 | 10 | M4 | E | B6 |
| A7 token totals | 10 | 5 | M6 | H | M1 |
| A8 reviewer contract | 8 | 8 | M5, N3 | I | M4 |
| M-1 security reviewer | - | 12 | M9 | J | - |
| M-2 config-protection | 7 | 7 | M5 | G | M3 |
| M-3 migration failures | 11 | 11 | M3 | K | M5 |
| M-4 premise re-test | 12 | - | - | D | - |
| M-5 inventory | 5 | 9 | M5 | - | M13 |
| M-6 numbers and sources | 13, 15 | 14, 16 | M7, M8, M13 | L | M12, M13 |
| M-7 token margin | 13 | - | M10 | L | nit |
| M-8 report command | - | 5 | - | - | M2 |
| M-9 phase stability, tests | - | - | - | - | M8 |
| M-10 file scope | - | 21 | - | - | M7, M9 |
| M-11 design vs tasks | - | - | - | - | M10 |
| M-12 goal wording | - | 18 | - | - | M11 |
| M-13 promised work, no task | - | 13 | N3 | L | M7 |
| M-14 structure | - | - | M11, N1 | - | - |
| M-15 glossary, language | - | 15 | M12 | - | nit |
| M-16 prerequisite 0.1 | - | 4 | - | - | nit |
| M-17 altitude | 16 | - | - | L | - |
| Nits | 15-16 | 17-25 | N1-N7 | L | nits |

## Suggested next step

Edit `design.md` and `tasks.md` for A1-A8 first (they are linked: A1-A3 are one rewrite of D6/D7), then M-1 to M-5. Re-run Stage 9 once on the edited plan. Do the CLI check above first, because three Blockers (A1, A2, A3) depend on its answers.
