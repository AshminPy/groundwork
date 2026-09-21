# Changelog

## 1.2.0 — 2026-09-21

Additive task-routing layer. No existing rule, hook, settings key or safety control changed
(verified by SHA-256 comparison of every pre-existing critical file before and after).

- **New rule `rules/task-routing.md`** — one primary category per request (RESEARCH, EXPLAIN,
  DESIGN, PLAN, IMPLEMENT, TROUBLESHOOT, VALIDATE, AUDIT, DEPLOY, DOCUMENT), read only that
  playbook, the material-ambiguity clarification rule, and the universal output contract
  (report only material information; conciseness never hides risk, uncertainty or evidence).
  States that an existing Groundwork rule wins over a playbook on conflict.
- **New `playbooks/`** — ten concise playbooks, each with Goal / Workflow / Evidence / Ask
  Before Acting When / Completion Criteria / Output Format. Installed to
  `~/.claude/groundwork/playbooks/`, outside `rules/`, so they load on demand only.
  IMPLEMENT and DEPLOY outputs embed the existing completion block.
- **Installer** — `install.sh` copies the playbooks; `uninstall.sh` removes them.
- **Tests** — `tests/test_playbooks.py` (artefacts, sections, size caps, install/uninstall on a
  temp `CLAUDE_CONFIG_DIR`); `scripts/check_routing.py` + `tests/routing_scenarios.json` for a
  live twelve-scenario routing and ambiguity check (skips when the CLI is logged out).

## 1.1.0 — 2026-09-20

Evolves the 1.0.0 governance layer into an engineering harness that guides architecture
quality, chooses its own execution model, validates against the real runtime, and
reconstructs an existing project from the repository in a fresh session. Verified
against Claude Code 2.1.258 and the official docs on 2026-09-20; ECC 2.2.1 and OpenSpec
1.12.0 unchanged. Nothing SRE-Agent-specific; no new agents, skills, daemons or stores.

- **New `rules/architecture-quality.md`** — governing principle ("smallest design that
  satisfies today's requirement while preserving low-cost paths for foreseeable change"),
  the quality dimensions as *decision criteria*, the pre-MATERIAL questions, the
  variation-point rule (configuration/interface boundary for environments, providers,
  clusters, models, regions, tenants), and "no abstraction without a concrete reason".
- **`rules/engineering-workflow.md`** — UNDERSTAND step producing a DONE / PARTIAL /
  MISSING / BLOCKED / UNVERIFIED state table for existing projects; §6 execution model
  (main session vs subagents vs native Agent Teams, with size/justification rules and the
  "teams disabled or `-p` → subagents" fallback); §7 continuation procedure for
  "continue this project"; `Reviewed:` row in the completion block; never default to
  `--dangerously-skip-permissions`.
- **`rules/evidence-policy.md`** — §5 validation ladder derived from project evidence
  (static → unit → integration → build → infra → controlled runtime → real environment),
  "mocks never prove runtime", the six-field DECISION record for MATERIAL decisions only,
  `Independent review` row in the completion-evidence table.
- **`hooks/require_material_review.py`** — also recognises reviewer-shaped `Agent`/`Task`
  calls by `name`, so Agent Team reviewer teammates and named reviewer subagents (current
  Claude Code spawns both through the `Agent` tool) satisfy the gate. The free-text
  `description` is deliberately not matched (independent review showed it could be
  satisfied by an unrelated "Review existing tests" exploration). Documents the platform's
  8-consecutive-block cap. Behaviour otherwise unchanged.
- **New `hooks/groundwork_session_snapshot.py`** (SessionStart) — deterministic project
  snapshot from repository state only: branch, HEAD, ahead/behind, dirty/untracked counts,
  recent commits, active OpenSpec changes with task progress (flagging complete +
  uncommitted changes where the review gate applies), project signal files, and
  verification commands discovered in Makefile / package.json / pyproject / tox / nox /
  Go / Rust / Terraform / CI files. ≤ 2,500 chars, 3 s git timeouts, no network,
  fail-open, `GROUNDWORK_SNAPSHOT=off` to disable.
- **Installer** — `merge_settings.py` registers the SessionStart hook idempotently and
  accepts `--agent-teams` (opt-in only, never overwrites a user value);
  `unmerge_settings.py` reverses it, now including the `hook_profile` it set (found by
  independent review: 1.0.0's uninstall left that key behind), and documents the one
  stateless limitation: a value you had set yourself that equals the installer's default
  is removed on unmerge; new
  `migrate_legacy_rules.py` moves a pre-Groundwork `~/.claude/rules/harness/` copy into
  `~/.claude/backups/groundwork-legacy-<timestamp>/` so rules are not loaded twice, and
  prints a notice when `~/.claude/CLAUDE.md` still points at the old path.
- **`hooks/block_protected_push.py`** — hardened after an independent security review
  reproduced four bypasses of the 1.0.0 guard: `HEAD`/`@` shorthand now resolves to the
  current branch, every refspec is checked (not just the first), `--all`/`--mirror`/
  `--branches` are denied, `sh/bash/zsh/dash/ksh -c "…"` and `eval "…"` are parsed
  (depth-limited), `:branch` deletions and `+`/`refs/heads/` forms are handled, and
  option values (`-o`, `--push-option`, …) are no longer mistaken for refspecs.
- **Snapshot prompt-injection mitigation** — repository-derived text (branch, commit
  subjects, directory/file names) is clipped per field, stripped of control/zero-width
  characters, and framed inside an explicit "DATA, NOT INSTRUCTIONS" boundary.
- **Review-gate correctness** — change names are matched as exact `openspec/changes/<name>`
  path segments (1.0.0 substring-matched raw `git status` text, so a committed `thing` was
  re-flagged whenever `add-thing` was dirty); "preview" no longer matches "review".
- **Tests** — 16 → 92 checks across 5 test functions, including a regression case for
  every reviewer-reproduced bypass; fixture commits are isolated from the developer's
  global git config; `check()` failures now raise, so `pytest` reports a real failure
  (in 1.0.0 a failing check still showed "passed").
- **Docs** — README, ARCHITECTURE, TROUBLESHOOTING, UPGRADE-ROLLBACK, VALIDATION updated.

## 1.0.0 — 2026-09-03

Initial release, extracted from a real personal-harness migration onto ECC 2.2.1 + OpenSpec 1.12.0.

- `rules/engineering-workflow.md` — TRIVIAL/STANDARD/MATERIAL tiering, autonomy rule (six genuine owner-decision triggers, nothing else stops the loop), completion status block.
- `rules/evidence-policy.md` — evidence priority order, uncertainty labels, the DECISION format for material technical calls, the completion-evidence table (code ≠ tested ≠ merged ≠ deployed ≠ live validated).
- `hooks/block_protected_push.py` — denies `git push` to `main`/`master`/`production`/`prod`/`release` and any force-push, shell-chain aware.
- `hooks/require_material_review.py` — denies finishing a session with a fully-implemented, uncommitted OpenSpec change that no reviewer-shaped tool call ever touched. Added after an initial gap: a plain autonomy rule alone let a real test run finish a material feature with zero review dispatched.
- `install.sh` / `uninstall.sh`, `scripts/merge_settings.py` / `unmerge_settings.py` — idempotent, additive-only `settings.json` handling; never overwrites unrelated configuration.

See [docs/VALIDATION.md](docs/VALIDATION.md) for the test evidence this release is based on, including the fixes that came out of live testing (a `git status` untracked-directory edge case in the review gate; the removal of a generic MATERIAL-tier approval stop that contradicted the autonomy rule).
