"""Deterministic validation: the orchestrator, not the worker, decides whether a task passed."""
from __future__ import annotations

import hashlib
import os
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path

CHECK_TIMEOUT_S = 600
OUTPUT_TAIL = 4000
# Never changed by a worker, whatever the write scope: repository internals, Claude/Groundwork config, CI. Compared
# case-insensitively (macOS file systems usually are).
FORBIDDEN_PREFIXES = (".git/", ".claude/", ".github/workflows/")
FORBIDDEN_FILES = (".mcp.json", "claude.md", ".gitmodules", ".gitattributes", ".git")
# Files a check typically executes or configures. A worker changing them can make a check pass without fixing
# anything, so such a change is reported and the result is never fully VERIFIED.
CHECK_FILE_PATTERNS = re.compile(r"(^|/)(tests?/|test_[^/]*$|[^/]*_test\.[^/]*$|conftest\.py$|makefile$|"
                                 r"package\.json$|pyproject\.toml$|setup\.cfg$|tox\.ini$|noxfile\.py$|pytest\.ini$|"
                                 r"justfile$|\.pre-commit-config\.yaml$)", re.I)
# Removed from a check's environment: checks run code the worker may have written, before anyone reviewed it.
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|COOKIE|SESSION)", re.I)
SECRET_PREFIXES = ("AWS_", "GOOGLE_", "GCLOUD_", "CLOUDSDK_", "AZURE_", "ARM_", "GH_", "GITHUB_", "GITLAB_",
                   "ANTHROPIC_", "OPENAI_", "VAULT_", "DOCKER_", "NPM_", "TF_VAR_")
SECRET_EXACT = ("SSH_AUTH_SOCK", "KUBECONFIG", "GIT_ASKPASS", "SSH_ASKPASS")


def check_env(base: dict | None = None) -> dict:
    env = {k: v for k, v in (os.environ if base is None else base).items()
           if not (SECRET_NAME.search(k) or k.startswith(SECRET_PREFIXES) or k in SECRET_EXACT)}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def run_check(cmd: str, cwd: str, timeout_s: int = CHECK_TIMEOUT_S) -> dict:
    """Run one owner-declared check as an argv list (no shell)."""
    start = time.monotonic()
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return {"cmd": cmd, "exit_code": None, "ok": False, "output_tail": f"cannot parse check: {e}", "duration_s": 0}
    if not argv:
        return {"cmd": cmd, "exit_code": None, "ok": False, "output_tail": "empty check", "duration_s": 0}
    try:
        proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                errors="replace", env=check_env(), start_new_session=True)
    except FileNotFoundError:
        return {"cmd": cmd, "exit_code": 127, "ok": False, "output_tail": f"command not found: {argv[0]}",
                "duration_s": 0}
    try:
        out, _ = proc.communicate(timeout=timeout_s)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        for sig in (signal.SIGTERM, signal.SIGKILL):  # the whole group: test servers a check started go too
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                break
            try:
                proc.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue
        out, code = f"check did not finish within {timeout_s}s", None
    return {"cmd": cmd, "exit_code": code, "ok": code == 0, "output_tail": out[-OUTPUT_TAIL:],
            "duration_s": round(time.monotonic() - start, 2)}


def run_checks(checks: list[str], cwd: str) -> list[dict]:
    return [run_check(c, cwd) for c in checks]


def _git(cwd: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", cwd, "-c", "core.quotepath=off", *args], capture_output=True, text=False,
                          timeout=60, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})


def is_git(path: str) -> bool:
    r = _git(path, "rev-parse", "--is-inside-work-tree")
    return r.returncode == 0 and r.stdout.strip() == b"true"


def fingerprint(path: str) -> str:
    """A hash of the working tree's content, so a read-only run that changed anything is detected."""
    h = hashlib.sha256()
    if is_git(path):
        h.update(_git(path, "diff", "--binary", "HEAD").stdout)
        untracked = _git(path, "ls-files", "--others", "--exclude-standard", "-z").stdout.split(b"\0")
        for rel in sorted(u for u in untracked if u):
            h.update(rel)
            try:
                h.update(hashlib.sha256((Path(path) / rel.decode()).read_bytes()).digest())
            except OSError:
                h.update(b"<unreadable>")
        return h.hexdigest()
    for root, dirs, files in sorted(os.walk(path)):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv"))
        for name in sorted(files):
            p = Path(root) / name
            try:
                st = p.stat()
            except OSError:
                continue
            h.update(f"{p.relative_to(path)}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()


def _z(out: bytes) -> list[str]:
    return [x for x in out.decode(errors="replace").split("\0") if x]


def changed_files(worktree: str, base: str) -> dict:
    """What differs from the worktree's base commit: committed-or-not tracked changes, untracked files, and files a
    .gitignore hides (a hidden .claude/settings.local.json still counts), plus any commits made on top of base."""
    tracked = _z(_git(worktree, "diff", "--name-only", "-z", base).stdout)
    untracked = _z(_git(worktree, "ls-files", "--others", "--exclude-standard", "-z").stdout)
    ignored = _z(_git(worktree, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").stdout)
    commits = _z(_git(worktree, "rev-list", "-z", f"{base}..HEAD").stdout)
    return {"files": sorted(set(tracked + untracked)), "ignored": sorted(set(ignored)), "commits": commits}


def _forbidden(rel: str) -> bool:
    low = rel.casefold()
    return low.startswith(FORBIDDEN_PREFIXES) or low in FORBIDDEN_FILES or low.split("/")[-1] == "claude.md"


def scope_violations(files: list[str], root: str | None = None) -> list[str]:
    """Protected paths, paths that climb out, and (with root) files whose real location is outside the worktree."""
    bad = []
    base = Path(root).resolve() if root else None
    for f in files:
        if _forbidden(f) or ".." in Path(f).parts:
            bad.append(f)
        elif base is not None:
            real = (base / f).resolve()
            if real != base and base not in real.parents:
                bad.append(f)
    return bad


def ignored_violations(ignored: list[str]) -> list[str]:
    """Ignored build output is fine; an ignored file under a protected path is not."""
    return [f for f in ignored if _forbidden(f)]


def check_related(files: list[str], checks: list[str], subdir: str = "") -> list[str]:
    """Changed files that a check runs or configures. Check arguments are relative to the check's working directory,
    which is `subdir` inside the repository; `files` are repository-relative."""
    named = set()
    for c in checks:
        try:
            args = shlex.split(c)[1:]
        except ValueError:
            continue
        for a in args:
            if not a.startswith("-"):
                named.add(os.path.normpath(os.path.join(subdir, a)))
    return [f for f in files if CHECK_FILE_PATTERNS.search(f) or os.path.normpath(f) in named]


_LINE_SUFFIX = re.compile(r"(:\d+(-\d+)?)+$")
_URL = re.compile(r"^[a-z]+://")


def checkable_sources(sources: list[str]) -> list[str]:
    return [s.strip() for s in sources or [] if s.strip() and not _URL.match(s.strip())]


def missing_sources(sources: list[str], root: str) -> list[str]:
    """Cited paths that do not exist inside the workspace. URLs cannot be checked offline and are not counted."""
    missing = []
    base = Path(root).resolve()
    for s in checkable_sources(sources):
        p = (base / _LINE_SUFFIX.sub("", s)).resolve()
        if base not in p.parents or not p.is_file():
            missing.append(s)
    return missing
