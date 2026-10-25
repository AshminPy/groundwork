#!/usr/bin/env python3
"""A stand-in for the `claude` binary in tests. Never calls a model.

FAKE_CLAUDE_PLAN: {"base": <calls already made>, "steps": [...]}, one step per `-p` call (the last repeats):
  {"result": {...structured_output...}, "text": "...", "exit": 0, "raw": "<literal stdout>", "stderr": "",
   "is_error": false, "subtype": "success", "write": {"relative/path": "content"}, "sleep": 0}
FAKE_CLAUDE_LOG: JSONL file; one line per call with argv, cwd, stdin and whether ANTHROPIC_API_KEY was visible.
FAKE_CLAUDE_AUTH: JSON printed for `claude auth status` (default: a claude.ai Max login).
"""
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    argv = sys.argv[1:]
    if argv[:2] == ["auth", "status"]:
        print(os.environ.get("FAKE_CLAUDE_AUTH") or json.dumps(
            {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "subscriptionType": "max"}))
        return 0
    stdin = sys.stdin.read()
    log = Path(os.environ["FAKE_CLAUDE_LOG"])
    with log.open("a") as f:
        f.write(json.dumps({"argv": argv, "cwd": os.getcwd(), "stdin": stdin, "pid": os.getpid(),
                            "env_api_key": "ANTHROPIC_API_KEY" in os.environ}) + "\n")
    n = sum(1 for _ in log.open()) - 1
    plan = json.loads(Path(os.environ["FAKE_CLAUDE_PLAN"]).read_text())
    steps = plan["steps"]
    step = steps[min(n - plan["base"], len(steps) - 1)]
    for rel, content in (step.get("write") or {}).items():
        p = Path(os.getcwd()) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    time.sleep(step.get("sleep", 0))
    if "raw" in step:
        sys.stdout.write(step["raw"])
    else:
        sid = argv[argv.index("--resume") + 1] if "--resume" in argv else argv[argv.index("--session-id") + 1]
        out = {"type": "result", "subtype": step.get("subtype", "success"), "is_error": step.get("is_error", False),
               "result": step.get("text", "ok"), "session_id": sid, "num_turns": 1, "total_cost_usd": 0.01,
               "usage": {"input_tokens": 10, "output_tokens": 5}, "modelUsage": {"claude-fake-1": {}},
               "permission_denials": step.get("denials", [])}
        if "result" in step:
            out["structured_output"] = step["result"]
        sys.stdout.write(json.dumps(out))
    sys.stderr.write(step.get("stderr", ""))
    return step.get("exit", 0)


if __name__ == "__main__":
    sys.exit(main())
