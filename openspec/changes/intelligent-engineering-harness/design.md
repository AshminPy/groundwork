## Context

Verified 2026-09-20 against the live machine and current official docs:

- Groundwork 1.0.0 = 2 rules (~107 lines), 2 hooks, installer. Live copies under `~/.claude/rules/harness/` and `~/.claude/hooks/` are byte-identical to the repo (`diff` clean). Tests: `python3 -m pytest tests` → 2 passed.
- Claude Code 2.1.258. Agent Teams: experimental, off by default, enabled by `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`; the lead spawns a teammate by calling the `Agent` tool with a `name`; `TeamCreate`/`TeamDelete` no longer exist; teammates do not spawn in `-p` mode; one team per session; no nested teams; teammates load CLAUDE.md/rules but not the lead's history (docs/en/agent-teams). The Task tools (`TaskCreate`…) are on by default only for Claude 3.x/4.x models, so `TaskCreated`/`TaskCompleted` hooks cannot be relied on (docs/en/tools-reference §Task tool availability).
- Stop hook: input has `stop_hook_active`, `last_assistant_message`; output `{"decision":"block","reason":…}` is the documented block format; Claude Code overrides the hook after 8 consecutive blocks (docs/en/hooks §Stop). Transcript may lag the in-memory conversation.
- SessionStart hook: fires on `startup|resume|clear|compact|fork`; plain stdout or `hookSpecificOutput.additionalContext` is injected before the first prompt; must be fast (docs/en/hooks §SessionStart).
- ECC 2.2.1 already injects a per-worktree session summary (≤ 8,000 chars) and instincts at SessionStart, and ships `save-session`/`resume-session`. OpenSpec 1.12.0 exposes `openspec list --json` / `status --all --json`.
- `~/.claude/rules/**/*.md` are loaded recursively at launch for every project (docs/en/memory). Every line added to a rule is paid in every session.

## Goals / Non-Goals

**Goals:**
- Architecture-quality guidance that changes what gets built for MATERIAL work, with near-zero cost for TRIVIAL work.
- A deterministic rule for main/subagent/team selection that never needs the user to name agents.
- A validation ladder and runtime-validation rule that make "tests pass" and "deployed" distinct from "works live".
- Fresh-session continuation from repository evidence, with one small deterministic hook.
- Review-gate compatibility with teammates and named subagents.
- Installer that stays additive/idempotent and cleans up the legacy rule copy.

**Non-Goals:**
- Any custom agent framework, scheduler, message bus, team manager, database, or persistence service.
- Permanent technology-specific teammate roles or new agent/skill catalogs.
- Duplicating ECC (session save/resume, reviewers, verification-loop) or OpenSpec (specs, tasks, archive).
- Enabling Agent Teams by default.
- Anything SRE-Agent-specific.

## Decisions

**D1 — Architecture guidance is a third rule file, not a hook.**
EVIDENCE: rules are loaded every session (docs/en/memory); a hook cannot judge design quality. WHY: judgment content belongs in instructions; keeping it in its own file keeps ownership clear and lets the workflow rule stay a router. TRADEOFFS: ~60 more lines of always-on context (~600 tokens). VALIDATION: rule text review + the SRE pilot. UNCERTAINTY: adherence is model behaviour, not enforced.

**D2 — Execution-model selection is rule text with a hard fallback, not tooling.**
EVIDENCE: Claude Code already decides team vs subagent natively when `name` is passed (docs/en/agent-teams §How Claude starts agent teams); ECC's `team-agent-orchestration`/`dev-team` skills are invocable presets. WHY: the platform provides the runtime; Groundwork only needs the criteria (independent workstreams, file ownership, size 2–4, one-line justification) and the fallback (disabled/non-interactive → subagents). TRADEOFFS: no deterministic guard against an unnecessary team; the platform itself gates spawning on the env var. VALIDATION: simple-task run with teams disabled produces no team (deterministic); team path verified via hook unit tests on constructed transcripts. UNCERTAINTY: live team formation not exercised on this machine (teams disabled, interactive-only).

