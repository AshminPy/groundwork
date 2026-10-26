"""Unit tests: adapter, classifier, routing, validation, store. No model calls (a stub binary stands in)."""
import json
import os
import time

import pytest

from groundwork_orchestrator import classifier, routing, validation
from groundwork_orchestrator.claude_adapter import (Failure, WorkerRequest, build_argv, classify_error, preflight,
                                                    run_worker, worker_env)
from groundwork_orchestrator.contract import validate_classification
from groundwork_orchestrator.store import InterruptedWrite, Store


def req(tmp_path, **kw):
    base = dict(prompt="hi", cwd=str(tmp_path), model="haiku", effort="low", tools=["Read"], timeout_s=30)
    base.update(kw)
    return WorkerRequest(**base)


# ---------------------------------------------------------------- adapter (T06, T07, subscription rules)
def test_argv_is_subscription_safe(tmp_path):
    argv = build_argv(req(tmp_path, json_schema={"type": "object"}), "claude")
    assert argv[:2] == ["claude", "-p"]
    assert "--bare" not in argv and "bypassPermissions" not in " ".join(argv)
    assert "--dangerously-skip-permissions" not in argv
    assert argv[argv.index("--permission-prompts") + 1] == "none"
    assert "hi" not in argv  # the prompt goes on stdin, never argv
    assert "--session-id" in argv and "--resume" not in argv
    resumed = build_argv(req(tmp_path, resume=True, session_id="abc"), "claude")
    assert resumed[resumed.index("--resume") + 1] == "abc" and "--session-id" not in resumed


def test_env_scrub_removes_api_billing():
    env = worker_env({"ANTHROPIC_API_KEY": "x", "ANTHROPIC_AUTH_TOKEN": "y", "CLAUDE_CODE_USE_BEDROCK": "1",
                      "PATH": "/bin"})
    assert env == {"PATH": "/bin"}


def test_worker_never_sees_api_key(fake, tmp_path):
    fake.plan([{"result": {"x": 1}}])
    r = run_worker(req(tmp_path, json_schema={"type": "object"}))
    assert r.ok and r.structured == {"x": 1}
    assert os.environ["ANTHROPIC_API_KEY"]  # set in the parent by the fixture
    assert fake.calls()[0]["env_api_key"] is False
    assert fake.calls()[0]["stdin"] == "hi"


def test_preflight_requires_claude_ai_login(fake, monkeypatch):
    assert preflight()[0] is True
    monkeypatch.setenv("FAKE_CLAUDE_AUTH", json.dumps({"loggedIn": True, "authMethod": "apiKey",
                                                       "apiProvider": "firstParty"}))
    ok, detail = preflight()
    assert not ok and "apiKey" in detail
    monkeypatch.setenv("FAKE_CLAUDE_AUTH", json.dumps({"loggedIn": False}))
    assert preflight()[0] is False


@pytest.mark.parametrize("text,failure", [
    ("Claude AI usage limit reached|1761400000", Failure.QUOTA),
    ("api_retry error=rate_limit", Failure.QUOTA),
    ("Not logged in · Please run /login", Failure.AUTH),
    ("model_not_found: claude-x", Failure.MODEL),
    ("something else broke", Failure.PROCESS),
])
def test_error_classes(text, failure):
    assert classify_error(text) is failure


def test_quota_result_is_quota_not_success(fake, tmp_path):
    fake.plan([{"is_error": True, "subtype": "error_during_execution", "text": "You've hit your usage limit"}])
    r = run_worker(req(tmp_path))
    assert not r.ok and r.failure is Failure.QUOTA and not r.failure.repairable


def test_process_failure_and_malformed(fake, tmp_path):
    fake.plan([{"raw": "not json", "exit": 1, "stderr": "boom"}])
    r = run_worker(req(tmp_path))
    assert not r.ok and r.failure is Failure.PROCESS and r.exit_code == 1 and "boom" in r.stderr_tail
    fake.plan([{"raw": "not json", "exit": 0}])
    assert run_worker(req(tmp_path)).failure is Failure.MALFORMED
    fake.plan([{"text": "done"}])  # exit 0, valid result, but the required structured output is missing
    r = run_worker(req(tmp_path, json_schema={"type": "object"}))
    assert not r.ok and r.failure is Failure.MALFORMED


