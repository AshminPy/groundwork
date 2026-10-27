# Critic report (Stage 7), revision 2

**Target:** `openspec/changes/replace-ecc-with-groundwork-core/design.md` (383 lines, revision 2). **Range:** whole file (no implementation-plan header exists in the design; the plan is `tasks.md`, reviewed in Stage 9).
**Reviewers:** design critic (DC), structural (ST), style (SY). Each was a fresh-context Goldfish that read the design, the first review and the code it cites.
**Result:** 0 Blockers in the design text itself. 14 Majors, about 20 Nits. The direction is unchanged and sound. The remaining problems are logic holes in the rebuilt parts, missing structure, and unexplained terms.

IDs: DC = design critic, ST = structural, SY = style. The status of each earlier finding is in `consolidated_review_report.md`.

## Design critic (DC)

### Major

**DC-1. `backup.sh` sourced by `setup.sh` breaks the installed copy that runs `--rollback` (D6, line 306).**
- `install.sh:138` copies `setup.sh` alone to `$CLAUDE_DIR/groundwork/bin/setup.sh`. The comment at `install.sh:131-137` says that copy is safe for `--doctor` and `--rollback` because it needs no `$HERE`-relative file. `groundwork rollback` dispatches to it.
- A top-level `source "$HERE/scripts/backup.sh"` fails there. The primary offline rollback (line 323) dies where an owner would run it.
- Fix: keep `make_backup` in `setup.sh` and give it a backup-only mode the migration calls, or copy `backup.sh` into `bin/` and source it from the script's own directory. Add a test that runs `--rollback` from an installed tree.

**DC-2. The M2 backup is not the pre-upgrade state (D6, lines 306-323; Context line 91).**
- The migration runs after `install.sh` copied hooks, ran `merge_settings.py` (`install.sh:196`) and deleted `commands/gw-*.md`. "As it was at M2" is new Groundwork plus ECC.
- A direct `./install.sh` makes no backup, so a failure before M2 leaves none.
- `setup.sh` (`run_setup`, line 764) already backs up before it calls `install.sh`. M2 adds a second full backup; `latest_backup` (`setup.sh:833-839`) calls two same-second backups "ambiguous".
- Fix: take the backup first. `setup.sh` passes its backup path to `install.sh`, and the migration reuses it; only a direct `./install.sh` makes its own. State which state the rollback restores.

**DC-3. Fail-closed covers parse failure only (D2, line 204).** `block_protected_push.py` has four give-up paths that deny only when the text mentions push: too long (864-866), too deep (871-873), unbalanced quotes (876-877), exception or timeout (1005-1010). A nested `bash -c 'bash -c "git commit --no-verify"'`, or any timeout, passes. Fix: make all four deny when `no-verify` or `hookspath` appears (case-insensitive); one test per path.

**DC-4. The D2 table has gaps (lines 193-203).**
- `am -n` (a synonym of `--no-verify` for `git am`; the first review listed it; confirm with `git help am`).
- Abbreviated long options (`--no-verif`): git accepts unique prefixes. ECC has the same hole.
- `pull --no-verify`; `git-commit` hyphen form.
- `--no-verify-signatures` (a real `merge` option) must not be denied by a prefix match.
- Env-var skips (`HUSKY=0`, `SKIP=…`, `GIT_CONFIG_PARAMETERS`), commit made by a script, deleting `.git/hooks`: deny or list under accepted gaps (line 202).

**DC-5. D5 subagent totals are selected by file mtime (line 295).** "Files modified since the turn start" counts whole files, so a subagent that spans turns is counted in full each time. The directory layout (`<session>/subagents/agent-*.jsonl`) is right, but `.prefix.json` and `.meta.json` sit beside them and must be excluded. The design never says how the directory is derived from `transcript_path`. `is_human_prompt` (`groundwork_telemetry.py:229`) skips `isSidechain` entries, so inline sidechain lines may double count. Nothing bounds the number of subagent files read. Fix: count only lines at or after the turn start, skip `isSidechain` in the main file, cap files and bytes (set `tokens.truncated`), and say that subagents finishing after Stop are missed.

