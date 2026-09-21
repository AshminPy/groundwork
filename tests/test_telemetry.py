#!/usr/bin/env python3
"""Deterministic checks for hooks/groundwork_telemetry.py — no Claude Code needed.

Run: python3 tests/test_telemetry.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
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
    env.pop("GROUNDWORK_PROFILE", None)
    env.update(env_extra or {})
    return subprocess.run(["python3", str(HOOK)], input=raw if raw is not None else json.dumps(payload),
                          capture_output=True, text=True, timeout=30, env=env)


def transcript(tmp: Path, turns, name="t.jsonl") -> Path:
    """turns: list of lists of tool_use dicts; a human prompt precedes each turn."""
    lines = []
    for turn in turns:
        lines.append({"type": "user", "message": {"role": "user", "content": "do the thing"}, "promptSource": "sdk"})
        for tu in turn:
            lines.append({"type": "assistant", "message": {"content": [{"type": "tool_use", **tu}]}})
            lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}})
    p = tmp / name
    p.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return p


def load_module():
    spec = importlib.util.spec_from_file_location("gw_telemetry", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BLOCK = "```\nHARNESS METADATA\nGroundwork 1.3.2 · IMPLEMENT\nExecution:   2 subagents\nEvidence:    repo + tests + runtime\nValidation:  verified\n```\n"

RESPONSE = """Status

Complete. The change is implemented and validated.

What matters
* [x] All checks passed.

Validation
Code, tests, review and live check all passed.

Technical details
* Tests: 12 passed

""" + BLOCK


def last(events: Path) -> dict:
    return json.loads(events.read_text().splitlines()[-1])


def test_outcome_classifier() -> None:
    """Outcome comes from the response's status language; nothing recognisable stays unknown."""
    print("outcome_from_text")
    m = load_module()
    cases = [
        # output-contract examples
        ("Status\n\nComplete. The change is implemented and validated.", "complete"),
        ("Status\n\nRoot cause found. The service account is missing the required IAM role.", "partial"),
        ("Status\n\nValidation failed. The deployment completed, but the health check still fails.", "failed"),
        # playbook vocabularies
        ("**Status** — Fixed. Retry logic restored; tests green.", "complete"),
        ("**Status:** Deployed. Version 1.4 is live in staging.", "complete"),
        ("**Result** pass with issues — two NICE TO HAVE findings.", "complete"),
        ("**Result**\nFail. Two of six requirements did not hold.", "failed"),
        ("**Result:** not verified — no staging access.", "partial"),
        ("Status\n\nPartial. Code and tests done; deployment not attempted.", "partial"),
        ("Status\n\nBlocked. The delete needs your approval.", "blocked"),
        ("## Status\nFailed. The migration aborted half way.", "failed"),
        ("Status\n\nNot yet complete — review pending.", "partial"),
        ("Status\n\nDone. All 12 tests pass, no failures.", "complete"),
        # review findings: a later failure/block/gap in the status paragraph outranks a leading "Complete."
        ("Status\n\nComplete. Two tests still fail.", "failed"),
        ("Status\n\nDone. Deployment failed in staging.", "failed"),
        ("Status\n\nComplete. Live production behaviour was not tested.", "partial"),
        ("Status\n\nDeployed to staging; production deploy not attempted.", "partial"),
        ("Status\n\nFixed. The health check no longer fails.", "complete"),
        ("Status\n\nDone, but the rollout needs your approval.", "blocked"),
        # seen in fresh sessions: a test count with "0 failed" is not a failure; a plain "Complete." opener is status language
        ("All Groundwork hook tests pass.\n\n**Result:** 93 passed, 0 failed, across all 5 hook test groups.", "complete"),
        ("Complete. `subtract(a, b)` is added to `calc.py`, tested, and committed (not pushed).\n\n**Validation**\n- ok", "complete"),
        ("Blocked. The command needs your approval.\n\n- x", "blocked"),
        # an explicit "Next action: none" declares nothing remains; a bare description under Result does not
        ("**Result:** Added `subtract(a, b)` to `calc.py`, ran the tests, committed. Not pushed.\n\n**Validation:** 2 passed\n\n**Risk:** none known\n\n**Next action:** none, unless you want this pushed.", "complete"),
        ("**Result:** Added `subtract(a, b)` to `calc.py`, ran the tests, committed.\n\n**Validation:** 2 passed", "unknown"),
        ("**Result:** The deploy failed in staging.\n\n**Next action:** none until you decide.", "failed"),
        # explicit Overall wins
        ("Status\n\nComplete.\n\n```\nOverall: PARTIAL\n```", "partial"),
        # behaviour-rule bold verdict openers
        ("**My call: all 4 fixes are tested. Safe to merge.**\n\n- x", "complete"),
        ("**Done. The block is now a fenced code block.**", "complete"),
        ("**My finding: the hook is fail-open by construction — no code path exits non-zero.**", "unknown"),
        # non-status playbooks: the result heading is a structural signal
        ("**Answer**\nTerraform state maps configuration to real resources.\n\n**Why it matters**\n…", "complete"),
        ("**Recommendation**\nUse Cloud Run.\n\nWhich region should it run in?", "blocked"),
        ("**Deliverable**\ndocs/runbook.md written.", "complete"),
        # missing / ambiguous -> unknown (never 'complete' just because text exists)
        ("Status\n\nI looked at the code and the tests.", "unknown"),
        ("Here is what I found in the repository.\n\n- a\n- b", "unknown"),
        ("", "unknown"),
        ("**What matters**\n- the config is fine", "unknown"),
    ]
    for text, want in cases:
        got = m.outcome_from_text(text)
        check(f"{want:8s} <- {text[:52]!r}", got == want, f"got {got}")
    finish()


