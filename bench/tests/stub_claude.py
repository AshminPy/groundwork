#!/usr/bin/env python3
"""Stub `claude` for dry runs: prints a canned stream-json result. When the arm's CLAUDE_CONFIG_DIR holds a
`.stub_solve` file, it copies the case's oracle into the workspace first, so the dry run exercises both a completed
and a not-completed path. (Arms get an allow-listed environment, so a marker file is used, not a variable.)"""
import json
import os
import shutil
import sys
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] == "auth":
    print(json.dumps({"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty"}))
    sys.exit(0)
sys.stdin.read()
cwd = Path.cwd()
case = cwd.parent.parent.name
config = Path(os.environ.get("CLAUDE_CONFIG_DIR", "/nonexistent"))
oracle = Path(__file__).resolve().parents[1] / "oracle" / case
if (config / ".stub_solve").exists() and oracle.exists():
    shutil.copytree(oracle, cwd, dirs_exist_ok=True)
print(json.dumps({"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "python3 -m pytest -q"}}]}}))
print(json.dumps({"type": "user", "message": {"content": [
    {"type": "tool_result", "tool_use_id": "t1", "is_error": False, "content": "1 passed"}]}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 2,
                  "result": "Done: the fix is implemented and all tests pass.",
                  "usage": {"input_tokens": 10, "output_tokens": 100, "cache_read_input_tokens": 5000,
                            "cache_creation_input_tokens": 200},
                  "modelUsage": {"claude-sonnet-stub": {}}, "permission_denials": []}))
