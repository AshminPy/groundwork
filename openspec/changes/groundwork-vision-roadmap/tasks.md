# Tasks

Planning only until the owner approves. Groups follow the milestone order in design D1. Each milestone ends with its own release gate. Tasks follow the recommended answers to the owner decisions in design.md. If the owner chooses otherwise, revise the affected tasks before applying.

Each task carries a work class (design D10):
- **[release-critical]** blocks its own milestone's release;
- **[product-critical]** is planned for the milestone but moves to the next release, with a note, if it is not ready;
- **[optional]** never blocks anything.

## 1. M0: Reconcile `main` with the released 2.4.0 (docs only, minimal)

- [x] 1.1 [release-critical] Replace `main`'s `## 2.4.0` CHANGELOG section with the one at tag `v2.4.0` (dated 2026-10-13, with the macOS fix bullets). Remove the already-released macOS entry, including the `groundwork report schedule` text, from Unreleased. Verify:
  - every section from `## 2.4.0` to the end is byte-identical to `git show v2.4.0:CHANGELOG.md`;
  - `## Unreleased` is still the first heading and holds only post-2.4.0 entries;
  - `grep -n "groundwork report schedule" CHANGELOG.md` returns nothing.
- [x] 1.2 [release-critical] Check that version behaviour is unchanged (design D11). Verify:
  - `grep -m1 -oE '^## [0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md` prints `## 2.4.0`;
  - `_top_changelog_version` from `scripts/groundwork_update.py` returns 2.4.0 for the file;
  - `python3 tests/test_groundwork_update.py` and `python3 -m pytest tests -q --ignore=tests/mutation` pass.
- [x] 1.3 [product-critical] Copy `docs/RELEASE-REPORT-2.4.md` from tag `v2.4.0`. Verify: `git diff v2.4.0 -- docs/RELEASE-REPORT-2.4.md` is empty.
- [x] 1.4 [release-critical] Open a docs-only PR containing nothing beyond 1.1–1.3. Done: #60, independently reviewed (approved, 0 MUST FIX), merged by owner approval as 086216d.

## 2. M1: Task-gate hardening (F7, F8, F11, F12)

- [ ] 2.1 [release-critical: blocker] F7: `[[` in argument position no longer hides the commands after it. Verify: a regression test with the report's proof of concept gets `ask`.
- [ ] 2.2 [release-critical: blocker] F8: a carriage return is not treated as a comment boundary. Verify: a regression test gets `ask`.
- [ ] 2.3 [product-critical] F11: a relative or computed `cd` into the Claude config directory, followed by an edit or write there, gets `ask`. Verify: regression tests for the relative and computed forms.
- [ ] 2.4 [release-critical: blocker] F12: bare `~/.ssh`, `~/.gnupg`, `~/.aws` and gcloud config directory arguments count as credential access. Verify: regression tests, plus false-positive tests showing that ordinary commands (`ls src`, `git status`, `pytest`) still run without a prompt.
- [ ] 2.5 [release-critical] Update `docs/TASK-LIFECYCLE.md` "Limits" to reflect the fixes. Verify: `python3 tests/test_task_lifecycle.py` passes.

## 3. M1: Push guard, settings mode and snapshot (F4, F5, F6, F9, F10, F13)

- [ ] 3.1 [release-critical: blocker] F4: newline-separated and tightly chained commands are split before the push check. Verify: a regression test is denied.
- [ ] 3.2 [release-critical: blocker] F5: nested shells accept combined flags such as `-lc` and `-ec`. Verify: a regression test is denied.
- [ ] 3.3 [release-critical: blocker] F6: combined short flags such as `-uf` and `-fu` count as force. Verify: a regression test is denied.
- [ ] 3.4 [product-critical] F10: branch resolution honours `git -C <dir>` and an in-command `cd`. Verify: regression tests are denied.
- [ ] 3.5 [release-critical: blocker] F13: `merge_settings.py` keeps the file mode of an existing `settings.json`. Verify: a test with a 0600 file still shows 0600 after the merge.
- [ ] 3.6 [product-critical] F9: replace the quadratic `tasks.md` regex in the snapshot with a linear parse. Verify: a test with a large adversarial `tasks.md` finishes in under 1 s and produces the same counts as before on normal files.
- [ ] 3.7 [release-critical] Update the push-guard row in `docs/ARCHITECTURE.md`. Verify: `python3 -m pytest tests/test_hooks.py -q` passes.