def test_timeout_kills_the_worker_group(fake, tmp_path):
    fake.plan([{"sleep": 60}])
    t = time.monotonic()
    r = run_worker(req(tmp_path, timeout_s=1))
    assert r.failure is Failure.TIMEOUT and time.monotonic() - t < 15
    pid = fake.calls()[0]["pid"]
    time.sleep(0.3)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_cancel_stops_the_worker(fake, tmp_path):
    fake.plan([{"sleep": 60}])
    r = run_worker(req(tmp_path), cancel=lambda: True)
    assert r.failure is Failure.CANCELLED


# ---------------------------------------------------------------- classifier (T01-T05)
@pytest.mark.parametrize("text,cat", [
    ("How does the session snapshot hook work?", "QUESTION"),
    ("Explain the architecture of this repository", "QUESTION"),
    ("Investigate why our GitHub Actions ARC runners stopped working", "TROUBLESHOOTING"),
    ("The test suite fails with a traceback in app.py", "TROUBLESHOOTING"),
    ("Implement a --verbose flag for the CLI", "PROJECT"),
    ("Write documentation for the routines command", "DOCUMENTATION"),
    ("Update the README with install steps", "DOCUMENTATION"),
    ("Write documentation for the add function", "DOCUMENTATION"),
    ("Explain the repo and write a README for it", "DOCUMENTATION"),
])
def test_rule_classification(text, cat):
    c = classifier.rule_classify(text)
    assert c is not None and c["category"] == cat and c["method"] == "rules"


@pytest.mark.parametrize("text", ["Explain the CLI and add a --verbose flag", "hello", "terraform"])
def test_ambiguous_goes_to_model(text):
    assert classifier.rule_classify(text) is None


def test_risk():
    assert classifier.rule_classify("Implement terraform for the production VPC")["risk"] == "high"
    assert classifier.rule_classify("How does the snapshot hook work?")["risk"] == "low"
    assert classifier.rule_classify("How does the snapshot hook work?", ledger_level="high")["risk"] == "high"


def test_classification_schema_validation():
    assert validate_classification({"category": "QUESTION", "risk": "low", "reasoning": "r"}) == []
    assert validate_classification({"category": "BANANA", "risk": "low", "reasoning": "r"})
    assert validate_classification({"category": "QUESTION", "risk": "huge", "reasoning": ""})
    assert validate_classification({"category": "QUESTION", "risk": "low", "reasoning": "r", "run": "rm -rf /"})
    assert validate_classification(None)


# ---------------------------------------------------------------- routing (T17)
def test_default_policy_matches_brief(tmp_path):
    p = routing.load_policy(tmp_path)
    assert routing.choose(p, "classifier")[ "model"] == "haiku" and routing.choose(p, "classifier")["effort"] == "low"
    assert routing.choose(p, "investigate")["model"] == "opus"
    assert routing.role_for("implement", "high") == "implement_complex"
    assert routing.choose(p, routing.role_for("implement", "medium"))["model"] == "sonnet"
    assert "policy routing.json" in routing.choose(p, "answer")["reason"]


def test_policy_override_and_rejection(tmp_path):
    pol = json.loads(routing.DEFAULT_POLICY.read_text())
    pol["roles"]["answer"]["model"] = "opus"
    (tmp_path / "routing.json").write_text(json.dumps(pol))
    assert routing.choose(routing.load_policy(tmp_path), "answer")["model"] == "opus"
    pol["roles"]["answer"]["model"] = "gpt-9"
    (tmp_path / "routing.json").write_text(json.dumps(pol))
    with pytest.raises(routing.PolicyError):
        routing.load_policy(tmp_path)


# ---------------------------------------------------------------- validation
def test_checks_and_sources(repo):
    r = validation.run_check("python3 check.py", str(repo))
    assert r["ok"] is False and "returned -1" in r["output_tail"]
    assert validation.run_check("definitely-not-a-command", str(repo))["exit_code"] == 127
    assert validation.missing_sources(["app.py:1", "README.md", "nope.py", "../etc/passwd", "https://x.y"],
                                      str(repo)) == ["nope.py", "../etc/passwd"]


