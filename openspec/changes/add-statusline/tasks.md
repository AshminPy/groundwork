# Tasks

## 1. Integration Catalog cache (lifecycle-driven, no scheduler)

- [x] 1.1 Add a `refresh` subcommand to `scripts/groundwork_integrations.py`: runs the same `determine_observation()` every entry already uses, then atomically writes `~/.claude/groundwork/integrations/cache.json` (temp file + `os.replace`), one entry per integration, each with its own `checked_at` (UTC ISO 8601). Prints the same table `list` already prints (byte-identical visible behavior at the CLI), so replacing a `list` call with `refresh` anywhere changes no visible output.
- [x] 1.2 Add tests: `refresh` writes a well-formed cache file with `checked_at` on every entry; the cache write is atomic (no partial file ever readable mid-write, verified by patching `os.replace`/interrupting and checking the original file is untouched); a malformed/missing cache file is read back as "no readiness data," never a crash, by the reader added in task 3.

## 2. Wire `refresh` into existing lifecycle points only

- [x] 2.1 `install.sh`: after installing `groundwork_integrations.py`, call `refresh` once, best-effort (failure/timeout must not fail the install).
- [x] 2.2 `setup.sh`'s `apply_capabilities()`: call `refresh` after `$CONFIG_PY init` writes `config.json` (covers both initial setup and `--configure`).
- [x] 2.3 `setup.sh --doctor`'s two existing "Integrations" sections (with and without `config.json` present): change their `groundwork_integrations.py list` call to `refresh` — output stays identical (task 1.1), cache is now also persisted as a side effect.
- [x] 2.4 Verify no other lifecycle point (SessionStart, a new scheduled job) was added — grep the diff for `cron`, `launchd`, `at `, `nohup`, `setsid`, `daemon` and confirm zero matches outside comments explaining why they were *not* used.

## 3. `scripts/groundwork_statusline.py`

- [x] 3.1 Parse the stdin JSON; extract model/context-window/cost/workspace/`session_id` fields defensively (missing/malformed stdin degrades to omitting those fields, never a crash or non-zero exit).
- [x] 3.2 Read `config.json` for the capability profile (CACHED); read `~/.claude/groundwork/integrations/cache.json` for Integration Catalog readiness (CACHED, never a live probe) with each entry's `checked_at` surfaced for staleness display; read `~/.claude/groundwork/VERSION` (CACHED) and display it as-is, unmodified, per design.md Decision 5.
- [x] 3.3 Implement the bounded backward-scan reader for `events.jsonl`: find the most recent record whose `session_id` matches the current session's, within a fixed, documented byte/line bound; return LAST-COMPLETED-TURN playbook/execution-mode/validation(`observed.tests_run`) fields, or none if no match is found within the bound.
- [x] 3.4 Implement one short-timeout `git` subprocess call (branch name + dirty/clean via `git status --porcelain`), scoped to the stdin JSON's own working directory; timeout or failure omits this field rather than blocking.
- [x] 3.5 Implement rendering: compact and detailed modes, per-section show/hide, Unicode-symbol and plain-text variants, and the documented last-turn/cached visual convention (e.g. a distinct marker for non-live fields; visible cache age for integrations). Read personalization from `~/.claude/groundwork/statusline-config.json`, defined safe defaults if absent/malformed.
- [x] 3.6 `main()` never raises and never exits non-zero for a rendering problem — worst case, print a minimal fallback line (e.g. just `GROUNDWORK`) rather than going blank or crashing.

## 4. Tests — `tests/test_groundwork_statusline.py`

- [x] 4.1 Rendering: compact, detailed, plain-text, and integrations-section-hidden variants each produce the expected, documented output shape.
- [x] 4.2 Missing integrations cache → no readiness shown, no crash. Stale cache (old `checked_at`) → age is visibly surfaced.
- [x] 4.3 Missing/empty telemetry → last-completed-turn fields omitted, no crash.
- [x] 4.4 Two distinct `session_id` values against the same synthetic `events.jsonl` (interleaved records) each resolve to only their own most recent record — deterministic proof of no cross-session leakage.
- [x] 4.5 Malformed `config.json` / `statusline-config.json` / integrations cache each fail safe to documented defaults, never a crash, never a non-zero exit.
- [x] 4.6 A fast `git` stub (clean and dirty branch states) and a timing-out/missing `git` stub — the latter omits the field rather than hanging or crashing.
- [x] 4.7 Full stdin-to-stdout smoke test with a realistic synthetic stdin JSON payload, asserting the rendered line(s) contain only fields the data-source contract permits.

## 5. Installation and settings integration

- [x] 5.1 `install.sh`: install `groundwork_statusline.py` alongside the other scripts (`chmod +x`, matching the existing pattern).
- [x] 5.2 `scripts/merge_settings.py`: add an additive `statusLine` merge rule — set only if the key is entirely absent from the user's `settings.json`; add a test proving an existing user `statusLine` value is left untouched by a merge.

## 6. Documentation

- [x] 6.1 `docs/ARCHITECTURE.md`: add a short section/row documenting the statusLine capability, its data-source contract, and that Integration Catalog readiness is cache-only there.
- [x] 6.2 `README.md`: repository-layout entries for the two new files.
- [x] 6.3 `CHANGELOG.md`: an entry describing the statusLine capability, its lifecycle-driven (not scheduled) cache refresh, and the explicit exclusion of Integration Usage Telemetry pending a separate future investigation.

## 7. Full validation

- [x] 7.1 `python3 -m pytest tests -q` — no regressions.
- [x] 7.2 `openspec validate add-statusline --strict`.
- [x] 7.3 Measure actual statusLine execution time (e.g. `time python3 scripts/groundwork_statusline.py < fixture.json`) across at least: warm cache, missing cache, missing telemetry, large synthetic telemetry file — record real numbers, not an estimate.
- [x] 7.4 Runtime validation: fresh install into a clean `CLAUDE_CONFIG_DIR`; upgrade install over an existing Groundwork setup (confirm unrelated existing `settings.json` entries are preserved); compact/detailed/plain-text rendering against real stdin-shaped JSON; dirty and clean real git states; two distinct synthetic `session_id`s against one real telemetry file.
- [x] 7.5 Dispatch an independent, fresh-context review against this OpenSpec change; fix only findings it reports as material (MUST FIX), and re-run affected validation after each fix.