## 4. M1: Routines (F1–F3, F14 and the schedule bug)

- [ ] 4.1 [release-critical: blocker] F1 and F2: list the git subcommands each routine's prompt uses. Replace `Bash(git *)` with exactly those read-only subcommands, using permission-rule syntax checked against current Claude Code documentation. Verify: unit tests assert each routine's grant set.
- [ ] 4.2 [product-critical] F3: remove `Read` from the `news` routine if its prompt does not need it; otherwise scope it to the paths it does need. Verify: a unit test asserts the grant set.
- [ ] 4.3 [product-critical] `groundwork routines schedule` saves the new hour and minute to `config.json`. Verify: a test shows `routines list` printing the new time after `schedule`.
- [ ] 4.4 [release-critical] Re-run each narrowed routine live in a sandbox config directory. Verify: each run's result file shows success, or a documented, expected "not configured" state.
- [ ] 4.5 [release-critical] Record F14 (`jira_eod` MCP grant) as a known limitation in the routines documentation, with the deferral justification from design D2. Verify: the docs line exists and names the justification.

## 5. M1: Release 2.5.0

- [ ] 5.1 [release-critical] Write the CHANGELOG `## 2.5.0` entry (task tracking plus the security fixes) and `docs/RELEASE-REPORT-2.5.md`. The report lists each finding's D2 class and disposition, and any product-critical item that moved to a later release. Verify:
  - `install.sh` derives VERSION 2.5.0 from the first heading;
  - every D2 release blocker is marked fixed, with its regression test named.
- [ ] 5.2 [release-critical] Run the full suite. Verify: `python3 -m pytest tests -q --ignore=tests/mutation` is green, and the counts are recorded in the release report.
- [ ] 5.3 [release-critical] Clean install, 2.4.0 to 2.5.0 upgrade, and rollback in sandbox config directories. Verify: `groundwork version` and `setup.sh --verify` show the expected version at each step.
- [ ] 5.4 [release-critical] Live COR-123 acceptance with real `claude -p` and a fake `gcloud` on the release candidate, covering:
  - intake;
  - native plan;
  - no prompts for ordinary work;
  - `ask` on cloud mutation;
  - evidence;
  - completion on archive;
  - fresh-session resume.
  Verify: transcript and ledger excerpts are in the release report.
- [ ] 5.5 [release-critical] Fresh-context independent review to Must-fix 0, then a ChatGPT/Codex release review relayed by the owner. Verify: the `REVIEW RESULT` block and the owner's relay are recorded.
- [ ] 5.6 [release-critical] Owner macOS smoke test (`docs/MACOS-SMOKE-TEST.md`). Verify: the owner's result is recorded.
- [ ] 5.7 [release-critical] The owner approves the merge, tag and publish. Verify: `groundwork update --check` on a 2.4.0 install reports 2.5.0.
- [ ] 5.8 [product-critical] Write the Purpose sections of the `health-dashboard` and `onboarding` main specs. Verify: `openspec validate --specs --strict` reports every spec passed.
- [ ] 5.9 [product-critical] After the release, archive `add-task-lifecycle-gate` and the other finished changes one at a time. Verify: `openspec validate --specs --strict` passes after each.
- [ ] 5.10 [product-critical] Refresh `docs/FUTURE-SCOPE.md` §7 and §14 for the ledger. Verify: no line says OpenSpec-tracked work has no state file.
- [ ] 5.11 [product-critical] Start the owner pilot when 2.5.0 is published. It has no fixed duration. Log findings in the release report as they occur: unneeded prompts, intake misclassifications and resume failures. Verify: the pilot section exists, and each finding is tagged with the area it touches (intake, ledger, gate, completion, other).

