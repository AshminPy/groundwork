# Tasks

Planning only until the owner approves. Groups follow the milestone order in design D1. Each milestone ends with its own release gate. Tasks follow the recommended answers to the owner decisions in design.md. If the owner chooses otherwise, revise the affected tasks before applying.

## 1. M0: Reconcile `main` with the released 2.4.0 (docs only)

- [ ] 1.1 Replace `main`'s `## 2.4.0` CHANGELOG section with the one at tag `v2.4.0` (dated 2026-10-13, with the macOS fix bullets), and remove the `groundwork report schedule` text from Unreleased. Verify: `git diff v2.4.0 -- CHANGELOG.md` shows only post-2.4.0 Unreleased entries, and `grep -n "groundwork report schedule" CHANGELOG.md` returns nothing.
- [ ] 1.2 Copy `docs/RELEASE-REPORT-2.4.md` from tag `v2.4.0`. Verify: `git diff v2.4.0 -- docs/RELEASE-REPORT-2.4.md` is empty.
- [ ] 1.3 Write the Purpose sections of the `health-dashboard` and `onboarding` main specs. Verify: `openspec validate --specs --strict` reports 10 passed.
- [ ] 1.4 Open a docs-only PR. The owner approves the merge.

## 2. M1: Task-gate hardening (F7, F8, F11, F12)

- [ ] 2.1 F7: `[[` in argument position no longer hides the commands after it. Verify: a regression test with the report's proof of concept gets `ask`.
- [ ] 2.2 F8: a carriage return is not treated as a comment boundary. Verify: a regression test gets `ask`.
- [ ] 2.3 F11: a relative or computed `cd` into the Claude config directory, followed by an edit or write there, gets `ask`. Verify: regression tests for the relative and computed forms.
- [ ] 2.4 F12: bare `~/.ssh`, `~/.gnupg`, `~/.aws` and gcloud config directory arguments count as credential access. Verify: regression tests, plus false-positive tests showing that ordinary commands (`ls src`, `git status`, `pytest`) still run without a prompt.
- [ ] 2.5 Update `docs/TASK-LIFECYCLE.md` "Limits" to reflect the fixes. Verify: `python3 tests/test_task_lifecycle.py` passes.

## 3. M1: Push guard, settings mode and snapshot (F4, F5, F6, F9, F10, F13)

- [ ] 3.1 F4: newline-separated and tightly chained commands are split before the push check. Verify: a regression test is denied.
- [ ] 3.2 F5: nested shells accept combined flags such as `-lc` and `-ec`. Verify: a regression test is denied.
- [ ] 3.3 F6: combined short flags such as `-uf` and `-fu` count as force. Verify: a regression test is denied.
- [ ] 3.4 F10: branch resolution honours `git -C <dir>` and an in-command `cd`. Verify: regression tests are denied.
- [ ] 3.5 F13: `merge_settings.py` keeps the file mode of an existing `settings.json`. Verify: a test with a 0600 file still shows 0600 after the merge.
- [ ] 3.6 F9: replace the quadratic `tasks.md` regex in the snapshot with a linear parse. Verify: a test with a large adversarial `tasks.md` finishes in under 1 s and produces the same counts as before on normal files.
- [ ] 3.7 Update the push-guard row in `docs/ARCHITECTURE.md`. Verify: `python3 -m pytest tests/test_hooks.py -q` passes.

## 4. M1: Routines (F1–F3 and the schedule bug)

- [ ] 4.1 For each routine, list the git subcommands its prompt uses. Replace `Bash(git *)` with exactly those read-only subcommands, using permission-rule syntax checked against current Claude Code documentation. Verify: unit tests assert each routine's grant set.
- [ ] 4.2 Remove `Read` from the `news` routine if its prompt does not need it; otherwise scope it to the paths it does need. Verify: a unit test asserts the grant set.
- [ ] 4.3 `groundwork routines schedule` saves the new hour and minute to `config.json`. Verify: a test shows `routines list` printing the new time after `schedule`.
- [ ] 4.4 Re-run each narrowed routine live in a sandbox config directory. Verify: each run's result file shows success, or a documented, expected "not configured" state.
- [ ] 4.5 Record F14 (`jira_eod` MCP grant) as a known limitation in the routines documentation. Verify: the docs line exists.

