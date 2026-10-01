#!/usr/bin/env python3
"""Deterministic checks for scripts/groundwork_update.py (Next Release Program, Phase 3) — the
version/update/rollback lifecycle: semver parsing, GitHub Releases API validation (never a draft,
prerelease, branch, or arbitrary ref), path-traversal-safe archive extraction, the
profile/schedule/Agent-Teams preservation that closes setup.sh's non-interactive schedule-reset
gotcha, and the update/rollback orchestration end to end against a stub installer.

All GitHub API/network access is monkeypatched (`mod._http_json` / `mod._http_bytes`) — these
tests never touch the real network, matching this repo's test-isolation convention. The actual
installer invocation is exercised for real via a stub shell script standing in for the fetched
tree's setup.sh (or the installed setup.sh for rollback), the same technique
test_groundwork_integrations.py uses for stubbing gh.

Run: python3 tests/test_groundwork_update.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import io
import json
import os
import ssl
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "groundwork_update.py"

_FAILURES: list[str] = []
PASS = FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        _FAILURES.append(f"{name}  {detail}")
        print(f"  FAIL {name}  {detail}")


def finish() -> None:
    failures = list(_FAILURES)
    _FAILURES.clear()
    assert not failures, "\n".join(failures)


def load_module():
    spec = importlib.util.spec_from_file_location("gw_update", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _capture_call(fn, *a, **kw):
    """Runs fn, returning (return_value, stdout_text, stderr_text) — same technique
    test_groundwork_integrations.py's _capture() uses, extended to also grab stderr and the
    return code, since groundwork_update.py's error paths write to stderr."""
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = StringIO(), StringIO()
    try:
        rc = fn(*a, **kw)
        return rc, sys.stdout.getvalue(), sys.stderr.getvalue()
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def _make_tarball(top_dirname: str, files: dict[str, bytes]) -> bytes:
    """Builds an in-memory .tar.gz with one top-level directory containing the given files —
    mirrors the single-top-level-dir layout of a real GitHub release tarball_url download."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        dir_info = tarfile.TarInfo(name=top_dirname)
        dir_info.type = tarfile.DIRTYPE
        dir_info.mode = 0o755
        tf.addfile(dir_info)
        for rel, data in files.items():
            info = tarfile.TarInfo(name=f"{top_dirname}/{rel}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _write_backup(root: Path, name: str, version_before: str, mtime_offset: float = 0) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "BACKUP-INFO.txt").write_text(f"source=/fake\nexisted=1\ncreated=2026-01-01\n"
                                        f"groundwork_version_before={version_before}\n")
    if mtime_offset:
        t = (d / "BACKUP-INFO.txt").stat().st_mtime + mtime_offset
        os.utime(d / "BACKUP-INFO.txt", (t, t))
    return d


# ---------------------------------------------------------------------------------------------
def test_semver_tuple() -> None:
    print("groundwork_update.py — _semver_tuple(): only strict vX.Y.Z / X.Y.Z parses, everything else is None")
    mod = load_module()
    check("'v2.2.0' -> (2,2,0)", mod._semver_tuple("v2.2.0") == (2, 2, 0))
    check("'2.2.0' -> (2,2,0)", mod._semver_tuple("2.2.0") == (2, 2, 0))
    check("'V2.2.0' -> (2,2,0) (case-insensitive leading v)", mod._semver_tuple("V2.2.0") == (2, 2, 0))
    check("'2.2' -> None (not three components)", mod._semver_tuple("2.2") is None)
    check("'2.2.0-rc1' -> None (prerelease suffix rejected, not silently truncated)",
          mod._semver_tuple("2.2.0-rc1") is None)
    check("'' -> None", mod._semver_tuple("") is None)
    check("'main' -> None (a branch name is never a version)", mod._semver_tuple("main") is None)
    check("'abc123def' -> None (a commit SHA is never a version)", mod._semver_tuple("abc123def") is None)
    check("(2,10,0) > (2,9,9) — tuple comparison orders by component, not lexicographically",
          mod._semver_tuple("2.10.0") > mod._semver_tuple("2.9.9"))
    finish()


def test_latest_release_rejects_non_stable() -> None:
    print("groundwork_update.py — latest_release(): only a real, stable, semver-tagged release is ever returned")
    mod = load_module()

    mod._http_json = lambda url: {"tag_name": "v3.1.4", "draft": False, "prerelease": False,
                                   "tarball_url": "fake://t"}
    rel, err = mod.latest_release()
    check("a normal stable release parses cleanly", err is None and rel["version"] == (3, 1, 4), (rel, err))

    mod._http_json = lambda url: {"tag_name": "v3.2.0", "draft": True, "prerelease": False, "tarball_url": "x"}
    rel, err = mod.latest_release()
    check("a draft release is refused even though the endpoint returned it", rel is None and err, (rel, err))

    mod._http_json = lambda url: {"tag_name": "v3.2.0", "draft": False, "prerelease": True, "tarball_url": "x"}
    rel, err = mod.latest_release()
    check("a prerelease is refused even though the endpoint returned it", rel is None and err, (rel, err))

    mod._http_json = lambda url: {"tag_name": "release-2026-01", "draft": False, "prerelease": False,
                                   "tarball_url": "x"}
    rel, err = mod.latest_release()
    check("a non-semver tag is refused rather than guessed at", rel is None and err, (rel, err))

    import urllib.error
    def raise_404(url):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    mod._http_json = raise_404
    rel, err = mod.latest_release()
    check("HTTP 404 (no release exists yet) is a clean UNKNOWN, not a crash", rel is None and err, (rel, err))

    def raise_conn_error(url):
        raise OSError("network unreachable")
    mod._http_json = raise_conn_error
    rel, err = mod.latest_release()
    check("a network failure is a clean UNKNOWN, not a crash", rel is None and err, (rel, err))
    finish()


def test_find_release_validates_against_published_list_only() -> None:
    print("groundwork_update.py — find_release(): never accepts a branch, SHA, draft, or prerelease as a version")
    mod = load_module()
    calls = []

    def fake_http_json(url):
        calls.append(url)
        return [
            {"tag_name": "v3.2.0", "draft": True, "prerelease": False, "tarball_url": "x"},
            {"tag_name": "v3.1.5", "draft": False, "prerelease": True, "tarball_url": "x"},
            {"tag_name": "v3.1.4", "draft": False, "prerelease": False, "tarball_url": "fake://t"},
        ]
    mod._http_json = fake_http_json

    rel, err = mod.find_release("3.1.4")
    check("a real published stable release is found", err is None and rel["tag"] == "v3.1.4", (rel, err))
    check("find_release queries the full /releases list, not /releases/latest",
          any(u.endswith("/releases") for u in calls), calls)

    rel, err = mod.find_release("3.2.0")
    check("a draft release is never selectable via --version even if its tag matches",
          rel is None and err, (rel, err))

    rel, err = mod.find_release("3.1.5")
    check("a prerelease is never selectable via --version even if its tag matches",
          rel is None and err, (rel, err))

    calls.clear()
    rel, err = mod.find_release("not-a-version")
    check("a non-semver string is rejected before any HTTP call is made",
          rel is None and err and calls == [], (rel, err, calls))

    rel, err = mod.find_release("9.9.9")
    check("a version with no matching published release is rejected, not silently accepted", rel is None and err)
    finish()


def test_safe_extract_rejects_path_traversal() -> None:
    print("groundwork_update.py — _safe_extract(): a malicious archive member outside the target dir is refused")
    mod = load_module()

    for bad_name in ("../evil.txt", "../../etc/evil", "a/../../evil.txt"):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            info = tarfile.TarInfo(name=bad_name)
            data = b"pwned"
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        buf.seek(0)
        with tempfile.TemporaryDirectory() as dest:
            with tarfile.open(fileobj=buf, mode="r:gz") as tf:
                raised = False
                try:
                    mod._safe_extract(tf, Path(dest))
                except ValueError:
                    raised = True
                check(f"member '{bad_name}' is rejected before extraction", raised, bad_name)
                check(f"member '{bad_name}' leaves no file outside the dest dir",
                      not (Path(dest).parent / "evil.txt").exists() and not (Path(dest).parent / "evil").exists())

    # A symlink member is rejected outright, not just path-checked: the path check alone only
    # validates where a member is *created*, not what a symlink then *points to* once extracted —
    # a symlink created early in tar order can make a later, path-valid-looking member (e.g.
    # "link/payload") write through it to an arbitrary location outside dest, since at validation
    # time (before extraction) no symlink exists on disk yet for resolve() to follow. A real,
    # independently-reproduced escape found by this change's own independent review, not a
    # theoretical concern — this regression test is the PoC that review used, kept as a test.
    with tempfile.TemporaryDirectory() as outside_dir:
        escape_target = Path(outside_dir) / "sensitive"
        escape_target.mkdir()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            link = tarfile.TarInfo(name="link")
            link.type = tarfile.SYMTYPE
            link.linkname = str(escape_target)  # absolute — the proven-live PoC shape
            tf.addfile(link)
            data = b"malicious payload"
            info = tarfile.TarInfo(name="link/escaped.py")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        buf.seek(0)
        with tempfile.TemporaryDirectory() as dest:
            with tarfile.open(fileobj=buf, mode="r:gz") as tf:
                raised = False
                try:
                    mod._safe_extract(tf, Path(dest))
                except ValueError:
                    raised = True
                check("a symlink archive member is rejected before extraction, never silently followed", raised)
        check("the symlink member writes nothing through to its target outside dest",
              not (escape_target / "escaped.py").exists(), escape_target)

    # A well-formed archive (the normal case) still extracts cleanly.
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="top/install.sh")
        data = b"#!/bin/sh\n"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    buf.seek(0)
    with tempfile.TemporaryDirectory() as dest:
        with tarfile.open(fileobj=buf, mode="r:gz") as tf:
            mod._safe_extract(tf, Path(dest))
        check("a well-formed archive still extracts normally", (Path(dest) / "top" / "install.sh").is_file())
    finish()


def test_find_backup_for_version() -> None:
    print("groundwork_update.py — _find_backup_for_version(): scans BACKUP-INFO.txt, picks the newest match")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        mod.BACKUP_ROOT = root
        older = _write_backup(root, "groundwork-20260101", "3.1.0", mtime_offset=-1000)
        newer = _write_backup(root, "groundwork-20260201", "3.1.0", mtime_offset=0)
        _write_backup(root, "groundwork-20260301", "3.1.4", mtime_offset=1000)

        found = mod._find_backup_for_version("3.1.0")
        check("picks the newest of two matching backups", found == newer, (found, older, newer))

        found_other = mod._find_backup_for_version("3.1.4")
        check("a different version resolves to its own distinct backup",
              found_other is not None and found_other.name == "groundwork-20260301", found_other)

        check("a version with no matching backup returns None", mod._find_backup_for_version("9.9.9") is None)
        check("an invalid version string returns None, not a crash", mod._find_backup_for_version("nope") is None)

    empty = Path(tempfile.mkdtemp()) / "does-not-exist"
    mod.BACKUP_ROOT = empty
    check("a missing backup root returns None rather than raising", mod._find_backup_for_version("3.1.0") is None)
    finish()


def test_check_is_non_mutating_and_reports_honestly() -> None:
    print("groundwork_update.py — --check: Current/Latest/Update-available, never UNKNOWN presented as certain")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        version_path = Path(tmpdir) / "VERSION"
        version_path.write_text("3.1.0\n")
        mod.VERSION_PATH = version_path

        mod._http_json = lambda url: {"tag_name": "v3.1.4", "draft": False, "prerelease": False, "tarball_url": "x"}
        rc, out, _ = _capture_call(mod._print_check, "3.1.0")
        check("an older installed version reports an update is available", "Update available: YES" in out, out)
        check("--check prints the current version", "Current: 3.1.0" in out, out)
        check("--check prints the latest published version", "Latest:  3.1.4" in out, out)
        check("--check exits 0 when the comparison is known", rc == 0, rc)

        rc2, out2, _ = _capture_call(mod._print_check, "3.1.4")
        check("an up-to-date installation reports no update available", "Update available: NO" in out2, out2)

        rc3, out3, _ = _capture_call(mod._print_check, "9.9.9")
        check("an installed version newer than the latest release is reported honestly, not as an update",
              "Update available: NO" in out3, out3)

        mod._http_json = lambda url: (_ for _ in ()).throw(OSError("no network"))
        rc4, out4, _ = _capture_call(mod._print_check, "3.1.0")
        check("a network failure reports Latest as UNKNOWN, never guessed", "UNKNOWN" in out4, out4)
        check("Update available stays UNKNOWN rather than defaulting to NO", "Update available: UNKNOWN" in out4, out4)
        check("an UNKNOWN result is a non-zero exit (never silently treated as 'no update')", rc4 != 0, rc4)

        rc5, _, _ = _capture_call(mod._print_check, None)
        check("--check with no installed VERSION file fails clean, not a crash", rc5 != 0, rc5)
    finish()


def test_preservation_reads() -> None:
    print("groundwork_update.py — reads current profile/Agent-Teams/schedule before any mutation")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Path(tmpdir) / "settings.json"
        report = Path(tmpdir) / "report.json"
        mod.SETTINGS_JSON = settings
        mod.REPORT_JSON = report

        settings.write_text(json.dumps({"env": {"GROUNDWORK_PROFILE": "fullstack",
                                                  "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}))
        report.write_text(json.dumps({"schedule": "monthly"}))
        check("reads the current profile verbatim", mod._read_current_profile() == "fullstack")
        check("reads Agent-Teams as enabled when set to the string '1'", mod._read_current_teams() is True)
        check("reads the current schedule verbatim (never silently reset to weekly)",
              mod._read_current_schedule() == "monthly")

        # Missing/malformed files fail safe rather than crashing; schedule specifically must still
        # default sanely since setup.sh's own non-interactive mode defaults to "weekly" with no
        # flag — but a *present*, valid schedule (above) must never be overridden by that default.
        mod.SETTINGS_JSON = Path(tmpdir) / "does-not-exist.json"
        mod.REPORT_JSON = Path(tmpdir) / "also-missing.json"
        check("missing settings.json => no profile (never invented)", mod._read_current_profile() is None)
        check("missing settings.json => Agent-Teams reads as disabled, not crash", mod._read_current_teams() is False)
        check("missing report.json => schedule falls back to 'weekly' (setup.sh's own default)",
              mod._read_current_schedule() == "weekly")

        report.write_text("{not valid json")
        mod.REPORT_JSON = report
        check("malformed report.json fails safe to 'weekly', not a crash", mod._read_current_schedule() == "weekly")

        report.write_text(json.dumps({"schedule": "not-a-real-schedule"}))
        check("an unrecognized schedule value falls back to 'weekly' rather than being passed through unchecked",
              mod._read_current_schedule() == "weekly")
    finish()


def _stub_setup_sh(path: Path, capture_log: Path, write_version_to: Path, write_version: str,
                    exit_code: int = 0) -> None:
    path.write_text(
        "#!/bin/sh\n"
        f'echo "$@" > {capture_log}\n'
        f'mkdir -p "$(dirname {write_version_to})"\n'
        f'echo "{write_version}" > {write_version_to}\n'
        f"exit {exit_code}\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class _UpdateArgs:
    def __init__(self, check=False, version=None):
        self.check = check
        self.version = version


def test_update_rejects_check_and_version_combo() -> None:
    print("groundwork_update.py — 'update --check --version X' is rejected outright, not silently resolved")
    mod = load_module()
    rc, _, err = _capture_call(mod.cmd_update, _UpdateArgs(check=True, version="3.1.4"))
    check("--check and --version together is a clean error", rc != 0 and "cannot be combined" in err, err)
    finish()


def test_update_not_installed_fails_clean() -> None:
    print("groundwork_update.py — update on an uninstalled Groundwork fails clean, never half-runs")
    mod = load_module()
    mod.VERSION_PATH = Path(tempfile.mkdtemp()) / "does-not-exist" / "VERSION"
    rc, _, err = _capture_call(mod.cmd_update, _UpdateArgs())
    check("update refuses to proceed with no installed VERSION file",
          rc != 0 and "not appear to be installed" in err, err)
    finish()


def test_update_already_on_target_is_noop() -> None:
    print("groundwork_update.py — update to the version already installed is a clean no-op, no installer invoked")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.VERSION_PATH = Path(tmpdir) / "VERSION"
        mod.VERSION_PATH.write_text("3.1.4\n")
        mod.INSTALLED_SETUP_SH = Path(tmpdir) / "installed-setup.sh"
        mod.INSTALLED_SETUP_SH.write_text("#!/bin/sh\nexit 0\n")
        mod._http_json = lambda url: {"tag_name": "v3.1.4", "draft": False, "prerelease": False, "tarball_url": "x"}

        called = {"n": 0}
        real_bytes = mod._http_bytes

        def tripwire(url):
            called["n"] += 1
            raise AssertionError("no archive should ever be downloaded when already on the target version")
        mod._http_bytes = tripwire
        try:
            rc, out, _ = _capture_call(mod.cmd_update, _UpdateArgs())
            check("already-on-target update exits 0", rc == 0, rc)
            check("already-on-target update says so, doesn't silently succeed", "nothing to do" in out.lower(), out)
            check("already-on-target update never downloads a release archive", called["n"] == 0)
        finally:
            mod._http_bytes = real_bytes
    finish()


def test_update_end_to_end_preserves_schedule_profile_teams() -> None:
    print("groundwork_update.py — a real update run: fetch, extract, invoke the fetched setup.sh with the "
          "CURRENT profile/schedule/Agent-Teams explicitly re-passed (closing setup.sh's non-interactive "
          "schedule-reset-to-weekly default), then verifies the resulting VERSION matches the target")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        mod.VERSION_PATH = tmp / "VERSION"
        mod.VERSION_PATH.write_text("3.1.0\n")
        mod.INSTALLED_SETUP_SH = tmp / "installed-setup.sh"
        mod.INSTALLED_SETUP_SH.write_text("#!/bin/sh\nexit 0\n")
        mod.SETTINGS_JSON = tmp / "settings.json"
        mod.SETTINGS_JSON.write_text(json.dumps({"env": {"GROUNDWORK_PROFILE": "fullstack",
                                                           "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}))
        mod.REPORT_JSON = tmp / "report.json"
        mod.REPORT_JSON.write_text(json.dumps({"schedule": "monthly"}))

        capture_log = tmp / "capture.log"
        fake_setup = tmp / "fake-setup-src.sh"  # staged into the tarball, not run directly from here
        _stub_setup_sh(fake_setup, capture_log, mod.VERSION_PATH, "3.1.4")
        tarball = _make_tarball("AshminPy-groundwork-abcdef1", {
            "install.sh": b"#!/bin/sh\nexit 0\n",
            "setup.sh": fake_setup.read_bytes(),
            "CHANGELOG.md": b"## 3.1.4\n\nRelease notes.\n\n## 3.1.0\n\nOlder.\n",
        })

        mod._http_json = lambda url: {"tag_name": "v3.1.4", "draft": False, "prerelease": False,
                                       "tarball_url": "fake://tarball"}
        mod._http_bytes = lambda url: tarball

        rc, out, err = _capture_call(mod.cmd_update, _UpdateArgs())
        check("end-to-end update exits 0", rc == 0, out + err)
        check("the fetched setup.sh was actually invoked", capture_log.exists(), out + err)

        argv_line = capture_log.read_text().strip() if capture_log.exists() else ""
        check("update passes --non-interactive", "--non-interactive" in argv_line, argv_line)
        check("update passes --no-install-prereqs (never installs OS packages itself)",
              "--no-install-prereqs" in argv_line, argv_line)
        check("update explicitly re-passes the CURRENT schedule ('monthly'), not setup.sh's own "
              "non-interactive default of 'weekly'", "--schedule monthly" in argv_line, argv_line)
        check("update explicitly re-passes the CURRENT profile ('fullstack')",
              "--profile fullstack" in argv_line, argv_line)
        check("update explicitly re-passes Agent-Teams as enabled", "--agent-teams" in argv_line, argv_line)
        check("update never passes --no-agent-teams when Agent-Teams was on",
              "--no-agent-teams" not in argv_line, argv_line)

        check("after a successful update, VERSION reflects the new installed version",
              mod.VERSION_PATH.read_text().strip() == "3.1.4", mod.VERSION_PATH.read_text())
    finish()


def test_update_declines_profile_flag_when_none_set() -> None:
    print("groundwork_update.py — when no profile was ever set, update omits --profile entirely "
          "(never invents one) — omission is what already correctly preserves settings.json today")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        mod.VERSION_PATH = tmp / "VERSION"
        mod.VERSION_PATH.write_text("3.1.0\n")
        mod.INSTALLED_SETUP_SH = tmp / "installed-setup.sh"
        mod.INSTALLED_SETUP_SH.write_text("#!/bin/sh\nexit 0\n")
        mod.SETTINGS_JSON = tmp / "does-not-exist-settings.json"
        mod.REPORT_JSON = tmp / "does-not-exist-report.json"

        capture_log = tmp / "capture.log"
        fake_setup = tmp / "fake-setup-src.sh"
        _stub_setup_sh(fake_setup, capture_log, mod.VERSION_PATH, "3.1.4")
        tarball = _make_tarball("top", {
            "install.sh": b"#!/bin/sh\nexit 0\n",
            "setup.sh": fake_setup.read_bytes(),
            "CHANGELOG.md": b"## 3.1.4\n\nnotes\n",
        })
        mod._http_json = lambda url: {"tag_name": "v3.1.4", "draft": False, "prerelease": False,
                                       "tarball_url": "x"}
        mod._http_bytes = lambda url: tarball

        rc, out, err = _capture_call(mod.cmd_update, _UpdateArgs())
        check("update with no prior profile still succeeds", rc == 0, out + err)
        argv_line = capture_log.read_text().strip()
        check("no --profile flag is passed when none was previously set", "--profile" not in argv_line, argv_line)
        check("Agent-Teams defaults to --no-agent-teams when never enabled",
              "--no-agent-teams" in argv_line, argv_line)
    finish()


def test_update_refuses_incomplete_or_mismatched_archive() -> None:
    print("groundwork_update.py — a fetched archive missing required files, or whose CHANGELOG doesn't "
          "match the requested release, is refused before anything touches the real installation")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        mod.VERSION_PATH = tmp / "VERSION"
        mod.VERSION_PATH.write_text("3.1.0\n")
        mod.INSTALLED_SETUP_SH = tmp / "installed-setup.sh"
        mod.INSTALLED_SETUP_SH.write_text("#!/bin/sh\nexit 0\n")
        mod.SETTINGS_JSON = tmp / "no-settings.json"
        mod.REPORT_JSON = tmp / "no-report.json"
        mod._http_json = lambda url: {"tag_name": "v3.1.4", "draft": False, "prerelease": False, "tarball_url": "x"}

        # Missing setup.sh entirely.
        incomplete = _make_tarball("top", {"install.sh": b"x", "CHANGELOG.md": b"## 3.1.4\n"})
        mod._http_bytes = lambda url: incomplete
        rc, _, err = _capture_call(mod.cmd_update, _UpdateArgs())
        check("an archive missing setup.sh is refused, not partially installed",
              rc != 0 and "missing" in err.lower(), err)

        # CHANGELOG top entry doesn't match the requested release tag.
        mismatched = _make_tarball("top", {
            "install.sh": b"x", "setup.sh": b"#!/bin/sh\nexit 0\n", "CHANGELOG.md": b"## 9.9.9\n",
        })
        mod._http_bytes = lambda url: mismatched
        rc2, _, err2 = _capture_call(mod.cmd_update, _UpdateArgs())
        check("a CHANGELOG/tag mismatch is refused rather than trusted blindly",
              rc2 != 0 and "does not match" in err2, err2)
    finish()


def test_update_install_failure_reports_rollback_hint() -> None:
    print("groundwork_update.py — when the fetched setup.sh itself fails, update reports it and points at rollback")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        mod.VERSION_PATH = tmp / "VERSION"
        mod.VERSION_PATH.write_text("3.1.0\n")
        mod.INSTALLED_SETUP_SH = tmp / "installed-setup.sh"
        mod.INSTALLED_SETUP_SH.write_text("#!/bin/sh\nexit 0\n")
        mod.SETTINGS_JSON = tmp / "no-settings.json"
        mod.REPORT_JSON = tmp / "no-report.json"

        capture_log = tmp / "capture.log"
        fake_setup = tmp / "fake-setup-src.sh"
        _stub_setup_sh(fake_setup, capture_log, mod.VERSION_PATH, "3.1.4", exit_code=7)
        tarball = _make_tarball("top", {
            "install.sh": b"x",
            "setup.sh": fake_setup.read_bytes(),
            "CHANGELOG.md": b"## 3.1.4\n",
        })
        mod._http_json = lambda url: {"tag_name": "v3.1.4", "draft": False, "prerelease": False, "tarball_url": "x"}
        mod._http_bytes = lambda url: tarball

        rc, _, err = _capture_call(mod.cmd_update, _UpdateArgs())
        check("a failing installer's exit code is propagated, not swallowed", rc == 7, rc)
        check("a failed update points the user at 'groundwork rollback'", "rollback" in err, err)
    finish()


def test_update_download_and_extract_failures_are_clean() -> None:
    print("groundwork_update.py — a network failure mid-download, or a corrupt archive, fails clean")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        mod.VERSION_PATH = tmp / "VERSION"
        mod.VERSION_PATH.write_text("3.1.0\n")
        mod.INSTALLED_SETUP_SH = tmp / "installed-setup.sh"
        mod.INSTALLED_SETUP_SH.write_text("#!/bin/sh\nexit 0\n")
        mod.SETTINGS_JSON = tmp / "no-settings.json"
        mod.REPORT_JSON = tmp / "no-report.json"
        mod._http_json = lambda url: {"tag_name": "v3.1.4", "draft": False, "prerelease": False, "tarball_url": "x"}

        def fail_download(url):
            raise OSError("connection reset")
        mod._http_bytes = fail_download
        rc, _, err = _capture_call(mod.cmd_update, _UpdateArgs())
        check("a download failure is a clean, non-zero error", rc != 0 and "download" in err.lower(), err)

        mod._http_bytes = lambda url: b"this is not a valid gzip tarball"
        rc2, _, err2 = _capture_call(mod.cmd_update, _UpdateArgs())
        check("a corrupt/unextractable archive is a clean, non-zero error",
              rc2 != 0 and "extract" in err2.lower(), err2)
    finish()


class _RollbackArgs:
    def __init__(self, version=None):
        self.version = version


def test_urlopen_cert_fallback_retries_only_on_cert_failure() -> None:
    print("groundwork_update.py — SSL cert-verification fallback: retries with certifi's bundle "
          "only on an actual certificate-verification failure, never on an unrelated network error, "
          "and never swallows the original error when certifi isn't installed")
    mod = load_module()
    real_urlopen = urllib.request.urlopen

    def cert_error():
        return urllib.error.URLError(
            ssl.SSLCertVerificationError(1, "certificate verify failed: unable to get local issuer certificate"))

    # Case 1: cert failure on first attempt, succeeds on retry -> the retry must pass a context kwarg
    # (proof it actually used the certifi-backed SSLContext, not a bare retry of the same call).
    calls = []

    def fake_urlopen_cert_then_ok(req, timeout=None, context=None):
        calls.append(context)
        if len(calls) == 1:
            raise cert_error()
        return "ok"

    urllib.request.urlopen = fake_urlopen_cert_then_ok
    try:
        result = mod._urlopen_with_cert_fallback(object(), 5)
        check("cert-verification failure retries once and succeeds", result == "ok", result)
        check("first attempt uses the interpreter's own default context (no explicit context)",
              calls[0] is None, calls)
        check("retry passes an explicit SSLContext (the certifi-backed fallback)",
              len(calls) == 2 and isinstance(calls[1], ssl.SSLContext), calls)
    finally:
        urllib.request.urlopen = real_urlopen

    # Case 2: a non-cert URLError must never be retried — it propagates on the first failure.
    attempts = []

    def fake_urlopen_other_error(req, timeout=None, context=None):
        attempts.append(1)
        raise urllib.error.URLError("Name or service not known")

    urllib.request.urlopen = fake_urlopen_other_error
    try:
        raised = False
        try:
            mod._urlopen_with_cert_fallback(object(), 5)
        except urllib.error.URLError:
            raised = True
        check("a non-certificate URLError is never retried", raised and len(attempts) == 1, attempts)
    finally:
        urllib.request.urlopen = real_urlopen

    # Case 3: cert failure but certifi is unavailable -> the original error re-raises unchanged,
    # never hidden and never a different, more confusing error.
    def fake_urlopen_cert_only(req, timeout=None, context=None):
        raise cert_error()

    urllib.request.urlopen = fake_urlopen_cert_only
    real_certifi = sys.modules.get("certifi", "__absent__")
    sys.modules["certifi"] = None  # forces `import certifi` to raise ImportError
    try:
        raised = False
        try:
            mod._urlopen_with_cert_fallback(object(), 5)
        except urllib.error.URLError as e:
            raised = isinstance(e.reason, ssl.SSLCertVerificationError)
        check("without certifi installed, the original cert error re-raises unchanged (never hidden)", raised)
    finally:
        urllib.request.urlopen = real_urlopen
        if real_certifi == "__absent__":
            del sys.modules["certifi"]
        else:
            sys.modules["certifi"] = real_certifi
    finish()


def test_rollback_not_installed_fails_clean() -> None:
    print("groundwork_update.py — rollback on an uninstalled Groundwork fails clean")
    mod = load_module()
    mod.INSTALLED_SETUP_SH = Path(tempfile.mkdtemp()) / "does-not-exist.sh"
    rc, _, err = _capture_call(mod.cmd_rollback, _RollbackArgs())
    check("rollback with no installed setup.sh refuses cleanly", rc != 0 and "installed" in err, err)
    finish()


def test_rollback_dispatches_to_installed_setup_sh() -> None:
    print("groundwork_update.py — rollback dispatches to the installed setup.sh --rollback, "
          "reusing its existing backup/restore mechanism rather than reimplementing one")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        capture_log = tmp / "capture.log"
        stub = tmp / "installed-setup.sh"
        stub.write_text(f'#!/bin/sh\necho "$@" > {capture_log}\nexit 0\n')
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        mod.INSTALLED_SETUP_SH = stub

        rc, _, _ = _capture_call(mod.cmd_rollback, _RollbackArgs())
        check("rollback with no --version exits 0", rc == 0, rc)
        check("rollback with no --version dispatches bare --rollback (latest backup)",
              capture_log.read_text().strip() == "--rollback", capture_log.read_text())

        mod.BACKUP_ROOT = tmp / "backups"
        mod.BACKUP_ROOT.mkdir()
        backup_dir = _write_backup(mod.BACKUP_ROOT, "groundwork-20260101", "3.1.0")
        rc2, _, _ = _capture_call(mod.cmd_rollback, _RollbackArgs(version="3.1.0"))
        check("rollback --version resolves the matching backup and passes it explicitly",
              f"--rollback {backup_dir}" == capture_log.read_text().strip(), capture_log.read_text())

        rc3, _, err3 = _capture_call(mod.cmd_rollback, _RollbackArgs(version="9.9.9"))
        check("rollback --version with no matching backup refuses cleanly, never falls back to 'latest'",
              rc3 != 0 and "no backup" in err3, err3)
    finish()


if __name__ == "__main__":
    for fn in (test_semver_tuple, test_latest_release_rejects_non_stable,
               test_find_release_validates_against_published_list_only, test_safe_extract_rejects_path_traversal,
               test_find_backup_for_version, test_check_is_non_mutating_and_reports_honestly,
               test_preservation_reads, test_update_rejects_check_and_version_combo,
               test_update_not_installed_fails_clean, test_update_already_on_target_is_noop,
               test_update_end_to_end_preserves_schedule_profile_teams,
               test_update_declines_profile_flag_when_none_set,
               test_update_refuses_incomplete_or_mismatched_archive,
               test_update_install_failure_reports_rollback_hint,
               test_update_download_and_extract_failures_are_clean,
               test_urlopen_cert_fallback_retries_only_on_cert_failure,
               test_rollback_not_installed_fails_clean, test_rollback_dispatches_to_installed_setup_sh):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
