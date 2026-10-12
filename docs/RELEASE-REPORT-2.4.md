# Groundwork 2.4.0 — release notes and report

**Release version**: 2.4.0 (MINOR: new capabilities, no removed command, no changed default).

**Status**: prepared for owner approval. Not merged, not tagged, not published.

**Release baseline**: `main` at `24080a6` (the merge of PR #40) plus PR #52 (`rc/milestone-1`), which merges the four pull requests below.

## Release notes (usable as the GitHub Release body)

Groundwork 2.4.0 adds four capabilities. None of them changes existing behaviour unless you use it.

- **Per-tool-call usage telemetry.** A small local record of which tool ran and whether the call succeeded (tool name, category, success or failure, timestamp, session id). It never stores commands, prompts, output or errors. Aborted calls are recorded as `interrupted` and kept out of the failure rate. `groundwork_report.py` gains a per-tool table. Turn it off with `GROUNDWORK_TELEMETRY=off`.
- **StatusLine symbol presets.** Two optional keys in `statusline-config.json`: `symbol_set` (`default`, `ascii`, `emoji`) and `separator` (`unicode`, `ascii`). Without them the output is unchanged.
- **Worktree awareness.** The session-start snapshot now names other worktrees of the same repository that hold work only on this machine (uncommitted changes, commits not on their upstream, or no upstream), so a new session does not forget them.
- **Groundwork Copilot.** `groundwork copilot explain` gives read-only help with what went wrong in the tmux pane you typed it in, or in text you pipe in with `--stdin`. Secret-shaped text is redacted before anything is sent, `--dry-run` shows the exact prompt without sending it, and it never runs a command.

**Upgrade**: `groundwork update` (once 2.4.0 is published) or `./setup.sh` from a clone. **What changes on upgrade**: two new hook registrations (`PostToolUse` and `PostToolUseFailure`, both for `groundwork_telemetry.py`), one new installed script (`groundwork_copilot.py`), one new file written on use (`telemetry/tool_events.jsonl`). **Rollback**: `groundwork rollback` or `./setup.sh --rollback`. Details are in [UPGRADE-ROLLBACK.md](UPGRADE-ROLLBACK.md); a short Mac check is in [MACOS-SMOKE-TEST.md](MACOS-SMOKE-TEST.md).

## 1. Scope

Derived from git history (`git log --merges origin/main..rc/milestone-1`): four merged pull requests, each reviewed before this release.

| PR | Head merged | Last reviewed commit | Recorded review |
|---|---|---|---|
| #43 per-tool-call telemetry | `ce54557` | `b3b3cc3` | confirmation review: approve, 0 MUST FIX |
| #42 statusLine symbol presets | `1445a63` | `ea63672` | confirmation review: approve, 0 MUST FIX |
| #46 snapshot worktrees | `83a5f95` | `c52b053` | fresh review: approve, 0 MUST FIX |
| #49 Groundwork Copilot | `7714bd8` | script blob `524ab82` | fresh review (round 10): approve, 0 MUST FIX |

An independent review of the integration (merge resolutions, the gaps between each reviewed commit and its head, interactions between the features) approved with 0 MUST FIX. The release-metadata commit that follows it changes only `CHANGELOG.md`, `README.md` and two new documents.

## 2. Test result

Re-run on the version-bumped tree: `python3 -m pytest tests -q` gives **134 passed** (main alone: 110; 134 = 110 + 2 for #43 + 5 for #42 + 2 for #46 + 15 for #49). `openspec validate --all --strict`: 14 pass, 2 fail; the same two specs (`onboarding`, `health-dashboard`, placeholder Purpose) fail on main, and the two new changes pass.

## 3. Runtime validation performed

In throwaway HOMEs, with the ECC step stubbed (no third-party fetch), on the version-bumped tree:

- Clean install: 10 of 10 settings checks; `setup.sh --verify` reports `Overall PASS`. A second install leaves `settings.json` and the installed tree identical (two generated state files excluded).
- Rollback restores `settings.json` byte for byte. Uninstall leaves no Groundwork entry or file and keeps user settings and data.
- Upgrade from v2.3.0: `VERSION` goes from 2.3.0 to 2.4.0 (`groundwork version` agrees), exactly two registrations are added once each, the user's telemetry file is untouched, a re-run is identical, and rollback restores the v2.3.0 tree byte for byte.
- Each feature was run and its output observed (earlier, on the release-candidate head `3b65aa6`; the code has not changed since): hook payloads containing a canary string left no canary in `tool_events.jsonl`; the three statusLine presets rendered as documented; the snapshot listed exactly the three sibling worktrees that held local-only work; the Copilot redacted all four planted secrets, refused outside tmux, and read only its own tmux pane. One real headless Claude Code run fired both new hooks and the snapshot hook (USD 0.037). One real Copilot call returned a correct explanation.
- The new hook adds a median of 33 ms per tool call on the test machine (a bare `python3` start is about 10 ms; 30 runs each).
- Every command in [MACOS-SMOKE-TEST.md](MACOS-SMOKE-TEST.md) was run on Linux with bash and passed its stated check (the optional live call excepted).

## 4. Known limitations

- **Not run on macOS.** The Copilot's tmux provider, the installer under macOS bash 3.2 and BSD tools, and path handling for worktrees (`/var` versus `/private/var`, case-insensitive file systems) are verified on Linux only. Use the smoke test.
- The `emoji` preset was checked as output bytes, never seen in a real terminal.
- A real tool-abort event was not observed; the `interrupted` path ran with payloads shaped as documented.
- `groundwork update` to a published 2.4.0 cannot be tested before it exists; the upgrade above ran `setup.sh` from a source tree.
- The real ECC and OpenSpec install step was stubbed on purpose.
- The repository has no CI; the gates are the local suite and the reviews.
- `setup.sh --verify` counts only four hook registrations, so it cannot notice a missing `PostToolUse` or `PostToolUseFailure` entry.
- `tool_events.jsonl` has no rotation (about 130 bytes per tool call).
- `ascii` does not make the whole statusLine ASCII (the git marker and the `·` joiners stay); only `plain_text` does.

## 5. Deliberately excluded work

The evidence receipt (#47, review loop not closed), the Jira `acli` probe (#41, owner decision pending), the Claude mods evaluation (#45), and the documentation-only pull requests (#44, #48, #50, #51). Nothing in this release depends on them.

## 6. Compatibility statement

No removed command, no changed flag, no changed default. The statusLine default output equals 2.3.0's on the same input. `groundwork` gains one sub-command (`copilot`). Claude Code 2.1 or newer is still the documented requirement (`install.sh` prints the detected version and does not enforce it); this release was exercised on Claude Code 2.1.296.

## 7. Release and tag information

- **Proposed tag**: `v2.4.0`, annotated, on the merge commit of PR #52. Use a **merge commit**, not a squash, so that #43, #42, #46 and #49 are marked merged.
- **Version mechanism**: `groundwork update` refuses to install a release whose top `CHANGELOG.md` entry does not match its tag. The top entry is `## 2.4.0` (checked with the update code's own parser, which returns `(2, 4, 0)`), and `install.sh` writes `VERSION` from the same line.
- **Date**: `CHANGELOG.md` carries 2026-10-11, the day this was prepared. Change it before tagging if the tag is made on another day.
- **Approval**: nothing has been merged, tagged or published; each needs the repository owner's approval.