## 5. M1: Release 2.5.0

- [ ] 5.1 Write the CHANGELOG `## 2.5.0` entry (task tracking plus the security fixes) and `docs/RELEASE-REPORT-2.5.md`. Verify: `install.sh` derives VERSION 2.5.0 from the first heading.
- [ ] 5.2 Run the full suite. Verify: `python3 -m pytest tests -q --ignore=tests/mutation` is green, and the counts are recorded in the release report.
- [ ] 5.3 Clean install, 2.4.0 to 2.5.0 upgrade, and rollback in sandbox config directories. Verify: `groundwork version` and `setup.sh --verify` show the expected version at each step.
- [ ] 5.4 Live COR-123 acceptance with real `claude -p` and a fake `gcloud` on the release candidate, covering:
  - intake;
  - native plan;
  - no prompts for ordinary work;
  - `ask` on cloud mutation;
  - evidence;
  - completion on archive;
  - fresh-session resume.
  Verify: transcript and ledger excerpts are in the release report.
- [ ] 5.5 Fresh-context independent review to Must-fix 0, then a ChatGPT/Codex release review relayed by the owner. Verify: the `REVIEW RESULT` block and the owner's relay are recorded.
- [ ] 5.6 Owner macOS smoke test (`docs/MACOS-SMOKE-TEST.md`). Verify: the owner's result is recorded.
- [ ] 5.7 The owner approves the merge, tag and publish. Verify: `groundwork update --check` on a 2.4.0 install reports 2.5.0.
- [ ] 5.8 After the release, archive `add-task-lifecycle-gate` and the other finished changes one at a time. Verify: `openspec validate --specs --strict` passes after each.
- [ ] 5.9 Refresh `docs/FUTURE-SCOPE.md` §7 and §14 for the ledger. Verify: no line says OpenSpec-tracked work has no state file.
- [ ] 5.10 Start the two-week owner pilot. At its end, record in the release report:
  - unneeded prompts;
  - intake misclassifications;
  - resume failures.
  Verify: the pilot section exists.

## 6. R9 baseline evaluation

- [ ] 6.1 Build three reference fixtures (STANDARD bug, COR-123-style Terraform VM with a fake `gcloud`, seeded troubleshooting failure) under `tests/eval/`. Verify: each fixture's own check fails before any fix.
- [ ] 6.2 Write `tests/eval/run_eval.py`. It runs one task in one arm (plain, Groundwork with ECC, Groundwork without ECC) through `claude -p --output-format json` in an isolated config directory, then extracts the measures in design D7. Verify: a dry run on one task produces one result row.
- [ ] 6.3 After the owner approves the API usage, run 3 tasks × 3 arms × 2 runs. Verify: `docs/EVALUATION.md` holds the table, with n, spread and observed-versus-expected labels.

## 7. E: ECC optional

- [ ] 7.1 Confirm the owner's ECC choice against the R9 baseline. Archive `groundwork-2-enterprise-sre` if task 5.8 has not. Write the MODIFIED `ecc-capability-policy` delta in this change. Verify: `openspec validate groundwork-vision-roadmap --strict` passes.
- [ ] 7.2 `install.sh`:
  - installs ECC only when selected;
  - an ECC failure warns instead of aborting;
  - a machine that already has ECC keeps it.
  Verify: install tests cover selected, declined, failing and already-present.
- [ ] 7.3 `setup.sh`:
  - asks once and records the answer in `config.json`;
  - `--non-interactive` and `groundwork update` keep the detected state;
  - `--verify` reports ECC as optional, not as a failure.
  Verify: `tests/test_setup.py` cases.
