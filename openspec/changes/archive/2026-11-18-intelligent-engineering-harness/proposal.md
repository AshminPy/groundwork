## Why

Groundwork 1.0.0 solved three gaps on top of ECC + OpenSpec: risk-tier routing, an evidence policy, and an enforced independent review for material changes. Real use since 2026-09-03 shows four gaps it does not cover:

1. **Architecture quality is not guided.** The workflow rule says "investigate → propose → apply" but gives no criteria for *what makes a design good*: nothing asks "what will change, what should be configuration, how is this observed, how is it rolled back" before a MATERIAL implementation starts. Result: first instances get wired permanently into code (single cluster, single model, single environment) and are re-engineered later.
2. **Execution model is left to habit.** Nothing tells Claude when to stay in the main session, when to delegate a focused investigation to a subagent, and when native Agent Teams (experimental, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) are justified. The user should never have to say "create four agents".
3. **Testing and runtime validation are under-specified.** The evidence policy has a completion table but no validation ladder, so "tests pass" is treated as proof of runtime behaviour, and generic commands (`pytest`, `npm test`) get run whether or not the project uses them.
4. **Continuation depends on chat history.** Opening a project in a fresh session and saying "continue this project" relies on ECC's session file (global, per-worktree match) and the model's memory, not on the repository. There is no deterministic, repo-native snapshot of branch, dirty files, OpenSpec progress, or the project's real verification commands.

A compatibility problem was also found while inspecting the live installation: the review-gate hook only recognises reviewer-shaped calls via `subagent_type`/`skill`. Current Claude Code (2.1.258, verified against the official docs 2026-09-20) launches Agent Team teammates and named subagents through the same `Agent` tool using `name` and `description`; a reviewer teammate spawned that way is invisible to the gate. Separately, this machine still carries the pre-Groundwork copy of the rules under `~/.claude/rules/harness/`, so running `install.sh` today would load two copies of every rule.

## What Changes

- **New rule `rules/architecture-quality.md`** — the governing principle ("smallest design that satisfies today's requirement while preserving low-cost paths for foreseeable change"), the quality dimensions as *decision criteria* (not a checklist), the pre-MATERIAL questions, and the variation-point rule (config/interface boundary for environments, providers, clusters, models, regions, tenants when the project clearly has more than one).
- **`rules/engineering-workflow.md`** gains: an UNDERSTAND step that produces a DONE / PARTIAL / MISSING / BLOCKED / UNVERIFIED state table for existing projects; an execution-model section (main session vs subagents vs Agent Teams, with size and justification rules and the "teams disabled or non-interactive → subagents" fallback); a CONTINUATION procedure for "continue this project"; a `Reviewed:` row in the completion block; explicit "never default to `--dangerously-skip-permissions`".
- **`rules/evidence-policy.md`** gains: the 7-rung validation ladder; "derive verification commands from project evidence, never invent them"; "mocks never prove runtime"; the compressed DECISION record (DECISION / EVIDENCE / WHY / TRADEOFFS / VALIDATION METHOD / UNCERTAINTY) for MATERIAL decisions only.
- **`hooks/require_material_review.py`** — also matches `name` and `description` on `Agent`/`Task` calls so reviewer teammates and named reviewer subagents satisfy the gate; unchanged fail-open behaviour; documents the platform's 8-consecutive-block cap.
- **New hook `hooks/groundwork_session_snapshot.py`** (SessionStart) — emits a deterministic, capped (≤ 2,500 chars) project snapshot from repository state only: branch, HEAD, ahead/behind, dirty/untracked counts, last commits, OpenSpec changes with task progress and whether the review gate applies, project signal files, and verification commands discovered in the repo (Makefile targets, package scripts, pytest/tox/CI). Fail-open, no network, ≤ 3 s git timeouts.
- **Installer** — `scripts/merge_settings.py` registers the SessionStart hook idempotently and supports `--agent-teams` (opt-in only; never enabled silently); `scripts/migrate_legacy_rules.py` moves a pre-Groundwork `~/.claude/rules/harness/` copy into a timestamped backup and tells the user to update the `CLAUDE.md` pointer; `uninstall.sh`/`unmerge_settings.py` reverse exactly what was added.
- **Tests** — `tests/test_hooks.py` extended: teammate/named-subagent review matching (positive and negative), snapshot hook (content, cap, fail-open), settings merge idempotency and user-override preservation, unmerge symmetry, legacy migration.
- **Docs** — README, ARCHITECTURE, VALIDATION, TROUBLESHOOTING, UPGRADE-ROLLBACK, CHANGELOG 1.1.0.

Explicitly **not** changed: TRIVIAL/STANDARD/MATERIAL tiers, the six owner-decision triggers, `block_protected_push.py`, ECC/OpenSpec installation paths, the additive-only settings merge.

## Capabilities

### New Capabilities
- `architecture-decision-guidance`: how Claude evaluates and records a MATERIAL architecture/implementation decision.
- `execution-model-selection`: how Claude chooses between the main session, subagents, and Agent Teams, and how a reviewer teammate satisfies the review gate.
- `validation-and-review-evidence`: the validation ladder, runtime-validation rule, and independent-review classification that back every completion claim.
- `project-continuation`: reconstructing an existing project's state from repository evidence in a fresh session, including the deterministic SessionStart snapshot.
- `harness-installation`: idempotent, additive install/uninstall including migration of the pre-Groundwork rule copy and opt-in Agent Teams enablement.

### Modified Capabilities
<!-- none: no existing main spec exists in this repo yet -->

## Impact

- Files: `rules/*.md` (3), `hooks/require_material_review.py`, new `hooks/groundwork_session_snapshot.py`, `scripts/merge_settings.py`, `scripts/unmerge_settings.py`, new `scripts/migrate_legacy_rules.py`, `install.sh`, `uninstall.sh`, `tests/test_hooks.py`, `docs/*`, `README.md`, `CHANGELOG.md`.
- Installed footprint: `~/.claude/rules/groundwork/` (3 files), `~/.claude/hooks/` (3 files), one extra `hooks.SessionStart` entry in `settings.json`. Every session pays ~1–2.5 KB of additional startup context for the snapshot; hooks add ~150 ms interpreter start each.
- No SRE-Agent-specific logic; no new agents, skills, daemons, databases, or message buses. Agent Teams remain an opt-in Claude Code experimental feature.
