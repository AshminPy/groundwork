#!/usr/bin/env python3
"""Accuracy-signal checks (openspec/changes/add-accuracy-signals): each collected field (design D2, D5-D11) and each
Performance-gaps metric (D3, D4, D8) is checked against hand-labelled fixtures. No Claude Code, no network.

Run: python3 tests/test_accuracy_signals.py   (or: python3 -m pytest tests -q)
"""
import _isolate  # noqa: F401  first: test runs never write the real signals.jsonl
import calendar
import datetime as dt
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / "hooks"
REPORT = REPO_ROOT / "scripts" / "groundwork_report.py"
HOOK = HOOKS / "groundwork_telemetry.py"
PUSH = HOOKS / "block_protected_push.py"

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok   {name}")
    else:
        _FAILURES.append(f"{name}  {detail}")
        print(f"  FAIL {name}  {detail}")


def finish() -> None:
    failures = list(_FAILURES)
    _FAILURES.clear()
    assert not failures, "\n".join(failures)


def load(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Env:
    """Points every telemetry path at a temp dir for the duration of a test."""
    KEYS = ("GROUNDWORK_SIGNALS_PATH", "GROUNDWORK_USAGE_PATH", "GROUNDWORK_TELEMETRY_PATH",
            "GROUNDWORK_TOOL_TELEMETRY_PATH", "GROUNDWORK_TELEMETRY", "CLAUDE_CONFIG_DIR")

    def __init__(self, td: Path):
        self.td, self.old = td, {}

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.update(GROUNDWORK_SIGNALS_PATH=str(self.td / "signals.jsonl"),
                          GROUNDWORK_USAGE_PATH=str(self.td / "usage.jsonl"),
                          GROUNDWORK_TELEMETRY_PATH=str(self.td / "events.jsonl"),
                          GROUNDWORK_TOOL_TELEMETRY_PATH=str(self.td / "tool_events.jsonl"),
                          CLAUDE_CONFIG_DIR=str(self.td / "cfg"))
        os.environ.pop("GROUNDWORK_TELEMETRY", None)
        return self

    def __exit__(self, *_):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_hook(script: Path, payload: dict, env: dict):
    return subprocess.run([sys.executable, str(script)], input=json.dumps(payload), capture_output=True, text=True,
                          env=env, timeout=30)


def lines(path: Path) -> list:
    return [json.loads(x) for x in path.read_text().splitlines()] if path.is_file() else []


# ---------------------------------------------------------------- isolation (task 0.2)
def test_isolation() -> None:
    p = os.environ.get("GROUNDWORK_SIGNALS_PATH", "")
    real = Path(os.path.expanduser("~/.claude")) / "groundwork" / "telemetry" / "signals.jsonl"
    check("the suite's default signals path is a temp file, not the real one", bool(p) and Path(p) != real
          and not p.startswith(os.path.expanduser("~/.claude")), p)
    finish()


# ---------------------------------------------------------------- D5 classification
def test_classify_bash() -> None:
    h = load(HOOK, "gw_tel_acc_d5")

    def rec(cmd, event="PostToolUse", **kw):
        data = {"tool_name": "Bash", "session_id": "s", "prompt_id": "p", "tool_use_id": "tu1",
                "tool_input": {"command": cmd, **{k: v for k, v in kw.items() if k == "run_in_background"}}}
        data.update({k: v for k, v in kw.items() if k != "run_in_background"})
        return h.build_tool_record(data, event)
    fail = lambda cmd, code=1, **kw: rec(cmd, "PostToolUseFailure", error=f"Exit code {code}\nFAILED x", **kw)
    cases = [
        ("pytest passes", rec("python3 -m pytest tests -q"), ("test", "pass")),
        ("pytest fails", fail("pytest -q"), ("test", "fail")),
        ("cd then pytest fails", fail("cd tests && pytest -q"), ("test", "fail")),
        ("env wrapper", fail("env CI=1 timeout 60 uv run pytest -q"), ("test", "fail")),
        ("build && test fails: either may have failed", fail("make build && pytest"), ("test", "unknown")),
        ("piped test", rec("pytest -q | tail -5"), ("test", "unknown")),
        ("test then ;", rec("pytest -q; echo done"), ("test", "unknown")),
        ("background test", rec("pytest -q", run_in_background=True), ("test", "unknown")),
        ("interrupted test", rec("pytest -q", tool_response={"interrupted": True}), ("test", "unknown")),
        ("interrupt failure", fail("pytest -q", is_interrupt=True), ("test", "unknown")),
        ("no exit line", rec("pytest -q", "PostToolUseFailure", error="Command timed out"), ("test", "unknown")),
        ("pytest exit 5 = no tests collected", fail("pytest -q", 5), ("test", "unknown")),
        ("go test exit 5 is a failure", fail("go test ./...", 5), ("test", "fail")),
        ("terraform plan exit 2 = changes", fail("terraform plan -detailed-exitcode", 2), ("check", "unknown")),
        ("terraform validate fails", fail("terraform validate"), ("check", "fail")),
        ("npm test", rec("npm test"), ("test", "pass")),
        ("python test file", rec("python3 tests/test_hooks.py"), ("test", "pass")),
        ("kubectl apply", rec("kubectl apply -f x.yaml"), ("deploy", None)),
        ("kubectl get", rec("kubectl get pods"), ("runtime_read", None)),
        ("curl", rec("curl -s https://x/health"), ("runtime_read", None)),
        ("claude -p", rec("claude -p 'hi'"), ("runtime_read", None)),
    ]
    for name, r, (kind, result) in cases:
        check(f"D5 {name}", r.get("kind") == kind and r.get("result") == result, json.dumps(r))
    for cmd in ("grep -rn pytest .", "pip install pytest", "cat pytest.ini", "echo kubectl apply", "git log",
                "vim tests/test_x.py", "bash -c 'pytest'"):
        r = rec(cmd)
        check(f"D5 never a test: {cmd}", "kind" not in r and "result" not in r, json.dumps(r))
    r = rec("pytest -q && git commit -m 'x'")
    check("test and commit in one command", r.get("kind") == "test" and r.get("git_commit") is True, json.dumps(r))
    check("git -C dir commit", rec("git -C repo commit -m x").get("git_commit") is True)
    check("git status is not a commit", "git_commit" not in rec("git status"))
    r = fail("pytest -q")
    check("ids kept, no command or output text stored", r.get("prompt_id") == "p" and r.get("tool_use_id") == "tu1"
          and "pytest" not in json.dumps(r) and "FAILED" not in json.dumps(r), json.dumps(r))
    # the task gate's parser is imported lazily: without it, kind still comes from the first word and result is unknown
    real = h._segments
    h._segments = lambda _cmd: None
    try:
        r = fail("pytest -q")
        check("parser missing: kind kept, result unknown", r.get("kind") == "test" and r.get("result") == "unknown", json.dumps(r))
    finally:
        h._segments = real
    finish()


# ---------------------------------------------------------------- D9 / D10 signals
def test_signals() -> None:
    h = load(HOOK, "gw_tel_acc_sig")
    rev = lambda agent, text: h.build_signal({"session_id": "s", "prompt_id": "p", "agent_id": "a1", "agent_type": agent,
                                              "last_assistant_message": text}, "SubagentStop")
    r = rev("ecc:code-reviewer", "Fine.\n```\nREVIEW RESULT\nVerdict:   approve\nMust-fix:  0\n```")
    check("SubagentStop review: approve, must-fix 0, agent id", r.get("kind") == "review" and r.get("must_fix") == 0
          and r.get("verdict") == "approve" and r.get("agent_id") == "a1" and r.get("source") == "subagent_stop", str(r))
    r = rev("code-reviewer", "REVIEW RESULT\nVerdict: approve")
    check("verdict-only approve means must-fix 0 (ledger rule)", r.get("must_fix") == 0, str(r))
    r = rev("ecc:security-reviewer", "Looks fine to me.")
    check("no result block -> parsed false", r.get("parsed") is False and "must_fix" not in r, str(r))
    check("non-review agent -> nothing", rev("Explore", "REVIEW RESULT\nMust-fix: 0") == {})
    tool = lambda status: h.tool_review_signal(
        {"session_id": "s", "prompt_id": "p", "tool_name": "Agent",
         "tool_input": {"subagent_type": "ecc:code-reviewer", "prompt": "review"},
         "tool_response": {"status": status, "agentId": "a9",
                           "content": [{"type": "text", "text": "REVIEW RESULT\nVerdict: changes-required\nMust-fix: 2"}]}},
        "PostToolUse")
    r = tool("completed")
    check("foreground Agent review -> signal keyed by agentId", r.get("source") == "tool" and r.get("agent_id") == "a9"
          and r.get("must_fix") == 2, str(r))
    check("background launch -> no tool signal (SubagentStop records it)", tool("async_launched") == {})

    p = lambda text: h.build_signal({"session_id": "s", "prompt": text}, "UserPromptSubmit")
    corrections = ["that didn't work", "That didn’t work", "it still doesn't work", "still failing with the same error",
                   "the build is still broken", "that's wrong", "That’s not right", "this is not what I asked for",
                   "you broke the login page", "Thanks. It did not work though"]
    neutral = ["does it work offline?", "how does this work", "fix the failing test in CI",
               "review the PR and tell me what is wrong with the approach", "what's wrong with my regex", "run the tests",
               "make it work", "/review that's wrong", "<task-notification>still failing</task-notification>",
               "```\nthat didn't work\n```\nplease add logging", "a\nb\nc\nd\ne\nthat didn't work",
               "x" * 301 + " that didn't work"]
    tp = [t for t in corrections if p(t).get("correction") is True]
    fp = [t for t in neutral if p(t).get("correction") is True]
    check("D10: every labelled correction matches", len(tp) == len(corrections), str(set(corrections) - set(tp)))
    check("D10: no labelled neutral prompt matches", not fp, str(fp))
    check("prompt record holds no prompt text", "failing" not in json.dumps(p("still failing with the same error")))
    check("slash command and envelope are marked skipped", p("/review").get("skipped") is True
          and p("<system-reminder>x</system-reminder>").get("skipped") is True and "skipped" not in p("hello"))
    check("is_correction skips slash commands and envelopes by itself", not h.is_correction("/review that's wrong")
          and not h.is_correction("<task-notification>still failing</task-notification>"))
    c = h.build_signal({"session_id": "s", "trigger": "auto"}, "PostCompact")
    check("PostCompact trigger recorded", c.get("kind") == "compact" and c.get("trigger") == "auto", str(c))
    check("unknown trigger normalised", h.build_signal({"session_id": "s", "trigger": "x"}, "PostCompact")["trigger"] == "unknown")
    check("other events build nothing", h.build_signal({"session_id": "s"}, "PreCompact") == {})
    finish()


# ---------------------------------------------------------------- D7 citations, D8 commit facts
def test_citations_and_commit_facts() -> None:
    h = load(HOOK, "gw_tel_acc_cit")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td).resolve()
        repo = td / "repo"
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "a.py").write_text("".join(f"line {i}\n" for i in range(10)))
        (repo / "README.md").write_text("x\n")
        (td / "outside.py").write_text("x\n" * 50)
        (repo / "src" / "link.py").symlink_to(td / "outside.py")
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        text = ("See src/a.py:3 and src/a.py:2-10, README.md:1, src/a.py:11, src/a.py:5-12, src/missing.py:4, "
                f"{repo}/src/a.py:4, {td}/outside.py:2, ../outside.py:1, src/link.py:1, "
                "db.example.com:5432, node.js:18, https://github.com/o/r/blob/main/src/a.py:3 and 10:30.")
        c = h.check_citations(text, str(repo / "src"))
        # checked: src/a.py:3, src/a.py:2-10, README.md:1 (git top level), src/a.py:11, src/a.py:5-12, src/missing.py:4,
        #          absolute inside -> 7; resolved: 3, 2-10, README:1, absolute 4 -> 4
        # unchecked: absolute outside, ../ escape, symlink out, host:port, node.js:18 -> 5; URL span and 10:30 ignored
        check("D7 citations: checked 7, resolved 4, unchecked 5", c == {"checked": 7, "resolved": 4, "unchecked": 5}, str(c))
        check("no cwd: nothing is checkable", h.check_citations("src/a.py:3", "")["checked"] == 0)
        with open(repo / "big.log", "wb") as fh:
            fh.write(b"x\n" * (3 * 1024 * 1024))  # 6 MB, over the 5 MB cap
        c = h.check_citations("see big.log:100, README.md:1 and README.md:0", str(repo))
        check("too-large file or malformed range -> not checkable, never unresolved",
              c == {"checked": 1, "resolved": 1, "unchecked": 2}, str(c))
        many = " ".join(f"src/a.py:{i % 9 + 1}-{i % 9 + 2}" for i in range(9)) + " " + " ".join(f"f{i}/x.py:1" for i in range(80))
        c = h.check_citations(many, str(repo))
        check("at most 50 distinct citations per reply", c["checked"] + c["unchecked"] <= 50, str(c))

        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin",
                        "https://alice:ghp_SECRET123@github.com/acme/widgets.git"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q",
                        "--allow-empty", "-m", "x"], check=True)
        f = h.commit_facts(str(repo))
        check("D8 commit facts: 40-hex head and owner/repo only", len(f.get("head", "")) == 40 and f.get("repo") == "acme/widgets"
              and "SECRET" not in json.dumps(f) and "alice" not in json.dumps(f), json.dumps(f))
        subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", "git@gitlab.com:acme/widgets.git"], check=True)
        check("non-GitHub origin -> no repo", "repo" not in h.commit_facts(str(repo)))
    finish()


