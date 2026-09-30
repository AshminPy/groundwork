#!/usr/bin/env python3
"""Deterministic checks for the groundwork CLI (scripts/groundwork_cli.py) and its installation
via install.sh/uninstall.sh — Phase 1 of openspec/changes/groundwork-cli-foundation/.

Real subprocess calls throughout (no mocking of the scripts under test): a real install.sh run
against stub claude/openspec/npm binaries (same pattern as tests/test_setup.py's Box), a real
uninstall.sh run, real PATH resolution via `bash -lc`. Both CLAUDE_CONFIG_DIR and HOME are
redirected to a disposable temp directory for every test — the real $HOME's shell rc files are
never touched.

Run: python3 tests/test_groundwork_cli.py   (or: python3 -m pytest tests -q)
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "scripts" / "groundwork_cli.py"
INSTALL = REPO_ROOT / "install.sh"
UNINSTALL = REPO_ROOT / "uninstall.sh"

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


class Env:
    """An isolated HOME + CLAUDE_CONFIG_DIR + stub claude/openspec/npm on PATH, so install.sh/
    uninstall.sh run for real without touching the real filesystem outside the temp root."""

    def __init__(self, root: Path):
        self.root = root
        self.home = root / "home"
        self.cfg = root / "home" / ".claude"
        self.home.mkdir(parents=True, exist_ok=True)
        bin_dir = root / "stubbin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "claude").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "2.1.258 (Claude Code)";; plugin) echo "ecc@ecc";; *) exit 0;; esac\n')
        (bin_dir / "openspec").write_text('#!/usr/bin/env bash\ncase "$1" in --version) echo "1.12.0";; *) exit 0;; esac\n')
        (bin_dir / "npm").write_text('#!/usr/bin/env bash\nexit 0\n')
        for f in ("claude", "openspec", "npm"):
            os.chmod(bin_dir / f, 0o755)
        self.env = dict(os.environ, HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.cfg),
                         PATH=f"{bin_dir}:{os.environ['PATH']}", NODE_USE_SYSTEM_CA="0")

    def run_install(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(INSTALL), *args], capture_output=True, text=True,
                              env=self.env, timeout=120)

    def run_uninstall(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(UNINSTALL), *args], capture_output=True, text=True,
                              env=self.env, timeout=120)

    def run_cli(self, *args) -> subprocess.CompletedProcess:
        gw = self.cfg / "groundwork" / "bin" / "groundwork"
        return subprocess.run(["python3", str(gw), *args], capture_output=True, text=True,
                              env=self.env, timeout=30)

    def run_in_login_shell(self, shell_cmd: str) -> subprocess.CompletedProcess:
        """A fresh subshell with a minimal PATH (no repo/stub dirs), sourcing the user's rc file
        the way a real new terminal would — proves PATH registration actually works, not just
        that the files exist."""
        env = dict(self.env)
        env["PATH"] = "/usr/bin:/bin"
        return subprocess.run(["bash", "-lc", shell_cmd], capture_output=True, text=True, env=env, timeout=30)


def test_cli_help_and_no_args_deterministic() -> None:
    print("groundwork_cli.py — --help / no-args / unknown flag (no install needed)")
    r = subprocess.run(["python3", str(CLI), "--help"], capture_output=True, text=True, timeout=15)
    check("--help exits 0", r.returncode == 0, r.stderr)
    check("--help lists version and doctor", "version" in r.stdout and "doctor" in r.stdout, r.stdout)

    r_no_args = subprocess.run(["python3", str(CLI)], capture_output=True, text=True, timeout=15)
    check("no-args exits 0", r_no_args.returncode == 0, r_no_args.stderr)
    check("no-args prints the same help", r_no_args.stdout == r.stdout, r_no_args.stdout[:200])

    r_bad = subprocess.run(["python3", str(CLI), "bogus-subcommand"], capture_output=True, text=True, timeout=15)
    check("unknown subcommand is a real error, not exit 0", r_bad.returncode != 0, f"rc={r_bad.returncode}")
    finish()


def test_version_reads_authoritative_source() -> None:
    print("groundwork_cli.py — version reads $CLAUDE_CONFIG_DIR/groundwork/VERSION")
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Path(tmpdir) / "cfg"
        (cfg / "groundwork").mkdir(parents=True)
        (cfg / "groundwork" / "VERSION").write_text("9.9.9\n")
        r = subprocess.run(["python3", str(CLI), "version"], capture_output=True, text=True,
                           env={**os.environ, "CLAUDE_CONFIG_DIR": str(cfg)}, timeout=15)
        check("version exits 0 when VERSION file exists", r.returncode == 0, r.stderr)
        check("version prints the exact VERSION file content", "9.9.9" in r.stdout, r.stdout)

        missing = Path(tmpdir) / "missing"
        r2 = subprocess.run(["python3", str(CLI), "version"], capture_output=True, text=True,
                            env={**os.environ, "CLAUDE_CONFIG_DIR": str(missing)}, timeout=15)
        check("version fails (not exit 0) when Groundwork isn't installed", r2.returncode != 0, r2.stdout)
    finish()


def shutil_which(cmd):
    import shutil
    return shutil.which(cmd)


def test_doctor_dispatches_not_reimplements() -> None:
    print("groundwork_cli.py — doctor dispatches to the installed setup.sh --doctor, byte-identical")
    if shutil_which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        e = Env(Path(tmpdir))
        r = e.run_install()
        check("install.sh exits 0", r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:])

        # Direct: run the installed setup.sh copy's --doctor mode exactly as groundwork_cli.py does.
        installed_setup = e.cfg / "groundwork" / "bin" / "setup.sh"
        check("install.sh copies setup.sh into the installed bin dir", installed_setup.is_file())
        direct = subprocess.run(["bash", str(installed_setup), "--doctor"], capture_output=True, text=True,
                                env=e.env, timeout=60)

        cli_doctor = e.run_cli("doctor")
        check("groundwork doctor exit code matches the installed setup.sh --doctor directly",
              cli_doctor.returncode == direct.returncode, f"cli={cli_doctor.returncode} direct={direct.returncode}")
        check("groundwork doctor stdout is byte-identical to the installed setup.sh --doctor",
              cli_doctor.stdout == direct.stdout, cli_doctor.stdout[:500] + "\n---\n" + direct.stdout[:500])
    finish()


def test_install_uninstall_registers_and_removes_path() -> None:
    print("groundwork CLI — install.sh registers PATH idempotently, uninstall.sh removes exactly what was added")
    if shutil_which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        e = Env(Path(tmpdir))
        # Seed a pre-existing .bashrc with unrelated content, and deliberately do NOT create .zshrc,
        # to prove (a) unrelated content survives untouched and (b) install.sh never creates an rc
        # file for a shell that doesn't have one.
        bashrc = e.home / ".bashrc"
        bashrc.write_text("# my own bashrc\nexport MY_VAR=1\n")
        zshrc = e.home / ".zshrc"
        check("precondition: .zshrc does not exist yet", not zshrc.exists())

        r = e.run_install()
        check("install.sh exits 0", r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:])

        gw_exe = e.cfg / "groundwork" / "bin" / "groundwork"
        env_script = e.cfg / "groundwork" / "env"
        check("groundwork executable installed", gw_exe.is_file() and os.access(gw_exe, os.X_OK))
        check("groundwork/env PATH helper installed", env_script.is_file())

        bashrc_text = bashrc.read_text()
        check("unrelated .bashrc content survives untouched", "export MY_VAR=1" in bashrc_text, bashrc_text)
        check(".bashrc gets the marked PATH-registration block",
              "groundwork CLI PATH" in bashrc_text and str(env_script) in bashrc_text, bashrc_text)
        check(".zshrc is still not created (install.sh never creates an rc file that didn't exist)",
              not zshrc.exists())

        # Idempotency: re-running install must not duplicate the block.
        r2 = e.run_install()
        check("second install.sh run exits 0", r2.returncode == 0, r2.stdout[-1000:] + r2.stderr[-500:])
        bashrc_text_2 = bashrc.read_text()
        check("re-running install does not duplicate the marked block",
              bashrc_text_2.count("groundwork CLI PATH (added by Groundwork's install.sh)") == 1, bashrc_text_2)

        # Real PATH resolution: a fresh login shell with a minimal PATH, sourcing .bashrc the way a
        # real new terminal would, must resolve `groundwork` on PATH.
        result = e.run_in_login_shell(f"source {bashrc} >/dev/null 2>&1; command -v groundwork")
        check("a fresh shell sourcing .bashrc resolves `groundwork` on PATH",
              result.returncode == 0 and str(gw_exe) in result.stdout,
              f"rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}")

        # Uninstall: exact removal, rest of .bashrc preserved.
        r3 = e.run_uninstall()
        check("uninstall.sh exits 0", r3.returncode == 0, r3.stdout[-1000:] + r3.stderr[-500:])
        check("groundwork executable removed", not gw_exe.exists())
        check("groundwork/env removed", not env_script.exists())
        bashrc_after = bashrc.read_text()
        check("marked block removed from .bashrc", "groundwork CLI PATH" not in bashrc_after, bashrc_after)
        check("unrelated .bashrc content still survives after uninstall", "export MY_VAR=1" in bashrc_after, bashrc_after)

        result2 = e.run_in_login_shell(f"source {bashrc} >/dev/null 2>&1; command -v groundwork")
        check("after uninstall, a fresh shell no longer resolves `groundwork`", result2.returncode != 0, result2.stdout)
    finish()


if __name__ == "__main__":
    for t in (test_cli_help_and_no_args_deterministic, test_version_reads_authoritative_source,
              test_doctor_dispatches_not_reimplements, test_install_uninstall_registers_and_removes_path):
        try:
            t()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
