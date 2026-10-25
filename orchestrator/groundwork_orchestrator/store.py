"""Durable task state: tasks, state transitions, idempotent operations and worker sessions (SQLite, stdlib).

LangGraph's checkpoints say *where* a workflow is; this store says *what happened*: every state change with its
reason, every side-effecting operation with a durable id, and every `claude -p` process with its session id.
Each transition and session end is also appended to events.jsonl for dashboards.
"""
from __future__ import annotations

import fcntl
import json
import os
import signal
import sqlite3
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .contract import State

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, request TEXT NOT NULL,
  workspace TEXT NOT NULL, state TEXT NOT NULL, contract TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS transitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, ts TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL,
  reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations (
  op_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, kind TEXT NOT NULL, side_effect INTEGER NOT NULL, status TEXT NOT NULL,
  started_at TEXT NOT NULL, ended_at TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, op_id TEXT NOT NULL, session_id TEXT NOT NULL,
  role TEXT NOT NULL, model TEXT NOT NULL, effort TEXT NOT NULL, reason TEXT, pid INTEGER, owner_pid INTEGER,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL, ended_at TEXT, exit_code INTEGER, duration_s REAL, failure TEXT, models TEXT,
  usage TEXT, cost_estimate_usd REAL);
"""


class InterruptedWrite(Exception):
    """A side-effecting operation started earlier and never finished: running it again could repeat the effect."""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_task_id() -> str:
    return "T" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def looks_like_claude(pid: int) -> bool:
    """True when the live process with this pid is a Claude Code CLI (or the test stand-in), per `ps`."""
    try:
        cmd = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "claude" in cmd.lower()


def group_alive(pgid: int) -> bool:
    """False when no member of the group can still be signalled. Callers only pass groups they started or verified
    as claude, so EPERM is the macOS answer for a group of exiting zombies (seen in testing), not another user."""
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def stop_group(pid: int, grace_s: float = 10) -> None:
    """SIGTERM the whole process group, then SIGKILL until no member is left (not only the leader)."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        deadline = time.monotonic() + grace_s
        while time.monotonic() < deadline:
            if not group_alive(pid):
                return
            time.sleep(0.1)


class TaskBusy(Exception):
    """Another orchestrator process is running this task."""


