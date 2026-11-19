#!/usr/bin/env python3
"""Regression cases for scope control (openspec/changes/harden-autonomy-evidence-review).

Unrelated discoveries are recorded with `groundwork task note`; status and completion warn about changed files the
plan never names and TODOs added since the task started. Nothing here ever blocks.
Run directly: python3 tests/test_scope_control.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS = REPO_ROOT / "hooks" / "groundwork_tasks.py"
sys.path.insert(0, str(REPO_ROOT / "hooks"))
import groundwork_tasks as gt  # noqa: E402

PASS = FAIL = 0
_FAILURES: list[str] = []
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        _FAILURES.append(f"{name}  {detail}")
        print(f"  FAIL {name}  {detail}")


def git(repo: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}).stdout


def cli(repo: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["python3", str(TASKS), *args], cwd=repo, capture_output=True, text=True, timeout=30,
                          env={**os.environ, **GIT_ENV})


def setup(tmp: Path) -> tuple[Path, dict]:
    repo = tmp / "repo"
    (repo / "hooks").mkdir(parents=True)
    (repo / "hooks" / "app.py").write_text("x = 1\n")
    (repo / "hooks" / "legacy.py").write_text("# TODO: an old note nobody asked about\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text("guide\n")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    change = repo / "openspec" / "changes" / "gw-1-fix-app"
    change.mkdir(parents=True)
    (change / "tasks.md").write_text("- [ ] Fix the parser in `hooks/app.py`\n")
    task = {"schema": gt.SCHEMA, "key": "GW-1", "title": "fix app", "mission": "fix the parser in app.py",
            "tier": gt.MATERIAL, "state": gt.OPEN, "change": "gw-1-fix-app", "created_at": gt.now(), "blockers": [],
            "base_commit": git(repo, "rev-parse", "HEAD").strip(), "evidence": {}}
    gt.save_task(gt.repo_root(repo), task)
    return repo, task


def test_scope_control() -> None:
    print("scope control — record discoveries, warn about drift, never block")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")
        repo, task = setup(tmp)
        root = gt.repo_root(repo)  # the resolved path the CLI also uses (/var vs /private/var on macOS)

        (repo / "hooks" / "app.py").write_text("x = 2\n")
        r = gt.scope_report(root, task)
        check("planned change only -> no warning", r["outside_plan"] == [] and r["new_todos"] == [], r)
        check("a TODO that existed before the task is not reported (stale TODO left alone)",
              not any("legacy.py" in t for t in r["new_todos"]), r)

        # Unrelated discovery: recorded as a note, no task is created, no file changes.
        r = cli(repo, "note", "GW-1", "docs/guide.md has a stale TODO about v1")
        tasks = [t["key"] for t in gt.load_tasks(root)]
        check("`task note` records the discovery", r.returncode == 0 and "note recorded" in r.stdout, r.stdout + r.stderr)
        check("no new task is created by a note", tasks == ["GW-1"], tasks)
        shown = cli(repo, "show", "GW-1").stdout
        check("the note is shown with the task", "docs/guide.md has a stale TODO" in shown, shown)
        check("note on an unknown task -> error", cli(repo, "note", "GW-9", "x").returncode == 1)

        # Unrelated change: an edit to a file the plan never names, and a new TODO.
        (repo / "docs" / "guide.md").write_text("guide\nTODO: rewrite this later\n")
        r = gt.scope_report(root, task)
        check("unrelated file change -> listed", r["outside_plan"] == ["docs/guide.md"], r)
        check("TODO added since the task started -> listed with its line", r["new_todos"] == ["docs/guide.md:2"], r)
        shown = cli(repo, "show", "GW-1").stdout
        check("status shows the scope warning and how to record it", "scope warning" in shown and "note GW-1" in shown, shown)

        # A new untracked file with a TODO is also seen.
        (repo / "hooks" / "extra.py").write_text("pass\n# FIXME later\n")
        r = gt.scope_report(root, task)
        check("untracked file outside the plan -> listed", "hooks/extra.py" in r["outside_plan"], r)
        check("TODO in an untracked file -> listed", "hooks/extra.py:2" in r["new_todos"], r)

        # Blocking dependency: a fix needed to unblock the task is legitimate once the plan says why.
        gt.set_blocker(root, "GW-1", "the parser needs hooks/extra.py first")
        (repo / "openspec" / "changes" / "gw-1-fix-app" / "tasks.md").write_text(
            "- [x] Fix the parser in `hooks/app.py`\n- [x] Unblock: add `hooks/extra.py` (the parser imports it)\n")
        (repo / "hooks" / "extra.py").write_text("pass\n")
        (repo / "docs" / "guide.md").write_text("guide\n")
        r = gt.scope_report(root, task)
        check("blocker fix named in the plan -> no warning", r["outside_plan"] == [] and r["new_todos"] == [], r)
        check("plan edits under openspec/ are never scope drift", not any(p.startswith("openspec/") for p in r["outside_plan"]))

        # Warnings never block completion: a STANDARD task with drift completes.
        std = {"schema": gt.SCHEMA, "key": "GW-2", "title": "tweak", "mission": "tweak app", "tier": gt.STANDARD,
               "state": gt.OPEN, "created_at": gt.now(), "blockers": [], "evidence": {},
               "base_commit": git(repo, "rev-parse", "HEAD").strip()}
        gt.save_task(root, std)
        (repo / "hooks" / "legacy.py").write_text("# TODO: an old note nobody asked about\n# TODO: and a new one\n")
        ok, msg = gt.complete(root, "GW-2")
        check("drift is a warning, never a refusal", ok and "TODO/FIXME added" in msg and "hooks/legacy.py:2" in msg, msg)
        del os.environ["CLAUDE_CONFIG_DIR"]
    assert not _FAILURES, "\n".join(_FAILURES)


if __name__ == "__main__":
    try:
        test_scope_control()
    except AssertionError:
        pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
