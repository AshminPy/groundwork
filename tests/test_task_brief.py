#!/usr/bin/env python3
"""Deterministic checks for hooks/groundwork_brief.py (feature 3 of
openspec/changes/core-evidence-continuity) — no Claude Code needed.

Run: python3 tests/test_task_brief.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "groundwork_brief.py"
SNAPSHOT = REPO_ROOT / "hooks" / "groundwork_session_snapshot.py"

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
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})


def make_repo(parent: Path, name: str, branch: str = "main") -> Path:
    repo = parent / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", branch)
    (repo / "a.txt").write_text("x\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def run(payload, home: Path, extra=None, raw=None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(home)
    env.pop("GROUNDWORK_BRIEF", None)
    env["GROUNDWORK_TELEMETRY_PATH"] = str(home / "events.jsonl")
    env.update(extra or {})
    return subprocess.run(["python3", str(HOOK)], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, timeout=30, env=env)


def transcript(tmp: Path, tools) -> Path:
    lines = [{"type": "user", "message": {"role": "user", "content": "do it"}}]
    for t in tools:
        lines.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": t, "input": {}}]}})
        lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}})
    p = tmp / "t.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    return p


def telemetry(home: Path, session: str, turns: int) -> None:
    with (home / "events.jsonl").open("a") as f:
        for _ in range(turns):
            f.write(json.dumps({"session_id": session, "observed": {"tools": ["Bash"]}}) + "\n")


def context(r: subprocess.CompletedProcess) -> str:
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    return (out.get("hookSpecificOutput") or {}).get("additionalContext", "")


JUDGMENT = "## Goal\nShip feature 3.\n\n## Next step\nWrite the tests.\n"


def test_paths() -> None:
    print("brief paths")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        home = tmp / "home"
        os.environ["CLAUDE_CONFIG_DIR"] = str(home)
        m = load(HOOK, "groundwork_brief")
        snap = load(SNAPSHOT, "groundwork_session_snapshot")
        repo = make_repo(tmp, "proj")
        p = m.brief_path(str(repo))
        inv = snap.investigation_path(str(repo))
        check("repo key matches the snapshot hook's investigation key", p is not None and p.parent.name == inv.stem,
              f"{p} vs {inv}")
        check("one file per branch, readable name", p is not None and p.name.startswith("main-") and p.suffix == ".md", str(p))
        git(repo, "checkout", "-q", "-b", "feat/x")
        p2 = m.brief_path(str(repo))
        check("branch name is made filename-safe", p2 is not None and p2.name.startswith("feat-x-") and "/" not in p2.name, str(p2))
        git(repo, "checkout", "-q", "-b", "feat-x")
        p3 = m.brief_path(str(repo))
        check("feat/x and feat-x never share a brief", p3 is not None and p3 != p2, f"{p2} {p3}")
        long_a, long_b = "z" * 120 + "a", "z" * 120 + "b"
        git(repo, "checkout", "-q", "-b", long_a)
        pa = m.brief_path(str(repo))
        git(repo, "checkout", "-q", "-b", long_b)
        pb = m.brief_path(str(repo))
        check("long branch names with a shared prefix never share a brief", pa != pb and len(pa.name) < 120, f"{pa.name} {pb.name}")
        other = make_repo(tmp / "elsewhere", "proj")
        check("same folder name, different repo: different key", m.brief_path(str(other)).parent != p.parent)
        check("not a git repo: no path", m.brief_path(str(tmp)) is None)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
    finish()


def test_refresh() -> None:
    print("snapshot refresh")
    m = load(HOOK, "groundwork_brief")
    base = "# Task brief: main\n\n" + JUDGMENT + "\n## Snapshot (hook-written)\n- old\n"
    new = m.refresh_snapshot(base, ["branch: main", "HEAD: abc"])
    check("judgment sections are kept byte for byte", new.startswith(base.split("## Snapshot")[0]), new)
    check("old snapshot replaced, not appended", "- old" not in new and new.count("## Snapshot") == 1, new)
    check("new facts present", "- HEAD: abc" in new, new)
    fresh = m.refresh_snapshot("", ["branch: main"])
    check("empty brief gets the template headings", all(h in fresh for h in ("## Goal", "## Next step", "## Snapshot")), fresh)
    check("template is not counted as filled", not m.judgment_filled(fresh))
    check("written Goal or Next step counts as filled", m.judgment_filled(base))
    middle = "# T\n\n## Goal\nA\n\n## Snapshot (hook-written)\n- old\n\n## Notes\nkeep me\n"
    bidi = m.render_context(Path("/x"), "## Goal\nA\u202eB\u200bC\n")
    check("bidi and zero-width characters are removed on reload", "\u202e" not in bidi and "\u200b" not in bidi, repr(bidi))
    own = "## Goal\nx\n\n## Snapshot hook decisions\nkeep me\n\n## Next step\ny\n"
    out = m.refresh_snapshot(own, ["a"])
    check("a Claude section titled 'Snapshot ...' is never treated as the hook's", "keep me" in out and "## Next step\ny" in out, out)
    check("such a section counts as judgment text", m.judgment_filled("## Snapshot hook decisions\nkeep me\n"))
    check("such a section is loaded at session start", "keep me" in m.render_context(Path("/x"), own))
    check("'## Next Step' (any case) is still shown first",
          m.render_context(Path("/x"), "## Goal\ng\n\n## Next Step\nNS\n").index("NS") < m.render_context(Path("/x"), "## Goal\ng\n\n## Next Step\nNS\n").index("\ng\n"))
    trailing = "## Goal\nx\n\n\n"
    check("trailing blank lines outside the snapshot are kept", m.refresh_snapshot(trailing, ["a"]).startswith(trailing))
    check("sections after the snapshot are kept", "keep me" in m.refresh_snapshot(middle, ["x"]))
    finish()


def test_round_trip_and_races() -> None:
    print("byte round-trip, sanitiser, edit race")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        home = tmp / "home"
        repo = make_repo(tmp, "proj")
        os.environ["CLAUDE_CONFIG_DIR"] = str(home)
        m = load(HOOK, "groundwork_brief")
        path = m.brief_path(str(repo))
        path.parent.mkdir(parents=True)
        crlf = b"## Goal\r\nKeep CRLF.\r\n\r\n## Snapshot (x)\r\n- a\r\n"
        path.write_bytes(crlf)
        m.refresh(str(repo), "s", "Stop", ["Bash"])
        check("CRLF judgment text survives a refresh byte for byte", path.read_bytes().startswith(b"## Goal\r\nKeep CRLF.\r\n\r\n"),
              repr(path.read_bytes()[:40]))
        bad = b"## Goal\nab\xff\n\n## Snapshot (x)\n- a\n"
        path.write_bytes(bad)
        m.refresh(str(repo), "s", "Stop", ["Bash"])
        check("invalid UTF-8 brief: left untouched", path.read_bytes() == bad, repr(path.read_bytes()[:40]))
        check("brief file is owner-only", oct(path.stat().st_mode & 0o777) == "0o600")
        check("brief directories are owner-only", oct(path.parent.stat().st_mode & 0o777) == "0o700"
              and oct(path.parent.parent.stat().st_mode & 0o777) == "0o700")
        hidden = "".join(chr(c) for c in (0x2060, 0x061C, 0x2028, 0x2029, 0x85, 0x9F, 0xAD, 0x2061, 0x200B, 0x202E, 0xFEFF,
                                           0xE0041, 0xE007F))
        ctx = m.render_context(Path("/x"), "## Goal\nA" + hidden + "B\n")
        check("every invisible format/control character is removed on reload", "AB" in ctx, repr(ctx[-20:]))
        path.write_text("## Goal\nOriginal.\n\n## Snapshot (x)\n- a\n")
        real = m.refresh_snapshot
        def racing(text, facts):
            path.write_text("## Goal\nEdited by Claude mid-refresh.\n\n## Snapshot (x)\n- a\n")
            m.refresh_snapshot = real
            return real(text, facts)
        m.refresh_snapshot = racing
        m.refresh(str(repo), "s", "Stop", ["Bash"])
        m.refresh_snapshot = real
        check("an edit made during a refresh is never overwritten", "Edited by Claude mid-refresh." in path.read_text(),
              path.read_text())
        m.mark_asked("s-mode")
        check("asked marker is owner-only", oct(m.asked_marker("s-mode").stat().st_mode & 0o777) == "0o600")
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
    finish()


def test_decision_log() -> None:
    print("append-only decision log")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        home = tmp / "home"
        repo = make_repo(tmp, "proj")
        os.environ["CLAUDE_CONFIG_DIR"] = str(home)
        m = load(HOOK, "groundwork_brief")
        path = m.brief_path(str(repo))
        log = m.log_path(path)
        check("log sits beside the brief, per branch", log.parent == path.parent and log.name.startswith(path.stem), str(log))

        def brief(decisions, rejected=""):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("## Goal\ng\n\n## Decisions\n" + decisions + "\n## Rejected\n" + rejected +
                            "\n## Next step\nn\n")

        brief("- Use hooks, not rules (https://code.claude.com/docs/en/hooks)\n- Park the harness\n")
        m.refresh(str(repo), "sess-1", "Stop", ["Bash"])
        text = log.read_text()
        check("new decisions are logged as ADDED with session and time",
              text.count("ADDED") == 2 and "sess-1" in text and "Use hooks, not rules" in text, text)
        check("the decision's link is kept in the log", "https://code.claude.com/docs/en/hooks" in text, text)
        check("a decision without a link or file:line is flagged", "Park the harness" in text and "no evidence cited" in text, text)
        first = log.read_bytes()
        m.refresh(str(repo), "sess-1", "Stop", ["Bash"])
        check("no change: nothing appended (no duplicates)", log.read_bytes() == first)

        brief("- Use hooks, not rules (https://code.claude.com/docs/en/hooks)\n- Park the harness (bench: m2-comparison.md:12)\n",
              "- Separate harness: 39/40 vs 40/40, slower\n")
        m.refresh(str(repo), "sess-2", "PreCompact", [])
        text = log.read_text()
        check("log is append-only: earlier bytes never change", log.read_bytes().startswith(first))
        check("a changed decision records the old text as REMOVED and the new one as ADDED",
              "REMOVED" in text and "m2-comparison.md:12" in text, text)
        check("rejected hypotheses are logged too", "Rejected" in text and "Separate harness" in text, text)

        brief("- Use hooks, not rules (https://code.claude.com/docs/en/hooks)\n")
        m.refresh(str(repo), "sess-3", "Stop", ["Bash"])
        text = log.read_text()
        check("a deleted decision is never lost: logged as REMOVED", text.count("REMOVED") >= 2 and "Separate harness" in text, text)
        check("log file is owner-only", oct(log.stat().st_mode & 0o777) == "0o600")
        check("each entry is one line (no injected newlines)",
              all(ln.startswith(("- ", "#", "<!--")) or not ln.strip() for ln in text.splitlines()), text)

        ctx = m.render_context(path, path.read_text())
        check("session start shows the log path and the latest entries", str(log) in ctx and "REMOVED" in ctx, ctx)
        check("context stays capped", len(ctx) <= 2600, str(len(ctx)))

        long = "- " + ("x" * 400) + " (https://example.com/long-evidence)\n- *Bold* decision (README.md:3)\n"
        brief(long)
        m.refresh(str(repo), "sess-5", "Stop", ["Bash"])
        ctx = m.render_context(path, path.read_text())
        check("a long entry keeps its evidence link when shortened for reload", "https://example.com/long-evidence" in ctx, ctx[-600:])
        check("only one bullet marker is stripped", "*Bold* decision" in log.read_text(), log.read_text()[-300:])
        hidden = "- Choose A" + chr(0xE0041) + chr(0x202E) + " (README.md:1)\n"
        brief(hidden)
        m.refresh(str(repo), "sess-4", "Stop", ["Bash"])
        check("invisible characters never reach the log", chr(0xE0041) not in log.read_text() and chr(0x202E) not in log.read_text())
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
    finish()


def test_evidence_ask() -> None:
    print("ask once for missing decision evidence")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        home = tmp / "home"
        home.mkdir()
        repo = make_repo(tmp, "proj")
        os.environ["CLAUDE_CONFIG_DIR"] = str(home)
        m = load(HOOK, "groundwork_brief")
        path = m.brief_path(str(repo))
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        path.parent.mkdir(parents=True)
        path.write_text("## Goal\ng\n\n## Decisions\n- Pin the runner to 0.14.0\n\n## Next step\nn\n")
        t = transcript(tmp, ["Bash"])
        stop = {"hook_event_name": "Stop", "cwd": str(repo), "session_id": "e1", "transcript_path": str(t),
                "stop_hook_active": False, "last_assistant_message": "done"}
        r = run(stop, home)
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        check("a decision without evidence: asked once to add a link or file:line",
              out.get("decision") == "block" and "Pin the runner" in out.get("reason", ""), r.stdout)
        check("never asked twice in a session", run(stop, home).stdout.strip() == "")
        check("never when stop_hook_active", run({**stop, "session_id": "e2", "stop_hook_active": True}, home).stdout.strip() == "")
        path.write_text("## Goal\ng\n\n## Decisions\n- Pin the runner to 0.14.0 (https://example.com/issue/1)\n\n## Next step\nn\n")
        check("decision with evidence: no ask", run({**stop, "session_id": "e3"}, home).stdout.strip() == "")
        log = m.log_path(path)
        check("the ask and the evidence fix both reached the log", "no evidence cited" in log.read_text()
              and "https://example.com/issue/1" in log.read_text(), log.read_text())
    finish()


def test_events() -> None:
    print("hook events")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        home = tmp / "home"
        home.mkdir()
        repo = make_repo(tmp, "proj")
        os.environ["CLAUDE_CONFIG_DIR"] = str(home)
        m = load(HOOK, "groundwork_brief")
        path = m.brief_path(str(repo))
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        t = transcript(tmp, ["Bash", "Edit"])

        r = run({"hook_event_name": "PreCompact", "cwd": str(repo), "session_id": "s1", "trigger": "auto"}, home)
        check("PreCompact creates the brief with a snapshot", r.returncode == 0 and path.is_file()
              and "## Snapshot" in path.read_text(), r.stderr)
        check("PreCompact never blocks compaction", r.stdout.strip() == "", r.stdout)
        path.write_text(path.read_text().replace("## Goal\n", "## Goal\nShip feature 3.\n"))
        r = run({"hook_event_name": "SessionStart", "cwd": str(repo), "session_id": "s2", "source": "compact"}, home)
        ctx = context(r)
        check("SessionStart reloads the brief verbatim", "Ship feature 3." in ctx and str(path) in ctx, ctx)
        check("reload is labelled as data and capped", "data" in ctx.lower() and len(ctx) <= 2600, str(len(ctx)))
        git(repo, "checkout", "-q", "-b", "other")
        r = run({"hook_event_name": "SessionStart", "cwd": str(repo), "session_id": "s2", "source": "startup"}, home)
        check("another branch never loads this branch's brief", "Ship feature 3." not in context(r), context(r))
        git(repo, "checkout", "-q", "main")

        big = "## Goal\n" + ("word " * 2000) + "\n## Next step\nfinish\n"
        path.write_text("# Task brief: main\n\n" + big + "\n## Snapshot (hook-written)\n- x\n")
        ctx = context(run({"hook_event_name": "SessionStart", "cwd": str(repo), "session_id": "s3", "source": "resume"}, home))
        check("oversized brief: Next step still shown, output capped", "finish" in ctx and len(ctx) <= 2600, str(len(ctx)))

        path.unlink()
        stop = {"hook_event_name": "Stop", "cwd": str(repo), "session_id": "s4", "transcript_path": str(t),
                "stop_hook_active": False, "last_assistant_message": "done"}
        telemetry(home, "s4", 1)
        r = run(stop, home)
        check("Stop after tool use writes the snapshot", path.is_file(), r.stderr)
        check("short session (<3 tool turns): no ask", r.stdout.strip() == "", r.stdout)
        telemetry(home, "s4", 2)
        r = run(stop, home)
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        check("substantive session with an empty brief: asks once", out.get("decision") == "block"
              and str(path) in out.get("reason", ""), r.stdout)
        r = run(stop, home)
        check("never asks twice in one session", r.stdout.strip() == "", r.stdout)
        telemetry(home, "s5", 3)
        r = run({**stop, "session_id": "s5", "stop_hook_active": True}, home)
        check("never asks when stop_hook_active", r.stdout.strip() == "", r.stdout)
        path.write_text(path.read_text().replace("## Goal\n", "## Goal\nShip it.\n"))
        telemetry(home, "s6", 3)
        r = run({**stop, "session_id": "s6"}, home)
        check("filled brief: no ask", r.stdout.strip() == "", r.stdout)
        check("Stop refresh kept the written Goal", "Ship it." in path.read_text())
        chat = tmp / "chat.jsonl"
        chat.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n")
        before = path.read_text()
        r = run({**stop, "session_id": "s7", "transcript_path": str(chat)}, home)
        check("chat turn: brief untouched, no output", r.stdout.strip() == "" and path.read_text() == before)

        r = run({"hook_event_name": "SessionStart", "cwd": str(tmp), "session_id": "s8", "source": "startup"}, home)
        check("outside a git repo: no output", r.returncode == 0 and r.stdout.strip() == "", r.stdout)
        r = run({"hook_event_name": "PreCompact", "cwd": str(repo), "session_id": "s9"}, home, {"GROUNDWORK_BRIEF": "off"})
        check("kill switch", r.stdout.strip() == "")
        r = run(None, home, raw="nope")
        check("bad stdin: exit 0, no output", r.returncode == 0 and r.stdout.strip() == "")
        blocked = tmp / "blocked"
        blocked.write_text("file, not a dir")
        r = run({"hook_event_name": "PreCompact", "cwd": str(repo), "session_id": "s10"}, blocked)
        check("unwritable config dir: fail open", r.returncode == 0 and r.stdout.strip() == "", r.stderr)
    finish()


if __name__ == "__main__":
    for fn in (test_paths, test_refresh, test_round_trip_and_races, test_decision_log, test_evidence_ask, test_events):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
