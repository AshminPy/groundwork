# Consolidated review report, revision 2: replace-ecc-with-groundwork-core

**Target:** `openspec/changes/replace-ecc-with-groundwork-core/design.md` (383 lines) and `tasks.md` (85 lines).
**Stages run:** 7 (critic: design, structural, style) and 9 (implementation readiness: readiness, codebase details, style). Stages 5, 6 and 8 were not re-run, as requested. Reports: `critic_report.md`, `implementation_readiness_report.md` in this folder. First review: `../consolidated_review_report.md`.
**Method:** six fresh-context reviewers read the files and the code. Facts the design marks as verified on 27 Oct were not marked unverified. I spot-checked three new claims in code myself (see Evidence).

## Verdict

- **Direction: GO (unchanged).** Remove ECC entirely.
- **Design and plan as written: NO-GO, but much closer.** Of the 8 first-round Blockers, 1 is resolved, 7 are partial. Of the 17 Majors, 9 are resolved, 8 partial. None is fully open. The migration order, backup and rollback design, the guard tables, the reviewer contract and the validation plan are real and mostly consistent with the code.
- **3 new Blockers**, all about running the plan safely and being able to finish it:
  1. The bench runs are isolated for the config dir only. Hook commands, the launchd job, shell rc files and `npm -g` still hit the real machine.
  2. `setup.sh` sourcing `scripts/backup.sh` breaks the installed `setup.sh`, which is where `groundwork rollback` and `--doctor` run.
  3. The "No ECC text" check cannot pass, because the plan writes ECC text into files that the allow-list does not cover.
- **Count of new findings:** 3 Blockers, about 30 Majors (several merge into the groups below), about 40 Nits.

## Earlier findings: status after revision 2