def test_latest_usage_cost() -> None:
    h = load(HOOK, "gw_tel_acc_usage")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with Env(td):
            now = time.time()
            iso_ = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
            (td / "usage.jsonl").write_text(
                json.dumps({"ts": iso_(now - 30), "session_id": "s", "ctx_pct": 42.0, "cost_usd": 1.25}) + "\n"
                + json.dumps({"ts": iso_(now - 5), "session_id": "other", "cost_usd": 9}) + "\n")
            u = h.latest_usage("s", now)
            check("D11: fresh reading -> ctx_pct, cost_usd and its age", u.get("ctx_pct") == 42.0 and u.get("cost_usd") == 1.25
                  and 29 <= u.get("cost_age_s", -1) <= 31, str(u))
            u = h.latest_usage("s", now + 120)
            check("D11: cost older than 60 s dropped, ctx kept", "cost_usd" not in u and u.get("ctx_pct") == 42.0, str(u))
            check("D11: unknown session -> nothing", h.latest_usage("unknown", now) == {})
    finish()


# ---------------------------------------------------------------- end to end through the hook processes
REVIEWED = "REVIEW RESULT\nVerdict: changes-required\nMust-fix: 1"


def test_hook_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with Env(td):
            env = dict(os.environ)
            base = {"session_id": "s1", "prompt_id": "p1", "cwd": str(td)}
            run_hook(HOOK, {**base, "hook_event_name": "UserPromptSubmit", "prompt": "still failing, token=abc"}, env)
            run_hook(HOOK, {**base, "hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_use_id": "t1",
                            "tool_input": {"command": "pytest -q"}, "error": "Exit code 1\nboom"}, env)
            run_hook(HOOK, {**base, "hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": "ecc:code-reviewer",
                            "last_assistant_message": REVIEWED}, env)
            run_hook(HOOK, {**base, "hook_event_name": "PostCompact", "trigger": "manual"}, env)
            r = run_hook(HOOK, {**base, "hook_event_name": "Notification", "message": "x"}, env)
            sig_ = lines(td / "signals.jsonl")
            check("signals: prompt, review, compact in order; other events write nothing",
                  [s["kind"] for s in sig_] == ["prompt", "review", "compact"] and r.returncode == 0
                  and not (td / "events.jsonl").exists(), str(sig_))
            check("every signal carries prompt_id and schema 1", all(s.get("prompt_id") == "p1" and s.get("schema") == 1 for s in sig_))
            rows = lines(td / "tool_events.jsonl")
            check("tool row: prompt_id, tool_use_id, kind test, result fail", len(rows) == 1 and rows[0].get("result") == "fail"
                  and rows[0].get("tool_use_id") == "t1" and rows[0].get("prompt_id") == "p1", str(rows))
            raw = (td / "signals.jsonl").read_text() + (td / "tool_events.jsonl").read_text()
            check("no prompt, command or output text stored", all(x not in raw for x in ("token", "abc", "pytest", "boom")))
            check("signals file 0600", ((td / "signals.jsonl").stat().st_mode & 0o777) == 0o600)
            env["GROUNDWORK_TELEMETRY"] = "off"
            before = (td / "signals.jsonl").read_text()
            run_hook(HOOK, {**base, "hook_event_name": "UserPromptSubmit", "prompt": "hi"}, env)
            check("GROUNDWORK_TELEMETRY=off -> nothing written", (td / "signals.jsonl").read_text() == before)
            env.pop("GROUNDWORK_TELEMETRY")
            target = td / "target.txt"
            target.write_text("")
            link = td / "link.jsonl"
            link.symlink_to(target)
            env["GROUNDWORK_SIGNALS_PATH"] = str(link)
            r = run_hook(HOOK, {**base, "hook_event_name": "UserPromptSubmit", "prompt": "hi"}, env)
            check("a symlinked signals path is never followed", target.read_text() == "" and r.returncode == 0)
            fifo = td / "fifo.jsonl"
            os.mkfifo(fifo)
            env["GROUNDWORK_SIGNALS_PATH"] = str(fifo)
            t0 = time.time()
            r = run_hook(HOOK, {**base, "hook_event_name": "UserPromptSubmit", "prompt": "hi"}, env)
            check("a FIFO at the signals path does not block the hook", r.returncode == 0 and time.time() - t0 < 10)
    finish()


