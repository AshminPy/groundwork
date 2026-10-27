# Goldfish Review Report

**Target:** `/Users/ashmin/projects/ai-projects/groundwork/openspec/changes/replace-ecc-with-groundwork-core/design.md` (`lines 1-185`)

Reviewers: egm-design, egm-structural, egm-style (one instance each). Reviewers read files only; they could not run commands. Items they say they did not verify are listed at the end.

Counts: 2 Blocker, 13 Major, 14 Nit.

## Prioritized Findings (Blockers -> Major -> Nits)

### B1. Migration backup is taken after ECC is already removed, so rollback does not restore ECC - Severity: Blocker
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Lines 139-149, 169, 180` (D6 steps, rollback, migration test)
* **Discrepancy Description**: Step 1 (`plugin uninstall`) and step 2 (`marketplace remove`) change `settings.json` first. Step 3 "backs up first" only after that. The backup therefore has no `enabledPlugins["ecc@ecc"]` and no `extraKnownMarketplaces.ecc`. Rollback step 2 says the restored backup does the same job; it does not. `merge_settings.py` has no backup code (grep for `backup|.bak` finds only `GROUNDWORK_DENY`). `install.sh:134` points at `setup.sh`'s `latest_backup`, so "which backs up first" is wrong or unattributed. The test at line 180 says "byte-identical" without saying identical to which state. There is also no ordering rule: today `install.sh` installs ECC at step 1 and Groundwork hooks at step 3, so a mid-run failure can leave neither in place.
* **Rationale & Recommendation**: Make the backup a named step 0, before any ECC removal. Order the migration: install new guards and reviewer agent, run `setup.sh --verify`, abort on failure, and only then remove ECC. State the exact state the test restores to.

### B2. Accuracy gate cannot detect the regressions it is meant to cover - Severity: Blocker
* **Reviewer Lens:** `egm-design`, `egm-style`
* **Affected Scope:** `Lines 129-132, 154, 175-177` (D4, Validation)
* **Discrepancy Description**: D4 mitigates "a quality drop the benchmark does not catch" using that same benchmark. Baseline is already 20/20 (ceiling effect). `--repeats 1` gives no variance estimate. The benchmark appears to be Q&A (reviewer's inference; bench code not read), so it does not exercise Edit/Write, the first-edit gate, `--no-verify`, config edits, or the reviewer round trip. The baseline `vg-2.5.0-r1b` is an older run, not a same-day control. "Median input tokens below 79,133" implies about 8% savings with no noise bound. "Evidence rate" (line 130) and "share of G replies with an Evidence section" (line 177) are two names for one metric, and the baseline number is not given. The revisit trigger ("a real incident") has no owner or date.
* **Rationale & Recommendation**: Re-run the baseline arm in the same window. Use at least 3 repeats and state a tolerance. Add an edit-and-guard scenario set to task 5.2 and a read-before-edit measure (share of Edit calls preceded by a Read of the same file). Define the evidence metric once with its baseline value. Name an owner and date for the revisit.

### M1. Rollback is inconsistent between design and tasks - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-structural`, `egm-style`
* **Affected Scope:** `Lines 144-147, 161, 169`
* **Discrepancy Description**: Rollback step 2 uses `merge_settings.py --ecc`. Task 6.3 removes ECC handling from `merge_settings.py`, and no task adds the flag. Line 146 hedges ("or the restored settings backup does the same"). Line 169 reverses the migration with `GROUNDWORK_KEEP_ECC=1`, but that flag only leaves ECC alone and the install step is removed (task 6.2), so it cannot reinstall. Line 161 says rollback is "one command"; D6 lists two commands plus a settings step. Rollback needs network and the GitHub tag, while uninstall deletes the local cache. Line 169 "steps 1 and 2 / Step 4" does not say these are D7 steps.
* **Rationale & Recommendation**: Choose one rollback mechanism and add the matching task. Keep a copy of `~/.claude/plugins/cache/ecc/ecc/2.2.1` until the owner accepts the change. Fix line 161 to say "two commands". Write "D7 step N".

### M2. "Data dir kept by default: we pass `--keep-data`" contradicts itself, and the flag is unverified - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-structural`, `egm-style`
* **Affected Scope:** `Lines 141-142, 162`
* **Discrepancy Description**: If kept by default, the flag is redundant; if the flag is needed, the default is delete. No evidence that `claude plugin uninstall --keep-data` exists (not verified by any reviewer). ECC logs and state live elsewhere (`~/.claude/session-data`, `~/.local/share/ecc-homunculus`, per the spec), so "rollback restores the plugin's own state" says little.
* **Rationale & Recommendation**: Cite `claude plugin uninstall --help` output, or make task 6.5 verify the flag before any migration code. State the real default once.

