#!/usr/bin/env python3
"""Groundwork version/update lifecycle (Next Release Program, Phase 3).

`update` and `rollback` reuse the existing installer end to end — this script never reimplements
install.sh's or setup.sh's logic, only fetches the right source tree and invokes them:

  groundwork_update.py update [--check] [--version X]
      --check           non-mutating: print Current/Latest/whether an update is available, exit
      (no flags)        install the latest published, non-draft, non-prerelease GitHub Release
      --version X       install that exact published release (rejects any ref that is not a real,
                         published, non-draft, non-prerelease release — never a branch, SHA, or
                         arbitrary tag)
  groundwork_update.py rollback [--version X]
      (no flags)        dispatches to the installed setup.sh's own `--rollback` (latest backup)
      --version X       restores the specific backup whose BACKUP-INFO.txt records that it was
                         taken immediately before version X was installed (setup.sh's own
                         make_backup() already records this on every `./setup.sh` run)

Authoritative source: the GitHub Releases API (never origin/main, a branch, a draft release, a
prerelease, or an arbitrary commit) — the same source Groundwork's own tagged releases already
use (docs/RELEASE-REPORT-2.2.md). `/releases/latest` already excludes drafts/prereleases by its
own documented and live-verified behavior; `--version` is additionally cross-checked against the
full `/releases` list so an unpublished or non-existent version is rejected before anything is
downloaded.

Never stores credentials, never requires sudo, never installs OS packages (always passes
`--no-install-prereqs` to the fetched setup.sh — a missing hard prerequisite is reported and left
for the user, exactly as setup.sh already does on its own). Update preserves the installation's
current profile/schedule/Agent-Teams choices by reading them before mutating and passing them back
explicitly to setup.sh --non-interactive, rather than trusting its own interactive-mode defaults
(one of which, --schedule, silently resets to "weekly" with no flag given — confirmed by reading
setup.sh's choose_schedule() directly, not assumed).
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

REPO_OWNER = "AshminPy"
REPO_NAME = "groundwork"
API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
USER_AGENT = "groundwork-update/1 (+https://github.com/AshminPy/groundwork)"
HTTP_TIMEOUT_S = 15
KNOWN_SCHEDULES = ("weekly", "daily", "monthly", "yearly", "disabled")

CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
VERSION_PATH = CLAUDE_DIR / "groundwork" / "VERSION"
INSTALLED_SETUP_SH = CLAUDE_DIR / "groundwork" / "bin" / "setup.sh"
SETTINGS_JSON = CLAUDE_DIR / "settings.json"
REPORT_JSON = CLAUDE_DIR / "groundwork" / "report.json"
BACKUP_ROOT = Path(os.environ.get("GROUNDWORK_BACKUP_DIR") or (Path.home() / ".claude-backups"))


def _read_version() -> Optional[str]:
    try:
        text = VERSION_PATH.read_text().strip()
        return text or None
    except OSError:
        return None


def _semver_tuple(v: str):
    v = (v or "").strip().lstrip("vV")
    parts = v.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def _http_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as r:
        return json.loads(r.read())


def _http_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S * 4) as r:  # a tarball download needs more than 15s
        return r.read()


def latest_release():
    """Returns (release_dict, None) or (None, reason). release_dict: tag, version (tuple),
    tarball_url. Never returns a draft or prerelease — GitHub's own /releases/latest endpoint
    already excludes both (confirmed live against this repo, not assumed)."""
    try:
        data = _http_json(f"{API_BASE}/releases/latest")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, "no published release exists yet for this repository"
        return None, f"GitHub Releases API returned HTTP {e.code}"
    except Exception as e:
        return None, f"could not reach the GitHub Releases API ({type(e).__name__}: {e})"
    if data.get("draft") or data.get("prerelease"):
        return None, "the latest release is a draft or prerelease (unexpected — refusing to treat it as stable)"
    tag = data.get("tag_name") or ""
    version = _semver_tuple(tag)
    if version is None:
        return None, f"latest release tag '{tag}' is not a recognized vX.Y.Z version — cannot compare safely"
    return {"tag": tag, "version": version, "tarball_url": data.get("tarball_url")}, None


def find_release(version_str: str):
    """Validates version_str against the real, published, non-draft, non-prerelease releases list.
    Never accepts a branch, a commit SHA, or any tag that isn't an actual published release."""
    want = _semver_tuple(version_str)
    if want is None:
        return None, f"'{version_str}' is not a valid vX.Y.Z version string"
    try:
        data = _http_json(f"{API_BASE}/releases")
    except Exception as e:
        return None, f"could not reach the GitHub Releases API ({type(e).__name__}: {e})"
    for rel in data:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        if _semver_tuple(rel.get("tag_name") or "") == want:
            return {"tag": rel["tag_name"], "version": want, "tarball_url": rel.get("tarball_url")}, None
    return None, f"'{version_str}' is not a published, non-draft, non-prerelease Groundwork release"


