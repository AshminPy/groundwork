#!/usr/bin/env python3
"""Deterministic checks for scripts/groundwork_statusline.py (Groundwork 2.1) — the statusLine's
LIVE / LAST-COMPLETED-TURN / CACHED / UNAVAILABLE data-source contract, session isolation (never
leaking one session_id's last-turn state into another's render), cache-only Integration Catalog
readiness (never a live probe), fail-safe behavior on malformed/missing state, and rendering.

Run: python3 tests/test_groundwork_statusline.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import json
import os
import stat
import sys
import tempfile
import time
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "groundwork_statusline.py"

_FAILURES: list[str] = []
PASS = FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        _FAILURES.append(f"{name}  {detail}")
        print(f"  FAIL {name}  {detail}")


def finish() -> None:
    failures = list(_FAILURES)
    _FAILURES.clear()
    assert not failures, "\n".join(failures)


def load_module():
    spec = importlib.util.spec_from_file_location("gw_statusline", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub_bin(dirpath: Path, name: str, exit_code: int, stdout_text: str = "", sleep_s: float = 0) -> None:
    script = dirpath / name
    body = "#!/bin/sh\n"
    if sleep_s:
        body += f"sleep {sleep_s}\n"
    if stdout_text:
        body += f"cat <<'EOF'\n{stdout_text}\nEOF\n"
    body += f"exit {exit_code}\n"
    script.write_text(body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _telemetry_record(session_id: str, ts: str, playbook: str, execution_mode: str = "single_agent",
                       tests_run: bool = False) -> dict:
    return {
        "schema": 2, "ts": ts, "session_id": session_id, "prompt_id": "p", "harness": "groundwork",
        "harness_version": "2.1.0", "cwd_hash": "deadbeef0000",
        "observed": {"tools": ["Bash"], "mcp_servers": [], "tests_run": tests_run},
        "declared": {"playbook": playbook, "execution_mode": execution_mode, "validation": "verified"},
    }


STDIN_FIXTURE = {
    "model": {"id": "claude-sonnet-5", "display_name": "Sonnet 5"},
    "session_id": "sess-test-1",
    "workspace": {"current_dir": "/tmp/does-not-matter", "project_dir": "/tmp/does-not-matter"},
    "cost": {"total_cost_usd": 1.23},
    "context_window": {"used_percentage": 42.3, "remaining_percentage": 57.7},
}


# ---------------------------------------------------------------------------------------------
def test_full_smoke_stdin_to_stdout() -> None:
    print("groundwork_statusline.py — full stdin-to-stdout smoke test, no cache/config/telemetry")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        mod.STATUSLINE_CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "statusline-config.json"
        old_stdin, old_stdout = sys.stdin, sys.stdout
        sys.stdin = StringIO(json.dumps(STDIN_FIXTURE))
        sys.stdout = StringIO()
        try:
            rc = mod.main()
            out = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = old_stdin, old_stdout
        check("exit code is 0", rc == 0, rc)
        check("output starts with GROUNDWORK", out.startswith("GROUNDWORK"), out)
        check("output is non-empty and single-line in compact mode", len(out.strip()) > 0 and "\n" not in out.strip(), out)
    finish()


def test_rendering_compact_and_detailed() -> None:
    print("groundwork_statusline.py — compact is one line, detailed is multi-line, both include context")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        _write_json(mod.CONFIG_PATH, {"profile": "sre-cloudops"})

        compact = mod.render(STDIN_FIXTURE, {**mod.DEFAULT_STATUSLINE_CONFIG, "mode": "compact"})
        detailed = mod.render(STDIN_FIXTURE, {**mod.DEFAULT_STATUSLINE_CONFIG, "mode": "detailed"})
        check("compact renders one line", "\n" not in compact, compact)
        check("detailed renders more than one line", "\n" in detailed, detailed)
        check("compact includes the profile", "sre-cloudops" in compact, compact)
        check("compact includes context percentage", "42%" in compact, compact)
        check("detailed includes context percentage", "42%" in detailed, detailed)
    finish()


def test_plain_text_fallback_has_no_unicode_symbols() -> None:
    print("groundwork_statusline.py — plain_text mode never emits the Unicode symbol set")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        _write_json(mod.INTEGRATIONS_CACHE_PATH, {
            "schema": 1,
            "integrations": {"GitHub": {"available": True, "configured": False, "connected": True,
                                         "used": None, "summary": "CONNECTED",
                                         "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}},
        })
        plain = mod.render(STDIN_FIXTURE, {**mod.DEFAULT_STATUSLINE_CONFIG, "plain_text": True})
        unicode_line = mod.render(STDIN_FIXTURE, {**mod.DEFAULT_STATUSLINE_CONFIG, "plain_text": False})
        forbidden = ["●", "◐", "○", "│", "·", "✓", "✗"]
        check("plain_text output contains no Unicode symbol from the box-drawing/status set",
              not any(ch in plain for ch in forbidden), plain)
        check("Unicode mode (for contrast) does use at least one of those symbols here",
              any(ch in unicode_line for ch in forbidden), unicode_line)
        check("plain_text output is pure ASCII", all(ord(c) < 128 for c in plain), plain)
    finish()


def test_integrations_section_hidden() -> None:
    print("groundwork_statusline.py — show_integrations: false hides the whole section")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        _write_json(mod.INTEGRATIONS_CACHE_PATH, {
            "schema": 1,
            "integrations": {"GitHub": {"available": True, "configured": False, "connected": True,
                                         "used": None, "summary": "CONNECTED",
                                         "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}},
        })
        shown = mod.render(STDIN_FIXTURE, {**mod.DEFAULT_STATUSLINE_CONFIG, "show_integrations": True})
        hidden = mod.render(STDIN_FIXTURE, {**mod.DEFAULT_STATUSLINE_CONFIG, "show_integrations": False})
        check("shown includes GitHub", "GitHub" in shown, shown)
        check("hidden excludes GitHub entirely", "GitHub" not in hidden, hidden)
    finish()


def test_missing_integrations_cache_shows_nothing_never_infers() -> None:
    print("groundwork_statusline.py — no cache file => no integration readiness shown, never inferred")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"  # never written
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        out = mod.render(STDIN_FIXTURE, dict(mod.DEFAULT_STATUSLINE_CONFIG))
        check("no crash and no integration name appears when cache is absent",
              "GitHub" not in out and "Jira" not in out, out)
    finish()


def test_stale_integrations_cache_shows_age_never_claims_live() -> None:
    print("groundwork_statusline.py — a stale cached entry surfaces its age instead of looking live")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        _write_json(mod.INTEGRATIONS_CACHE_PATH, {
            "schema": 1,
            "integrations": {"GitHub": {"available": True, "configured": False, "connected": True,
                                         "used": None, "summary": "CONNECTED",
                                         "checked_at": "2020-01-01T00:00:00Z"}},
        })
        out = mod.render(STDIN_FIXTURE, dict(mod.DEFAULT_STATUSLINE_CONFIG))
        check("stale entry's rendering includes a visible age annotation (parenthesized)",
              "GitHub" in out and "(" in out and ")" in out, out)
    finish()


def test_malformed_and_missing_state_fails_safe() -> None:
    print("groundwork_statusline.py — malformed/missing config, cache, and telemetry all fail safe, never crash")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        mod.STATUSLINE_CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "statusline-config.json"

        mod.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        mod.CONFIG_PATH.write_text("{not valid json")
        mod.INTEGRATIONS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        mod.INTEGRATIONS_CACHE_PATH.write_text('{"integrations": "not-a-dict"')
        mod.STATUSLINE_CONFIG_PATH.write_text("[]")  # valid JSON, wrong shape (not an object)
        mod.TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        mod.TELEMETRY_PATH.write_text("not even json\n{also not json\n")

        try:
            cfg = mod._load_statusline_config()
            out = mod.render(STDIN_FIXTURE, cfg)
            crashed = False
        except Exception as e:
            out = str(e)
            crashed = True
        check("malformed config/cache/telemetry/statusline-config never raises", not crashed, out)
        check("degrades to documented defaults (compact mode, GROUNDWORK header present)",
              not crashed and out.startswith("GROUNDWORK"), out)

        old_stdin, old_stdout = sys.stdin, sys.stdout
        sys.stdin = StringIO(json.dumps(STDIN_FIXTURE))
        sys.stdout = StringIO()
        try:
            rc = mod.main()
        finally:
            sys.stdin, sys.stdout = old_stdin, old_stdout
        check("main() still exits 0 with every state file malformed", rc == 0, rc)
    finish()


def test_two_session_ids_never_leak_last_turn_state() -> None:
    print("groundwork_statusline.py — two concurrent session_ids resolve to only their own last-turn record")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.TELEMETRY_PATH = Path(tmpdir) / "events.jsonl"
        records = [
            _telemetry_record("session-A", "2026-09-30T05:00:00Z", "IMPLEMENT"),
            _telemetry_record("session-B", "2026-09-30T05:01:00Z", "TROUBLESHOOT", execution_mode="subagents"),
            _telemetry_record("session-A", "2026-09-30T05:02:00Z", "VALIDATE"),
        ]
        mod.TELEMETRY_PATH.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        rec_a = mod._last_turn_for_session("session-A")
        rec_b = mod._last_turn_for_session("session-B")
        rec_c = mod._last_turn_for_session("session-C-never-appeared")

        check("session-A resolves to its OWN latest record (VALIDATE), not session-B's more recent-by-line entry",
              rec_a is not None and rec_a["declared"]["playbook"] == "VALIDATE", rec_a)
        check("session-B resolves to its own record (TROUBLESHOOT)",
              rec_b is not None and rec_b["declared"]["playbook"] == "TROUBLESHOOT", rec_b)
        check("session-B's record is never session-A's",
              rec_b is not None and rec_b["declared"]["playbook"] != rec_a["declared"]["playbook"], (rec_a, rec_b))
        check("a session_id with no matching record returns None, never another session's data",
              rec_c is None, rec_c)

        fields_a = mod._last_turn_fields(rec_a)
        fields_b = mod._last_turn_fields(rec_b)
        check("session-A's rendered fields reflect only its own execution_mode (single_agent)",
              fields_a.get("execution_mode") == "single_agent", fields_a)
        check("session-B's rendered fields reflect only its own execution_mode (subagents)",
              fields_b.get("execution_mode") == "subagents", fields_b)
    finish()


def test_session_with_no_record_degrades_cleanly() -> None:
    print("groundwork_statusline.py — brand-new session with zero telemetry records renders with no last-turn field")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"  # never created
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        rec = mod._last_turn_for_session("brand-new-session")
        check("no telemetry file at all => None, not a crash", rec is None)
        out = mod.render(STDIN_FIXTURE, dict(mod.DEFAULT_STATUSLINE_CONFIG))
        check("render still succeeds with no telemetry file", out.startswith("GROUNDWORK"), out)
    finish()


def test_interrupted_session_shows_previous_completed_turn_not_partial_state() -> None:
    print("groundwork_statusline.py — a crashed/interrupted turn (no new record) still shows the prior completed turn")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.TELEMETRY_PATH = Path(tmpdir) / "events.jsonl"
        records = [_telemetry_record("session-X", "2026-09-30T05:00:00Z", "TROUBLESHOOT")]
        mod.TELEMETRY_PATH.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        # simulate a crash mid-turn: nothing new is ever appended for this "next" turn
        rec = mod._last_turn_for_session("session-X")
        check("previous completed turn's record is what's returned (no partial/corrupt entry exists to misread)",
              rec is not None and rec["declared"]["playbook"] == "TROUBLESHOOT", rec)
    finish()


def test_last_turn_never_shows_bare_unknown() -> None:
    print("groundwork_statusline.py — playbook=='unknown' AND execution_mode=='unknown' (the common "
          "case for a tool-using turn with no Harness-metadata footer) never renders as a bare '~unknown'")
    mod = load_module()
    fields = {"playbook": "unknown", "execution_mode": "unknown", "tests_run": False}
    out = mod._fmt_last_turn(fields, plain=False, show_validation=True)
    check("no last-turn text is rendered when both playbook and execution_mode are 'unknown'",
          out is None, out)

    fields_mixed = {"playbook": "IMPLEMENT", "execution_mode": "unknown", "tests_run": False}
    out_mixed = mod._fmt_last_turn(fields_mixed, plain=False, show_validation=True)
    check("a known playbook still renders even when execution_mode is 'unknown'",
          out_mixed is not None and "unknown" not in out_mixed and "IMPLEMENT" in out_mixed, out_mixed)
    finish()


def test_git_status_no_commits_yet_reports_real_branch() -> None:
    print("groundwork_statusline.py — a brand-new repo with zero commits ('## No commits yet on "
          "<branch>') reports the real branch name, never a mis-parsed 'No'")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        import subprocess
        subprocess.run(["git", "init", "-q", "-b", "main", tmpdir], check=True)
        result = mod._git_status(tmpdir)
        check("branch is the real name ('main'), never the mis-parsed word 'No'",
              result is not None and result[0] == "main" and result[0] != "No", result)
    finish()


def test_git_status_clean_and_dirty() -> None:
    print("groundwork_statusline.py — git branch/dirty via a single fast subprocess call")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        import subprocess
        subprocess.run(["git", "init", "-q", tmpdir], check=True)
        subprocess.run(["git", "-C", tmpdir, "config", "user.email", "t@example.com"], check=True)
        subprocess.run(["git", "-C", tmpdir, "config", "user.name", "t"], check=True)
        (Path(tmpdir) / "f.txt").write_text("hello\n")
        subprocess.run(["git", "-C", tmpdir, "add", "f.txt"], check=True)
        subprocess.run(["git", "-C", tmpdir, "commit", "-q", "-m", "init"], check=True)

        clean = mod._git_status(tmpdir)
        check("clean repo => dirty is False", clean is not None and clean[1] is False, clean)

        (Path(tmpdir) / "f.txt").write_text("changed\n")
        dirty = mod._git_status(tmpdir)
        check("modified file => dirty is True", dirty is not None and dirty[1] is True, dirty)
        check("branch name is non-empty in both cases", bool(clean[0]) and bool(dirty[0]), (clean, dirty))
    finish()


def test_git_status_missing_or_timeout_omits_field_never_hangs() -> None:
    print("groundwork_statusline.py — a missing/non-repo cwd or a timed-out git call omits the field, never blocks")
    mod = load_module()
    check("non-existent directory => None, no exception", mod._git_status("/definitely/does/not/exist/at/all") is None)
    check("empty/None cwd => None", mod._git_status(None) is None and mod._git_status("") is None)

    with tempfile.TemporaryDirectory() as tmpdir:
        not_a_repo = Path(tmpdir) / "not-a-repo"
        not_a_repo.mkdir()
        check("a real directory that is not a git repo => None, no exception", mod._git_status(str(not_a_repo)) is None)

    with tempfile.TemporaryDirectory() as bindir:
        _stub_bin(Path(bindir), "git", 0, sleep_s=5)
        old_path = os.environ.get("PATH")
        old_timeout = mod.GIT_TIMEOUT_S
        os.environ["PATH"] = bindir + os.pathsep + (old_path or "")
        mod.GIT_TIMEOUT_S = 0.3
        try:
            start = time.monotonic()
            result = mod._git_status("/tmp")
            elapsed = time.monotonic() - start
            check("a hanging git call times out quickly and returns None, never hangs the render",
                  result is None and elapsed < 3.0, (result, elapsed))
        finally:
            mod.GIT_TIMEOUT_S = old_timeout
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path
    finish()


def test_unavailable_fields_never_appear() -> None:
    print("groundwork_statusline.py — review/MUST-FIX state, role/persona, and evidence-label counts "
          "never appear anywhere in rendered output (no code path reads or renders them)")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        # Plant a telemetry record with extra, unexpected fields resembling review/role/evidence data,
        # to prove the reader only ever extracts playbook/execution_mode/tests_run — nothing else.
        poisoned = _telemetry_record("sess-test-1", "2026-09-30T05:00:00Z", "IMPLEMENT")
        poisoned["declared"]["must_fix_count"] = 7
        poisoned["declared"]["review_verdict"] = "changes-required"
        poisoned["declared"]["role"] = "Infrastructure Engineer"
        poisoned["declared"]["evidence_verified_count"] = 12
        mod.TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        mod.TELEMETRY_PATH.write_text(json.dumps(poisoned) + "\n")
        out = mod.render(STDIN_FIXTURE, {**mod.DEFAULT_STATUSLINE_CONFIG, "mode": "detailed"})
        for forbidden in ("must_fix", "MUST FIX", "changes-required", "Infrastructure Engineer",
                          "review_verdict", "evidence_verified", "role"):
            check(f"'{forbidden}' never appears in rendered output even when present in the source record",
                  forbidden not in out, out)
    finish()


def test_execution_time_is_fast() -> None:
    print("groundwork_statusline.py — measured end-to-end execution time is small (no expensive operations)")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        mod.CLAUDE_DIR = Path(tmpdir)
        mod.CONFIG_PATH = mod.CLAUDE_DIR / "groundwork" / "config.json"
        mod.TELEMETRY_PATH = mod.CLAUDE_DIR / "groundwork" / "telemetry" / "events.jsonl"
        mod.INTEGRATIONS_CACHE_PATH = mod.CLAUDE_DIR / "groundwork" / "integrations" / "cache.json"
        mod.VERSION_PATH = mod.CLAUDE_DIR / "groundwork" / "VERSION"
        _write_json(mod.CONFIG_PATH, {"profile": "sre-cloudops"})
        # A larger synthetic telemetry file (well within the bounded-scan window) to make sure the
        # tail-scan itself stays fast, not just the happy-path empty case.
        records = [_telemetry_record(f"other-session-{i}", "2026-09-30T05:00:00Z", "IMPLEMENT") for i in range(500)]
        records.append(_telemetry_record("sess-test-1", "2026-09-30T05:00:01Z", "VALIDATE"))
        mod.TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        mod.TELEMETRY_PATH.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        start = time.monotonic()
        for _ in range(20):
            mod.render(STDIN_FIXTURE, dict(mod.DEFAULT_STATUSLINE_CONFIG))
        elapsed_per_call = (time.monotonic() - start) / 20
        check(f"average render() time over 20 calls is well under 1s (got {elapsed_per_call * 1000:.1f}ms)",
              elapsed_per_call < 1.0, elapsed_per_call)
    finish()


def test_no_expensive_subprocess_names_appear_in_source() -> None:
    print("groundwork_statusline.py — source never actually invokes claude mcp list / gh auth status / "
          "network calls (checked as call-shaped patterns, not prose — the docstring names them by design, "
          "to document that they are NOT called)")
    source = SCRIPT.read_text()
    # Call-shaped patterns (as they'd appear in a real subprocess.run([...]) argv list), distinct
    # from this file's own docstring prose that deliberately names these commands as excluded.
    for forbidden in ('"mcp", "list"', '"auth", "status"', "urllib", "requests", "socket.", "http.client"):
        check(f"'{forbidden}' (a real subprocess call shape) does not appear in scripts/groundwork_statusline.py",
              forbidden not in source, forbidden)
    check("the only subprocess.run call in the file is the git status one",
          source.count("subprocess.run(") == 1, source.count("subprocess.run("))
    finish()


if __name__ == "__main__":
    for fn in (
        test_full_smoke_stdin_to_stdout, test_rendering_compact_and_detailed,
        test_plain_text_fallback_has_no_unicode_symbols, test_integrations_section_hidden,
        test_missing_integrations_cache_shows_nothing_never_infers,
        test_stale_integrations_cache_shows_age_never_claims_live,
        test_malformed_and_missing_state_fails_safe,
        test_two_session_ids_never_leak_last_turn_state,
        test_session_with_no_record_degrades_cleanly,
        test_interrupted_session_shows_previous_completed_turn_not_partial_state,
        test_last_turn_never_shows_bare_unknown, test_git_status_no_commits_yet_reports_real_branch,
        test_git_status_clean_and_dirty, test_git_status_missing_or_timeout_omits_field_never_hangs,
        test_unavailable_fields_never_appear, test_execution_time_is_fast,
        test_no_expensive_subprocess_names_appear_in_source,
    ):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
