## Context

Evidence:
- `hooks/groundwork_tasks.py:48` (`MAX_HISTORY = 60`) contradicted the accuracy-signals plan's first draft, which said the ledger history was uncapped; it was corrected during implementation, before that plan's rebuilt commit (`openspec/changes/add-accuracy-signals/egm-review.md`, on PR #75's branch).
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

- Pushing per green step could commit the step that completes `tasks.md` and so skip the review Stop hook, which
  checks only uncommitted changes (`hooks/require_material_review.py`, via `dirty_change_names` in
  `hooks/groundwork_shared.py:28`); the rule keeps that step uncommitted until a review reports `Must-fix: 0`.
- **Owner review (2026-10-29):** no implicit installs at session start. Tools come from the explicit, pinned `scripts/cloud-setup.sh` (pytest 9.2.0, OpenSpec 1.13.2, user-local; set as the cloud environment's Setup script or run by hand). The hook only sets `PYTHONDONTWRITEBYTECODE` and names what is missing; it ran in 0.15 s. The setup script installed OpenSpec from an empty home in 6.6 s and was a no-op on a second run; its pip path was not exercised (pytest was already present), and `pip install --user` can be refused on a PEP 668 system Python.
- **Push rule:** per-step pushes stay on the task's own feature branch; ready-for-review, merge, release and approval still need the independent review and the owner's authorization.

- Pinning means a later OpenSpec fix is not picked up until the pin is raised.
- The npm install path was not exercised from an empty npm prefix in validation (RUNTIME VALIDATION REQUIRED in a fresh
  cloud container).
