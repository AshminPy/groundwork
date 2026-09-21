#!/usr/bin/env python3
"""Deterministic checks for scripts/groundwork_report.py — no Claude Code, no launchd, no network.

Run: python3 tests/test_report.py   (or: python3 -m pytest tests -q)
"""
import datetime as dt
import importlib.util
import json
import os
import plistlib
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "groundwork_report.py"

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


def load():
    spec = importlib.util.spec_from_file_location("gw_report", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rec(day, profile="work", playbook="IMPLEMENT", version="1.3.3", env="unknown", exec_mode="single_agent",
        outcome="complete", validation="verified", block=True, evidence=("repo", "tests"), tests=True, impl=True,
        deploy=False, tools=("Bash", "Edit"), mcp=(), clarify=False) -> dict:
    return {"schema": 2, "ts": f"{day}T10:00:00Z", "session_id": "s", "prompt_id": "p", "harness": "Groundwork",
            "harness_version": version, "cwd_hash": "abc",
            "observed": {"profile": profile, "tools": list(tools), "mcp_servers": list(mcp), "agent_calls": 0, "agent_types": [],
                         "files_changed": 2 if impl else 0, "tests_run": tests, "implementation_performed": impl, "deployment_performed": deploy},
            "declared": {"block_present": block, "playbook": playbook, "execution_mode": exec_mode, "agent_count": 0, "agent_roles": [],
                         "evidence_sources": list(evidence), "validation": validation, "environment": env, "outcome": outcome,
                         "clarification_required": clarify}}


def synthetic(ref: dt.date) -> list:
    """A deterministic 400-day history with hand-countable numbers per period."""
    rows = []
    d = lambda n: (ref - dt.timedelta(days=n)).isoformat()
    # last 7 days: 6 IMPLEMENT complete (work), 1 DEPLOY failed (work, staging), 1 personal VALIDATE partial
    for i in range(6):
        rows.append(rec(d(i), playbook="IMPLEMENT"))
    rows.append(rec(d(2), playbook="DEPLOY", env="staging", outcome="failed", validation="not_verified", deploy=True, tests=False))
    rows.append(rec(d(3), profile="personal", playbook="VALIDATE", outcome="partial", validation="partial", impl=False))
    # days 8-24: 10 complete IMPLEMENT (5 v1.3.3, 5 v1.3.2 subagents), 2 TROUBLESHOOT blocked with a question,
    # 2 tool-using turns without a block (unknown), 1 with a block but unknown outcome
    for i in range(5):
        rows.append(rec(d(8 + i), version="1.3.3"))
    for i in range(5):
        rows.append(rec(d(14 + i), version="1.3.2", exec_mode="subagents"))
    rows.append(rec(d(20), playbook="TROUBLESHOOT", outcome="blocked", validation="not_verified", clarify=True, impl=False))
    rows.append(rec(d(21), playbook="TROUBLESHOOT", outcome="blocked", validation="not_verified", clarify=True, impl=False))
    rows.append(rec(d(22), block=False, outcome="unknown", validation="unknown", evidence=()))
    rows.append(rec(d(23), block=False, outcome="unknown", validation="unknown", evidence=()))
    rows.append(rec(d(24), outcome="unknown"))
    # previous 30-day period (days 31-60): 12 tasks, 6 complete 6 failed -> completion 50%
    for i in range(6):
        rows.append(rec(d(31 + i)))
    for i in range(6):
        rows.append(rec(d(40 + i), outcome="failed"))
    # days 61-90: 10 complete, agent_team, mcp github
    for i in range(10):
        rows.append(rec(d(61 + i), exec_mode="agent_team", mcp=("github",), tools=("Bash", "mcp__github__x")))
    # older: one complete DESIGN task per month for months 4..13 back, version 1.1.0
    for m in range(4, 14):
        rows.append(rec(d(30 * m), playbook="DESIGN", version="1.1.0", impl=False, tests=False))
    return rows


def write_events(path: Path, rows: list, extra_lines=()) -> None:
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        for l in extra_lines:
            f.write(l + "\n")


def run_cli(args, env_extra=None) -> subprocess.CompletedProcess:
    env = dict(os.environ, GROUNDWORK_NO_LAUNCHCTL="1")
    env.update(env_extra or {})
    return subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True, timeout=120, env=env)


