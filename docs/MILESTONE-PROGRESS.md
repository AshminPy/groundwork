# Milestone progress record (post-2.3.0)

Purpose: let a fresh session resume the post-2.3.0 milestone programme without repeating
completed investigations. Current state only, not a log. Every row says how it was established.
Anything in this file is a hint to re-check against the repository (evidence-policy.md §8).

Last updated: 2026-10-11 (Phase 0 complete).

## Operating constraints (from the owner, unchanged)

- One focused branch and one draft PR per milestone. No auto-merge. No release published without
  explicit authorization.
- Never claim a test, review, deployment or runtime result that was not observed. Mark anything
  that needs hardware or accounts this environment lacks as `RUNTIME VALIDATION REQUIRED`.
- No new paid APIs or external services, no security-sensitive permission changes, no community
  code installed into a company environment without owner approval.
- Independent reviews must be dispatched from the main session (worktree-isolated subagents do not
  have the Agent tool).

## Baseline (Phase 0) — VERIFIED unless marked

| Item | Value | Evidence |
|---|---|---|
| main | `24080a6` (merge of #40) | `git log`, `git fetch origin main` |
| Latest release | v2.3.0, published 2026-10-01T19:07:50Z, not draft, not prerelease | GitHub releases API |
| Tests on main | 110 passed, 0 failed (78 s) | `python3 -m pytest tests -q` |
| OpenSpec strict | 12 of 14 pass; `spec/onboarding` and `spec/health-dashboard` fail on a placeholder `## Purpose` warning | `openspec validate --all --strict`; both specs also exist at the v2.3.0 tag, so this is pre-existing, not caused by any open PR |
| CI | none: no `.github/` directory | `ls .github` |
| Claude Code in this container | 2.1.296 | `claude --version` |
| Container limits | Linux x86_64; no `acli`, `jira`, Hammerspoon, `osascript` or Chromium; `gh` present | `command -v` |

Hooks Groundwork registers (4): `block_protected_push.py` (PreToolUse), `require_material_review.py`
and `groundwork_telemetry.py` (Stop), `groundwork_session_snapshot.py` (SessionStart) — from
`scripts/merge_settings.py`. Deny rules include `sudo`, `rm -rf /*`, `rm -rf ~*`, `chmod 777`,
`git push --force*`, `dd`, `mkfs*`, `diskutil erase*`. Integration catalog: GitHub, Spacelift, Jira,
Confluence, AWS, GCP, Kubernetes, Terraform, Grafana, Datadog (`scripts/groundwork_integrations.py`).

## Native Claude Code facts checked this session

| Fact | Status | Source |
|---|---|---|
| 33 hook events exist, including `PostToolUse` and `PostToolUseFailure` | VERIFIED | https://code.claude.com/docs/en/hooks |
| `PostToolUse` fires only after a tool completes successfully; input has `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, optional `duration_ms` | VERIFIED | same page |
| `PostToolUseFailure` fires when a started tool throws or an MCP tool returns an error; input has `tool_name`, `tool_input`, `tool_use_id`, `error`, optional `is_interrupt`, optional `duration_ms`; no `tool_response` | VERIFIED | same page |
| A call rejected before execution (unknown tool, failed validation, permission denial) fires neither event; cancelling a running tool does not fire `PostToolUseFailure` | VERIFIED | same page |
| `claude --permission-prompts host\|none` exists (with `--print`); `--permission-mode` choices are `acceptEdits, auto, bypassPermissions, manual, dontAsk, plan` | VERIFIED | `claude --help` on 2.1.296 |
| Background sessions exist: `claude --bg`, `claude agents`, `claude attach`, `claude logs` | VERIFIED (help text only, not exercised) | `claude --help` on 2.1.296 |
| `/goal` slash command | UNVERIFIED | not visible in `--help`; check live docs before documenting |

## Open pull requests (all draft, all based on main `24080a6`, none merged by this programme)

| PR | Branch | Head | State |
|---|---|---|---|
| #43 | `feat/per-tool-call-telemetry` | `2754abb` | Phase 1a |
| #41 | `feat/jira-acli-connected-probe` | `dba92d8` | Phase 1b — see Jira conflict below |
| #42 | `feat/statusline-symbol-presets` | `2a07a3c` | Phase 1c |
| #31 | `docs/post-release-future-candidates` | `5c2dda1` | stale base `66a382f`; docs only; its diff against main looks large only because the base is old |

#41 and #43 both edit `CHANGELOG.md` under `## Unreleased` and conflict there only
(`git merge-tree`); #42 conflicts with neither. Resolve mechanically in whichever merges second.

Experimental branch `experimental/terminal-copilot-mvp` (`1231ce3`) holds the Terminal Copilot MVP:
code complete, statically reviewed, **never run on macOS**; no PR by design.

## Known tension: Jira (#41)

The owner earlier stated Jira is reached through Claude driving an already-authenticated browser
session, not through `acli`. The Phase 1 directive asks to verify "Jira authenticated CLI behavior
using actual observed output". `acli` is not installed here, so no output can be observed.
Rule applied: `cli_success_marker` stays unset and the Jira probe can never report CONNECTED from an
inferred marker. Owner decision needed on whether #41 should be closed.

## Milestones

| # | Milestone | Branch / PR | Status |
|---|---|---|---|
| 0 | Baseline audit and this record | `docs/milestone-progress` | COMPLETE when this PR is open |
| 1a | #43 telemetry | existing PR | not started |
| 1b | #41 Jira acli | existing PR | not started |
| 1c | #42 symbol presets | existing PR | not started |
| 2 | Claude mods research | TBD | not started |
| 3 | Evidence references and confidence labels | TBD | not started |
| 4 | Groundwork Copilot | TBD | not started |
| 5 | Hands-Free SRE proof of concept | TBD | not started |
| 6 | Autoship | TBD | not started |
| 7 | SmartMemory | TBD | not started |
| 8 | Final security and release audit | TBD | not started |

## Acceptance criteria — Phase 1 (to be confirmed against the PR code in each milestone)

- #43: one count per executed call, keyed by `tool_use_id`; success from `PostToolUse`, failure from
  `PostToolUseFailure`; denied, rejected and cancelled calls are documented as not observable, not
  silently counted; interrupts kept separate from errors; data stays in a local file with owner-only
  permissions; no `tool_input` or `tool_response` content persisted.
- #41: the Jira probe never reports CONNECTED from a guessed output; any marker must come from real
  `acli` output or stay unset.
- #42: default rendering byte-identical to today; unknown `symbol_set` or `separator` falls back to
  the default; existing config files without the new keys behave unchanged; `ascii` output contains
  no non-ASCII characters.
- All three: full suite green, `openspec validate --all --strict` no worse than baseline, one fresh
  independent review reporting zero MUST FIX.

## Resume instructions

1. `git fetch`; compare `main` and the PR heads above with this table.
2. Re-run `python3 -m pytest tests -q`; expect 110 passed on main.
3. Continue at the first milestone not marked COMPLETE.