def test_guardrails() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with Env(td):
            env = dict(os.environ)
            payload = {"tool_name": "Bash", "session_id": "s1", "prompt_id": "p1", "tool_use_id": "tu7",
                       "tool_input": {"command": "git push origin main"}, "cwd": str(td), "hook_event_name": "PreToolUse"}
            p = run_hook(PUSH, payload, env)
            sig_ = lines(td / "signals.jsonl")
            check("push guard: deny printed and recorded with its tool_use_id", '"deny"' in p.stdout and bool(sig_)
                  and sig_[-1].get("hook") == "push_guard" and sig_[-1].get("decision") == "deny"
                  and sig_[-1].get("tool_use_id") == "tu7" and sig_[-1].get("cause") == "policy", p.stdout[:200] + str(sig_))
            # design D6: the guard without groundwork_shared.py next to it still denies
            iso_dir = td / "isolated"
            iso_dir.mkdir()
            shutil.copy(PUSH, iso_dir / PUSH.name)
            p = run_hook(iso_dir / PUSH.name, payload, env)
            check("guard-module-missing: push still denied, exit 0", p.returncode == 0 and '"deny"' in p.stdout,
                  p.stdout[:200] + p.stderr[-300:])
            env["GROUNDWORK_SIGNALS_PATH"] = "/proc/nonexistent/x/signals.jsonl"
            p = run_hook(PUSH, payload, env)
            check("unwritable signals path: push still denied", p.returncode == 0 and '"deny"' in p.stdout, p.stderr[-200:])
    finish()


# ---------------------------------------------------------------- report: fixtures
REF = "2026-10-20"
BASE = calendar.timegm((2026, 10, 15, 10, 0, 0))


