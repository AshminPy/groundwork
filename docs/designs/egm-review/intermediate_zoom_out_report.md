# Stage 8: Intermediate Zoom Out report

Target: `docs/designs/groundwork-architecture.md` (full file, unchanged since Stage 5)
Reviewer: `egm:egm-zoom-out`, standard `zoom-out-standard.md`. It read the Stage 5, 6 and 7 reports.

## Overall altitude
The as-built half (lines 10-287) is at about the right altitude. The plan half (288-410) is uneven. Change A is written at code level and is less justified, because a simpler root fix was not considered. Change B is at the right altitude but rests on an unmeasured premise. Of the 60-odd findings so far, five change the design; the rest are polish or belong to another document.

## Findings that change the design

1. **Major. Change B's premise is unproven and its pass test would not show the goal was met (355-376, 403-406, 67-68, 85-90).** The gap is about 58k input tokens per answer; rules are about 12.6k of it. A perfect cut to 15,000 bytes leaves about 45k unexplained. Q1 admits the ECC share is unmeasured; the owner's own 39 KB of rules and hook-injected text are also unattributed. It is unknown whether 79k vs 21k is cached or uncached, or sums several API calls. The pass rule (first-request tokens drop by "removed bytes / 4") nearly restates the edit and does not test G5 (cost per answer). Cheapest fix: add a step 0 that measures token composition for one benchmark question, gate Change B on it, and define G5 as a number on cost per answer.
2. **Major. Change B's mechanism may raise cost and bring back the failure that justified hooks (238, 369-376).** Line 376 makes every task read a reference file: an extra round trip per task, and each round trip pays the whole prefix again. Simpler version: delete or shorten in place the rule text that a hook already enforces. That needs no `reference/` directory, no playbook-to-reference mapping and no `install.sh`/`uninstall.sh`/`setup.sh` changes, and it resolves Comprehension #10. Move text to `reference/` only for parts that cannot be dropped and are rarely needed.
3. **Major. Change A is built on the wrong root fix (294-336).** Stage 5 #1 proposed `python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/<name>.py"` and marked it unverified. The reviewer infers it is stronger than Stage 5 said: a `settings.json` in `/other` only takes effect when Claude Code runs with `CLAUDE_CONFIG_DIR=/other`, so the variable should be present when those hooks run. This is an inference and needs one test. If it holds, a constant command removes `hook_root`, `cmd`, the "byte-identical default" requirement, the dual-form unmerge (item 2), and Comprehension #2 and #3. The plugin route (Critic D7) would also remove the path problem for hooks; it is a larger move, so give it a one-line "considered, rejected because" in Alternatives. Caveat: the scheduled jobs and the status line run outside that environment and need a separate look.
4. **Major. G6 promises more than the plan delivers, and the scheduler work goes beyond G6 (69-70, 104-111, 227-229, 298-300, 322-335).** G6 says macOS or Linux, but the report and routine jobs are launchd-only (Critic D1, Comprehension #7). G6 says "any config folder", not "two installs side by side". The label-suffix work (items 3-4, about a third of Change A) serves only coexistence. Cheapest fix: narrow G6 to "scheduled jobs are macOS only, one job per machine", and drop items 3-4 unless the owner actually runs two config folders. Fully specifying `label_suffix` (Comprehension #8, #9) would add detail for a feature that may not be needed.
5. **Major. The document does two jobs and its role is unstated (title, 31-34, 276-284).** It describes the system as built and plans two changes. The as-built tables overlap `docs/ARCHITECTURE.md`, which the document itself calls stale. Decide: either this document supersedes `docs/ARCHITECTURE.md` (and says so, with a single source of truth for the hook list), or the as-built half shrinks to a link. The missing Risks section and the missing CUJs and alternatives for A and B (Critic S1, S3, S4) are real but cheap if kept to a few lines each.

## Contradictions between the reports
- **Comprehension wants more detail; Zoom Out wants less.** Comprehension #2, #8, #9, #12 ask for the 15-entry table, `label_suffix` internals and every data-file schema. Stage 5 #1 and #7 say to drop or replace that machinery. Resolution: do not specify what you may delete; for as-built data formats link to `docs/` and the code.
- **Severity of the "six events" error.** Comprehension: Blocker. Stage 5: Nit. It is a one-word typo (341 vs seven listed events) and only matters through the `--verify` spec, which falls away if Change A items 3-4 shrink.
- **Stage 5 #4 vs YAGNI.** Folding the single-source hook list into Change A is added scope. Fix the list in place; keep single-source as a Future Improvement.
- **Critic D7 asks for more alternatives than Stage 5.** Two additions are needed: "constant env-var command" (Change A) and "trim in place" (Change B). Plugin, skills and smaller hook set get one line each.
- **Alternative B wording.** Stage 5 accepts "worse on every measured axis"; Critic D7 and ST5 correctly say 39/40 vs 40/40 is a tie within noise. The rejection still stands on speed and output tokens; change the wording.
- **Cost framing.** Stage 5 treats Change B as a worthwhile bet needing measurement; Critic D8 says the whole 3.8x cost lacks a ceiling. Same finding at two levels; finding 1 covers both.

## Noise at this stage
- Style critic's 26 nits; Comprehension #13-#19; Critic S5-S9, D11, D12; Stage 5 #5, #6, #9 (for #9 one test is enough, not a rule).
- Critic D3, D4, D5, D10 (headless `ask`, fail-open asymmetry, privacy scope, brief keyed by sha8 with no locking) are real hardening items for the as-built system, not for Changes A and B. Record them as one-line entries in a Risks section; do not expand this document's scope to fix them.

## Missed in the detailed plan (288-410)
- Nit: line 290 says A and B are independent, but both edit `install.sh`, `uninstall.sh` and the `setup.sh --verify` section. State the merge order.
- Nit: Change A verification (400-402) covers the install and a SessionStart snapshot only. It does not check the status-line command or the scheduled-job path, both of which the plan changes.
- Major (folded into finding 1): Change B's pass criteria use the parked benchmark branch (`bench/vanilla-vs-groundwork`) and cannot detect regressions in moved behaviours (DECISION record, validation ladder).
- Nit: Q2 and Q4 are live defects the plan neither schedules nor drops. Say they are out of scope for these two changes.

## Mitigations that would add complexity (do not add now)
Single-source hook list (Stage 5 #4); systemd or cron path for Linux (D1); SessionStart self-check for safety hooks and file locking (D4, D10); full data-format specs (Comprehension #12); a `reference/` directory with a playbook mapping as a first move.
Cheap and simplifying, worth doing: pin OpenSpec (D2), put a number on G5, fix the "six events" typo.

## Verdict
Do not approve Change B as written, and rework Change A before building.
- Keep the as-built half, with its role stated.
- Change A: test the env-var command first. If it holds, delete items 1-3, the dual-form unmerge and the label-suffix work. Narrow G6 to macOS-only scheduling.
- Change B: add a measure-first step. Prefer trimming in place to creating `reference/`. Define success on cost per answer.