## 6. R9 baseline evaluation

- [ ] 6.1 [product-critical] Build three reference fixtures (STANDARD bug, COR-123-style Terraform VM with a fake `gcloud`, seeded troubleshooting failure) under `tests/eval/`. Verify: each fixture's own check fails before any fix.
- [ ] 6.2 [product-critical] Write `tests/eval/run_eval.py`. It runs one task in one arm (plain, Groundwork with ECC, Groundwork without ECC) through `claude -p --output-format json --max-budget-usd <cap>` in an isolated config directory, using the per-run caps in design D7. It records whether a run hit its cap, then extracts the D7 measures. Verify: a unit test checks that each run type gets its cap.
- [ ] 6.3 [product-critical] Ask the owner to authorize the stated maximum of $69.00 for the baseline (25 capped runs, design D7). Verify: the authorization is recorded before any run.
- [ ] 6.4 [product-critical] Dry run: one STANDARD task in one arm, within its cap. Verify: it produces one result row and its observed cost.
- [ ] 6.5 [product-critical] Run 3 tasks × 3 arms × 2 runs, plus the 6 resume runs. Verify: `docs/EVALUATION.md` holds the table, with n, spread, observed-versus-expected labels, the capped runs, and the observed total against the $69.00 maximum.

## 7. E: ECC optional

- [ ] 7.1 [product-critical] The owner picks the ECC default for new installs from the R9 baseline. Then:
  - archive `groundwork-2-enterprise-sre` if task 5.9 has not;
  - write the MODIFIED `ecc-capability-policy` delta in this change;
  - write the `task-lifecycle` delta for the `--no-verify` hard block.
  Verify: the decision is recorded in design D8, and `openspec validate groundwork-vision-roadmap --strict` passes.
- [ ] 7.2 [release-critical] `install.sh`:
  - installs ECC only when selected;
  - an ECC failure warns instead of aborting;
  - a machine that already has ECC keeps it.
  Verify: install tests cover selected, declined, failing and already-present.
- [ ] 7.3 [release-critical] `setup.sh`:
  - asks once, offering the owner-chosen default, and records the answer in `config.json`;
  - `--non-interactive` and `groundwork update` keep the detected state;
  - `--verify` reports ECC as optional, not as a failure.
  Verify: `tests/test_setup.py` cases.
- [ ] 7.4 [release-critical] `merge_settings.py` and `unmerge_settings.py` set or keep `hook_profile` and the GateGuard globs only when ECC is present. Verify: merge and unmerge tests both ways.
- [ ] 7.5 [release-critical] The task gate denies `git commit --no-verify`, `git commit -n` and `git push --no-verify`, with or without ECC. This keeps today's hard block; changing it to `ask` is out of scope and would need separate owner approval (design D8). Verify:
  - gate tests for every bypass form, run with ECC present and absent;
  - a test that `git commit -m msg` is not denied;
  - a live check that a real `claude -p` session cannot run the bypass.
- [ ] 7.6 [release-critical] Native-first rule wording in `rules/engineering-workflow.md`, with ECC agents only "when installed". Update the ARCHITECTURE enforced-controls table and the README: `--no-verify` is now enforced by Groundwork, and "investigate before edit" is enforced only with ECC. Verify: `grep -n "ecc:" rules/` shows only lines that offer a native alternative, and `tests/test_playbooks.py` passes.
- [ ] 7.7 [release-critical] Live checks:
  - a clean install without ECC passes `--verify`;
  - a MATERIAL fixture completes with a native reviewer that emits `REVIEW RESULT`;
  - an upgrade on a machine with ECC leaves it enabled.
  Verify: the evidence is in the release report.
- [ ] 7.8 [release-critical] Release gate as in 5.2, 5.3, 5.5 and 5.7. Verify: the owner approves.

## 8. M2: Intelligent task planning