### M3. Migration section is a pointer, and failure cases are missing - Severity: Major
* **Reviewer Lens:** `egm-structural`, `egm-design`
* **Affected Scope:** `Lines 167-169`
* **Discrepancy Description**: No ordered procedure. Not covered: half-done run (plugin removed, settings not edited); ECC re-added by hand after migration; `GROUNDWORK_KEEP_ECC=1` with new guards (two overlapping `--no-verify` blocks); multiple config dirs; project-scope `enabledPlugins["ecc@ecc"]` in other repos (will warn); sessions running during migration hitting a deleted plugin path; `uninstall.sh` behaviour for the new agent and its "ECC left untouched" text (`uninstall.sh:26,139`). "Three settings keys" (line 143) are not named; per the ecc-independence spec they are `enabledPlugins["ecc@ecc"]`, `extraKnownMarketplaces.ecc`, `pluginConfigs["ecc@ecc"]`, and `merge_settings.py:300` writes only the last.
* **Rationale & Recommendation**: Write numbered migration steps with a verification command after each, a partial-failure recovery path, and a note to close running sessions first. Name the three keys and say which tool writes each.

### M4. ECC-text cleanup list is incomplete and the grep check would miss real references - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-structural`
* **Affected Scope:** `Lines 46-54, 181`; task 7.1
* **Discrepancy Description**: `rules/engineering-workflow.md` has ECC references at lines 3, 15, 20, 21, 22, 25, 60, 66, 68, 78, 92. Design and task 7.1 list 3, 20, 21, 22, 25, 78, 92. Lines 60, 66, 68 say "ECC reviewers" / "ECC skills" without `ecc:`, so `grep -rn 'ecc:'` misses them, and they would still point Claude at ECC. Other uncovered mentions: `install.sh:5-7,43,56`, `uninstall.sh:26,139`, `hooks/block_protected_push.py:4`, `hooks/require_material_review.py:8,18`, `hooks/groundwork_telemetry.py:108`, `scripts/check_routing.py:14`. Lines 20-21 tell Claude to use `ecc:planner` and `ecc:tdd-guide`; the design never says what replaces them. Outside the repo, `~/.claude/CLAUDE.md:9` and `~/.claude/rules/behavior.md:157` still name ECC and `/ecc:save-session`.
* **Rationale & Recommendation**: Replace the line list with a grep-defined scope: `grep -rniE '\becc\b|ecc:'` over docs, rules, hooks, scripts, playbooks, with an allow-list (CHANGELOG, CREDITS, THIRD_PARTY_NOTICES, migration code). State replacements for the planner/tdd steps. List the personal-rule files as manual follow-ups.

### M5. Protections ECC provides that the plan weakens or drops silently - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Lines 60-100` (inventory), spec `git-integrity-guards`, task 3.1
* **Discrepancy Description**:
  * Prompt Defense Baseline: `code-reviewer.md:8-15` has a prompt-injection block. The new reviewer has `Bash` and reads untrusted diffs. Task 3.1 omits this block.
  * config-protection: ECC matches case-insensitively (`config-protection.js:97-104`) and treats a dangling symlink as an existing config (line 112). Its protected set is lines 22-96. The new spec says "for example ..." and has no case or symlink behaviour. `ask` becomes a denial in headless `-p` runs (`groundwork_task_gate.py:1097`), so bench and CI act as a block.
  * block-no-verify: the spec denies an unparseable command that contains `--no-verify` or `core.hooksPath` (spec line 38). The design omits this. `block_protected_push.py` fail-closes only on `_mentions_push` (about lines 876-877, 1009-1010) and `continue`s on non-push git commands (947-957). D2 "reuse its parser" understates the new deny paths and their tests.
  * The ported reviewer range `code-reviewer.md:29-111` includes a false-positive list with Express/React/TypeScript examples (81-108); "drop React/Node checklists" must cover it.
  * Line 80 gateguard: ECC's destructive pattern is `drop table|delete from|truncate|dd if=` (line 56). SQL run via `python -c` or similar is covered by neither side; "already asked/denied" should name this limit.
* **Rationale & Recommendation**: Derive the protected-config list from ECC's set and add a test that the new list is a superset. Add case and symlink scenarios. Port or explicitly justify dropping the prompt-defense block. Add the unparseable `--no-verify` rule and a "fix: no-verify docs" false-positive test to the tasks.

### M6. D5 (token usage) does not match the telemetry code and skips real hazards - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Lines 134-137`
* **Discrepancy Description**: Design says tokens are read "after `groundwork_shared.mark_turn_start`". `groundwork_telemetry.py` does not import it; it uses its own `current_turn()` and `is_human_prompt()`. `mark_turn_start` is used in `groundwork_reply_check.py:41,146-148`. Not addressed: assistant entries repeat the same `usage` for each content block of one message (sum without de-duplicating by message id and request id will overcount); whether reviewer subagent tokens (sidechain or separate entries) are included, which is likely the largest cost; `build_record` returns `{}` for a conversational turn, so totals are also omitted there. D5 has no alternatives (for example other data sources).
* **Rationale & Recommendation**: Correct the reference. Specify de-duplication and a test for it. State whether subagent usage counts. State the conversational-turn behaviour. Add one line on why transcript parsing was chosen.