| ID | Status | Line that resolves it, and what is left |
|---|---|---|
| A1 backup first, complete, keys named | PARTIAL | design 88-91, 306, 314, 318 (script, three keys named). Left: the backup is taken after Groundwork files and settings are written (`install.sh:196` precedes it), so it is not the pre-upgrade state; `setup.sh:764` already backs up, so there are two (N-4). |
| A2 one rollback, offline | PARTIAL | design 316, 323-335 (`--keep-data`, primary and fallback rollback, `KEEP_ECC` effects, `groundwork update`). Left: the offline rollback runs from the installed `setup.sh`, which cannot source `backup.sh` (NEW-B2). |
| A3 order; config-dir isolation | PARTIAL | design 337-346; tasks 5 then 7; isolation shown at design 81. Left: only the config dir is isolated (NEW-B1). |
| A4 validation plan | PARTIAL | design 365-378: 3 repeats, delta rule, one baseline file, pinned commit. Left: bench checkout and invocation, same-day ECC-on re-run, read-before-edit rule cannot fail the right way (N-9, N-10, N-11). |
| A5 no-verify guard | PARTIAL | design 189-205 (function, placement, table, deny text, fail closed). Left: fail closed covers the parser only; `_bypasses_hooks` cannot see `-c` data; table gaps (N-5, N-6). |
| A6 ECC-text cleanup | PARTIAL | design 378; tasks file scope lines for `engineering-workflow.md` etc. Left: the check cannot pass (NEW-B3); more sites are missing (N-14). |
| A7 token totals | PARTIAL | design 291-301 (`current_turn`, de-dup by `message.id`, subagents, `{}` case, report script). Left: subagent selection by mtime, schema bump breaks the report, no truncation or turn-start signal (N-7, N-8). |
| A8 reviewer contract | RESOLVED | design 218-273 (marker, tools, `REVIEW RESULT` block, severity table, kept and dropped sections, install and uninstall rules, licence, no byte cap). Nit: tasks 3.1 assertions unnamed. |
| M-1 security reviewer | RESOLVED | design 152, 241 (merged into the reviewer). |
| M-2 config-protection | RESOLVED | design 207-214 (32 names, lstat rule, tools, `ask`, kill switch, error log removed). Nits: citations, NotebookEdit not in ECC's matcher, ask versus hard block. |
| M-3 migration failure handling | RESOLVED | design 308-321 (M0-M9 with failure column). New: `installPath` pre-check (N-3). |
| M-4 re-test the premise | RESOLVED | design 27-32 (re-tested on 2.1.310). |
| M-5 inventory | PARTIAL | design 112-170 (corrected rows, dispatchers named, destructive classes table). Left: the table says "Covered" for classes the task gate does not catch (N-12). |
| M-6 numbers and sources | PARTIAL | design 44, 62, 68, 95. Left: bare figures at 129, 139, 181-183, 338; truncated session id at 68; "4 parts" unnamed (N-19). |
| M-7 token margin | RESOLVED | design 371 (delta rule). Nit: the 5.5k basis is not stated. |
| M-8 wrong report command | RESOLVED | design 301 (`groundwork_report.py`, not `groundwork usage`). Left: the section does not fit the report's structure as described (N-8). |
| M-9 phase stability | PARTIAL | design 338-339; tasks group 5. Left: `test_setup.py:161`, `:381-426`, `setup.sh:664`, `test_hooks.py:1712-1721` are not named (N-13). |
| M-10 file scope | PARTIAL | tasks 1-28 (table). Left: missing ECC text files and lines; no `install.sh` lines; legacy env cleanup in `unmerge_settings.py` (N-14, N-15). |
| M-11 design versus tasks | PARTIAL | 6 KB cap gone; p90 200 ms in the design (216). Left: socket wording differs in design, spec and task 2.5; "200 recorded inputs" undefined. |
| M-12 goal wording | RESOLVED | design 100-101. |
| M-13 promised work without tasks | PARTIAL | tasks 3.2, 6.2 (CREDITS, notices, AgentShield, superseded notice). Left: design 155 cites task 7.2 (should be 6.2); `groundwork update` has no task; code-review-agent install and uninstall scenarios have no test task. |
| M-14 structure for the standard | PARTIAL | H1 (1), risk severity and owner (350-357). Left: no Problem Statement, no Proposed Architecture, Alternatives only for D1 and D4 (N-16). |
| M-15 plain language, glossary | PARTIAL | glossary 5-19; observations dated. Left: KEEP and DROP undefined; about 15 terms missing; finding IDs in headings (N-17, N-18). |
| M-16 prerequisite 0.1 | RESOLVED | design 338 (PR #73 merged first, bypass tests named). |
| M-17 altitude | RESOLVED | 6 KB cap and marker detail moved or removed. Residue: normative text duplicated in design and specs. |

Count: RESOLVED 10 (A8, M-1, M-2, M-3, M-4, M-7, M-8, M-12, M-16, M-17), PARTIAL 15, OPEN 0. First-round nits: most wording nits are fixed; still open: `GIT_VALUE_OPTIONS` duplication note, D7-to-group mapping, `openspec validate` slowness note, `--runs-dir` in the validation command, p90 extraction command, "4 parts" list.

## New findings

### Blockers

| ID | Finding | Evidence | Fix |
|---|---|---|---|
| NEW-B1 | **Bench isolation covers the config dir only.** (a) Hook commands in `settings.json` point to the real `~/.claude/hooks/*` (old files), so group 7 tests the old guards. (b) `install.sh` and rollback repoint or unlink the real launchd job (`com.groundwork.report`). (c) `install.sh` edits real rc files and runs `npm install -g`. (d) Tasks 7.1/7.2/8.3 can be read as acting on the real config dir; backup root is ambiguous. | `merge_settings.py:50-80`; `install.sh:81,111-112,170`; `groundwork_report.py:43,635,655`; `setup.sh:854` | Task before 7.1: relative hook commands or rewrite and grep the bench `settings.json`; set `GROUNDWORK_NO_LAUNCHCTL=1`, scratch `GROUNDWORK_LAUNCH_AGENTS_DIR`, scratch `HOME`, `GROUNDWORK_BACKUP_DIR`; hash real state before and after; one command per checkbox with its environment. |
| NEW-B2 | **Installed `setup.sh` cannot source `backup.sh`.** `groundwork rollback` and `--doctor` run the copy in `bin/`. Same cause: `--verify` hook list from `merge_settings.py` is unreadable there. Python cannot source a bash function. | `install.sh:131-138`; `setup.sh:26`; `groundwork_update.py:74` | Ship `backup.sh` (and the hook list) into `bin/`, remove in uninstall, define the call interface, add an installed-tree test of `--rollback` and `--doctor`. |
| NEW-B3 | **"No ECC text" check cannot pass.** The plan writes ECC text in `setup.sh`, `install.sh`, `uninstall.sh`, `merge_settings.py`, README, two docs and the reviewer licence header; none are allow-listed. The pattern uses a table-escaped `\|`. | design 378 versus tasks 5.3, 6.2; spec ecc-independence line 67 | One allow-list in one place, widened; the exact command in a code block in task 6.1. |

### Majors (grouped)

| ID | Finding | Source |
|---|---|---|
| N-3 | A bench copy made with `cp -R ~/.claude` carries the real absolute `installPath`; the first `plugin uninstall` could delete the real ECC cache. Add an M1 pre-check that every `installPath` is under the target dir, and hash the real cache before and after. | DC-8 |
| N-4 | The backup is not the pre-upgrade state, and two backups exist in one install (`latest_backup` may call them "ambiguous"). `setup.sh` should pass its backup path to `install.sh`. | DC-2, CB M4 |
| N-5 | Fail closed covers parse failure only. Four give-up paths allow a bypass: `block_protected_push.py:864-866, 871-873, 876-877, 1005-1010`. One test each. | DC-3, CB M2, IR N-M9 |
| N-6 | D2 table gaps: `am -n`, abbreviated long options, `pull`, `git-commit`, env skips (`HUSKY=0`, `SKIP`); `--no-verify-signatures` must stay allowed; `_bypasses_hooks` cannot see `-c` data (`_git_invocation` drops it); `git config core.hooksPath` ask is in the git-guard table (design) but the task gate (tasks). | DC-4, CB M1, M3, ST-9 |
| N-7 | D5 subagent files are chosen by mtime (counts whole files); `isSidechain` double count; no file or byte cap; the hook has no turn-start or truncation signal (`current_turn` returns a bare list); `requests` counts `<synthetic>` messages. | DC-5, CB M6 |
| N-8 | Schema bump to 3 sends every field to "unknown" in the report (`groundwork_report.py:113` branches on `== 2`); the token section does not fit `normalise()` or `compute()` (no percentile helper); name loader and Markdown-only scope. | CB M5, M7 |
| N-9 | Bench mechanics: no task checks out `feat/m2-question-evidence` at a SHA; no literal `bench.run` command; no way to point arm G at a config dir; no edit-guard runner invocation; no `durationMs` command; no `--runs-dir`. | IR N-M6, CB M11, SW S-M9 |
| N-10 | "Same day" ECC-on baseline has no task (tasks 7.3, 7.4 compare to days-old group 1 data). | ST-2, IR N-M5 |
| N-11 | Read-before-edit pass rule (ECC-off ≥ ECC-on − 10 points) fails by construction because the gate forces ECC-on near 100%; 9 runs cannot measure 10 points. Use an absolute floor or make it informational. | DC-7 |
| N-12 | Destructive-class table overstates coverage: `checkout -- <path>`, `rm -r` forms, `--amend`, `switch -C`, `find -exec rm`, SQL through `docker exec`. | DC-6 |
| N-13 | Existing tests that break are not named (`test_setup.py:161, 381-426`; `setup.sh:664` `ECC_REF` and `VERIFY_FAILS`; `test_hooks.py:1712-1721`), so the "suite green" step in 5.3 cannot pass. | IR N-M3, CB M9 |
| N-14 | ECC text sites missing from the file scope: `rules/evidence-policy.md:35`, `docs/MACOS-SMOKE-TEST.md`, `docs/CONTEXT-ENGINEERING.md`, `docs/FUTURE-SCOPE.md`, `merge_settings.py:19,24`, `setup.sh:710`, `block_protected_push.py:4`, `install.sh:5-7,43-44,56,64,67-72`; `ecc:code-explorer` and `ecc:architect` have no mapping. | IR N-M1, CB M8 |
| N-15 | `GATEGUARD_EXEMPT_GLOBS` leaves `GROUNDWORK_ENV_DEFAULTS`, so uninstall stops cleaning it; keep a legacy list and test. Delete all of `merge_settings.py:299-303`. | CB M10 |
| N-16 | Structure: no Problem Statement, no Proposed Architecture; Alternatives only for D1 and D4; risk table lacks security rows and has three owner words; `M-1` (finding) collides with `M1` (migration step). | ST-5 to ST-8 |
| N-17 | Language: finding IDs in headings; KEEP and DROP undefined; about 15 terms missing from the glossary; dense cells; gate/guard terms mixed; bare numbers. | SY-1 to SY-7 |
| N-18 | Tasks: many checkboxes hold several actions; "verify" clauses with no command or expected value; "fails on main" is ambiguous on a feature branch; "group", "step", "phase" unmapped. | SW S-M1 to S-M4 |
| N-19 | Design and proposal drift: design 155 cites task 7.2 (should be 6.2); D7 omits the baseline group; proposal says 90 days and 4.5 MB (design: 66 days, 9 MB); `CREDITS.md` listed for group 7 with no task; `groundwork update`, reviewer install and uninstall scenarios, `test_reply_check.py` have no task. | ST-3, ST-4, ST-10, ST-12, SW S-M5 |
| N-20 | Tasks that need the design open: 2.1, 2.3, 3.1, 4.1, 5.3, 6.1, 8.2, 8.5 (see readiness report). | SW S-M10 |

### Nits

Wrong or off citations (`config-protection.js:22-63` and `110-127`; `DB_CLIENTS` defined at `groundwork_task_gate.py:79`; `parse_review_result` at `require_material_review.py:146`; prompt-defence block 8-16); NotebookEdit not in ECC's matcher; ask versus ECC's hard block; unreachable "claude missing" branch from `install.sh`; in-process p90 versus 164 ms hook baseline; reuse `write_atomic`; `set -e` on migration failure; regression-test labels for 3.3 and 5.4; `openspec validate` on the superseded notice; 1.6 no failure branch; copy `LICENSE` before 8.3; `cp -Rc` for bench copies; long sentences; "Evidence" term variants; scenario (d) `pyproject.toml` gap; `requests` synthetic; backup size. Full list with line numbers is in the two reports.

## Items confirmed correct in revision 2 (do not re-check)

`block_protected_push.py` early exits 947-957 and `GIT_VALUE_OPTIONS` at 76; `groundwork_task_gate.py` 723-727, 1165-1178, 1352-1353; `groundwork_telemetry.py:236`; `gateguard-fact-force.js:1264-1274`; 32 protected names; `REVIEW_PATTERN` (line 83) matches `groundwork-code-reviewer`; the `engineering-workflow.md` lines 3, 15, 20-22, 25, 60, 66, 68, 78, 92 contain ECC text as the tasks say; `require_material_review.py` 8, 18, 310-311; `groundwork_session_snapshot.py:6`; `groundwork_telemetry.py:108`; `check_routing.py:14`; `setup.sh` 14, 83, 86, 239-255; `uninstall.sh` 26, 139; test file names and `claude` stub lines; subagent file layout `<session>/subagents/agent-*.jsonl`.

## Residual uncertainty

- No reviewer ran `git help am` or tested git option abbreviation; `am -n`, `--no-verif` and `--no-verify-signatures` are plausible, not proven (DC-4, CB M3).
- I did not run any bench command. The claim that `installPath` in a `cp -R` copy points at the real cache is conditional on how the copy is made (DC-8).

## Suggested next step

Fix NEW-B1 to NEW-B3 first; they change the shape of tasks 5.1, 5.3, 6.1, 7.1 and 7.2. Then N-3 to N-8 in one pass over D2, D5, D6 and the matching tasks. Batch N-16 to N-20 (structure, language, task wording) into one editing pass. Re-run Stage 9 once on the edited `tasks.md`.

## Traceability matrix

Key: DC, ST, SY in `critic_report.md`; IR (readiness), CB (codebase), SW (style) in `implementation_readiness_report.md`. In the readiness report, IR items are labelled N-B/N-M, CB items B/M, SW items S-B/S-M.

| Consolidated | Source findings |
|---|---|
| NEW-B1 | IR N-B1, N-M7; CB B2; SW S-B1 |
| NEW-B2 | CB B1; IR N-M2, N-M4; DC-1 |
| NEW-B3 | IR N-B2; ST-1; SW S-M7 |
| N-3 | DC-8 |
| N-4 | DC-2; CB M4 |
| N-5 | DC-3; CB M2; IR N-M9 |
| N-6 | DC-4; CB M1, M3; ST-9; SW S-M6 |
| N-7 | DC-5; CB M6 |
| N-8 | CB M5, M7; IR N-M8 |
| N-9 | IR N-M6; CB M11; SW S-M9 |
| N-10 | ST-2; IR N-M5; SW S-M8 |
| N-11 | DC-7 |
| N-12 | DC-6 |
| N-13 | IR N-M3; CB M9 |
| N-14 | IR N-M1; CB M8 |
| N-15 | CB M10 |
| N-16 | ST-5 to ST-8 |
| N-17 | SY-1 to SY-8 |
| N-18 | SW S-M1 to S-M4 |
| N-19 | ST-3, ST-4, ST-10 to ST-13; SW S-M5 |
| N-20 | SW S-M10 |
