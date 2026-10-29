"""OS sandbox for the grader (design B9). Hidden tests import and run agent-written code, so they never run with the
owner's privileges: no network, read-only system directories, the run's workspace as the only writable path, no home,
repository or other runs, and a cleared environment.

- Linux: bubblewrap (`bwrap --unshare-all`).
- macOS: `sandbox-exec` with a deny-by-default profile, OFF by default (fail closed). It has not been verified on a
  real Mac, and code under test could ask system services (LaunchServices `open`, `osascript`, the pasteboard) to
  act outside the sandbox. Enable it only with GW_BENCH_MACOS_GRADER=verified, after the isolation check, which then
  also probes `open`, `osascript` and `pbpaste`, has passed on that Mac. Until then grade in Linux.
- Anything else: refuse (fail closed).

`isolation_check()` is the deterministic regression: a test that must fail to read a host file, open a network
connection or write outside the workspace, and must succeed at writing inside it and importing pytest and yaml.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SYSTEM_DIRS = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32", "/opt")
SANDBOX_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC", "USER": "bench",
               "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"}


class SandboxUnavailable(RuntimeError):
    pass


def kind() -> str | None:
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return "bwrap"
    if sys.platform == "darwin" and shutil.which("sandbox-exec") and \
            os.environ.get("GW_BENCH_MACOS_GRADER") == "verified":
        return "sandbox-exec"
    return None


def _python_dirs() -> list[str]:
    """Where the grader's Python, pytest and PyYAML live, so they stay importable (read-only) inside the sandbox."""
    dirs = {sys.prefix, sys.base_prefix, os.path.dirname(os.path.realpath(sys.executable))}
    for mod in ("pytest", "_pytest", "pluggy", "iniconfig", "yaml"):
        try:
            m = __import__(mod)
            dirs.add(os.path.dirname(os.path.dirname(os.path.realpath(m.__file__))))
        except ImportError:
            pass
    return sorted(dirs)


def _bwrap(ws: Path, cmd: list[str], cwd: Path) -> list[str]:
    a = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv"]
    for k, v in {**SANDBOX_ENV, "HOME": "/tmp/home"}.items():
        a += ["--setenv", k, v]
    bound = []
    for d in SYSTEM_DIRS:
        if os.path.islink(d):
            a += ["--symlink", os.readlink(d), d]
        elif os.path.isdir(d):
            a += ["--ro-bind", d, d]
            bound.append(d)
    for d in _python_dirs():
        if os.path.isdir(d) and not any(d == b or d.startswith(b + "/") for b in bound):
            a += ["--ro-bind", d, d]
    a += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/tmp/home",
          "--bind", str(ws), str(ws), "--chdir", str(cwd)]
    return a + cmd


def _profile(ws: Path) -> str:
    reads = ["/usr", "/bin", "/sbin", "/System", "/Library", "/opt/homebrew", "/private/etc", "/private/var/db/timezone",
             "/dev", *_python_dirs()]
    sub = " ".join(f'(subpath "{os.path.realpath(r)}")' for r in reads)
    w = os.path.realpath(ws)
    py = os.path.realpath(sys.executable)
    return f"""(version 1)
(deny default)
(allow process-fork signal sysctl-read ipc-posix-shm)
(allow process-exec (literal "{py}") (subpath "/bin") (literal "/usr/bin/env"))
(allow mach-lookup (global-name "com.apple.system.opendirectoryd.libinfo") (global-name "com.apple.system.logger"))
(allow file-read-metadata)
(allow file-read* (literal "/") {sub})
(allow file-read* file-write* (subpath "{w}"))
(allow file-write* (literal "/dev/null"))
(deny network*)
"""


def wrap(ws: Path, cmd: list[str], cwd: Path) -> tuple[list[str], dict]:
    """The command to run instead of `cmd`, and the environment to run it with."""
    k = kind()
    if k == "bwrap":
        return _bwrap(ws.resolve(), cmd, cwd.resolve()), {"PATH": "/usr/bin:/bin"}
    if k == "sandbox-exec":
        return ["sandbox-exec", "-p", _profile(ws), *cmd], {**SANDBOX_ENV, "HOME": str(ws.resolve())}
    raise SandboxUnavailable("no grader sandbox: install bubblewrap (Linux) or run on macOS with sandbox-exec")


ISOLATION_TEST = '''import os
import socket
from pathlib import Path

HOST_FILE = {host_file!r}
REPO_FILE = {repo_file!r}
OUTSIDE_DIR = {outside_dir!r}
OWNER_HOME = {owner_home!r}


def test_host_file_is_unreadable():
    try:
        Path(HOST_FILE).read_text()
    except OSError:
        return
    raise AssertionError("read a host file outside the workspace")


def test_owner_home_is_unreadable():
    try:
        names = os.listdir(OWNER_HOME)
    except OSError:
        return
    assert not names, "listed the owner's home directory"


def test_network_is_blocked():
    for host, port in (("1.1.1.1", 443), ("example.com", 443)):
        try:
            socket.create_connection((host, port), timeout=5).close()
        except OSError:
            continue
        raise AssertionError(f"opened a connection to {{host}}:{{port}}")


def test_write_outside_is_blocked():
    try:
        Path(OUTSIDE_DIR, "escaped.txt").write_text("x")
    except OSError:
        return
    raise AssertionError("wrote outside the workspace")


def test_no_escape_through_system_services():
    import shutil
    import subprocess
    import sys
    if sys.platform != "darwin":
        return
    for cmd in (["open", "-g", "-a", "Terminal", "/"], ["osascript", "-e", "return 1"], ["pbpaste"]):
        if not shutil.which(cmd[0]):
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        assert r.returncode != 0, f"{{cmd[0]}} worked inside the sandbox"


def test_repository_is_unreadable():
    try:
        Path(REPO_FILE).read_text()
    except OSError:
        return
    raise AssertionError("read a file in the benchmark repository")


def test_positive_controls():
    Path(__file__).with_name("inside.txt").write_text("ok")
    import pytest  # noqa: F401
    import yaml  # noqa: F401
'''


def isolation_check(timeout_s: int = 120, sandboxed: bool = True) -> tuple[bool, str]:
    """Run the isolation test through the same sandboxed path the grader uses. True only if every check passed and
    nothing escaped. `sandboxed=False` is the negative control for the unit test: without the sandbox the same test
    must fail, which shows the check can detect a leak."""
    if sandboxed and kind() is None:
        return False, "no grader sandbox available"
    with tempfile.TemporaryDirectory(prefix="gw-grader-iso-") as tmp:
        root = Path(tmp).resolve()
        outside = root / "outside"
        outside.mkdir()
        host_file = outside / "host-secret.txt"
        host_file.write_text("GWGRADER-HOST-SECRET-5150\n")
        ws = root / "ws"
        dest = ws / ".bench_hidden"
        dest.mkdir(parents=True)
        (dest / "test_isolation.py").write_text(ISOLATION_TEST.format(
            host_file=str(host_file), outside_dir=str(outside), owner_home=str(Path.home()),
            repo_file=str(Path(__file__).resolve().parent / "FROZEN.json")))
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", os.devnull, "--rootdir", str(dest),
               "--confcutdir", str(dest), str(dest)]
        argv, env = wrap(ws, cmd, dest) if sandboxed else (cmd, {"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
        try:
            r = subprocess.run(argv, cwd=dest, env=env, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return False, "isolation check timed out"
        out = (r.stdout + r.stderr)[-2000:]
        escaped = (outside / "escaped.txt").exists()
        ok = r.returncode == 0 and "7 passed" in out and not escaped and (dest / "inside.txt").exists()
        return ok, out