### M7. Hook-latency evidence is one session and its cause is unknown - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-style`
* **Affected Scope:** `Lines 33-45, 80, 112, 176`
* **Discrepancy Description**: The 7,531 ms p90 comes from one interactive transcript. The design says `NODE_USE_SYSTEM_CA=1` appears in that environment with unknown source. If bench config dirs lack it, ECC may not be slow there and the "from 7,531 ms" comparison cannot be tested in the bench. "Node 2-3 times per tool call" (line 112) has no count. "This session's transcript" and "blocked 5 times" (lines 33, 80) cannot be identified later; "restatements that changed nothing" is a judgement with no criterion.
* **Rationale & Recommendation**: Measure before and after in the launch path the owner uses, and record the variable's value per run. Give transcript ID/date. Cite the hook entries that match `.*` for the process count or drop the number. State the retry criterion ("retry text identical").

### M8. Usage evidence is weaker than presented - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Lines 13, 16-31, 108`
* **Discrepancy Description**: "90 days, 471 transcripts" assumes 90 days of retention; `~/.claude/settings.json` has no `cleanupPeriodDays` (default believed to be 30 days, not verified). "0 calls" is meaningless for rules, contexts, and slash commands, which are not Agent/Skill calls. "280+ other skills" (line 108) conflicts with 369 skills (line 13); 369 minus 3 used is about 366.
* **Rationale & Recommendation**: Record the earliest transcript date. Say what "used" means per kind of component. Use one skill count.

### M9. Dropped `security-reviewer` conflicts with the fresh-laptop argument - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Lines 101, 125, 164`; task 8.2
* **Discrepancy Description**: D3 rejects relying on personal agents because a fresh laptop would have none. Line 101 drops `security-reviewer` on that same reliance, with only an advisory `--doctor` line. Task 8.2 requires a "security reviewer plus code reviewer". Whether the owner's agent has "the same name" is unchecked (ECC's is namespaced `ecc:security-reviewer`).
* **Rationale & Recommendation**: Ship a security-review mode in the new reviewer, or state the gap as accepted and fix task 8.2.

### M10. Token pass criterion has almost no margin - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-structural`
* **Affected Scope:** `Lines 9-14, 175`
* **Discrepancy Description**: 65.1k - 6,195 - ~340 = about 58.6k. The limit "<= 59k" leaves roughly 0.3-0.4k for the new reviewer's description. The baseline is one fresh session with no stated run-to-run variance.
* **Rationale & Recommendation**: Measure variance over at least 3 baseline runs. Use a delta rule (for example "drops by >= 6.0k") or state headroom for the new agent description.

### M11. No Alternatives section, no Proposed Architecture, no Problem Statement - Severity: Major
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Lines 70-156`
* **Discrepancy Description**: The standard's Alternatives Rule requires evidence that other designs were rejected. Alternatives appear only inside D1, D2, D3, D6. D4 (slimmed gateguard), D5 (other token sources) and D7 (phase order) have none. Component layout and data flow of the four rebuilt parts are not shown; the problem is only in proposal.md and the Context bullets.
* **Rationale & Recommendation**: Add an "Alternatives Considered" table covering every decision, and a short "Proposed Architecture" subsection (hook and agent layout). Add a Problem Statement or point to proposal.md.

### M12. Undefined jargon and inconsistent terms hurt a non-native reader - Severity: Major
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Lines 74, 105, 116, 135`; also 14, 30, 68, 80, 83, 101, 104, 125, 127, 152
* **Discrepancy Description**: "dispatchers", "santa-method", "pass^k", "third shell parser", "prompt marker" are never explained. "Owner"/"user", "gate"/"gateguard"/"fact-forcing gate", "brief"/"task brief"/"per-branch brief", "This Mac"/"owner's disk" are mixed.
* **Rationale & Recommendation**: Add a one-line gloss at first use. Pick one term per concept.

### M13. Counts and sources inconsistent - Severity: Major
* **Reviewer Lens:** `egm-style`, `egm-design`
* **Affected Scope:** `Lines 5, 6, 13, 108, 111`
* **Discrepancy Description**: See M8 for the skill count. "Rebuild 4 parts" (line 111) does not name the four. "Five agents byte-identical in v2.2.3" and the v2.2.3 hook claims are not checkable from the supplied files (line 5).
* **Rationale & Recommendation**: Name the four parts once near the top. Cite the evidence for the v2.2.3 claims.

## Nits

