# Stage 5: Initial Zoom Out report

Target: `docs/designs/groundwork-architecture.md` (full file, 410 lines)
Reviewer: `egm:egm-zoom-out`, standard `zoom-out-standard.md`

Summary: the as-built half is accurate. The plan half has one altitude problem (Change A), one root-cause gap (Change B) and some inconsistencies.

## Claims checked and found correct
- 15 hook entries match `scripts/merge_settings.py` (push 1, review 1, telemetry 3, snapshot 1, task gate 4, reply check 2, brief 3).
- Cited lines match the code: `merge_settings.py:50-80`, `:305-307`; `install.sh:65-73`, `:81`, `:91`, `:196`; `groundwork_report.py:43`; `groundwork_routines.py:58`; `groundwork_reply_check.py:145-159`.
- Doc-drift claims hold: `README.md:220` says "five hooks"; `docs/ARCHITECTURE.md` (about line 30) says "four"; the code has seven hook files.
- `setup.sh --verify` claim holds (line 642 checks six files; line 681 `reg -ge 4`).
- The constant `~/.claude` hook path is real, so the Change A problem statement is real.

## Findings

| # | Severity | Doc lines | Finding |
|---|---|---|---|
| 1 | Major | 302-328 | Change A items 1-3 are written at code level (`hook_root`, `cmd`, `label_suffix`, `shlex.quote`, `sha256[:8]`) and may be more machinery than needed. The simpler option is not considered: a constant command like `python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/<name>.py"`. Whether Claude Code runs hook commands through a shell and passes `CLAUDE_CONFIG_DIR` is UNVERIFIED. If it holds, `hook_root`, the dual-form unmerge (item 2) and the "byte-identical default" concern disappear. Justify the absolute-path approach or switch. |
| 2 | Major | 355-394, 67, 263, 357 | Change B targets a cost share not shown to be significant. Extra cost is about 58k input tokens per answer; rules are about 12.6k tokens, roughly a fifth. "Largest share Groundwork owns" is true, but Q1 admits the ECC share is unmeasured. It is not stated whether 79k vs 21k is cached or uncached input; if rules are in a cached prefix, shrinking them may barely move cost or latency. Measure the composition first, or call Change B a bet. G5 is not tied to a demonstrated root cause. |
| 3 | Major | 238, 368, 392, 403-406 | Change B reintroduces the failure mode that justified hooks. Alternative A says Claude skips rules under load (31 of 51 turns lacked metadata). Change B moves about 70% of rule text into on-demand reference files Claude must remember to read. The 15,000-byte target has no stated basis. The test that required phrases still exist proves the text exists, not that it is followed. 20 questions (20/20 correctness, >=18/20 evidence) may be too coarse to catch regressions in moved behaviours such as the DECISION record and validation ladder. |
| 4 | Major | 337-342, 278-281 | Change A item 5 hardcodes yet another hook list. Future Improvements calls for a single source of truth. Change A adds a fourth place to keep in sync (`merge_settings.py`, `install.sh` chmod, `setup.sh`, docs). Fold the single-source fix in (derive from `merge_settings.py`) or say why it is deferred. |
| 5 | Nit | 341 | "all six events" but seven are listed (PreToolUse, PostToolUse, PostToolUseFailure, Stop, SessionStart, UserPromptSubmit, PreCompact). |
| 6 | Nit | 340 | "seven hook files plus `groundwork_shared.py`" omits `groundwork_tasks.py`, which `setup.sh:642` verifies and `install.sh:95-102` chmods. Unclear whether the verify list should include it. |
| 7 | Nit/Major | 298-300, 322-335 | The scheduled-job collision is a narrow case. G6 says install works "in any config folder", not that two installs coexist. If coexistence is not needed, drop items 3 and 4 (about a third of Change A) and document "one scheduled job per machine". `uninstall.sh` already disables jobs via the `ROUTINES` registry (`groundwork_routines.py:48-68`); the description at lines 330-335 ("not every `com.groundwork.*` job") should be checked against that and `uninstall.sh:9`. |
| 8 | Nit | Open Questions Q2, Q4 | Q2 (reply check fires on progress messages) and Q4 (usage tracking records nothing when another tool owns `statusLine`) are live defects. The plan neither schedules nor drops them. State they are out of scope or promote one. |
| 9 | Nit | 382-388 | Change B item 4 is a speculative "modify if needed" list over seven files. A grep shows 17 mentions of the two rule filenames across 7 files. Replace with a rule: a test fails if any hook or script names a rule section that no longer exists. |
| 10 | Nit | Goals vs 368, 406 | G5 has no number, while G1 and G2 do. Put the 15,000-byte target in Goals. |

## No findings
- No premature optimisation; no new abstraction beyond Changes A and B.
- Rejecting the LangGraph orchestrator and the citation checker is well supported by the cited measurements.
- Reuse is handled well (native `ask` permissions, existing libraries).

## Not verified by the reviewer
- CUJ 4 claim that `settings.json` edits trigger `ask`.
- Line 245 cites `orchestrator/bench/results/m2-comparison.md:12` on another branch; not opened.
- PR numbers (#63, #66, #72) and the benchmark artifact URL.
