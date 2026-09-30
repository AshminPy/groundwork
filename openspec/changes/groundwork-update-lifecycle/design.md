# Design — Groundwork version/update lifecycle (Next Release Program, Phase 3)

## Architecture-quality §2 answers (MATERIAL tier: mutates the installation, fetches external code)

- **What is likely to change?** Which release is "latest" changes with every tag; the design reads
  that live from the GitHub Releases API rather than hard-coding a version anywhere.
- **What should be configuration rather than code?** Nothing new is introduced as config — the
  installation's existing `settings.json` (profile, Agent-Teams) and `report.json` (schedule) are
  read, not duplicated into a second store.
- **What needs a stable interface?** `groundwork update [--check|--version X]` /
  `groundwork rollback [--version X]` — the contract is "installs/restores a real, whole
  installation," not any internal mechanism, so the fetch-then-invoke-installer approach can change
  later without breaking the interface.
- **How would another instance/provider/environment be added?** Not applicable — there is exactly
  one release source (this repository's own GitHub Releases) and no evidence of a second one.
- **Which manual operational steps can reasonably be automated?** The `git pull && ./setup.sh`
  workflow itself — that is the entire point of this change.
- **What fails if a dependency is unavailable, and how is that failure handled/surfaced?** GitHub
  API unreachable → `--check` reports `UNKNOWN` (never a guessed answer); `update` reports the
  clean HTTP/network error and performs no mutation. Download failure → reported, no mutation
  (nothing was extracted yet). Extraction failure → reported, no mutation. Installer failure →
  reported with the pre-existing backup's location and a pointer to `groundwork rollback` (the
  backup was already taken by `setup.sh`'s own `make_backup()` before it made any change).
- **How will an operator observe/troubleshoot this?** `update --check` prints machine-clear
  `Current`/`Latest`/`Update available` lines; `update` prints the archive being fetched, the
  target version, and passes through the fetched `setup.sh`'s own stdout/stderr live (not
  captured/hidden) so its existing `--doctor`-verifiable state is visible exactly as it already is
  for a manual `./setup.sh` run.
- **How will it be tested? Deployed/rolled back?** Deterministic tests with the GitHub API and the
  installer both stubbed (`tests/test_groundwork_update.py`); deployed via the existing
  `install.sh` (one new copy step); rolled back via the pre-existing `setup.sh --rollback`.
- **What security boundary exists?** No credential of any kind; the GitHub Releases API is called
  unauthenticated (public repo, same as the existing release-verification workflow); no ref other
  than a real, published, non-draft, non-prerelease release tag is ever accepted; a fetched
  archive's members are validated against path traversal before extraction; `--no-install-prereqs`
  is always passed so no OS package is ever installed by this code, and no `sudo` is invoked.
- **Scaling/cost implications?** One unauthenticated GitHub API call per `--check`/`update`
  invocation, run by the user on demand — no scheduled polling, no added load.

## Product Value Gate

See `proposal.md`'s "Product Value Gate (concise)" table — reproduced there rather than here since
it belongs with the "Why."

## DECISION 1 — Fetch the target release's source via its GitHub-generated tarball (`urllib` +
`tarfile`, stdlib only), not `git clone`

EVIDENCE: `git clone`/`rsync`/`find -exec cp -r`-shaped commands were denied outright by this
session's own permission system while investigating the fetch mechanism (not a design choice —
observed directly). Live-tested the alternative: `urllib.request.urlopen()` against a GitHub
Release's own `tarball_url` (the same field the Releases API already returns,
`https://api.github.com/repos/AshminPy/groundwork/releases/latest` → `.tarball_url`) succeeds with
no credentials for this public repository, and `tarfile.open(fileobj=io.BytesIO(data),
mode="r:gz")` extracts it cleanly into a single top-level directory
(`AshminPy-groundwork-<short-sha>/`) containing `install.sh`/`setup.sh`/`CHANGELOG.md` —
live-verified, not assumed.

WHY: stdlib-only (`urllib`, `tarfile`) matches every other Groundwork script's zero-new-dependency
footprint; requires no `git` binary on the installed machine at all (an installed-only Groundwork,
by definition, may not have a clone of the repo, and may not have `git` configured with any
particular remote). A tarball download is also strictly less capable than a clone (no arbitrary
ref, no history, no `.git` directory reachable) — which is a security property, not a limitation:
it structurally cannot be pointed at an unpublished branch or commit, only at whatever
`tarball_url` a real Release object supplies.