### N1. Structure and headings - Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Lines 1-185`, `70-156`, `160-165`
* **Discrepancy Description**: No H1 title (starts at H2 "Context"). "Inventory" is an unnumbered H3 among numbered D1-D7. "Agents, skills and other parts" is a bare paragraph. Risks are arrow bullets with no severity, likelihood, or owner, and the security risks of the new guards are not stated (for example config-protection `ask` bypass through Bash `sed -i`; loss of config-protection as a control; prompt-injection exposure).
* **Rationale & Recommendation**: Add an H1, number or demote consistently, and turn Risks into a small table with severity and mitigation.

### N2. Wording differs between proposal and design - Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Line 149`, proposal.md:22
* **Discrepancy Description**: proposal says "disables and uninstalls"; design rejects `disable`.
* **Rationale & Recommendation**: Align the wording.

### N3. Placeholder and borrowed ideas without tasks - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** `Lines 103, 105, 122`
* **Discrepancy Description**: `<pinned version>` is a placeholder. Two-reviewer loop and pass^k are "borrowed" with no owner or task. An extra frontmatter key as an ownership marker is assumed to be ignored by Claude Code; line 122 "a marker line" gives no marker text.
* **Rationale & Recommendation**: Pick and record a real version. Drop the borrowed ideas or add tasks. Cover the frontmatter assumption in the task 3.3 round-trip test and give the marker text.

### N4. Guard latency budget looser than baseline - Severity: Nit
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** spec `git-integrity-guards` line 38
* **Discrepancy Description**: Budget is <= 300 ms; baseline p90 is 164 ms.
* **Rationale & Recommendation**: Consider a tighter bound.

### N5. Stale ECC comment and existing duplication not mentioned - Severity: Nit
* **Reviewer Lens:** `egm-design`, `egm-structural`
* **Affected Scope:** `hooks/groundwork_telemetry.py:108`, `hooks/groundwork_session_snapshot.py:6-7`, `Line 116`
* **Discrepancy Description**: The `ecc:code-reviewer` comment in telemetry is stale. `GIT_VALUE_OPTIONS` is already duplicated in `groundwork_task_gate.py:807` and `block_protected_push.py:76`, so D2's "avoids a third shell parser" is true but ignores existing duplication.
* **Rationale & Recommendation**: Include in the cleanup list; mention the existing duplication.

### N6. Subjective or informal wording - Severity: Nit
* **Reviewer Lens:** `egm-style`
* **Affected Scope:** `Lines 3, 6, 45, 67, 92, 93, 99, 101, 129, 137, 163, 164`
* **Discrepancy Description**: "the good parts", "what make reviews trustworthy", "npm/Express-centric", "several are no-ops here" (name which), "advisory, not a failure", "UNKNOWN" in capitals, "Nobody used 'in case'", "fix 1 (PR #72)", a "—" empty table cell (line 93), and a wordy line 3 and line 129.
* **Rationale & Recommendation**: Use plain, specific wording. Suggested: "keeping only the used parts"; "targets npm/Express projects"; "prints a warning and exits 0"; "unknown"; "features with no recorded use"; "the same rule as PR #72 (commit 5618a88)"; "n/a" in the empty cell; "Facts that shape the design:" for line 3.

### N7. Mixed figures for one fact - Severity: Nit
* **Reviewer Lens:** `egm-structural`
* **Affected Scope:** `Lines 5, 33-39, 112`
* **Discrepancy Description**: "about 6.5k tokens" (line 112) is 6,195 + ~340; stated in several places.
* **Rationale & Recommendation**: State the figure once and refer to it.

## Verified correct (by reviewers, from reading)
`install.sh:59-72`; `merge_settings.py:300-303`; `setup.sh:86` and `646-665`; `unmerge_settings.py:14` and `125-133`; `require_material_review.py:83` (`REVIEW_PATTERN`, matches `groundwork-code-reviewer`) and `310-311`; `code-reviewer.md:5` (`model: sonnet`); `mcp-health-check.js:19` loads `https`; `gateguard-fact-force.js:1264-1274`; `groundwork_task_gate.py` `check_file` at 1165 and `_git_destructive` at 820; `mark_turn_start` at `groundwork_shared.py:79`; 68 ECC agents; token arithmetic 6,195 + 1,812 = 8,007; no `input_tokens` in `hooks/`.

## Not verified by any reviewer
Existence of `claude plugin uninstall --keep-data`; ECC dispatcher sub-hook completeness; whether hook profile `standard` enables each ON/OFF flag as listed; default transcript retention; the benchmark code and numbers (baseline 20/20, 79,133 tokens, 7,531 ms); `agents/code-reviewer.md:29-111` content; the v2.2.3 claims.

## Process note
The harness flagged the design reviewer's output as containing a settings-json pattern and neutralized control tags. No instructions were found in it; it only discusses `settings.json` keys.
