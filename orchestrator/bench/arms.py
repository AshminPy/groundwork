"""The two M1 arms, launched the same way apart from the harness itself.

A: plain `claude -p` with the instruction as typed. B: Groundwork PR #62 (`groundwork_orchestrator query`).
Both get Read/Grep/Glob only, the same isolation flags and read fence (taken from PR #62's adapter so they cannot
drift), the same cleaned environment, and the user's normal settings, so Groundwork's hooks run in both.
"""
from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from groundwork_orchestrator.claude_adapter import ISOLATION_FLAGS, claude_bin, worker_env
from groundwork_orchestrator.store import stop_group

ORCH_DIR = Path(__file__).resolve().parents[1]
READ_TOOLS = "Read,Grep,Glob"
TIMEOUT_S = 1200   # the same wall-clock limit for both arms


def clean_env() -> dict:
    return worker_env()


def arm_a_argv(model: str, effort: str, max_turns: int | None = None) -> list[str]:
    argv = [claude_bin() or "claude", "-p", "--output-format", "stream-json", "--verbose", "--include-hook-events",
            "--permission-prompts", "none", *ISOLATION_FLAGS, "--model", model, "--effort", effort,
            "--tools", READ_TOOLS, "--allowedTools", READ_TOOLS, "--no-session-persistence"]
    return argv + (["--max-turns", str(max_turns)] if max_turns else [])


def parse_stream(stdout: str) -> dict:
    ev = {"tool_uses": [], "tool_results": [], "hook_events": set(), "result": None, "rate_limit": None,
          "compact_boundaries": 0}
    for line in stdout.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        t, st = d.get("type"), d.get("subtype")
        if st == "hook_started":
            ev["hook_events"].add(d.get("hook_event"))
        elif st == "compact_boundary":
            ev["compact_boundaries"] += 1
        elif t == "rate_limit_event":
            ev["rate_limit"] = d.get("rate_limit_info")
        elif t == "assistant":
            for c in d["message"].get("content") or []:
                if c.get("type") == "tool_use":
                    ev["tool_uses"].append({"name": c["name"], "input": c.get("input") or {}})
        elif t == "user" and isinstance(d.get("message", {}).get("content"), list):
            for c in d["message"]["content"]:
                if c.get("type") == "tool_result":
                    ev["tool_results"].append({"is_error": bool(c.get("is_error"))})
        elif t == "result":
            ev["result"] = d
    return ev


def _usage(u: dict | None) -> dict:
    u = u or {}
    return {"input": u.get("input_tokens", 0), "cache_read": u.get("cache_read_input_tokens", 0),
            "cache_creation": u.get("cache_creation_input_tokens", 0), "output": u.get("output_tokens", 0)}


def _outside(ws: Path, tool_input: dict) -> bool:
    path = tool_input.get("file_path") or tool_input.get("path")
    if not path:
        return False
    p = Path(path) if os.path.isabs(path) else ws / path
    return not str(p.resolve()).startswith(str(ws.resolve()))


def run_arm_a(ws: Path, instruction: str, model: str, effort: str, timeout_s: int = TIMEOUT_S) -> dict:
    start = time.monotonic()
    try:
        p = subprocess.run(arm_a_argv(model, effort), cwd=ws, input=instruction, capture_output=True, text=True,
                           env=clean_env(), timeout=timeout_s)
        stdout, stderr, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        stdout, stderr, code = (out.decode() if isinstance(out, bytes) else out), "timeout", None
    wall = round(time.monotonic() - start, 1)
    ev = parse_stream(stdout)
    r = ev["result"] or {}
    ok = code == 0 and r.get("subtype") == "success" and not r.get("is_error")
    return {"ok": ok, "error": None if ok else (r.get("subtype") or (stderr or "no result")[-300:]),
            "exit_code": code, "wall_s": wall, "final_text": r.get("result") or "",
            "usage": _usage(r.get("usage")), "models": sorted((r.get("modelUsage") or {}).keys()),
            "sessions": 1, "num_turns": r.get("num_turns"),
            "tool_calls": len(ev["tool_uses"]),
            "outside_read_attempts": sum(1 for t in ev["tool_uses"] if _outside(ws, t["input"])),
            "hooks": sorted(h for h in ev["hook_events"] if h), "compact_boundaries": ev["compact_boundaries"],
            "rate_limit": ev["rate_limit"], "raw_stdout": stdout}


