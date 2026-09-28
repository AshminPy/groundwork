# Context engineering (Groundwork 2.1)

What actually enters a Claude Code session's context when Groundwork is installed, classified and measured where the platform exposes a real measurement. No fabricated token counts — anything not directly measurable is stated as such.

## Inventory

| Source | Classification | Measured | Notes |
|---|---|---|---|
| 5 Groundwork rule files (`rules/*.md`) | **Always loaded** | 290 lines total (`wc -l rules/*.md`, 2026-09) | Claude Code loads every `*.md` under `~/.claude/rules/` recursively at launch — this is the one thing Groundwork cannot make lazy; kept intentionally small (imperative lines, no prose padding) for exactly that reason |
| Session-start snapshot (`groundwork_session_snapshot.py`) | **Always loaded, capped** | ≤2,500 characters (`MAX_CHARS` in the hook) | Emitted once per session start (startup/resume/clear/compact/fork); git facts, OpenSpec progress, discovered verification commands, investigation-continuity content when present |
| Investigation-continuity file | **Persisted, surfaced always-loaded when present** | ≤800 characters display cap (`MAX_INVESTIGATION_CHARS`), read generously then truncated | One file per repository, created lazily by the model's own write — not installed, not present unless an investigation is genuinely ongoing |
| Playbooks (`playbooks/*.md`, 10 files) | **Selectively loaded** | 1,838–3,589 bytes each (`MAX_PLAYBOOK_BYTES = 4000` cap), 25,497 bytes total across all 10 | Read only when `task-routing.md` selects the one matching category — the other nine never enter context for that task |
| ECC (if installed) | **Always loaded, third-party, unpinned** | ~27,000–43,600 tokens always-on, independently corroborated across two separate measurements (this session's own dependency audit, and a community measurement) — see `docs/RELEASE-REPORT-2.0.md`/dependency-audit findings; **not re-measured here**, cited from those sources, not fabricated fresh | The dominant context cost in a Groundwork+ECC session by a wide margin; ECC is optional (§ capability resolution below), and disabling it (`claude plugin disable ecc@ecc`) is the one lever Groundwork itself has never had to build, because Claude Code already provides it |
| Skill full bodies (SKILL.md content beyond the always-in-context description) | **Lazy / progressive disclosure** | Not independently measured — this is Claude Code's own documented native mechanism (descriptions always present, full body loads only on invocation) | Applies to every plugin-sourced and native skill, including ECC's 292; Groundwork does not need to build anything to get this |
| MCP tool schemas | **Lazy, scope-dependent** | Not measured | Configurable per-project/session rather than globally always-on; Groundwork's own MCP/integration guidance (`docs/INTEGRATIONS.md`) explicitly recommends scoping this way rather than a blanket-enabled server list |
| Deferred/searchable tools (this session's own `ToolSearch` mechanism) | **Lazy, directly observed** | N/A | Directly observed in this very session: a large set of tool schemas are not resident in context up front; they are fetched on demand by name/keyword search immediately before first use. This is the platform's own answer to "tool bloat" and is exactly the pattern §7's capability-resolution model leans on rather than reimplementing |
| Subagent (`Agent` tool) dispatches | **Isolated** | N/A | Directly observed throughout this project's own implementation history: a subagent's exploration, file reads, and reasoning never appear in the parent session's context — only its final structured report does. This is why "dispatch a subagent to investigate/gather capability evidence" is itself a valid, native way to keep discovery cheap rather than reading everything into the main session first |
| Telemetry (`~/.claude/groundwork/telemetry/events.jsonl`) | **Persisted, never re-read into context by a hook** | N/A | Append-only; read only by the separate report generator process, never by a hook, so it cannot grow a session's context regardless of its size |
| Git state, OpenSpec task state, docs, tests | **Reconstructed each session** | N/A | Never cached or persisted by Groundwork; re-read from the repository every time per `engineering-workflow.md` §7 — this is deliberate: stale cached state is worse than a cheap re-read |
| Routines (2.1, new) | **Isolated by construction** | N/A | Each routine run is its own separate, non-interactive `claude -p` process — it never shares or pollutes the interactive session's context, and its own context is exactly the routine's own prompt plus whatever evidence it reads, nothing else |
| CLAUDE.md, native Claude Code system prompt/tool definitions | **Always loaded, not Groundwork's to change** | N/A | Native to every session regardless of Groundwork; out of scope |

## Unnecessary or duplicated

None found. This was checked deliberately, not assumed: Groundwork's own capability-ownership matrix (`docs/ARCHITECTURE.md`) was built and independently re-reviewed across the 2.0 implementation specifically to catch this, and this audit found nothing new to add. The one real, non-trivial cost in the system (ECC's always-on catalog) is not duplicated by Groundwork — it is a third-party cost Groundwork inherits and documents honestly, not one it created.

## What this means for 2.1's own additions

- The capability-resolution model (`engineering-workflow.md`) is written as judgment guidance in already-always-loaded rule text — a few lines, not a new mechanism, because the discovery order itself needs to be always-known, while the capabilities it discovers stay lazy.
- The MCP/integration matrix and curated-skills evaluation are documentation, not installed defaults — nothing in them adds to any session's context unless the user configures the specific capability.
- Routines run as fully isolated, separate processes — they cannot add anything to an interactive session's context by construction.
- No custom context-management infrastructure was built. Every lazy-loading requirement in the 2.1 brief is met by a mechanism Claude Code already provides (progressive-disclosure skills, scoped/deferred MCP, tool search, subagent isolation) or by Groundwork's own existing patterns (playbooks read on demand, investigations created lazily).
