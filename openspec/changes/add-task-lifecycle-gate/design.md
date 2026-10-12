## Context

Existing pieces this builds on, verified in the repository:
- `hooks/require_material_review.py`: the Stop gate. Its `is_review_call()` and `parse_review_result()` are reused, not copied.
- `hooks/groundwork_session_snapshot.py`: SessionStart facts. Its per-repository key scheme (`<slug>-<sha256(root)[:10]>`) is reused for the task ledger.
- `scripts/groundwork_cli.py`: the pass-through CLI pattern.
- `scripts/merge_settings.py`: the idempotent hook registration.
- `.claude/commands/opsx/*.md` and the `openspec-*` skills: the native OpenSpec workflow (explore, propose, apply, sync, archive). `/opsx:archive` moves the change with `mv <change> <changes>/archive/<date>-<name>`. `openspec archive <name>` does the same and syncs specs (OpenSpec CLI 1.13.2, run in this container).

Claude Code hook contract (code.claude.com/docs/en/hooks, read 2026-10-12):
- A `PreToolUse` `permissionDecision` of `ask` shows the user's permission prompt. It also prompts in auto mode. In a non-interactive `-p` run with no one to answer, the call is denied and Claude reads the reason.
- `deny` blocks the call. Across hooks, the precedence is deny > defer > ask > allow.
- `UserPromptSubmit` receives `prompt`. `PostToolUseFailure` carries `error`. An Agent `tool_response` carries the subagent's `content`.

History: the first build of this change gated ordinary work behind owner approval codes, required plan sections, and checked edits against an approved file scope. Live use showed it blocked normal development and duplicated what native OpenSpec already does. The owner redirected M1: native OpenSpec is the primary workflow, and Groundwork extends it. This design replaces the first one.

## Goals / Non-Goals

Goals:
- Tasks recorded automatically, and kept across sessions.
- MATERIAL tasks planned with native OpenSpec, and revisable at any time.
- Ordinary work without approval prompts; sensitive actions authorized by the owner.
- Completion backed by evidence; native sync and archive keep working.

Non-goals:
- A spec engine or plan format of Groundwork's own.
- A sandbox against a deliberately adversarial process running as the same user.
- Jira API access.

## Decisions

### D1. Native OpenSpec artifacts are the plan; Groundwork only reads them

DECISION: Groundwork reads the change's `tasks.md` checkboxes and one `## Verification` section, in `design.md`, `proposal.md` or `tasks.md`. The section lists the exact commands that prove the change, in backticks. Groundwork reads them fresh on every status, evidence and completion check. Phase comes from the artifacts:
- planning: no `tasks.md` yet, as in native OpenSpec where apply requires tasks;
- implementing: unchecked tasks remain;
- verifying: every task is checked;
- archived: the change sits under `openspec/changes/archive/`.

EVIDENCE: `openspec status --change X --json` reports `applyRequires: ["tasks"]` (CLI 1.13.2). The `/opsx:archive` command moves the change into `archive/`.

WHY: one source of truth. The user revises the plan naturally, and Groundwork never disagrees with OpenSpec about it.

TRADEOFFS: a MATERIAL plan must add the `## Verification` section for completion. That is the one convention Groundwork adds, and intake tells Claude about it.

### D2. Sensitive actions use Claude Code's own permission prompt

DECISION: the `PreToolUse` hook returns `ask` for sensitive actions, in every repository and directory, task or no task. It never asks for anything else. No approval codes, plan digests or file-scope checks. File tools writing the task ledger get `deny`.

EVIDENCE: hook contract above. The shell parser from the first build (quoting, here-documents, substitutions, nested shells, scripts, `cd` tracking) is reused unchanged. Its regression tests are kept.

WHY: the native prompt is the authorization channel the user already knows. It covers "explicit authorization for production, destructive, credential-related and security-sensitive actions" without a second approval system. Ordinary development is never interrupted.

