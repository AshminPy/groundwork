## Context

Existing pieces this builds on, verified in the repository:
- `hooks/require_material_review.py`: the Stop gate. Its `is_review_call()` and `parse_review_result()` are reused, not copied.
- `hooks/groundwork_session_snapshot.py`: SessionStart facts. Its per-repository key scheme (`<slug>-<sha256(root)[:10]>`, used for the investigation file) is reused for the task ledger.
- `hooks/groundwork_shared.py`: shared helpers.
- `scripts/groundwork_cli.py`: the pass-through CLI pattern.
- `scripts/merge_settings.py`: the idempotent hook registration.

Claude Code hook contract (code.claude.com/docs/en/hooks, read 2026-10-12):
- `UserPromptSubmit` receives `prompt`, and also fires for scheduled tasks, background-subagent reports and other sessions' messages.
- `UserPromptExpansion` "runs when a user-typed command expands into a prompt". A `PreToolUse` hook on `Skill` fires instead when Claude calls the tool.
- Settings hooks also run inside subagents.
- `PostToolUseFailure` carries `error` whose first line is `Exit code N` for Bash.
- Agent `tool_response` carries the subagent's `content`.
- A timed-out hook does not block.

Runtime-verified in this container (Claude Code 2.1.296): typing `/gw-probe COR-1 abc123` in `claude -p` fired `UserPromptExpansion` with `command_name: gw-probe` and `command_args: COR-1 abc123`.

## Goals / Non-Goals

Goals: the M1 lifecycle. Intake, then plan, then owner approval, then gated execution, then evidence, then completion, then fresh-session recovery. Every gate is a deterministic check in a hook or the ledger CLI, never a reminder.

Non-goals:
- A sandbox against a deliberately adversarial process running as the same user. Same-user code can write the ledger file.
- Jira API access.
- New UI.

## Decisions

### D1. The ledger lives outside the repository, keyed per repository

DECISION: store one JSON file per task at `$CLAUDE_CONFIG_DIR/groundwork/tasks/<slug>-<sha256(repo root)[:10]>/<KEY>.json`. The plan stays in the repository as the OpenSpec change.

EVIDENCE: `investigation_path()` in `hooks/groundwork_session_snapshot.py` uses the same key. OpenSpec changes are repository files (`openspec/changes/<name>/`).

WHY: approvals must not be shippable. A cloned repository containing a forged `approved` record would bypass the gate if state lived in the tree. Keying by repository root keeps projects apart. Separate `CLAUDE_CONFIG_DIR`s keep work and personal apart.

TRADEOFFS: state does not travel with a fresh clone on another machine. The plan does, but approval and evidence must be redone. Two worktrees of one repository get separate ledgers.

VALIDATION METHOD: tests prove two repositories with the same key stay separate, and that a ledger file planted in the repository is ignored.

UNCERTAINTY: none material.

### D2. Owner approval only through `UserPromptExpansion` of a typed `/gw-approve`

DECISION: approval and cancellation are user commands (`commands/gw-approve.md`, `commands/gw-cancel.md`, `disable-model-invocation: true`). The ledger records approval only from the `UserPromptExpansion` event.

EVIDENCE: the hooks documentation quoted under Context, plus the runtime probe.

WHY: `UserPromptSubmit` is also fed by scheduled tasks, background subagents and cross-session messages, so a phrase in a prompt is not proof a person typed it. A CLI `approve` command can be run by Claude through Bash.

Defence in depth, because the event's behaviour for scheduled or cross-session text that starts with `/gw-approve` was not tested:
- `PreToolUse` denies any `Skill` call for these commands.
- It denies tool input containing `gw-approve` or `gw-cancel` in any command that is not read-only, scheduled prompts, messages to other sessions and MCP calls.
- File edits, subagent prompts and read-only commands such as `grep` may contain the text; they cannot deliver it as typed input.
- A nested `claude` session is a sensitive command. It needs an Approved Operation after approval, and is not read-only before it.

TRADEOFFS: the owner must be in a Claude Code session to approve. There is no terminal or CLI approval.

VALIDATION METHOD:
- unit: approval via `UserPromptSubmit` text is not recorded.
- unit: a Skill call is denied.
- live: `/gw-approve` in a real session records the approval.

UNCERTAINTY: RUNTIME VALIDATION REQUIRED for whether a cross-session message or scheduled prompt beginning with `/gw-approve` expands as a command. The `PreToolUse` text check blocks Claude from creating either.

### D3. Approval is bound to a digest of the plan

DECISION: the approval code is `sha256` over `proposal.md`, `design.md` and `specs/**/*.md`, truncated to 10 hex characters. Execution is allowed only while the current digest equals the approved one. `tasks.md` is not in the digest. The number of tasks at approval is recorded, and completion refuses if `tasks.md` has fewer.

WHY:
- Scope, Verification and Approved Operations live in the proposal or design, so editing them after approval voids the approval instead of silently widening scope.
- `tasks.md` is the progress checklist. In the live acceptance run, the model ticked and annotated it during execution. With `tasks.md` in the digest (checkboxes normalised), the annotations voided the approval, and in-scope work was reported as outside the scope.

TRADEOFFS:
- Any wording fix to the proposal, design or specs needs re-approval.
- Task wording can change after approval without re-approval. This grants no authority: the gate reads Scope and Approved Operations from the proposal or design only. The task count is recorded when approval is requested; approval is refused, and completion is refused, while `tasks.md` has fewer tasks.