def test_telemetry_hook() -> None:
    print("groundwork_telemetry.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfg = tmp / "claude"
        (cfg / "groundwork").mkdir(parents=True)
        (cfg / "groundwork" / "VERSION").write_text("1.3.2\n")
        env = {"CLAUDE_CONFIG_DIR": str(cfg)}
        events = cfg / "groundwork" / "telemetry" / "events.jsonl"

        # turn 1 (old): a deploy; turn 2 (current): edits, a test run, an MCP call, two agents, a secret in a command
        t = transcript(tmp, [
            [{"name": "Bash", "input": {"command": "terraform apply -auto-approve"}}],
            [{"name": "Read", "input": {"file_path": "/repo/a.py"}},
             {"name": "Edit", "input": {"file_path": "/repo/a.py"}},
             {"name": "Write", "input": {"file_path": "/repo/b.py"}},
             {"name": "Edit", "input": {"file_path": "/repo/a.py"}},
             {"name": "Bash", "input": {"command": "TOKEN=sk-live-SECRET123 python3 tests/test_hooks.py"}},
             {"name": "mcp__github__list_prs", "input": {"repo": "x"}},
             {"name": "Agent", "input": {"subagent_type": "Explore", "prompt": "map"}},
             {"name": "Agent", "input": {"name": "security-reviewer", "prompt": "review"}}],
        ])
        payload = {"session_id": "sess-1", "prompt_id": "p-9", "cwd": str(tmp), "transcript_path": str(t),
                   "last_assistant_message": RESPONSE, "hook_event_name": "Stop"}
        r = run(payload, {**env, "GROUNDWORK_PROFILE": "work"})
        check("exit 0 and silent", r.returncode == 0 and r.stdout.strip() == "" and r.stderr.strip() == "", r.stdout + r.stderr)
        check("one record appended", events.is_file() and len(events.read_text().splitlines()) == 1)
        rec = last(events); ob, de = rec["observed"], rec["declared"]
        check("schema 2 with observed / declared split", rec["schema"] == 2 and set(ob) == {"profile", "tools", "mcp_servers", "agent_calls", "agent_types", "files_changed", "tests_run", "implementation_performed", "deployment_performed"} and set(de) == {"block_present", "playbook", "execution_mode", "agent_count", "agent_roles", "evidence_sources", "validation", "environment", "outcome", "clarification_required"}, json.dumps(rec))
        check("identifiers and version", rec["session_id"] == "sess-1" and rec["prompt_id"] == "p-9" and rec["harness_version"] == "1.3.2" and rec["harness"] == "Groundwork")
        check("observed profile from GROUNDWORK_PROFILE", ob["profile"] == "work")
        check("concise block parsed: headline playbook, N subagents, evidence, validation", de["playbook"] == "IMPLEMENT" and de["execution_mode"] == "subagents" and de["agent_count"] == 2 and de["evidence_sources"] == ["repo", "tests", "runtime"] and de["validation"] == "verified", json.dumps(de))
        check("no Agents line: roles filled from observed agent types", de["agent_roles"] == ["explore", "security-reviewer"], json.dumps(de))
        check("outcome complete from the Status sentence", de["outcome"] == "complete")
        check("observed agent calls and types from the transcript", ob["agent_calls"] == 2 and ob["agent_types"] == ["explore", "security-reviewer"], json.dumps(ob))
        check("current turn only: deploy from the previous turn not counted", ob["deployment_performed"] is False and ob["tests_run"] is True)
        check("tools, mcp servers, distinct files", ob["tools"] == ["Read", "Edit", "Write", "Bash", "mcp__github__list_prs", "Agent"] and ob["mcp_servers"] == ["github"] and ob["files_changed"] == 2, json.dumps(ob))
        check("implementation flag", ob["implementation_performed"] is True)
        check("no clarification question", de["clarification_required"] is False)
        raw = events.read_text()
        check("no secrets, commands, paths or prompt text stored", all(x not in raw for x in ("SECRET123", "terraform apply", "/repo/a.py", "test_hooks", "do the thing", "map")), raw)
        check("cwd stored only as a short hash", len(rec["cwd_hash"]) == 12 and str(tmp) not in raw)
        check("owner-only permissions (file 0600, dir 0700)", (events.stat().st_mode & 0o777) == 0o600 and (events.parent.stat().st_mode & 0o777) == 0o700, oct(events.stat().st_mode & 0o777))

        # consistency: observed Agent calls are authoritative for count, mode and roles
        one_agent = transcript(tmp, [[{"name": "Agent", "input": {"subagent_type": "ecc:code-reviewer", "prompt": "review"}},
                                      {"name": "Bash", "input": {"command": "pytest -q"}}]], "one.jsonl")
        inconsistent = RESPONSE.replace("Execution:   2 subagents", "Execution:   2 subagents\nAgents:      1 — code reviewer")
        run({**payload, "transcript_path": str(one_agent), "last_assistant_message": inconsistent}, env)
        rec = last(events); ob, de = rec["observed"], rec["declared"]
        check("declared '2 subagents' + 1 role vs 1 observed call -> count 1, mode subagents, one role", ob["agent_calls"] == 1 and ob["agent_types"] == ["ecc:code-reviewer"] and de["agent_count"] == 1 and de["execution_mode"] == "subagents" and de["agent_roles"] == ["code reviewer"], json.dumps(rec))
        run({**payload, "transcript_path": str(one_agent), "last_assistant_message": RESPONSE.replace("Execution:   2 subagents", "Execution:   2 subagents\nAgents:      2 — explorer, reviewer")}, env)
        de = last(events)["declared"]
        check("declared 2 roles vs 1 observed call -> count 1, observed role replaces declared roles", de["agent_count"] == 1 and de["agent_roles"] == ["ecc:code-reviewer"], json.dumps(de))
        run({**payload, "last_assistant_message": RESPONSE.replace("Execution:   2 subagents", "Execution:   2 subagents\nAgents:      2 — explorer, reviewer")}, env)
        de = last(events)["declared"]
        check("declared count matches 2 observed calls -> declared roles kept", de["agent_count"] == 2 and de["agent_roles"] == ["explorer", "reviewer"], json.dumps(de))
        run({**payload, "last_assistant_message": RESPONSE.replace("Execution:   2 subagents", "Execution:   single agent")}, env)
        de = last(events)["declared"]
        check("declared 'single agent' but 2 observed calls -> subagents, 2, observed roles", de["execution_mode"] == "subagents" and de["agent_count"] == 2 and de["agent_roles"] == ["explore", "security-reviewer"], json.dumps(de))
        run({**payload, "transcript_path": str(transcript(tmp, [[{"name": "Bash", "input": {"command": "ls"}}]], "none.jsonl")), "last_assistant_message": RESPONSE.replace("Execution:   2 subagents", "Execution:   single agent\nAgents:      1 — reviewer")}, env)
        de = last(events)["declared"]
        check("no observed calls and declared single agent -> count 0, no roles", de["execution_mode"] == "single_agent" and de["agent_count"] == 0 and de["agent_roles"] == [], json.dumps(de))
        run({**payload, "transcript_path": "/nonexistent/x.jsonl", "last_assistment_message": None, "last_assistant_message": RESPONSE.replace("Execution:   2 subagents", "Execution:   2 subagents\nAgents:      2 — a, b")}, env)
        de = last(events)["declared"]
        check("transcript unreadable (nothing observed) -> declared values kept as stated", de["agent_count"] == 2 and de["execution_mode"] == "subagents" and de["agent_roles"] == ["a", "b"], json.dumps(de))

        # profile unset -> unknown (never taken from the model's block)
        run({**payload, "last_assistant_message": RESPONSE.replace("Execution:", "Profile:     work\nExecution:")}, env)
        check("profile without GROUNDWORK_PROFILE -> unknown even if the block states one", last(events)["observed"]["profile"] == "unknown")

        # full (long) layout and bullets still parsed
        long_block = ("Harness metadata\n* Harness: Groundwork\n* **Playbook:** DEPLOY\n* Execution: agent team\n* Agents: 3 — lead, implementer, validator\n"
                      "* Evidence: repo / runtime / docs\n* Validation: partial\n* Environment: staging\n")
        run({**payload, "last_assistant_message": "Status\n\nDeployed. Health check green.\n\n" + long_block}, env)
        de = last(events)["declared"]
        check("long layout: bold key, agent team, slash-separated evidence, environment; declared 3 roles reconciled to the 2 observed calls", de["playbook"] == "DEPLOY" and de["execution_mode"] == "agent_team" and de["agent_count"] == 2 and de["agent_roles"] == ["explore", "security-reviewer"] and de["evidence_sources"] == ["repo", "runtime", "docs"] and de["environment"] == "staging" and de["outcome"] == "complete", json.dumps(de))

        # privacy: free text in the block must not leak paths / tokens / sentences
        leaky = ("Status\n\nComplete.\n\n```\nHARNESS METADATA\nGroundwork 1.3.2 · IMPLEMENT\nExecution:   1 subagent\n"
                 "Agents:      1 — reviewer-with-token-sk-live-51h8abcdefghijklmnop, /tmp/x, explorer\n"
                 "Evidence:    /Users/me/secret-client/src/auth.py + AKIAABCDEXAMPLE123 + repo (static read) + tests\n"
                 "Validation:  verified\nEnvironment: prod-db_password=supersecrethunter2-ghp_abcdefgh\n```\n")
        run({**payload, "last_assistant_message": leaky}, env)
        raw = events.read_text(); de = last(events)["declared"]
        check("path / token tokens dropped from evidence", de["evidence_sources"] == ["repo", "tests"], json.dumps(de["evidence_sources"]))
        check("agent roles: leaky declared roles replaced by the observed agent types", de["agent_roles"] == ["explore", "security-reviewer"], json.dumps(de["agent_roles"]))
        check("secret-shaped environment -> unknown", de["environment"] == "unknown")
        check("nothing leaky stored", all(x not in raw for x in ("secret-client", "AKIA", "akia", "sk-live", "ghp_", "supersecret", "/tmp/x")), raw)
        run({**payload, "last_assistant_message": RESPONSE.replace("· IMPLEMENT", "· SOMETHING")}, env)
        check("unknown playbook -> unknown", last(events)["declared"]["playbook"] == "unknown")

        # outcome through the hook, end to end
        for sentence, want in (("Validation failed. The deployment completed, but the health check still fails.", "failed"),
                               ("Blocked. Which environment should I delete?", "blocked"),
                               ("Partial. Tests pass; live validation not attempted.", "partial"),
                               ("Complete. Merged and live-validated.", "complete"),
                               ("I looked at the code.", "unknown")):
            run({**payload, "last_assistant_message": "Status\n\n" + sentence + "\n\n" + BLOCK}, env)
            got = last(events)["declared"]["outcome"]
            check(f"hook outcome {want} <- {sentence[:40]!r}", got == want, got)
        run({**payload, "last_assistant_message": "Status\n\nBlocked. Which environment?\n\n" + BLOCK + "\nWhich environment: dev, staging or prod?"}, env)
        check("trailing question -> clarification_required", last(events)["declared"]["clarification_required"] is True)

        # no block but tools used -> observed facts recorded, declared unknown, block_present false
        n_before = len(events.read_text().splitlines())
        run({**payload, "last_assistant_message": "**Complete.** subtract() added; 2 passed."}, env)
        rec = last(events)
        check("no block + tool use -> record with observed facts, block_present false", len(events.read_text().splitlines()) == n_before + 1 and rec["declared"]["block_present"] is False and rec["declared"]["playbook"] == "unknown" and rec["declared"]["outcome"] == "complete" and rec["observed"]["files_changed"] == 2, json.dumps(rec))
        # no block and no tool use -> nothing (conversational reply)
        n_before = len(events.read_text().splitlines())
        run({**payload, "last_assistant_message": "Sure — Terraform state maps config to real resources.", "transcript_path": str(transcript(tmp, [[]], "empty.jsonl"))}, env)
        check("no block, no tool use -> nothing appended", len(events.read_text().splitlines()) == n_before)
        check("block_present true when the block exists", json.loads(events.read_text().splitlines()[0])["declared"]["block_present"] is True)
        check("append-only: first record intact", '"sess-1"' in events.read_text().splitlines()[0])

        # current-turn detection reads from the tail; cost follows turn size
        big = transcript(tmp, [
            [{"name": "Bash", "input": {"command": "terraform apply -auto-approve"}}],
            [{"name": "Read", "input": {"file_path": "/repo/big.txt", "pad": "x" * 600_000}},
             {"name": "Edit", "input": {"file_path": "/repo/c.py"}},
             {"name": "Bash", "input": {"command": "pytest -q"}}],
        ], "big.jsonl")
        run({**payload, "transcript_path": str(big)}, env)
        ob = last(events)["observed"]
        check("multi-chunk turn: boundary found, previous-turn deploy excluded", ob["deployment_performed"] is False and ob["tests_run"] is True and ob["files_changed"] == 1 and ob["tools"] == ["Read", "Edit", "Bash"], json.dumps(ob))
        huge = tmp / "huge.jsonl"
        with huge.open("w") as fh:
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": "old"}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "kubectl apply -f x"}}]}}) + "\n")
            for _ in range(200_000):
                fh.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "filler " * 20}]}}) + "\n")
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": "new"}}) + "\n")
            for _ in range(2_000):
                fh.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Grep", "input": {"pattern": "x"}}]}}) + "\n")
        t0 = time.time(); r = run({**payload, "transcript_path": str(huge)}, env); dt = time.time() - t0
        ob = last(events)["observed"]
        check(f"large session ({huge.stat().st_size // 1_000_000} MB, 200k old lines): only the current turn parsed, {dt:.2f}s", r.returncode == 0 and ob["tools"] == ["Grep"] and ob["deployment_performed"] is False and dt < 3.0, json.dumps(ob) + f" dt={dt:.2f}")

        # opt-out, malformed input, unreadable transcript, unwritable path: all silent, exit 0
        n_before = len(events.read_text().splitlines())
        r = run(payload, {**env, "GROUNDWORK_TELEMETRY": "off"})
        check("GROUNDWORK_TELEMETRY=off -> no write", r.returncode == 0 and len(events.read_text().splitlines()) == n_before)
        r = run(None, env, raw="not json")
        check("malformed input -> exit 0, silent", r.returncode == 0 and r.stdout == "")
        r = run({**payload, "transcript_path": "/nonexistent/x.jsonl"}, env)
        check("unreadable transcript -> still records (block present) with empty observed facts", r.returncode == 0 and last(events)["observed"]["tools"] == [])
        r = run(payload, {**env, "GROUNDWORK_TELEMETRY_PATH": "/nonexistent-root-dir/events.jsonl"})
        check("unwritable path -> exit 0, silent", r.returncode == 0 and r.stdout == "" and r.stderr == "")
    finish()


if __name__ == "__main__":
    for fn in (test_outcome_classifier, test_telemetry_hook):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
