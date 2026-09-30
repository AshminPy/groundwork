# Quiet interaction + routine readiness

## Why

Two independent, user-value-driven daily-experience gaps, investigated together but scoped separately below:

**Quiet interaction**: normal engineering questions currently surface as `QUESTION → "I'll read..." → "Now I'll check..." → tool narration → ANSWER` rather than `QUESTION → quiet evidence gathering → ANSWER`. Investigated live (this session, current official Claude Code docs): the narration is not caused by Groundwork's own rules — `rules/output-contract.md` already forbids narration in the *final* response ("no narration of commands run, files inspected or hypotheses considered") — it comes from Claude Code's own base system prompt instruction to "give short updates" mid-turn, which output-contract.md has never addressed because it was scoped to the final answer, not the process. Claude Code ships a built-in `Concise` output style (confirmed current, requires ≥v2.1.237) that does exactly this — leads with the result, drops preamble/narration/recaps — while explicitly preserving "anything you need to act safely: error reports, failing test output, security warnings, and confirmations for destructive actions."

**Routine readiness**: a scheduled Groundwork routine must never unexpectedly depend on someone being present to approve an interactive prompt. Traced `scripts/groundwork_routines.py`'s actual execution path: `build_command()` already unconditionally includes `--permission-mode dontAsk --permission-prompts none` for every routine, so a routine structurally cannot hang on an unavailable interactive approval — it fails closed (auto-deny), not fail-hang. The real, evidenced gap is different: Groundwork already gathers per-routine `enabled`/`access`/`available`/`connected` data (`_doctor_rows()`, `check_access()`) but never synthesizes it into an explicit READY/BLOCKED verdict before a user schedules a routine — so a routine can look "configured" in `setup.sh --routines` output without the user being able to tell at a glance whether it will actually do useful unattended work. One routine (`jira_eod`, the only mutating one) has an additional, honest limitation: no Jira access mechanism has a real connectivity check, and its tool grant is a necessarily-broad wildcard (the Jira MCP server is user-configured, unlike GitHub's one hardcoded, well-known server) — this needs to be surfaced truthfully, not faked into narrower scoping that doesn't actually exist.

## What Changes

- Extend `rules/output-contract.md` with a short, scoped principle: do not narrate routine read-only investigation mid-turn; still surface user-input/approval needs, blockers, failures, conflicting evidence, security concerns, destructive/mutating actions, materially-changed state, and genuinely long-running progress.
- Additively set `outputStyle: "Concise"` in `settings.json` via `merge_settings.py` (only if the key is absent — an existing explicit user preference is never touched), with symmetric removal in `unmerge_settings.py`, following Groundwork's existing additive-settings philosophy (same pattern as the `statusLine` key).
- Add a routine readiness synthesis (`readiness_state()` in `scripts/groundwork_routines.py`) that classifies each routine as `READY` / `BLOCKED` / `NOT ENABLED` from data Groundwork already collects — no new probes, no new permission model, no second parallel framework. Surface it in `setup.sh --routines` output.
- Add a regression test asserting `build_command()` always includes `--permission-mode dontAsk` and `--permission-prompts none` for every routine, and never introduces a blanket bypass — a structural, testable guarantee that a scheduled routine can never depend on interactive approval.
- Document, truthfully, that `jira_eod`'s live-posting mode has no real Jira connectivity check today for any access mechanism, and that its tool grant is a broad, server-level wildcard rather than a narrowly-scoped write permission — recorded as a known limitation, not silently fixed with fake granularity.

## Non-Goals

- No stdout filtering, terminal wrapper, custom renderer, or second Claude Code client.
- No new permission/readiness framework parallel to the Integration Catalog's existing available/configured/connected model.
- No blanket `bypassPermissions` or auto-authorization of arbitrary Bash/MCP/filesystem/cloud mutation.
- No narrowing of Jira MCP tool grants to fake read/write scoping Claude Code cannot actually express for an arbitrary user-configured server.
- No statusLine changes, no Integration Usage Telemetry, no dashboard changes, no release automation.
