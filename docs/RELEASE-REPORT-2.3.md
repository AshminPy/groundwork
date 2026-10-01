# Groundwork 2.3.0 — release report

**Release version**: 2.3.0

**Release baseline**: `main` at the merge of PR #37 (`629f927`), the validated state after a
real-world certificate-verification bug report required re-cutting this release — see "Re-cut
notice" below.

**Scope**: derived from git history (`git log v2.2.0..main --oneline --merges`), not from
conversation memory — six merged pull requests: #29 (quiet interaction / routine readiness), #30
(`groundwork` CLI foundation), #32 (Integration Catalog CLI), #33 (version/update/rollback
lifecycle), #34 (Routines CLI), #37 (SSL cert-verification fallback for `groundwork update`). PR
#31 (three future-feature candidates, documentation only) was confirmed still open/unmerged via the
GitHub API and is correctly excluded from this release.

**Re-cut notice**: `v2.3.0` was originally tagged and published at the PR #34 merge commit
(`7a78f972`). A real user running the published release hit `SSL: CERTIFICATE_VERIFY_FAILED` in
`groundwork update --check` — confirmed as a genuine gap in `groundwork_update.py` (python.org's
macOS Python 3.14 installer ships with an empty default certificate trust store until its own
one-time setup step is run; the certificate itself was independently confirmed genuine, not
intercepted), not a defect in the reporting user's own setup. Fixed via PR #37, reviewed, merged.
Rather than publish a `v2.3.0` known to fail this real-world case and immediately need `v2.3.1`,
the original `v2.3.0` tag and GitHub Release were deleted and re-cut at the post-fix commit. Nothing
else changed between the two cuts.

## 1. Major capabilities and their user value

- **`groundwork` CLI foundation** — one discoverable command (`groundwork --help`/`version`/
  `doctor`) in place of needing to know which of several separate scripts, or which `setup.sh`
  flag, does what.
- **Integration Catalog via the CLI** — `groundwork integrations list/show NAME/doctor NAME/
  refresh`: see which external systems are available, configured, and actually connected, from one
  command, with `doctor NAME` explaining *why* each observation is what it is.
- **Self-update and rollback** — `groundwork update [--check|--version X]` installs a real,
  published Groundwork release (never a branch or arbitrary commit) while preserving the
  installation's profile/schedule/Agent-Teams setting; `groundwork rollback [--version X]` restores
  a prior installation from the backup `setup.sh` already takes automatically. Falls back to
  `certifi`'s CA bundle on an actual certificate-verification failure (never preferred over a
  working system/proxy CA), fixing a real `SSL: CERTIFICATE_VERIFY_FAILED` failure on python.org's
  macOS Python installer.
- **Routines via the CLI** — `groundwork routines list/run NAME/doctor [NAME]/schedule NAME FREQ`:
  run, check, and schedule Groundwork's unattended automation from one command.
- **Quiet interaction** — normal read-only investigation no longer narrates every step; blockers,
  risks, and destructive actions remain fully visible.
- **Routine readiness** — a single, honest `READY`/`READY (connectivity not verifiable)`/
  `BLOCKED`/`NOT ENABLED` verdict per routine, reusing existing checks rather than adding a new
  probe or a second readiness model.

Every one of these is additive: no previously documented direct-script or `setup.sh` interface was
removed or changed in a way that breaks existing usage.

## 2. Security and reliability findings and fixes

- During Phase 3's own independent review, a path-traversal/"zip-slip" archive-extraction escape
  was found in `groundwork update`'s release-tarball extraction: a symlink archive member could
  make the extraction write a file outside its target directory, and could in principle let a
  compromised release substitute an attacker-controlled `setup.sh` for the real one. Fixed by
  rejecting any non-regular-file archive member outright before extraction. A second, adversarial
  confirmation review independently reproduced the original escape, confirmed the fix closes it
  (including trying symlinks, hardlinks, and reordering the malicious member), and reported 0
  remaining MUST FIX.
- Post-publication, a real user reported `groundwork update --check` failing with
  `SSL: CERTIFICATE_VERIFY_FAILED` — root-caused to python.org's macOS Python 3.14 installer
  shipping an empty default certificate trust store (a known installer gap, independently confirmed
  as unrelated to any interception). `_urlopen_with_cert_fallback()` now tries the interpreter's own
  default trust store first (so a working system/enterprise/proxy CA, e.g. this project's own
  outbound HTTPS proxy, is never displaced) and retries once against `certifi`'s bundle only on an
  actual certificate-verification failure; a non-cert error is never retried, and a failure with
  `certifi` absent or the retry also failing propagates the original error unchanged. Two
  independent reviews: the first found and the fix closed one MUST FIX (a test's unmocked,
  undeclared dependency on the real `certifi` package, reproduced crashing the test file's own
  standalone entry point); the second, fresh-context confirmation review reported 0 remaining MUST
  FIX. See PR #37.

## 3. Test result

