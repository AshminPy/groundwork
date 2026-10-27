# Intermediate Zoom Out Report (Stage 8)

**Target:** `/Users/ashmin/projects/ai-projects/groundwork/openspec/changes/replace-ecc-with-groundwork-core/design.md` (lines 1-185)
**Reviewer lens:** `egm-zoom-out`
**Inputs:** zoom_out_report.md, comprehension_report.md, critic_report.md, plus spot-checks against the repo files.

## Verdict

- Architecture: GO. Removing ECC entirely is the right choice.
- Design as written: NO-GO until the seven minimum changes below are made.
- No Blocker shows the core choice is wrong. Every Blocker is about execution: backup order, migration order, validation, or guard detail.
- Why slimming ECC still loses: the agent and skill lists cost about 6.5k tokens per request, the `.*` hooks start Node on every tool call, and usage is about 100 calls in 90 days, almost all of them `code-reviewer`.
- Limit of this review: none of the four stages (including this one) could run commands. Hook behavior claims from the earlier reports were not re-run.

## Answers to the four questions

1. **Findings that change direction or scope.** None change the direction. Three change scope: rollback/migration order, the validation plan, and the width of the ECC-text cleanup.
2. **Does a Blocker mean the core choice is wrong?** No. Only the execution is wrong.
3. **Not covered by any stage:**
   - What `setup.sh make_backup` actually captures. If it skips `plugins/cache/ecc`, the offline rollback has nothing to restore.
   - Whether `claude plugin` honors the bench's separate config dir. If not, the bench uninstall hits the real machine.
   - A hook-by-hook coverage test. "Lose no protection" is a negative claim backed only by a hand-built inventory.
   - The contradiction between dropping the security reviewer and the "fresh laptop" argument used for the code reviewer.
   - How the new `ask` behaves in headless, subagent and bypass-permission runs.
4. **Go / no-go and minimum changes:** see the end of this report.

## Prioritized Findings

### A. Backup order and rollback are broken - Severity: Blocker
* **Affected Scope:** design D6 (lines 139-149), line 161, line 169.
* **Discrepancy:** The backup happens after the plugin is uninstalled and the marketplace removed, so a restored backup has no ECC keys. D6 step 3 says `merge_settings.py` "backs up first", but that script has no backup code (verified: no `backup` or `.bak` match). The backup is in `setup.sh:239` (`make_backup`). `merge_settings.py --ecc` is hedged and has no task. `GROUNDWORK_KEEP_ECC=1` cannot reinstall ECC, so line 169 is wrong. `--keep-data` is contradictory and unverified. Rollback needs network and an upstream tag, while uninstall deletes the local cache.
* **Recommendation:** Make the backup step 0, before any removal, and include `plugins/cache/ecc` and the marketplace clone. Make offline restore the primary rollback and the network command the fallback. Pick one mechanism and drop the `--ecc` flag if restore covers it. Name the three settings keys: `enabledPlugins["ecc@ecc"]`, `extraKnownMarketplaces.ecc`, `pluginConfigs["ecc@ecc"]`. Cite `claude plugin uninstall --help`.

### B. Phase order is impossible - Severity: Blocker
* **Affected Scope:** D7 steps 3-4; `tasks.md` 5.1, 6.2, 6.5.
* **Discrepancy:** The bench measures the migration before the migration code exists. Neither document says how `install.sh` or `claude` is pointed at the bench config dir.
* **Recommendation:** Build the migration first and measure that real path, or declare the bench run manual and add a check that the real migration reaches the same state. Prove `CLAUDE_CONFIG_DIR` isolation before any uninstall runs. Fix the order inside the migration: backup, install guards and reviewer, `setup.sh --verify`, then remove ECC.

### C. Validation plan cannot catch what it claims - Severity: Blocker
* **Affected Scope:** D4 and the Validation table, rows "Accuracy" and "Hook wait".
* **Discrepancy:** The accuracy check is 20 fixed cases, one repeat, against a baseline already at 20/20. It tests question answering, not edits, `--no-verify`, config changes or reviews. D4 names the benchmark as the mitigation for the risk it misses. "Input tokens" is undefined; the 79,133 figure may exclude cache reads. `bench.run` is on a parked branch. The 7.5 s hook wait came from one session with `NODE_USE_SYSTEM_CA=1`; the bench may not set it, so "p90 <= 500 ms" could pass without proving anything.
* **Recommendation:** At least 3 repeats on both arms with a stated tolerance. Add an edit-and-guard scenario set. Merge or pin the bench code. Define each metric once. Show that ECC-on reproduces the slow baseline in the same environment.

### D. "No partial install" premise is stale - Severity: Major
* **Affected Scope:** Context line 6, D1.
* **Discrepancy:** The premise comes from a September spec; today is late October.
* **Recommendation:** Re-test `skillOverrides` and `Agent(name)` deny rules on the current CLI and record the version. This is cheap. Removal likely still wins because of the hooks, but this is the central premise and should be re-tested, not inherited.