def _orch(args: list[str], home: Path, timeout_s: int) -> subprocess.CompletedProcess:
    """Run the orchestrator CLI in its own process group. On timeout the whole group is stopped: the orchestrator's
    workers run in their own sessions, so that is done with PR #62's own stop_group (it finds them by pid)."""
    env = {**os.environ, "GROUNDWORK_ORCH_HOME": str(home), "GROUNDWORK_ORCH_TELEMETRY": "off"}
    proc = subprocess.Popen([sys.executable, "-m", "groundwork_orchestrator", *args], cwd=ORCH_DIR, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        _stop_workers(home)
        raise
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


def _stop_workers(home: Path) -> None:
    db = home / "state.db"
    if not db.exists():
        return
    con = sqlite3.connect(db)
    try:
        pids = [p for (p,) in con.execute("select pid from sessions where pid is not null and ended_at is null")]
    finally:
        con.close()
    for pid in pids:
        stop_group(pid)


def b_visible_text(contract: dict) -> str:
    """What PR #62 shows the user as the answer: the result text plus its sources and stated unknowns. The harness's
    own status line is left out, so the grader cannot be swayed by it."""
    r = contract.get("result") or {}
    parts = [str(r[k]).strip() for k in ("answer", "document", "summary", "root_cause") if r.get(k)]
    if r.get("sources"):
        parts.append("sources: " + ", ".join(map(str, r["sources"])))
    for k in ("unknowns", "unverified_claims"):
        if r.get(k):
            parts.append(f"{k}: " + "; ".join(map(str, r[k])))
    if contract.get("evidence"):   # the evidence section the CLI prints under the answer (M2 and later)
        from groundwork_orchestrator import evidence
        parts.append(evidence.render(contract["evidence"]))
    return "\n\n".join(parts)


def _b_sessions(home: Path) -> dict:
    out = {"usage": {"input": 0, "cache_read": 0, "cache_creation": 0, "output": 0}, "sessions": 0,
           "models": set(), "roles": [], "session_failures": []}
    db = home / "state.db"
    if not db.exists():
        return out
    con = sqlite3.connect(db)
    try:
        for role, mods, u, failure in con.execute("select role, models, usage, failure from sessions"):
            out["sessions"] += 1
            out["roles"].append(role)
            out["models"].update(json.loads(mods or "[]"))
            if failure:
                out["session_failures"].append(failure)
            for k, v in _usage(json.loads(u or "{}")).items():
                out["usage"][k] += v
    finally:
        con.close()
    return out


def run_arm_b(ws: Path, instruction: str, home: Path, timeout_s: int = TIMEOUT_S) -> dict:
    home.mkdir(parents=True, exist_ok=True)
    _orch(["allow", str(ws)], home, 60)
    start = time.monotonic()
    try:
        p = _orch(["query", instruction, "--workspace", str(ws), "--json"], home, timeout_s)
        stdout, stderr, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        stdout, stderr, code = "", "timeout", None
    wall = round(time.monotonic() - start, 1)
    try:
        status = json.loads(stdout)
    except json.JSONDecodeError:
        status = {}
    c, state, tid = status.get("contract") or {}, status.get("state"), status.get("task_id")
    # Read-only benchmark: nothing is ever approved. A waiting or blocked task is closed and counted as a failure.
    if tid and state == "WAITING_APPROVAL":
        _orch(["reject", tid], home, 120)
    elif tid and state == "BLOCKED":
        _orch(["cancel", tid], home, 120)
    s = _b_sessions(home)
    ok = state == "PASSED"
    return {"ok": ok, "error": None if ok else (state or (stderr or "no output")[-300:]), "exit_code": code,
            "wall_s": wall, "final_text": b_visible_text(c), "usage": s["usage"], "models": sorted(s["models"]),
            "sessions": s["sessions"], "roles": s["roles"], "session_failures": s["session_failures"],
            "state": state, "harness_category": c.get("category"), "workflow": c.get("workflow"),
            "routing": {k: v.get("model") for k, v in (c.get("routing") or {}).items()},
            "harness_evidence_status": c.get("evidence_status"), "answer_evidence": c.get("answer_evidence"),
            "claims": [{k: x.get(k) for k in ("id", "status", "reason")} for x in (c.get("evidence") or {}).get("claims", [])]}
