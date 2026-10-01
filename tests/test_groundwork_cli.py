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


def test_integrations_dispatches_not_reimplements() -> None:
    print("groundwork_cli.py — integrations forwards verbatim to the installed groundwork_integrations.py")
    if shutil_which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        e = Env(Path(tmpdir))
        r = e.run_install()
        check("install.sh exits 0", r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:])

        installed_integrations = e.cfg / "groundwork" / "bin" / "groundwork_integrations.py"
        check("install.sh copies groundwork_integrations.py into the installed bin dir",
              installed_integrations.is_file())

        for subargs in (["list"], ["show", "github"], ["doctor", "github"]):
            direct = subprocess.run(["python3", str(installed_integrations), *subargs],
                                    capture_output=True, text=True, env=e.env, timeout=30)
            via_cli = e.run_cli("integrations", *subargs)
            check(f"groundwork integrations {' '.join(subargs)} exit code matches direct invocation",
                  via_cli.returncode == direct.returncode,
                  f"cli={via_cli.returncode} direct={direct.returncode}")
            check(f"groundwork integrations {' '.join(subargs)} stdout is byte-identical to direct invocation",
                  via_cli.stdout == direct.stdout, via_cli.stdout[:300] + "\n---\n" + direct.stdout[:300])

        # --help must reach the installed script's own real help text, not a stub — this is the
        # specific argparse REMAINDER + -h interaction (https://bugs.python.org/issue9334) that
        # main() works around by intercepting "integrations" before argparse ever sees it.
        help_direct = subprocess.run(["python3", str(installed_integrations), "--help"],
                                     capture_output=True, text=True, env=e.env, timeout=30)
        help_via_cli = e.run_cli("integrations", "--help")
        check("groundwork integrations --help reaches the installed script's real help text, byte-identical",
              help_via_cli.stdout == help_direct.stdout and help_via_cli.returncode == help_direct.returncode,
              help_via_cli.stdout[:300])
        check("groundwork integrations --help is not the bare argparse stub",
              "Integration Catalog" in help_via_cli.stdout, help_via_cli.stdout)

        # Unknown integration name: a real, non-zero error, no traceback, passed through untouched.
        bad = e.run_cli("integrations", "show", "totally-not-a-real-integration")
        check("unknown integration name via the CLI returns non-zero, no traceback",
              bad.returncode == 1 and "Traceback" not in bad.stderr, bad.stdout + bad.stderr)

        # Top-level help still lists "integrations" as a subcommand.
        top_help = e.run_cli("--help")
        check("groundwork --help lists 'integrations'", "integrations" in top_help.stdout, top_help.stdout)
    finish()


