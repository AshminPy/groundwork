## Why

Groundwork's workflow rules say MATERIAL work needs an OpenSpec plan, verification and an independent review, and that sensitive actions need the owner's authorization. Before this change nothing recorded a task when it arrived. "Complete" was not tied to observed evidence. A fresh session could not see which task was in flight. The owner asked for task tracking that survives sessions and is backed by evidence (M1 of the Groundwork engineering-workflow programme).

The first build of M1 added approval codes, a plan-section gate and a file-scope gate. In use, these blocked ordinary development and fought native OpenSpec's flexibility. The owner set the direction: native OpenSpec is the primary workflow. Groundwork extends it with tracking, evidence and authorization for sensitive actions, and does not replace it.

## What Changes

- **Automatic, lightweight intake.** A `UserPromptSubmit` hook classifies each prompt without a model call. It records a task when the prompt has a Jira-style key or is MATERIAL engineering work. It records the tier, risk categories and a short intake checklist. For a MATERIAL task it creates the native OpenSpec change (`openspec new change <key>-<slug>`) and tells Claude to plan and implement it the native way (`/opsx:propose`, `/opsx:apply`).
- **Native OpenSpec is the source of truth.** Groundwork reads the change's artifacts as they are, every time: progress from `tasks.md` checkboxes, and the verification commands from a `## Verification` section. Phase (planning, implementing, verifying, archived) comes from those artifacts. The plan can be revised at any time. Native explore, propose, apply, sync and archive are unchanged.
- **No approval codes and no scope gate.** Ordinary edits, commands and plan changes run without prompts.
- **Sensitive actions ask the owner.** A `PreToolUse` hook returns Claude Code's native `ask` decision, which shows the user's permission prompt. It applies in every repository, with or without a task. It covers:
  - cloud, cluster, Terraform and Helm mutations;
  - database clients;
  - remote execution;
  - data-sending HTTP requests;
  - recursive deletes of, or outside, the working directory;
  - destructive Git (forced or deleting push, `reset --hard`, `clean -f`, branch force-delete, stash drop, discarding changes);
  - credential access, and elevated privileges;
  - commands that cannot be checked;
  - edits to Claude Code settings or Groundwork's hooks.
  File tools cannot write the task ledger.
- **Evidence.** `PostToolUse` and `PostToolUseFailure` record:
  - runs of the declared verification commands, with their outcome and a fingerprint of the code, excluding `openspec/`;
  - foreground review results (`REVIEW RESULT`);
  - sensitive operations that ran.
- **Evidence-based completion.**
  - A MATERIAL task completes when every task is checked, every declared verification passed on the current code after the last sensitive operation, and the latest review reports zero MUST FIX.
  - A STANDARD task completes on request.
  - Archiving the change natively (`openspec archive`, or the `/opsx:archive` move) completes the task when the evidence is in place.
- **Continuity.** The SessionStart snapshot lists open tasks as task, phase, progress, evidence and next action. `groundwork task list|show` shows the same. The ledger lives under `$CLAUDE_CONFIG_DIR/groundwork/tasks/`, never in the repository, so projects and config directories (for example work and personal) never mix.

Not in this change: Jira fetching (intake only recognises the key), MCP catalog (M3), completion-claim text checks at Stop (M2), statusLine task display (M3).

## Capabilities

### New Capabilities
- `task-lifecycle`: task intake, native OpenSpec planning, authorization for sensitive actions, evidence capture, evidence-based completion and task continuity.

## Impact

New:
- `hooks/groundwork_tasks.py`: ledger, intake classifier, plan reader, evidence, completion, CLI.
- `hooks/groundwork_task_gate.py`: the hook entry for four events.
- `tests/test_task_lifecycle.py` and `docs/TASK-LIFECYCLE.md`.

Changed:
- `scripts/merge_settings.py` and `unmerge_settings.py`: four hook registrations; an older install's `UserPromptExpansion` entry is removed.
- `install.sh`, `uninstall.sh` and `setup.sh`: copy, remove and verify the files.
- `scripts/groundwork_cli.py`: the `groundwork task` pass-through.
- `hooks/groundwork_session_snapshot.py`: open-task lines.
- `rules/engineering-workflow.md`, `CHANGELOG.md` and `docs/ARCHITECTURE.md`.

No new dependency: Python standard library only, plus the OpenSpec CLI that is already installed. No network access.
