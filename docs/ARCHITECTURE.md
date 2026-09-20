# Architecture

## Responsibility split

```
OpenSpec   → WHAT / WHY. Delta specs with acceptance criteria as scenarios,
             a design decision record, a task checklist. Per-repo, file-based
             (openspec/ directory + .claude/commands/opsx + .claude/skills/openspec-*).
             No plugin, no hooks — nothing to conflict with ECC by construction.

ECC        → HOW. 68 agents (planner, code-explorer, tdd-guide, code-reviewer,
             language-specific reviewers, security-reviewer, …), 286 skills,
             94 command shims. Installed once, user-scoped, as a single Claude
             Code plugin. Its own hooks: GateGuard (investigate-before-edit,
             destructive-Bash fact gate), block-no-verify, session persistence,
             pre-compact save, continuous learning.

Claude Code → the runtime. Subagents (Agent tool), experimental Agent Teams
             (named Agent calls when CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1),
             SendMessage, permissions, hooks, CLAUDE.md/rules loading, auto memory.

Groundwork → the governance layer. Three rule files loaded into every session's
             context; three hooks that enforce or inject what the rules can only
             ask for.
```

Groundwork does not replace any upstream project's job. It exists because, tested plainly, neither ECC nor OpenSpec on its own reliably makes an agent plan, design for change, test against the real runtime, review, and honestly report completion for a request that doesn't spell every step out. See [VALIDATION.md](VALIDATION.md) for the actual tests that established this.

## The three rules

| File | Owns |
|---|---|
| `rules/engineering-workflow.md` | Tier classification (TRIVIAL / STANDARD / MATERIAL); the execution order UNDERSTAND → DESIGN → IMPLEMENT → TEST → INDEPENDENT REVIEW → FIX MUST FIX → VERIFY → RUNTIME VALIDATE → REPORT; the state table for existing projects; the completion status block; the six owner-decision triggers (autonomy); §6 execution model (main session / subagents / Agent Teams); §7 continuation procedure |
| `rules/architecture-quality.md` | The governing design principle; quality dimensions as decision criteria; the pre-MATERIAL questions; the variation-point rule; no abstraction without a reason |
| `rules/evidence-policy.md` | Evidence priority; VERIFIED / UNVERIFIED / ASSUMPTION / INFERENCE / RUNTIME VALIDATION REQUIRED; the six-field DECISION record; source rules; the validation ladder; the completion-evidence table; the RCA rule; repository-wins-over-memory |

Every line in these files is paid in every session (Claude Code loads `~/.claude/rules/**/*.md` at launch), so they are written as short imperative lines, and anything a hook can enforce is a hook instead.

## Request lifecycle

```
                 USER GOAL  (a fresh session first receives the Groundwork snapshot:
                     │       branch · HEAD · dirty files · OpenSpec progress · discovered commands)
                     ▼
   rules/engineering-workflow.md classifies the request
                     │
        ┌────────────┼────────────┐
    TRIVIAL       STANDARD      MATERIAL
        │             │             │
    just do it   UNDERSTAND     UNDERSTAND — state table from repo evidence
        │         inline plan   openspec init (if needed)
        │         + dimensions  /opsx:propose — proposal, delta spec,
        │           that apply  design (answers architecture-quality.md §2),
        │         + tests       tasks; openspec validate
        │         + self-       DECISION records (evidence-policy.md §3)
        │           review      choose execution model (§6): main /
        │             │         subagents / Agent Team
        │             │             │
        │             │       /opsx:apply — implement, tests from the
        │             │       project's own commands (validation ladder)
        │             │             │
        │             │       independent fresh-context review —
        │             │       ECC reviewer, subagent, or reviewer
        │             │       teammate; MUST FIX vs NICE TO HAVE;
        │             │       ENFORCED by hooks/require_material_review.py
        │             └────────────┤
        │                          ▼
        │              verify → runtime-validate when runtime matters
        │              → deploy / live-validate if in scope
        └────────────────┬─────────┘
                          ▼
              COMPLETION STATUS block
   Code / Tests / Reviewed / Merged / Deployed / Live validated
      → COMPLETE / PARTIAL / BLOCKED / PLANNED / FAILED
```

## What is actually enforced versus advisory

Being honest about this distinction is the whole point of Groundwork — a rule that only asks is not the same as a rule that blocks.

