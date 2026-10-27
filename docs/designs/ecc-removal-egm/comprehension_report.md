# Goldfish Review Report (Comprehension lens)

**Target:** `/Users/ashmin/projects/ai-projects/groundwork/openspec/changes/replace-ecc-with-groundwork-core/design.md` (lines 1-185)
**Implementation plan used:** `tasks.md` in the same folder (design has no plan section)
**Method:** two independent naive-reader passes (A and B), merged and deduplicated. Reviewers could not run shell commands. Claims about what ECC hooks do (design lines 78-93) were checked only against hook IDs and matchers in `hooks.json`, not against the ECC hook scripts.

## Verdict

A naive reader could not re-implement this from the documents alone. Most of the behavior lives in the four spec files, not in `design.md`, and the design never says which document is the contract. Three places are internally inconsistent (rollback, task order, telemetry boundary). Several measurements cannot be reproduced.

Severity counts: **6 Blocker, 9 Major, 10 Nit**.

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. Settings-key removal has no defined mechanism - Severity: Blocker
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 143, 145-146 (D6 step 3 and rollback); `tasks.md` 6.2, 6.3; `specs/ecc-independence/spec.md` lines 15, 19
* **Discrepancy Description:** Step 3 says "remove the three settings keys through `merge_settings.py`". The keys are never named in the design. They appear only in the spec: `enabledPlugins["ecc@ecc"]`, `extraKnownMarketplaces.ecc`, `pluginConfigs["ecc@ecc"]`. `merge_settings.py` only adds keys today (it handles only `pluginConfigs["ecc@ecc"].options.hook_profile`, lines 24 and 300-303) and has no remove mode. Task 6.3 deletes the ECC code from that same file. It is unclear whether the removal lives in `merge_settings.py`, `unmerge_settings.py`, or a new script. It is also not stated whether `claude plugin uninstall` already removes some of the keys, which would make the step partly a no-op. The claim that `merge_settings.py` takes a backup first (line 143) was not verified.
* **Rationale & Recommendation:** Name the three keys in the design. Name the one script, flag and function that removes them, and the order: backup, uninstall, marketplace removal, settings edit. State what happens if one step fails after another succeeded. State how ECC is detected (`claude plugin list | grep` as in `install.sh:68`, or reading `settings.json`); the two differ for a plugin present in settings but not installed.

### 2. Rollback and opt-out are contradictory or circular - Severity: Blocker
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 141, 145-146, 169; `specs/ecc-independence/spec.md` lines 15, 29-34
* **Discrepancy Description:**
  * Line 146 offers two rollback mechanisms ("a small new flag `merge_settings.py --ecc`, or the restored settings backup"). The flag has no defined behavior (key already exists? does it also restore `enabledPlugins` and the marketplace entry?).
  * Line 141 says the plugin data dir is "kept by default: we pass `--keep-data`". If it is the default, passing the flag is redundant; if the flag is needed, it is not the default. No source shows `claude plugin uninstall` has this flag. The "plugin's own state" restored by rollback is undefined, and it is a different set from the "data outside the plugin" paths in spec lines 29-34.
  * Line 169 says rollback includes re-running `install.sh` with `GROUNDWORK_KEEP_ECC=1`. That flag leaves ECC as it is (spec line 15); it cannot reinstall ECC. The sentence is wrong or means something else.
  * `GROUNDWORK_KEEP_ECC=1`: not stated whether it is read from the environment or settings, or which of `install.sh`, `setup.sh`, `groundwork update` honor it. `groundwork update` is named in the spec but defined nowhere and has no task. Task 6.3 still removes `hook_profile` handling, which conflicts with "ECC and its settings keys are left exactly as they were".
  * The rollback command pins `affaan-m/ECC#v2.2.1` as a literal; `install.sh:65` has an override (`GROUNDWORK_ECC_REF`). Not stated whether rollback honors it. Rollback needs network and the tag; the Risks section (line 161) calls it "one command" but D6 shows two joined by `&&`.
