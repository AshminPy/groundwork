#!/usr/bin/env python3
"""Deterministic checks for hooks/groundwork_decisions.py (decision records) and its wiring into the task gate and
the branch brief — no Claude Code needed.

Run: python3 tests/test_decision_records.py   (or: python3 -m pytest tests -q)
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "groundwork_decisions.py"
GATE = REPO_ROOT / "hooks" / "groundwork_task_gate.py"
BRIEF = REPO_ROOT / "hooks" / "groundwork_brief.py"
sys.path.insert(0, str(REPO_ROOT / "hooks"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

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
        print(f"  FAIL {name}\n       {str(detail)[:600]}")


def finish() -> None:
    if _FAILURES:
        raise AssertionError("\n".join(_FAILURES))


class Env:
    """A temporary Claude config dir, records folder and git repository on a chosen branch."""

    def __init__(self, branch: str = "main"):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cfg = self.tmp / "cfg"
        self.rec = self.tmp / "records"
        self.repo = self.tmp / "repo"
        self.cfg.mkdir()
        self.repo.mkdir()
        git = ["git", "-C", str(self.repo)]
        subprocess.run(git + ["init", "-q", "-b", branch], check=True)
        subprocess.run(git + ["-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q",
                              "--allow-empty", "-m", "init"], check=True)
        self.transcript = self.tmp / "t.jsonl"
        self.transcript.write_text("")
        self.env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.cfg), "GROUNDWORK_DECISIONS_DIR": str(self.rec),
                    "GROUNDWORK_TELEMETRY": "off"}
        for k in ("GROUNDWORK_DECISIONS", "GROUNDWORK_TASK_GATE"):
            self.env.pop(k, None)

    def close(self):
        self._tmp.cleanup()

    def hook(self, script: Path, payload: dict, extra_env: dict | None = None) -> dict:
        base = {"cwd": str(self.repo), "session_id": "s1", "transcript_path": str(self.transcript)}
        r = subprocess.run([sys.executable, str(script)], input=json.dumps({**base, **payload}), text=True,
                           capture_output=True, env={**self.env, **(extra_env or {})}, timeout=60)
        out = r.stdout.strip()
        try:
            return json.loads(out.splitlines()[-1]) if out else {}
        except ValueError:
            return {"_raw": out, "_err": r.stderr}

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(HOOK), *args], text=True, capture_output=True, env=self.env,
                              cwd=str(self.repo), timeout=60)

    def say(self, text: str, uuid: str, ts: str | None = None) -> str:
        if ts is None:
            import groundwork_decisions as gd
            ts = gd.utc_now()
        with self.transcript.open("a") as f:
            f.write(json.dumps({"type": "user", "uuid": uuid, "timestamp": ts,
                                "message": {"role": "user", "content": text}}) + "\n")
        return ts

    def tool_use(self, name: str, inp: dict) -> None:
        with self.transcript.open("a") as f:
            f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "x", "name": name, "input": inp}]}}) + "\n")

    def record(self) -> Path | None:
        hits = sorted(self.rec.glob("*- decisions.md")) if self.rec.is_dir() else []
        return hits[0] if hits else None


def pre(env: Env, tool: str, ti: dict) -> dict:
    out = env.hook(GATE, {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti})
    return out.get("hookSpecificOutput") or {}


def test_unit() -> None:
    print("format, keys and configuration")
    import groundwork_decisions as gd
    check("branch key: feat/COR-12850-fix", _with_branch("feat/COR-12850-fix") == "COR-12850")
    check("branch key: lower-case unknown key is not a ticket", _with_branch("feat/cor-12850-fix") is None)
    check("branch key: lower-case key with a record counts", _with_branch("feat/cor-12850-fix", record=True) == "COR-12850")
    for b in ("bump-node-18", "release/v2-1", "upgrade-python-3", "feat/k8s-1", "deps/go-1",
              "dependabot/npm_and_yarn/eslint-8.0.0"):
        check(f"branch key: not in {b}", _with_branch(b) is None)
    check("branch key: not in claude/decision-records-6172a6", _with_branch("claude/decision-records-6172a6") is None)
    check("branch key: not in release-1.2", _with_branch("release-1.2") is None)
    check("prompt key: heads the prompt", gd.prompt_key("COR-5: add the replica") == "COR-5")
    check("prompt key: engineering work names a key", gd.prompt_key("please fix the alert for COR-77 today") == "COR-77")
    check("prompt key: a question only mentions a key", gd.prompt_key("what is COR-5 about?") is None)
    check("prompt key: /decision command", gd.prompt_key("/decision COR-9 rejected use X") == "COR-9")
    text = gd.new_record("COR-1", "t", {"task_id": "COR-1", "status": "open", "repos": []})
    meta, _ = gd.parse(text)
    check("frontmatter round-trips", meta.get("task_id") == "COR-1" and meta.get("repos") == [], json.dumps(meta))
    check("all six sections exist", all(gd.section_span(text, n) for n in gd.SECTIONS))
    t2 = gd.append_to_section(text, "Decisions", "- D-1 · x · first")
    t2 = gd.append_to_section(t2, "Decisions", "- D-2 · x · second")
    check("entries append in order inside their section",
          gd.section_text(t2, "Decisions") == "- D-1 · x · first\n- D-2 · x · second", gd.section_text(t2, "Decisions"))
    check("other sections untouched", gd.section_text(t2, "Rejected") == "")
    check("next id", gd.next_id(t2, "D") == "D-3" and gd.next_id(t2, "R") == "R-1")
    check("waiting: DBA team", gd.waiting_phrase("Next: waiting on the DBA team to approve the schema.") is not None)
    check("waiting: reply from someone", gd.waiting_phrase("Paused, awaiting a reply from Priya.") is not None)
    check("waiting: not the owner", gd.waiting_phrase("Waiting for your approval to commit.") is None)
    check("waiting: not a build", gd.waiting_phrase("Waiting for the build to finish.") is None)
    from groundwork_config import validate_config
    check("config: valid decision_records", validate_config(
        {"decision_records": {"work_dir": "~/w", "personal_dir": "~/p", "work_roots": ["~/x"]}}) == [])
    probs = validate_config({"decision_records": {"work_dir": "", "work_roots": "x", "other": 1}})
    check("config: bad decision_records reported", len(probs) == 3, json.dumps(probs))
    finish()


def _with_branch(branch: str, record: bool = False):
    import groundwork_decisions as gd
    env = Env(branch)
    old = {k: os.environ.get(k) for k in ("CLAUDE_CONFIG_DIR", "GROUNDWORK_DECISIONS_DIR")}
    try:
        os.environ.update({"CLAUDE_CONFIG_DIR": str(env.cfg), "GROUNDWORK_DECISIONS_DIR": str(env.rec)})
        if record:
            env.cli("create", "COR-12850", "--title", "x")
        return gd.branch_key(str(env.repo))
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        env.close()


def test_folders() -> None:
    print("folder selection from config")
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "cfg"
        (cfg / "groundwork").mkdir(parents=True)
        work, personal, root = Path(tmp) / "w", Path(tmp) / "p", Path(tmp) / "company"
        root.mkdir()
        (cfg / "groundwork" / "config.json").write_text(json.dumps({"decision_records": {
            "work_dir": str(work), "personal_dir": str(personal), "work_roots": [str(root)]}}))
        code = ("import sys,json; sys.path.insert(0, sys.argv[1]); import groundwork_decisions as gd; "
                "print(json.dumps([str(gd.folder_for(sys.argv[2])), str(gd.folder_for(sys.argv[3]))]))")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfg)}
        env.pop("GROUNDWORK_DECISIONS_DIR", None)
        r = subprocess.run([sys.executable, "-c", code, str(REPO_ROOT / "hooks"), str(root / "repo"), tmp],
                           text=True, capture_output=True, env=env)
        got = json.loads(r.stdout or "[]")
        check("cwd under a work root -> work folder, else personal",
              got == [str(work), str(personal)], r.stdout + r.stderr)
    finish()


def test_cli_and_approval() -> None:
    print("CLI and the owner's approval of entries")
    env = Env("feat/COR-12850-replication")
    try:
        r = env.cli("create", "COR-12850", "--title", "Replication / setup")
        path = env.record()
        check("create writes one record named <KEY> - <title> - decisions.md",
              r.returncode == 0 and path is not None and path.name.startswith("COR-12850 - ")
              and path.name.endswith(" - decisions.md") and "/" not in path.name[:-3], r.stdout + r.stderr)
        check("record is owner-only", path is not None and (path.stat().st_mode & 0o777) == 0o600)
        again = env.cli("create", "COR-12850", "--title", "other")
        check("create is idempotent", again.returncode == 0 and "exists" in again.stdout and len(list(env.rec.iterdir())) == 1)
        env.cli("add", "COR-12850", "rejected", "Debezium — no licence, https://example.com/a")
        env.cli("add", "COR-12850", "decision", "GoldenGate")
        r = env.cli("add", "COR-12850", "decision", "GoldenGate classic", "--supersedes", "D-1")
        text = path.read_text()
        check("add numbers entries and supersedes without editing", "- R-1 · " in text and "- D-1 · " in text
              and "- D-2 · " in text and "(supersedes D-1)" in text and text.count("GoldenGate") == 2, text)
        token = "ghp_" + "Z9y8X7w6V5u4T3s2R1q0P9o8N7m6L5k4J3i2"
        env.cli("state", "COR-12850", f"owner pasted {token} for the API")
        env.cli("add", "COR-12850", "rule", f"use {token} only in staging")
        env.cli("waiting", "COR-12850", f"ops — rotate {token}")
        text = path.read_text()
        check("CLI text (state, add, waiting) is redacted before it is written", token not in text and "[redacted" in text, text)
        env.cli("waiting", "COR-12850", "--clear")
        bad = env.cli("add", "COR-12850", "decision", "x", "--supersedes", "D-9")
        check("supersedes must name an existing entry", bad.returncode != 0)
        show = env.cli("show", "COR-12850").stdout
        check("show marks superseded decisions and lists Rejected first",
              "D-1" in show and "[superseded]" in show and show.index("Rejected") < show.index("Decisions"), show)

        add_cmd = f'python3 {HOOK} add COR-12850 decision "x"'
        out = pre(env, "Bash", {"command": add_cmd})
        check("PreToolUse: `add` asks the owner", out.get("permissionDecision") == "ask", json.dumps(out))
        out = pre(env, "Bash", {"command": f'groundwork decision add COR-12850 rule "y"'})
        check("PreToolUse: `groundwork decision add` asks the owner", out.get("permissionDecision") == "ask", json.dumps(out))
        for sub in ("create COR-1 --title t", 'state COR-12850 "s"', "show COR-12850"):
            out = pre(env, "Bash", {"command": f"python3 {HOOK} {sub}"})
            check(f"PreToolUse: `{sub.split()[0]}` does not ask", out.get("permissionDecision") is None, json.dumps(out))
        out = pre(env, "Edit", {"file_path": str(path), "old_string": "## Standing rules\n",
                                "new_string": "## Standing rules\n\n- S-1 · x · never use port 22\n"})
        check("PreToolUse: Edit appending to a record asks the owner", out.get("permissionDecision") == "ask", json.dumps(out))
        d1 = next(ln for ln in path.read_text().splitlines() if ln.startswith("- D-1 "))
        out = pre(env, "Edit", {"file_path": str(path), "old_string": d1, "new_string": d1 + " (edited)"})
        check("PreToolUse: Edit changing an existing entry is denied (append-only)",
              out.get("permissionDecision") == "deny" and "append-only" in out.get("permissionDecisionReason", ""),
              json.dumps(out))
        out = pre(env, "Write", {"file_path": str(path), "content": "---\n---\n"})
        check("PreToolUse: Write dropping entries is denied", out.get("permissionDecision") == "deny", json.dumps(out))
        out = pre(env, "Bash", {"command": f"echo hi >> '{path}'"})
        check("PreToolUse: shell redirect into a record asks", out.get("permissionDecision") == "ask", json.dumps(out))
        out = pre(env, "Bash", {"command": f'python3 {HOOK} add COR-12850 decision "x" && gh pr create --title a --body b'})
        check("PreToolUse: a record ask never hides the task gate's PR-review deny",
              out.get("permissionDecision") == "deny" and "review" in out.get("permissionDecisionReason", ""), json.dumps(out))
        out = pre(env, "Bash", {"command": f"cat '{path}'"})
        check("PreToolUse: reading a record is untouched", out.get("permissionDecision") is None, json.dumps(out))

        before = json.loads(json.dumps(__import__("groundwork_decisions").parse(path.read_text())[0]))
        time.sleep(0.01)
        env.hook(GATE, {"hook_event_name": "PostToolUse", "tool_name": "Edit",
                        "tool_input": {"file_path": str(path), "old_string": "a", "new_string": "b"}})
        after = __import__("groundwork_decisions").parse(path.read_text())[0]
        check("PostToolUse: an approved Edit stamps last_updated", after.get("last_updated") != before.get("last_updated"),
              f"{before.get('last_updated')} -> {after.get('last_updated')}")
    finally:
        env.close()
    finish()


def test_task_note_link() -> None:
    print("task note link")
    env = Env()
    try:
        note = env.tmp / "P-001 - Thing.md"
        note.write_text("# P-001\n")
        env.cli("create", "GW-7", "--title", "thing", "--task-note", str(note))
        rec = env.record()
        meta = __import__("groundwork_decisions").parse(rec.read_text())[0]
        check("record links to the task note", meta.get("task_note") == "[[P-001 - Thing]]", json.dumps(meta))
        check("task note links to the record", f"[[{rec.stem}]]" in note.read_text(), note.read_text())
    finally:
        env.close()
    finish()


def test_stop_gates() -> None:
    print("Stop: record required, waiting needs Waiting on")
    env = Env("feat/COR-12850-x")
    try:
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "done"})
        check("no record -> block with the create command", out.get("decision") == "block" and "create COR-12850" in
              out.get("reason", ""), json.dumps(out))
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": True, "last_assistant_message": "done"})
        check("stop_hook_active -> never block again", out == {}, json.dumps(out))
        env.cli("create", "COR-12850", "--title", "x")
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "done"})
        check("record exists -> no block", out == {}, json.dumps(out))
        msg = "Status: blocked. Waiting on the DBA team to approve the schema change."
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": msg})
        check("waiting on someone with empty Waiting on -> block", out.get("decision") == "block"
              and "waiting COR-12850" in out.get("reason", ""), json.dumps(out))
        env.cli("waiting", "COR-12850", "DBA team — schema approval")
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": msg})
        check("Waiting on filled -> no block", out == {}, json.dumps(out))
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False,
                              "last_assistant_message": "Waiting for your go-ahead to commit."}, )
        check("waiting on the owner -> no block", out == {}, json.dumps(out))
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": msg},
                       {"GROUNDWORK_DECISIONS": "off"})
        check("kill switch", out == {}, json.dumps(out))
    finally:
        env.close()
    env = Env()
    try:
        env.say("what is COR-5 about?", "q1")
        env.hook(HOOK, {"hook_event_name": "UserPromptSubmit", "prompt": "what is COR-5 about?"})
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "x"})
        check("question that only mentions a key -> no gate", out == {}, json.dumps(out))
        out = env.hook(HOOK, {"hook_event_name": "UserPromptSubmit", "prompt": "COR-6: fix the replica lag alert"})
        ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext", "")
        check("prompt naming a key as work activates it (no record yet)", "COR-6 has no decision record" in ctx, json.dumps(out))
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "x"})
        check("prompt key -> record required at Stop", out.get("decision") == "block", json.dumps(out))
    finally:
        env.close()
    finish()


def test_load_and_capture() -> None:
    print("SessionStart load, PreCompact and Stop capture")
    env = Env("feat/COR-12850-x")
    try:
        env.say("COR-12850: set up replication, never use Debezium", "u1")
        env.say("<task-notification>background done</task-notification>", "u2")
        token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
        env.say(f"the token is {token} use it", "u3")
        with env.transcript.open("a") as f:
            f.write(json.dumps({"type": "user", "uuid": "u4", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "x", "content": "not the owner"}]}}) + "\n")
        env.hook(HOOK, {"hook_event_name": "PreCompact", "trigger": "auto"})
        rec = env.record()
        text = rec.read_text() if rec else ""
        owner = text.split("## Owner messages", 1)[-1]
        check("PreCompact creates the record when missing", rec is not None and rec.name.startswith("COR-12850 - "))
        check("owner prompt captured verbatim as a quote", "> COR-12850: set up replication, never use Debezium" in owner, owner)
        check("system envelopes and tool results are not captured",
              "background done" not in owner and "not the owner" not in owner, owner)
        check("secret-shaped text is redacted", token not in text and "[redacted" in owner, owner)
        env.hook(HOOK, {"hook_event_name": "PreCompact", "trigger": "auto"})
        check("capture is deduplicated", rec.read_text().count("never use Debezium") == 1)
        env.say("also keep the old cluster", "u5")
        env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": True, "last_assistant_message": "ok"})
        check("Stop captures the latest owner prompt", "> also keep the old cluster" in rec.read_text())
        env.cli("add", "COR-12850", "rejected", "Debezium — owner said no, see message u1")
        for source in ("startup", "resume", "compact", "clear"):
            out = env.hook(HOOK, {"hook_event_name": "SessionStart", "source": source})
            ctx = (out.get("hookSpecificOutput") or {}).get("additionalContext", "")
            check(f"SessionStart ({source}) loads Rejected as data", "Do not re-propose" in ctx and "R-1" in ctx
                  and "Debezium" in ctx, ctx[:300])
    finally:
        env.close()
    env = Env()
    try:
        env.say("COR-1: unrelated earlier task message", "e1", "2026-01-01T00:00:00.000Z")
        env.hook(HOOK, {"hook_event_name": "UserPromptSubmit", "prompt": "COR-2: new task"})
        env.say("COR-2: new task", "e2")
        env.hook(HOOK, {"hook_event_name": "PreCompact"})
        rec = env.record()
        owner = rec.read_text().split("## Owner messages", 1)[-1] if rec else ""
        check("a prompt-activated key captures only messages from its activation on",
              "COR-2: new task" in owner and "unrelated earlier" not in owner, owner)
    finally:
        env.close()
    env = Env()
    try:
        env.hook(HOOK, {"hook_event_name": "UserPromptSubmit", "prompt": "COR-8: rotate the key"})
        env.cli("create", "COR-8", "--title", "rotate")
        out = env.hook(HOOK, {"hook_event_name": "SessionStart", "source": "compact"})
        check("post-compaction load uses the session's prompt key",
              "COR-8" in (out.get("hookSpecificOutput") or {}).get("additionalContext", ""), json.dumps(out))
    finally:
        env.close()
    finish()


def test_outward_gate() -> None:
    print("PreToolUse: push, PR, Jira, email and chat need a fresh record")
    env = Env("feat/COR-12850-x")
    try:
        push = {"command": "git push origin feat/COR-12850-x"}
        out = pre(env, "Bash", push)
        check("no record -> push denied", out.get("permissionDecision") == "deny" and "no decision record" in
              out.get("permissionDecisionReason", ""), json.dumps(out))
        env.cli("create", "COR-12850", "--title", "x")
        env.cli("add", "COR-12850", "rejected", "Debezium — no licence")
        time.sleep(0.05)
        env.say("COR-12850: actually also use the DR region", "o1")
        out = pre(env, "Bash", push)
        reason = out.get("permissionDecisionReason", "")
        check("owner wrote after last_updated -> push denied, Rejected shown",
              out.get("permissionDecision") == "deny" and "Debezium" in reason and "state COR-12850" in reason, json.dumps(out))
        env.hook(HOOK, {"hook_event_name": "PreCompact"})
        out = pre(env, "Bash", push)
        check("the hook's own capture does not unlock the gate", out.get("permissionDecision") == "deny", json.dumps(out))
        for cmd in ("gh pr create --title t --body b", "gh pr merge 3", "gh pr comment 3 -b x", "jira issue move COR-1 Done",
                    "git -C . push"):
            out = pre(env, "Bash", {"command": cmd})
            check(f"stale -> `{cmd}` denied", out.get("permissionDecision") == "deny", json.dumps(out))
        for tool, ti in (("mcp__claude_ai_Atlassian__addCommentToJiraIssue", {"issueIdOrKey": "COR-1"}),
                         ("mcp__plugin_productivity_slack__slack_send_message", {"text": "hi"}),
                         ("mcp__99e35de1-89c9-4b50-8a2c-83c832f6a348__send_message", {"to": "a"})):
            out = pre(env, tool, ti)
            check(f"stale -> {tool.split('__')[-1]} denied", out.get("permissionDecision") == "deny", json.dumps(out))
        for tool, ti in (("mcp__99e35de1-89c9-4b50-8a2c-83c832f6a348__create_draft", {"to": "a"}),
                         ("mcp__claude_ai_Atlassian__getJiraIssue", {"issueIdOrKey": "COR-1"})):
            out = pre(env, tool, ti)
            check(f"stale -> {tool.split('__')[-1]} (no send/change) allowed", out.get("permissionDecision") is None, json.dumps(out))
        click = {"action": "left_click", "coordinate": [1, 1], "action_summary": "Opens the transition menu"}
        out = pre(env, "mcp__Claude_Browser__computer", click)
        check("browser click elsewhere -> allowed", out.get("permissionDecision") is None, json.dumps(out))
        env.tool_use("mcp__Claude_Browser__navigate", {"url": "https://example.atlassian.net/browse/COR-12850"})
        out = pre(env, "mcp__Claude_Browser__computer", click)
        check("browser click on Jira -> denied", out.get("permissionDecision") == "deny", json.dumps(out))
        out = pre(env, "mcp__Claude_Browser__computer", {"action": "screenshot"})
        check("browser screenshot on Jira -> allowed", out.get("permissionDecision") is None, json.dumps(out))
        out = pre(env, "Bash", {"command": "git status"})
        check("non-outward command -> allowed", out.get("permissionDecision") is None, json.dumps(out))
        out = pre(env, "Bash", {"command": f'python3 {HOOK} add COR-12850 decision "x" && git push origin feat/COR-12850-x'})
        check("stale -> `decision add && git push` denied, not just asked", out.get("permissionDecision") == "deny", json.dumps(out))
        r = env.cli("state", "COR-12850", "Owner added the DR region; plan updated")
        out = pre(env, "Bash", push)
        check("record updated after the owner's message -> push not blocked by this gate",
              r.returncode == 0 and out.get("permissionDecision") != "deny", json.dumps(out))
        env.say("ok push it", "o2", time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() + 2)))
        check("a newer owner message makes it stale again", pre(env, "Bash", push).get("permissionDecision") == "deny")
        out = env.hook(GATE, {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": push},
                       {"GROUNDWORK_DECISIONS": "off"})
        check("kill switch", (out.get("hookSpecificOutput") or {}).get("permissionDecision") != "deny", json.dumps(out))

        env.hook(GATE, {"hook_event_name": "PostToolUse", "tool_name": "mcp__claude_ai_Atlassian__transitionJiraIssue",
                        "tool_input": {"issueIdOrKey": "COR-12850", "transition": "Good for review"}})
        meta = __import__("groundwork_decisions").parse(env.record().read_text())[0]
        check("Good for review closes the record", meta.get("status") == "closed", json.dumps(meta))
        check("closed record -> no outward gate", pre(env, "Bash", push).get("permissionDecision") != "deny")
        out = env.hook(HOOK, {"hook_event_name": "Stop", "stop_hook_active": False,
                              "last_assistant_message": "Waiting on the DBA team to approve."})
        check("closed record -> no Stop gate", out == {}, json.dumps(out))
    finally:
        env.close()
    env = Env()
    try:
        out = pre(env, "Bash", {"command": "git push origin main"})
        check("no task key -> no gate", out.get("permissionDecision") != "deny", json.dumps(out))
    finally:
        env.close()
    finish()


def test_brief_link() -> None:
    print("branch brief links to the record")
    env = Env("feat/COR-12850-x")
    try:
        env.cli("create", "COR-12850", "--title", "x")
        env.tool_use("Edit", {"file_path": "/tmp/x", "old_string": "a", "new_string": "b"})
        env.hook(BRIEF, {"hook_event_name": "PreCompact"})
        briefs = list((env.cfg / "groundwork" / "briefs").rglob("*.md"))
        text = briefs[0].read_text() if briefs else ""
        check("snapshot lists the decision record", f"decision record: {env.record()}" in text, text)
    finally:
        env.close()
    finish()


def test_cli_dispatch() -> None:
    print("groundwork decision dispatch")
    import groundwork_cli
    groundwork_cli.INSTALLED_DECISIONS_PY = HOOK
    env = Env()
    try:
        old = dict(os.environ)
        os.environ.update(env.env)
        try:
            rc = groundwork_cli.main(["decision", "list"])
        finally:
            os.environ.clear()
            os.environ.update(old)
        check("`groundwork decision list` reaches the module", rc == 0)
    finally:
        env.close()
    finish()


if __name__ == "__main__":
    for fn in (test_unit, test_folders, test_cli_and_approval, test_task_note_link, test_stop_gates,
               test_load_and_capture, test_outward_gate, test_brief_link, test_cli_dispatch):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