def js_metrics(html_text: str, window, filters: dict) -> dict:
    """Run the dashboard's own JS computeMetrics under node against the embedded buckets."""
    node = shutil.which("node")
    if not node:
        return {}
    script = f"""
const h=require('fs').readFileSync(process.argv[1],'utf8');
const data=JSON.parse(h.match(/<script id="gw-data" type="application\\/json">([\\s\\S]*?)<\\/script>/)[1]);
const js=h.match(/<script>([\\s\\S]*?)<\\/script>/)[1];const m={{exports:{{}}}};new Function('module',js)(m);
console.log(JSON.stringify(m.exports.computeMetrics(data.buckets,{json.dumps(window)},data.ref,{json.dumps(filters)})));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html_text)
        p = f.name
    try:
        r = subprocess.run([node, "-e", script, p], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    finally:
        os.unlink(p)


def test_report() -> None:
    print("groundwork_report.py")
    m = load()
    ref = dt.date(2026, 9, 21)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfg = tmp / "claude"
        (cfg / "groundwork" / "telemetry").mkdir(parents=True)
        events = cfg / "groundwork" / "telemetry" / "events.jsonl"
        agents = tmp / "agents"
        env = {"CLAUDE_CONFIG_DIR": str(cfg), "GROUNDWORK_LAUNCH_AGENTS_DIR": str(agents)}
        dash = cfg / "groundwork" / "reports" / "dashboard.html"

        # -- empty telemetry
        r = run_cli(["generate", "--now", "2026-09-21"], env)
        check("missing telemetry -> dashboard written, exit 0", r.returncode == 0 and dash.is_file(), r.stderr)
        check("missing telemetry -> 0 records reported", "records=0" in r.stdout, r.stdout)
        events.write_text("")
        r = run_cli(["generate", "--now", "2026-09-21", "--snapshot"], env)
        md_path = cfg / "groundwork" / "reports" / "2026-09-21.md"
        check("empty telemetry -> snapshot written, exit 0", r.returncode == 0 and md_path.is_file())
        md = md_path.read_text()
        check("empty telemetry -> N/A, never 0%", "Total tasks: 0" in md and "N/A (insufficient data)" in md and "0%" not in md, md)
        check("empty telemetry -> no-tasks gap line", "No tasks recorded in this period." in md)

        # -- malformed records, missing fields, schema 1
        rows = synthetic(ref)
        v1 = {"ts": "2026-08-26T09:00:00Z", "harness_version": "1.3.0", "profile": "unknown", "playbook": "AUDIT", "execution_mode": "single_agent",
              "tools": ["Read"], "mcp_servers": [], "evidence_sources": ["repo"], "outcome": "unknown", "validation": "partial",
              "tests_run": False, "implementation_performed": False, "deployment_performed": False, "files_changed": 0, "environment": "unknown"}
        write_events(events, rows + [v1], extra_lines=["not json", "{}", '{"ts": "nope"}', '{"schema": 2, "ts": "2026-08-27T00:00:00Z"}', "[1,2]", ""])
        records, stats = m.load_events(events)
        check("malformed / missing lines skipped and counted", stats["malformed"] == 4 and len(records) == len(rows) + 2, json.dumps(stats))
        bare = [x for x in records if x["day"] == "2026-08-27"][0]
        check("schema-2 line with missing observed/declared -> unknown fields, no crash", bare["playbook"] == "UNKNOWN" and bare["outcome"] == "unknown" and bare["tools"] == [] and bare["block"] is True, json.dumps(bare))
        old = [x for x in records if x["version"] == "1.3.0"][0]
        check("schema-1 flat record normalised", old["playbook"] == "AUDIT" and old["validation"] == "partial" and old["block"] is True)

        # -- health calculations on the 30-day window (hand-counted from synthetic())
        buckets, gran = m.aggregate(records)
        check("day buckets", gran == "day" and all(len(b["day"]) == 10 for b in buckets))
        c = m.compute(buckets, 30, ref)
        s = c["summary"]
        # (ref-30, ref]: 8 + 15 + v1 + bare = 25 tasks; known outcomes: 6 complete + failed + partial + 10 complete + 2 blocked = 20
        check("30d total 25", s["total"] == 25, str(s["total"]))
        check("30d completion 16/20", s["completion"] == {"rate": 80.0, "num": 16, "den": 20}, json.dumps(s["completion"]))
        check("30d gap 4/20 (1 failed, 1 partial, 2 blocked)", s["gap"] == {"rate": 20.0, "num": 4, "den": 20}, json.dumps(s["gap"]))
        check("30d verified outcome 16/16", s["verified_outcome"] == {"rate": 100.0, "num": 16, "den": 16}, json.dumps(s["verified_outcome"]))
        # validation known: verified 17 (16 complete + 1 unknown-outcome), partial 2 (VALIDATE + v1), not_verified 3 -> 17/22
        check("30d validation 17/22", s["validation"] == {"rate": round(100 * 17 / 22, 1), "num": 17, "den": 22}, json.dumps(s["validation"]))
        check("30d compliance 23/25", s["compliance"] == {"rate": 92.0, "num": 23, "den": 25}, json.dumps(s["compliance"]))
        check("30d evidence 22/23 (bare record declares none)", s["evidence"] == {"rate": round(100 * 22 / 23, 1), "num": 22, "den": 23}, json.dumps(s["evidence"]))
        check("30d unknown outcomes counted but excluded from denominators", s["outcomes"]["unknown"] == 5 and s["known"] == 20, json.dumps(s["outcomes"]))
        check("rework and accuracy are None (insufficient data), never 0", c["rework"] is None and c["accuracy"] is None)
        # -- gaps (deterministic sentences)
        gaps = "\n".join(c["gaps"])
        check("gap: highest-gap playbook needs >=3 known outcomes (TROUBLESHOOT has 2) -> IMPLEMENT/VALIDATE/DEPLOY excluded too -> none or IMPLEMENT", ("has the highest gap rate" not in gaps) or ("IMPLEMENT" in gaps), gaps)
        check("gap: compliance sentence with counts", "Metadata compliance is 92% (2 of 25" in gaps, gaps)
        check("gap: files changed without verified validation (failed DEPLOY + 2 no-block turns)", "3 task(s) that changed files did not declare verified validation" in gaps, gaps)
        check("gap: unknown outcomes sentence", "5 task(s) had no recognisable outcome" in gaps, gaps)
        check("gap: blocked + clarifying questions", "2 task(s) ended blocked; 2 asked a clarifying question" in gaps, gaps)
        check("gap: failed sentence", "1 task(s) ended failed" in gaps, gaps)
        # -- trends: previous 30 days has 12 known (6 complete, 6 failed) -> completion 50 -> +30
        check("trend completion +30 vs previous period", c["trends"].get("completion") == 30.0, json.dumps(c["trends"]))
        check("trend gap -30", c["trends"].get("gap") == -30.0, json.dumps(c["trends"]))
        # -- 7 / 90 / 365 / all
        c7 = m.compute(buckets, 7, ref)
        check("7d: 8 tasks, completion 6/8", c7["summary"]["total"] == 8 and c7["summary"]["completion"] == {"rate": 75.0, "num": 6, "den": 8}, json.dumps(c7["summary"]))
        check("7d: previous 7 days (days 8-14) has 6 known -> completion trend present", "completion" in c7["trends"], json.dumps(c7["trends"]))
        s90 = m.compute(buckets, 90, ref)["summary"]
        check("90d: 25 + 12 + 10 = 47 tasks", s90["total"] == 47, str(s90["total"]))
        c365 = m.compute(buckets, 365, ref)
        check("year: monthly DESIGN tasks inside 365 days counted (months 4..12 = 9)", c365["by_playbook"]["DESIGN"]["total"] == 9, json.dumps(c365["by_playbook"].get("DESIGN")))
        call = m.compute(buckets, None, ref)
        check("all data: every record, no previous period, no trends", call["summary"]["total"] == len(records) and call["previous"] is None and call["trends"] == {}, str(call["summary"]["total"]))
        # -- filters
        sp = m.compute(buckets, 30, ref, {"profile": "personal"})["summary"]
        check("profile filter personal -> 1 partial VALIDATE", sp["total"] == 1 and sp["gap"] == {"rate": 100.0, "num": 1, "den": 1}, json.dumps(sp))
        spb = m.compute(buckets, 30, ref, {"playbook": "TROUBLESHOOT"})["summary"]
        check("playbook filter -> 2 blocked", spb["total"] == 2 and spb["outcomes"]["blocked"] == 2, json.dumps(spb))
        sv = m.compute(buckets, 30, ref, {"version": "1.3.2"})
        check("version filter -> 5 subagent tasks", sv["summary"]["total"] == 5 and sv["exec_modes"] == {"subagents": 5}, json.dumps(sv["exec_modes"]))
        se = m.compute(buckets, 30, ref, {"environment": "staging"})["summary"]
        check("environment filter -> the failed deploy", se["total"] == 1 and se["outcomes"]["failed"] == 1)
        st = m.compute(buckets, 90, ref)
        check("tools / mcp / versions / exec modes aggregated", st["mcp"] == {"github": 10} and st["exec_modes"]["agent_team"] == 10 and set(st["versions"]) >= {"1.3.3", "1.3.2", "1.3.0"} and st["tools"].get("Bash", 0) >= 40, json.dumps({"mcp": st["mcp"], "exec": st["exec_modes"]}))
        check("weekly series inside the window", len(c["series"]) >= 4 and all(p["n"] > 0 for p in c["series"]), json.dumps([p["week"] for p in c["series"]]))
        # -- insufficient data: one record -> rates exist with den 1, no trends
        one, _ = m.aggregate([records[0]])
        c1 = m.compute(one, 30, ref)
        check("insufficient data: no trends with one record", c1["trends"] == {} and c1["summary"]["total"] == 1)

        # -- HTML generation (manual) + privacy + Python/JS parity
        r = run_cli(["generate", "--now", "2026-09-21", "--window", "30", "--snapshot"], env)
        check("manual generation exit 0, three files", r.returncode == 0 and len([l for l in r.stdout.splitlines() if l.endswith((".html", ".md"))]) == 3, r.stdout + r.stderr)
        page = dash.read_text()
        embedded = page.split('<script id="gw-data" type="application/json">')[1].split("</script>")[0]
        check("dashboard is self-contained: no external URLs, scripts or fonts", "http://" not in page and "https://" not in page and "src=" not in page and "@import" not in page)
        check("dashboard embeds buckets only: no session ids, hashes or timestamps", '"session_id"' not in page and '"cwd_hash"' not in page and "T10:00:00Z" not in page and "abc" not in embedded)
        check("dashboard has the cards, charts, gaps and filters", all(x in page for x in ('id="cards"', 'id="trend"', 'id="gaps-pb"', 'id="validation"', 'id="versions"', 'id="win"', 'id="profile"', 'id="playbook"', 'id="version"', 'id="environment"')))
        check("dashboard states the N/A policy in its definitions", "show N/A rather than 0%" in page)
        check("files owner-only", (dash.stat().st_mode & 0o777) == 0o600)
        if shutil.which("node"):
            for win, flt in ((30, {}), (7, {}), (90, {"version": "1.3.2"}), (30, {"profile": "personal"}), (None, {}), (365, {"playbook": "DESIGN"})):
                py = m.compute(buckets, win, ref, flt)
                js = js_metrics(page, win, flt)
                same = (js["summary"] == py["summary"] and js["trends"] == py["trends"] and js["gaps"] == py["gaps"]
                        and js["exec_modes"] == py["exec_modes"] and js["versions"] == py["versions"] and js["tools"] == py["tools"]
                        and [(p["week"], p["n"]) for p in js["series"]] == [(p["week"], p["n"]) for p in py["series"]]
                        and {k: v["total"] for k, v in js["by_playbook"].items()} == {k: v["total"] for k, v in py["by_playbook"].items()})
                check(f"Python and JS agree: window={win} filters={flt}", same, json.dumps({"py": py["summary"], "js": js.get("summary")}))
        else:
            print("  skip node parity (node not on PATH)")
        snap_md = md_path.read_text()
        check("markdown snapshot carries the same headline numbers and trends", "Completion: 80% (16/20) ↑30%" in snap_md and "Gap rate: 20% (4/20) ↓30%" in snap_md, snap_md[:600])

        # -- schedules: all frequencies, replacement without duplicates, disabled removes
        for freq, key in (("daily", {"Hour": 8, "Minute": 0}), ("weekly", {"Weekday": 1, "Hour": 8, "Minute": 0}),
                          ("monthly", {"Day": 1, "Hour": 8, "Minute": 0}), ("yearly", {"Month": 1, "Day": 1, "Hour": 8, "Minute": 0})):
            r = run_cli(["schedule", freq], env)
            plists = list(agents.glob("*.plist"))
            pl = plistlib.load(open(plists[0], "rb")) if plists else {}
            check(f"schedule {freq}: exactly one plist, correct calendar, snapshot command", r.returncode == 0 and len(plists) == 1 and pl.get("StartCalendarInterval") == key and pl["ProgramArguments"][-2:] == ["generate", "--snapshot"] and pl["Label"] == "com.groundwork.report", r.stdout + r.stderr + json.dumps(pl))
            check(f"schedule {freq}: config saved", json.loads((cfg / "groundwork" / "report.json").read_text())["schedule"] == freq)
        r = run_cli(["schedule", "weekly", "--hour", "6"], env)
        pl = plistlib.load(open(next(agents.glob("*.plist")), "rb"))
        check("schedule --hour replaces in place (still one plist)", pl["StartCalendarInterval"]["Hour"] == 6 and len(list(agents.glob("*.plist"))) == 1)
        r = run_cli(["schedule", "disabled"], env)
        check("schedule disabled: plist removed, config disabled", r.returncode == 0 and not list(agents.glob("*.plist")) and json.loads((cfg / "groundwork" / "report.json").read_text())["schedule"] == "disabled")
        m.is_macos = lambda: False
        try:
            res = m.schedule("weekly")
        finally:
            m.is_macos = lambda: True
        check("non-macOS: schedule saves config, writes no plist, says how to run manually", res["plist"] is None and "manually" in res["note"] and not list(agents.glob("*.plist")), json.dumps(res))
        r = run_cli(["status"], env)
        check("status prints config and paths", r.returncode == 0 and '"schedule": "disabled"' in r.stdout and "dashboard_present" in r.stdout)
        (cfg / "groundwork" / "report.json").write_text(json.dumps({"schedule": "weekly", "window_days": 90, "hour": 8}))
        r = run_cli(["generate", "--now", "2026-09-21", "--snapshot"], env)
        check("window_days from config (90) is independent of the weekly schedule", "last 90 days" in md_path.read_text())

        # -- bounded: MAX_BYTES tail read (constant lowered for the test)
        write_events(events, [rec((ref - dt.timedelta(days=i)).isoformat()) for i in range(200)])
        saved = m.MAX_BYTES
        m.MAX_BYTES = 4096
        try:
            recs, st = m.load_events(events)
        finally:
            m.MAX_BYTES = saved
        check("MAX_BYTES: only the tail is read, skipped bytes reported, no malformed partial line", 0 < len(recs) < 200 and st["bytes_skipped"] == events.stat().st_size - 4096 and st["malformed"] == 0, json.dumps(st) + f" {len(recs)}")
        check("rate rounds half up like the JS twin (1/16 -> 6.3)", m._rate(1, 16)["rate"] == 6.3 and m._rate(1, 3)["rate"] == 33.3)

        # -- bounded: weekly collapse above MAX_BUCKETS
        many = [rec((ref - dt.timedelta(days=i % 3000)).isoformat(), playbook=random.Random(i).choice(["A", "B", "C"]), version=f"v{i % 3}") for i in range(5000)]
        write_events(events, many)
        recs, _ = m.load_events(events)
        bk, gran = m.aggregate(recs)
        check("bucket cap -> weekly granularity, bounded count", gran == "week" and len(bk) <= m.MAX_BUCKETS, f"{gran} {len(bk)}")
    finish()


if __name__ == "__main__":
    try:
        test_report()
    except AssertionError:
        pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