TRADEOFFS: no incremental fetch (a full tree download every `update` run, same as any clean
install); acceptable, since Groundwork's own source tree is small and this only runs on explicit
user action, never on a schedule.

VALIDATION METHOD: live-reproduced the `git clone` denial before pivoting (not assumed);
live-verified the tarball fetch+extract path against the real GitHub API;
`tests/test_groundwork_update.py::test_update_end_to_end_preserves_schedule_profile_teams` and
its siblings exercise the full fetch→extract→validate→invoke pipeline deterministically with the
network stubbed.

UNCERTAINTY: none material.

## DECISION 2 — `update` always ends by invoking the *fetched* tree's own, unmodified `setup.sh`;
it never reimplements any install step

EVIDENCE: `setup.sh`'s `run_setup()` already performs the complete, already-tested install sequence
(backup via `make_backup()`, file sync, `merge_settings.py`, capability/profile application,
routine/statusline wiring) — re-reading and reimplementing any piece of that inside
`groundwork_update.py` would be exactly the "duplicated installer logic" the Phase 3 instructions
explicitly forbid, and would create a second place those steps could silently drift out of sync.

WHY: the smallest design that satisfies "update Groundwork to a newer release" is "run the
installer that release ships, the same way a user manually running `git pull && ./setup.sh` would
have" — `groundwork update` automates exactly that manual workflow, it does not replace it with a
new one.

TRADEOFFS: `update`'s own code has no fine-grained control over individual install steps (it
cannot, say, update only `groundwork_cli.py` and skip everything else) — acceptable, since nothing
in this program's requirements asked for partial/selective updates, and a whole-installer run is
also the only way to guarantee the installed tree is internally consistent (Groundwork 2.1's
`choose_capabilities()`/`choose_schedule()` steps are interdependent; running them individually
would risk exactly the kind of half-applied state this design avoids).

VALIDATION METHOD: `test_update_end_to_end_preserves_schedule_profile_teams` proves the fetched
`setup.sh` is actually invoked (not bypassed) with the expected flags; `install.sh`/`setup.sh`
themselves are completely unmodified by this change (confirmed by diff — this change touches
`scripts/groundwork_update.py`, `scripts/groundwork_cli.py`, and one `install.sh` copy-step
addition only).

UNCERTAINTY: none material.

## DECISION 3 — Explicitly re-read and re-pass the current profile/schedule/Agent-Teams settings to
the fetched `setup.sh --non-interactive`, rather than trusting its own non-interactive defaults

EVIDENCE: Read `setup.sh`'s `choose_schedule()`/`choose_profile()`/`choose_capabilities()`
directly. `choose_schedule()` (lines 304–316 at the time of this investigation) hard-codes
`SCHEDULE=weekly` when `NONINT=1` and no `--schedule` flag is given — a naive
`setup.sh --non-interactive` call would silently reset a user's custom reporting schedule back to
weekly. By contrast, `choose_profile()`/`choose_capabilities()` correctly leave
`PROFILE`/`CAP_PROFILE` empty when not explicitly passed, which *correctly* preserves the existing
`settings.json` profile and `config.json` capabilities by omission (skipping
`merge_settings.py --profile`/`apply_capabilities()` entirely rather than overwriting with a
default).

WHY: this asymmetry means `groundwork_update.py` must explicitly read and re-pass the *current*
schedule (never trust the non-interactive default) but must *never* unconditionally pass
`--profile`/`--capability-profile` — passing an empty/guessed value would override the correct
existing omission-based preservation with a wrong one. `_read_current_profile()` returns `None`
when unset, and `cmd_update` only adds `--profile` to `setup_args` when that value is truthy,
matching `choose_profile()`'s own correct-by-omission behavior; `--schedule` is always passed
explicitly since that is the one flag whose omission is unsafe.

TRADEOFFS: this couples `groundwork_update.py` to `setup.sh`'s current flag names and
non-interactive-mode defaults — if `setup.sh` changes those, `groundwork_update.py` needs a
matching update. Accepted: the alternative (blindly trusting `setup.sh --non-interactive` with no
flags) was confirmed live to silently corrupt user state.

