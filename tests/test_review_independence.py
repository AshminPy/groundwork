#!/usr/bin/env python3
"""Regression cases for review independence (openspec/changes/harden-autonomy-evidence-review).

A review clears the MATERIAL Stop gate only when a reviewer subagent's own result names the current
content fingerprint. Run directly: python3 tests/test_review_independence.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_hooks import (HOOKS, REVIEW_HOOK, check, git, make_repo, repo_fp, run_hook,  # noqa: E402
                        write_review_events, write_tasks)
import test_hooks  # noqa: E402

TASKS = HOOKS / "groundwork_tasks.py"


def approve(fp: str) -> str:
    return f"No blocking issues.\n\nREVIEW RESULT\nVerdict: approve\nMust-fix: 0\nReviewed: {fp}\n"


def gate(repo: Path, transcript: Path) -> str:
    return run_hook(REVIEW_HOOK, {"cwd": str(repo), "transcript_path": str(transcript)})


def test_review_independence() -> None:
    print("review independence — fresh context, bound to the reviewed content")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        repo = make_repo(tmp)
        (repo / "app.py").write_text("print('v1')\n")
        write_tasks(repo, done=True)

        # The author writes its own REVIEW RESULT in its reply text: that is not a review call.
        t = tmp / "self-review.jsonl"
        t.write_text(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": approve(repo_fp(repo))}]}}) + "\n")
        out = gate(repo, t)
        check("author's own REVIEW RESULT text -> block", '"decision": "block"' in out
              and "no independent fresh-context review" in out, out)

        # A subagent review of the current content clears the gate.
        t = write_review_events(tmp, "current.jsonl", [{"kind": "review", "id": "r1", "result": approve(repo_fp(repo))}])
        check("subagent review naming the current fingerprint -> allow", gate(repo, t) == "", gate(repo, t))

        # Ticking task boxes, or archiving, changes only openspec/: the review stays current.
        (repo / "openspec" / "changes" / "add-thing" / "tasks.md").write_text("- [x] first\n- [x] second\n- [x] third\n")
        check("plan-only change after review -> still allow", gate(repo, t) == "", gate(repo, t))

        # Staging or committing without a content change keeps the review current.
        git(repo, "add", "app.py")
        check("staging after review -> still allow", gate(repo, t) == "", gate(repo, t))

        # A code change after the review makes it stale.
        reviewed = repo_fp(repo)
        (repo / "app.py").write_text("print('v2')\n")
        out = gate(repo, t)
        check("code change after review -> block as stale", '"decision": "block"' in out and "stale" in out
              and reviewed in out and repo_fp(repo) in out, out)

        # A fresh review of the new content clears it again.
        t2 = write_review_events(tmp, "rereview.jsonl", [
            {"kind": "review", "id": "r1", "result": approve(reviewed)},
            {"kind": "edit"},
            {"kind": "review", "id": "r2", "result": approve(repo_fp(repo))}])
        check("fresh review after the change -> allow", gate(repo, t2) == "", gate(repo, t2))

        # A malformed or wrong-length fingerprint never matches.
        t3 = write_review_events(tmp, "bad-fp.jsonl", [{"kind": "review", "id": "r1", "result": approve("not-a-hash")}])
        out = gate(repo, t3)
        check("unparseable Reviewed value -> block", '"decision": "block"' in out and "no REVIEW RESULT block" in out, out)

        # A background reviewer: the Agent tool_result only says it launched. Its verdict is in the subagent
        # transcript Claude Code writes under <session>/subagents/, matched by the meta file's toolUseId.
        t4 = write_review_events(tmp, "async.jsonl", [
            {"kind": "review", "id": "toolu_async1", "result": "Async agent launched successfully.\nagentId: a1"}])
        out = gate(repo, t4)
        check("background reviewer still running (no subagent transcript yet) -> block", '"decision": "block"' in out, out)
        sub = t4.with_suffix("") / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-a1.meta.json").write_text(json.dumps({"toolUseId": "toolu_async1", "name": "code-reviewer"}))
        (sub / "agent-a1.jsonl").write_text("\n".join(json.dumps(e) for e in [
            {"type": "user", "message": {"content": "review app.py"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": approve(repo_fp(repo))}]}},
        ]) + "\n")
        check("background reviewer's own transcript names the current fingerprint -> allow", gate(repo, t4) == "", gate(repo, t4))
        (sub / "agent-a1.meta.json").write_text(json.dumps({"toolUseId": "toolu_other", "name": "code-reviewer"}))
        out = gate(repo, t4)
        check("subagent transcript for a different tool call is not used -> block", '"decision": "block"' in out, out)

        # A reviewer that quotes an earlier approval above its own final verdict: the last block decides.
        quoted = approve(repo_fp(repo)) + "\nMy own verdict:\n\nREVIEW RESULT\nVerdict: changes-required\nMust-fix: 2\n" \
            f"Reviewed: {repo_fp(repo)}\n"
        t5 = write_review_events(tmp, "quoted.jsonl", [{"kind": "review", "id": "r1", "result": quoted}])
        out = gate(repo, t5)
        check("quoted earlier approval above a final MUST FIX block -> block on the final one",
              '"decision": "block"' in out and "2 unresolved MUST FIX" in out, out)

        # The fingerprint command is what the block messages point to.
        r = subprocess.run(["python3", str(TASKS), "fingerprint"], cwd=repo, capture_output=True, text=True, timeout=30)
        check("`groundwork task fingerprint` prints fingerprint and head", r.returncode == 0
              and f"fingerprint: {repo_fp(repo)}" in r.stdout and "head: " in r.stdout, r.stdout + r.stderr)
        r = subprocess.run(["python3", str(TASKS), "fingerprint"], cwd=tmp, capture_output=True, text=True, timeout=30)
        check("fingerprint outside a repository -> exit 2", r.returncode == 2, r.stdout + r.stderr)
    test_hooks.finish()


GATE = HOOKS / "groundwork_task_gate.py"
REVIEW_CHECK = HOOKS.parent / "scripts" / "review_check.py"


def commit_fp(repo: Path, rev: str = "HEAD") -> str:
    r = subprocess.run(["python3", str(TASKS), "fingerprint", "--commit", rev], cwd=repo, capture_output=True,
                       text=True, timeout=30)
    return r.stdout.split("fingerprint: ", 1)[1].split()[0]


def pr_gate(repo: Path, transcript: Path, cmd: str, cfg: Path) -> str:
    return run_hook(GATE, {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd},
                           "cwd": str(repo), "transcript_path": str(transcript)}, env={"CLAUDE_CONFIG_DIR": str(cfg)})


def ci_check(repo: Path, body: str) -> subprocess.CompletedProcess:
    import os
    return subprocess.run(["python3", str(REVIEW_CHECK)], cwd=repo, capture_output=True, text=True, timeout=30,
                          env={**os.environ, "PR_BODY": body})


def test_pr_review() -> None:
    print("review independence — pull requests, including committed changes")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfg = tmp / "cfg"
        repo = make_repo(tmp)
        (repo / "app.py").write_text("print('v1')\n")
        write_tasks(repo, done=True)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "v1")

        reviewed = repo_fp(repo)
        check("clean tree: the commit fingerprint equals the working-tree fingerprint", commit_fp(repo) == reviewed)
        none = write_review_events(tmp, "pr-none.jsonl", [{"kind": "bash", "command": "echo work"}])
        out = pr_gate(repo, none, "gh pr create --title t --body b", cfg)
        check("gh pr create with no review -> deny", '"permissionDecision": "deny"' in out
              and "no independent reviewer subagent" in out and reviewed in out, out)
        check("draft PR before the review -> allowed", pr_gate(repo, none, "gh pr create --draft -t t -b b", cfg) == "")
        skill = write_review_events(tmp, "pr-skill.jsonl", [{"kind": "review", "id": "s1", "review_name": "Skill",
                                                               "input": {"skill": "code-review"}, "result": approve(reviewed)}])
        out = pr_gate(repo, skill, "gh pr create -t t -b b", cfg)
        check("gh pr create after an inline Skill review only -> deny", '"permissionDecision": "deny"' in out
              and "inline as a Skill" in out, out)
        good = write_review_events(tmp, "pr-good.jsonl", [{"kind": "review", "id": "r1", "result": approve(reviewed)}])
        check("gh pr create after a review of the commit -> allowed", pr_gate(repo, good, "gh pr create -t t -b b", cfg) == "")
        check("wrapped in cd && ... -> still checked", '"deny"' in pr_gate(tmp, none, f"cd {repo} && gh pr create -t t", cfg))

        # A plan-only commit keeps the review current; a code commit after the review makes it stale.
        (repo / "openspec" / "changes" / "add-thing" / "tasks.md").write_text("- [x] first\n- [x] second\n- [x] third\n")
        git(repo, "commit", "-qam", "plan")
        check("plan-only commit after the review -> still allowed", pr_gate(repo, good, "gh pr create -t t -b b", cfg) == "")
        (repo / "app.py").write_text("print('v2')\n")
        git(repo, "commit", "-qam", "v2")
        out = pr_gate(repo, good, "gh pr create -t t -b b", cfg)
        check("code commit after the review -> deny as stale", '"deny"' in out and "stale" in out
              and reviewed in out and commit_fp(repo) in out, out)
        must = write_review_events(tmp, "pr-must.jsonl", [{"kind": "review", "id": "r2", "result":
                                   "REVIEW RESULT\nVerdict: changes-required\nMust-fix: 1\nReviewed: " + commit_fp(repo)}])
        out = pr_gate(repo, must, "gh pr create -t t -b b", cfg)
        check("review with a MUST FIX -> deny", '"deny"' in out and "1 unresolved MUST FIX" in out, out)
        out = pr_gate(repo, must, "gh pr new --fill", cfg)
        check("gh pr new (the built-in alias) is checked too", '"deny"' in out and "1 unresolved MUST FIX" in out, out)
        check("other gh commands are not affected", pr_gate(repo, none, "gh pr list", cfg) == "")

        # The CI check reads the review from the PR description and the fingerprint from the PR head commit.
        r = ci_check(repo, "Summary.\n\n" + approve(commit_fp(repo)))
        check("CI: description names the head fingerprint -> pass", r.returncode == 0, r.stdout + r.stderr)
        r = ci_check(repo, "Summary.\n\n" + approve(reviewed))
        check("CI: description names an older fingerprint -> fail as changed after review", r.returncode == 1
              and "changed after the review" in r.stderr, r.stderr)
        r = ci_check(repo, "Summary only.")
        check("CI: no REVIEW RESULT block -> fail with the fix", r.returncode == 1 and commit_fp(repo) in r.stderr, r.stderr)
        r = ci_check(repo, "REVIEW RESULT\nVerdict: changes-required\nMust-fix: 2\nReviewed: " + commit_fp(repo))
        check("CI: MUST FIX in the recorded review -> fail", r.returncode == 1 and "2 unresolved" in r.stderr, r.stderr)
    test_hooks.finish()


if __name__ == "__main__":
    for fn in (test_review_independence, test_pr_review):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{test_hooks.PASS} passed, {test_hooks.FAIL} failed")
    sys.exit(1 if test_hooks.FAIL else 0)
