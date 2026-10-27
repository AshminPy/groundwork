#!/usr/bin/env python3
"""Deterministic checks for hooks/groundwork_reply_check.py — no Claude Code needed.

Run: python3 tests/test_reply_check.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "groundwork_reply_check.py"

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
    sys.path.insert(0, str(HOOK.parent))
    spec = importlib.util.spec_from_file_location("groundwork_reply_check", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(payload, env_extra=None, raw=None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("GROUNDWORK_REPLY_CHECK", None)
    env.update(env_extra or {})
    return subprocess.run(["python3", str(HOOK)], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, timeout=30, env=env)


def transcript(tmp: Path, tool_names, name="t.jsonl") -> Path:
    lines = [{"type": "user", "message": {"role": "user", "content": "do the thing"}}]
    for tool in tool_names:
        lines.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": tool, "input": {}}]}})
        lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}})
    p = tmp / name
    p.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return p


META = "```\nHARNESS METADATA\nGroundwork 2.4.0 · IMPLEMENT\nExecution:   single agent\nEvidence:    repo / tests\nValidation:  verified\n```"
TECH = "**Technical details**\n- Command: `python3 -m pytest tests -q` → 12 passed\n\n"
EVID = "**Evidence & references**\n- `hooks/parser.py:42` — the new empty-input branch\n\n"
FULL = "Complete. The parser now accepts empty input.\n\n" + TECH + EVID + META


def test_check_reply() -> None:
    m = load_module()
    print("check_reply")
    check("no tools: never asks, even for an empty reply", m.check_reply("", []) == [])
    check("bookkeeping-only tools count as no tools",
          m.check_reply("ok", ["ToolSearch", "TodoWrite", "mcp__ccd_turn__update_plan", "mcp__ccd_turn__wrap_up"]) == [])
    got = m.check_reply(FULL, ["Bash"])
    check("complete reply after Bash: nothing missing", got == [], str(got))
    got = m.check_reply(FULL.replace(META, ""), ["Bash"])
    check("missing metadata is reported", got == ["metadata"], str(got))
    bold_meta = FULL.replace(META, "**Harness metadata**\nGroundwork 2.4.0 · IMPLEMENT\nValidation: verified")
    check("bold 'Harness metadata' heading counts", "metadata" not in m.check_reply(bold_meta, ["Bash"]))
    no_tech = FULL.replace(TECH, "")
    check("Technical details required when Bash ran", m.check_reply(no_tech, ["Bash"]) == ["technical_details"])
    check("Technical details not required for a read-only turn", m.check_reply(no_tech, ["Read", "Grep"]) == [])
    mention = no_tech.replace("Complete.", "Complete. See the Technical details below.")
    check("an inline mention is not a Technical details section", m.check_reply(mention, ["Bash"]) == ["technical_details"])
    no_ref = FULL.replace("- `hooks/parser.py:42` — the new empty-input branch", "- the parser was checked")
    check("reply with no reference anywhere is reported", m.check_reply(no_ref, ["Bash"]) == ["evidence"])
    check("no Evidence section and no reference is reported", m.check_reply(FULL.replace(EVID, ""), ["Bash"]) == ["evidence"])
    inline = FULL.replace(EVID, "").replace("Complete.", "Complete. The fix is at `hooks/parser.py:42`.")
    check("inline file:line without an Evidence & references section is reported (owner: links in every reply)",
          m.check_reply(inline, ["Bash"]) == ["evidence"], str(m.check_reply(inline, ["Bash"])))
    empty_section = FULL.replace("- `hooks/parser.py:42` — the new empty-input branch", "- see above")
    check("an Evidence section with no link or file:line inside it is reported",
          m.check_reply(empty_section + "\nAlso `hooks/parser.py:42`.", ["Bash"]) == ["evidence"])
    in_meta = FULL.replace(EVID, "").replace("Validation:  verified", "Validation:  verified https://example.com/x")
    check("a link inside the metadata block does not count as the Evidence section", "evidence" in m.check_reply(in_meta, ["Bash"]))
    read_only = FULL.replace(TECH, "").replace(EVID, "")
    check("read-only tool turns need the Evidence section too", m.check_reply(read_only, ["Read"]) == ["evidence"])
    for heading in ("## Evidence & references", "Evidence and references", "**Evidence**", "### Evidence & References"):
        variant = FULL.replace("**Evidence & references**", heading)
        check(f"evidence heading variant accepted: {heading}", m.check_reply(variant, ["Bash"]) == [])
    for ref in ("https://code.claude.com/docs/en/hooks", "[hooks docs](https://code.claude.com/docs/en/hooks)",
                "`scripts/merge_settings.py:120-140`", "tests/test_x.py:7"):
        variant = FULL.replace("`hooks/parser.py:42`", ref)
        check(f"evidence reference form accepted: {ref}", m.check_reply(variant, ["Bash"]) == [])
    tech_first = TECH + EVID + META
    check("reply opening with Technical details misses the explanation", "explanation" in m.check_reply(tech_first, ["Bash"]))
    import time as _t
    t0 = _t.monotonic()
    m.check_reply("Done. " + "a" * 20000 + "\n" + META, ["Bash"])
    check("a 20,000-character token is checked in well under a second", _t.monotonic() - t0 < 1.0, f"{_t.monotonic() - t0:.2f}s")
    saved = m.META_HEADING
    m.META_HEADING = None
    check("telemetry module unavailable: metadata check cannot pass silently but never crashes",
          isinstance(m.check_reply(FULL, ["Bash"]), list))
    m.META_HEADING = saved
    got = m.check_reply(META, ["Bash"])
    check("metadata-only reply misses explanation, technical details and evidence",
          got == ["explanation", "technical_details", "evidence"], str(got))
    finish()


def test_classify_prompt() -> None:
    m = load_module()
    print("classify_prompt")
    check("single strong signal routes", m.classify_prompt("debug this crash in the parser") == "TROUBLESHOOT")
    check("explain question routes", m.classify_prompt("explain how the snapshot hook works") == "EXPLAIN")
    check("two categories -> no route (low confidence adds nothing)",
          m.classify_prompt("review the design and deploy it") is None)
    check("no signal -> no route", m.classify_prompt("ok") is None)
    check("slash command -> no route", m.classify_prompt("/compact") is None)
    finish()


def playbook_home(tmp: Path) -> Path:
    pb = tmp / "groundwork" / "playbooks"
    pb.mkdir(parents=True)
    (pb / "troubleshoot.md").write_text("# T\n\n## Output Format\nHeadings: Status · Root cause · Fix.\n\n## Other\nignored\n")
    return tmp


def context_of(r: subprocess.CompletedProcess) -> str:
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    return (out.get("hookSpecificOutput") or {}).get("additionalContext", "")


def test_prompt_hook() -> None:
    print("UserPromptSubmit")
    with tempfile.TemporaryDirectory() as d:
        env = {"CLAUDE_CONFIG_DIR": str(playbook_home(Path(d)))}
        r = run({"hook_event_name": "UserPromptSubmit", "prompt": "debug this crash in the parser"}, env)
        ctx = context_of(r)
        check("prompt hook exits 0", r.returncode == 0, r.stderr)
        check("reminder added", "HARNESS METADATA" in ctx and "Evidence & references" in ctx, ctx)
        check("confident route adds that playbook's Output Format", "Root cause" in ctx and "ignored" not in ctx, ctx)
        check("context stays small", len(ctx) < 2000, str(len(ctx)))
        ctx = context_of(run({"hook_event_name": "UserPromptSubmit", "prompt": "review the design and deploy it"}, env))
        check("low-confidence route: reminder only", "Output Format" not in ctx and "HARNESS METADATA" in ctx, ctx)
        r = run({"hook_event_name": "UserPromptSubmit", "prompt": "/compact"}, env)
        check("slash command: no output", r.returncode == 0 and r.stdout.strip() == "", r.stdout)
        r = run({"hook_event_name": "UserPromptSubmit", "prompt": "explain how hooks work"}, env)
        check("missing playbook file: reminder only, no crash", r.returncode == 0 and "HARNESS METADATA" in context_of(r), r.stderr)
    finish()


def test_stop_hook() -> None:
    print("Stop")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        base = {"hook_event_name": "Stop", "transcript_path": str(transcript(tmp, ["Bash"])), "stop_hook_active": False}
        r = run({**base, "last_assistant_message": "Done."})
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        check("tool turn missing parts is asked once (block)", out.get("decision") == "block", r.stdout)
        check("reason names the missing parts",
              all(w in out.get("reason", "") for w in ("HARNESS METADATA", "Evidence")), out.get("reason", ""))
        r = run({**base, "last_assistant_message": FULL})
        check("complete reply: no output", r.returncode == 0 and r.stdout.strip() == "", r.stdout)
        r = run({**base, "stop_hook_active": True, "last_assistant_message": "Done."})
        check("never asks again when stop_hook_active", r.returncode == 0 and r.stdout.strip() == "", r.stdout)
        chat = transcript(tmp, [], name="chat.jsonl")
        r = run({**base, "transcript_path": str(chat), "last_assistant_message": "Sure, here is the answer."})
        check("chat turn (no tools) untouched", r.stdout.strip() == "", r.stdout)
        r = run({**base, "transcript_path": str(tmp / "missing.jsonl"), "last_assistant_message": "Done."})
        check("unreadable transcript: fail open", r.returncode == 0 and r.stdout.strip() == "", r.stdout)
        r = run({**base, "last_assistant_message": "Done."}, {"GROUNDWORK_REPLY_CHECK": "off"})
        check("kill switch disables the check", r.stdout.strip() == "", r.stdout)
        r = run({**base, "hook_event_name": "SubagentStop", "last_assistant_message": "Done."})
        check("SubagentStop ignored", r.stdout.strip() == "", r.stdout)
        r = run(None, raw="not json")
        check("bad stdin: exit 0, no output", r.returncode == 0 and r.stdout.strip() == "", r.stderr)
        r = run({k: v for k, v in base.items()})
        check("missing last_assistant_message: fail open (no request)", r.returncode == 0 and r.stdout.strip() == "", r.stdout)
        r = run({**base, "stop_hook_active": True, "last_assistant_message": FULL})
        check("complete reply with stop_hook_active: no output", r.stdout.strip() == "", r.stdout)
        r = run({"hook_event_name": "UserPromptSubmit", "prompt": "debug this crash"}, {"GROUNDWORK_REPLY_CHECK": "off"})
        check("kill switch disables the prompt reminder too", r.stdout.strip() == "", r.stdout)
    finish()


def test_stop_without_transcript() -> None:
    """Sessions that are not saved (claude -p --no-session-persistence, some CI and SDK runs) have no transcript.
    The turn's tool use then comes from Groundwork's per-tool-call telemetry since the prompt was submitted."""
    print("Stop without a transcript")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        events = tmp / "tool_events.jsonl"
        env = {"CLAUDE_CONFIG_DIR": str(tmp / "cfg"), "GROUNDWORK_TOOL_TELEMETRY_PATH": str(events)}
        def tool(sid, ts):
            with events.open("a") as f:
                f.write(json.dumps({"schema": 1, "ts": ts, "session_id": sid, "tool": "Read", "category": "builtin",
                                    "success": True}) + "\n")
        import time as _t
        now = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
        missing = str(tmp / "never-written.jsonl")
        stop = {"hook_event_name": "Stop", "session_id": "s1", "transcript_path": missing, "stop_hook_active": False,
                "last_assistant_message": "Done."}
        r = run(stop, env)
        check("no prompt marker yet: fail open (no output)", r.returncode == 0 and r.stdout.strip() == "", r.stdout)
        run({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "read the config"}, env)
        tool("s1", "2000-01-01T00:00:00Z")   # an older turn's tool call
        tool("other", now)                   # another session's tool call
        r = run(stop, env)
        check("no tool call by this session since the prompt: chat turn, untouched", r.stdout.strip() == "", r.stdout)
        tool("s1", now)
        r = run(stop, env)
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        check("a tool call since the prompt, missing parts: asked once", out.get("decision") == "block", r.stdout)
        r = run({**stop, "last_assistant_message": FULL}, env)
        check("complete reply: no output", r.stdout.strip() == "", r.stdout)
        r = run({**stop, "stop_hook_active": True}, env)
        check("never asks twice (stop_hook_active)", r.stdout.strip() == "", r.stdout)
        run({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "/compact"}, env)
        check("a slash command still marks the turn start", (tmp / "cfg").exists())
    finish()


if __name__ == "__main__":
    for fn in (test_check_reply, test_classify_prompt, test_prompt_hook, test_stop_hook, test_stop_without_transcript):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