def _top_changelog_version(path: Path):
    try:
        text = path.read_text()
    except OSError:
        return None
    m = re.search(r"^## (\d+\.\d+\.\d+)", text, re.MULTILINE)
    return _semver_tuple(m.group(1)) if m else None


def _safe_extract(tf: tarfile.TarFile, dest: Path) -> None:
    """Rejects any archive member whose resolved path would land outside dest (path traversal /
    "zip-slip"), before extracting anything. GitHub's own tarballs are well-formed, but a release
    tarball is still content fetched over the network — verified defensively, not assumed safe."""
    dest = dest.resolve()
    for member in tf.getmembers():
        target = (dest / member.name).resolve()
        if target != dest and dest not in target.parents:
            raise ValueError(f"refusing to extract archive member outside the target directory: {member.name}")
    tf.extractall(dest)  # noqa: S202 — membership already validated above


def _read_current_profile() -> Optional[str]:
    try:
        data = json.loads(SETTINGS_JSON.read_text())
        value = data.get("env", {}).get("GROUNDWORK_PROFILE")
        return value or None
    except Exception:
        return None


def _read_current_teams() -> bool:
    try:
        data = json.loads(SETTINGS_JSON.read_text())
        return data.get("env", {}).get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1"
    except Exception:
        return False


def _read_current_schedule() -> str:
    try:
        data = json.loads(REPORT_JSON.read_text())
        s = data.get("schedule")
        return s if s in KNOWN_SCHEDULES else "weekly"
    except Exception:
        return "weekly"


def _find_backup_for_version(version_str: str) -> Optional[Path]:
    want = _semver_tuple(version_str)
    if want is None or not BACKUP_ROOT.is_dir():
        return None
    candidates = []
    for d in BACKUP_ROOT.iterdir():
        info = d / "BACKUP-INFO.txt"
        if not info.is_file():
            continue
        try:
            text = info.read_text()
        except OSError:
            continue
        m = re.search(r"^groundwork_version_before=(.+)$", text, re.MULTILINE)
        if m and _semver_tuple(m.group(1).strip()) == want:
            candidates.append(d)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)  # newest match first
    return candidates[0]


def _print_check(current: Optional[str]) -> int:
    if current is None:
        print(f"Current: unknown (no VERSION file at {VERSION_PATH} — is Groundwork installed?)", file=sys.stderr)
        return 1
    print(f"Current: {current}")
    rel, err = latest_release()
    if err:
        print(f"Latest:  UNKNOWN ({err})")
        print("Update available: UNKNOWN")
        return 1
    latest_str = rel["tag"].lstrip("vV")
    print(f"Latest:  {latest_str}")
    cur = _semver_tuple(current)
    if cur is None:
        print("Update available: UNKNOWN (installed VERSION is not a recognized vX.Y.Z string)")
        return 1
    if rel["version"] > cur:
        print("Update available: YES")
    elif rel["version"] == cur:
        print("Update available: NO (already on the latest published release)")
    else:
        print("Update available: NO (installed version is newer than the latest published release)")
    return 0