* **Rationale & Recommendation:** Pick one rollback mechanism and specify it. Define `--keep-data` precisely (default or flag, and what it keeps). Fix line 169. Define `GROUNDWORK_KEEP_ECC` scope, source and effect on `--verify`. Either define `groundwork update` or remove it from the spec.

### 3. No-verify guard: scope and flag semantics are open - Severity: Blocker
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 78, 110, 116-117; `specs/git-integrity-guards/spec.md` (no-verify requirement, line 38)
* **Discrepancy Description:**
  * Line 116 says reuse the git option parser "for `push`". That parser is built around push detection (`_git_invocation`, `GIT_VALUE_OPTIONS`, `push_positionals`). The spec requires blocking `commit`, `merge`, `rebase`, `cherry-pick` and `am`. The design does not say how the push-oriented flow is extended, or whether the check runs before or after the existing push-only early exits.
  * `-n` means different things: `push -n` is `--dry-run`, `merge -n` is `--no-stat`, `am -n` differs again. The spec says `commit -n` only; the design is silent on the others, and on whether `push -n` must stay allowed.
  * Not addressed: `--no-verify=...` forms, case-insensitive `core.hooksPath` (git config keys are case-insensitive), `--config-env`, `GIT_CONFIG_*` env vars, `git config core.hooksPath`, aliases, and invocation inside `sh -c`, `xargs`, `eval` or heredocs.
  * The fail-closed rule ("deny when it cannot parse a command that contains `--no-verify` or `core.hooksPath`", spec line 38) is not in the design. It can conflict with the "ordinary commits" scenario where `git commit -m "fix: no-verify docs"` must run. "Cannot parse" is undefined.
  * The deny message is "say to fix the failing check instead"; exact text is not given, so tests cannot assert on it.
  * `tasks.md` 2.1 tests `commit -n` and `-an`, but not `merge`, `rebase`, `cherry-pick`, `am`.
  * The claim "no Groundwork hook matches (grep of `hooks/*.py`)" (line 78) shows no recorded grep or result.
* **Rationale & Recommendation:** Add a table: git subcommand x flag forms that deny, and forms that must be allowed. State fail-closed scope precisely. Add test cases to task 2.1 for each row. Record the grep command and its output.

### 4. Task order is impossible: bench migration is used before it is built - Severity: Blocker
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 151-156 (D7 steps 3-4); `tasks.md` 5.1, 5.2, 6.2, 6.5, 3.3
* **Discrepancy Description:** D7 measures the result in the bench copy (step 3) before the migration is shipped (step 4). Task 5.1 says "migrate ECC off there only" but the migration code is built in 6.2 and tested in 6.5. It is not said whether 5.1 uses manual commands or the migration script. If manual, the migration code path is never what was measured. Tasks 3.3 and 6.2 both edit `install.sh` with no stated order. How `install.sh` targets a different config dir is not stated (no variable named; `<config dir>` on lines 117 and 122 is undefined). Task 0.1 (branch `fix/gate-plugin-dir-false-ask`, "16 review-found bypasses") is described as "unrelated to ECC" (line 152) yet gates this work, and may touch `groundwork_task_gate.py`, the same file task 2.4 edits.
* **Rationale & Recommendation:** Reorder so the migration (6.2) exists before 5.1, or state that 5.1 is manual and add a later check that the real migration reaches the same end state. Define the config-dir variable. Say why 0.1 must come first, or move it out.

