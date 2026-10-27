#!/usr/bin/env python3
"""Deterministic checks for the context-band view: the telemetry hook records the context-window %
at task end, and the report groups outcomes by it. No Claude Code, no network.

Run: python3 tests/test_context_bands.py   (or: python3 -m pytest tests -q)
"""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT = REPO_ROOT / "scripts" / "groundwork_report.py"
HOOK = REPO_ROOT / "hooks" / "groundwork_telemetry.py"

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


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def event(ts: str, sid="s1", outcome="complete", tests=True, ctx=None) -> dict:
    observed = {"profile": "work", "tools": ["Bash"], "mcp_servers": [], "agent_calls": 0, "agent_types": [],
                "files_changed": 1, "tests_run": tests, "implementation_performed": True, "deployment_performed": False}
    if ctx is not None:
        observed["ctx_pct"] = ctx
    return {"schema": 2, "ts": ts, "session_id": sid, "prompt_id": "p", "harness": "Groundwork", "harness_version": "2.5.0",
            "cwd_hash": "abc", "observed": observed,
            "declared": {"block_present": True, "playbook": "IMPLEMENT", "execution_mode": "single_agent", "agent_count": 0,
                         "agent_roles": [], "evidence_sources": ["repo"], "validation": "verified", "environment": "unknown",
                         "outcome": outcome, "clarification_required": False}}


def band(result: dict, label: str) -> dict:
    return next(b for b in result["bands"] if b["band"] == label)


def test_report_bands() -> None:
    m = load(REPORT, "gw_report_ctx")
    ref = dt.date(2026, 10, 27)
    day = f"{ref.isoformat()}T10:00:00Z"
    norm = lambda rows: [m.normalise(r) for r in rows]

    # recorded by the hook: band edges are lower-inclusive; 100 lands in the top band
    rows = [event(day, ctx=10), event(day, ctx=29.9, outcome="partial"), event(day, ctx=30),
            event(day, ctx=70, tests=False), event(day, ctx=84.9, outcome="failed"), event(day, ctx=100)]
    r = m.context_bands(norm(rows), {}, 30, ref)
    check("bands: 0–30 holds 10 and 29.9", band(r, "0–30%")["n"] == 2, str(r["bands"]))
    check("bands: 30 is in 30–50 (lower edge inclusive)", band(r, "30–50%")["n"] == 1)
    check("bands: 70 and 84.9 are in 70–85", band(r, "70–85%")["n"] == 2)
    check("bands: 100 is in the top band, labelled 85–100", band(r, "85–100%")["n"] == 1)
    check("bands: all six recorded, none joined or unmatched", (r["recorded"], r["joined"], r["unmatched"]) == (6, 0, 0))
    b = band(r, "0–30%")
    check("rates: completion 1/2, gap 1/2 in 0–30", (b["completion"]["num"], b["completion"]["den"], b["gap"]["num"]) == (1, 2, 1), str(b))
    b = band(r, "70–85%")
    check("rates: verified outcome needs an observed test/deploy (0/1 in 70–85)",
          b["verified_outcome"] == {"rate": 0.0, "num": 0, "den": 1}, str(b))
    check("rates: low data flagged below the trend minimum", band(r, "70–85%")["low_n"] is True)

    # invalid recorded values are treated as missing, never as a number
    bad = [event(day, ctx=v) for v in (True, 150, -1, "50")]
    r = m.context_bands(norm(bad), {}, 30, ref)
    check("invalid ctx_pct (bool, >100, <0, string) is not placed", r["unmatched"] == 4 and r["recorded"] == 0, str(r))

    # fallback: match the statusLine reading at or just before the task end, same session, recent enough
    end = dt.datetime(2026, 10, 27, 10, 0, tzinfo=dt.timezone.utc).timestamp()
    usage = {"s1": [(end - 600, 55.0), (end - 60, 62.0), (end + 60, 99.0)], "s2": [(end - 3600, 40.0)]}
    rows = [event(day, sid="s1"), event(day, sid="s2"), event(day, sid="s3")]
    r = m.context_bands(norm(rows), usage, 30, ref)
    check("fallback: newest reading before the task end is used (62 -> 50–70), not a later one",
          band(r, "50–70%")["n"] == 1 and band(r, "85–100%")["n"] == 0, str(r["bands"]))
    check("fallback: a reading older than 15 minutes is not used; unknown sessions are not placed",
          (r["joined"], r["unmatched"]) == (1, 2), str(r))

    # period: same window as the main report
    old = f"{(ref - dt.timedelta(days=40)).isoformat()}T10:00:00Z"
    r = m.context_bands(norm([event(old, ctx=50), event(day, ctx=50)]), {}, 30, ref)
    check("window: tasks outside the period are excluded", r["recorded"] == 1)

    # usage loader: tolerant of junk lines, keeps only valid readings
    with tempfile.TemporaryDirectory() as td:
        up = Path(td) / "usage.jsonl"
        up.write_text("\n".join([json.dumps({"ts": iso(end), "session_id": "a", "ctx_pct": 12}), "not json",
                                 json.dumps({"ts": "bad", "session_id": "a", "ctx_pct": 5}),
                                 json.dumps({"ts": iso(end), "session_id": "a", "ctx_pct": "x"}),
                                 json.dumps([1, 2])]) + "\n")
        u = m.load_usage(up)
        check("load_usage: only the valid reading is kept", u == {"a": [(end, 12.0)]}, str(dict(u)))
        check("load_usage: a missing file gives no data, no error", m.load_usage(Path(td) / "none.jsonl") == {})
    finish()


