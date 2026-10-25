"""Command line for the orchestrator: `groundwork query` submits a task, `groundwork orch ...` operates on tasks."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import routing, workspace
from .claude_adapter import preflight
from .contract import new_contract
from .store import Store, TaskBusy, new_task_id

EXIT = {"PASSED": 0, "WAITING_APPROVAL": 3, "BLOCKED": 4, "CANCELLED": 5, "FAILED": 1}
BUSY_EXIT = 6


def home_dir() -> Path:
    env = os.environ.get("GROUNDWORK_ORCH_HOME")
    if env:
        return Path(env)
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / "groundwork" / "orchestrator"


def _orchestrator():
    from .graph import Orchestrator  # imported late: `allow`, `list` and `show` work without LangGraph loaded
    return Orchestrator(home_dir())


def render(status: dict, store: Store) -> str:
    c, tid = status["contract"], status["task_id"]
    lines = [f"Task {tid}: {status['state']}" + (f" — {c.get('evidence_status')}" if c.get("evidence_status") else ""),
             f"  request:  {c['request']}",
             f"  category: {c.get('category')} (risk {c.get('risk')}, workflow {c.get('workflow')})"]
    if c.get("classification"):
        lines.append(f"  why:      {c['classification'].get('reasoning')}")
    for kind, ch in (c.get("routing") or {}).items():
        lines.append(f"  model:    {kind} → {ch['model']} / effort {ch['effort']} ({ch['reason']})")
    if c.get("worktree"):
        lines.append(f"  worktree: {c['worktree']['path']} (branch {c['worktree']['branch']})")
    result = c.get("result") or {}
    for key in ("answer", "summary", "root_cause", "document"):
        if result.get(key):
            lines += ["", f"{key}:", result[key].strip()]
    if result.get("confirmed") is not None:
        lines.append(f"root cause confirmed by worker evidence: {result['confirmed']}")
    if result.get("sources"):
        lines.append("sources: " + ", ".join(result["sources"]))
    for k in ("unknowns", "unverified_claims"):
        if result.get(k):
            lines.append(f"{k}: " + "; ".join(result[k]))
    if c.get("validation"):
        lines += ["", "validation (deterministic):"]
        for i in c["validation"][-1]["items"]:
            mark = "[!]" if i.get("warning") else ("[x]" if i["ok"] else "[ ]")
            detail = f" — {i['detail']}" if i.get("detail") else ""
            files = f" — files: {', '.join(i['files'])}" if i.get("files") else ""
            lines.append(f"  {mark} {i['check']}{detail}{files}")
    if c.get("retry_count"):
        lines.append(f"repairs: {c['retry_count']}")
    if c.get("outcome"):
        lines += ["", f"outcome: {c['outcome']}"]
    w = status.get("waiting")
    if w and w["value"].get("kind") == "approval":
        lines += ["", f"next: review the plan, then `groundwork orch approve {tid}` or `groundwork orch reject {tid}`"]
        plan = c.get("plan") or {}
        for step in plan.get("steps") or []:
            lines.append(f"  - {step}")
        for s in c.get("symptoms") or []:
            lines.append(f"  observed: `{s['cmd']}` exit {s['exit_code']}: "
                         f"{(s['output_tail'].strip().splitlines() or [''])[-1][:200]}")
        lines.append(f"  on approval: a worker changes files only in a new worktree (branch gw/{tid}); "
                     f"then these must exit 0: {', '.join(c['checks']) or '(none)'}")
        lines.append(f"  [!] {w['value'].get('exposure', '')}")
    elif w and w["value"].get("kind") == "blocked":
        lines += ["", f"next: fix the cause, then `groundwork orch resume {tid}` (or `groundwork orch cancel {tid}`)"]
    return "\n".join(lines)


def cmd_query(a) -> int:
    home = home_dir()
    if not a.request.strip():
        print("query: the request is empty", file=sys.stderr)
        return 2
    if any("," in c for c in a.check or []):
        print("query: a --check command cannot contain a comma (Claude Code's tool rules are comma-separated); "
              "put it in a script and check that instead", file=sys.stderr)
        return 2
    contract = new_contract(new_task_id(), a.request.strip(), os.path.realpath(a.workspace), a.check or [], a.allow_write)
    orch = _orchestrator()
    try:
        status = orch.start(contract)
        print(json.dumps(status, indent=2, default=str) if a.json else render(status, orch.store))
        return EXIT.get(status["state"], 1)
    finally:
        orch.close()


def cmd_show(a) -> int:
    store = Store(home_dir())
    t = store.task(a.task_id)
    if not t:
        print(f"show: no task {a.task_id}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({**t, "transitions": store.transitions(a.task_id), "sessions": store.sessions(a.task_id),
                          "operations": store.operations(a.task_id)}, indent=2, default=str))
        return 0
    orch = _orchestrator()
    try:
        print(render(orch.status(a.task_id), store))
    finally:
        orch.close()
    print("\nhistory:")
    for tr in store.transitions(a.task_id):
        print(f"  {tr['ts']}  {tr['from_state'] or '-':>16} → {tr['to_state']:<16} {tr['reason']}")
    print("sessions:")
    for s in store.sessions(a.task_id):
        cost = f", est. ${s['cost_estimate_usd']:.4f} (client-side estimate, not a bill)" if s["cost_estimate_usd"] else ""
        print(f"  {s['role']}: {s['model']}/{s['effort']} session {s['session_id']} pid {s['pid']} — {s['status']}"
              f"{' (' + s['failure'] + ')' if s['failure'] else ''}, {s['duration_s']}s{cost}")
    return 0


def cmd_list(a) -> int:
    for t in Store(home_dir()).list_tasks(a.limit):
        print(f"{t['id']}  {t['state']:<16} {t['category'] or '-':<15} {t['evidence_status'] or '':<18} "
              f"{t['request'][:60]}")
    return 0


def _answer(task_id: str, value_for) -> int:
    orch = _orchestrator()
    try:
        if not orch.store.task(task_id):
            print(f"no task {task_id}", file=sys.stderr)
            return 2
        waiting = orch.pending_interrupt(task_id)
        value = value_for(waiting["value"] if waiting else None)
        if value is None:
            return 2
        status = orch.resume(task_id, value)
        print(render(status, orch.store))
        return EXIT.get(status["state"], 1)
    finally:
        orch.close()


def cmd_approve(a) -> int:
    def v(w):
        if not w or w.get("kind") != "approval":
            print("approve: this task is not waiting for approval", file=sys.stderr)
            return None
        return {"approved": True}
    return _answer(a.task_id, v)


def cmd_reject(a) -> int:
    def v(w):
        if not w or w.get("kind") != "approval":
            print("reject: this task is not waiting for approval", file=sys.stderr)
            return None
        return {"approved": False}
    return _answer(a.task_id, v)


def cmd_resume(a) -> int:
    def v(w):
        if w and w.get("kind") == "approval":
            print("resume: this task is waiting for approval; use approve or reject", file=sys.stderr)
            return None
        if w and w.get("kind") == "blocked":
            if "interrupted_write" in (w.get("reason") or "") and not a.release_interrupted:
                print("resume: a write was interrupted and may have partly happened. Inspect the worktree, then run "
                      "resume again with --release-interrupted to let it run again.", file=sys.stderr)
                return None
            return {"retry": True, "release_interrupted": a.release_interrupted}
        return {}  # crashed mid-node: re-enter it (value is ignored when nothing is waiting)
    return _answer(a.task_id, v)


def cmd_cancel(a) -> int:
    orch = _orchestrator()
    try:
        w = orch.pending_interrupt(a.task_id)
        if w:
            value = {"approved": False} if w["value"].get("kind") == "approval" else {"cancel": True}
            print(render(orch.resume(a.task_id, value), orch.store))
        else:
            state = orch.store.state(a.task_id).value
            if state in ("PASSED", "FAILED", "CANCELLED"):
                print(f"{a.task_id} is already {state}")
                return 0
            orch.store.request_cancel(a.task_id)
            print(f"cancel requested for {a.task_id}: if a worker is running, it stops within a second; if the "
                  f"process that ran it died, run `groundwork orch resume {a.task_id}` to stop it cleanly")
        return 0
    finally:
        orch.close()


def cmd_allow(a) -> int:
    try:
        print(f"allowed workspace: {workspace.allow(home_dir(), a.path)}")
        return 0
    except workspace.WorkspaceError as e:
        print(f"allow: {e}", file=sys.stderr)
        return 2


def cmd_doctor(_a) -> int:
    ok, detail = preflight()
    print(f"[{'x' if ok else ' '}] subscription login: {detail}")
    try:
        p = routing.load_policy(home_dir())
        print(f"[x] routing policy: {p['_path']}")
    except routing.PolicyError as e:
        ok = False
        print(f"[ ] routing policy: {e}")
    try:
        import langgraph  # noqa: F401
        print("[x] langgraph importable")
    except ImportError:
        ok = False
        print("[ ] langgraph is not installed in this interpreter")
    cfg = workspace.load_config(home_dir())
    print(f"[{'x' if cfg['allowed_workspaces'] else ' '}] allowed workspaces: {cfg['allowed_workspaces'] or 'none yet'}")
    print(f"    state: {home_dir()}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="groundwork orch", description="Groundwork orchestrator (opt-in add-on).")
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("query", help="submit a request")
    q.add_argument("request")
    q.add_argument("--workspace", default=os.getcwd(), help="allowed directory to work in (default: current)")
    q.add_argument("--check", action="append", help="a command that must exit 0 to prove the result (repeatable)")
    q.add_argument("--allow-write", action="store_true",
                   help="let TROUBLESHOOTING/DOCUMENTATION tasks change files (in a worktree, after approval)")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_query)
    s = sub.add_parser("show", help="show a task with its history and sessions")
    s.add_argument("task_id")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_show)
    li = sub.add_parser("list", help="recent tasks")
    li.add_argument("--limit", type=int, default=20)
    li.set_defaults(func=cmd_list)
    for name, fn in (("approve", cmd_approve), ("reject", cmd_reject), ("cancel", cmd_cancel)):
        x = sub.add_parser(name)
        x.add_argument("task_id")
        x.set_defaults(func=fn)
    r = sub.add_parser("resume", help="retry a blocked task or continue one a crash interrupted")
    r.add_argument("task_id")
    r.add_argument("--release-interrupted", action="store_true",
                   help="after inspecting the worktree, allow an interrupted write to run again")
    r.set_defaults(func=cmd_resume)
    al = sub.add_parser("allow", help="add a workspace to the allowlist")
    al.add_argument("path")
    al.set_defaults(func=cmd_allow)
    sub.add_parser("doctor", help="read-only readiness check").set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except TaskBusy as e:
        print(str(e), file=sys.stderr)
        return BUSY_EXIT
    except RuntimeError as e:  # e.g. an orphaned worker that would not stop
        print(f"groundwork orch: {e}", file=sys.stderr)
        return 1
