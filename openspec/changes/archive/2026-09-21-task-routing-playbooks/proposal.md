## Why

Groundwork 1.1.0 governs *how* engineering work is executed, but every request still arrives without a stated task shape: the model decides ad hoc whether it is researching, explaining, designing, fixing or deploying, and the answer's structure varies with it. Two costs follow: verbose narration of investigation steps the user did not ask for, and either too many clarification questions or none where one was needed (a destructive action with an ambiguous target). Loading a full workflow for every task type into every session would fix consistency at an unacceptable context cost.

## What Changes

- **New rule `rules/task-routing.md`** (always loaded, ~45 lines): classify each substantive request into exactly one of ten categories, read only that category's playbook, apply a material-ambiguity rule (ask only when the missing information could change correctness, safety, architecture, permissions, target environment, a destructive action or the outcome), and a universal output contract that suppresses narration without hiding material risk or evidence.
- **New `playbooks/` directory** (ten files, installed to `~/.claude/groundwork/playbooks/`, never under `rules/` so never auto-loaded): RESEARCH, EXPLAIN, DESIGN, PLAN, IMPLEMENT, TROUBLESHOOT, VALIDATE, AUDIT, DEPLOY, DOCUMENT. Each has the same six sections: Goal, Workflow, Evidence, Ask Before Acting When, Completion Criteria, Output Format.
- **Installer**: `install.sh` copies the playbooks; `uninstall.sh` removes them. No `settings.json` change.
- **Tests**: structural checks (every category has a playbook, every playbook has the six sections, size cap, install copies them idempotently) plus a live scenario checker for the twelve routing/ambiguity cases.
- **Docs**: README, ARCHITECTURE, CHANGELOG.

Explicitly unchanged: `engineering-workflow.md`, `evidence-policy.md`, `architecture-quality.md`, all three hooks, the settings merge, tiers, OpenSpec use, the review gate, the completion block. The rule states that any conflict is resolved in favour of the existing rule.

## Capabilities

### New Capabilities
- `task-routing`: one-category classification, on-demand playbook loading, material-ambiguity clarification, and the universal output contract.

### Modified Capabilities
<!-- none — additive layer only -->

## Impact

- Always-loaded context grows by one ~45-line rule; each task reads one ~40–60-line playbook on demand.
- Installed footprint: `~/.claude/rules/groundwork/task-routing.md` and `~/.claude/groundwork/playbooks/*.md`.
- No hook, permission, or safety behaviour changes; the non-regression check is a SHA-256 comparison of the pre-existing critical files before and after.