VALIDATION METHOD: unit tests that ticking and annotating `tasks.md` keeps the approval valid, that removing a task is refused at completion, and that a scope edit voids the approval.

### D4. Two layers of execution gating: `PreToolUse` per call, plus a git audit after every call

DECISION:
- `PreToolUse` gates edit tools by path, Bash with a read-only allowlist before approval and a sensitive-command list after it, and MCP tools by verb.
- After approval, a sensitive command runs only when its words equal an Approved Operation exactly, and not in the same command as `export`, an assignment or `source`. In the live acceptance run, a prefix match let the model add flags the owner had not seen; a different `--project` would have passed the same way.
- After every Bash, Agent or MCP call, `PostToolUse`/`PostToolUseFailure` diff the working tree against the base commit recorded at intake. Paths that were dirty at intake are excluded. The audit reports out-of-scope paths to Claude.
- `complete` re-runs the audit and refuses on any violation.

WHY: shell parsing cannot see every write (`python -c`, generated scripts, subagents' shells). The git audit is path-agnostic and catches any in-repository change however it was made. The allowlist before approval is fail-closed: an unknown command is denied, not trusted.

TRADEOFFS: before approval, some harmless commands are denied, such as `sed`, `awk` and running tests. Claude has the Read and Grep tools and can ask. Side effects outside the repository are only covered by the sensitive-command list. The shell parser follows bash for quoting, comments, line continuations, here-strings, here-documents, arithmetic, compound-command keywords and operator runs, and denies what it cannot parse. A script written and run in the same command is denied, because the gate reads a script only when it runs; programs such as Python are not inspected. The working directory is not part of an Approved Operation's match.

VALIDATION METHOD: tests for each class, plus a live test where an out-of-scope edit is denied.

### D5. Evidence is matched to the current working-tree fingerprint, not to timestamps

DECISION: each verification and review record stores a fingerprint of the working tree, excluding the task's own plan directory. The fingerprint is a hash of `git diff --binary <base>` plus untracked paths, sizes and mtimes. Completion requires, on the current fingerprint:
- a successful run of every declared verification command, after the last approved sensitive operation;
- a review reporting zero MUST FIX findings.

WHY: it is exact. Any change after verification makes the evidence stale, whichever tool made it, and editing `tasks.md` does not. A review only counts when it came from a foreground subagent with a parsed `REVIEW RESULT` block. This is stricter than the Stop gate's presence-only fallback, because completion is the claim that matters.

TRADEOFFS:
- A large diff costs one bounded `git diff` per verification or review event. Above 20 MB the fingerprint falls back to `--stat` plus mtimes.
- Background reviews are not captured.

### D6. Deterministic intake, with the model writing the plan

DECISION: the hook decides only facts it can decide from text:
- whether the prompt is a task, and its key;
- the tier floor (MATERIAL when cloud, infrastructure, data, security or production signals or deployment verbs appear);
- risk categories;
- a fixed checklist per category.

The model writes the analysis in the plan (prerequisites, missing information, risks, estimate with uncertainty). The plan gate checks that those sections exist and are non-empty.

WHY: deterministic checks first. Effort numbers and domain prerequisites need reasoning, and the gate makes them mandatory instead of inventing them.

TRADEOFFS: keyword classification has false positives ("for instance") and misses. The owner can `/gw-cancel` a spurious task. An open STANDARD task whose key returns with MATERIAL signals and an action verb is escalated. MATERIAL work under no key at all is not caught; Claude can register it with `groundwork task intake`.

## Architecture-quality §2 answers

- **Likely to change:** keyword lists, the read-only and sensitive command lists, and the required plan sections. They are module-level constants, and tests pin behaviour, not the lists.
- **Another project, environment or provider:** projects are separated by repository key, and environments by `CLAUDE_CONFIG_DIR`. A new provider's CLI is one entry in the sensitive and read-only verb tables.
- **Automated steps:** intake, change creation, plan validation, digest, evidence capture and scope audit. Approval is deliberately manual.
- **Dependency unavailable:**
  - Without the OpenSpec CLI, intake records the task and tells Claude to create the change, and `request-approval` refuses.
  - Without git, there is no ledger and no gate, because there is no repository identity. That is fail-open, the same as the existing hooks.
  - A gate error while a MATERIAL task is active denies (fail closed).
- **Observability:** `groundwork task list|show` and the SessionStart snapshot lines show it, and every deny reason names the task, its state and the next action. The ledger's `history` holds each state change.
- **Testing:**
  - unit: `tests/test_task_lifecycle.py` drives the hook with real Claude Code payload shapes against temporary git repositories and `CLAUDE_CONFIG_DIR`s, including a full deterministic lifecycle.
  - live: real `claude -p` sessions in a sandbox config directory against a fixture repository.
- **Deploy and rollback:** the new files are installed by `install.sh` and registered by `merge_settings.py`, and `uninstall.sh`/`unmerge_settings.py` remove them. Ledger data is kept on uninstall, like telemetry. `GROUNDWORK_TASK_GATE=off` in settings `env` is the owner's kill switch. Claude cannot change hook environment, and settings edits are denied during a gated task.
- **Security boundary:** approval comes only from a person typing a command. The ledger lives outside the repository. Owner commands and ledger files cannot be written by Claude's tools. This is not a same-user sandbox, as stated under Non-Goals.
- **Scaling and cost:** one Python process per tool call (about 40 ms). With no active task, the hook only stats the ledger directory. There are no network or model calls.