def test_update_rollback_dispatches_not_reimplements() -> None:
    print("groundwork_cli.py — update/rollback forward verbatim to the installed groundwork_update.py "
          "(Phase 3, openspec/changes/groundwork-update-lifecycle/) — network-free paths only, so this "
          "stays a deterministic dispatch check, not a live-release test")
    if shutil_which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        e = Env(Path(tmpdir))
        r = e.run_install()
        check("install.sh exits 0", r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:])

        installed_update = e.cfg / "groundwork" / "bin" / "groundwork_update.py"
        check("install.sh copies groundwork_update.py into the installed bin dir", installed_update.is_file())

        # --help for both subcommands: no network involved, argparse.REMAINDER + -h interception
        # bug (https://bugs.python.org/issue9334) — same reasoning already fixed for "integrations".
        for name in ("update", "rollback"):
            help_direct = subprocess.run(["python3", str(installed_update), name, "--help"],
                                         capture_output=True, text=True, env=e.env, timeout=30)
            help_via_cli = e.run_cli(name, "--help")
            check(f"groundwork {name} --help reaches the installed script's real help text, byte-identical",
                  help_via_cli.stdout == help_direct.stdout and help_via_cli.returncode == help_direct.returncode,
                  help_via_cli.stdout[:300])

        # A deterministic, network-free error path: "--check" and "--version" together is rejected
        # before any HTTP call is made, so the dispatched output is byte-identical without needing
        # a live GitHub API call.
        direct_combo = subprocess.run(["python3", str(installed_update), "update", "--check", "--version", "9.9.9"],
                                      capture_output=True, text=True, env=e.env, timeout=30)
        via_cli_combo = e.run_cli("update", "--check", "--version", "9.9.9")
        check("groundwork update --check --version X exit code matches direct invocation",
              via_cli_combo.returncode == direct_combo.returncode,
              f"cli={via_cli_combo.returncode} direct={direct_combo.returncode}")
        check("groundwork update --check --version X stderr is byte-identical to direct invocation",
              via_cli_combo.stderr == direct_combo.stderr, via_cli_combo.stderr[:300] + "\n---\n" + direct_combo.stderr[:300])

        # rollback --version with no matching backup: also deterministic and network-free.
        direct_rb = subprocess.run(["python3", str(installed_update), "rollback", "--version", "9.9.9"],
                                   capture_output=True, text=True, env=e.env, timeout=30)
        via_cli_rb = e.run_cli("rollback", "--version", "9.9.9")
        check("groundwork rollback --version X (no matching backup) exit code matches direct invocation",
              via_cli_rb.returncode == direct_rb.returncode,
              f"cli={via_cli_rb.returncode} direct={direct_rb.returncode}")
        check("groundwork rollback --version X (no matching backup) stderr is byte-identical to direct invocation",
              via_cli_rb.stderr == direct_rb.stderr, via_cli_rb.stderr[:300] + "\n---\n" + direct_rb.stderr[:300])

        # Top-level help lists both new subcommands.
        top_help = e.run_cli("--help")
        check("groundwork --help lists 'update'", "update" in top_help.stdout, top_help.stdout)
        check("groundwork --help lists 'rollback'", "rollback" in top_help.stdout, top_help.stdout)
    finish()


def test_routines_dispatches_not_reimplements() -> None:
    print("groundwork_cli.py — routines forwards verbatim to the installed groundwork_routines.py "
          "(Phase 4, openspec/changes/groundwork-routine-cli-ux/)")
    if shutil_which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        e = Env(Path(tmpdir))
        r = e.run_install()
        check("install.sh exits 0", r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:])

        installed_routines = e.cfg / "groundwork" / "bin" / "groundwork_routines.py"
        check("install.sh copies groundwork_routines.py into the installed bin dir", installed_routines.is_file())
        check("install.sh also copies groundwork_config.py alongside it (groundwork_routines.py imports it)",
              (e.cfg / "groundwork" / "bin" / "groundwork_config.py").is_file())

        for subargs in (["list"], ["doctor"], ["doctor", "news"]):
            direct = subprocess.run(["python3", str(installed_routines), *subargs],
                                    capture_output=True, text=True, env=e.env, timeout=30)
            via_cli = e.run_cli("routines", *subargs)
            check(f"groundwork routines {' '.join(subargs)} exit code matches direct invocation",
                  via_cli.returncode == direct.returncode,
                  f"cli={via_cli.returncode} direct={direct.returncode}")
            check(f"groundwork routines {' '.join(subargs)} stdout is byte-identical to direct invocation",
                  via_cli.stdout == direct.stdout, via_cli.stdout[:300] + "\n---\n" + direct.stdout[:300])

        # --help must reach the installed script's own real help text — the same argparse
        # REMAINDER + -h interaction (https://bugs.python.org/issue9334) that main() works around
        # by intercepting "routines" before argparse ever sees it.
        help_direct = subprocess.run(["python3", str(installed_routines), "--help"],
                                     capture_output=True, text=True, env=e.env, timeout=30)
        help_via_cli = e.run_cli("routines", "--help")
        check("groundwork routines --help reaches the installed script's real help text, byte-identical",
              help_via_cli.stdout == help_direct.stdout and help_via_cli.returncode == help_direct.returncode,
              help_via_cli.stdout[:300])
        check("groundwork routines --help is not a bare stub",
              "Routines" in help_via_cli.stdout, help_via_cli.stdout)

        # Unknown routine name: a real, non-zero error, no traceback, passed through untouched.
        bad = e.run_cli("routines", "doctor", "not-a-real-routine")
        check("unknown routine name via the CLI returns non-zero, no traceback",
              bad.returncode != 0 and "Traceback" not in bad.stderr, bad.stdout + bad.stderr)

        # Top-level help still lists "routines" as a subcommand.
        top_help = e.run_cli("--help")
        check("groundwork --help lists 'routines'", "routines" in top_help.stdout, top_help.stdout)
    finish()