### 5. Telemetry token totals: turn boundary, de-duplication and record shape undefined - Severity: Blocker
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 134-137 (D5); `specs/usage-telemetry/spec.md`; `tasks.md` 4.2, 4.3
* **Discrepancy Description:**
  * D5 says to read `usage` "after the turn's prompt marker (`groundwork_shared.mark_turn_start`)". That function (`groundwork_shared.py:79`) takes `session_id`; its only caller is `groundwork_reply_check.py:148`. The telemetry hook finds the turn through `current_turn`/`is_human_prompt` (`groundwork_telemetry.py:228-244`). The spec says "since the turn's prompt". Three different boundary rules are implied.
  * A transcript can hold several lines for one API response (streamed chunks, repeated `message.id`). The doc does not say to de-duplicate, nor how `requests` is counted (assistant line with `usage`, or unique message id). Sidechain (subagent) messages are not addressed.
  * Where the new fields go is not stated: top level or inside the `observed` object (`groundwork_telemetry.py:43`, schema 2), and whether the schema version changes. Behavior for a turn with a transcript but no assistant usage (zeros or absent) is not stated.
  * "Never message text" (spec line 4) conflicts with the existing hook, which reads text for outcome parsing (`outcome_from_text`, `status_paragraph`). Scope the rule to the new code.
  * "Same rule as fix 1 (PR #72)" (line 137) refers to an unnumbered item; commit `5618a88` is a different area.
  * The report command is `groundwork usage` in the spec "or the existing report command" in task 4.3; its name and period flags are not given. `tests/test_usage.py` is named as if it exists.
  * Line 135 says "the Stop hook" but the file has both `build_tool_record` (per tool call) and `build_record` (per turn); not said which to extend.
* **Rationale & Recommendation:** Pick one turn-boundary function (reuse `current_turn`). State de-dup by `message.id`, the `requests` definition, sidechain policy, field placement and schema version, and zero-usage behavior. Name the report command and flags. Replace "fix 1 (PR #72)" with a real description.

### 6. Validation criteria cannot be measured or reproduced as written - Severity: Blocker
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 37-45, 55, 154, 163, 175-177, 185; `tasks.md` 1.1, 1.2, 5.2, 5.3, 8.4
* **Discrepancy Description:**
  * "PreToolUse p90 <= 500 ms": not stated whether per hook, summed per call, or max per call; denied or failed hooks have no `hook_success.durationMs`. The baseline (7,531 ms) came from "this session's transcript" (line 37), but task 1.2 measures from `vg-2.5.0-r1b` benchmark transcripts: two baselines for one number. The "164 ms Groundwork and others" figure mixes vendors.
  * The slowdown is attributed to `NODE_USE_SYSTEM_CA=1` whose source is UNKNOWN (settings say `0`, session carries `1`; which settings file and key is not given). The bench environment may not carry `1`, so the timing test could pass without proving anything. Nothing says to verify the variable is set during the bench run. Any other Node-starting hook keeps the cost; no remedy is given.
  * Accuracy criteria: "correct" has no grader or rubric; the 20 fixed cases are not described; "Evidence section" detection is unstated; the baseline Evidence rate is never recorded (only 20/20, 79,133 tokens and 3 requests); whether "input tokens" is summed over 3 requests or per request is unstated.
  * `--repeats 1` on a stochastic model with a median threshold is noisy. Task 5.3 says only "stop" on failure, with no rerun policy. The design cites pass^k (line 105) but does not use it.
  * `bench.run` lives on a parked branch (`feat/m2-question-evidence`, line 55); no task checks it out or merges it. Line 177 omits `--runs-dir` that task 5.2 uses. "G pointed at the bench copy" has no mechanism (env var or config dir). Whether `~/gw-bench/groundwork` contains ECC is assumed.
  * Token targets: "Custom agents <= 2.5k (from 8.0k)" is derived (6,195 + 1,812 = 8,007), and includes ~340 skill-name tokens that are not agents. "Total <= 59k (from 65.1k)" leaves 0.4k slack after removing 6.5k; the new reviewer agent description is not budgeted. The `/context` measurement does not say which directory or config dir it ran in.
* **Rationale & Recommendation:** Define each metric (unit, aggregation, source field, denominator). Record all baselines in one place. Check the env variable in the bench run. Add a rerun or pass^k rule. Say how to obtain `bench.run` and point G at the bench copy. Budget the new agent.