Full deterministic suite: **107 passed**, 0 failed, on the final merged `main` (`python3 -m pytest
tests -q`). Includes new/extended suites for every phase:
`test_groundwork_cli.py`/`test_groundwork_integrations.py`/`test_groundwork_update.py`/
`test_groundwork_routines.py`.

## 4. OpenSpec result

`openspec validate --all --strict`: all four phases' own changes (now archived as
`groundwork-cli-foundation`, `groundwork-integrations-cli`, `groundwork-update-lifecycle`,
`groundwork-routine-cli-ux`) validate clean. Two pre-existing, unrelated placeholder-Purpose
warnings remain on `health-dashboard`/`onboarding` — not introduced by this release, not owned by
it, left untouched per the "do not rewrite historical archived decisions" convention. The SSL
cert-fallback fix (PR #37) was a STANDARD-tier bug fix, not OpenSpec-tracked, consistent with
engineering-workflow.md's tiering.

## 5. Runtime validation already performed

Each phase was independently validated live in a disposable sandbox at merge time (never the real
`$HOME`); this release additionally re-validated the **integrated product** as one whole after all
four phases landed together: a real `setup.sh --non-interactive --capability-profile sre-cloudops`
install; `groundwork --help/version/doctor`; the full `integrations` surface
(`list`/`show github`/`doctor github`/`refresh`) showing the correct independent
AVAILABLE/CONFIGURED/CONNECTED/USED truth model; `routines list/doctor` showing the correct mix of
READY/BLOCKED/NOT ENABLED; a real, live `update --check` against the actual GitHub Releases API; a
real, live `claude -p` routine run (`news`, non-mutating) that returned a genuine `PARTIAL`
semantic status; statusLine rendering correctly afterward; and — specifically testing upgrade
safety — re-running `install.sh` against an existing installation with a planted unrelated
`settings.json` key and a planted `mcpServers` entry confirmed both survived untouched.

A code-level security sweep confirmed only one non-CLI file (`rules/output-contract.md`, +3 lines,
from the unrelated quiet-interaction change) changed under `rules/`/`hooks/` since `v2.2.0` — no
permission, hook, or safety control was weakened by this release.

## 6. Known limitations

Only one published release (`v2.2.0`) existed at the time `groundwork update`/`rollback` were
originally built and validated, so a true "previous release → next release" upgrade could not be
exercised against two real releases at that time — the update mechanism itself was validated
against that one real release plus a controlled stub installer.

**Resolved**: once a real `v2.3.0` was published, the real N→N+1 upgrade was exercised end to end in
a disposable sandbox: a genuine `v2.2.0` install (via `git archive v2.2.0` + its own `setup.sh`) →
`groundwork update --version 2.2.0` (real downgrade fetch/install of the real `v2.2.0` release, exit
0) → `groundwork update` with no flags (real upgrade to the real, published `v2.3.0` release, exit
0) → `groundwork rollback` (real restore of the pre-update backup, exit 0, reverted `VERSION` to
`2.2.0`). An unrelated planted `settings.json` key, an `mcpServers` entry, and the installation's
`profile` survived every transition unchanged. This was re-confirmed against the final, re-cut
`v2.3.0` commit (including the SSL cert-fallback fix) before this report's publication.

A pre-`v2.3.0` installation has no `groundwork` command or `groundwork_update.py` at all (both are
new in this release), so it cannot self-update — it needs one manual `git checkout v2.3.0 &&
bash install.sh` (or equivalent) to bootstrap onto `v2.3.0`, after which `groundwork update` is
available for all future releases. Independently confirmed on a real, pre-existing installation.

## 7. Deliberately excluded work

`groundwork routines status`/`unschedule`/`latest` were evaluated via a Product Value Gate and not
built: `list` already serves as the status view, `schedule NAME disabled` already is the unschedule
action, and `latest` stays reachable only via the existing direct-script interface (outside the
requested CLI shape). No terminal copilot, voice control, custom themes, usage telemetry,
dashboards, task observer, or new integrations/routines are part of this release.

## 8. Compatibility statement

No removed command, no changed flag semantics, no changed on-disk format. The one internal
extension (`groundwork_routines.py`'s `doctor` gaining an optional routine-name argument) is
backward compatible by default (`name=None` reproduces prior behavior exactly, unchanged call site
in `setup.sh --doctor`).

## 9. Release/tag information

- **Tag**: `v2.3.0`, annotated, re-created on this document's own merge commit (the final release
  commit, including PR #37's SSL fix and this release-metadata update) after the original
  `v2.3.0` tag and GitHub Release — published at the pre-fix PR #34 merge commit `7a78f972` — were
  deleted by the repository owner, per the re-cut notice above. No other published Groundwork
  release tag was touched.
- **GitHub Release**: no `create_release`/release-delete-class tool was available through this
  session's GitHub MCP toolset, so deleting the original release and publishing the re-cut one were
  both performed by the repository owner directly on GitHub; same for the tag push (this session's
  git transport receives an HTTP 403 pushing tags, though branch pushes succeed normally).
