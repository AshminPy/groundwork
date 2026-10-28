## Context

Evidence:
- `hooks/groundwork_tasks.py:48` (`MAX_HISTORY = 60`) contradicted the accuracy-signals design's "uncapped history".
- PR #75's review history: 1, 1, 4 and 0 must-fix findings over four rounds.
- A container restart on 2026-10-28 deleted an unpushed worktree, and pytest and `openspec` were missing afterwards.

## Decisions

- **Rule text, not new hooks.** Each rule is one sentence in the step it governs, because the rules file is paid for in every
  session. A hook cannot judge whether a design claim was checked, so these stay judgment rules.
- **The MUST FIX bar goes into the reviewer's brief.** That is where it changes the reviewer's output.
- **Pinned OpenSpec (1.15.0).** `install.sh` installs `@latest` for users; the repo hook pins the version its changes were
  validated with, because a newer release added a strict-mode warning that failed an existing change's validation.
- **Cloud-only hook.** It exits at once unless `CLAUDE_CODE_REMOTE=true`, so local contributors' machines are untouched.

## Risks

- Pinning means a later OpenSpec fix is not picked up until the pin is raised.
- The npm install path was not exercised from an empty npm prefix in validation (RUNTIME VALIDATION REQUIRED in a fresh
  cloud container).
