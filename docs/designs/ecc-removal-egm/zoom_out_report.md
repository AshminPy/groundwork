# Goldfish Review Report (Zoom-Out lens)

**Target:** `/Users/ashmin/projects/ai-projects/groundwork/openspec/changes/replace-ecc-with-groundwork-core/design.md` (lines 1-185)

**Verdict:** changes required. 2 Blockers, 10 Majors, 4 Nits.

Spot-checked citations that are accurate: `merge_settings.py:300`, `install.sh:59-72`, `REVIEW_PATTERN` at line 83, `code-reviewer.md:29-111`, the `sonnet` pin at `code-reviewer.md:5`. Most of the hook inventory matches `hooks.json`.

Not read in full by the reviewer (findings that depend on them are marked unverified): `hooks/groundwork_task_gate.py`, `hooks/groundwork_telemetry.py`, `scripts/unmerge_settings.py`, the benchmark code.

## Prioritized Findings (Blockers -> Major -> Nits)

### 1. The accuracy gate cannot detect a quality drop - Severity: Blocker
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Validation, row "Accuracy"; D4
* **Discrepancy Description:** The gate is 20 fixed cases, one repeat (`--repeats 1`), against a baseline already at 20/20. At the ceiling, a regression can only show up as noise. The benchmark scores read-only question answering. It does not exercise edits, destructive shell commands, bypass attempts or reviews, which are what the fact-forcing gate, the no-verify block and the reviewer protect. D4 names "a quality drop the benchmark does not catch" as the risk, then names the same benchmark as the mitigation. "Median input tokens below 79,133" and "Evidence rate >= baseline" are strict inequalities on one noisy run. The benchmark code lives on a parked branch (`feat/m2-question-evidence`), so the gate depends on code that is not on main.
* **Rationale & Recommendation:**
  * Run at least 3 repeats on both the baseline arm and the ECC-off arm, with a stated tolerance (for example tokens up by at most 2%, Evidence rate not lower by more than one case).
  * Add a small edit-and-guard scenario set: edit without reading, `--no-verify`, config weakening, a reviewer round trip.
  * Merge the benchmark module or pin its commit before using it as a gate.
  * Define "input tokens". The API `input_tokens` excludes cache reads and writes. If 79,133 counts only `input_tokens`, it is not comparable with the request size shown by `/context`.

### 2. Rollback depends on the network and an upstream tag - Severity: Blocker
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** D6 rollback; Risks, "Rollback is one command"
* **Discrepancy Description:** Rollback runs `claude plugin marketplace add "affaan-m/ECC#v2.2.1"`. This needs GitHub, and the tag must still exist unmoved. Uninstalling removes the plugin cache. `--keep-data` keeps only the plugin data directory, not the code. Rollback is therefore not guaranteed.
* **Rationale & Recommendation:** Before uninstalling, archive `~/.claude/plugins/cache/ecc` and the marketplace clone into the timestamped backup. Make the offline restore the primary rollback and the network command the fallback. Test the rollback with the network off.

### 3. Contradictory or unverified CLI behavior - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** D6 step 1; Risks
* **Discrepancy Description:** "Its persistent data dir is kept by default: we pass `--keep-data`" contradicts itself (default keeps it, or the flag is needed, not both). No source shows that `--keep-data` exists. Risks says the CLI is "exercised in the bench copy first", but nothing says `claude plugin` honors the bench's separate config dir. If it uses the real `~/.claude`, the bench test would uninstall ECC from the real machine.
* **Rationale & Recommendation:** Record the CLI help output. State how the bench copy is isolated (for example `CLAUDE_CONFIG_DIR`) and prove it before running the uninstall. Fix the sentence.

