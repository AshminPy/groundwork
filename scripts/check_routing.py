#!/usr/bin/env python3
"""Live routing check — model-behaviour evidence, not a unit test.

For each scenario in tests/routing_scenarios.json it starts a fresh headless Claude Code
session (`claude -p`) with the installed Groundwork rules loaded, asks only for the
routing decision, and compares category and ask/no-ask against the expectation.

It proves what Claude actually chose on this machine, with the currently installed
rules; it does not prove future sessions will choose the same. Skips (exit 0) when the
CLI is not logged in — never fakes a result.

Usage: python3 scripts/check_routing.py [--model haiku|sonnet|…] [--only <substring of prompt>]
Cost note: each scenario is a fresh session that loads the full rule/plugin context (~$0.20 on
sonnet with ECC installed); use --only while iterating, or --model haiku for a cheaper pass.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = REPO_ROOT / "tests" / "routing_scenarios.json"

ASK = (
    "You are being used to check Groundwork's task routing rule (~/.claude/rules/groundwork/task-routing.md). "
    "For the request below, do NOT do the task and do NOT run tools. Reply with exactly two lines:\n"
    "CATEGORY: <one of RESEARCH, EXPLAIN, DESIGN, PLAN, IMPLEMENT, TROUBLESHOOT, VALIDATE, AUDIT, DEPLOY, DOCUMENT>\n"
    "ASK_FIRST: <YES if the routing rule's material-ambiguity test means you must ask a clarifying question before acting, else NO>\n\n"
    "Request: "
)


def logged_in() -> bool:
    try:
        out = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=30).stdout
        return json.loads(out).get("loggedIn") is True
    except Exception:
        return False


def main() -> int:
    model = None
    if "--model" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1]
    if not logged_in():
        print("SKIP: claude CLI is not logged in (run `claude login`); no routing evidence produced.")
        return 0
    scenarios = json.loads(SCENARIOS.read_text())
    if "--only" in sys.argv:
        needle = sys.argv[sys.argv.index("--only") + 1].lower()
        scenarios = [s for s in scenarios if needle in s["prompt"].lower()]
    env = dict(os.environ, NODE_USE_SYSTEM_CA="0")
    failures = 0
    total_cost = 0.0
    print(f"{'expected':13s} {'asks':5s} {'got':13s} {'asks':5s} prompt")
    for s in scenarios:
        cmd = ["claude", "-p", ASK + s["prompt"], "--output-format", "json", "--max-turns", "1"]
        if model:
            cmd += ["--model", model]
        try:
            raw = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env, cwd=str(REPO_ROOT)).stdout
            data = json.loads(raw)
            text = data.get("result", "")
            total_cost += float(data.get("total_cost_usd") or 0)
        except Exception as exc:  # network/CLI failure is reported, not hidden
            text = f"ERROR {exc}"
        got_cat = next((line.split(":", 1)[1].strip().upper() for line in text.splitlines() if line.upper().startswith("CATEGORY:")), "?")
        got_ask = next((line.split(":", 1)[1].strip().upper().startswith("Y") for line in text.splitlines() if line.upper().startswith("ASK_FIRST:")), None)
        ok = got_cat == s["expected"] and got_ask == s["expect_question"]
        failures += 0 if ok else 1
        print(f"{s['expected']:13s} {str(s['expect_question']):5s} {got_cat:13s} {str(got_ask):5s} {'ok  ' if ok else 'FAIL'} {s['prompt'][:60]}")
    print(f"\n{len(scenarios) - failures}/{len(scenarios)} scenarios matched; total cost ${total_cost:.3f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
