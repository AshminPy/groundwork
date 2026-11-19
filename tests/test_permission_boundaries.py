#!/usr/bin/env python3
"""Permission tiers (docs/PERMISSIONS.md): HARD DENY, HUMAN APPROVAL and AUTONOMOUS probes through the real hooks.

Each probe sends Claude Code's PreToolUse payload to the installed hook scripts in a temporary repository on a
feature branch, with CLAUDE_CONFIG_DIR pointing at a temporary directory. Run directly:
python3 tests/test_permission_boundaries.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / "hooks"
PUSH = HOOKS / "block_protected_push.py"
GATE = HOOKS / "groundwork_task_gate.py"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import merge_settings  # noqa: E402

PASS = FAIL = 0
_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        _FAILURES.append(f"{name}  {detail}")
        print(f"  FAIL {name}  {detail}")


def decision(hook: Path, repo: Path, env: dict, tool: str, tool_input: dict) -> str:
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": str(repo),
               "transcript_path": ""}
    r = subprocess.run(["python3", str(hook)], input=json.dumps(payload), capture_output=True, text=True, timeout=30,
                       env=env)
    if not r.stdout.strip():
        return "allow"
    return json.loads(r.stdout).get("hookSpecificOutput", {}).get("permissionDecision", "other")


def tier(repo: Path, env: dict, tool: str, tool_input: dict) -> str:
    """The strongest decision across Groundwork's PreToolUse hooks: deny beats ask beats allow, as in Claude Code."""
    found = [decision(GATE, repo, env, tool, tool_input)]
    if tool == "Bash":
        found.append(decision(PUSH, repo, env, tool, tool_input))
    return "deny" if "deny" in found else "ask" if "ask" in found else "allow"


def test_permission_boundaries() -> None:
    print("permission tiers — hard deny, human approval, autonomous")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        repo = tmp / "repo"
        repo.mkdir()
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(tmp / "cfg"), "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_SYSTEM": os.devnull}
        for args in (["init", "-q", "-b", "main"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init"],
                     ["checkout", "-qb", "feature/x"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True, env=env, capture_output=True)
        (repo / "app.py").write_text("x = 1\n")
        transcript = tmp / "t.jsonl"
        transcript.write_text(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "echo hi"}}]}}) + "\n")

        deny_rules = set(merge_settings.GROUNDWORK_DENY)
        for rule in ("Bash(sudo *)", "Bash(rm -rf /*)", "Bash(rm -rf ~*)", "Bash(git push --force*)", "Bash(git push -f *)"):
            check(f"HARD DENY native rule shipped: {rule}", rule in deny_rules)

        hard_deny = ["git push origin main", "git push origin HEAD:master", "git push --force origin feature/x",
                     "git push origin +feature/x", "git push --mirror origin", "cd . && git push origin main"]
        for cmd in hard_deny:
            got = tier(repo, env, "Bash", {"command": cmd})
            check(f"HARD DENY: {cmd}", got == "deny", got)
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(repo),
                   "tool_input": {"command": "gh pr create -t t -b b"}, "transcript_path": str(transcript)}
        r = subprocess.run(["python3", str(GATE)], input=json.dumps(payload), capture_output=True, text=True,
                           timeout=30, env=env)
        check("HARD DENY: gh pr create with no independent review", '"permissionDecision": "deny"' in r.stdout, r.stdout)

        approval = ["cat .env", "cat ~/.aws/credentials", "gcloud compute instances delete vm1", "kubectl delete pod x",
                    "terraform apply", "helm upgrade app ./chart", "git reset --hard HEAD~1", "git clean -fdx", "git checkout -- .", "git branch -D old",
                    "psql -c 'drop table t'", "sudo ls", "gh auth token",
                    "echo '{\"disableAllHooks\": true}' > ~/.claude/settings.json"]
        for cmd in approval:
            got = tier(repo, env, "Bash", {"command": cmd})
            check(f"HUMAN APPROVAL: {cmd}", got in ("ask", "deny"), got)
        for tool, path in (("Read", str(repo / ".env")), ("Edit", os.path.expanduser("~/.claude/settings.json")),
                           ("Edit", str(tmp / "cfg" / "hooks" / "groundwork_task_gate.py"))):
            got = tier(repo, env, tool, {"file_path": path, "old_string": "a", "new_string": "b"})
            check(f"HUMAN APPROVAL: {tool} {Path(path).name}", got == "ask", got)

        autonomous = ["ls -la", "git status", "git diff", "python3 -m pytest -q", "git add -A", "git commit -m x",
                      "git checkout -b feature/y", "git push origin feature/x", "gh pr create --draft -t t -b b",
                      "gh pr list", "rm -rf build", f"rm -rf {tmp}/scratch"]
        for cmd in autonomous:
            got = tier(repo, env, "Bash", {"command": cmd})
            check(f"AUTONOMOUS: {cmd}", got == "allow", got)
        for tool in ("Read", "Edit"):
            got = tier(repo, env, tool, {"file_path": str(repo / "app.py"), "old_string": "1", "new_string": "2"})
            check(f"AUTONOMOUS: {tool} a repository file", got == "allow", got)
    assert not _FAILURES, "\n".join(_FAILURES)


if __name__ == "__main__":
    try:
        test_permission_boundaries()
    except AssertionError:
        pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