def iso(t: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def stop(t, sid="s1", pid="p1", outcome="complete", validation="verified", impl=True, cit=(0, 0, 0), version="2.6.0",
         cost=None, cost_age=None, head=None, repo=None):
    ob = {"files_changed": 1 if impl else 0, "implementation_performed": impl, "tests_run": False, "deployment_performed": False}
    if cit is not None:
        ob["citations"] = dict(zip(("checked", "resolved", "unchecked"), cit))
    if cost is not None:
        ob.update(cost_usd=cost, cost_age_s=cost_age)
    if head:
        ob.update(head=head, repo=repo)
    return {"schema": 2, "ts": iso(t), "session_id": sid, "prompt_id": pid, "harness_version": version, "observed": ob,
            "declared": {"outcome": outcome, "validation": validation, "block_present": True}}


def row(t, sid="s1", pid="p1", kind=None, result=None, ok=True, tuid="", commit=False):
    r = {"schema": 1, "ts": iso(t), "session_id": sid, "prompt_id": pid, "tool": "Bash", "category": "builtin", "success": ok}
    if kind:
        r["kind"] = kind
    if result:
        r["result"] = result
    if tuid:
        r["tool_use_id"] = tuid
    if commit:
        r["git_commit"] = True
    return r


def sig(t, kind, sid="s1", pid="p1", **kw):
    return {"schema": 1, "ts": iso(t), "session_id": sid, "prompt_id": pid, "kind": kind, **kw}


def gaps_of(rep, events, rows=(), signals=(), ledger=(), window=30, ci=None):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for name, items in (("e", events), ("r", rows), ("s", signals)):
            (td / name).write_text("".join(json.dumps(x) + "\n" for x in items))
        recs, _ = rep.load_events(td / "e")
        g = rep.performance_gaps(recs, rep.load_tool_rows(td / "r"), rep.load_signals(td / "s"), list(ledger), window,
                                 dt.date.fromisoformat(REF), ci)
    return {q["id"]: q for q in g["questions"]}, g


def task(created, complete=True, reviews=(), ops=(), sid="s9", tier="MATERIAL", truncated=False):
    return {"created": created, "tier": tier, "complete": complete, "sid": sid, "reviews": list(reviews),
            "ops": list(ops), "truncated": truncated}


# ---------------------------------------------------------------- report: questions
def test_q1_q2() -> None:
    rep = load(REPORT, "gw_rep_acc_q1")
    ev, rows = [], []
    # 6 file-changing turns declared complete and verified: last known test fail x2 (one fail-only, one pass then fail),
    # fail then pass, piped only (unknown), and two with no test call
    plan = [["fail"], ["pass", "fail"], ["fail", "pass"], ["unknown"], [], []]
    for i, results in enumerate(plan):
        t = BASE + i * 600
        for j, res in enumerate(results):
            rows.append(row(t - 100 + j, pid=f"p{i}", kind="test", result=res, ok=res != "fail"))
        ev.append(stop(t, pid=f"p{i}"))
    q, _ = gaps_of(rep, ev, rows)
    check("Q1a: 2 of 6 complete turns ended on a failing test", (q["1a"]["num"], q["1a"]["den"]) == (2, 6), str(q["1a"]))
    check("Q1a: 5..19 cases flagged low data", "low data" in q["1a"]["answer"], q["1a"]["answer"])
    check("Q1b: 2 of 6 verified turns ran no check of any result (a piped test is still a check)",
          (q["1b"]["num"], q["1b"]["den"]) == (2, 6), str(q["1b"]))
    check("Q2: final states pass 1, fail 2, unknown 1, none 2; fail share 2/3",
          "pass 1, fail 2, unknown 1, no test 2" in q["2"]["notes"][0] and (q["2"]["num"], q["2"]["den"]) == (2, 3), str(q["2"]))
    check("Q2: fewer than 5 known -> insufficient data (3)", q["2"]["answer"] == "insufficient data (3)", q["2"]["answer"])
    q, _ = gaps_of(rep, [stop(BASE, pid="fp")], [row(BASE - 9, pid="fp", kind="test", result="fail", ok=False),
                                                   row(BASE - 5, pid="fp", kind="test", result="pass")])
    check("Q2 scenario: fail then pass -> final state pass, not counted in 1a",
          "pass 1, fail 0" in q["2"]["notes"][0] and q["1a"]["num"] == 0, str(q["2"]) + str(q["1a"]))
    q, _ = gaps_of(rep, ev + [stop(BASE + 9000, pid="px", outcome="unknown")],
                   rows + [row(BASE + 8990, pid="px", kind="test", result="fail", ok=False)])
    check("1c: outcome unstated and last test failed -> counted", q["1c"]["answer"] == "1", q["1c"]["answer"])
    check("Q1a shows the outcome-unstated share", any("Outcome unstated in 14% (1/7)" in n for n in q["1a"]["notes"]),
          str(q["1a"]["notes"]))
    q, _ = gaps_of(rep, [stop(BASE, cit=None)], [row(BASE - 5, kind="test", result="fail", ok=False)])
    check("turns written before this change (no citations field) are left out of Q1/Q2",
          q["1a"]["den"] == 0 and q["1a"]["answer"] == "insufficient data (0)")
    finish()


def test_turn_merge_and_attribution() -> None:
    rep = load(REPORT, "gw_rep_acc_d3")
    ev = [stop(BASE, outcome="complete", cit=(2, 1, 0)), stop(BASE + 20, outcome="unknown", cit=(1, 1, 0))]
    sg = [sig(BASE + 10, "guardrail", hook="reply_check", decision="block", cause="policy")]
    q, g = gaps_of(rep, ev, signals=sg)
    check("two Stops of one prompt = one turn", g["head"][0] == "1 turn(s) in the period", str(g["head"]))
    check("merged turn keeps the stated outcome (complete) and sums citations",
          (q["5"]["num"], q["5"]["den"]) == (2, 3) and q["1a"]["den"] == 1, str(q["5"]) + str(q["1a"]))
    check("Q11: the reply check sent it back -> 1/1", (q["11"]["num"], q["11"]["den"]) == (1, 1), str(q["11"]))
    rows = [row(BASE + 100, pid="p-lost", kind="test", result="fail", ok=False),
            row(BASE - 50, pid="", kind="test", result="fail", ok=False)]
    q, g = gaps_of(rep, [stop(BASE)], rows)
    check("no_stop turn counted apart", "1 with tool calls but no Stop record" in " ".join(g["head"]), str(g["head"]))
    check("fallback-matched record counted and labelled", "1 record(s) without a prompt id matched by time" in g["head"], str(g["head"]))
    check("fallback row belongs to the next Stop of the session", q["1a"]["num"] == 1, str(q["1a"]))
    old = BASE - 40 * 86400
    q, _ = gaps_of(rep, [stop(old, pid="old"), stop(BASE, pid="new")], [row(old - 10, pid="old", kind="test", result="fail", ok=False)])
    check("window edge: out-of-window failure affects no in-window turn", (q["1a"]["num"], q["1a"]["den"]) == (0, 1), str(q["1a"]))
    finish()


def test_q3_ledger() -> None:
    rep = load(REPORT, "gw_rep_acc_q3")
    q, _ = gaps_of(rep, [stop(BASE)])
    check("empty ledger -> 3a/3b not collected: task ledger empty",
          q["3a"]["answer"] == q["3b"]["answer"] == "not collected: task ledger empty", q["3a"]["answer"])
    L = [task(BASE, reviews=[(BASE + 10, 2), (BASE + 20, 0)], ops=[BASE + 30]),   # clean review before the operation
         task(BASE, reviews=[(BASE + 10, 0)], ops=[BASE + 30, BASE + 50]),        # clean review before the operations
         task(BASE, reviews=[(BASE + 40, 0)], ops=[BASE + 30]),                   # operation before review -> 3a
         task(BASE, complete=True, reviews=[]),                                    # complete, never reviewed -> 3a
         task(BASE, complete=False, reviews=[(BASE + 5, 1), (BASE + 6, 3), (BASE + 7, 0)]),
         task(BASE, complete=False, reviews=[(BASE + 5, None)]),                   # no known must-fix
         task(BASE, reviews=[(BASE + 5, 1)], truncated=True),                      # history lost its start
         task(BASE, tier="STANDARD", sid="s1")]
    q, _ = gaps_of(rep, [stop(BASE)], ledger=L)
    check("Q3a: 2 of 4 shipped before a clean review", (q["3a"]["num"], q["3a"]["den"]) == (2, 4), str(q["3a"]))
    check("Q3b: 2 of 4 first reviews found defects; median 1.5 reviews until clean",
          (q["3b"]["num"], q["3b"]["den"]) == (2, 4)
          and any("median reviews until must-fix 0: 1.5 (4 tasks)" in n for n in q["3b"]["notes"]), str(q["3b"]))
    check("truncated history left out and counted", any("1 task(s) left out" in n for n in q["3b"]["notes"]), str(q["3b"]["notes"]))
    sg = [sig(BASE, "review", sid="s1", agent_id="a1", parsed=True, must_fix=0),
          sig(BASE + 1, "review", sid="s2", agent_id="a2", parsed=True, must_fix=0),
          sig(BASE + 2, "review", sid="s2", agent_id="a2", parsed=False), sig(BASE + 3, "review", sid="s2", parsed=False)]
    q, _ = gaps_of(rep, [stop(BASE)], signals=sg, ledger=L)
    check("Q3c: reviews outside ledger sessions, de-duplicated by agent id", q["3c"]["answer"] == "2", q["3c"]["answer"])
    # the real ledger reader: review and operation events from history, no command text kept
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "repo-abc1234567"
        d.mkdir()
        (d / "repo.json").write_text(json.dumps({"root": "/x"}))
        (d / "GW-1.json").write_text(json.dumps({"tier": "MATERIAL", "state": "complete", "created_at": BASE, "session_id": "s9",
                                                  "history": [{"ts": BASE, "event": "intake", "detail": "MATERIAL task"},
                                                              {"ts": BASE + 5, "event": "operation", "detail": "terraform apply SECRET"},
                                                              {"ts": BASE + 9, "event": "review", "detail": "ecc:code-reviewer: must_fix=2"},
                                                              {"ts": BASE + 9, "event": "review", "detail": "x: must_fix=None"}]}))
        got = rep.load_ledger(Path(td))
        check("ledger reader: reviews, operations, not truncated, no command text",
              len(got) == 1 and got[0]["reviews"] == [(BASE + 9, 2), (BASE + 9, None)] and got[0]["ops"] == [BASE + 5]
              and got[0]["truncated"] is False and "SECRET" not in json.dumps(got), json.dumps(got))
    finish()


def test_q4_corrections() -> None:
    rep = load(REPORT, "gw_rep_acc_q4")
    ev, sg = [], []
    for i in range(6):
        t = BASE + i * 20000
        ev.append(stop(t, pid=f"p{i}"))
        sg.append(sig(t + 600, "prompt", pid=f"n{i}", correction=i < 2))
    ev.append(stop(BASE + 6 * 20000, pid="p6"))
    sg.append(sig(BASE + 6 * 20000 + 3 * 3600, "prompt", pid="late", correction=True))
    ev.append(stop(BASE + 7 * 20000, pid="p7"))
    sg += [sig(BASE + 7 * 20000 + 60, "prompt", pid="env", correction=False, skipped=True),
           sig(BASE + 7 * 20000 + 120, "prompt", pid="me", correction=True)]
    q, _ = gaps_of(rep, ev, signals=sg)
    # p0..p5: next prompt 10 min later (2 corrections); p6: next prompt 3 h later, not counted;
    # p7: the envelope prompt is skipped and the user's correction 2 min later counts
    check("Q4: 3 of 7 complete turns followed by a correction within 2 h", (q["4"]["num"], q["4"]["den"]) == (3, 7), str(q["4"]))
    finish()


def test_q5_q7_q8_q9_q10_q11() -> None:
    rep = load(REPORT, "gw_rep_acc_more")
    q, _ = gaps_of(rep, [stop(BASE, pid="a", cit=(4, 3, 1)), stop(BASE + 60, pid="b", cit=(2, 2, 1))])
    check("Q5: 5/6 resolved, low data, 2 not checkable", (q["5"]["num"], q["5"]["den"]) == (5, 6)
          and "low data" in q["5"]["answer"] and "2 not checkable" in q["5"]["notes"], str(q["5"]))
    ev = [stop(BASE + i * 100, pid=f"p{i}") for i in range(4)]
    rows = [row(BASE + 5, pid="p0", tuid="tu1", ok=False)]
    sg = [sig(BASE + 1, "guardrail", pid="p0", hook="task_gate", decision="ask", cause="policy", tool_use_id="tu1"),
          sig(BASE + 2, "guardrail", pid="p0", hook="task_gate", decision="ask", cause="policy", tool_use_id="tu3"),
          sig(BASE + 101, "guardrail", pid="p1", hook="task_gate", decision="ask", cause="internal_error", tool_use_id="tu2"),
          sig(BASE + 102, "guardrail", pid="p1", hook="task_gate", decision="ask", cause="policy", tool_use_id="tu4"),
          sig(BASE + 103, "guardrail", pid="p1", hook="task_gate", decision="ask", cause="policy", tool_use_id="tu5"),
          sig(BASE + 201, "guardrail", pid="p2", hook="review_gate", decision="block", cause="policy"),
          sig(BASE + 250, "review", pid="p2", agent_id="r1", parsed=True, must_fix=0)]
    q, _ = gaps_of(rep, ev, rows, sg)
    n7 = " | ".join(q["7"]["notes"])
    check("Q7: distinct (prompt, hook, decision) firings; no per-100 rate below 5 turns", "review_gate 1; task_gate 2 |" in n7, n7)
    check("Q7: an ask joined by tool_use_id to a PostToolUseFailure row counts as approved (1 of 5 asks)",
          "asks approved: 20% (1/5) low data" in n7 and q["7"]["answer"] == "3 firing(s) in 4 turns", n7 + q["7"]["answer"])
    check("Q7: internal_error decisions counted", "1 decided because the guard could not check" in n7, n7)
    check("Q11: turns the review gate or reply check sent back", (q["11"]["num"], q["11"]["den"]) == (1, 4), str(q["11"]))
    ev = [stop(BASE, pid="a", outcome="partial", cost=1.0, cost_age=10),
          stop(BASE + 600, pid="b", cost=1.5, cost_age=20),
          stop(BASE + 630, pid="c", cost=1.5, cost_age=50)]
    q, _ = gaps_of(rep, ev)
    check("Q8: two turns 30 s apart sharing one reading -> the second is outside coverage (1/2)",
          "coverage 50% (1/2) of completed turns" in q["8"]["notes"][0] and q["8"]["answer"] == "insufficient data (1)", str(q["8"]))
    ev = [stop(BASE + i * 100, pid=f"p{i}") for i in range(8)]
    rows = [row(BASE + i * 100 - 5, pid=f"p{i}", kind="test", result="fail" if i >= 5 else "pass") for i in range(8)]
    q, _ = gaps_of(rep, ev, rows, [sig(BASE + 450, "compact", pid="p5", trigger="auto")])
    check("Q9: one compaction; 1a of the 3 turns before and after side by side",
          q["9"]["answer"] == "1 compaction(s)" and "1a before insufficient data (3) · after insufficient data (3)" in q["9"]["notes"][0],
          str(q["9"]))
    ev = [stop(BASE + i * 100, pid=f"a{i}", version="2.5.0") for i in range(5)] + \
         [stop(BASE + 10000 + i * 100, pid=f"b{i}", version="2.6.0") for i in range(3)]
    rows = [row(BASE + i * 100 - 5, pid=f"a{i}", kind="test", result="fail" if i < 2 else "pass") for i in range(5)]
    q, _ = gaps_of(rep, ev, rows)
    v = {r[0]: r for r in q["10"]["rows"]}
    check("Q10: 2.5.0 shows its 1a rate, 2.6.0 insufficient data",
          v["2.5.0"][1] == "40% (2/5) low data" and v["2.6.0"][1] == "insufficient data (3)", str(q["10"]["rows"]))
    finish()


def test_q6_ci() -> None:
    rep = load(REPORT, "gw_rep_acc_ci")
    sha = "a" * 40
    ev = [stop(BASE, pid="c1", head=sha, repo="acme/widgets"), stop(BASE + 60, pid="c2", head="b" * 40, repo="../../user")]
    rows = [row(BASE - 5, pid="c1", commit=True), row(BASE + 55, pid="c2", commit=True)]
    q, _ = gaps_of(rep, ev, rows)
    check("Q6 without --github: opt-in with the commit-turn count", q["6"]["answer"] == "opt-in: run generate --github"
          and "2 commit turn(s) recorded" in q["6"]["notes"], str(q["6"]))
    calls = []

    class P:
        def __init__(self, rc=0, out="", err=""):
            self.returncode, self.stdout, self.stderr = rc, out, err

    def fake(argv, **kw):
        calls.append(argv)
        url = argv[-1]
        if "check-runs" in url:
            page = int(url.rsplit("page=", 1)[1])
            batch = [{"status": "completed", "conclusion": "success"}] * (100 if page == 1 else 1)
            return P(out=json.dumps({"total_count": 101, "check_runs": batch}))
        return P(out=json.dumps({"statuses": [{"state": "success"}]}))
    res = rep.fetch_ci([("acme/widgets", sha), ("../../user", "b" * 40), ("acme/x", "nothex")], run=fake)
    check("D8: paginated check-runs plus status -> pass", res[("acme/widgets", sha)] == "pass", str(res))
    check("D8: an unsafe repo or SHA never reaches gh", res[("../../user", "b" * 40)] == "invalid"
          and res[("acme/x", "nothex")] == "invalid" and all("../../user" not in " ".join(c) for c in calls), str(calls))
    check("D8: read-only GET, second page fetched", all(c[:4] == ["gh", "api", "--method", "GET"] for c in calls)
          and any("page=2" in c[-1] for c in calls), str(calls))
    check("D8 mapping: failure / failed status / pending / no checks / status only",
          rep.ci_state([{"status": "completed", "conclusion": "timed_out"}], []) == "fail"
          and rep.ci_state([{"status": "completed", "conclusion": "success"}], [{"state": "failure"}]) == "fail"
          and rep.ci_state([{"status": "in_progress"}], []) == "pending" and rep.ci_state([], []) == "no_checks"
          and rep.ci_state([], [{"state": "success"}]) == "pass"
          and rep.ci_state([{"status": "completed", "conclusion": "success"}], [{"state": "pending"}]) == "pending")
    res = rep.fetch_ci([("acme/widgets", sha)], run=lambda a, **k: P(1, err="gh: Not Found (HTTP 404)"))
    check("D8: 404 -> not on GitHub", res[("acme/widgets", sha)] == "not_on_github", str(res))
    res = rep.fetch_ci([("acme/widgets", sha)], run=lambda a, **k: P(4, err="To get started with GitHub CLI, please run:  gh auth login"))
    check("D8: not logged in -> not available", res == {"_unavailable": "gh is not logged in"}, str(res))

    def missing(*a, **k):
        raise FileNotFoundError("gh")
    check("D8: gh missing -> not available", rep.fetch_ci([("acme/widgets", sha)], run=missing) == {"_unavailable": "gh is not installed"})
    q, _ = gaps_of(rep, ev, rows, ci={("acme/widgets", sha): "pass", ("../../user", "b" * 40): "invalid"})
    check("Q6 with results: 1/1 pass shown as insufficient data, invalid counted as not readable",
          q["6"]["answer"] == "insufficient data (1)" and "not readable 1" in q["6"]["notes"][0], str(q["6"]))
    finish()


def test_generate_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with Env(td):
            (td / "events.jsonl").write_text(json.dumps(stop(BASE)) + "\n")
            (td / "tool_events.jsonl").write_text(json.dumps(row(BASE - 5, kind="test", result="fail", ok=False)) + "\n")
            env = dict(os.environ)
            stub = td / "bin"
            stub.mkdir()
            (stub / "gh").write_text("#!/bin/sh\necho called >> \"$GH_LOG\"\nexit 1\n")
            (stub / "gh").chmod(0o755)
            env.update(PATH=f"{stub}:{env['PATH']}", GH_LOG=str(td / "gh.log"))
            p = subprocess.run([sys.executable, str(REPORT), "generate", "--out", str(td / "out"), "--now", REF, "--snapshot"],
                               capture_output=True, text=True, env=env, timeout=60)
            md = (td / "out" / f"{REF}.md").read_text()
            page = (td / "out" / "dashboard.html").read_text()
            check("generate exits 0; last stdout line is records=",
                  p.returncode == 0 and p.stdout.strip().splitlines()[-1].startswith("records="), p.stdout + p.stderr)
            check("without --github no gh call is made", not (td / "gh.log").exists())
            check("Markdown and HTML carry the Performance gaps section, Q1a to Q11",
                  "## Performance gaps" in md and 'id="perf-gaps"' in page
                  and all(f"| {i} |" in md for i in ("1a", "1b", "2", "3a", "4", "5", "6", "7", "8", "9", "10", "11")))
            check("Q1a counts the failing turn", "| 1a | Does it say complete while tests fail? | insufficient data (1) |" in md, md[:600])
            check("benchmark footer and relabelled broad-match card",
                  "Benchmark score per release: not collected" in md and "Complete + test-shaped command" in page
                  and "Verified accuracy" not in page and "Rework rate" not in page)
            check("no session or prompt ids embedded in the page", '"s1"' not in page and '"p1"' not in page)
            p = subprocess.run([sys.executable, str(REPORT), "generate", "--out", str(td / "out"), "--now", REF, "--github"],
                               capture_output=True, text=True, env=env, timeout=60)
            check("--github with no commit turns: still exits 0 and records= stays last",
                  p.returncode == 0 and p.stdout.strip().splitlines()[-1].startswith("records="), p.stdout + p.stderr)
    finish()


def test_review_fixes() -> None:
    """Regression tests for the independent-review findings (correctness and security reviews)."""
    h = load(HOOK, "gw_tel_acc_fix")
    rec = lambda cmd, event="PostToolUse", **kw: h.build_tool_record(
        {"tool_name": "Bash", "session_id": "s", "tool_input": {"command": cmd}, **kw}, event)
    fail = lambda cmd, code=1: rec(cmd, "PostToolUseFailure", error=f"Exit code {code}")
    check("masked commit is not a commit turn", "git_commit" not in rec("git commit -m x || true")
          and "git_commit" not in rec("git commit -m x | cat") and rec("git add . && git commit -m x").get("git_commit") is True)
    check("exit 126/127 (command not found) -> unknown", fail("pytest -q", 127).get("result") == "unknown"
          and fail("pytest -q", 126).get("result") == "unknown")
    check("--help / --version / --collect-only are not test runs", all("kind" not in rec(c) for c in
          ("pytest --help", "pytest --version", "python3 -m pytest --collect-only -q")))
    p = lambda text: h.build_signal({"session_id": "s", "prompt": text}, "UserPromptSubmit").get("correction")
    check("conditional phrasing is not a correction", not p("if it doesn't work, tell me")
          and not p("when it still fails, tell me") and not p("if the tests are still failing, fix them")
          and p("I tried it when I got home. That's wrong")
          and p("that didn't work"))
    r = h.build_tool_record({"tool_name": "Read", "session_id": "s", "tool_use_id": {"a": "SECRETOBJ"},
                             "prompt_id": "ok-1"}, "PostToolUse")
    check("non-id values are never stored", "tool_use_id" not in r and r.get("prompt_id") == "ok-1", str(r))
    r = h.build_signal({"session_id": "s", "agent_id": "a b/../etc", "agent_type": "code-reviewer",
                        "last_assistant_message": "REVIEW RESULT\nMust-fix: 99999999999999999999"}, "SubagentStop")
    check("odd agent id dropped; must-fix capped", "agent_id" not in r and r.get("must_fix") == 1000, str(r))
    t0 = time.time()
    h.review_fields("\n" * 200000 + "REVIEW RESULT\nMust-fix: 0")
    h.parse_metadata("\n" * 200000 + "Harness metadata\n")
    check("blank-line floods parse quickly", time.time() - t0 < 2, f"{time.time() - t0:.2f}s")

    rep = load(REPORT, "gw_rep_acc_fix")
    # Q6: a commit turn with no GitHub origin is counted on its own, never as "not readable"
    ev = [stop(BASE, pid="c1", head="a" * 40, repo=None)]
    rows = [row(BASE - 5, pid="c1", commit=True)]
    res = rep.fetch_ci(rep.commit_turns(rep.build_turns(rep.load_events(_write(ev))[0], rep.load_tool_rows(_write(rows)), [])[0]),
                       run=lambda *a, **k: (_ for _ in ()).throw(AssertionError("gh must not run")))
    check("Q6: no GitHub remote -> no_remote, gh not called", list(res.values()) == ["no_remote"], str(res))
    # Q3: ledger with tasks but none MATERIAL
    q, _ = gaps_of(rep, [stop(BASE)], ledger=[task(BASE, tier="STANDARD")])
    check("Q3: STANDARD-only ledger says no MATERIAL tasks recorded", q["3a"]["answer"] == "not collected: no MATERIAL tasks recorded")
    # Q7 per-100 shown from 5 turns
    ev = [stop(BASE + i * 100, pid=f"p{i}") for i in range(5)]
    q, _ = gaps_of(rep, ev, signals=[sig(BASE + 1, "guardrail", pid="p0", hook="push_guard", decision="deny", cause="policy")])
    check("Q7: per-100 rate shown from 5 turns", "push_guard 1 (20.0/100)" in q["7"]["notes"][0], q["7"]["notes"][0])
    q, _ = gaps_of(rep, ev, signals=[sig(BASE + 1, "guardrail", pid="p0", hook="push_guard", decision="deny", cause="policy"),
                                     sig(BASE + 2, "guardrail", pid="lost", hook="push_guard", decision="deny", cause="policy")])
    check("Q7: a firing in a prompt with no Stop record is outside the per-100 population",
          "push_guard 1 (20.0/100)" in q["7"]["notes"][0], q["7"]["notes"][0])
    # Q8 positive median and Q10 change against the previous period
    ev = [stop(BASE + i * 600, pid=f"k{i}", outcome="complete", cost=1.0 + i, cost_age=10) for i in range(7)]
    q, _ = gaps_of(rep, ev)
    check("Q8: median $1.00 over 6 turns (low data), coverage 6/7", q["8"]["answer"] == "$1.00 median low data"
          and "coverage 86% (6/7)" in q["8"]["notes"][0], str(q["8"]))
    prev = BASE - 30 * 86400
    ev = [stop(prev + i * 100, pid=f"o{i}") for i in range(5)] + [stop(BASE + i * 100, pid=f"n{i}") for i in range(5)]
    rows = [row(prev + i * 100 - 5, pid=f"o{i}", kind="test", result="fail", ok=False) for i in range(5)] + \
           [row(BASE + i * 100 - 5, pid=f"n{i}", kind="test", result="pass") for i in range(5)]
    q, _ = gaps_of(rep, ev, rows)
    check("Q10: change against the previous period", "1a -100.0 points" in q["10"]["notes"][0], q["10"]["notes"][0])
    # Q9: two nearby compactions do not double-count a turn
    ev = [stop(BASE + i * 100, pid=f"z{i}") for i in range(4)]
    rows = [row(BASE + i * 100 - 5, pid=f"z{i}", kind="test", result="fail", ok=False) for i in range(4)]
    q, _ = gaps_of(rep, ev, rows, [sig(BASE + 150, "compact", pid="z1"), sig(BASE + 160, "compact", pid="z1")])
    check("Q9: overlapping windows counted once", "1a before insufficient data (2)" in q["9"]["notes"][0], q["9"]["notes"][0])
    # poisoned local files never take the dashboard down
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "s").write_text('{"schema":1,"ts":"2026-10-15T10:00:00Z","session_id":"s","kind":"review","parsed":true,"must_fix":Infinity}\n')
        d = td / "led" / "r-1"
        d.mkdir(parents=True)
        (d / "GW-1.json").write_text('{"tier":"MATERIAL","created_at":1e300,"history":[]}')
        (d / "GW-2.json").write_text('{"tier":"MATERIAL","created_at":Infinity,"history":[]}')
        fifo = td / "fifo"
        os.mkfifo(fifo)
        t0 = time.time()
        sigs, led, fr = rep.load_signals(td / "s"), rep.load_ledger(td / "led"), rep.load_signals(fifo)
        check("poisoned numbers skipped; FIFO not read", sigs and sigs[0]["must_fix"] is None and led == [] and fr == []
              and time.time() - t0 < 5, str(sigs) + str(led))
    finish()


