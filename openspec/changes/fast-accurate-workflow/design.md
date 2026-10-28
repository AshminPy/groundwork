## Context

Evidence:
- `hooks/groundwork_tasks.py:48` (`MAX_HISTORY = 60`) contradicted the accuracy-signals plan's first draft, which said the ledger history was uncapped; it was corrected before that plan was committed (`openspec/changes/add-accuracy-signals/egm-review.md`, on PR #75's branch).
- PR #75's description lists its review rounds: 1, 1, 4 and 0 must-fix findings.
- A container restart on 2026-10-28 deleted an unpushed worktree, and pytest and `openspec` were missing afterwards.

## Decisions

- **Rule text, not new hooks.** Each rule is one sentence in the step it governs, because the rules file is paid for in every
  session. A hook cannot judge whether a design claim was checked, so these stay judgment rules.
- **The MUST FIX bar goes into the reviewer's brief.** That is where it changes the reviewer's output.
- **Pinned OpenSpec (1.13.2), the same as `setup.sh:85` `LAST_VERIFIED_OPENSPEC`.** Checked on 2026-10-28: 1.13.2 passes
  `openspec validate --changes --strict` on all 8 changes; 1.15.0, npm's `latest` that day, fails 6 of them on its new
  requirement-length warning (UNVERIFIED for releases between them other than 1.14.3, which the review found also fails).
  `install.sh` still installs `@latest` for users; aligning it is a separate decision.
- **Cloud-only, never fatal.** It exits at once unless `CLAUDE_CODE_REMOTE=true`, so local contributors' machines are
  untouched; a failed install prints a warning and the hook still exits 0.

## Risks

- Pinning means a later OpenSpec fix is not picked up until the pin is raised.
- The npm install path was not exercised from an empty npm prefix in validation (RUNTIME VALIDATION REQUIRED in a fresh
  cloud container).