- [ ] 8.0 [product-critical] Once 2.5.0 is published, start M2 on its own branch off `main`. This may run during the pilot (design D10). Verify: the branch exists and nothing from it merges before 8.9.
- [ ] 8.1 [product-critical] Read the `## Planning` section (Estimate, Depends on, Priority) from the change's artifacts, reporting unparsed lines. Verify: unit tests for each line form, en dash, revision and an unparsable line.
- [ ] 8.2 [product-critical] Readiness from blockers, open dependencies, untracked keys and cycles. Verify: unit tests for each `task-planning` readiness scenario.
- [ ] 8.3 [product-critical] `groundwork task next` with the six-key order and reasons. `list` and the snapshot use the same order and name the next task. Verify: an order test with fixed inputs and a determinism test.
- [ ] 8.4 [product-critical] Show estimates as labelled estimates (range, confidence, no date) in `list`, `show`, `next` and the snapshot. Verify: output tests, including the no-estimate case.
- [ ] 8.5 [product-critical] Multi-key intake: every new key that heads its own clause gets its own task and OpenSpec change; references do not. Verify: intake tests for the two-ticket prompt and the reference-only prompt.
- [ ] 8.6 [product-critical] One-time planning guidance in MATERIAL intake context. Verify: a test that it appears on creation and not on a later prompt.
- [ ] 8.7 [product-critical] Document `## Planning` and `next` in `docs/TASK-LIFECYCLE.md` and the PLAN playbook. Verify: `tests/test_playbooks.py` passes.
- [ ] 8.8 [release-critical] Live run: submit the two-ticket prompt in a sandbox with real `claude -p`. Check:
  - both tasks are recorded;
  - Claude writes `## Planning` with an estimate and `Depends on`;
  - `next` recommends the prerequisite;
  - a fresh session shows the same.
  Verify: transcript excerpts are in the release report.
- [ ] 8.9 [release-critical] M2 merge gate. Verify:
  - every pilot finding logged in 5.11 that touches intake, the ledger, the gate or completion is fixed on `main` or explicitly deferred with a reason;
  - at least one real MATERIAL task went from intake to completion or cancellation on 2.5.0;
  - the M2 branch has merged `main` and passes the full suite;
  - then the release gate as in 5.2, 5.3, 5.5 and 5.7, with owner approval.

## 9. M3: Integrated developer experience

- [ ] 9.1 [product-critical] Add the RECORDED data class and the `task` statusLine segment (one task, or several with the next task), hideable through the `task` section. Verify: statusLine tests for each scenario and a test that no subprocess other than the bounded git call runs.
- [ ] 9.2 [product-critical] Integration hints in MATERIAL intake context from `integrations/cache.json`, through a small signal-to-catalog map, with "unknown" when the cache is missing. Verify: tests for a cached entry, a missing cache, and no probe subprocess.
- [ ] 9.3 [optional] Dashboard: no clipped axis or bar labels; tool and MCP rows sorted. Verify: a Playwright screenshot at desktop and phone widths, checked by eye. This never blocks the M3 release.
- [ ] 9.4 [release-critical] Document the statusLine segment and intake hints in `docs/ARCHITECTURE.md` and the README. Verify: the documented commands run as written.
- [ ] 9.5 [release-critical] Live check: COR-123 intake shows the GCP hint, and the statusLine renders the task segment with measured render time. Verify: the evidence is in the release report.
- [ ] 9.6 [release-critical] Release gate as in 5.2, 5.3, 5.5 and 5.7. Optional tasks are not part of the gate. Verify: the owner approves.

## 10. R9 re-run and close-out

- [ ] 10.1 [product-critical] Re-run the evaluation (plain against Groundwork as released) after the owner authorizes its own stated maximum, computed as in design D7. Compare with the baseline. Verify: `docs/EVALUATION.md` gains a dated section with observed differences and the observed cost.
- [ ] 10.2 [product-critical] Archive this change once all milestones have shipped, or first split unshipped milestones into a follow-up change. Verify: `openspec validate --specs --strict` passes.

## Verification

- `python3 -m pytest tests -q --ignore=tests/mutation`
- `openspec validate groundwork-vision-roadmap --strict`
