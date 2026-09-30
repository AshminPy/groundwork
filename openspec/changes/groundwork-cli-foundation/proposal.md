# Proposal — Groundwork CLI foundation (Next Release Program, Phase 1)

## Why

Groundwork today has no single, discoverable user-facing entry point. A user or Claude Code
session that wants to check Groundwork's health, see its version, or diagnose a problem has to
already know which of ~6 separately-invoked scripts and shell entry points owns that
functionality, the exact installed path (`~/.claude/groundwork/bin/<script>.py` vs. repo-relative
`scripts/<script>.py` depending on context), and each script's own flag dialect (some use
`argparse`, some raw `sys.argv`; `--help` support is inconsistent; `uninstall.sh` has none at
all). This is confirmed by a full command-surface audit of the current repository (see
`design.md` DECISION 1's evidence) — not assumed.

This phase introduces `groundwork` as that entry point, starting with the smallest useful base:
`groundwork --help`, `groundwork version`, `groundwork doctor`. It does not rebuild any existing
capability — it dispatches to the same scripts that already exist and already compute real,
evidence-backed state.

## What Changes

- A new `groundwork` executable (pure Python 3 stdlib, mirrors every other Groundwork script's
  runtime footprint) installed to `$CLAUDE_CONFIG_DIR/groundwork/bin/groundwork`.
- `groundwork --help` / `groundwork -h`: lists the implemented subcommands, works with no
  arguments too (shows the same help).
- `groundwork version`: reports the installed Groundwork version from the same authoritative
  source `setup.sh --verify` already reads (`$CLAUDE_CONFIG_DIR/groundwork/VERSION`), never
  inferred from git state.
- `groundwork doctor`: dispatches to the exact same code path `./setup.sh --doctor` already
  uses (`verify_install` + capability/integration/routine sections) — same output, new entry
  point, no behavior change.
- A small, idempotent PATH-registration mechanism (`$CLAUDE_CONFIG_DIR/groundwork/env`,
  sourced from the user's existing shell rc file(s)) so `groundwork --help` works from a normal
  terminal after installation, without requiring the user to know or type any installed path.
  Mirrors the exact pattern already used by well-known installers (`uv`, `rustup`) — evidence in
  `design.md` DECISION 2, not invented.
- `install.sh` gains the steps to install the `groundwork` executable and register the PATH
  helper; `uninstall.sh` gains the symmetric removal.
- Tests (deterministic, no `claude` subprocess needed for `--help`/`version`; `doctor` tested the
  same way `setup.sh --doctor` is already tested) and documentation updates (README.md gains
  `groundwork` as the documented entry point alongside, not instead of, the existing direct
  script/flag invocations audited in DECISION 1 — none of which stop working).

## Non-Goals (explicitly out of scope for this change)

Per the Next Release Program's own phase boundaries and exclusion list:

- `groundwork integrations *`, `groundwork routines *` subtrees — Phase 2 / Phase 4.
- `groundwork update` / `groundwork update --check` / `groundwork update --version` /
  `groundwork rollback` — Phase 3 (version/update lifecycle requires its own design gate).
- Any command not already backed by real, existing Groundwork functionality (no `groundwork
  integrations install`, no arbitrary MCP installer, no credential manager).
- Terminal Copilot, voice control, custom Groundwork theme, Integration Usage analytics, MCP/CLI
  call counters, a read/write usage dashboard, Task Observer, a live activity dashboard, GitHub
  release automation, semantic-release, a package registry, Nerd Font requirement, terminal-
  specific themes, unrelated refactors.
- Rewriting any existing script's internal logic. `groundwork doctor`/`version` dispatch to
  existing, already-tested code; they do not reimplement it.
- git-autonomy / protected-branch-guard changes (§12 of the program) — evaluated separately in
  `design.md` DECISION 3 as USE EXISTING CAPABILITY, requiring no code change in this phase.

## Acceptance Criteria (Phase 1 gate — Phase 2 does not begin until these hold)

1. `groundwork --help` works from a normal terminal after a real `install.sh` run, without
   invoking any source-tree script by path.
2. `groundwork version` and `groundwork doctor` produce output that matches (for `doctor`,
   identical to) the existing `./setup.sh --verify` / `./setup.sh --doctor` output, proving no
   behavior drift.
3. Every hard-compatibility path the audit identified (hook/statusLine literal paths in
   settings.json, launchd plist `ProgramArguments` for `groundwork_report.py`/
   `groundwork_routines.py`) is unchanged and independently re-verified after this change.
4. `install.sh` → `groundwork --help`/`version`/`doctor` → `uninstall.sh` → the PATH
   registration and the `groundwork` executable are both cleanly removed, real end-to-end, in a
   disposable test `$CLAUDE_CONFIG_DIR`.
5. Full deterministic test suite green; `openspec validate --strict` clean; independent
   fresh-context review with 0 remaining MUST FIX.