def test_fingerprint_detects_changes(repo):
    a = validation.fingerprint(str(repo))
    (repo / "app.py").write_text("x = 1\n")
    b = validation.fingerprint(str(repo))
    (repo / "new.txt").write_text("y")
    c = validation.fingerprint(str(repo))
    assert len({a, b, c}) == 3


def test_scope_violations():
    assert validation.scope_violations(["app.py", ".claude/settings.json", ".github/workflows/ci.yml", ".git/HEAD"]) \
        == [".claude/settings.json", ".github/workflows/ci.yml", ".git/HEAD"]


# ---------------------------------------------------------------- store idempotency (T12 building block)
def test_run_op_idempotent(tmp_path):
    s = Store(tmp_path)
    s.create_task({"task_id": "T1", "request": "r", "workspace": str(tmp_path)})
    calls = []
    assert s.run_op("T1", "k", True, lambda op: calls.append(op) or {"ok": True, "v": 1}) == {"ok": True, "v": 1}
    assert s.run_op("T1", "k", True, lambda op: calls.append(op) or {"ok": True, "v": 2}) == {"ok": True, "v": 1}
    assert len(calls) == 1
    # a failed op runs again on retry
    s.run_op("T1", "f", True, lambda op: {"ok": False})
    assert s.run_op("T1", "f", True, lambda op: {"ok": True, "v": 3})["v"] == 3


def test_interrupted_side_effect_is_not_repeated(tmp_path):
    s = Store(tmp_path)
    s.create_task({"task_id": "T1", "request": "r", "workspace": str(tmp_path)})

    def crash(op):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        s.run_op("T1", "w", True, crash)
    with pytest.raises(InterruptedWrite):
        s.run_op("T1", "w", True, lambda op: {"ok": True})
    assert s.release_interrupted("T1") == ["T1:w"]
    assert s.run_op("T1", "w", True, lambda op: {"ok": True, "again": True})["again"]
    with pytest.raises(KeyboardInterrupt):  # a read-only op that never finished simply runs again
        s.run_op("T1", "r", False, crash)
    assert s.run_op("T1", "r", False, lambda op: {"ok": True})["ok"]


# ---------------------------------------------------------------- independent-review fixes (2026-10-25)
def test_checks_get_no_secrets(repo, monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    monkeypatch.setenv("GITHUB_TOKEN", "y")
    probe = ("python3 -c \"import os, sys; bad = [k for k in ('ANTHROPIC_API_KEY', 'AWS_SECRET_ACCESS_KEY', "
             "'GITHUB_TOKEN') if k in os.environ]; print(bad); sys.exit(1 if bad else 0)\"")
    r = validation.run_check(probe, str(repo))
    assert r["ok"], r["output_tail"]
    assert validation.check_env({"PATH": "/bin", "MY_API_KEY": "k"}) == {"PATH": "/bin", "GIT_TERMINAL_PROMPT": "0"}


def test_check_timeout_kills_its_children(repo):
    r = validation.run_check("sh -c 'sleep 60 & sleep 60'", str(repo), timeout_s=1)
    assert r["exit_code"] is None and "did not finish" in r["output_tail"]


def test_changed_files_sees_commits_and_ignored(repo):
    from conftest import git
    base = git(repo, "rev-parse", "HEAD").strip()
    (repo / "new.py").write_text("x = 1\n")
    git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "add", "new.py")
    git(repo, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "worker commit")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "x.pyc").write_text("")
    ch = validation.changed_files(str(repo), base)
    assert "new.py" in ch["files"] and len(ch["commits"]) == 1 and "__pycache__/x.pyc" in ch["ignored"]
    assert validation.ignored_violations(ch["ignored"]) == []
    assert validation.ignored_violations([".claude/settings.local.json"]) == [".claude/settings.local.json"]


