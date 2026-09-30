# Proposal — Groundwork version/update lifecycle (Next Release Program, Phase 3)

## Why

Phases 1–2 gave Groundwork a single discoverable entry point (`groundwork --help`/`version`/
`doctor`/`integrations`). There is still no supported way for an installed Groundwork to check
whether a newer release exists, or to move itself to one — the only documented path today is
`git pull && ./setup.sh` from a repo clone (`docs/UPGRADE-ROLLBACK.md`), which requires the user to
already have a clone and to know that workflow exists. Groundwork's own install model (a single
`install.sh`/`setup.sh` copied into `$CLAUDE_CONFIG_DIR/groundwork/bin/`) has no self-update path
at all from an installed-only location.

### Product Value Gate (concise)

| Command | Decision | Why |
|---|---|---|
| `groundwork version` | USE EXISTING CAPABILITY | Already implemented in Phase 1 (`groundwork_cli.py::cmd_version`), reads the authoritative installed `VERSION` file. No change needed. |
| `groundwork update --check` | BUILD | Real, common need (know if an update exists) with zero mutation risk; the GitHub Releases API is confirmed reachable and already the authoritative source for Groundwork's own tagged releases. |
| `groundwork update` | BUILD REDUCED SCOPE | Real need, but only as thin orchestration over the *existing* `setup.sh`/`install.sh` — fetch the target release's source tree, then hand off to its own unmodified installer. No new installer logic. |
| `groundwork update --version VERSION` | BUILD REDUCED SCOPE | Same mechanism as plain `update`, gated to a specific published release rather than "latest" — needed for downgrading past a bad release or pinning, and it's the same code path with one extra validation step, not separate scope. |
| `groundwork rollback` | BUILD | `setup.sh --rollback`/`make_backup()` already exist, already run before every `setup.sh` invocation, and are already self-contained against `$CLAUDE_DIR` (confirmed by reading `run_rollback`/`latest_backup` directly — no `$HERE`-relative reference). `groundwork rollback` only needs to dispatch to what already exists. |
| `groundwork rollback --version VERSION` | BUILD REDUCED SCOPE | `setup.sh`'s own `make_backup()` already records `groundwork_version_before=<VERSION>` in every backup's `BACKUP-INFO.txt` — version-labeled rollback is a lookup against data that already exists, not new versioning infrastructure. |

No command in this set required DEFER or DO NOT BUILD: every one maps either to an existing,
already-safe mechanism (`version`, `rollback`) or to thin orchestration over one (`update`,
`update --check`, `update --version`, `rollback --version`) with no new installer logic and no new
persistent state beyond what `setup.sh` already writes.

## What Changes

