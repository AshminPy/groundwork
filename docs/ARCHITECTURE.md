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

Groundwork → the governance layer. Two rule files loaded into every session's
             context; two hooks that enforce what the rules can only ask for.
```

Groundwork does not replace either upstream project's job. It exists because, tested plainly, neither one on its own reliably makes an agent plan, test, review, and honestly report completion for a request that doesn't spell every step out. See [VALIDATION.md](VALIDATION.md) for the actual tests that established this.

## Request lifecycle

```
                 USER GOAL
                     │
                     ▼
   rules/engineering-workflow.md classifies the request
                     │
        ┌────────────┼────────────┐
    TRIVIAL       STANDARD      MATERIAL
        │             │             │
    just do it   inline plan   openspec init (if needed)
        │         + tests      /opsx:propose — proposal,
        │         + self-      delta spec, design decision,
        │         review       tasks; openspec validate
        │             │             │
        │             │       evidence-backed decisions
        │             │       (rules/evidence-policy.md)
        │             │             │
        │             │       /opsx:apply — implement,
        │             │       write tests, run them
        │             │             │
        │             │       independent fresh-context
        │             │       review — MUST FIX vs
        │             │       NICE TO HAVE; only MUST FIX
        │             │       blocks — ENFORCED by
        │             │       hooks/require_material_review.py
        │             └────────────┤
        │                          ▼
        │              deploy / live-validate if in scope
        └────────────────┬─────────┘
                          ▼
              COMPLETION STATUS block
   Code / Tests / Merged / Deployed / Live validated
      → COMPLETE / PARTIAL / BLOCKED / PLANNED / FAILED
```

## What is actually enforced versus advisory

Being honest about this distinction is the whole point of Groundwork — a rule that only asks is not the same as a rule that blocks.

| Mechanism | Enforced (hook blocks) or advisory (rule text) |
|---|---|
| Tier classification (TRIVIAL/STANDARD/MATERIAL) | Advisory — judgment call, not machine-checked |
| OpenSpec proposal/spec/design/tasks for MATERIAL work | Advisory — the rule says to, nothing blocks skipping it |
| Evidence labels (VERIFIED/UNVERIFIED/ASSUMPTION/…) | Advisory |
| Independent review before a MATERIAL change is "done" | **Enforced** — `hooks/require_material_review.py`, a Stop hook |
| No direct push to main/master/production, no force-push | **Enforced** — `hooks/block_protected_push.py`, a PreToolUse hook |
| Investigate before first edit of a file / destructive Bash | **Enforced** — ECC's own GateGuard hook |
| No `--no-verify` git bypass | **Enforced** — ECC's own `block-no-verify` hook |
| Completion status block format and hard rules | Advisory |

Two of Groundwork's three additions are advisory by design (tiering and evidence policy are judgment calls a hook can't safely make). The third — independent review — is the one gap that *can* be checked mechanically (did a reviewer-shaped tool call happen in this transcript, yes or no), so it is a hard gate, not a request.

## `require_material_review.py` — how the gate actually works

On every `Stop` event:
1. Look for `openspec/changes/*/tasks.md` under the current working directory where every checkbox is `[x]`.
2. Of those, keep only the ones `git status` shows as dirty (uncommitted/untracked) — i.e. this session's own fresh work, not an old change someone already reviewed and merged.
3. If any remain, scan the session transcript for a `Task`/`Agent` tool call whose `subagent_type` contains "review", or a `Skill` call whose name contains "review".
4. Found → allow the Stop. Not found → block, naming the change and what's missing.

Fails open on any error (no git, no `openspec/` directory, unreadable transcript) — a broken guard should never become a silent session-wide bypass of Claude's own permission model, and it should never accidentally hang a session that has nothing to do with OpenSpec at all.

Reviewer *selection* is untouched — any reviewer-shaped call satisfies the gate. This is deliberate: Groundwork enforces that independent review happened, not which specific reviewer ran it.

## Autonomy — when Groundwork asks versus proceeds

The generic "should I apply this?" stop for every MATERIAL-tier change was tried and removed — it fired constantly and added nothing evidence didn't already answer. The current rule: continue whenever repository evidence, runtime evidence, or official documentation gives a clear answer, and stop only for a genuine owner decision — business/product ambiguity, multiple materially different architectures with no evidence to pick between them, an irreversible/destructive operation, missing credentials, a security boundary needing authorization, or information nothing available can determine. See [VALIDATION.md](VALIDATION.md) for what actually triggers each path in practice — including three attempts at constructing a "genuine architecture ambiguity" test that all turned out to have a real evidence-based answer (a citable RFC, an established convention, the repo's own dependency posture), and one that had none (a pricing/monetization decision) and correctly stopped.
