# Consolidated review report

Target: `docs/designs/groundwork-architecture.md` (410 lines; split at line 288: FeatureRange 1-287, DetailedRange 288-410)
Mode: uninterrupted, all five stages. The target document was not edited.
Stage reports (same folder): `zoom_out_report.md` (5), `comprehension_report.md` (6), `critic_report.md` (7), `intermediate_zoom_out_report.md` (8), `implementation_readiness_report.md` (9).

## Bottom line
The "as built" half is accurate where it was checked: the 15 hook entries, the cited `file:line` references and the doc-drift claims all match the code. The "next two changes" half is not ready to build.

- **Change A (install in any config folder)** has the right goal, but the plan is built on a heavier fix than needed, and it would leave existing custom-folder installs with every hook firing twice.
- **Change B (smaller always-loaded rules)** rests on a cost premise nobody has measured. Its main design decision (which text stays) is left to the implementer, and its pass test would not show the goal was met.
- Fewer than ten findings change the design. The rest, mostly nits from the style and comprehension passes, are polish.

## Blockers
Stages 6 and 9 raised these. Stages 5, 7 and 8 raised none; the Stage 8 reviewer rated the "six events" error as a Nit, not a Blocker, because it is a one-word typo.

| ID | Where | Blocker | Stage sources |
|---|---|---|---|
| B1 | 302-320 | No migration for existing custom-folder installs. Merge matches on the exact command string, so re-running adds 15 new entries beside the 15 legacy `~/.claude` ones: every hook fires twice (double telemetry, double Stop blocks, double `ask`). `groundwork update` would not repair the installs this change exists for. | R1 (S9), C4 |
| B2 | 361-367 | Change B's central decision (which text stays in the 15,000 bytes, per file and section) is left to the implementer. Fails the Zero-Decision Rule. | R11 (S9) |
| B3 | 340-342 | Event and file counts contradict each other: "six events" lists seven; "seven hook files" vs the 8 executable files plus `groundwork_shared.py` (`install.sh:95-102`); "15 hook commands" has no table. The `--verify` target counts cannot be written. | S6 #1, C1, ST (S9), S5 #5 |
| B4 | 105-110, 302-313 | The 15 hook entries (event, matcher, timeout, path) are not enumerated, so `cmd(root, rel)` and the "byte-identical to 2.5.0" test cannot be written from the document. Becomes moot if the constant env-var command is adopted (see D1). | S6 #2 |

## Major findings, grouped

