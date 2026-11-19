# Groundwork 2.6.0 — release notes and report

**Release version**: 2.6.0 (MINOR: new checks and commands, no removed command, no changed flag).

**Status**: prepared on 2026-11-19 on `feat/sha-bound-review` (PR #84). The owner approved this scope on 2026-11-19:
merge the approved PRs (#83 and #84), run one upgrade smoke test, require the `review-check` status check on `main`,
and publish 2.6.0 if those checks pass. The coordination demo and the comparative benchmark stay as remaining work.

## Release notes (usable as the GitHub Release body)

Groundwork 2.6.0 binds independent review to the exact code it covered and checks it again in CI. It also checks the
files and lines that replies cite, warns about changes outside a task's plan, and defines the permission tiers in one
place.

- **Review bound to the code.** A review counts only from a reviewer subagent whose REVIEW RESULT block reports
  `Must-fix: 0` and names the content fingerprint it reviewed (`groundwork task fingerprint`). A code change after
  the review makes it stale. Inline Skill reviews and the author's own text do not count.
- **Pull request review.** A non-draft `gh pr create` / `gh pr new`, or a `gh pr edit` that sets the description, is
  denied until such a review covers the commit being published. The new `review-check` workflow fails a PR whose
  description does not record an approval of its head. `main` requires that check from GitHub Actions.
- **Citation check.** When a reply cites a repository file that does not exist, or a line past the end of a file,
  Claude is asked once to correct it.
- **Scope control.** `groundwork task note` records an unrelated finding without starting work on it. `show` and
  `complete` warn about changed files the plan never names and TODOs added during the task.
- **Permission tiers.** HARD DENY, HUMAN APPROVAL and AUTONOMOUS are defined in `docs/PERMISSIONS.md`, mapped to the
  native deny rules and the existing hooks, and probed through the real hooks.
- **Coordination runbook.** `docs/COORDINATION.md` describes one coordinating session plus background sessions in
  their own worktrees, using native Claude Code and the task ledger. No orchestrator.
- **Also included:** outcome by context fill on the health dashboard, the opt-in OpenSpec store for task files, the
  compact reply format, and CLI tests that no longer touch the real LaunchAgents report job.

**Upgrade**: `groundwork update`, or `git pull` and `./setup.sh` (or `./install.sh`) from a clone. Then start a new
Claude Code session.

**What changes on upgrade**: no new hook registrations (15, as in 2.5.0). The existing hook scripts are replaced.
No new files are written on install.

## 1. Test result

- Full suite before the last two commits: 21 test files, every file run directly. 20 passed on the first run.
  `test_groundwork_routines.py` had 1 failing check of 172: it depends on live `claude mcp list` output, also fails
  sometimes on `main`, and passed 172/172 on a rerun.
- After the `gh pr edit` gate: review independence 31, hooks 414, permission tiers 43, evidence validation 22, scope
  control 14, reply check 66, task lifecycle 206. All passed, in our run and again in the independent reviewer's run.
- PR #83: `tests/test_groundwork_cli.py` 83 passed in the reviewer's run, and the real report plist was unchanged.
- `openspec validate --all --strict`: 24 passed, 0 failed.

## 2. Runtime validation performed

**Upgrade smoke test** on macOS, in a throwaway HOME, with the ECC fetch stubbed (the recipe in MACOS-SMOKE-TEST.md),
`GROUNDWORK_NO_LAUNCHCTL=1`:
- `setup.sh --non-interactive` from v2.5.0: exit 0, `VERSION` 2.5.0, 15 hook entries.
- Upgrade from this tree: exit 0, `VERSION` 2.6.0, 15 hook entries. `setup.sh --verify` reports Overall PASS.
- A second run leaves `settings.json` byte-for-byte identical.
- The installed task gate denies `gh pr create` with no review: "no independent reviewer subagent reviewed …".
- `setup.sh --rollback` to the pre-upgrade backup restores `VERSION` 2.5.0 and 15 hook entries.
- The tree tested is PR #84's head. PR #83 changes only `tests/test_groundwork_cli.py`, which is not installed.

**Live runs** (earlier in this change): a real `claude -p` run with this branch's hooks denied `gh pr create` without
a review, asked before `cat .env`, denied `git push origin main`, and asked once about a citation of `app.py:999`,
which Claude corrected. The Stop gate blocked with no review, passed after a background reviewer approved the current
code, and blocked again after an edit.

**GitHub**: `review-check` failed on PR #84's old description and passed after the approved review block was recorded.
CI computed the same fingerprint as the local tool.

## 3. Independent reviews

- PR #84: several fresh reviewers across the commits. One MUST FIX (`gh pr new` skipped the PR check) was fixed and
  re-reviewed. The final review of the complete PR approved with Must-fix 0.
- PR #83: a fresh reviewer approved with Must-fix 0.
- The release commit (this report, CHANGELOG, README) is covered by its own fresh review, recorded on PR #84.

## 4. Known limitations

- **The review record is not a hard guarantee.** The checks prove that a fresh-context reviewer reported on the exact
  code, not that the review was thorough. Anyone who can edit a PR description can type the block, and a
  `pull_request` workflow runs the PR's own code. A hard guarantee needs a second identity, such as a required
  approving review from another account or app. See `docs/PERMISSIONS.md`.
- **Local parsing gaps** (CI is the backstop): an attached short flag (`-bTEXT`) and `gh api` writes are not parsed;
  `gh pr edit N` checks the local HEAD; `git commit && gh pr create` in one command is denied, which is safe.
- **The subagent transcript layout** is observed in Claude Code 2.1.316, not documented. If it changes, the gate
  blocks rather than allows.
- **Claude Projects cloud threads** do not load hooks or permission rules. `disableAllHooks` switches every hook off,
  and only a managed policy can prevent that.
- **A harmless warning:** `hooks/groundwork_task_gate.py` raises a `SyntaxWarning` (an escape sequence in a docstring).
- **Untested before publishing:** `groundwork update` to the published 2.6.0 cannot be tested before the release
  exists.

## 5. Remaining work (not verified in this release)

- **Coordination demo.** The end-to-end run in `docs/COORDINATION.md` has not happened. Claude Code refuses
  `claude --bg` in a folder the owner has not trusted, and accepting workspace trust is the owner's decision.
- **Comparative benchmark.** `openspec/changes/harden-autonomy-evidence-review/benchmark.md` defines arms V (plain
  Claude Code), G (Groundwork 2.5.0) and U (2.6.0). A 1-case calibration reports the projected cost, and the 30-run
  pilot runs only after budget approval.

## 6. Compatibility statement

- No removed command, no changed flag.
- `groundwork task` gains `note` and `fingerprint`.
- New checks: the PR review deny, the citation ask-once, and the scope warnings (warnings never block).
- Exercised on Claude Code 2.1.316 and gh 2.105.0.

## 7. Release and tag information

- **Tag**: `v2.6.0`, annotated, on the merge of PR #84 into `main`, after PR #83 is merged.
- **Version mechanism**: `install.sh` writes `VERSION` from the first `## X.Y.Z` heading of `CHANGELOG.md`, and
  `groundwork update` checks that heading against the tag. The top entry is `## 2.6.0 — 2026-11-19`.
