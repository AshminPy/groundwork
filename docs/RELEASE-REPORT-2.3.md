# Groundwork 2.3.0 — release report

**Release version**: 2.3.0

**Release baseline**: `main` at the merge of PR #34 (`c23a2e9`), the validated state immediately
before the release branch (`release/2.3.0`) was cut.

**Scope**: derived from git history (`git log v2.2.0..main --oneline --merges`), not from
conversation memory — exactly five merged pull requests: #29 (quiet interaction / routine
readiness), #30 (`groundwork` CLI foundation), #32 (Integration Catalog CLI), #33 (version/update/
rollback lifecycle), #34 (Routines CLI). PR #31 (three future-feature candidates, documentation
only) was confirmed still open/unmerged via the GitHub API and is correctly excluded from this
release.

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
  a prior installation from the backup `setup.sh` already takes automatically.
- **Routines via the CLI** — `groundwork routines list/run NAME/doctor [NAME]/schedule NAME FREQ`:
  run, check, and schedule Groundwork's unattended automation from one command.
- **Quiet interaction** — normal read-only investigation no longer narrates every step; blockers,
  risks, and destructive actions remain fully visible.
- **Routine readiness** — a single, honest `READY`/`READY (connectivity not verifiable)`/
  `BLOCKED`/`NOT ENABLED` verdict per routine, reusing existing checks rather than adding a new
  probe or a second readiness model.

Every one of these is additive: no previously documented direct-script or `setup.sh` interface was
removed or changed in a way that breaks existing usage.

## 2. Security finding and fix (this cycle)

During Phase 3's own independent review, a path-traversal/"zip-slip" archive-extraction escape was
found in `groundwork update`'s release-tarball extraction: a symlink archive member could make the
extraction write a file outside its target directory, and could in principle let a compromised
release substitute an attacker-controlled `setup.sh` for the real one. Fixed by rejecting any
non-regular-file archive member outright before extraction. A second, adversarial confirmation
review independently reproduced the original escape, confirmed the fix closes it (including trying
symlinks, hardlinks, and reordering the malicious member), and reported 0 remaining MUST FIX.

## 3. Test result

Full deterministic suite: **106 passed**, 0 failed, on the final merged `main` (`python3 -m pytest
tests -q`). Includes new/extended suites for every phase:
`test_groundwork_cli.py`/`test_groundwork_integrations.py`/`test_groundwork_update.py`/
`test_groundwork_routines.py`.

## 4. OpenSpec result

`openspec validate --all --strict`: all four phases' own changes (now archived as
`groundwork-cli-foundation`, `groundwork-integrations-cli`, `groundwork-update-lifecycle`,
`groundwork-routine-cli-ux`) validate clean. Two pre-existing, unrelated placeholder-Purpose
warnings remain on `health-dashboard`/`onboarding` — not introduced by this release, not owned by
it, left untouched per the "do not rewrite historical archived decisions" convention.

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

Only one published release (`v2.2.0`) existed at the time `groundwork update`/`rollback` were built
and validated, so a true "previous release → next release" upgrade could not be exercised against
two real releases before now — the update mechanism itself was validated against that one real
release plus a controlled stub installer. Publishing `v2.3.0` is the first opportunity to validate
a genuine N→N+1 upgrade for real; see the post-release verification note in this release's process
record for the result, if publication succeeded.

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

- **Tag**: `v2.3.0`, annotated, created on the validated release-preparation merge commit.
- **GitHub Release**: see this release's process record for status — no `create_release`-class
  tool was available through this session's GitHub MCP toolset at publication time; if so, the tag
  was pushed (or reported blocked) per the documented authorization contingency, and GitHub Release
  creation was reported as requiring manual owner action rather than treated as a defect.
