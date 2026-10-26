#!/usr/bin/env python3
"""Deterministic checks for usage visibility in scripts/groundwork_statusline.py (feature 2 of
openspec/changes/core-evidence-continuity): the throttled usage record, `groundwork usage`, and the
optional plan-usage segment. No Claude Code needed.

Run: python3 tests/test_usage.py   (or: python3 -m pytest tests -q)
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "groundwork_statusline.py"
CLI = REPO_ROOT / "scripts" / "groundwork_cli.py"

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


def env_for(home: Path, usage: Path | None = None) -> dict:
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(home)
    env.pop("GROUNDWORK_TELEMETRY_PATH", None)
    env["GROUNDWORK_USAGE_PATH"] = str(usage or home / "groundwork" / "telemetry" / "usage.jsonl")
    return env


def render(env: dict, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                          text=True, timeout=30, env=env)


def report(env: dict, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "usage", *args], capture_output=True, text=True,
                          timeout=30, env=env)


def payload(session="s-1", cost=1.5, five=42.0, seven=10.0, name="fix runner"):
    return {
        "session_id": session, "session_name": name, "transcript_path": "/secret/transcript.jsonl",
        "workspace": {"current_dir": "/nowhere/groundwork", "project_dir": "/nowhere/groundwork"},
        "model": {"id": "claude-opus-5-5", "display_name": "Opus"},
        "cost": {"total_cost_usd": cost},
        "context_window": {"used_percentage": 37},
        "rate_limits": {"five_hour": {"used_percentage": five, "resets_at": 1793000000},
                        "seven_day": {"used_percentage": seven, "resets_at": 1793500000}},
    }


def records(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


ALLOWED = {"ts", "session_id", "project", "model", "cost_usd", "ctx_pct",
           "five_hour_pct", "five_hour_resets_at", "seven_day_pct", "seven_day_resets_at",
           "spend_limit_pct", "spend_limit_resets_at"}


def test_record() -> None:
    print("usage record")
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        env = env_for(home)
        usage = Path(env["GROUNDWORK_USAGE_PATH"])
        r = render(env, payload())
        recs = records(usage)
        check("render exits 0 and prints the line", r.returncode == 0 and r.stdout.startswith("GROUNDWORK"), r.stderr)
        check("one record written", len(recs) == 1, str(recs))
        check("record holds only allowed fields (no transcript path, no content)",
              bool(recs) and set(recs[0]) <= ALLOWED and "secret" not in usage.read_text(), str(recs))
        check("session name is never stored (it can be taken from the first prompt)",
              "fix runner" not in usage.read_text(), usage.read_text())
        state = usage.with_name("usage-state.json")
        check("throttle state file is owner-only", state.exists() and oct(state.stat().st_mode & 0o777) == "0o600",
              oct(state.stat().st_mode) if state.exists() else "missing")
        check("record carries cost and plan usage", bool(recs) and recs[0]["cost_usd"] == 1.5 and recs[0]["five_hour_pct"] == 42.0)
        check("project is the folder name only", bool(recs) and recs[0]["project"] == "groundwork", str(recs))
        check("usage file is owner-only", usage.exists() and oct(usage.stat().st_mode & 0o777) == "0o600")
        render(env, payload(cost=1.6))
        check("same session within a minute: throttled to one record", len(records(usage)) == 1)
        render(env, payload(session="s-2"))
        check("another session records independently", len(records(usage)) == 2)
        render(env, {"workspace": {"current_dir": "/x"}})
        check("no session_id: no record", len(records(usage)) == 2)
        blocker = home / "file-not-dir"
        blocker.write_text("x")
        r = render(env_for(home, blocker / "usage.jsonl"), payload(session="s-9"))
        check("unwritable usage path: render still prints, exit 0", r.returncode == 0 and r.stdout.startswith("GROUNDWORK"), r.stderr)
    finish()


def iso(seconds_ago: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds_ago))


def write(path: Path, recs: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in recs) + "not json\n")


def rec(sid, ago, cost, five=None, project="groundwork"):
    r = {"ts": iso(ago), "session_id": sid, "session_name": sid, "project": project, "cost_usd": cost}
    if five is not None:
        r["five_hour_pct"] = five
    return r


def test_report() -> None:
    print("groundwork usage report")
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        env = env_for(home)
        usage = Path(env["GROUNDWORK_USAGE_PATH"])
        r = report(env)
        check("no data: friendly message, exit 0", r.returncode == 0 and "No usage records" in r.stdout, r.stdout + r.stderr)
        write(usage, [
            rec("big", 6 * 3600, 1.0),            # before the 5h window: baseline only
            rec("big", 3 * 3600, 3.0),
            rec("big", 600, 6.0, five=82),         # +5.0 inside the window
            rec("small", 3600, 0.5),
            rec("small", 300, 1.5),                # +1.0 (first in-window record has no baseline)
            rec("cleared", 3000, 4.0),
            rec("cleared", 2000, 0.2),             # /clear reset the counter: the drop is skipped
            rec("cleared", 100, 2.2),              # +2.0 after the reset (a lower bound by design)
            rec("old", 3 * 86400, 9.0),
            rec("old", 2 * 86400, 12.0),          # outside 5h, inside 7d
        ])
        r = report(env)
        out = r.stdout
        lines = [ln for ln in out.splitlines() if ln[:1].isdigit()]
        check("report exits 0", r.returncode == 0, r.stderr)
        check("ranked by cost increase within the window",
              len(lines) == 3 and "big" in lines[0] and "cleared" in lines[1] and "small" in lines[2], out)
        check("baseline before the window is used (big = +$5.00)", bool(lines) and "$5.00" in lines[0], out)
        check("a /clear reset is skipped, never negative (cleared = +$2.00, a lower bound)",
              len(lines) > 1 and "$2.00" in lines[1], out)
        check("sessions outside the window are excluded", "old" not in "\n".join(lines), out)
        check("shows the latest account-wide plan usage, labelled with when it was seen", "5h 82%" in out and "as of" in out, out)
        check("never claims a session exceeded the limit", "exceed" not in out.lower(), out)
        check("explains the limit is shared", "shared" in out.lower(), out)
        r = report(env, "--window", "7d")
        check("7d window includes older sessions", "old" in r.stdout and "$3.00" in r.stdout, r.stdout)
        stale = [rec("x", 600, 1.0, five=95)]
        stale[0]["five_hour_resets_at"] = time.time() - 60
        write(usage, stale)
        check("a plan figure whose window already reset is not shown", "95%" not in report(env).stdout, report(env).stdout)
        old = [rec("ancient", 9 * 86400 + i, 1.0) for i in range(3)] + [rec("fresh", 60, 1.0)]
        write(usage, old)
        import importlib.util
        spec = importlib.util.spec_from_file_location("sl", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        os.environ["GROUNDWORK_USAGE_PATH"] = str(usage)
        spec.loader.exec_module(mod)
        mod.trim_usage(time.time(), min_bytes=0)
        kept = records(usage)
        check("trim drops records older than 8 days and keeps recent ones",
              [r["session_id"] for r in kept] == ["fresh"], str(kept))
        write(usage, old)
        mod.USAGE_TRIM_BYTES = 0
        state = usage.with_name("usage-state.json")
        state.write_text(json.dumps({"_last_trim": time.time() - 60}))
        mod.record_usage(payload(session="t-1"))
        check("trim runs at most once an hour (recent trim: file not rewritten)",
              "ancient" in usage.read_text(), usage.read_text()[:200])
        state.write_text(json.dumps({"_last_trim": time.time() - 7200}))
        mod.record_usage(payload(session="t-2"))
        check("trim runs again after an hour", "ancient" not in usage.read_text(), usage.read_text()[:200])
        r = report(env, "--window", "1y")
        check("invalid window rejected with a non-zero exit", r.returncode != 0, r.stdout + r.stderr)
    finish()


def test_segment() -> None:
    print("plan-usage segment")
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        env = env_for(home)
        r = render(env, payload(five=82.4))
        check("segment shown when rate limits are present", "5h 82%" in r.stdout, r.stdout)
        p = payload(session="s-2")
        p.pop("rate_limits")
        r = render(env, p)
        check("no segment without rate limits (e.g. not Pro/Max)", "5h" not in r.stdout, r.stdout)
        cfg = home / "groundwork" / "statusline-config.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"show_plan_usage": False}))
        r = render(env, payload(session="s-3", five=82.4))
        check("segment can be turned off", "5h" not in r.stdout, r.stdout)
        cfg.write_text("{}")
        g = payload(session="s-4")
        g["rate_limits"] = {"spend_limit": {"used_percentage": 62.8, "resets_at": time.time() + 86400}}
        r = render(env, g)
        check("gateway spend limit shown when there is no 5h plan window", "spend 63%" in r.stdout, r.stdout)
        usage = Path(env["GROUNDWORK_USAGE_PATH"])
        check("gateway spend limit recorded", records(usage)[-1].get("spend_limit_pct") == 62.8, str(records(usage)[-1:]))
        out = report(env).stdout
        check("report shows the gateway spend limit", "spend limit 63%" in out, out)
    finish()


def test_cli_forwards() -> None:
    print("groundwork usage (CLI)")
    with tempfile.TemporaryDirectory() as d:
        home = Path(d)
        env = env_for(home)
        r = subprocess.run([sys.executable, str(CLI), "usage"], capture_output=True, text=True, timeout=30, env=env)
        check("missing install: clear error, exit 1", r.returncode == 1 and "not found" in r.stderr, r.stderr)
        bin_dir = home / "groundwork" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "groundwork_statusline.py").write_text(SCRIPT.read_text())
        r = subprocess.run([sys.executable, str(CLI), "usage"], capture_output=True, text=True, timeout=30, env=env)
        check("installed: forwards to the statusline script's usage report",
              r.returncode == 0 and "No usage records" in r.stdout, r.stdout + r.stderr)
    finish()


if __name__ == "__main__":
    for fn in (test_record, test_report, test_segment, test_cli_forwards):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