### E. ECC-text cleanup is wider than listed - Severity: Major
* **Affected Scope:** Context lines 46-54; task 7.1; Validation row "No ECC text".
* **Discrepancy:** `rules/engineering-workflow.md` mentions ECC at lines 3, 15, 20, 21, 22, 25, 60, 66, 68, 78, 92; the plan lists only 3, 20, 21, 22, 25, 78, 92. More references exist in `install.sh`, `uninstall.sh:26,139`, `hooks/block_protected_push.py:4`, `hooks/require_material_review.py:8,18`, `hooks/groundwork_telemetry.py:108`, `scripts/check_routing.py:14`. The check `grep 'ecc:'` is case-sensitive and needs a colon, so it misses prose.
* **Recommendation:** Replace the hand-built list with `grep -rniE '\becc\b'` over rules, hooks, scripts, docs and playbooks, with an explicit allow-list. Name what replaces `ecc:planner` and `ecc:tdd-guide` in the MATERIAL workflow steps. Update `uninstall.sh:139` ("ECC left untouched").

### F. No-verify guard is under-specified - Severity: Major
* **Affected Scope:** D2; `git-integrity-guards` spec.
* **Discrepancy:** Reusing `block_protected_push.py` is right (no third parser), but it is push-centric and `continue`s on other git commands. Missing: a table of subcommand/flag forms to deny and to allow; the fail-closed rule for unparseable commands (in the spec, not the design); a test for `git commit -m "fix: no-verify docs"`; `-n` semantics (`push -n` is `--dry-run`); `commit -nm`; aliases; `GIT_CONFIG_*` environment variables.
* **Recommendation:** Add the deny/allow table and these tests before implementation.

### G. Config-protection weakens ECC silently - Severity: Major
* **Affected Scope:** Inventory, `config-protection` row.
* **Discrepancy:** ECC matches case-insensitively and treats a dangling symlink as an existing file. The spec's file list is "for example". Bash routes such as `sed -i` bypass an Edit-tool ask. In headless runs `ask` becomes a denial (documented at `hooks/groundwork_task_gate.py:1096-1099`), so behavior differs from interactive.
* **Recommendation:** Make the file list closed and a superset of ECC's. State the case and symlink rules. Accept the Bash gap explicitly.

### H. Token telemetry (D5) does not match the code - Severity: Major
* **Affected Scope:** D5; `usage-telemetry` spec.
* **Discrepancy:** `groundwork_telemetry.py` has its own `current_turn` and `is_human_prompt`; `mark_turn_start` belongs to the reply-check hook. The design is silent on de-duplicating repeated `message.id` lines, on whether subagent/sidechain tokens count, on conversational turns where `build_record` returns `{}`, and on where the new fields go. Reviewer subagent tokens are likely the largest cost, so omitting them understates the total.
* **Recommendation:** Specify turn boundary, de-duplication and subagent policy; put the field list in the spec.

### I. Reviewer rebuild drops parts without saying so - Severity: Major
* **Affected Scope:** D3; inventory agents row.
* **Discrepancy:** Drops the Prompt Defense Baseline (`code-reviewer.md:8`) and the AI-generated-code addendum. The reviewer has Bash and reads untrusted diffs, so the injection block matters. The verdict model also changes: in ECC, HIGH only warns; in the rebuild, HIGH is must-fix, so the gate blocks more often. Marker text and severity scale are undefined.
* **Recommendation:** Keep a short injection-defense block. State the stricter verdict as deliberate. Define the marker and scale.

### J. Security reviewer dropped on a rejected argument - Severity: Major
* **Affected Scope:** inventory line 101; D3 line 125; `tasks.md` 8.2.
* **Discrepancy:** D3 rejects relying on personal agents because a fresh laptop has none. Line 101 relies on exactly that for the security reviewer. The `--doctor` advisory has no task.
* **Recommendation:** Ship a security-review mode in the new reviewer, or accept the gap and fix task 8.2.

### K. Migration scope has missing cases - Severity: Major
* **Affected Scope:** D6; `ecc-independence` spec.
* **Discrepancy:** Not covered: project-scope installs in other repos; a migration that fails halfway; open sessions keeping ECC hooks until restart; a sweep of `settings.json` for `ecc` paths (for example the statusline script); what `GROUNDWORK_KEEP_ECC=1` does to `--verify` and tests; `groundwork update`, which is referenced but defined nowhere.
* **Recommendation:** Add each as a spec scenario or an explicit out-of-scope line.

### L. Smaller items - Severity: Nit
* Altitude: the 6 KB cap, marker line and 200-call sample belong in `tasks.md`.
* YAGNI: the santa-method and pass^k "borrowed ideas" have no task. Cut or task them. The AgentShield version placeholder needs a real version.
* Numbers: skill count conflicts (369 vs "280+"); 340 tokens for 369 skill names is implausible.
* Margin: the 59k target leaves about 0.4k, with the new agent description unbudgeted.
* The "90 days" usage window assumes transcript retention that is unverified.

## Final go / no-go

**Architecture: GO. Design: NO-GO until these minimum changes are made.**

1. Move the backup to step 0 and include the ECC cache. Offline restore is the primary rollback. Verify the CLI flags and config-dir isolation first.
2. Reorder D7 so the real migration code is what the bench measures.
3. Replace the validation plan: 3+ repeats with tolerance, an edit-and-guard scenario set, merged or pinned bench code, defined metrics, and a hook-wait baseline measured in the same environment.
4. Re-test the partial-install premise on the current CLI.
5. Specify the guard tables (no-verify, config-protection) and the telemetry rules (turn boundary, de-duplication, subagent policy).
6. Widen the ECC-text cleanup with a case-insensitive grep and an allow-list.
7. Decide the security-reviewer and dropped-reviewer-section questions explicitly.

Counts: 3 Blockers, 8 Majors, 1 Nit group.