### 4. The hook-wait criterion may pass trivially - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Context, "Measured hook time"; Validation, "Hook wait"
* **Discrepancy Description:** The 7.5 s figure comes from one planning session. The cause (`NODE_USE_SYSTEM_CA=1`) has an unknown source. If the bench or `claude -p` subprocess does not inherit it, ECC-on would also show a low p90 there, and the <= 500 ms check proves nothing.
* **Rationale & Recommendation:** Measure ECC-on in the same bench environment first and show it reproduces the slow baseline. Task 1.2 records timings from old transcripts, not from the new run's conditions. State that other Node hooks and CLIs stay slow while the variable is set.

### 5. Inventory and destructive-command claim are incomplete - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Inventory, gateguard row and the "Drop" list
* **Discrepancy Description:** `posttooluse-dispatcher.js:30` registers `post:governance-capture` (profiles `standard,strict`). Only `pre:governance-capture` is listed, as OFF. The claim that destructive commands are "already asked/denied by `_git_destructive` and the deny list" is only partly supported. ECC's gate uses a regex for `drop table|delete from|truncate|dd if=` (`gateguard-fact-force.js:56`) plus first-attempt checks on `rm`. Groundwork covers `rm -r` (around line 725), cloud CLIs and `DB_CLIENTS` (line 79). Whether it treats SQL text or `dd` the same way is unverified.
* **Rationale & Recommendation:** Add the missing `post:governance-capture` row. Add a table mapping each of gateguard's destructive classes to the Groundwork check that covers it. Mark any gap "accepted loss" or add a test.

### 6. No-verify guard coverage against bypass routes is unspecified - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Inventory, `block-no-verify`; git-integrity-guards spec
* **Discrepancy Description:** Not covered: `git config core.hooksPath`, `GIT_CONFIG_PARAMETERS`/`GIT_CONFIG_COUNT`, hook-skip variables (`HUSKY=0`, `SKIP=`), aliases that expand to `commit -n`, and `commit -nm`. The D2 reuse claim is fair: `block_protected_push.py` already parses `-c` and aliases (`_git_invocation`, around lines 694-720). The "fail-open except deny on unparseable `--no-verify`" rule needs a test.
* **Rationale & Recommendation:** List the supported bypass forms and the known unsupported ones. State that tampering with `.git/hooks` files is out of scope.

### 7. Config-protection moves from block to ask and loses ECC behavior silently - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Inventory, `config-protection`; git-integrity-guards spec
* **Discrepancy Description:** ECC matches case-insensitively and treats a dangling symlink as an existing file (`config-protection.js:97-112`). The spec says nothing on either. The spec's file list is "for example". It is unclear how "ask" behaves in headless or `claude -p` runs, in subagents, and under bypass-permission modes, where no human can answer.
* **Rationale & Recommendation:** Make the file list closed and at parity with ECC's `PROTECTED_FILES`. State what "ask" does with no human (deny or allow). State that the `sed -i` and `echo >` routes exist in ECC too (parity).

### 8. The reviewer rebuild drops ECC reviewer parts and changes the verdict model - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Inventory (agents); D3
* **Discrepancy Description:** ECC's `code-reviewer.md` also has a "Prompt Defense Baseline" (line 8) and a "v1.8 AI-Generated Code Review Addendum" (line 312). The plan lists neither. ECC's verdict is Approve / Warning / Block, where HIGH only warns. The new agent makes HIGH a must-fix, so the gate blocks more often than today. The owner already has many `*-reviewer` agents in `~/.claude/agents`.
* **Rationale & Recommendation:** Decide explicitly whether to keep the two dropped sections. State the verdict change as deliberate and cover it in fixture checks. Say why a new generic reviewer is needed next to the existing ones.

### 9. ECC references remain after the planned cleanup - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Context, "ties to ECC"; Validation, "No ECC text"; task 7.1
* **Discrepancy Description:** `rules/engineering-workflow.md` mentions ECC at lines 20, 21, 25, 66, 68, 78, 92. Task 7.1 lists lines 3, 20-22, 25, 78, 92, so 66 and 68 are missing. The check `grep -rn 'ecc:'` is case-sensitive and needs a colon, so it misses lines 66, 68 and 78. The MATERIAL "Plan" and "TDD" steps point at `ecc:planner` and `ecc:tdd-guide`. Usage data shows 0 calls.
* **Rationale & Recommendation:** Add lines 66 and 68. Use `grep -rniE '\becc\b'` over `rules hooks playbooks agents docs` with an explicit exemption list. State what replaces the plan and TDD steps (built-in Plan agent, or nothing) rather than deleting the wording.