### 7. Config-protection "ask" list is open-ended - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 79, 117; `specs/git-integrity-guards/spec.md` (line 27); `groundwork_task_gate.py:1165`
* **Discrepancy Description:** The list of "known config" files is "for example" in the spec and absent from the design. ECC's own list is not cited. `pyproject.toml` is excluded with no verifiable reason. `.flake8`, `setup.cfg`, `tox.ini`, `.pylintrc`, `mypy.ini`, `.pre-commit-config.yaml`, `.editorconfig` are neither in nor out. Not stated: glob and basename matching, case sensitivity, directory depth, definition of "existing" (on disk at hook time), symlinks, `MultiEdit` on a new file, whether the kill switch `GROUNDWORK_TASK_GATE=off` disables the ask, and the ask wording. Bash edits (`sed -i ruff.toml`) bypass an Edit-tool ask; the doc is silent on accepting that. The 300 ms budget test ("200 sample calls") does not define the sample.
* **Rationale & Recommendation:** Give the exact list and matching rule in one place, state the Bash gap as accepted or covered, and define the sample for the timing test.

### 8. Reviewer agent contract is described by reference to ECC - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 99-101, 120-125; `tasks.md` 3.1, 3.4, 8.2; `specs/code-review-agent/spec.md` lines 8, 19, 26, 29
* **Discrepancy Description:** The "marker line in the frontmatter" has no key or text, yet install, uninstall and tests depend on it. The `REVIEW RESULT` block format is not defined in this change; it exists in `rules/output-contract.md:46-51` and is parsed at `require_material_review.py:93,336`, but the design implies a new contract and does not cite it. Severity scale is only "CRITICAL and HIGH are MUST FIX"; MEDIUM and LOW are undefined. The ">80% confident" rule (ECC `code-reviewer.md:27,33`) is not stated. The 6 KB cap forces cuts, but ECC's checklist (lines 113-258), "Prompt Defense Baseline" (line 8), "Project-Specific Guidelines" (line 299) and "v1.8 addendum" (line 312) are not assigned keep or drop. The Python section "covering the checks of ECC `python-reviewer`" lists no checks, and that file was not supplied. Spec says tools (Read, Grep, Glob, Bash) are "read-only", but Bash is not. The gate matches `(?<![a-zA-Z])review` on the agent name (confirmed for `groundwork-code-reviewer`); the design does not say it matches `subagent_type` on an `Agent` call. `model: sonnet` (confirmed `code-reviewer.md:5`): alias or pinned id not said. Task 7.1 changes gate guidance text (`require_material_review.py:310-311`) with no test.
* **Rationale & Recommendation:** Include the agent's actual rules in the change (or a fixed list of kept sections), define the marker, the severity scale, and point to the `REVIEW RESULT` contract. Fix the "read-only" wording or restrict Bash.

### 9. Hook inventory is hard to verify - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 5, 74, 78-93, 161
* **Discrepancy Description:** Line 74 says sub-hooks of "the three dispatchers" are listed individually, but the dispatchers are never named (`pre:bash:dispatcher`, `post:dispatcher:sync`, `post:dispatcher:async` in `hooks.json`). Sub-hook IDs such as `pre:bash:block-no-verify` are not top-level IDs in `hooks.json`, so a reader cannot find them. Row 92 packs 16 IDs into one cell with one reason; some IDs could not be matched. The completeness claim "every hook is in the inventory" (line 161) is therefore unverified. Line 93 says four hooks are OFF in the standard profile with no source for the profile table. Line 80 cites `gateguard-fact-force.js:1264-1274` without a directory. "Blocked this session 5 times" cannot be identified later. The deny list (`settings deny list`) is not named. The 25 MB / 1,149 observations / 9 MB figures have no command. `mcp-health-check.js:19` has no path.
* **Rationale & Recommendation:** Add the dispatcher names, full paths, and the profile source. Provide the command that generated the inventory so it can be re-run.