def test_scope_casefold_and_symlink_escape(repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "link").symlink_to(outside)
    assert validation.scope_violations([".Claude/x", "CLAUDE.md", "docs/claude.md", "link/f.txt", "ok.py"],
                                       str(repo)) == [".Claude/x", "CLAUDE.md", "docs/claude.md", "link/f.txt"]


def test_a_directory_is_not_a_source(repo):
    assert validation.missing_sources([".", "calc"], str(repo)) == [".", "calc"]


def test_cli_refuses_a_check_with_a_comma(home):
    from groundwork_orchestrator import cli
    os.environ["GROUNDWORK_ORCH_HOME"] = str(home)
    try:
        assert cli.main(["query", "How does it work?", "--check", "python3 -c 'print(1,2)'"]) == 2
    finally:
        del os.environ["GROUNDWORK_ORCH_HOME"]


def test_check_related_handles_subdirs_and_prefixes():
    assert validation.check_related(["sub/check.py", "app.py"], ["python3 check.py"], "sub") == ["sub/check.py"]
    assert validation.check_related(["../x"], ["python3 ./../x"]) == ["../x"]  # a real ./ prefix, not stripped chars
    assert validation.check_related(["tests/test_a.py", "Makefile"], ["make"]) == ["tests/test_a.py", "Makefile"]


def test_stop_group_waits_for_every_member():
    import subprocess
    from groundwork_orchestrator.store import group_alive, stop_group
    # the leader exits on SIGTERM; its child ignores SIGTERM and must still be killed
    p = subprocess.Popen(["sh", "-c", "(trap '' TERM; sleep 60) & trap 'exit 0' TERM; sleep 60 & wait"],
                         start_new_session=True)
    time.sleep(0.5)
    stop_group(p.pid, grace_s=2)
    p.wait(timeout=5)
    assert not group_alive(p.pid)


# ---------------------------------------------------------------- change requests vs questions (M2 classifier fix)
CITE = " Cite the files (with line numbers) that support each part of your answer."


@pytest.mark.parametrize("text", [
    # The two M1 benchmark questions PR #62 misrouted to PROJECT because "support" is a change keyword.
    "We need a nightly export of about 50,000 invoices. Given the documented limits of the PayAPI version this "
    "repository uses and the existing client, should we use offset pagination or cursor pagination? Give a decision "
    "and the evidence." + CITE,
    "As the code is today, is it safe for create_refund to be retried automatically on a 503? Start with yes or no, "
    "then give the decision and the evidence." + CITE,
    "Which HTTP status codes does this client retry on?" + CITE,
    "Should we add retries to create_refund?",
    "Does the client support cursor pagination?",
])
def test_questions_that_mention_change_words_stay_questions(text):
    c = classifier.rule_classify(text)
    assert c is not None and c["category"] == "QUESTION", (classifier.scores(text), c)


@pytest.mark.parametrize("text", [
    "Add retries to create_refund.",
    "Please refactor the client into smaller modules",
    "Can you add a --dry-run flag to the CLI?",
    "We need you to support cursor pagination in list_invoices.",
    "Read the client and then replace offset pagination with cursor pagination.",
    "Context: the export is slow\nAdd cursor pagination to list_invoices",
])
def test_requested_changes_are_projects(text):
    c = classifier.rule_classify(text)
    assert c is not None and c["category"] == "PROJECT", (classifier.scores(text), c)


@pytest.mark.parametrize("text,cat", [
    ("According to the vendored PayAPI documentation for the API version this repository uses, what is the maximum "
     "page size when listing invoices?" + CITE, "QUESTION"),
    ("What does the README say about installation?", "QUESTION"),
    ("Document each public function in payapi/client.py with a one-line description.", "DOCUMENTATION"),
    ("Write a short 'Configuration' section for the README.", "DOCUMENTATION"),
])
def test_documentation_means_a_request_to_write_docs(text, cat):
    c = classifier.rule_classify(text)
    assert c is not None and c["category"] == cat, (classifier.scores(text), c)


@pytest.mark.parametrize("text", ["Tell me how dict.update works", "How does dict.update handle duplicate keys?"])
def test_method_names_are_not_change_requests(text):
    assert classifier.scores(text)["PROJECT"] == 0
