# Task tracking

Groundwork records engineering tasks, keeps them across sessions and ties completion to evidence. Native OpenSpec stays the workflow: explore, propose, apply, sync and archive work as they always do. OpenSpec change: [`openspec/changes/add-task-lifecycle-gate/`](../openspec/changes/add-task-lifecycle-gate/).

```
prompt ──► intake ──► planning ──► implementing ──► verifying ──► complete ──► archived
           (hook)     /opsx:propose  /opsx:apply      checks pass   groundwork task complete,
                                                      + review      or the native archive
```

## Pilot scope

This is a controlled pilot.
- **Permissions.** Run it with Claude Code's normal permission modes: default, or `acceptEdits`. Do not use `bypassPermissions` or `--dangerously-skip-permissions`. The install sets neither, and Groundwork's authorization prompt is not verified under them.
- **No unattended production or destructive operations.** Production, cloud, cluster, destructive and credential-related actions need a person to answer the permission prompt in an interactive session. Unattended runs — `claude -p`, scheduled routines, background agents — must not perform them. In a headless run nobody can answer the prompt, so such an action is denied.
- **Guards still apply.** The protected-branch guard (`block_protected_push.py`) still blocks direct pushes to protected branches. Merges, tags and releases still need the owner's approval.
- **Not a sandbox.** Groundwork's checks confirm intent. They do not contain programs (see Limits).

## What happens

| Step | Who | What Groundwork does |
|---|---|---|
| Intake | the prompt hook | A ticket key (`COR-123`) or MATERIAL engineering work becomes a task. Questions, slash commands and keyless STANDARD work do not. MATERIAL when cloud, infrastructure, data, security, production or deployment words appear. MATERIAL tasks get a native OpenSpec change (`openspec new change <key>-<slug>`). Claude is told to plan and implement it the native way. |
| Plan | Claude, with the owner | The native OpenSpec artifacts are the plan. Add an un-numbered `## Verification` section (in `design.md`, `proposal.md` or `tasks.md`) with one line per command, each starting with the command in backticks (`` - `pytest -q` — unit tests ``). Revise any artifact at any time. Groundwork reads them fresh on every check. |
| Implement | Claude | Ordinary edits, builds, tests, commits and pushes run without prompts. Sensitive actions show Claude Code's permission prompt (below). |
| Evidence | the hook | Records each run of a declared verification command (passed or failed, on which version of the code), each foreground review's `REVIEW RESULT`, and each sensitive operation that ran. |
| Complete | Claude runs `groundwork task complete <KEY>`, or archives natively | MATERIAL: every task in `tasks.md` is checked, each declared verification passed on the current code after the last sensitive operation, and the latest review reports `Must-fix: 0`. STANDARD: on request. A native archive (`openspec archive`, `/opsx:archive`) completes the task when this evidence is in place. Otherwise it reports what is missing. |

Phase comes from the native artifacts: **planning** (no `tasks.md` yet), **implementing** (unchecked tasks), **verifying** (all checked), **archived** (moved to `openspec/changes/archive/`).

Evidence follows the content of the code, not the plan:
- Editing the proposal, design, specs or tasks, syncing specs, archiving, staging and committing never make a passed verification stale.
- Changing a file does.
- The latest run on the current code decides. In one command, a verification counts only when it ran after any sensitive operation in that command.

## What asks for authorization

Groundwork returns Claude Code's native `ask` decision, which shows the usual permission prompt. It does this in every repository, task or no task, for:

- cloud, cluster, Terraform and Helm changes (`gcloud … create`, `kubectl apply`, `terraform apply`, …), database clients, `ssh`, and HTTP requests that send data;
- recursive deletes of, or outside, the working directory (`rm -rf .`, `rm -rf ~/x`, `rm -rf "$VAR"`, `cd /other && rm -rf data`). Deletes inside it and in temporary directories do not ask;
- destructive Git, also behind `git -C dir` or `-c k=v`: forced or deleting push, `reset --hard`, `clean -f`, `branch -D`, `stash drop`/`clear`, `checkout .`/`restore .`, `checkout -f`/`switch -f`, `filter-branch`, `update-ref -d`, `reflog expire`;
- credential access: `.env`, SSH keys, cloud credential files, `gh auth`, `aws configure`, `kubectl get secret`, `vault`, and similar;
- `sudo`, `doas`, `su` and `pkexec` (also behind `env`, `time`, `timeout`, `xargs`), commands that cannot be checked (piped into a shell, computed, PowerShell), and changes to Claude Code settings, Groundwork's hooks or the task ledger. Running the task CLI never asks, unless its output is redirected into one of those files.