@contextmanager
def task_lock(home: Path, task_id: str):
    """One process per task at a time (start, resume, approve, cancel). Released automatically if the process dies."""
    d = Path(home) / "locks"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(d / f"{task_id}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise TaskBusy(f"task {task_id} is being run by another groundwork process; try again when it finishes")
        yield
    finally:
        os.close(fd)


class Store:
    def __init__(self, home: Path):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.home / "state.db"
        self.events_path = self.home / "events.jsonl"
        self.conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        os.chmod(self.db_path, 0o600)

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ events
    def emit(self, event: str, task_id: str, **fields) -> None:
        if os.environ.get("GROUNDWORK_ORCH_TELEMETRY", "").lower() == "off":
            return
        rec = {"schema": 1, "ts": now(), "event": event, "task_id": task_id, **fields}
        fd = os.open(self.events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    # ------------------------------------------------------------------ tasks
    def create_task(self, contract: dict) -> None:
        t = now()
        with self.conn:
            self.conn.execute("INSERT INTO tasks (id, created_at, updated_at, request, workspace, state, contract) "
                              "VALUES (?,?,?,?,?,?,?)", (contract["task_id"], t, t, contract["request"],
                                                         contract["workspace"], State.CREATED.value, json.dumps(contract)))
            self.conn.execute("INSERT INTO transitions (task_id, ts, from_state, to_state, reason) VALUES (?,?,?,?,?)",
                              (contract["task_id"], t, None, State.CREATED.value, "request received"))
        self.emit("transition", contract["task_id"], from_state=None, to_state=State.CREATED.value)

    def task(self, task_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["contract"] = json.loads(d["contract"])
        return d

    def contract(self, task_id: str) -> dict:
        t = self.task(task_id)
        if t is None:
            raise KeyError(task_id)
        return t["contract"]

    def update_contract(self, task_id: str, **fields) -> dict:
        with self.conn:
            c = self.contract(task_id)
            c.update(fields)
            self.conn.execute("UPDATE tasks SET contract=?, updated_at=? WHERE id=?", (json.dumps(c), now(), task_id))
        return c

    def state(self, task_id: str) -> State:
        return State(self.task(task_id)["state"])

    def transition(self, task_id: str, to: State, reason: str) -> None:
        with self.conn:
            cur = self.conn.execute("SELECT state FROM tasks WHERE id=?", (task_id,)).fetchone()["state"]
            if cur == to.value:
                return
            t = now()
            self.conn.execute("UPDATE tasks SET state=?, updated_at=? WHERE id=?", (to.value, t, task_id))
            self.conn.execute("INSERT INTO transitions (task_id, ts, from_state, to_state, reason) VALUES (?,?,?,?,?)",
                              (task_id, t, cur, to.value, reason))
        c = self.contract(task_id)
        self.emit("transition", task_id, from_state=cur, to_state=to.value, reason=reason, category=c.get("category"))

    def transitions(self, task_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT ts, from_state, to_state, reason FROM transitions "
                                                   "WHERE task_id=? ORDER BY id", (task_id,))]

    def list_tasks(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute("SELECT id, created_at, state, request, contract FROM tasks ORDER BY created_at DESC "
                                 "LIMIT ?", (limit,))
        out = []
        for r in rows:
            c = json.loads(r["contract"])
            out.append({"id": r["id"], "created_at": r["created_at"], "state": r["state"], "request": r["request"],
                        "category": c.get("category"), "evidence_status": c.get("evidence_status")})
        return out

    def request_cancel(self, task_id: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE tasks SET cancel_requested=1 WHERE id=?", (task_id,))

    def cancel_requested(self, task_id: str) -> bool:
        row = self.conn.execute("SELECT cancel_requested FROM tasks WHERE id=?", (task_id,)).fetchone()
        return bool(row and row["cancel_requested"])

    # ------------------------------------------------------------------ operations (idempotency)
    def op(self, op_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM operations WHERE op_id=?", (op_id,)).fetchone()
        return dict(row) if row else None

    def op_result(self, op_id: str) -> dict:
        op = self.op(op_id)
        if not op or op["result"] is None:
            raise KeyError(f"operation {op_id} has no result")
        return json.loads(op["result"])

    def run_op(self, task_id: str, kind: str, side_effect: bool, fn: Callable[[str], dict]) -> dict:
        """Run `fn(op_id)` at most once successfully per (task, kind).

        - done: return the stored result, never run again (a crash after it finished repeats nothing);
        - failed (fn returned ok=False): the stored result was a failure; running again is what a retry means;
        - started but never ended: a read-only op runs again; a side-effecting op raises InterruptedWrite, because
          its effect may already have happened and the owner must decide (Store.release_interrupted)."""
        op_id = f"{task_id}:{kind}"
        existing = self.op(op_id)
        if existing and existing["status"] == "done":
            return json.loads(existing["result"])
        if existing and existing["status"] == "started":
            self.abandon_sessions(op_id=op_id)
            if existing["side_effect"]:
                raise InterruptedWrite(f"operation {kind} started at {existing['started_at']} and never finished")
        if existing:
            with self.conn:
                self.conn.execute("UPDATE operations SET op_id=? WHERE op_id=?",
                                  (f"{op_id}#{existing['status']}-{int(time.time() * 1000)}", op_id))
        with self.conn:
            self.conn.execute("INSERT INTO operations (op_id, task_id, kind, side_effect, status, started_at) "
                              "VALUES (?,?,?,?,?,?)", (op_id, task_id, kind, int(side_effect), "started", now()))
        result = fn(op_id)
        status = "failed" if isinstance(result, dict) and result.get("ok") is False else "done"
        with self.conn:
            self.conn.execute("UPDATE operations SET status=?, ended_at=?, result=? WHERE op_id=?",
                              (status, now(), json.dumps(result), op_id))
        return result

    def release_interrupted(self, task_id: str) -> list[str]:
        """Owner decision after an InterruptedWrite: keep the record under a new id so the op can run again."""
        rows = self.conn.execute("SELECT op_id FROM operations WHERE task_id=? AND status='started' AND side_effect=1",
                                 (task_id,)).fetchall()
        with self.conn:
            for r in rows:
                self.conn.execute("UPDATE operations SET op_id=?, status='abandoned', ended_at=? WHERE op_id=?",
                                  (f"{r['op_id']}#abandoned-{int(time.time() * 1000)}", now(), r["op_id"]))
        return [r["op_id"] for r in rows]

    def operations(self, task_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT op_id, kind, side_effect, status, started_at, ended_at "
                                                   "FROM operations WHERE task_id=? ORDER BY started_at", (task_id,))]

    # ------------------------------------------------------------------ sessions
    def session_start(self, task_id: str, op_id: str, session_id: str, role: str, model: str, effort: str,
                      reason: str) -> int:
        with self.conn:
            cur = self.conn.execute("INSERT INTO sessions (task_id, op_id, session_id, role, model, effort, reason, "
                                    "owner_pid, status, started_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                    (task_id, op_id, session_id, role, model, effort, reason, os.getpid(), "starting",
                                     now()))
        return cur.lastrowid

    def session_pid(self, row_id: int, pid: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE sessions SET pid=?, status='running' WHERE id=?", (pid, row_id))

    def session_finish(self, row_id: int, result: dict) -> None:
        status = "ok" if result["ok"] else "failed"
        with self.conn:
            self.conn.execute(
                "UPDATE sessions SET status=?, ended_at=?, exit_code=?, duration_s=?, failure=?, models=?, usage=?, "
                "cost_estimate_usd=?, session_id=? WHERE id=?",
                (status, now(), result.get("exit_code"), result.get("duration_s"), result.get("failure"),
                 json.dumps(result.get("models") or []), json.dumps(result.get("usage") or {}),
                 result.get("cost_estimate_usd"), result.get("session_id"), row_id))
        row = dict(self.conn.execute("SELECT * FROM sessions WHERE id=?", (row_id,)).fetchone())
        usage = result.get("usage") or {}
        self.emit("session", row["task_id"], role=row["role"], model=row["model"], effort=row["effort"],
                  status=status, failure=row["failure"], duration_s=row["duration_s"],
                  models=result.get("models") or [], cost_estimate_usd=row["cost_estimate_usd"],
                  input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"))

    def abandon_sessions(self, op_id: str | None = None, task_id: str | None = None) -> int:
        """Reconcile sessions still marked running. Called only while this process holds the task lock, so no other
        orchestrator can be driving them: they are orphans. A worker process that is still alive is stopped (SIGTERM,
        then SIGKILL) — but only if it still looks like a claude process, so a recycled pid is never signalled. A
        session is marked abandoned only once its process is confirmed gone; otherwise this raises."""
        q, args = "SELECT id, pid FROM sessions WHERE status IN ('starting','running')", []
        if op_id:
            q, args = q + " AND op_id=?", [op_id]
        elif task_id:
            q, args = q + " AND task_id=?", [task_id]
        n = 0
        for r in self.conn.execute(q, args).fetchall():
            if pid_alive(r["pid"]) and looks_like_claude(r["pid"]):
                stop_group(r["pid"])
                if group_alive(r["pid"]):
                    raise RuntimeError(f"orphaned worker pid {r['pid']} did not stop; stop it yourself, then resume")
            with self.conn:
                self.conn.execute("UPDATE sessions SET status='abandoned', ended_at=? WHERE id=?", (now(), r["id"]))
            n += 1
        return n

    def sessions(self, task_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM sessions WHERE task_id=? ORDER BY id", (task_id,))]
