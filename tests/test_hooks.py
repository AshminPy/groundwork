#!/usr/bin/env python3
"""Unit tests for Groundwork's hooks — no Claude Code or network required.

Run: python3 tests/test_hooks.py
Each case constructs the exact JSON payload Claude Code sends to a hook on stdin
and checks the hook's stdout. These are the same cases the hooks were built and
fixed against — see docs/VALIDATION.md for how they connect to real, live tests.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEW_HOOK = REPO_ROOT / "hooks" / "require_material_review.py"
PUSH_HOOK = REPO_ROOT / "hooks" / "block_protected_push.py"

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}  {detail}")


def run_hook(hook: Path, payload: dict) -> str:
    result = subprocess.run(
        ["python3", str(hook)],
        input=json.dumps(payload),
        capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip()


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True,
                    env={"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t.com",
                         "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t.com"})


def make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "openspec" / "changes" / "add-thing").mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    return repo


def write_tasks(repo: Path, done: bool, change: str = "add-thing") -> None:
    box = "[x]" if done else "[ ]"
    (repo / "openspec" / "changes" / change / "tasks.md").write_text(f"- [x] first\n- {box} second\n")


def write_transcript(tmp: Path, name: str, tool_use: dict | None) -> Path:
    path = tmp / name
    lines = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash",
              "input": {"command": "echo hi"}}]}}]
    if tool_use:
        lines.append({"type": "assistant", "message": {"content": [tool_use]}})
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    return path


def test_review_gate() -> None:
    print("require_material_review.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        repo = make_repo(tmp)
        empty_transcript = write_transcript(tmp, "empty.jsonl", None)
        review_task = {"type": "tool_use", "name": "Task", "input": {"subagent_type": "code-reviewer"}}
        review_skill = {"type": "tool_use", "name": "Skill", "input": {"skill": "ecc:orch-review"}}

        # 1. no openspec dir at all -> allow
        no_openspec = tmp / "no-openspec"
        no_openspec.mkdir()
        out = run_hook(REVIEW_HOOK, {"cwd": str(no_openspec), "transcript_path": str(empty_transcript)})
        check("no openspec/ dir -> allow", out == "", out)

        # 2. incomplete tasks -> allow
        write_tasks(repo, done=False)
        out = run_hook(REVIEW_HOOK, {"cwd": str(repo), "transcript_path": str(empty_transcript)})
        check("incomplete tasks -> allow", out == "", out)

        # 3. complete, uncommitted, no review in transcript -> BLOCK
        write_tasks(repo, done=True)
        out = run_hook(REVIEW_HOOK, {"cwd": str(repo), "transcript_path": str(empty_transcript)})
        check("complete + no review -> block", '"decision": "block"' in out and "add-thing" in out, out)

        # 4. complete, Task-shaped reviewer in transcript -> allow
        t = write_transcript(tmp, "with-task-review.jsonl", review_task)
        out = run_hook(REVIEW_HOOK, {"cwd": str(repo), "transcript_path": str(t)})
        check("complete + Task reviewer -> allow", out == "", out)

        # 5. complete, Skill-shaped reviewer in transcript -> allow
        t = write_transcript(tmp, "with-skill-review.jsonl", review_skill)
        out = run_hook(REVIEW_HOOK, {"cwd": str(repo), "transcript_path": str(t)})
        check("complete + Skill reviewer -> allow", out == "", out)

        # 6. already committed (not this session's work) -> allow
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "commit the change")
        out = run_hook(REVIEW_HOOK, {"cwd": str(repo), "transcript_path": str(empty_transcript)})
        check("already committed -> allow", out == "", out)

        # 7. malformed hook input -> fail open
        result = subprocess.run(["python3", str(REVIEW_HOOK)], input="not json",
                                 capture_output=True, text=True, timeout=15)
        check("malformed input -> fail open", result.stdout.strip() == "", result.stdout)

        # 8. no git repo -> fail open
        no_git = tmp / "no-git"
        (no_git / "openspec" / "changes" / "x").mkdir(parents=True)
        (no_git / "openspec" / "changes" / "x" / "tasks.md").write_text("- [x] done\n")
        out = run_hook(REVIEW_HOOK, {"cwd": str(no_git), "transcript_path": str(empty_transcript)})
        check("no git repo -> fail open", out == "", out)

        # 9. two changes, only the fresh+complete one blocks
        write_tasks(repo, done=True, change="add-thing")  # already committed at step 6, so inert
        (repo / "openspec" / "changes" / "second-thing").mkdir(parents=True)
        write_tasks(repo, done=True, change="second-thing")
        out = run_hook(REVIEW_HOOK, {"cwd": str(repo), "transcript_path": str(empty_transcript)})
        check("mixed: blocks only the fresh change", "second-thing" in out and out.count("decision") == 1, out)


def test_push_guard() -> None:
    print("block_protected_push.py")
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "init")

        cases = [
            ("git push origin main", True),
            ("git push origin feature/x", False),
            ("git push", True),  # current branch is main
            ("git push --force origin feature/x", True),
            ("git push origin HEAD:main", True),
            ('echo "git push origin main"', False),  # quoted text, not a real push
            ("git status && git push -u origin fix/abc", False),
        ]
        for cmd, expect_denied in cases:
            out = run_hook(PUSH_HOOK, {"tool_name": "Bash", "cwd": str(repo), "tool_input": {"command": cmd}})
            denied = '"permissionDecision": "deny"' in out
            check(f"{cmd!r} -> {'deny' if expect_denied else 'allow'}", denied == expect_denied, out)


if __name__ == "__main__":
    if shutil.which("git") is None:
        print("git not found on PATH — cannot run these tests")
        sys.exit(1)
    test_review_gate()
    test_push_guard()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