### A. Change A is more machinery than needed (and the alternative is untested)
- **D1. Test a constant hook command first.** `python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/<name>.py"` may work for every config folder. Stage 8 infers the variable is present whenever the custom `settings.json` is active. This is UNVERIFIED and needs one test. If it holds, it removes `hook_root`, `cmd`, the byte-identical requirement, the dual-form unmerge and B1/B4. Caveat: scheduled jobs and the status line run outside that environment. (S5 #1, S8 #3)
- **D2. G6 promises more than the plan delivers.** G6 says macOS or Linux, but scheduled jobs are launchd-only (`install.sh:114` says so). The label-suffix work (items 3-4, about a third of Change A) serves only two installs side by side, which G6 does not require. Narrow G6 to "scheduled jobs are macOS only, one job per machine" and drop items 3-4 unless two config folders are a real need. (S5 #7, S6 #7, S7 D1, S8 #4)
- **D3. If items 3-4 stay,** the suffix is under-specified: define "default folder" (an explicit `CLAUDE_CONFIG_DIR=~/.claude` must give an empty suffix), `.hexdigest()`/encoding, put it in `groundwork_config.py` (routines does not import `groundwork_report`), update both plist-path functions, and decide what happens to already-scheduled 2.5.0 jobs. (S6 #8, R4, C3)
- **D4. Step 4 (`uninstall.sh`) is mostly unnecessary.** Uninstall already calls the installed report and routines scripts, which compute their own label. Drop the step or rewrite it as "no change". (R5, C2, S5 #7)
- **D5. `merge()`/`unmerge()` contracts are undefined:** where `root` comes from, the eight `*_CMD`/`STATUSLINE_VALUE` constants that `unmerge_settings.py` imports, the status-line comparison, and the existing tests that import them. (R2, C4)
- **D6. `hook_root`: resolved or only absolute?** On macOS `/tmp/x` resolves to `/private/tmp/x`, so the test can pass or fail by choice. Define the quoted string and test a path with a space. (R3, C6)
- **D7. `setup.sh --verify`:** give the new counts, say whether `groundwork_tasks.py` counts, change `hooks_registered()` (four events today), and check that each registered command points at `$CLAUDE_DIR/hooks/<file>`, not just contains "groundwork". (R6, C1, S5 #4)
- **D8. Tests:** missing cases (re-merge with legacy entries, space in path, status line, idempotency, routines labels, other folder untouched); put the install test in `tests/test_setup.py`; audit existing assertions expecting `~/.claude/hooks/...`. (R8, C5)
- **D9. The Verification Plan install check probably cannot run:** a fresh `mktemp -d` folder has no Claude login, and `install.sh` runs `claude plugin ...` there. Use a deterministic stub-payload check. (R17)

### B. Change B's premise, mechanism and test
- **D10. Premise not shown.** The gap is about 58k input tokens per answer; rules are about 12.6k. Even a perfect cut leaves about 45k unexplained. The ECC share, the owner's own rules and hook-injected text are unattributed, and cached vs uncached input is unstated. Add a step 0: measure token composition for one benchmark question, and gate Change B on it. Define G5 as a number on cost per answer. (S5 #2, S7 D8/D9, S8 #1)
- **D11. Mechanism may raise cost and bring back the failure that justified hooks.** On-demand reference files need an extra read and tool round trip, and the doc's own Alternative A says Claude skips rules it must remember to read (31 of 51 turns). Prefer trimming in place text that a hook already enforces, with no `reference/` directory. Mandatory every-turn rules (the "ask before" triggers) must stay always-loaded. (S5 #3, S8 #2, R12)
- **D12. Pass criteria are not measurable:** no way to run the harness on this branch (it lives on a parked branch); "evidence >= 18/20" equals the baseline with no noise margin; "tokens drop by bytes / 4" has no measurement source or tolerance; 20 questions will not catch regressions in the DECISION record, ask triggers or validation ladder. (S6 #11, R18, S5 #3)
- **D13. Test list is incomplete:** 17 references to rule filenames across `test_hooks.py` (11), `test_playbooks.py` (5), `test_telemetry.py` (1); `test_setup.py:151` counts; `test_playbooks.py:53-63, :87` line caps and required strings. Hook-text edits (item 4) should be a grep-driven list. (R13, R15, C9)
- **D14. Install/uninstall/verify/rollback for `reference/`:** add the directory to `mkdir`/`cp`/`rm -rf`, give the expected count, say whether any rule file is deleted, and confirm rollback coverage. (R14, C9)

### C. Document-level gaps (cheap fixes)
- **D15. No Risks & Mitigations section** (required by the standard); risks are scattered (fail-open paragraph, Q2/Q3, NFR bullets). Add one H2 with a line each for: fail-open safety hooks, headless `ask`, unpinned OpenSpec (`install.sh:81` is `@latest`), privacy scope beyond telemetry, brief keyed by `<branch>-<sha8>` going stale per commit, no locking for shared state. These are hardening items for the as-built system; record them, do not expand scope. (S7 S1/S2/D3/D4/D5/D10, S8)
- **D16. Changes A and B have no CUJ and no alternatives in the feature half.** Add a few lines each. Alternatives to add: "constant env-var command" (A), "trim in place" (B), one line each for plugin, native skills, smaller hook set. (S7 S3/S4/D7, S8)
- **D17. The document's role is unstated.** It overlaps `docs/ARCHITECTURE.md` (which it calls stale). Decide: supersede it, or shrink the as-built half to a link. (S8 #5)
- **D18. Open Questions Q1, Q2, Q4** are live defects/decisions that the plan neither schedules nor drops; say they are out of scope for A and B. (S5 #8, S7 D9, S8)
- **D19. Vocabulary and formats:** MATERIAL, tiers, task ledger, KEY, "sensitive actions", the exact required reply-format strings, "block once" semantics. Link to the rules/`docs/` instead of re-specifying. (S6 #4-#6, #12)
- **D20. Unsupported or overstated wording:** "worse on every measured axis" (39/40 vs 40/40 is a tie within noise; the rejection stands on speed and output tokens), "zero runtime cost" (rules cost about 12.6k tokens), "every hook fails open" followed by an exception, "most of the time"/"reliably" unquantified, bytes/4 token estimate unlabelled. (ST1-ST6, D20 style items)

## Disagreements between stages and how they resolve
- Comprehension asks for more detail (15-entry table, `label_suffix`, data schemas); Zoom Out says delete what you may not need. Resolution: decide D1/D2 first; specify only what survives; link as-built data formats instead of embedding them.
- "Six events" severity: Blocker (S6) vs Nit (S5, S8). Resolution: it is a typo, but it blocks writing the `--verify` target counts, so fix it with D7.
- Folding a single-source hook list into Change A (S5 #4) is added scope; keep it as a Future Improvement.
- Cost framing: S5 (a bet needing measurement) and S7 D8 (no ceiling) are the same finding at two levels, covered by D10.

## What was not verified
- No reviewer ran code or tests; the codebase reviewer had no shell. The 50,339-byte and 15,000-byte figures and "160 passed at `ccc807e`" are unchecked.
- Not checked: CUJ 4's claim that `settings.json` edits trigger `ask`; `orchestrator/bench/results/m2-comparison.md:12` (on another branch); PR numbers #63, #66, #72; the benchmark artifact URL.
- The `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` hook command is an inference (UNVERIFIED), not a tested fact.
- Most reviewers read only the supplied goldfish files plus a few extra scripts; claims about files they did not open are marked as such in their reports.

## Consolidated action list
Priority order (Blocker, then Major, then Nit).

| Pri | Action | Source findings |
|---|---|---|
| 1 Blocker | Test the constant env-var hook command; decide Change A's fix before writing more detail (D1). | B1, B4, D1, D5, D6 |
| 1 Blocker | Add a migration rule for legacy `~/.claude` entries on re-merge to a custom folder, with a test (needed under either fix). | B1 |
| 1 Blocker | Give Change B a per-file, per-section disposition table with byte budgets, or replace it with "trim in place" and a measure-first step 0. | B2, D10, D11 |
| 1 Blocker | Fix the counts (events, hook files, entries) and state what each means. | B3, D7 |
| 2 Major | Narrow G6 (macOS scheduling, one job per machine) and drop label-suffix and uninstall work unless two installs are a real need; if kept, specify per D3/D4. | D2-D4 |
| 2 Major | Define success for Change B as cost per answer, with a runnable, noise-aware benchmark method. | D10, D12 |
| 2 Major | Complete `--verify`, test list and install/uninstall/rollback steps; replace the login-dependent install check. | D7-D9, D13, D14 |
| 2 Major | Add a Risks & Mitigations section, CUJs and alternatives for A and B, and state the document's role. | D15-D18 |
| 3 Nit | Wording, units, links, heading styles, repeated facts. | D19, D20, style nits |

## Traceability matrix (raw findings to consolidated items)
| Stage report | Raw finding(s) | Consolidated item |
|---|---|---|
| Stage 5 zoom-out | #1 env-var command | D1 |
| | #2 Change B cost share | D10 |
| | #3 Change B reintroduces skipped rules | D11, D12 |
| | #4 hardcoded hook list | D7 |
| | #5, #6 event/file counts | B3 |
| | #7 scheduler collision | D2 |
| | #8 Q2/Q4 | D18 |
| | #9 Change B item 4 | D13 |
| | #10 G5 has no number | D10, D20 |
| Stage 6 comprehension | #1 | B3 |
| | #2 | B4 |
| | #3 | B1 |
| | #4, #5, #6, #12 | D19 |
| | #7 | D2 |
| | #8, #9 | D3, D4 |
| | #10 | B2 |
| | #11 | D12 |
| | #13-#19 | D20 (nits) |
| Stage 7 critic | D1 (Linux) | D2 |
| | D2 (OpenSpec `@latest`) | D15 |
| | D3, D4, D5, D10 | D15 |
| | D6, D8 | D10, D12 |
| | D7 (alternatives) | D16 |
| | D9 (open questions) | D18 |
| | D11, D12 | D15, D20 |
| | S1-S4 (structure) | D15, D16 |
| | S5-S9, style ST1-ST6 and nits | D20 |
| Stage 8 zoom-out | findings 1-5 | D10, D11, D1, D2, D17 |
| | contradictions | "Disagreements" section |
| Stage 9 readiness | R1 | B1 |
| | R2-R10 | D3-D9 |
| | R11 | B2 |
| | R12-R16 | D11, D13, D14 |
| | R17-R20 | D9, D12 |
| Stage 9 codebase | C1 | B3, D7 |
| | C2-C10 | D3-D6, D8, D13 |
| Stage 9 style | 4 major, 12 nit | B3, D12, D20 |