- [ ] 7.4 `merge_settings.py` and `unmerge_settings.py` set or keep `hook_profile` and the GateGuard globs only when ECC is present. Verify: merge and unmerge tests both ways.
- [ ] 7.5 The task gate asks for `git commit --no-verify`, `git commit -n` and `git push --no-verify`. Verify: gate tests, including that `git commit -m msg` does not ask.
- [ ] 7.6 Native-first rule wording in `rules/engineering-workflow.md`, with ECC agents only "when installed". Update the ARCHITECTURE enforced-controls table and the README. Verify: `grep -n "ecc:" rules/` shows only lines that offer a native alternative, and `tests/test_playbooks.py` passes.
- [ ] 7.7 Live checks:
  - a clean install without ECC passes `--verify`;
  - a MATERIAL fixture completes with a native reviewer that emits `REVIEW RESULT`;
  - an upgrade on a machine with ECC leaves it enabled.
  Verify: the evidence is in the release report.
- [ ] 7.8 Release gate as in 5.2, 5.3, 5.5 and 5.7. Verify: the owner approves.

## 8. M2: Intelligent task planning

- [ ] 8.1 Read the `## Planning` section (Estimate, Depends on, Priority) from the change's artifacts, reporting unparsed lines. Verify: unit tests for each line form, en dash, revision and an unparsable line.
- [ ] 8.2 Readiness from blockers, open dependencies, untracked keys and cycles. Verify: unit tests for each `task-planning` readiness scenario.
- [ ] 8.3 `groundwork task next` with the six-key order and reasons. `list` and the snapshot use the same order and name the next task. Verify: an order test with fixed inputs and a determinism test.
- [ ] 8.4 Show estimates as labelled estimates (range, confidence, no date) in `list`, `show`, `next` and the snapshot. Verify: output tests, including the no-estimate case.
- [ ] 8.5 Multi-key intake: every new key that heads its own clause gets its own task and OpenSpec change; references do not. Verify: intake tests for the two-ticket prompt and the reference-only prompt.
- [ ] 8.6 One-time planning guidance in MATERIAL intake context. Verify: a test that it appears on creation and not on a later prompt.
- [ ] 8.7 Document `## Planning` and `next` in `docs/TASK-LIFECYCLE.md` and the PLAN playbook. Verify: `tests/test_playbooks.py` passes.
- [ ] 8.8 Live run: submit the two-ticket prompt in a sandbox with real `claude -p`. Check:
  - both tasks are recorded;
  - Claude writes `## Planning` with an estimate and `Depends on`;
  - `next` recommends the prerequisite;
  - a fresh session shows the same.
  Verify: transcript excerpts are in the release report.
- [ ] 8.9 Release gate as in 5.2, 5.3, 5.5 and 5.7, including pilot findings triaged into M2. Verify: the owner approves.

## 9. M3: Integrated developer experience

- [ ] 9.1 Add the RECORDED data class and the `task` statusLine segment (one task, or several with the next task), hideable through the `task` section. Verify: statusLine tests for each scenario and a test that no subprocess other than the bounded git call runs.
- [ ] 9.2 Integration hints in MATERIAL intake context from `integrations/cache.json`, through a small signal-to-catalog map, with "unknown" when the cache is missing. Verify: tests for a cached entry, a missing cache, and no probe subprocess.
- [ ] 9.3 Dashboard: no clipped axis or bar labels; tool and MCP rows sorted. Verify: a Playwright screenshot at desktop and phone widths, checked by eye and attached to the release report.
- [ ] 9.4 Document the statusLine segment and intake hints in `docs/ARCHITECTURE.md` and the README. Verify: the documented commands run as written.
- [ ] 9.5 Live check: COR-123 intake shows the GCP hint, and the statusLine renders the task segment with measured render time. Verify: the evidence is in the release report.
- [ ] 9.6 Release gate as in 5.2, 5.3, 5.5 and 5.7. Verify: the owner approves.

## 10. R9 re-run and close-out

- [ ] 10.1 Re-run the evaluation (plain against Groundwork as released) and compare with the baseline. Verify: `docs/EVALUATION.md` gains a dated section with observed differences.
- [ ] 10.2 Archive this change once all milestones have shipped, or first split unshipped milestones into a follow-up change. Verify: `openspec validate --specs --strict` passes.

## Verification

- `python3 -m pytest tests -q --ignore=tests/mutation`
- `openspec validate groundwork-vision-roadmap --strict`