def test_generate_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        ev, usage, out = td / "events.jsonl", td / "usage.jsonl", td / "out"
        ref = "2026-10-27"
        rows = [event(f"{ref}T10:00:00Z", sid="secret-session-id-123", ctx=75)] + \
               [event(f"{ref}T11:00:00Z", sid="sess-joined")]
        ev.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        usage.write_text(json.dumps({"ts": f"{ref}T10:58:00Z", "session_id": "sess-joined", "ctx_pct": 20}) + "\n")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(td / "cfg"), "GROUNDWORK_USAGE_PATH": str(usage)}
        p = subprocess.run([sys.executable, str(REPORT), "generate", "--events", str(ev), "--out", str(out),
                            "--now", ref, "--snapshot", "--window", "30"], capture_output=True, text=True, env=env, timeout=60)
        check("generate exits 0", p.returncode == 0, p.stderr[-400:])
        page = (out / "dashboard.html").read_text()
        md = (out / f"{ref}.md").read_text()
        check("dashboard has the context-band panel", 'id="ctx-bands"' in page and "Outcome by context fill" in page)
        check("dashboard reports 2 tasks placed (1 recorded, 1 matched)", "2 task(s) placed in a band" in page, page[page.find("ctx-bands"):][:300])
        check("dashboard never embeds session ids", "secret-session-id-123" not in page and "sess-joined" not in page)
        check("markdown snapshot has the band table", "## Outcome by context fill at task end" in md and "| 70–85% (low data) | 1 |" in md, md[-900:])
        check("markdown states the association-not-cause caveat", "association, not cause" in md)

        # no task has a reading: no table (band labels contain "0%"; an empty table would read as rates)
        ev.write_text(json.dumps(event(f"{ref}T12:00:00Z", sid="nobody")) + "\n")
        usage.write_text("")
        p = subprocess.run([sys.executable, str(REPORT), "generate", "--events", str(ev), "--out", str(out),
                            "--now", ref, "--snapshot", "--window", "30"], capture_output=True, text=True, env=env, timeout=60)
        page, md = (out / "dashboard.html").read_text(), (out / f"{ref}.md").read_text()
        section = md[md.find("## Outcome by context fill"):]
        check("no readings: section says so, shows no table and no 0%",
              p.returncode == 0 and "No task in this period has a context reading (1 not placed)" in section
              and "| Context fill |" not in section and "0%" not in section, section[:300])
        check("no readings: dashboard panel has no table", 'id="ctx-bands"' in page and 'class="ctx"' not in page)
    finish()


def test_hook_records_ctx() -> None:
    with tempfile.TemporaryDirectory() as td:
        usage = Path(td) / "usage.jsonl"
        old_env = os.environ.get("GROUNDWORK_USAGE_PATH")
        os.environ["GROUNDWORK_USAGE_PATH"] = str(usage)
        try:
            h = load(HOOK, "gw_telemetry_ctx")
            now = time.time()
            usage.write_text("\n".join([
                json.dumps({"ts": iso(now - 300), "session_id": "s1", "ctx_pct": 40}),
                "garbage",
                json.dumps({"ts": iso(now - 30), "session_id": "s1", "ctx_pct": 71.26}),
                json.dumps({"ts": iso(now - 20), "session_id": "other", "ctx_pct": 5}),
                json.dumps({"ts": iso(now - 3000), "session_id": "stale", "ctx_pct": 90}),
                json.dumps({"ts": iso(now - 10), "session_id": "badpct", "ctx_pct": True}),
            ]) + "\n")
            check("hook: newest reading for this session, rounded", h.latest_ctx_pct("s1", now) == 71.3, str(h.latest_ctx_pct("s1", now)))
            check("hook: a reading older than 15 minutes is ignored", h.latest_ctx_pct("stale", now) is None)
            check("hook: unknown session gives None", h.latest_ctx_pct("nobody", now) is None)
            check("hook: a non-numeric reading gives None", h.latest_ctx_pct("badpct", now) is None)
            check("hook: empty or 'unknown' session id gives None", h.latest_ctx_pct("", now) is None and h.latest_ctx_pct("unknown", now) is None)

            text = "Complete. Done.\n\nHarness metadata\nGroundwork 2.5.0 · IMPLEMENT\nExecution: single agent\nValidation: verified\n"
            rec = h.build_record({"session_id": "s1", "transcript_path": "", "cwd": td}, text)
            check("hook: per-turn record carries observed.ctx_pct", rec.get("observed", {}).get("ctx_pct") == 71.3, str(rec.get("observed")))
            rec = h.build_record({"session_id": "nobody", "transcript_path": "", "cwd": td}, text)
            check("hook: no reading -> field absent, not 0", rec and "ctx_pct" not in rec["observed"], str(rec.get("observed")))
            usage.unlink()
            check("hook: missing usage file gives None, no error", h.latest_ctx_pct("s1", now) is None)
        finally:
            if old_env is None:
                os.environ.pop("GROUNDWORK_USAGE_PATH", None)
            else:
                os.environ["GROUNDWORK_USAGE_PATH"] = old_env
    finish()


if __name__ == "__main__":
    for t in (test_report_bands, test_generate_end_to_end, test_hook_records_ctx):
        try:
            t()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