**DC-6. The destructive-class table says "Covered" too often (lines 160-170).** ECC also gates `git checkout -- <path>`, `git rm -r`, `git commit --amend`, `git switch -C` and `find … -exec rm` (`gateguard-fact-force.js:452-546`). The task gate's `_git_destructive` (`groundwork_task_gate.py:820-847`) catches `checkout .` only. SQL is covered only for a bare client, not `docker exec … psql` or `python -c`. Fix: add these rows as covered or accepted loss; soften "Covered".

**DC-7. The read-before-edit pass rule cannot be falsified (Validation line 374; D4 line 289).** ECC-on's rate is pushed near 100% by the gate itself, so "ECC-off ≥ ECC-on − 10 points" fails by construction. With 9 runs one run moves the rate more than 10 points, so the D4 revisit trigger cannot be measured. Fix: an absolute floor (for example ≥ 80% over at least 30 edit calls), or make it informational and gate on "tests pass".

**DC-8. Bench copies may point at the real `~/.claude` (lines 81, 341-343, 354).** Isolation was shown with the read-only `claude plugin list`. `installed_plugins.json` stores an absolute `installPath`; a copy made with `cp -R ~/.claude` carries the real cache path, and the first `plugin uninstall` could delete the real cache. The design does not say how the copies are made, and the mitigation (line 354) checks after the uninstall. Fix: M1 pre-check that every ECC `installPath` is under the target dir (else abort); hash the real cache before and after.

### Nit
- `config-protection.js:22-55` is wrong: the set spans 22-63 (32 entries correct). The lstat/case rules are at 96-131, not 97-112.
- `latest_backup` same-second ambiguity: the printed fallback should name the directory.
- M3 (line 315): "hooks installed" must mean registered in `settings.json`; say the migration runs after `merge_settings.py`.
- `install.sh:59-73` ECC install block is removed in task 5.3 but D6 never says so; a re-run would reinstall ECC.
- Scenario (d): ECC's list excludes `pyproject.toml`; relaxing ruff there passes the guard. Add to accepted gaps (line 212).
- Backup size: M2 copies `projects/` transcripts (fast clone on APFS, full copy elsewhere).
- `requests` (line 294): exclude `<synthetic>` zero-usage messages.

## Structural (ST)

No Blockers. Eight Majors.

- **ST-1. The "No ECC text" check cannot pass (line 378).** The plan itself writes ECC text into files outside the allow-list: D6 messages ("ECC kept by owner"), the `--verify` row (spec: "present, not used by Groundwork"), the rollback and AgentShield docs (task 6.2: `README.md`, `docs/UPGRADE-ROLLBACK.md`, `docs/TROUBLESHOOTING.md`), `setup.sh`, `install.sh`, `uninstall.sh`, `merge_settings.py`, and the reviewer agent's licence header. The spec allow-list (ecc-independence, line 67) includes the licence header; the design's does not. Fix: one list, widened, in one place.
- **ST-2. "Same day" ECC-on baseline has no task (lines 371-373 versus tasks 1.3, 1.5, 7.3, 7.4).** Groups 1 and 7 are days apart. Add a re-run task in group 7, or drop "same day" and state a drift tolerance.
- **ST-3. Wrong task reference (line 155).** "task 7.2" is the rollback test; the AgentShield pin is in task 6.2.
- **ST-4. D7 omits the baseline step and three words name one sequence (lines 337-346, 354, 361-367).** D7 "steps", Migration Plan "phases", tasks "groups". No mapping. Line 354 "step 3 checks the real dir" reads like D6 M3. Line 367 says "task 1.x".
- **ST-5. ID collision: review finding `M-1` versus migration step `M1` (lines 3, 152, 313, 316, 354).** Line 216 cites `CR-N4`, not declared on line 3. Rename migration steps `D6.0 … D6.9`.
- **ST-6. No Problem Statement and no Proposed Architecture (lines 21-23, 97-110).** "See proposal.md for why." The four rebuilt parts (git guard, config-protection ask, reviewer, token totals) are never listed together (D1 says "4 parts"). No install-time and run-time flow.
- **ST-7. Alternatives Rule met only for D1 and D4.** D2, D3, D5, D6, D7 have none (for example: new standalone hook versus the git guard; disable versus uninstall; settings-only backup; migrate before measuring).
- **ST-8. Risk table is thin on security and owner vocabulary is mixed (lines 350-357).** Missing: fail-closed false denials, headless ask becoming denial, the Bash gap for config edits, prompt injection into a reviewer with Bash, telemetry reading transcripts. Owners: "Groundwork maintainer", "maintainer", "owner"; no likelihood column.

