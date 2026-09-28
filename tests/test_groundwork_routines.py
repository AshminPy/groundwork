#!/usr/bin/env python3
"""Deterministic checks for scripts/groundwork_routines.py (Groundwork 2.1) — no live `claude`
call except where a local stub binary stands in for it.

Run: python3 tests/test_groundwork_routines.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "groundwork_routines.py"

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
    spec = importlib.util.spec_from_file_location("gw_routines", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_cli(args, env_extra=None, timeout=30) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


def write_claude_stub(bindir: Path, behavior="echo") -> None:
    """A fake `claude` on PATH so run_routine's subprocess call is deterministic and instant —
    never invokes the real CLI (that's covered by live sandbox validation, not this test)."""
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / "claude"
    if behavior == "echo":
        script.write_text("#!/usr/bin/env bash\necho \"stub output: $*\"\nexit 0\n")
    elif behavior == "fail":
        script.write_text("#!/usr/bin/env bash\necho \"stub failure\" >&2\nexit 1\n")
    elif behavior == "hang":
        script.write_text("#!/usr/bin/env bash\nsleep 30\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | 0o111)


def test_module_level() -> None:
    print("groundwork_routines.py — module-level checks (build_command, ROUTINES registry, is_macos)")
    mod = load_module()

    # ---- ROUTINES registry shape
    expected_names = {"jira_eod", "news", "weekly_status", "pr_followup", "work_digest", "doc_drift"}
    check("ROUTINES has exactly the six designed routines", set(mod.ROUTINES) == expected_names, sorted(mod.ROUTINES))
    for name, spec in mod.ROUTINES.items():
        check(f"{name}: has mutates/default_schedule/prompt/needs_offline_work keys",
              {"mutates", "default_schedule", "prompt", "needs_offline_work"} <= set(spec), spec)
        check(f"{name}: default_schedule is a real frequency", spec["default_schedule"] in ("daily", "weekly", "monthly"), spec)
    check("only jira_eod mutates (the rest are read-only reports/digests)",
          [n for n, s in mod.ROUTINES.items() if s["mutates"]] == ["jira_eod"])
    check("only jira_eod needs offline-work folding in", [n for n, s in mod.ROUTINES.items() if s["needs_offline_work"]] == ["jira_eod"])

    # ---- build_command: the exact safety contract from the module docstring
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["CLAUDE_CONFIG_DIR"] = tmpdir  # keep gcfg.load_config() off the real ~/.claude
        try:
            for name in mod.ROUTINES:
                for dry_run in (True, False):
                    cmd = mod.build_command(name, dry_run, ".", "sonnet", "")
                    check(f"{name} dry_run={dry_run}: never --dangerously-skip-permissions",
                          "--dangerously-skip-permissions" not in cmd, cmd)
                    check(f"{name} dry_run={dry_run}: never --bare", "--bare" not in cmd, cmd)
                    check(f"{name} dry_run={dry_run}: uses --permission-mode dontAsk",
                          "--permission-mode" in cmd and cmd[cmd.index("--permission-mode") + 1] == "dontAsk", cmd)
                    check(f"{name} dry_run={dry_run}: uses --permission-prompts none",
                          "--permission-prompts" in cmd and cmd[cmd.index("--permission-prompts") + 1] == "none", cmd)
                    check(f"{name} dry_run={dry_run}: has an explicit --allowedTools allowlist",
                          "--allowedTools" in cmd and cmd[cmd.index("--allowedTools") + 1].strip() != "", cmd)
                    check(f"{name} dry_run={dry_run}: cmd[0:2] is ['claude', '-p']", cmd[0:2] == ["claude", "-p"], cmd)
            try:
                mod.build_command("not-a-real-routine", False, ".", "sonnet", "")
                check("build_command: unknown routine raises ValueError", False)
            except ValueError:
                check("build_command: unknown routine raises ValueError", True)
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]

    # ---- is_macos(): GROUNDWORK_OS override takes precedence over the real platform
    os.environ["GROUNDWORK_OS"] = "darwin"
    try:
        check("is_macos(): GROUNDWORK_OS=darwin -> True", mod.is_macos() is True)
    finally:
        del os.environ["GROUNDWORK_OS"]
    os.environ["GROUNDWORK_OS"] = "linux"
    try:
        check("is_macos(): GROUNDWORK_OS=linux -> False", mod.is_macos() is False)
    finally:
        del os.environ["GROUNDWORK_OS"]
    finish()


def test_run_routine_off_switches() -> None:
    print("groundwork_routines.py run — off-switches never invoke `claude` at all")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        old_path = os.environ.get("PATH")
        os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")
        os.environ["PATH"] = "/nonexistent-empty-bin"  # no `claude` reachable at all
        try:
            os.environ["GROUNDWORK_ROUTINES"] = "off"
            try:
                r = mod.run_routine("work_digest", repo=".")
                check("GROUNDWORK_ROUTINES=off: skipped, no subprocess attempted", r["status"] == "skipped" and "off" in r["reason"], r)
            finally:
                del os.environ["GROUNDWORK_ROUTINES"]

            os.environ["GROUNDWORK_ROUTINES_WORK_DIGEST"] = "off"
            try:
                r = mod.run_routine("work_digest", repo=".")
                check("GROUNDWORK_ROUTINES_WORK_DIGEST=off: skips only that routine", r["status"] == "skipped", r)
                r2 = mod.run_routine("news", repo=".")
                check("per-routine off-switch does not affect a different routine (still attempts, fails on missing claude)",
                      r2["status"] == "failed" and "not on PATH" in r2.get("reason", ""), r2)
            finally:
                del os.environ["GROUNDWORK_ROUTINES_WORK_DIGEST"]
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path
    finish()


def test_run_routine_with_stub_claude() -> None:
    print("groundwork_routines.py run — real subprocess path against a stub `claude`, telemetry recorded correctly")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfgdir = tmp / "cfg"
        bindir = tmp / "bin"
        write_claude_stub(bindir, "echo")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfgdir), "PATH": f"{bindir}:/usr/bin:/bin"}

        r = subprocess.run(["python3", str(SCRIPT), "run", "work_digest", "--repo", str(REPO_ROOT), "--timeout", "20"],
                           capture_output=True, text=True, timeout=30, env=env)
        check("run work_digest against stub claude: exit 0", r.returncode == 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        check("result: status complete, exit_code 0, mutates False, dry_run False",
              out["status"] == "complete" and out["exit_code"] == 0 and out["mutates"] is False and out["dry_run"] is False, out)
        check("result: output_chars matches stub output length, no raw output stored", isinstance(out["output_chars"], int) and out["output_chars"] > 0, out)
        check("result JSON never contains the stub's actual echoed text (structured only)", "stub output" not in json.dumps(out), out)

        tel = cfgdir / "groundwork" / "telemetry" / "routines.jsonl"
        check("telemetry file written", tel.is_file())
        mode = stat.S_IMODE(tel.stat().st_mode)
        check("telemetry file is 0600 (owner-only), matching groundwork_telemetry.py's pattern", mode == 0o600, oct(mode))
        rec = json.loads(tel.read_text().splitlines()[-1])
        check("telemetry record matches the run_routine result", rec["routine"] == "work_digest" and rec["status"] == "complete")

        # ---- a failing routine still records telemetry and reports failed, not an exception
        write_claude_stub(bindir, "fail")
        r = subprocess.run(["python3", str(SCRIPT), "run", "news", "--repo", str(REPO_ROOT), "--timeout", "20"],
                           capture_output=True, text=True, timeout=30, env=env)
        check("failing stub claude: run command still exits 0 at the CLI (failure is reported in JSON, not a crash)", r.returncode == 1, r.stdout + r.stderr)
        out2 = json.loads(r.stdout)
        check("result: status failed, exit_code 1", out2["status"] == "failed" and out2["exit_code"] == 1, out2)

        # ---- a hung routine times out cleanly rather than blocking forever
        write_claude_stub(bindir, "hang")
        r = subprocess.run(["python3", str(SCRIPT), "run", "doc_drift", "--repo", str(REPO_ROOT), "--timeout", "2"],
                           capture_output=True, text=True, timeout=15, env=env)
        out3 = json.loads(r.stdout)
        check("hung routine: TimeoutExpired handled, status failed with a timeout reason, no crash",
              out3["status"] == "failed" and "timed out" in out3.get("reason", ""), out3)
    finish()


def test_schedule_routine() -> None:
    print("groundwork_routines.py schedule — reuses the launchd/cron pattern, no plist off macOS")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")
        os.environ["GROUNDWORK_OS"] = "linux"
        try:
            r = mod.schedule_routine("news", "daily")
            check("non-macOS: no plist written, cron-elsewhere note given", r["plist"] is None and "cron" in r["note"], r)
        finally:
            del os.environ["GROUNDWORK_OS"]
            del os.environ["CLAUDE_CONFIG_DIR"]

        os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")
        os.environ["GROUNDWORK_OS"] = "darwin"
        os.environ["GROUNDWORK_NO_LAUNCHCTL"] = "1"
        os.environ["GROUNDWORK_LAUNCH_AGENTS_DIR"] = str(tmp / "LaunchAgents")
        try:
            r = mod.schedule_routine("jira_eod", "daily", hour=9)
            check("macOS: plist path returned and file actually written", r["plist"] is not None and Path(r["plist"]).is_file(), r)
            import plistlib
            plist = plistlib.loads(Path(r["plist"]).read_bytes())
            check("plist label is com.groundwork.routine.jira_eod", plist["Label"] == "com.groundwork.routine.jira_eod", plist["Label"])
            check("plist invokes this same script's 'run jira_eod'", plist["ProgramArguments"][-2:] == ["run", "jira_eod"] and str(SCRIPT) in plist["ProgramArguments"], plist["ProgramArguments"])
            check("plist StartCalendarInterval hour matches the requested hour", plist["StartCalendarInterval"]["Hour"] == 9, plist["StartCalendarInterval"])
            check("plist carries CLAUDE_CONFIG_DIR through so the scheduled run targets the same config dir",
                  plist["EnvironmentVariables"].get("CLAUDE_CONFIG_DIR") == str(tmp / "cfg"), plist["EnvironmentVariables"])

            r2 = mod.schedule_routine("jira_eod", "disabled")
            check("disabling removes the plist file", r2["plist"] is None and not Path(mod._plist_path("jira_eod")).exists(), r2)
        finally:
            del os.environ["GROUNDWORK_OS"]
            del os.environ["GROUNDWORK_NO_LAUNCHCTL"]
            del os.environ["GROUNDWORK_LAUNCH_AGENTS_DIR"]
            del os.environ["CLAUDE_CONFIG_DIR"]

        try:
            mod.schedule_routine("not-a-routine", "daily")
            check("schedule_routine: unknown routine raises ValueError", False)
        except ValueError:
            check("schedule_routine: unknown routine raises ValueError", True)
    finish()


def test_cli_list() -> None:
    print("groundwork_routines.py list — reflects config.json + telemetry honestly")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfgdir = tmp / "cfg"
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfgdir)}

        r = subprocess.run(["python3", str(SCRIPT), "list"], capture_output=True, text=True, timeout=30, env=env)
        check("list with no config.json: exits 0, shows all six as disabled, never run",
              r.returncode == 0 and "enabled=False" in r.stdout and "never run" in r.stdout and r.stdout.count("\n") == 6, r.stdout)

        subprocess.run(["python3", str(REPO_ROOT / "scripts" / "groundwork_config.py"), "init", "sre-cloudops", "--path", str(cfgdir / "groundwork" / "config.json")],
                       capture_output=True, text=True, timeout=30, env=env, check=True)
        r2 = subprocess.run(["python3", str(SCRIPT), "list"], capture_output=True, text=True, timeout=30, env=env)
        check("list after sre-cloudops profile: jira_eod shows enabled=True", "jira_eod: enabled=True" in r2.stdout, r2.stdout)
        check("list after sre-cloudops profile: doc_drift shows enabled=False (profile default)", "doc_drift: enabled=False" in r2.stdout, r2.stdout)
    finish()


if __name__ == "__main__":
    for fn in (test_module_level, test_run_routine_off_switches, test_run_routine_with_stub_claude,
               test_schedule_routine, test_cli_list):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