| Mechanism | Enforced (hook) or advisory (rule text) |
|---|---|
| Tier classification (TRIVIAL/STANDARD/MATERIAL) | Advisory — judgment call, not machine-checked |
| OpenSpec proposal/spec/design/tasks for MATERIAL work | Advisory — the rule says to, nothing blocks skipping it |
| Architecture-quality questions and DECISION records | Advisory |
| Evidence labels, validation ladder, runtime-validation rule | Advisory |
| Execution model choice (main / subagent / team) | Advisory; the platform itself gates team spawning on `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` and interactivity |
| Project snapshot at session start | **Injected** — `hooks/groundwork_session_snapshot.py`, a SessionStart hook. Deterministic facts, framed as data (explicit ▼/▲ boundary, per-field caps, control characters stripped). This *mitigates* prompt injection from hostile branch/commit/file names; it cannot eliminate it, because the text is still shown to the model |
| Independent review before a MATERIAL change is "done" | **Enforced** — `hooks/require_material_review.py`, a Stop hook. Residual gameability: a call merely *named* "…review…" satisfies it; the gate proves a review-shaped delegation happened, not its quality |
| No direct push to main/master/production, no force-push | **Enforced** for every `git push` the parser can see — `hooks/block_protected_push.py`, a PreToolUse hook: shell chains, `sh/bash/zsh -c`, `eval`, `HEAD`/`@`, multi-refspec, `:branch` deletion, `--all`/`--mirror`. Not parsed: other wrappers (`xargs`, `python -c`, a script that pushes) and non-exact branch names (`Main`, `release/1.2`). Claude Code's own Bash permission prompt is the backstop for those |
| Investigate before first edit of a file / destructive Bash | **Enforced** — ECC's own GateGuard hook |
| No `--no-verify` git bypass | **Enforced** — ECC's own `block-no-verify` hook |
| Completion status block format and hard rules | Advisory |

## `require_material_review.py` — how the gate actually works

On every `Stop` event:
1. Look for `openspec/changes/*/tasks.md` under the current working directory where every checkbox is `[x]`.
2. Of those, keep only the ones `git status` shows as dirty (uncommitted/untracked) — i.e. this session's own fresh work, not an old change someone already reviewed and merged.
3. If any remain, scan the session transcript for a reviewer-shaped call: an `Agent`/`Task` tool call whose `subagent_type` or `name` contains "review", or a `Skill` call whose name contains "review". `name` matters because current Claude Code launches Agent Team teammates and named subagents through the same `Agent` tool, often with no reviewer-specific `subagent_type`. The free-text `description` deliberately does not count — an unrelated "Review existing tests" exploration would otherwise satisfy the gate by coincidence.
4. Found → allow the Stop. Not found → block, naming the change and what's missing. Claude Code stops re-running any Stop hook after 8 consecutive blocks, so the gate can never trap a session.

Fails open on any error (no git, no `openspec/` directory, unreadable transcript). Reviewer *selection* is untouched — any reviewer-shaped call satisfies the gate. Groundwork enforces that independent review happened, not which specific reviewer ran it.

## `groundwork_session_snapshot.py` — what continuation is built on

On every `SessionStart` (startup, resume, clear, compact, fork) it injects, as `additionalContext`, only facts it can read from the repository: git branch/HEAD/ahead-behind/dirty counts/recent commits, each active OpenSpec change with `<done>/<total>` tasks (flagging a complete-and-uncommitted change as "review gate applies"), the signal files and directories present, and the verification commands the repo declares (Makefile targets, package scripts, pytest/ruff/mypy in pyproject, tox/nox, Go/Rust, Terraform directories, CI workflows). Capped at 2,500 characters, 3-second git timeouts, no network, fail-open, `GROUNDWORK_SNAPSHOT=off` to disable. It complements ECC's SessionStart bootstrap (saved session summary + instincts, matched by worktree) rather than duplicating it: ECC remembers what the last session *said*, the snapshot shows what the repository *is*.

Continuation itself is the rule in `engineering-workflow.md` §7: reconstruct from snapshot → git → OpenSpec → docs → tests/CI/IaC → implementation → only then session files and memory; produce the DONE / PARTIAL / MISSING / BLOCKED / UNVERIFIED table; act on code over docs. There is deliberately no Groundwork state file, database, or daemon — OpenSpec tasks and git are the record.

## Execution model — how Claude chooses main / subagent / team

`engineering-workflow.md` §6. Main session for sequential work sharing context; subagents for isolated investigation, verbose reads, and independent judgment (reviews); an Agent Team only for two or more genuinely independent workstreams with separate file ownership, sized 2–4, with a one-line justification, specialists derived from the task (reusing existing subagent definitions), and the lead synthesizing. When teams are disabled or the session is non-interactive, the same decomposition runs on subagents. Groundwork adds no orchestration code: the Agent tool, `SendMessage`, the task list and the platform's own hooks are the runtime.

## Autonomy — when Groundwork asks versus proceeds

The generic "should I apply this?" stop for every MATERIAL-tier change was tried and removed — it fired constantly and added nothing evidence didn't already answer. The current rule: continue whenever repository evidence, runtime evidence, or official documentation gives a clear answer, and stop only for a genuine owner decision — business/product ambiguity, multiple materially different architectures with no evidence to pick between them, an irreversible/destructive operation, missing credentials, a security boundary needing authorization, or information nothing available can determine. See [VALIDATION.md](VALIDATION.md) for what actually triggers each path in practice.