Drift between design, specs, tasks and proposal:
- **ST-9.** The `git config core.hooksPath` ask sits in the D2 git-guard table (line 201), but tasks put it in `groundwork_task_gate.py`.
- **ST-10.** code-review-agent scenarios "Install and uninstall" and "An owner's file with the same name" have no test task.
- **ST-11.** Guard timing stated three ways: latency (design 216), "no socket opened" (spec 66-71), "no socket module imported" (task 2.5).
- **ST-12.** Proposal line 5 says 90 days and 471 sessions (design: 66 days); proposal line 8 says command log 4.5 MB (design 139: 9 MB).
- **ST-13.** `usage-telemetry` spec has no `## Purpose`. Proposal Impact omits `docs/VALIDATION.md`, `bench/edit-guard/`, `docs/designs/ecc-removal-baseline.md`.

Nits: glossary lacks "fact-forcing gate", "dispatcher", `hook_profile`, `bench.run`, "Evidence section", "STANDARD"; inventory second table and destructive table have no headings; line 154 says commands had 0 uses but line 58 says `/ecc:terminal-opener` typed twice; "6.5k" has no derivation (6,195 + ~340); "—" cells (168, 312); `\|` in a table cell (378); validation command still omits `--runs-dir` (372); `GIT_VALUE_OPTIONS` duplication (`groundwork_task_gate.py:807`) not mentioned; where the `--verify` hook list lives (task 5.3 says `merge_settings.py`, design does not); normative text duplicated in design and specs (REVIEW RESULT block, deny text, 32 names, D5 fields).

## Style (SY)

No Blockers. Closest: line 196 ("`m F C c t S u`") and lines 199 versus 201 ("deny" for `-c core.hooksPath`, "ask" for `git config core.hooksPath`) are easy to confuse. Reword as "deny: sets it for one command" and "ask: sets it permanently".

- **SY-1 (Major). Finding IDs in headings and body (lines 112, 187, 218, 291, 303, 337, 365; 27, 100, 152, 216).** A future reader has no key. Delete them from headings; put one trace table in an appendix.
- **SY-2 (Major). KEEP and DROP are undefined.** "KEEP as token totals" and "KEEP as `groundwork-code-reviewer`" keep none of ECC's code. Use "Replace" and "Remove", or define both.
- **SY-3 (Major). Terms used but not in the Glossary:** dispatcher, headless (own row), APFS clone, subagent, p90, delta rule, read-before-edit rate, G-ECC-on / G-ECC-off, bench, frontmatter, PreCompact, fail closed, user-scope, project-scope, atomically, "Standard" (line 119, clashes with MATERIAL).
- **SY-4 (Major). Dense table cells (two or more facts):** lines 196, 372 (six pass conditions), 374 (six scenarios and five rules), 313, 139, 137, 252, 143. Split rows or use a second table.
- **SY-5 (Major). Pronoun and two-fact sentences:** lines 3, 22, 23, 66, 185, 214, 263, 335, 338, 296.
- **SY-6 (Major). Mixed terms:** "gate" means task gate, review gate and fact-forcing gate; "guard" versus "git guard"; "config-protection" versus "config protection ask"; "reviewer" versus "reviewer agent"; "migration" as script and as the whole change.
- **SY-7 (Major). Bare numbers:** line 129 (25 MB, 1,149), 139 (9 MB), 168, 181-183 ("6.5k"), 371 ("≥ 5.5k" has no basis), 372 ("− 1" no unit), 68 (truncated session id), 44 ("66 days, not 90" refers to a claim the reader never saw), 338 ("16 review-found bypasses").
- **SY-8 (Nit). Informal wording:** lines 168, 252, 271, 154, 304 ("goes"), 339 ("green"), 129 ("0 learned rules" reads as a judgement).
- "—" and empty cells remain at 133, 138, 168, 312, 319-321.
