# Task lifecycle gate

Groundwork records engineering tasks and enforces their lifecycle with hooks, not instructions. OpenSpec change: [`openspec/changes/add-task-lifecycle-gate/`](../openspec/changes/add-task-lifecycle-gate/).

```
prompt ──► intake ──► planning ──► awaiting-approval ──► approved ──► complete
           (hook)     plan in       request-approval       owner types   groundwork task complete
                      openspec/     checks the plan        /gw-approve   checks the evidence
```

## What happens

| Step | Who | What Groundwork checks |
|---|---|---|
| Intake | the prompt hook | A ticket key (`COR-123`) or an action verb that is not a question becomes a task. MATERIAL when cloud, infrastructure, data, security, production or deployment words appear. STANDARD otherwise: tracked, no approval gate. MATERIAL tasks get an OpenSpec change (`openspec new change <key>-<slug>`). |
| Planning | Claude | Only read-only commands, and edits inside `openspec/changes/<change>/`. |
| Request approval | Claude runs `groundwork task request-approval <KEY>` | `openspec validate --strict` passes. `tasks.md` has checkboxes. The plan has `## Prerequisites`, `## Risks`, `## Missing Information`, `## Estimate` (a number plus confidence or uncertainty), `## Scope` (paths in backticks), `## Verification` (commands in backticks). It may have `## Approved Operations` (exact sensitive commands). Each Verification and Approved Operations entry must be one exact, simple command: no placeholders, `&&`, pipes or redirection. On success it prints an approval code: a digest of the plan. |
| Approval | **the owner types** `/gw-approve <KEY> <code>` | The code must match the current plan. Only a typed slash command records it (Claude Code's `UserPromptExpansion` event). Text such as "approve COR-123" in a message does not. Claude cannot run, send or schedule the command. |
| Execution | Claude | Edits only inside Scope. Sensitive commands only when they equal an Approved Operation exactly, with no extra arguments and no `export`, `eval`, `source` or function definition in the same command: cloud, cluster, Terraform and Helm mutations, recursive deletes, ssh, mutating HTTP, database clients. Editing the proposal, design or specs voids the approval; ticking or annotating `tasks.md` does not, and approved tasks cannot be removed. After every Bash, agent or MCP call, a git audit reports any change outside Scope. |
| Completion | Claude runs `groundwork task complete <KEY>` | The plan is unchanged since approval and every task is checked. No out-of-scope change remains. Each Verification command passed on the current working tree, after the last approved operation. It must have run exactly as declared: no extra arguments, not piped, and followed only by `&&`. A foreground review subagent reported `Must-fix: 0` on the current working tree. |

`/gw-cancel <KEY>` (owner only) stops a task gating the repository.

Which ticket a prompt is for:
- The first key not yet in the ledger, so `COR-124: follow-up to COR-123 …` registers COR-124.
- Otherwise the first open key. An open STANDARD task asked to do MATERIAL work is escalated and gated.
- Otherwise a closed key, which opens a fresh task only when the prompt asks for work (an action verb). The old record is kept as `<KEY>.closed-<time>.json`.

While a task waits on the owner, a reply without a ticket key is treated as input to that task, and Claude is shown that task's state.

Any tool that runs a shell command (Bash, Monitor) is checked the same way. PowerShell is denied while a task is gated. A nested `claude` session counts as a sensitive command. The scope audit ignores generated caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`).

## Commands

```bash
groundwork task list            # open tasks in this repository (--all: every repository)
groundwork task show COR-123    # one task: plan, approval, scope, evidence, history, next action
groundwork task request-approval COR-123
groundwork task complete COR-123
groundwork task block COR-123 "waiting for the network team"   # or --clear
```

A new session sees the open tasks, their state and their next action in the session snapshot.

## Where state lives

- The plan is the OpenSpec change in the repository.
- The ledger is `~/.claude/groundwork/tasks/<repo>-<hash>/<KEY>.json`, outside the repository, so a cloned repository cannot ship an approval.
- One ledger per repository. A separate `CLAUDE_CONFIG_DIR` (for example work and personal) has its own ledgers.
- Uninstall keeps the ledger.

## Switching it off

Set `"GROUNDWORK_TASK_GATE": "off"` in the `env` of `~/.claude/settings.json`. Claude cannot change a hook's environment, and settings edits are denied while a task is gated.

## Limits

- **Not a sandbox.** Code that runs with your user's permissions (for example a Python script Claude writes inside Scope) can write the ledger or call a cloud API that the shell check cannot see. The gate controls Claude's tool calls and audits the repository. It does not contain arbitrary programs.
- **Programs are not inspected.** Sensitive commands inside shell scripts run directly are found. Sensitive calls inside Python, Node and other programs are not.
- **Side effects outside the repository** are covered only by the sensitive-command list. The git audit covers changes inside the repository however they were made.
- **Intake is keyword-based.** It can miss a MATERIAL request or flag a harmless one. The owner can `/gw-cancel` a spurious task.
- **Read-only allowlist.** Before approval some harmless commands are denied (`sed`, `awk`, running tests, command substitution). Claude can use Read and Grep instead.
- **Reviews must run in the foreground** and end with a `REVIEW RESULT` block. Background reviews are not captured.
- **Not runtime-validated:** whether another session's message or a scheduled prompt that begins with `/gw-approve` would expand as a command. Claude is denied creating either.