### 10. Remaining ECC text is wider than the list and the check - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 46-54, 83, 181; `tasks.md` 6.x, 7.1; `specs/ecc-independence/spec.md` lines 44-48
* **Discrepancy Description:** The design lists `engineering-workflow.md` lines 3, 20, 21, 22, 25, 78, 92. The reviewers also found ECC mentions at lines 15, 60, 66 ("curated ECC reviewers") and 68 ("ECC skills"). Other ties missing from the list: `uninstall.sh:26,139`, `install.sh:5-7,43,56`, `setup.sh:14,83`, `scripts/check_routing.py:14`. The check `grep -rn 'ecc:' rules hooks playbooks` finds only `ecc:`, so prose telling Claude to use "ECC reviewers" passes while violating the spec. The spec greps the installed tree (`rules/groundwork/*.md`, `groundwork/playbooks/*.md`); the command uses repo-relative paths, and the table says "installed tree". `/ecc:` is a substring of `ecc:` and adds nothing. Replacements for `ecc:planner` and `ecc:tdd-guide` are not named (task 7.1 says "Groundwork's reviewer and the task brief").
* **Rationale & Recommendation:** Generate the list from a grep (case-insensitive `ecc`) rather than hand-listing lines, and run the same grep on the installed tree.

### 11. Migration failure handling and detection - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 139-149; `specs/ecc-independence/spec.md`
* **Discrepancy Description:** The only failure case described is rollback. Nothing covers uninstall succeeding but marketplace removal or settings edit failing, partial states, or idempotent re-run. Which config directory is targeted and how `claude` is pointed at it is not stated.
* **Rationale & Recommendation:** Specify the state machine (steps, failure at each, re-run safety) and test each.

### 12. Security reviewer is dropped with no replacement in the product - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 101, 164; `tasks.md` 8.2; `ecc-independence` health-check requirement
* **Discrepancy Description:** The ECC security reviewer is dropped in favor of the owner's personal agent from another repo (`claude-toolkit`), which Groundwork does not install. A fresh machine has no security reviewer, yet task 8.2 requires "security reviewer plus code reviewer". Line 164 promises an advisory `--doctor` check, but no spec requirement or task covers it.
* **Rationale & Recommendation:** Either ship a minimal security reviewer or state that 8.2 is owner-machine-only. Add the `--doctor` requirement and task, or delete the promise.

### 13. Promised work with no task - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 103, 105; `tasks.md` 7.2
* **Discrepancy Description:** The "optional mode note in the review rule", the pass^k consistency metric in `docs/VALIDATION.md` and the pinned `npx ecc-agentshield@<version>` command are promised, but no task creates them and no version is chosen. `CREDITS.md` and `THIRD_PARTY_NOTICES.md` handling is inconsistent between proposal and tasks. Marking `ecc-capability-policy` "superseded" (task 7.2) does not say how.
* **Rationale & Recommendation:** Add tasks or remove the promises. Pick the AgentShield version.

### 14. Owner-specific facts mixed with product requirements - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 5, 33, 80, 91, 106-107, 185
* **Discrepancy Description:** "This Mac", "this session", "the owner's manual prompts" and the owner's personal agent file refer to one machine and one conversation. A later reader cannot tell which statements are requirements and which are observations. Claims about the "Browser pane", "Claude-in-Chrome" and desktop terminal tabs have no source. The numbers in the measured table cannot be reproduced without the command and the directory used.
* **Rationale & Recommendation:** Separate "evidence from the owner's machine" (with date and command) from requirements.

### 15. Undefined terms and acronyms - Severity: Major
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** throughout; first uses at lines 3, 6, 55, 80, 87, 92, 102-105
* **Discrepancy Description:** Load-bearing terms with no gloss: ECC (never expanded), MATERIAL and STANDARD, REVIEW RESULT, "the brief"/"task brief", Evidence section, evidence policy, "Groundwork 2.0 decision D4", Stop-time reply check, bench copy (defined only by task 1.1), arms V and G (defined once at line 55), `hook_success.durationMs`, Claude Code hook events (PreToolUse, PostToolUseFailure, PreCompact, Stop). Mentioned-only terms: Gateguard, AgentShield, santa-method, eval-harness, pass^k, Plan Canvas, homunculus. "Owner" and "the user" are used interchangeably. The motivation is only "see proposal.md" (line 3).
* **Rationale & Recommendation:** Add a short glossary at the top of the design with the load-bearing terms and links.

