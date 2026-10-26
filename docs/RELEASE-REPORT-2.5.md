# Groundwork 2.5.0 — release notes and report

**Release version**: 2.5.0 (MINOR: new capabilities and security fixes, no removed command, no changed default).

**Status**: prepared on 2026-10-26 on the `release/2.5.0` branch. The owner approved this scope on 2026-10-26: merge PR #61, then release.

**Release baseline**: `main` at `0fca8a2` (the merge of PR #61), plus this release metadata.

## Release notes (usable as the GitHub Release body)

Groundwork 2.5.0 moves the evidence and continuity rules from "asked for" to "checked by hooks", fixes the security findings of the 2026-10-12 scan, and ships task tracking around native OpenSpec as a controlled pilot.

- **Reply format check.**
  - Every prompt gets a short format reminder. When the request clearly matches one task type, it also gets that playbook's Output Format.
  - When a tool-using reply is missing a plain-language result, `Technical details` (when commands ran), an `Evidence & references` section with a link or `file:line`, or the `HARNESS METADATA` block, Claude is asked once to add only the missing part.
  - Chat turns are never touched. Claude Code shows the one-time request as "Stop hook error"; that is its label for any Stop-hook request, not a failure.
  - Turn it off with `GROUNDWORK_REPLY_CHECK=off`.
- **Task brief and decision log.**
  - One brief per repository branch, under `~/.claude/groundwork/briefs/`. It is saved before every compaction (manual or automatic) and after each tool-using turn, and reloaded at the start of every session.
  - An append-only decision log keeps every decision and rejected option with the links it cites. Lines with no source are marked `no evidence cited`.
  - Claude is asked once per session to fill an empty brief or to add evidence to a decision that has none.
  - Turn it off with `GROUNDWORK_BRIEF=off`.
- **`groundwork usage`.**
  - Ranks sessions by how much they used in the last 5 hours or 7 days, from records the Groundwork statusLine writes (ids and numbers only).
  - The statusLine can show `5h NN%`, or `spend NN%` behind a Claude apps gateway.
  - Claude Code's own `/status` → Usage view covers much of the same ground for the last 24 hours.
- **Security fixes (scan of 2026-10-12, F1-F13; F14 deferred with a justification).**
  - The push guard now catches protected-branch and force pushes hidden behind separators, subshells, wrappers, quoting or computed destinations. It denies a push it cannot check.
  - The task gate catches more hidden commands, credential directories and settings or hook edits.
  - Settings permissions are tightened, routine grants are narrowed, and the routine schedule time is now recorded.
- **Task tracking around native OpenSpec (pilot).** Engineering tasks are recorded automatically, kept across sessions and completed only on evidence. Sensitive actions show Claude Code's normal permission prompt.
- **New-machine checklist.** A 10-minute live check per feature, in [NEW-MACHINE-CHECKS.md](NEW-MACHINE-CHECKS.md). Step 0 shows how to find a company policy (`allowManagedHooksOnly`, `disableAllHooks`) that would switch all hooks off.

**Upgrade**: `groundwork update`, or `git pull` and `./setup.sh` (or `./install.sh`) from a clone. Then start a new Claude Code session.

**What changes on upgrade**:
- New hook scripts: `groundwork_reply_check.py` and `groundwork_brief.py`. Hook registrations go from 6 (2.4.0) to 15, including the task gate's 4.
- New files written on use: `briefs/`, `telemetry/usage.jsonl`.

**Rollback**: `groundwork rollback` or `./setup.sh --rollback`. See [UPGRADE-ROLLBACK.md](UPGRADE-ROLLBACK.md).

## 1. Scope

Derived from `git log --merges v2.4.0..main`. Every code pull request was reviewed before merge.

| PR | What | Recorded review |
|---|---|---|
| #54, #56 | task tracking around native OpenSpec; README rewrite | reviewed in their PRs (pre-2.5 work on `main`) |
| #55, #57, #60 | fresh-session proof; macOS test fixes; reconcile main with 2.4.0 | reviewed in their PRs |
| #61 | security release blockers F1-F13 | five adversarial rounds, final review approve, 0 MUST FIX at `a1db5ae`; integration review of #61 merged with main (`a643e27`): approve, 0 MUST FIX |
| #66 | reply format check, strict Evidence section | approve, 0 MUST FIX (two rounds) |
| #67 | usage visibility | round 1: 1 MUST FIX (session name stored), fixed; round 2: approve, 0 MUST FIX |
| #69 | task brief and decision log | four rounds, each MUST FIX fixed with a test; final approve, 0 MUST FIX; decision log: approve, 0 MUST FIX |
| #68 | new-machine checklist (docs) | not separately reviewed (docs only) |
| #70 | usage records follow the config dir (test leak into `~/.claude`) | approve, 0 MUST FIX |

## 2. Test result

- **Release tree:** `python3 -m pytest tests -q --ignore=tests/mutation -p no:cacheprovider` on macOS gives **158 passed** (7 warnings, 446 s).
- **#61 merged with main (`a643e27`):**
  - First run: 157 passed, 1 failed. The failure was `test_snapshot_worktrees`, a wall-clock budget check. It passed 2 of 2 when re-run alone, and the snapshot code is byte-identical to #61's.
  - Second full run: 158 passed.
- **One earlier failure** during these merges was a timing race in `test_invalid_symbol_set_and_separator_fall_back_safely`: two renders printed cache ages "0s" and "1s". It is fixed by freezing the test's clock (`011eb50`).

## 3. Runtime validation performed

**Upgrade test** on macOS, in a throwaway HOME, with the ECC fetch stubbed (the recipe in MACOS-SMOKE-TEST.md):
- `setup.sh --non-interactive` from v2.4.0 gives `VERSION` 2.4.0 and 6 hook entries.
- Upgrading from this tree gives `VERSION` 2.5.0 and 15 hook entries. `setup.sh --verify` reports Overall PASS, and `groundwork version` prints `Groundwork 2.5.0`.
- A second run leaves `settings.json` byte-for-byte identical.
- `setup.sh --rollback` to the pre-upgrade backup restores `VERSION` 2.4.0, and `settings.json` is byte-for-byte identical to the 2.4.0 install.

**Live `claude -p` runs**, with the new hooks added through `--settings`:
- **Reply check:** a tool turn that replied only "3" got one request and was completed with Technical details, an evidence link and the metadata block. A chat turn ("2+2") was untouched.
- **Strict evidence:** an ordinary request got one request, and the follow-up listed the command output and the man page.
- **Brief:**
  - a new session answered with the brief's next step without reading any file;
  - a real `/compact` on a resumed session refreshed the snapshot ("updated by: PreCompact") and kept the written Goal;
  - a decision added without a source was logged as `no evidence cited` and asked about once.

**Interactive check on the owner's Mac after installing `main`:**
- The prompt reminder appeared in a running session; Claude Code reloads hooks when settings change.
- The brief hook asked once for Goal and Next step, and the brief was written.

## 4. Known limitations

- **`groundwork usage` needs Groundwork's statusLine.** Groundwork never replaces a statusLine you already have. With another tool's statusLine (seen on the owner's Mac), no usage records are written. Claude Code's `/status` → Usage shows a 24-hour view instead.
- **Automatic compaction was not observed live.** It fires the same PreCompact event as `/compact`, which was tested.
- **The reply check costs one short follow-up** whenever a tool-using reply lacks the Evidence section. On the 40 saved benchmark answers, 34 would have needed one.
- **The task-tracking pilot:**
  - its prompt intake can record a pasted conversation log as a task;
  - in `claude -p` workspaces it can write an `openspec/` folder.
- **Timing-sensitive tests:** the lifecycle tests (60-second subprocess timeouts) and `test_snapshot_worktrees` can fail on a heavily loaded machine. They pass when re-run.
- **A harmless warning:** `hooks/groundwork_task_gate.py` raises a `SyntaxWarning` (an escape sequence in a docstring).
- **Managed work machines:** a policy setting `allowManagedHooksOnly` or `disableAllHooks` switches all Groundwork hooks off. See NEW-MACHINE-CHECKS.md step 0.
- **Untested before publishing:** `groundwork update` to a published 2.5.0 cannot be tested before the release exists. The real ECC install step was stubbed on purpose.
- **No CI:** the gates are the local suite and the reviews.

## 5. Deliberately excluded work

- The orchestrator add-on (PRs #62, #64, #65), parked after measurement.
- The plan document (PR #63).
- Evidence features 1 (benchmark in core) and 5 (decision gate), which wait for an owner decision because they spend plan quota.
- Feature 4 (citation check), not built after measurement (852 citations, 0 real errors, 6 of 6 flags false).

## 6. Compatibility statement

- No removed command, no changed flag.
- The new hooks are on by default, and each has its own off switch.
- `groundwork` gains one sub-command (`usage`). The statusLine gains one setting (`show_plan_usage`, default on, shown only when Claude Code sends plan usage).
- Exercised on Claude Code 2.1.310.

## 7. Release and tag information

- **Tag**: `v2.5.0`, annotated, on the merge of `release/2.5.0` into `main`.
- **Version mechanism**: `install.sh` writes `VERSION` from the first `## X.Y.Z` heading of `CHANGELOG.md`, and `groundwork update` checks that the same heading matches the tag (`scripts/groundwork_update.py:180-186`). The top entry is `## 2.5.0 — 2026-10-26`.
- **Approval**: the owner approved "Merge #61, then release 2.5.0" on 2026-10-26.