def test_task_gate_guardrails() -> None:
    gate = HOOKS / "groundwork_task_gate.py"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with Env(td):
            env = dict(os.environ)
            base = {"hook_event_name": "PreToolUse", "session_id": "s1", "prompt_id": "p1", "tool_use_id": "tu9",
                    "tool_name": "Bash", "cwd": str(td)}
            p = run_hook(gate, {**base, "tool_input": {"command": "cat <<EOF $(("}}, env)
            sig_ = lines(td / "signals.jsonl")
            check("task gate: an unparseable command asks and records cause internal_error",
                  '"ask"' in p.stdout and sig_ and sig_[-1].get("hook") == "task_gate" and sig_[-1].get("cause") == "internal_error"
                  and sig_[-1].get("tool_use_id") == "tu9", p.stdout[:200] + str(sig_))
            iso_dir = td / "isolated"
            iso_dir.mkdir()
            for f in HOOKS.glob("*.py"):
                if f.name != "groundwork_shared.py":
                    shutil.copy(f, iso_dir / f.name)
            p = run_hook(iso_dir / gate.name, {**base, "tool_input": {"command": "cat <<EOF $(("}}, env)
            check("task gate without groundwork_shared still asks", p.returncode == 0 and '"ask"' in p.stdout, p.stdout[:200] + p.stderr[-300:])
    finish()


