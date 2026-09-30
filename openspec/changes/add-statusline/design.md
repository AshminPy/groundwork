# Design

## Context

Verified this session by direct inspection of `main` (HEAD `6d2e90f`) and current official Claude Code documentation — not assumed:

- **Claude Code's `statusLine`** (`code.claude.com/docs/en/statusline.md`, `settings-reference.md`): configured via a `statusLine` settings key (`{"type":"command","command":...}`); any executable receives a full JSON document on stdin on every refresh and its stdout becomes the rendered line. Ten documented refresh triggers (new message, `/compact` finishing, permission/vim-mode change, rate-limit-window resets, an optional `refreshInterval`, etc.), a hardcoded 300ms debounce, and — critically — **an in-flight script is cancelled, never queued**, on the next trigger. No documented hard timeout, but the docs are explicit: "slow scripts block the status line from updating until they complete; keep scripts fast," with the officially recommended mitigation being to cache slow operations keyed by the stdin JSON's own `session_id` (stable across resumes). `context_window.current_usage` (the per-component token breakdown) goes briefly `null` immediately after `/compact` and repopulates on the next API response; `context_window.used_percentage` does not go null and is the reliable field across compaction. There is **no plain git-branch field** in the schema outside worktree sessions (`worktree.branch` only) — a script must shell out for it itself.
- **`hooks/groundwork_telemetry.py`** (Stop hook): appends one JSONL record per turn to `~/.claude/groundwork/groundwork/telemetry/events.jsonl` (one file per `CLAUDE_CONFIG_DIR`, i.e. per machine, shared by every concurrent session), tagged with that turn's own `session_id`. No `flock`/lockfile — relies on the `O_APPEND` open-flag's local-filesystem atomicity for small single-`write()` records; safe locally, not guaranteed on a network-mounted `CLAUDE_CONFIG_DIR`. Captures structural metadata only (tool names, MCP server names, counts, declared playbook/execution-mode/validation labels parsed from the response's own Harness-metadata block) — never prompt text, command text, file paths, or credential-shaped strings (`TOKEN_SHAPED` regex rejects anything digit-containing and ≥12 chars).
- **`hooks/groundwork_session_snapshot.py`** (SessionStart hook): recomputes git/OpenSpec/investigation-file facts fresh at each SessionStart-class event (startup/resume/`/clear`/`/compact`/fork per `docs/CONTEXT-ENGINEERING.md`), capped at 2500 chars, injected as `additionalContext` — never written to a file Groundwork owns, so nothing here is readable by a separate statusLine process.
- **`scripts/groundwork_integrations.py`**: `_mechanism_available` (near-instant `shutil.which`, or a memoized-per-process `claude mcp list` up to `MCP_LIST_TIMEOUT_S=15`), `_mechanism_connected` (only implemented for GitHub's `gh auth status`, `CLI_AUTH_TIMEOUT_S=10`) — a full `list`/`show` run can cost up to ~25s worst case. This is categorically incompatible with a statusLine process that Claude Code will simply cancel on the next refresh trigger rather than wait for.
- **`scripts/groundwork_config.py`**: `_cmd_init` (`init --force`, called by `setup.sh`'s `apply_capabilities()` on every initial setup **and every `--configure` re-run**) calls `save_config(default_config(profile), path)` — an unconditional full rewrite of `config.json` from a fixed-shape template (`profile`/`cloud`/`platform`/`integrations`/`skills`/`routines` only). Any other key placed in `config.json` would be silently discarded on the next `--configure`.
- **`scripts/merge_settings.py`**: the established, tested pattern for additive, non-clobbering settings.json merges (`write_atomic()` via temp-file + `os.replace`; each rule checked against the existing value before writing, e.g. env defaults are "set only if the key is absent").
- **`~/.claude/groundwork/VERSION`**: written once by `install.sh` via `grep -m1 -oE '^## [0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md`, which deliberately does not match a `## Unreleased` heading — so a freshly-installed VERSION reflects the last *cut* release, not necessarily HEAD's exact feature set, whenever unreleased work (like the Integration Catalog, merged without its own version bump) sits on top of it.

## Goals / Non-Goals

**Goals:**
- A truthful, minimal Groundwork statusLine, with an explicit and enforced LIVE / LAST-COMPLETED-TURN / CACHED / UNAVAILABLE contract per field (see spec.md).
- Correct session isolation: never show one session's last-turn state to another.
- Integration Catalog readiness shown only from a pre-computed cache, refreshed at existing lifecycle points — no new scheduled/background process.
- Measured, not assumed, fast execution.
- The smallest useful personalization surface.

**Non-Goals:**
- No background/cron/launchd/daemon process, in this first implementation, to refresh the Integration Catalog cache — see Decision 1.
- No review/MUST-FIX-state, role/persona, or evidence-label-count field — no durable source exists for any of the three (see Decision 4 / spec.md's Unavailable-fields requirement); adding one would require new instrumentation, out of scope here.
- No Integration Usage Telemetry or per-invocation usage dashboard — investigated this session and found **NOT reliably supported**: `turn_facts()` never reads `tool_result`/`is_error` (no `PostToolUse` hook exists anywhere in Groundwork), so success/failure is not recoverable; read/write classification does not exist; domain/capability attribution works only for MCP-named tools (`mcp__<server>__<method>`) and collapses entirely for Bash-invoked CLIs; timestamps are per-turn, not per-call. Building this would need a new `PostToolUse` capture point — a separate future change, after its own investigation. This change creates no counters, fake zeros, or inferred usage metrics of any kind.
- No theme engine, custom shell prompt framework, startup banner, Nerd Font dependency, or animation — Claude Code continues to own general terminal theming; Groundwork owns only Groundwork-specific information.
- No fix to the VERSION/`## Unreleased` semantics described above — Decision 5 classifies it as expected release semantics, not a defect this change should silently work around.

## Decisions

**1. Integration Catalog cache refresh is lifecycle-driven, not scheduled — no daemon, cron, or launchd job.**
The user's own binding requirement for this change. The Integration Catalog's probes cost up to ~25s worst case (`claude mcp list` + `gh auth status`), categorically unsafe inside a statusLine process. Investigated three lifecycle points and adopted all three (the fourth candidate, SessionStart, was investigated and explicitly rejected — see below):
  - **Install** (`install.sh`): one best-effort `groundwork_integrations.py refresh` call after installing the script, non-fatal to the install if it fails/times out.
  - **Configuration** (`setup.sh`'s `apply_capabilities()`, invoked by both initial setup and `--configure`): `configured` observations depend on `config.json`, so refreshing right after it's written keeps the cache in sync with the state that most directly drives it.
  - **Explicit refresh / status command** (`groundwork_integrations.py refresh`, callable any time; and `setup.sh --doctor`'s two existing "Integrations" sections, which already perform this exact live probe every time `--doctor` runs — they now also persist the result as a side effect, changing zero visible `--doctor` output).
  **SessionStart was investigated and rejected**: the existing session-snapshot hook's own design constraint is "keep hooks fast" (3s git-subprocess timeouts); adding a probe with a documented worst case of ~25s would violate that constraint on every session start, not just occasionally. This is a deliberate narrowing of the user's candidate list to the three lifecycle points that are actually safe, not a claim that lifecycle-driven refresh is insufficient — no background/scheduled execution is introduced.
  If a user never triggers any of these three lifecycle points, the cache simply does not exist yet — the statusLine must display no integration readiness rather than inferring any (Decision 3 / spec.md).

**2. Integration Catalog cache: `~/.claude/groundwork/integrations/cache.json`, one entry per integration, each carrying its own `checked_at`.**
Written atomically (temp file + `os.replace`, matching `merge_settings.py`'s `write_atomic()`) by a new `refresh` subcommand that runs the exact same `determine_observation()` computation `list`/`show` already use — no new probe logic, no duplication of truthful-state rules. Per-entry `checked_at` (not one file-level timestamp) keeps the schema correct if a future change ever does partial/incremental refreshes, and lets the statusLine show per-integration staleness precisely.

**3. Integration Catalog readiness is legitimately machine-wide state, unlike last-turn session state — one shared cache file is correct here.**
GitHub/Jira/etc. auth and presence are facts about the machine/user's own credentials and installed tools, not about a specific repository or Claude Code session — two concurrent sessions on the same machine genuinely share the same answer to "is `gh` authenticated right now." This is different in kind from `events.jsonl`'s last-completed-turn fields (Decision 4), which are session-scoped and must never cross-leak.

**4. Session isolation for last-completed-turn fields: filter `events.jsonl` by the stdin JSON's own `session_id`; never a global `current-state.json`.**
`session_id` is already present on every telemetry record (`hooks/groundwork_telemetry.py`) and is documented as stable across resumes in Claude Code's own stdin JSON — no new field or file is needed. The statusLine performs a **bounded backward scan** (from end-of-file, growing the read window up to a fixed cap) for the most recent record whose `session_id` matches the current session; if none is found within that bound, the field is UNAVAILABLE for this render, never inferred from a different session's most recent record. This bound is a deliberate, documented trade-off: true worst-case correctness would require an unbounded scan of a file shared by every concurrent session on the machine, which is incompatible with the performance requirement; realistic concurrent-session counts make the bound generous in practice.
Live git branch/dirty state is inherently session/worktree-safe because it is a live subprocess call scoped to the stdin JSON's own `workspace.current_dir` — never a shared file.

**5. The VERSION-lags-HEAD gap is expected release semantics, not a defect this change fixes.**
`install.sh`'s regex intentionally matches only a numbered `## X.Y.Z` CHANGELOG heading, never `## Unreleased` — standard "Keep a Changelog"-style practice where a version is assigned only at an actual release/tag step, not at every merge. This is consistent with the repository's own history (`## 2.1.0 — 2026-09-28` was itself a deliberate release heading, cut after prior unreleased work accumulated). The statusLine displays whatever `VERSION` currently contains, honestly labeled as "the installed release," with no attempt to infer or override it from HEAD/CHANGELOG state — doing so would itself be a form of inference the user's binding requirements forbid. If the project's release cadence changes such that `VERSION` misleads users in practice, that is a separate, standalone fix to `install.sh`'s regex or the release process, not something folded into this change.

**6. Personalization lives in its own file, `~/.claude/groundwork/statusline-config.json`, never inside `config.json`.**
Per Context above, `groundwork_config.py init --force` unconditionally rewrites `config.json` from a fixed template on every `--configure` run — co-locating personalization there would silently discard a user's display preferences the next time they reconfigure capabilities, an entirely unrelated action. A small standalone file (hand-editable, like `config.json` itself; safe defaults if absent or malformed) keeps the two concerns — capability profile vs. display preference — decoupled, matching the existing precedent of `config.json` itself being explicitly documented as hand-editable.

**7. `statusLine` is merged into `settings.json` additively — set only if the key is absent.**
Matches every existing `merge_settings.py` rule's philosophy (never clobber a user's own choice). A user who has already configured a custom `statusLine` keeps it untouched; Groundwork's own statusLine is offered only into an empty slot.

**8. [Correction, post-implementation] A fresh cached Integration Catalog entry now visibly shows its age too, not only a stale one.**
The first implementation only annotated a cached integration's rendering once it crossed the staleness threshold; a fresh entry (e.g. `GitHub ●`) carried no visible marker distinguishing it from a hypothetical LIVE reading. Owner review on PR #26 caught that this could visually imply CONNECTED/CONFIGURED/AVAILABLE is a live observation even though it always means "as of the last cached check." Corrected: `_fmt_integrations()` now appends a compact age (`· 4m` / `- 4m` in plain mode) to every cached entry, fresh or stale; a stale entry additionally gets a leading `!` on the age itself (`· !2h`) so it stays visually distinct from a merely-fresh one without a verbose per-entry label. No change to the underlying readiness model, the cache schema, or the refresh lifecycle (still install/configure/doctor-only, no scheduling).

## Data-source contract (summary; full field table in spec.md)

| Timing | Fields | Source |
|---|---|---|
| LIVE | model, context %, cost (where supplied); git branch/dirty | stdin JSON; one short-timeout `git` subprocess |
| LAST-COMPLETED-TURN | playbook, execution mode, tests-run/validation | `events.jsonl`, tail, filtered by `session_id` |
| CACHED | capability profile; Integration Catalog readiness; Groundwork version; routine last-run result | `config.json`; `integrations/cache.json`; `VERSION`; `routines/results/*.json` |
| UNAVAILABLE (never displayed) | review/MUST-FIX state; role/persona; evidence-label counts | no durable source exists anywhere in Groundwork today |

## Risks / Trade-offs

- **[Risk] A statusLine process spawned very frequently (rapid-fire triggers) could still add up to non-trivial I/O even at low per-call cost** → Mitigation: every read is a small bounded file (config.json, statusline-config.json, integrations cache, a bounded tail of events.jsonl); git subprocess carries an explicit short timeout and is skipped (not retried) on failure. Measured at validation time, not merely claimed.
- **[Risk] The bounded backward-scan of `events.jsonl` could miss a genuinely-existing last-turn record for the current session if enough other sessions' records were appended after it** → Accepted trade-off (Decision 4): the field degrades to UNAVAILABLE for that render rather than either an unbounded scan (performance risk) or a wrong cross-session guess (truthfulness risk).
- **[Risk] `O_APPEND`-only telemetry writes are not safe on a network-mounted `CLAUDE_CONFIG_DIR`** → Pre-existing property of `groundwork_telemetry.py`, unchanged by this read-only consumer; noted, not addressed here (would be a separate telemetry-hardening change if it ever matters in practice).
- **[Trade-off] Integration Catalog readiness can be stale between lifecycle-triggered refreshes (potentially hours/days if a user never runs `--doctor`/`--configure`)** → Accepted and made visible: every cached entry carries `checked_at`; the statusLine surfaces cache age and never claims cached readiness is live.
- **[Trade-off] No SessionStart-triggered refresh** → Accepted (Decision 1): correctness here is bounded staleness, not incorrectness — cached data is always honestly aged, never wrong-in-kind.

## Migration Plan

Purely additive: new script, new test file, small additive edits to `groundwork_integrations.py` (new subcommand), `install.sh`, `setup.sh`, `merge_settings.py`, three docs. No existing config schema, hook, or CLI command changes; no existing test needs to change. Rollback is deleting the new files/cache directory and reverting the small edits — no data migration.