VALIDATION METHOD: `test_update_end_to_end_preserves_schedule_profile_teams` (schedule set to
`monthly`, profile to `fullstack`, Agent-Teams on — asserts all three reach the invoked `setup.sh`
verbatim) and `test_update_declines_profile_flag_when_none_set` (no profile ever configured →
`--profile` is never passed, proving the omission path isn't broken by this change either).

UNCERTAINTY: none material.

## DECISION 4 — `rollback --version VERSION` is a lookup against `BACKUP-INFO.txt`'s existing
`groundwork_version_before=` field, not new versioning infrastructure

EVIDENCE: `setup.sh`'s `make_backup()` (called by `run_setup()` before every install) already
writes a full `$CLAUDE_DIR` snapshot per run, with `BACKUP-INFO.txt` recording
`groundwork_version_before=<VERSION>` — the version that snapshot's *content* actually is, written
unconditionally on every `setup.sh` run today, not introduced by this change.
`run_rollback()`/`latest_backup()` (which `setup.sh --rollback [DIR]` dispatches to) restore a
complete `$CLAUDE_DIR` from a given backup directory and were confirmed, by reading them directly,
to reference nothing `$HERE`-relative — the same property that already makes `--doctor` safe to
run from an installed copy (Phase 1 precedent).

WHY: as long as every `update` goes through DECISION 2's "always invoke the fetched setup.sh" path
(which always backs up first via the unmodified `make_backup()`), version-labeled rollback reduces
to "find the newest backup directory whose `BACKUP-INFO.txt` says it was taken right before version
X" — a small, new `_find_backup_for_version()` scan function, zero new backup format, zero new
metadata store, zero changes to `make_backup()`/`run_rollback()` themselves.

TRADEOFFS: rollback can only reach a version for which a backup still exists on disk (backups are
not pruned by this change, and were not pruned before it either — `setup.sh`'s existing behavior,
unchanged); a version installed, then updated past, then whose backup was manually deleted is not
recoverable. Accepted — proving guaranteed-available rollback to an arbitrary historical version
would require building real backup-retention/versioning infrastructure, which the Phase 3
instructions explicitly say to DEFER rather than overengineer ("If proving safe rollback requires
substantial migration/version-management architecture, DEFER it").

VALIDATION METHOD: `test_find_backup_for_version` (newest-match selection, no-match handling);
`test_rollback_dispatches_to_installed_setup_sh` (both bare `rollback` and `rollback --version`
dispatch correctly, and a `--version` with no matching backup refuses cleanly rather than silently
falling back to "latest").

UNCERTAINTY: rollback's *scope* is exactly what `setup.sh --rollback`'s existing full-`$CLAUDE_DIR`
restore already covers (Groundwork-owned files, settings.json merge state, config.json, hooks,
rules, scripts, statusLine — everything `make_backup()`'s `cp -Rp` snapshot includes). This change
adds no new compatibility checking beyond what the existing mechanism already does or doesn't do;
if a future release changes `$CLAUDE_DIR`'s schema in a way `setup.sh --rollback` itself cannot
safely reverse, that is a pre-existing property of the reused mechanism, not something this change
introduces or resolves.

## DECISION 5 — Validation scope given only one published release exists

EVIDENCE: `find_release`/`latest_release` called live against
`https://api.github.com/repos/AshminPy/groundwork/releases` during this change's own validation
confirmed exactly one published, non-draft, non-prerelease release (`v2.2.0`) exists for this
repository.

WHY: a true "install release N, then update to release N+1" scenario needs two real releases to
exist; only one does. Building a second throwaway release solely to test this would itself be a
production action (publishing a GitHub Release) outside this change's scope and authority.

TRADEOFFS: the update *mechanism* (fetch, safety checks, preservation, installer invocation,
post-verify) is validated end-to-end against a controlled stub installer standing in for a real
fetched `setup.sh` (proving the orchestration is correct) plus a real, live call to the actual
GitHub Releases API (proving `latest_release()`/`find_release()` work against real data) — but a
real two-release upgrade path (old Groundwork binary content → new Groundwork binary content) is
not exercised end-to-end in this validation pass.

VALIDATION METHOD: documented here and in the final report as a known material limitation, per this
program's evidence-first requirement, rather than silently assumed covered.

UNCERTAINTY: RUNTIME VALIDATION REQUIRED — a true N→N+1 upgrade will only be provable once a
second Groundwork release is actually published; this should be checked opportunistically the next
time Groundwork cuts a release, not blocked on here.