- A new `scripts/groundwork_update.py`, installed to
  `$CLAUDE_CONFIG_DIR/groundwork/bin/groundwork_update.py`, implementing:
  - `update --check` — non-mutating. Prints `Current: X` / `Latest: Y` / whether an update is
    available, using the GitHub Releases API (`/releases/latest`) as the sole authoritative source
    — never `origin/main`, a branch, a draft, a prerelease, or an arbitrary commit.
  - `update` — installs the latest published, non-draft, non-prerelease release: downloads its
    source tarball (`urllib`/`tarfile`, stdlib only — no `git clone` dependency), validates it
    (required files present, `CHANGELOG.md`'s top entry matches the requested tag), then invokes
    *that fetched tree's own, unmodified* `setup.sh --non-interactive`. The installation's current
    profile, report schedule, and Agent-Teams setting are read *before* the update and re-passed
    explicitly, closing a real gap in `setup.sh`'s own non-interactive mode (`choose_schedule()`
    silently resets to `weekly` with no `--schedule` flag — confirmed by reading the function
    directly).
  - `update --version VERSION` — same mechanism, targeting one specific published release;
    rejects anything that is not a real, published, non-draft, non-prerelease release.
  - `rollback` — dispatches to the *installed* `setup.sh --rollback` (confirmed self-contained
    against `$CLAUDE_DIR`, same as `doctor`'s existing dispatch precedent).
  - `rollback --version VERSION` — resolves the specific backup directory whose
    `BACKUP-INFO.txt` records `groundwork_version_before=VERSION` (a field `make_backup()` already
    writes on every `setup.sh` run), then dispatches to `setup.sh --rollback <dir>`.
- `groundwork_cli.py` gains `update`/`rollback` as pure pass-through dispatches to the installed
  `groundwork_update.py`, the same `argv[0]` interception pattern already established for
  `integrations` in Phase 2 (works around the `argparse.REMAINDER` + `-h` interception limitation,
  https://bugs.python.org/issue9334).
- `install.sh` copies `scripts/groundwork_update.py` into the installed bin directory.
- Tests: `tests/test_groundwork_update.py` (new — semver parsing, release-API validation,
  path-traversal-safe extraction, backup lookup, preservation logic, and full update/rollback
  orchestration against stub installers); `tests/test_groundwork_cli.py` gains a dispatch-fidelity
  test for `update`/`rollback`.
- Docs: `docs/UPGRADE-ROLLBACK.md` and `README.md` updated to document `groundwork update`/
  `rollback` as the preferred interface, alongside the existing `git pull && ./setup.sh` workflow
  (which stays valid, unchanged).

## Non-Goals (explicitly out of scope for this change)

- No second installer and no duplicated installer logic — `update` always ends by invoking the
  fetched tree's own `setup.sh`; it never re-implements any install step itself.
- No credential storage of any kind (GitHub, Claude, AWS, MCP, or otherwise) — the GitHub Releases
  API is called unauthenticated, exactly as Groundwork's own release-verification workflow
  (`docs/RELEASE-REPORT-2.2.md`) already does for a public repository.
- No acceptance of an arbitrary ref as a "version" — `git` branches, commit SHAs, tags without a
  matching published, non-draft, non-prerelease GitHub Release are all rejected before any file is
  fetched or any installer is invoked.
- No bypass of repository/tag/release protections, and no `sudo` — `update` always passes
  `--no-install-prereqs` to the fetched `setup.sh`; a missing hard prerequisite is reported and
  left for the user exactly as `setup.sh` already does unassisted.
- No new rollback/versioning infrastructure — `rollback --version` is a lookup against
  `BACKUP-INFO.txt` data `make_backup()` already writes; no new backup format, no new metadata
  store.
- `groundwork routines *` — a later phase, untouched by this change.

## Known Material Limitation

Groundwork's `v2.2.0` tag is confirmed (via the GitHub Releases API, live) to be the *only*
published, non-draft, non-prerelease release that exists for this repository at the time of this
change. A true "previous published release → next published release" upgrade scenario therefore
cannot be validated end-to-end against two real releases; validation instead proves the update
*mechanism* (fetch, validate, preserve, invoke, verify) against a controlled stub installer plus a
real, live `update --check`/`find_release` call against the one real release that exists. This is
disclosed here rather than glossed over, per this program's evidence-first requirement — see
`design.md` DECISION 5.

## Acceptance Criteria (Phase 3 gate)

1. `groundwork version` is unchanged (still reads the authoritative installed `VERSION` file;
   no redesign, since no defect was found in it).
2. `groundwork update --check` never mutates installed state, reports `Current`/`Latest`/whether an
   update is available, and reports `UNKNOWN` (never a guess) when the release API is unreachable
   or the installed/remote version string doesn't parse as semver.
3. `groundwork update` and `groundwork update --version VERSION` only ever install a real,
   published, non-draft, non-prerelease GitHub Release — never `origin/main`, a branch, or an
   arbitrary commit — and always invoke the fetched tree's own, unmodified installer rather than
   reimplementing install logic.
4. A non-interactive `update` explicitly preserves the installation's current profile, report
   schedule, and Agent-Teams setting rather than trusting `setup.sh`'s own interactive-mode
   defaults (closing the confirmed `choose_schedule()` reset-to-`weekly` gap).
5. `groundwork rollback` and `groundwork rollback --version VERSION` dispatch to the existing,
   already-safe `setup.sh --rollback` mechanism — no new backup/restore logic is introduced.
6. A path-traversal/"zip-slip" archive member is rejected before extraction.
7. No credential of any kind is stored or required; no `sudo` is invoked; no OS package is
   installed by this code.
8. Full test suite green; `openspec validate groundwork-update-lifecycle --strict` valid;
   independent fresh-context review with 0 MUST FIX remaining.