### 16. Cited spec and file lines not checked - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 6, 113, 124
* **Discrepancy Description:** The path `groundwork-2-enterprise-sre/specs/ecc-capability-policy/spec.md:4-8` and the v2.2.3 claim ("five agents byte-identical", commit `25278e7`) were not verified (only v2.2.1 is on disk). "The five agents" are not explicitly mapped to the table. Line 124 ("the gate reads the verdict deterministically") implies a new contract when the gate already parses it.
* **Rationale & Recommendation:** Verify or mark as UNVERIFIED.

### 17. Wrong citation for "never stores commands" - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 87-88
* **Discrepancy Description:** The claim is attributed to the usage-telemetry spec, which has no such requirement (it forbids reading message text and secrets). The real source is a comment in `groundwork_telemetry.py` (~line 78, "must never read `tool_input.command`").
* **Rationale & Recommendation:** Cite the right file.

### 18. "Lose no protection" goal is not testable - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 58-63
* **Discrepancy Description:** A negative cannot be tested directly; the only evidence is the inventory, which is incomplete (finding 9).
* **Rationale & Recommendation:** State it as "every inventory row marked KEEP has a Groundwork test".

### 19. Step numbering clash - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 142-149, 151-156, 167-169
* **Discrepancy Description:** D6 steps and D7 steps are both numbered; "steps 1 and 2 are normal reverts" and "step 4" in the Migration Plan are ambiguous.
* **Rationale & Recommendation:** Prefix (D6.3, D7.4).

### 20. Section 7 and 8.1 `openspec validate --strict` not in design - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** `tasks.md` 7, 8.1; design D7
* **Discrepancy Description:** Tasks run `openspec validate ... --strict`, which the design never mentions, and which is slow under `NODE_USE_SYSTEM_CA=1` (line 163). No timeout guidance. D7 steps 4-5 do not map to task numbers.
* **Rationale & Recommendation:** Add a mapping table D7 step to task numbers.

### 21. Task 6.4 `--verify` source of hook list - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** `tasks.md` 6.4
* **Discrepancy Description:** `setup.sh --verify` must check "every registered hook entry", a new check. Where the expected list comes from (`merge_settings.py` or a constant) is not stated. `unmerge_settings.py` ("keep able to clean an old key") has no test task.
* **Rationale & Recommendation:** Name the source of truth for the list and add the test.

### 22. Docs location - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** `tasks.md` 1.1
* **Discrepancy Description:** Output goes to `docs/designs/ecc-removal-baseline.md`; `docs/designs/` is untracked and its relation to the change folder is unexplained. Spec says "agent installed to `agents/`" while the repo path appears only in task 3.1. Proposal says "per-session token totals" but the spec says per-turn.
* **Rationale & Recommendation:** Align wording across proposal, spec and tasks.

### 23. Spec header style - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** `specs/usage-telemetry/spec.md`
* **Discrepancy Description:** The delta for an existing capability is headed `ADDED Requirements` with no Purpose section; the proposal calls it a modified capability.
* **Rationale & Recommendation:** Use consistent delta headers.

### 24. Citation line precision - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 49, 80
* **Discrepancy Description:** `merge_settings.py:300` is actually 300-303; `gateguard-fact-force.js:1264-1274` has no directory and the range looks odd for the file.
* **Rationale & Recommendation:** Use exact ranges with full paths.

### 25. Reference to existing facts that were confirmed (no action) - Severity: Nit
* **Reviewer Lens:** `comprehension`
* **Affected Scope:** design lines 49, 52, 121, 123
* **Discrepancy Description:** Confirmed correct: `install.sh:59-72`, `merge_settings.py:300-303`, `setup.sh:86,646-665`, `unmerge_settings.py:14,125-133`, `require_material_review.py:83` and `310-311`, ECC `code-reviewer.md:4-5`, three dispatcher hooks in `hooks.json`, `mcp-health-check` registered with matcher `.*` for pre and post.
* **Rationale & Recommendation:** None. Listed so these are not re-checked.