### 10. Token totals may double-count and miss subagent work - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** D5; usage-telemetry spec
* **Discrepancy Description:** Transcripts commonly write one assistant message as several lines repeating the same `message.id` and `usage`. Summing every line inflates totals. Subagent tokens sit in separate sidechain transcripts, so "tokens per turn" would exclude them. The spec requires reading "only usage and timestamp fields", but the existing `current_turn` parser reads full entries (unverified, telemetry hook not fully read).
* **Rationale & Recommendation:** De-duplicate by message or request id. State whether subagent usage is included. Add a duplicate-line fixture to the spec scenario. Confirm the field-only read in a test.

### 11. Migration scope gaps - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** D6; ecc-independence spec
* **Discrepancy Description:** Only user scope is handled. ECC may be installed at project scope in other repos, and a custom `CLAUDE_DIR` is not covered. Open sessions keep ECC hooks until restarted. `GROUNDWORK_KEEP_ECC=1` leaves ECC in place, but Groundwork's own tests and `--doctor` still change, and it is not said how. Other settings may point at ECC paths (the plugin ships `ecc-statusline.js`).
* **Rationale & Recommendation:** Print a restart notice. Sweep `settings.json` for any `ecc` path before removal. Define behavior under `GROUNDWORK_KEEP_ECC=1`. Say whether project scope is out of scope.

### 12. The "no partial install" premise should be re-verified - Severity: Major
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Context, "A plugin is all or nothing"; D1
* **Discrepancy Description:** The claim comes from a 2.0 spec of 2026-09. It is now late October, and `skillOverrides` and `Agent(name)` deny rules can change between versions. D1 rejects slimming on this basis, so it is the central premise.
* **Rationale & Recommendation:** Re-test on the current CLI and record version and output. If an agent deny rule removes the description from the list, the ~6.5k saving may be reachable without removal.

### 13. Thin margin and a questionable number - Severity: Nit
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Context table; Validation
* **Discrepancy Description:** 369 skill names costing ~340 tokens is under one token per name, which is not plausible. The target (<= 59k from 65.1k) depends on a ~6.5k saving and leaves about 0.4k margin. The new reviewer's description adds tokens.
* **Rationale & Recommendation:** Re-check the measurement and its label. Widen the margin or state the tolerance.

### 14. Unspecified rollback flag and stale uninstall text - Severity: Nit
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** D6 rollback step 2; `uninstall.sh:139`
* **Discrepancy Description:** `merge_settings.py --ecc` is "a small new flag, or the restored backup does the same", and no task builds it. The install command already passes `--config hook_profile=standard`. `uninstall.sh:139` still says "ECC and OpenSpec were left untouched", and no task updates it.
* **Rationale & Recommendation:** Pick one option and drop the flag if unneeded. Add a task for the uninstall text.

### 15. Evidence base for "0 calls" - Severity: Nit
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** Context, "Measured use"
* **Discrepancy Description:** Counts cover `Agent` and `Skill` tool calls in 471 transcripts. Subagent-initiated calls, typed `/ecc:*` commands and hook-driven use may be missed. The ECC install date is not given, so the 90-day window may be too long.
* **Rationale & Recommendation:** Add a one-line caveat and the install date. "Drop 63 other agents" is probably still right.

### 16. Altitude - Severity: Nit
* **Reviewer Lens:** `zoom-out`
* **Affected Scope:** D3, D5, D7
* **Discrepancy Description:** Details like the 6 KB file size limit, the exact marker line and `p90 <= 300 ms` on 200 calls are too low-level for a design.
* **Rationale & Recommendation:** Move them to `tasks.md` and shorten D3 and D5. The design does not need to change otherwise.
