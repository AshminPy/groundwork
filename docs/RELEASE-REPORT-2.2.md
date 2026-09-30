# Groundwork 2.2.0 — release report

**Release version**: 2.2.0
**Release date**: 2026-09-30
**Release baseline**: `main` at `08f5cc6` (merge of PR #27), the validated state immediately before the release branch (`release/2.2.0`) was cut. This is Groundwork's **first formal, tagged GitHub release** — no prior version (1.0.0 through 2.1.0) was ever tagged or published as a GitHub Release; all prior history exists only in `CHANGELOG.md`.

---

## 1. Major capabilities

Two new, purely additive capabilities, both merged to `main` before this release was cut:

| Capability | Merged via | Merge commit |
|---|---|---|
| Integration Catalog | PR [#23](https://github.com/AshminPy/groundwork/pull/23) (implementation), [#24](https://github.com/AshminPy/groundwork/pull/24) (tasks complete), [#25](https://github.com/AshminPy/groundwork/pull/25) (OpenSpec archive) | `5577090`, `88eb002`, `6d2e90f` |
| statusLine | PR [#26](https://github.com/AshminPy/groundwork/pull/26) (implementation), [#27](https://github.com/AshminPy/groundwork/pull/27) (OpenSpec archive) | `577dc7e`, `08f5cc6` |

Neither capability removed, renamed, or changed the behavior of anything that existed before it. Both are opt-in in the sense that they add new files, a new optional CLI, and a new optional Claude Code `statusLine` integration point — an existing installation gains them automatically on upgrade, but nothing existing stops working or behaves differently.

## 2. Integration Catalog summary

`scripts/groundwork_integrations.py` is a structured, code-defined catalog of the external-system integrations documented in `docs/INTEGRATIONS.md` (GitHub, Jira, Confluence, AWS, GCP, Kubernetes, Terraform, Spacelift, and five observability tools). For each, it records capability ids and approved access mechanism(s) (`mcp`/`cli`/`api`), and reports three **independent** truthful readiness observations rather than a single collapsed status:

- **`available`** — the access mechanism is present on this machine
- **`configured`** — non-secret Groundwork configuration (`config.json`) references it
- **`connected`** — a real reachability/auth check actually ran and succeeded (today, only the GitHub `gh` CLI mechanism has one, and it requires the command's own explicit success confirmation, not exit code alone — this was verified against a real environment where `gh auth status` exits 0 on a failed login)

A separate, independent `used` observation is read from existing telemetry (never new tracking). A single display-only summary label (`CONNECTED` > `CONFIGURED` > `AVAILABLE` > `NOT CONFIGURED`) is derived for `list`/`show`'s concise output, but is never itself the stored truth — any combination of the three booleans is preserved rather than forced into a lifecycle. `groundwork_integrations.py list`/`show NAME` are read-only CLI commands, folded into `./setup.sh --doctor`. The catalog installs nothing and stores no credentials for any integration; it builds no MCP tool-loading/activation engine of its own (Claude Code's native Tool Search already does that).

## 3. statusLine summary

`scripts/groundwork_statusline.py` is a Claude Code `statusLine` command rendering Groundwork-specific state. Every displayed field is classified as exactly one of four kinds — see "truthful state semantics" below. The Integration Catalog cache that backs its integration-readiness display is refreshed only at existing lifecycle points (`install.sh`, `setup.sh` after capability configuration, `setup.sh --doctor`) — never on a timer, cron, or launchd schedule. Personalization (compact/detailed, per-section show/hide, plain-text-vs-Unicode) lives in a new standalone file, `~/.claude/groundwork/statusline-config.json`, kept out of `config.json` because `groundwork_config.py init --force` unconditionally rewrites that file on every `--configure` and would silently discard personalization stored there.

## 4. Truthful state semantics (the data-source contract)

Every field the statusLine can display is classified as exactly one of:

- **LIVE** — supplied directly by Claude Code's own stdin JSON, or computed fresh each render by one short-timeout `git status --porcelain --branch` call.
- **LAST-COMPLETED-TURN** — read from the existing telemetry log, filtered to the *current* session's own `session_id` only — never another session's most recent record. Rendered with a leading `~` so it is never mistaken for the in-progress turn.
- **CACHED** — capability profile, installed version, and Integration Catalog readiness, read from a cache file the statusLine itself never writes or probes. Every cached integration reading visibly shows its observation age (e.g. `GitHub ● · 4m`), even while still fresh, so CACHED is never mistaken for LIVE; a stale entry (≥15 min) additionally gets a leading `!` on the age.
- **UNAVAILABLE, never displayed** — review/MUST-FIX state, role/persona, evidence-label counts. No durable source exists for any of these anywhere in Groundwork today, and none is guessed.

The statusLine process itself never runs `claude mcp list`, `gh auth status`, or any other integration/network probe.

## 5. Test result

```
$ python3 -m pytest tests -q
77 passed in ~76s

$ python3 tests/test_groundwork_integrations.py
135 passed, 0 failed

$ python3 tests/test_groundwork_statusline.py
57 passed, 0 failed
```

The `test_groundwork_statusline.py` count is corrected here from the `49` figure that shipped in the `Unreleased`-section CHANGELOG text — that number predated two tests added during the pre-merge age-display fix and was never updated; `57` is the actual, freshly re-run count as of this release.

## 6. OpenSpec result

```
$ openspec validate --changes --strict
✓ change/groundwork-2-enterprise-sre
✓ change/groundwork-2.1-context-routines-ux
✓ change/intelligent-engineering-harness
Totals: 3 passed, 0 failed (3 items)
```

Both capabilities' OpenSpec changes are archived: `openspec/changes/archive/2026-09-30-add-integration-catalog/` and `openspec/changes/archive/2026-09-30-add-statusline/`, with their delta specs merged into `openspec/specs/`.

## 7. Runtime validation already performed

Performed live against the actually-installed scripts in this sandbox, not simulated:

- Fresh install and upgrade install, both producing a correctly populated `~/.claude/groundwork/integrations/cache.json` and installed `statusLine` script.
- An existing user-configured `statusLine` value, and an unrelated `settings.json` key, both confirmed untouched by a reinstall (`merge_settings.py`'s additive-only behavior).
- Compact and detailed statusLine rendering, both Unicode and plain-text modes.
- Session isolation: two synthetic telemetry records under different `session_id`s, each resolving only to its own last-completed-turn state.
- Fresh vs. stale Integration Catalog cache entries, both visibly distinguishable in the rendered output.
- Missing-cache and malformed-cache inputs, both failing safe (no invented readiness).
- Exactly one `subprocess.run` call present in `groundwork_statusline.py` (the bounded-timeout `git` call) — confirmed by direct inspection.
- Measured end-to-end execution time of the installed statusLine script, real subprocess-timed runs in this sandbox: averages in the **~45–58ms** range across multiple independent measurement rounds this session, including one from the release-delta reviewer's own independent 10-run measurement (58.2ms average, range 50.2–67.1ms). This is a measurement from this validation environment, not a universal performance guarantee — actual latency on a different machine, OS, or disk will differ.

## 8. Known limitations

- `uninstall.sh` doesn't explicitly clean up `~/.claude/groundwork/statusline-config.json` or the `integrations/` cache directory.
- The Integration Catalog cache can be stale for hours or days if a user never runs `--doctor`/`--configure`/`refresh` — this is accepted, and made visible to the user via the cache's own `checked_at` age display, rather than hidden.
- `~/.claude/groundwork/VERSION` reflects the latest numbered CHANGELOG heading at install time — a user who installs between releases sees the previous release's version number until the next numbered heading exists. This is expected Keep-a-Changelog-style behavior, not a defect.
- The Integration Catalog's `connected` observation has a real reachability check for only one mechanism (GitHub's `gh` CLI) today; every other integration's `connected` value is always `false` until a similar check is added for it.

## 9. Deliberately excluded work

- **Integration Usage Telemetry** (a per-invocation domain/mechanism/capability/read-write/success-failure dashboard) was investigated, not built. Current findings: Groundwork registers no `PostToolUse`/`PostToolUseFailure` hook today (Claude Code itself supports both; Groundwork simply doesn't consume them yet), so per-invocation success/failure is never captured; read/write classification has no platform-provided field anywhere; domain attribution works reliably for MCP-named tools and only through an explicitly maintained, narrow allowlist for Bash-invoked CLIs. No counters, fake zeros, or inferred metrics were added anywhere in this release.
- No new hooks, no new database, no scheduled/cron/launchd process for any part of either capability.

## 10. Compatibility statement

Backward-compatible feature release. No existing file, CLI flag, hook, or default behavior was removed or changed. An existing user-configured Claude Code `statusLine` is preserved untouched (`merge_settings.py` sets the key only if entirely absent). The existing installation workflow (`git clone` + `./setup.sh`) remains unchanged and fully supported; both new capabilities install automatically as part of the same `install.sh` run, with no new required prerequisite.

## 11. Installation behavior

`install.sh`/`setup.sh` have no dependency on any git tag or branch — they operate on whatever is currently checked out locally, exactly as before this release. Publishing the `v2.2.0` tag and GitHub Release does not change how installation is performed; it only gives users and tooling a stable, citable reference point for "the code as of 2.2.0," which did not exist for any prior version.

## 12. Release/tag information

- **Tag**: `v2.2.0`, annotated, created on the exact verified `main` commit that carries this release's metadata (CHANGELOG/README/ARCHITECTURE/this report), after that commit passed the full test suite and `openspec validate --changes --strict` a final time.
- **GitHub Release**: "Groundwork 2.2.0 — Integration Catalog & statusLine", created from the `v2.2.0` tag, not a draft, not a prerelease.
- **This is Groundwork's first formal release.** No prior version was tagged or published; a stray local-only `v2.1.0` tag (created after the fact, never pushed to `origin`, referencing commit `069fb44`) was independently re-verified as unpublished anywhere (no remote tag, no GitHub Release, no install/release mechanism depending on it) and deleted before this tag was created, so it does not collide with or precede `v2.2.0`.
- **Release process convention established by this release** (see `rules/` for Groundwork's engineering-workflow governance; this is the release-specific addition): validated `main` → release metadata PR (CHANGELOG boundary move, README/ARCHITECTURE version-label corrections, this report) → independent review of the release delta only → merge → final exact-commit re-validation (tests + OpenSpec + fresh-install VERSION check) → annotated tag on that exact commit → push the tag → GitHub Release from the tag. No release automation, no GitHub Actions release workflow, no package publishing, and no signing infrastructure were introduced — none is justified by a single release; this can be automated later if repeated releases show it's worth it.

---

*Every figure in this report was re-verified by running the underlying command during this release (§5–§7), not recalled from memory or copied from the `Unreleased` CHANGELOG text without checking — the one place that text was found stale (§5's test count) was corrected before this report was written.*