Commands are checked inside wrappers, nested shells, scripts run directly, command substitutions and here-documents. File tools cannot write the task ledger. Pushes to protected branches are still blocked by `block_protected_push.py`.

## Commands

```bash
groundwork task list            # open tasks in this repository (--all: every repository)
groundwork task show COR-123    # one task: phase, progress, verification state, review, history
groundwork task complete COR-123
groundwork task cancel COR-123
groundwork task block COR-123 "waiting for the network team"   # or --clear
groundwork task intake "deploy the cache to production"        # record work the intake missed
```

A new session sees each open task as one line: `KEY [phase n/m] title · evidence: … · next: …`.

## Where state lives

- The plan is the OpenSpec change in the repository.
- The ledger is `~/.claude/groundwork/tasks/<repo>-<hash>/<KEY>.json`, outside the repository, so a cloned repository cannot ship evidence.
- There is one ledger per repository. A separate `CLAUDE_CONFIG_DIR` (for example work and personal) has its own ledgers.
- Uninstall keeps the ledger. Records from the earlier approval-code build are read as open tasks.

## Switching it off

Set `"GROUNDWORK_TASK_GATE": "off"` in the `env` of `~/.claude/settings.json`. Edits to settings ask first.

## Limits

- **Headless runs.** In a non-interactive `claude -p` run nobody can answer the prompt, so sensitive actions are denied, and Claude sees the reason. Run them interactively.
- **Not a sandbox.** Programs such as Python or Node are not inspected. A script Claude writes can call a cloud API that the shell check cannot see. MCP tools are left to Claude Code's own permission rules.
- **Intake is keyword-based.** It can miss MATERIAL work or flag harmless work. Use `groundwork task intake` or `groundwork task cancel`.
- **Shell checking is conservative.** What cannot be parsed asks. After a `cd`, a recursive delete is judged in every directory the command may be in, so `cd frontend && … && cd .. && rm -rf frontend/dist` asks. This includes `xargs … sh -c '…'`, `sh -c "$(…)"`, `eval "$(…)"` and a script written and run in the same command. A command name taken from a computed variable (`TF=$(command -v terraform); $TF apply`) is not resolved.
- **Parsed the way bash parses.** `[[` is a test only where bash reads a command name, a carriage return is part of a
  word (it never starts a comment), and credential directories count with or without a trailing slash (`~/.ssh`, all of
  `~/.aws` and `~/.config/gcloud`). A `cd` into the Claude config directory is followed through earlier `cd`s and
  assignments in the same command. After a `cd` the gate cannot compute (`cd "$(…)"`, `cd -`, a glob, or CDPATH
  set), a `cd` whose target names the config directory (`.claude`, also as a glob such as `.cl*`) counts as
  entering it; the computed directory itself counts as inside when the command names the config directory's full
  path or `~/.claude`. A relative path is resolved against every directory the command may be in (`cd ~ && rm
  .claude/hooks/x`, a session started in the config directory, `env -C`), and `sh -c` / `eval` strings are
  checked the same way. Not followed: a path built at run time other than through a `cd`, and deleting a
  directory above the config directory, which the delete checks cover (2026-10-12 security scan, F7, F8, F11,
  F12).
- **Reviews must run in the foreground** and end with a `REVIEW RESULT` block. Background reviews and background verification runs are not evidence.
- **Evidence fingerprint.** Untracked files larger than 5 MB count by size and modification time, not content, so staging such a file changes the fingerprint once. A change inside a git submodule's working tree is not seen until the submodule's commit changes.
- **Not verified:** how the `ask` decision behaves under `bypassPermissions` mode.