def test_stop_records_commit_facts() -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td).resolve()
        with Env(td):
            repo = td / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:acme/widgets.git"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-q",
                            "--allow-empty", "-m", "x"], check=True)
            env = dict(os.environ)
            base = {"session_id": "s1", "prompt_id": "p1", "cwd": str(repo)}
            run_hook(HOOK, {**base, "hook_event_name": "PostToolUse", "tool_name": "Bash",
                            "tool_input": {"command": "git commit -m x"}, "tool_response": {}}, env)
            t = td / "t.jsonl"
            t.write_text(json.dumps({"type": "user", "message": {"content": "go"}}) + "\n" + json.dumps(
                {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "git commit -m x"}}]}}) + "\n")
            run_hook(HOOK, {**base, "hook_event_name": "Stop", "transcript_path": str(t), "last_assistant_message": "Complete."}, env)
            ob = lines(td / "events.jsonl")[-1]["observed"]
            check("Stop of a commit turn records head and owner/repo", len(ob.get("head", "")) == 40 and ob.get("repo") == "acme/widgets", str(ob))
            run_hook(HOOK, {**base, "prompt_id": "p2", "hook_event_name": "Stop", "transcript_path": str(t),
                            "last_assistant_message": "Complete."}, env)
            ob = lines(td / "events.jsonl")[-1]["observed"]
            check("a turn without a commit records no head", "head" not in ob, str(ob))
    finish()