def test_statusline_dispatches_not_reimplements() -> None:
    print("groundwork_cli.py — statusline forwards verbatim to the installed groundwork_statusline.py's "
          "own 'config get/set/unset/list' CLI")
    if shutil_which("bash") is None:
        print("  skip: bash not available")
        return
    with tempfile.TemporaryDirectory() as tmpdir:
        e = Env(Path(tmpdir))
        r = e.run_install()
        check("install.sh exits 0", r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:])

        installed_statusline = e.cfg / "groundwork" / "bin" / "groundwork_statusline.py"
        check("install.sh copies groundwork_statusline.py into the installed bin dir", installed_statusline.is_file())

        for subargs in (["config", "list"], ["config", "set", "integrations_min_state", "connected"],
                        ["config", "get", "integrations_min_state"], ["config", "unset", "integrations_min_state"]):
            direct = subprocess.run(["python3", str(installed_statusline), *subargs],
                                    capture_output=True, text=True, env=e.env, timeout=30)
            via_cli = e.run_cli("statusline", *subargs)
            check(f"groundwork statusline {' '.join(subargs)} exit code matches direct invocation",
                  via_cli.returncode == direct.returncode,
                  f"cli={via_cli.returncode} direct={direct.returncode}")
            check(f"groundwork statusline {' '.join(subargs)} stdout is byte-identical to direct invocation",
                  via_cli.stdout == direct.stdout, via_cli.stdout[:300] + "\n---\n" + direct.stdout[:300])

        # --help must reach the installed script's own real help text, same REMAINDER+-h workaround
        # as integrations/update/rollback/routines (https://bugs.python.org/issue9334).
        help_direct = subprocess.run(["python3", str(installed_statusline), "config", "--help"],
                                     capture_output=True, text=True, env=e.env, timeout=30)
        help_via_cli = e.run_cli("statusline", "config", "--help")
        check("groundwork statusline config --help reaches the installed script's real help text, byte-identical",
              help_via_cli.stdout == help_direct.stdout and help_via_cli.returncode == help_direct.returncode,
              help_via_cli.stdout[:300])

        # A bare "groundwork statusline" (no further args) must never hang waiting on stdin — the
        # installed script's zero-argv path is reserved for Claude Code's own statusLine
        # invocation. cmd_statusline() short-circuits this before any subprocess is spawned.
        bare = e.run_cli("statusline")
        check("bare 'groundwork statusline' returns promptly with a non-zero, informative exit — never hangs",
              bare.returncode != 0 and "config" in (bare.stdout + bare.stderr), bare.stdout + bare.stderr)

        # Unknown key via set: a real, non-zero error, no traceback, passed through untouched.
        bad = e.run_cli("statusline", "config", "set", "not_a_real_key", "x")
        check("unknown statusline config key via the CLI returns non-zero, no traceback",
              bad.returncode != 0 and "Traceback" not in bad.stderr, bad.stdout + bad.stderr)

        # Top-level help still lists "statusline" as a subcommand.
        top_help = e.run_cli("--help")
        check("groundwork --help lists 'statusline'", "statusline" in top_help.stdout, top_help.stdout)
    finish()


if __name__ == "__main__":
    for t in (test_cli_help_and_no_args_deterministic, test_version_reads_authoritative_source,
              test_doctor_dispatches_not_reimplements, test_install_uninstall_registers_and_removes_path,
              test_integrations_dispatches_not_reimplements, test_update_rollback_dispatches_not_reimplements,
              test_routines_dispatches_not_reimplements, test_statusline_dispatches_not_reimplements):
        try:
            t()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