**D3 — Review gate matches `subagent_type` OR `name` (regex "review"); NOT `description`.**
EVIDENCE: teammates are spawned via `Agent` with `name`; `subagent_type` may be absent or generic (docs/en/agent-teams, docs/en/sub-agents §Subagent names). The first draft also matched `description`; the independent code review showed that an early `Explore` call described as "Review existing test layout before implementing" would then satisfy the gate months before the gated diff existed. WHY: `subagent_type` and `name` are persona identifiers set once per call; `description` is free prose. Smallest change that keeps the gate honest for teams; reviewer selection stays contextual. TRADEOFFS: a non-reviewer *named* "reviewer" would satisfy the gate — acceptable, the gate enforces that a review-shaped delegation happened, not its quality. VALIDATION: unit cases (positive: `name`; negative: implementer-only, description-only). UNCERTAINTY: transcript lag at Stop time could miss a reviewer dispatched in the final turn; the gate re-evaluates on the next Stop.

**D4 — Continuation = SessionStart snapshot hook + rule procedure; no continuation file.**
EVIDENCE: git and OpenSpec already hold the state (`tasks.md` checkboxes, `openspec status --all --json`); ECC injects the matching session summary; docs say SessionStart must be fast. WHY: a snapshot is deterministic and repo-native; a Groundwork state file would be a second source of truth that drifts. TRADEOFFS: STANDARD work without OpenSpec relies on branch/commit state for intent; the rule tells Claude to leave the next step in the commit/branch when stopping mid-task. VALIDATION: unit tests on constructed repos; live `claude -p` run quoting the injected snapshot. UNCERTAINTY: none on mechanism; usefulness depends on repos keeping OpenSpec/commit hygiene.

**D5 — Snapshot discovers verification commands, never invents them.**
EVIDENCE: user requirement §7; Makefile/package.json/pyproject/CI files are deterministic sources. WHY: gives the continuation procedure and the validation ladder real commands. TRADEOFFS: heuristic file detection may list a target that is not the intended test entry point — the rule says to confirm against README. VALIDATION: unit test with Makefile + package.json fixtures.

**D6 — Installer migrates the legacy `rules/harness` copy to a backup instead of deleting it.**
EVIDENCE: live machine has `~/.claude/rules/harness/` (pre-Groundwork path) and `~/.claude/CLAUDE.md` points to it. WHY: additive/reversible; avoids double-loading rules. TRADEOFFS: the user must edit the CLAUDE.md pointer themselves (the installer must not edit a user-authored file). VALIDATION: migration unit test with a temp `CLAUDE_CONFIG_DIR`.

**D7 — Agent Teams stay opt-in (`install.sh --agent-teams`).**
EVIDENCE: experimental; enabling changes ordinary delegation (named subagents become teammates) (docs/en/agent-teams §Enable). WHY: an installer must not silently change how every session delegates. TRADEOFFS: teams are unavailable until the user opts in. VALIDATION: merge test with/without the flag.

**D8 — Stop hook keeps `decision: block` and relies on the platform's 8-block cap.**
EVIDENCE: docs/en/hooks §Stop (documented format; override after 8 consecutive blocks). WHY: no state file needed; a model that cannot dispatch a reviewer is released by the platform, not by a Groundwork bypass. TRADEOFFS: up to 8 extra turns in a pathological case. VALIDATION: existing live evidence (docs/VALIDATION.md) plus unit tests.

## Risks / Trade-offs

- Always-on context grows by roughly 120 rule lines plus ≤ 2.5 KB snapshot per session. Mitigation: hard cap on the snapshot; rules written as short imperative lines.
- Rule adherence is model behaviour. Mitigation: the only things that can be enforced (push guard, review happened) stay hooks; everything else is validated by observation in the SRE pilot and reported honestly.
- A user-level `~/.claude/rules/behavior.md` on this machine still contains retired-harness instructions (plan-first gate, `/verified-ship`). Out of Groundwork's scope; reported in the limitations.
- `~/projects/ai-projects/claude-toolkit/install.sh` still `rsync --delete`s into `~/.claude/rules/` and `~/.claude/hooks/`; running it would remove Groundwork. Out of scope; reported.