def test_third_review_fixes() -> None:
    h = load(HOOK, "gw_tel_acc_fix3")
    r = h.build_tool_record({"tool_name": "Bash", "session_id": "s", "tool_input": {"command": "timeout 60 pytest -q"},
                             "error": "Exit code 124"}, "PostToolUseFailure")
    check("exit 124 (killed by timeout) -> unknown", r.get("result") == "unknown", str(r))
    rep = load(REPORT, "gw_rep_acc_fix3")
    old = [stop(BASE - 1000 - i, pid=f"o{i}", cit=None) for i in range(20)]
    new = [stop(BASE + i * 100, pid=f"n{i}") for i in range(10)]
    sg = [sig(BASE + i * 100 - 5, "guardrail", pid=f"n{i}", hook="reply_check", decision="block", cause="policy") for i in range(5)]
    q, _ = gaps_of(rep, old + new, signals=sg)
    check("Q11 and Q7 count only turns this change recorded", (q["11"]["num"], q["11"]["den"]) == (5, 10)
          and "reply_check 5 (50.0/100)" in q["7"]["notes"][0] and q["7"]["answer"] == "5 firing(s) in 10 turns",
          str(q["11"]) + q["7"]["notes"][0])
    sg = [sig(BASE + 1, "guardrail", pid="n0", hook="push_guard", decision="deny", cause="policy", tool_use_id="t1"),
          sig(BASE + 2, "guardrail", pid="n0", hook="task_gate", decision="ask", cause="policy", tool_use_id="t1")]
    q, _ = gaps_of(rep, new, signals=sg)
    check("Q7: an ask on a call another guard denied is not counted", "asks approved: insufficient data (0)" in " | ".join(q["7"]["notes"]),
          " | ".join(q["7"]["notes"]))
    gate = HOOKS / "groundwork_task_gate.py"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with Env(td):
            env = dict(os.environ)
            base = {"hook_event_name": "PreToolUse", "session_id": "s1", "prompt_id": "hello my secret prompt text",
                    "tool_use_id": {"a": "SECRETOBJ"}, "tool_name": "Bash", "cwd": str(td)}
            p = run_hook(gate, {**base, "tool_input": {"command": "bash -c 'echo \"x'"}}, env)
            sig_ = lines(td / "signals.jsonl")
            check("nested parse failure asks with cause internal_error", '"ask"' in p.stdout and sig_
                  and sig_[-1].get("cause") == "internal_error", p.stdout[:200] + str(sig_))
            p = run_hook(gate, {**base, "tool_input": {"command": "find . -exec bash -c 'echo \"x' \\;"}}, env)
            sig2 = lines(td / "signals.jsonl")
            check("suffixed nested label (find -exec) also records internal_error", '"ask"' in p.stdout
                  and sig2[-1].get("cause") == "internal_error", p.stdout[:200] + str(sig2[-1]))
            raw = (td / "signals.jsonl").read_text()
            check("guardrail records drop values that are not ids", "secret" not in raw and "SECRETOBJ" not in raw
                  and "prompt_id" not in sig_[-1] and "tool_use_id" not in sig_[-1] and sig_[-1]["session_id"] == "s1", raw)
            p = run_hook(PUSH, {**base, "session_id": {"x": 1}, "tool_input": {"command": "git push origin main"}}, env)
            sig_ = lines(td / "signals.jsonl")
            check("push guard: object session id stored as unknown, deny unchanged",
                  '"deny"' in p.stdout and sig_[-1].get("session_id") == "unknown", p.stdout[:200] + str(sig_[-1]))
    finish()


def _write(items) -> Path:
    fd, name = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        f.write("".join(json.dumps(x) + "\n" for x in items))
    return Path(name)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(name)
            fn()
    print("all accuracy-signal checks passed")
