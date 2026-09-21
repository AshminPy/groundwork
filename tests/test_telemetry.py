#!/usr/bin/env python3
"""Deterministic checks for hooks/groundwork_telemetry.py — no Claude Code needed.

Run: python3 tests/test_telemetry.py   (or: python3 -m pytest tests -q)
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
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


def run(payload, env_extra=None, raw=None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(["python3", str(HOOK)], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, timeout=30, env=env)


def transcript(tmp: Path, turns) -> Path:
    """turns: list of lists of tool_use dicts; a human prompt precedes each turn."""
    lines = []
    for turn in turns:
        lines.append({"type": "user", "message": {"role": "user", "content": "do the thing"}, "promptSource": "sdk"})
        for tu in turn:
            lines.append({"type": "assistant", "message": {"content": [{"type": "tool_use", **tu}]}})
            lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}})
    p = tmp / "t.jsonl"
    p.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return p


RESPONSE = """Status

Complete. The change is implemented and installed.

What matters
* [x] All checks passed.

Technical details
* Tests: 12 passed
```
STATUS
Overall: COMPLETE
```

Harness metadata
* Harness: Groundwork
* Profile: Work
* Playbook: IMPLEMENT
* Execution: Subagents
* Agents: 2 — explorer, reviewer
* Evidence: Repo + tests + runtime
* Validation: Verified
"""


def test_telemetry_hook() -> None:
    print("groundwork_telemetry.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfg = tmp / "claude"
        (cfg / "groundwork").mkdir(parents=True)
        (cfg / "groundwork" / "VERSION").write_text("1.3.0\n")
        env = {"CLAUDE_CONFIG_DIR": str(cfg)}
        events = cfg / "groundwork" / "telemetry" / "events.jsonl"

        # turn 1 (old): a deploy; turn 2 (current): edits, a test run, an MCP call, two agents, a secret in a command
        t = transcript(tmp, [
            [{"name": "Bash", "input": {"command": "terraform apply -auto-approve"}}],
            [{"name": "Read", "input": {"file_path": "/repo/a.py"}},
             {"name": "Edit", "input": {"file_path": "/repo/a.py"}},
             {"name": "Write", "input": {"file_path": "/repo/b.py"}},
             {"name": "Edit", "input": {"file_path": "/repo/a.py"}},
             {"name": "Bash", "input": {"command": "TOKEN=sk-live-SECRET123 pytest -q"}},
             {"name": "mcp__github__list_prs", "input": {"repo": "x"}},
             {"name": "Agent", "input": {"subagent_type": "Explore", "prompt": "map"}},
             {"name": "Agent", "input": {"name": "security-reviewer", "prompt": "review"}}],
        ])
        payload = {"session_id": "sess-1", "prompt_id": "p-9", "cwd": str(tmp), "transcript_path": str(t),
                   "last_assistant_message": RESPONSE, "hook_event_name": "Stop"}
        r = run(payload, env)
        check("exit 0 and silent", r.returncode == 0 and r.stdout.strip() == "" and r.stderr.strip() == "", r.stdout + r.stderr)
        check("one record appended", events.is_file() and len(events.read_text().splitlines()) == 1)
        rec = json.loads(events.read_text().splitlines()[0])
        check("identifiers and version", rec["session_id"] == "sess-1" and rec["prompt_id"] == "p-9" and rec["harness_version"] == "1.3.0" and rec["harness"] == "Groundwork")
        check("metadata block parsed", rec["playbook"] == "IMPLEMENT" and rec["execution_mode"] == "subagents" and rec["profile"] == "work" and rec["validation"] == "verified", json.dumps(rec))
        check("agents from block", rec["agent_count"] == 2 and rec["agent_roles"] == ["explorer", "reviewer"], json.dumps(rec["agent_roles"]))
        check("evidence sources split", rec["evidence_sources"] == ["repo", "tests", "runtime"], json.dumps(rec["evidence_sources"]))
        check("outcome from Overall", rec["outcome"] == "complete")
        check("current turn only: deploy from the previous turn not counted", rec["deployment_performed"] is False and rec["tests_run"] is True)
        check("tools, mcp servers, distinct files", rec["tools"] == ["Read", "Edit", "Write", "Bash", "mcp__github__list_prs", "Agent"] and rec["mcp_servers"] == ["github"] and rec["files_changed"] == 2, json.dumps(rec))
        check("implementation flag", rec["implementation_performed"] is True)
        check("no clarification question", rec["clarification_required"] is False)
        raw = events.read_text()
        check("no secrets, commands, paths or prompt text stored", all(s not in raw for s in ("SECRET123", "terraform apply", "/repo/a.py", "do the thing", "map")), raw)
        check("cwd stored only as a short hash", len(rec["cwd_hash"]) == 12 and str(tmp) not in raw)

        # review finding 1: free text in the block must not leak paths / tokens / sentences
        leaky = RESPONSE.replace("* Evidence: Repo + tests + runtime",
                                 "* Evidence: /Users/me/secret-client/src/auth.py + AKIAABCDEXAMPLE123 + repo (static read) + tests, not executed") \
                        .replace("* Profile: Work", "* **Profile:** user@example.com") \
                        .replace("* Playbook: IMPLEMENT", "* **Playbook:** IMPLEMENT") \
                        .replace("* Agents: 2 — explorer, reviewer", "* Agents: 2 — explorer, /tmp/x, reviewer with a very long role description that is not a label")
        run({**payload, "last_assistant_message": leaky + "* Environment: prod\n"}, env)
        raw = events.read_text(); rec3 = json.loads(raw.splitlines()[-1])
        check("path / token / sentence tokens dropped from evidence", rec3["evidence_sources"] == ["repo", "tests", "not executed"], json.dumps(rec3["evidence_sources"]))
        check("secret-shaped values in every free-text line are dropped", all(x not in raw for x in ("ghp_", "sk-live", "supersecret")) and run({**payload, "last_assistant_message": RESPONSE.replace("* Profile: Work", "* Profile: prod-db_password=supersecrethunter2-ghp_abcdefgh").replace("* Agents: 2 — explorer, reviewer", "* Agents: 1 — reviewer-with-token-sk-live-51h8abcdefghijklmnop").replace("* Environment: x", "")}, env).returncode == 0 and (lambda r: r["profile"] == "unknown" and r["agent_roles"] == ["explore", "security-reviewer"] and "sk-live" not in json.dumps(r))(json.loads(events.read_text().splitlines()[-1])), events.read_text().splitlines()[-1])
        check("email-shaped profile -> unknown; bold keys still parsed", rec3["profile"] == "unknown" and rec3["playbook"] == "IMPLEMENT", json.dumps(rec3))
        check("agent roles: only labels kept", rec3["agent_roles"] == ["explorer"], json.dumps(rec3["agent_roles"]))
        check("environment label kept", rec3["environment"] == "prod")
        check("nothing leaky stored", all(x not in raw for x in ("secret-client", "AKIA", "akia", "user@example", "/tmp/x")), raw)
        run({**payload, "last_assistant_message": RESPONSE.replace("* Playbook: IMPLEMENT", "* Playbook: SOMETHING ELSE")}, env)
        check("unknown playbook -> unknown", json.loads(events.read_text().splitlines()[-1])["playbook"] == "unknown")

        # review finding 2: the contract's own example Status sentences map to an outcome
        for sentence, want in (("Validation failed. The deployment completed, but the health check still fails.", "failed"),
                               ("Root cause found. The service account is missing the required IAM role.", "partial"),
                               ("Complete. The change is implemented and validated.", "complete")):
            msg = "Status\n\n" + sentence + "\n\nHarness metadata\n* Harness: Groundwork\n* Playbook: VALIDATE\n"
            run({**payload, "last_assistant_message": msg}, env)
            got = json.loads(events.read_text().splitlines()[-1])["outcome"]
            check(f"outcome from Status sentence -> {want}", got == want, got)
        n_before = len(events.read_text().splitlines())

        # review finding 3: current-turn detection reads from the tail; cost follows turn size
        big = transcript(tmp, [
            [{"name": "Bash", "input": {"command": "terraform apply -auto-approve"}}],
            [{"name": "Read", "input": {"file_path": "/repo/big.txt", "pad": "x" * 600_000}},
             {"name": "Edit", "input": {"file_path": "/repo/c.py"}},
             {"name": "Bash", "input": {"command": "pytest -q"}}],
        ])
        run({**payload, "transcript_path": str(big)}, env)
        rec4 = json.loads(events.read_text().splitlines()[-1])
        check("multi-chunk turn: boundary found, previous-turn deploy excluded", rec4["deployment_performed"] is False and rec4["tests_run"] is True and rec4["files_changed"] == 1 and rec4["tools"] == ["Read", "Edit", "Bash"], json.dumps(rec4))
        huge = tmp / "huge.jsonl"
        with huge.open("w") as fh:
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": "old"}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "kubectl apply -f x"}}]}}) + "\n")
            for _ in range(200_000):
                fh.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "filler " * 20}]}}) + "\n")
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": "new"}}) + "\n")
            for _ in range(2_000):
                fh.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Grep", "input": {"pattern": "x"}}]}}) + "\n")
        import time as _t
        t0 = _t.time(); r = run({**payload, "transcript_path": str(huge)}, env); dt = _t.time() - t0
        rec5 = json.loads(events.read_text().splitlines()[-1])
        check(f"large session ({huge.stat().st_size // 1_000_000} MB, 200k old lines): only the current turn parsed, {dt:.2f}s", r.returncode == 0 and rec5["tools"] == ["Grep"] and rec5["deployment_performed"] is False and dt < 3.0, json.dumps(rec5) + f" dt={dt:.2f}")
        check("records appended for each of the above", len(events.read_text().splitlines()) == n_before + 2)

        # canonical layout: fenced code block, aligned Key: value lines, no bullets
        fenced = ("Status\n\nComplete. Done.\n\n```\nSTATUS\nCode: ok\nOverall: PARTIAL\n```\n\n```\nHARNESS METADATA\n"
                  "Harness:        Groundwork\nProfile:        work\nPlaybook:       DEPLOY\nExecution:      agent team\n"
                  "Agents:         3 — lead, implementer, validator\nEvidence:       repo + runtime\nValidation:     partial\nEnvironment:    staging\n```\n")
        run({**payload, "last_assistant_message": fenced}, env)
        recf = json.loads(events.read_text().splitlines()[-1])
        check("code-block layout parsed", recf["playbook"] == "DEPLOY" and recf["execution_mode"] == "agent_team" and recf["agent_count"] == 3 and recf["agent_roles"] == ["lead", "implementer", "validator"] and recf["evidence_sources"] == ["repo", "runtime"] and recf["validation"] == "partial" and recf["environment"] == "staging" and recf["profile"] == "work" and recf["outcome"] == "partial", json.dumps(recf))

        # no metadata block -> no record (trivial/conversational reply)
        n_before = len(events.read_text().splitlines())
        run({**payload, "last_assistant_message": "Sure — Terraform state maps config to real resources."}, env)
        check("no metadata block -> nothing appended", len(events.read_text().splitlines()) == n_before)

        # blocked outcome with a question -> clarification_required
        blocked = "Status\n\nBlocked. Which environment should I delete?\n\nHarness metadata\n* Harness: Groundwork\n* Playbook: DEPLOY\n* Execution: Single agent\n* Validation: Not verified\n\nWhich environment: dev, staging or prod?"
        run({**payload, "last_assistant_message": blocked, "transcript_path": str(transcript(tmp, [[]]))}, env)
        rec2 = json.loads(events.read_text().splitlines()[-1])
        check("blocked + question + not_verified + single_agent + zero agents", rec2["outcome"] == "blocked" and rec2["clarification_required"] is True and rec2["validation"] == "not_verified" and rec2["execution_mode"] == "single_agent" and rec2["agent_count"] == 0, json.dumps(rec2))

        # append-only: the first record is intact
        check("append-only", len(events.read_text().splitlines()) == n_before + 1 and '"sess-1"' in events.read_text().splitlines()[0])
        n_before = len(events.read_text().splitlines())
        check("owner-only permissions (file 0600, dir 0700)", (events.stat().st_mode & 0o777) == 0o600 and (events.parent.stat().st_mode & 0o777) == 0o700, oct(events.stat().st_mode & 0o777) + " " + oct(events.parent.stat().st_mode & 0o777))

        # opt-out, malformed input, unreadable transcript, unwritable path: all silent, exit 0
        r = run(payload, {**env, "GROUNDWORK_TELEMETRY": "off"})
        check("GROUNDWORK_TELEMETRY=off -> no write", r.returncode == 0 and len(events.read_text().splitlines()) == n_before)
        r = run(None, env, raw="not json")
        check("malformed input -> exit 0, silent", r.returncode == 0 and r.stdout == "")
        r = run({**payload, "transcript_path": "/nonexistent/x.jsonl"}, env)
        check("unreadable transcript -> still records with empty turn facts", r.returncode == 0 and json.loads(events.read_text().splitlines()[-1])["tools"] == [])
        r = run(payload, {**env, "GROUNDWORK_TELEMETRY_PATH": "/nonexistent-root-dir/events.jsonl"})
        check("unwritable path -> exit 0, silent", r.returncode == 0 and r.stdout == "" and r.stderr == "")
    finish()


if __name__ == "__main__":
    try:
        test_telemetry_hook()
    except AssertionError:
        pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
