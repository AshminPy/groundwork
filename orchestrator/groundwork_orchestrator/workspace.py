"""Workspace allowlist, isolated git worktrees for writes, and the bridge to Groundwork's existing task ledger."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path


class WorkspaceError(Exception):
    pass


def config_path(home: Path) -> Path:
    return Path(home) / "config.json"


def load_config(home: Path) -> dict:
    try:
        cfg = json.loads(config_path(home).read_text())
    except (OSError, json.JSONDecodeError):
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    cfg.setdefault("allowed_workspaces", [])
    return cfg


def allow(home: Path, path: str) -> str:
    real = os.path.realpath(path)
    if not os.path.isdir(real):
        raise WorkspaceError(f"{path} is not a directory")
    cfg = load_config(home)
    if real not in cfg["allowed_workspaces"]:
        cfg["allowed_workspaces"].append(real)
    p = config_path(home)
    Path(home).mkdir(parents=True, exist_ok=True, mode=0o700)
    p.write_text(json.dumps(cfg, indent=2) + "\n")
    os.chmod(p, 0o600)
    return real


def check_allowed(home: Path, path: str) -> str:
    real = os.path.realpath(path)
    for root in load_config(home)["allowed_workspaces"]:
        if real == root or real.startswith(root.rstrip("/") + "/"):
            return real
    raise WorkspaceError(f"{real} is not an allowed workspace; allow it first with: groundwork orch allow {real}")


def git_root(path: str) -> str | None:
    r = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=30)
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 else None


def ensure_worktree(home: Path, workspace: str, task_id: str) -> dict:
    """Create (or find) the task's worktree on branch gw/<task_id>, based on the workspace's HEAD. Idempotent."""
    root = git_root(workspace)
    if not root:
        raise WorkspaceError(f"{workspace} is not a git repository; writes need an isolated git worktree")
    wt = Path(home) / "worktrees" / task_id
    branch = f"gw/{task_id}"
    if wt.exists():
        if git_root(str(wt)) != os.path.realpath(wt):
            raise WorkspaceError(f"{wt} exists but is not a git worktree")
        # Only reached when worktree creation is re-run after a crash, before any worker ran in it.
        head = subprocess.run(["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=30).stdout.strip()
        return {"path": os.path.realpath(wt), "branch": branch, "repo": root, "base": head, "created": False}
    wt.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "-C", root, "worktree", "add", "-b", branch, str(wt), "HEAD"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise WorkspaceError(f"git worktree add failed: {(r.stderr or r.stdout).strip()}")
    head = subprocess.run(["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True,
                          timeout=30).stdout.strip()
    return {"path": os.path.realpath(wt), "branch": branch, "repo": root, "base": head, "created": True}


def subpath_in_worktree(workspace: str, worktree: dict) -> str:
    """The workspace may be a sub-directory of its repository; the worker works in the same place in the worktree."""
    rel = os.path.relpath(os.path.realpath(workspace), worktree["repo"])
    return str(Path(worktree["path"]) / rel) if rel != "." else worktree["path"]


# ------------------------------------------------------------------ the existing Groundwork task ledger
def _ledger_candidates() -> list[Path]:
    env = os.environ.get("GROUNDWORK_HOOKS_DIR")
    claude_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))
    repo_hooks = Path(__file__).resolve().parents[2] / "hooks"
    return [Path(p) for p in (env,) if p] + [repo_hooks, claude_dir / "hooks"]


def load_ledger():
    """hooks/groundwork_tasks.py, imported by path, or None when Groundwork's ledger is not available."""
    for d in _ledger_candidates():
        f = d / "groundwork_tasks.py"
        if f.is_file():
            spec = importlib.util.spec_from_file_location("groundwork_tasks", f)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
            except Exception:
                continue
            return mod
    return None


def ledger_intake(workspace: str, request: str) -> dict:
    """Record the task the way an interactive session would, once, so worker prompts attach to it instead of
    creating duplicates. Never fatal: the orchestrator works without the ledger."""
    gt = load_ledger()
    if gt is None:
        return {"available": False}
    try:
        res = gt.intake(workspace, request, session_id="groundwork-orchestrator")
        cls = gt.classify(request)
    except Exception as e:  # the ledger must never break a task
        return {"available": True, "error": str(e)}
    keys = [t["key"] for t in (res or {}).get("tasks", [])]
    return {"available": True, "action": (res or {}).get("action"), "keys": keys,
            "level": (cls or {}).get("level"), "tier": (cls or {}).get("tier")}