TRADEOFFS:
- In a headless `-p` run, sensitive actions are denied. That is the safe default; run them interactively.
- `ask` under `bypassPermissions` is not verified.
- MCP tools are left to Claude Code's own permission rules. Groundwork does not classify them.

### D3. Evidence is tied to the code, not to the plan

DECISION: each verification or review record stores a fingerprint: a hash of `git diff --binary <base commit>`, plus untracked paths, sizes and mtimes. `openspec/` and generated caches are excluded. For each declared command, the latest run on the current fingerprint, after the last sensitive operation, decides passed or failed. Otherwise the command is stale or not run.

WHY: any code change after verification makes it stale, whichever tool made it. Revising the plan, syncing specs or archiving the change never does. That is what lets the user revise plans freely.

TRADEOFFS:
- One bounded `git diff` per evidence event. Above 20 MB it falls back to `--stat` plus mtimes.
- Background runs and background reviews are not evidence.

### D4. Completion

DECISION:
- MATERIAL: `groundwork task complete <KEY>` succeeds when every task in `tasks.md` is checked, at least one valid verification is declared, every declared verification passed on the current code, and the latest parsed review reports `Must-fix: 0`.
- STANDARD: it completes on request.
- After a successful native archive (`openspec archive`, or the `/opsx:archive` move), the hook tries completion. When evidence is missing, the task stays open and Claude is told what is missing.

WHY: completion is the claim that matters, so it rests on evidence. Archive is the native "done" step, so it completes the task when it can.

### D5. The ledger lives outside the repository, keyed per repository

DECISION: one JSON file per task at `$CLAUDE_CONFIG_DIR/groundwork/tasks/<slug>-<sha256(repo root)[:10]>/<KEY>.json`. The plan stays in the repository.

WHY: a cloned repository cannot ship forged evidence. Keying by root keeps projects apart, and separate config directories keep work and personal apart.

TRADEOFFS: evidence does not travel with a clone; the plan does.

### D6. Deterministic intake

DECISION: the hook decides only what it can decide from text: whether the prompt is a task, its key, the tier, the risk categories and a fixed checklist per category. Untracked STANDARD work (no key) is not recorded. A keyless prompt while a MATERIAL task is open is treated as more of that task.

TRADEOFFS: keyword classification has false positives and misses. `groundwork task cancel` drops a spurious task, and `groundwork task intake` records a missed one.

## Architecture-quality §2 answers

- **Likely to change:** the keyword lists and the sensitive-command tables. They are module constants, and the tests pin behaviour.
- **Another project, environment or provider:** projects are separated by repository key, and environments by `CLAUDE_CONFIG_DIR`. A new provider CLI is one entry in the sensitive-command table.
- **Automated:** intake, change creation, evidence capture, phase, and completion on archive.
- **Dependency unavailable:**
  - Without the OpenSpec CLI, intake records the task and tells Claude to create the change.
  - Without git there is no ledger, because there is no repository identity, but sensitive actions still ask.
  - A hook error on `PreToolUse` asks; on other events it is silent.
- **Observability:** the snapshot lines and `groundwork task list|show` show task, phase, progress, evidence and next action. The ledger's `history` holds each event.
- **Testing:**
  - unit: `tests/test_task_lifecycle.py` drives the hook with real payload shapes against temporary git repositories and config directories.
  - live: real `claude -p` sessions in a sandbox config directory against a fixture repository.
- **Deploy and rollback:** `install.sh` and `merge_settings.py` install and register the hook; `uninstall.sh` and `unmerge_settings.py` remove it. Ledger data is kept on uninstall. `GROUNDWORK_TASK_GATE=off` in settings `env` is the kill switch.
- **Security boundary:**
  - sensitive actions need the user's authorization;
  - the ledger lives outside the repository and file tools cannot write it;
  - settings and hook edits ask.
  This is not a same-user sandbox.
- **Scaling and cost:** one Python process per tool call. There are no network or model calls.