def cmd_update(args) -> int:
    if args.check and args.version:
        print("update: --check and --version cannot be combined — use 'groundwork update --check' to see "
              "what's available, or 'groundwork update --version X' to install a specific release",
              file=sys.stderr)
        return 1
    current = _read_version()
    if args.check:
        return _print_check(current)

    if current is None:
        print(f"update: Groundwork does not appear to be installed (no VERSION file at {VERSION_PATH})",
              file=sys.stderr)
        return 1
    if not INSTALLED_SETUP_SH.exists():
        print(f"update: {INSTALLED_SETUP_SH} not found — is Groundwork installed via install.sh?", file=sys.stderr)
        return 1

    rel, err = find_release(args.version) if args.version else latest_release()
    if err:
        print(f"update: {err}", file=sys.stderr)
        return 1

    cur_tuple = _semver_tuple(current)
    print(f"Current: {current}")
    print(f"Target:  {rel['tag'].lstrip('vV')}")
    if cur_tuple == rel["version"]:
        print("Already on the target version — nothing to do.")
        return 0

    profile = _read_current_profile()
    teams = _read_current_teams()
    schedule = _read_current_schedule()

    with tempfile.TemporaryDirectory(prefix="groundwork-update-") as tmp:
        tmp_path = Path(tmp)
        print(f"Fetching {rel['tag']} ...")
        try:
            archive = _http_bytes(rel["tarball_url"])
        except Exception as e:
            print(f"update: failed to download the release archive ({type(e).__name__}: {e})", file=sys.stderr)
            return 1
        try:
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
                _safe_extract(tf, tmp_path)
        except Exception as e:
            print(f"update: failed to extract the release archive ({type(e).__name__}: {e})", file=sys.stderr)
            return 1

        top_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        if len(top_dirs) != 1:
            print(f"update: unexpected archive layout (expected exactly one top-level directory, "
                  f"found {len(top_dirs)}) — refusing to install", file=sys.stderr)
            return 1
        src = top_dirs[0]

        for required in ("install.sh", "setup.sh", "CHANGELOG.md"):
            if not (src / required).is_file():
                print(f"update: fetched release is missing {required} — refusing to install from an "
                      "incomplete or corrupt source", file=sys.stderr)
                return 1
        changelog_version = _top_changelog_version(src / "CHANGELOG.md")
        if changelog_version != rel["version"]:
            print(f"update: the fetched source's CHANGELOG.md top entry ({changelog_version}) does not match "
                  f"the requested release tag ({rel['tag']}) — refusing to install", file=sys.stderr)
            return 1

        setup_args = ["bash", str(src / "setup.sh"), "--non-interactive", "--no-install-prereqs",
                      "--schedule", schedule]
        if profile:
            setup_args += ["--profile", profile]
        setup_args += ["--agent-teams"] if teams else ["--no-agent-teams"]

        print(f"Installing {rel['tag']} (a full backup of the current installation is taken automatically "
              "before anything changes) ...")
        result = subprocess.run(setup_args)
        if result.returncode != 0:
            print(f"update: install failed (exit {result.returncode}). Your previous installation was backed "
                  "up first — run 'groundwork rollback' to restore it, or './setup.sh --verify' for detail.",
                  file=sys.stderr)
            return result.returncode

    new_version = _read_version()
    print(f"Updated: {current} -> {new_version}")
    if _semver_tuple(new_version or "") != rel["version"]:
        print(f"update: WARNING — installed VERSION ({new_version}) does not match the requested release "
              f"({rel['tag']}) after install", file=sys.stderr)
        return 1
    return 0


def cmd_rollback(args) -> int:
    if not INSTALLED_SETUP_SH.exists():
        print(f"rollback: {INSTALLED_SETUP_SH} not found — is Groundwork installed?", file=sys.stderr)
        return 1
    if args.version:
        backup_dir = _find_backup_for_version(args.version)
        if backup_dir is None:
            print(f"rollback: no backup under {BACKUP_ROOT} was taken immediately before version "
                  f"{args.version} was installed — nothing to restore", file=sys.stderr)
            return 1
        result = subprocess.run(["bash", str(INSTALLED_SETUP_SH), "--rollback", str(backup_dir)])
    else:
        result = subprocess.run(["bash", str(INSTALLED_SETUP_SH), "--rollback"])
    return result.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_update = sub.add_parser("update", help="check for, or install, a published Groundwork release")
    p_update.add_argument("--check", action="store_true",
                           help="non-mutating: report current vs. latest published version only")
    p_update.add_argument("--version", help="install this exact published release instead of the latest")
    p_update.set_defaults(func=cmd_update)
    p_rollback = sub.add_parser("rollback", help="restore a prior installation from an existing backup")
    p_rollback.add_argument("--version",
                             help="restore the backup taken immediately before this version was installed")
    p_rollback.set_defaults(func=cmd_rollback)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
