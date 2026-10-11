# Milestone progress record (post-2.3.0)

Purpose: let a fresh session resume the post-2.3.0 milestone programme without repeating
completed investigations. Current state only, not a log. Every row says how it was established.
Anything in this file is a hint to re-check against the repository (evidence-policy.md §8).

Last updated: 2026-10-11 (Phases 0-2 delivered; Phases 3, 4 and 7 built, first reviews fixed, confirmation reviews running; Phases 5, 6, 8 not started).

## Operating constraints (from the owner, unchanged)

- One focused branch and one draft PR per milestone. No auto-merge. No release published without
  explicit authorization.
- Never claim a test, review, deployment or runtime result that was not observed. Mark anything
  that needs hardware or accounts this environment lacks as `RUNTIME VALIDATION REQUIRED`.
- No new paid APIs or external services, no security-sensitive permission changes, no community
  code installed into a company environment without owner approval.
- Independent reviews must be dispatched from the main session (worktree-isolated subagents do not
  have the Agent tool). After a MUST FIX, only a fresh review reporting zero counts.

## Baseline (Phase 0) — VERIFIED unless marked

| Item | Value | Evidence |
|---|---|---|
| main | `24080a6` (merge of #40) | `git log`, `git fetch origin main` |
| Latest release | v2.3.0, published 2026-10-01T19:07:50Z, not draft, not prerelease | GitHub releases API |
| Tests on main | 110 passed | `python3 -m pytest tests -q` |
| OpenSpec strict | 12 of 14 pass; `spec/onboarding` and `spec/health-dashboard` fail on a placeholder `## Purpose` warning (exists at the v2.3.0 tag, not caused by any PR) | `openspec validate --all --strict` |
| CI | none: no `.github/` directory | `ls .github` |
| Claude Code in the build container | 2.1.296 | `claude --version` |
| Container limits | Linux x86_64; no `acli`, Hammerspoon, `osascript`, browser; Atlassian hosts blocked by the proxy (CONNECT 403) | `command -v`, `curl` |

## Native Claude Code facts (official docs read 2026-10-11)

| Fact | Status | Source |
|---|---|---|
| `PostToolUse` fires only on success; `PostToolUseFailure` on failure (fields incl. `error`, `is_interrupt`); calls denied by permissions or rejected before execution fire neither; cancelling a running tool fires no failure event | VERIFIED | https://code.claude.com/docs/en/hooks |
| `claude --permission-prompts host\|none`; `--permission-mode` choices `acceptEdits, auto, bypassPermissions, manual, dontAsk, plan`; background sessions `claude --bg`, `agents`, `attach`, `logs` | VERIFIED (help text; background sessions not exercised) | `claude --help` 2.1.296 |
| Mods (JS/TS plugins) run before non-managed `PreToolUse` hooks and can approve calls such a hook blocked; `permissions.deny` rules hold over a mod only where the built-in guard loads; `allowManagedModsOnly` is read from managed settings only | VERIFIED | https://code.claude.com/docs/en/plugins/mods/{overview,events,admin} |
| `/goal` exists as a Claude Code feature (named on the mods admin page); its behaviour was not read | UNVERIFIED beyond existence | admin page |

## Pull requests (all draft; none merged by this programme)

| PR | Branch | Head | State |
|---|---|---|---|
| #43 telemetry | `feat/per-tool-call-telemetry` | `ce54557` | Milestone 1a COMPLETE |
| #41 Jira acli | `feat/jira-acli-connected-probe` | `2533ea2` | Milestone 1b COMPLETE (reduced to availability-only) |
| #42 symbol presets | `feat/statusline-symbol-presets` | `1445a63` | Milestone 1c COMPLETE |
| #45 mods evaluation | `docs/claude-mods-evaluation` | `c821f46` | Milestone 2 PARTIAL |
| #44 this record | `docs/milestone-progress` | see PR | living record |
| #31 future candidates (docs) | `docs/post-release-future-candidates` | `5c2dda1` | stale base `66a382f`; holds FUTURE-SCOPE §14 (evidence references, evidence confidence, Hands-Free) that Phase 3 implements; not merged |
| (Phase 3) | `feat/evidence-receipt` | local `5b6bd1e`, **not pushed** | first reviews: 6 + 10 MUST FIX, all fixed; confirmation reviews running |
| (Phase 4) | `feat/groundwork-copilot` | local `8a94fff`, **not pushed** | first reviews: 7 + 6 MUST FIX, all fixed; confirmation reviews running |
| (Phase 7) | `feat/snapshot-worktrees` | local `3ce9410`, **not pushed** | first review: 3 MUST FIX, fixed; confirmation review running |

#41 and #43 both edit `CHANGELOG.md` under `## Unreleased` and conflict there only; the others do
not conflict (`git merge-tree`). Resolve mechanically in whichever merges second.

**The three local-only branches above exist only in the build container's worktrees** (`/home/user/groundwork`, `-copilot`, `-continuity`); if the container is lost, they are lost. Push them as soon as their confirmation reviews pass.

Experimental branch `experimental/terminal-copilot-mvp` (`1231ce3`) holds the Terminal Copilot MVP:
code complete, statically reviewed, **never run on macOS**; no PR by design.

## Milestones

| # | Milestone | Status | Evidence and what is NOT done |
|---|---|---|---|
| 0 | Baseline audit and this record | COMPLETE | PR #44 |
| 1a | #43 telemetry | COMPLETE | Reproduced and fixed: aborted calls counted as failures; "total calls" overclaim. Review 1: 1 MUST FIX (stale spec/rollback text), fixed; confirmation review: approve, 0. 112 tests. NOT done: a real abort event (RUNTIME VALIDATION REQUIRED); file rotation; `setup.sh --verify` does not count the two new hook events |
| 1b | #41 Jira acli | COMPLETE | Reproduced false CONNECTED from exit code 0; catalog now fails closed and does not run an unverified command. Review 1: 1 MUST FIX, fixed; confirmation: approve, 0. 115 tests. NOT done: observing real `acli` output (impossible here). **Owner decision:** Jira is reached by browser in the owner's setup, so keep or close |
| 1c | #42 symbol presets | COMPLETE | Default output byte-identical to main (588 cases). Review 1: 2 test-only MUST FIX, fixed and mutation-verified; confirmation: approve, 0. 115 tests. NOT done: real terminal rendering of the emoji preset |
| 2 | Claude mods | PARTIAL | Static review of five mods at pinned SHAs; Flightdeck and redgreen ADOPT-AFTER-TEST, mdview and ClaudePanel DEFER, Skins REJECT. Review found 1 MUST FIX (false overlap claim), corrected and verified directly without a second review round. NOT done: any runtime trial (needs the owner's disposable machine), so the acceptance is not demonstrated |
| 3 | Evidence references and confidence | IN CONFIRMATION REVIEW | The first version claimed the label "can be too low but never too high"; two independent reviews (security: forged HIGH via shell constructs; correctness: stale verification, review parsing, false references, cross-project transcript, redaction) disproved it with reproductions. Fixed: order-aware (a pass counts only if nothing that could change the tree came after it), stricter parsing, differential test of ~1,000 command compositions against a real bash, 28 of 29 mutants caught; the label is now documented as a best-effort **estimate** with listed known gaps. 131 tests. NOT done: judging the labels against real sessions (owner) |
| 4 | Groundwork Copilot | IN CONFIRMATION REVIEW | `groundwork copilot explain`: read-only, tmux-pane-bound (tty + process ancestry), `--stdin` for other terminals. **Found by review and verified directly:** `--tools ""` alone leaves plugin MCP tools in the model's tool list and lets a project's hooks and MCP server run; the call now uses `--safe-mode` (tool/MCP lists empty, nothing ran), prompt on stdin, scratch cwd. Also fixed: redaction after cutting, JSON/URL/PGP redaction gaps, a cubic-time regex, unredacted git facts, `git status` running `core.fsmonitor`. 119 tests, 26 mutants caught, opt-in live test. NOT done: macOS terminals (iTerm2/Terminal.app readers not built), other Claude Code versions (RUNTIME VALIDATION REQUIRED) |
| 5 | Hands-Free SRE proof of concept | not started | Needs a microphone and macOS; likely BLOCKED here |
| 6 | Autoship | not started | |
| 7 | SmartMemory | IN CONFIRMATION REVIEW | Reproducible gap found: a fresh session's snapshot showed one checkout while 2 of 8 sibling worktrees held unpushed work. Fix is one bounded section of the existing SessionStart snapshot (no new state, file or memory system). Review found a budget that was not a real bound, git failures shown as clean, and a submodule listing itself; fixed. NOT built (not needed): any stored memory |
| 8 | Final security and release audit | not started | |

## Findings carried forward to the final audit (Phase 8)

- Groundwork's settings-file hooks (push guard, review gate, telemetry) are not enforced against an
  installed Claude Code mod (docs/CLAUDE-MODS.md); `permissions.deny` holds only where the guard loads.
- `scripts/groundwork_routines.py` treats `gh auth status` exit code 0 alone as connected, the signal
  the catalog rejects (pre-existing).
- The statusline config keys are not documented in any README or docs page (pre-existing).
- OpenSpec strict baseline failures (`onboarding`, `health-dashboard`) are a one-line `## Purpose` fix each.
- Background-agent reviews arrive as later messages, not tool results, so they are not credited by the
  evidence receipt.
- `groundwork_copilot.py` and `groundwork_evidence.py` each carry their own redaction patterns; consider one shared module.
- An edit that deleted a module constant (`MAX_WALK_DIRS`) was hidden by a pre-existing `try/except: pass` in the snapshot hook and found only by an older test: audit that file for other swallowed errors.
- The snapshot hook's existing git calls (`git_facts`, `openspec_facts`) have 3 s/5 s timeouts each against a 10 s hook timeout.
- Lesson recorded: a claim that something is "safe by construction" (no tools; label never too high) was wrong twice and was caught only by an independent reviewer who ran the real thing; verify containment claims against the real CLI.

## Resume instructions

1. `git fetch`; compare `main` and the PR heads above with this table.
2. Re-run `python3 -m pytest tests -q`; expect 110 passed on main.
3. Continue at the first milestone not marked COMPLETE; open owner decisions are the Jira PR (#41),
   whether to run the mods trial, and judging the evidence labels against sessions the owner knows.
