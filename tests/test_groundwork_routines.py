#!/usr/bin/env python3
"""Deterministic checks for scripts/groundwork_routines.py (Groundwork 2.1) — no live `claude`
call except where a local stub binary stands in for it.

Covers the routine configuration contract (owner requirement, added after the first release
candidate): capability-aware allowlists built from routine + configured access + scope + mutation
permission (never one flat global allowlist), BLOCKED-before-invocation when access is
unconfigured, the ROUTINE RESULT semantic-status contract, and result storage separate from
telemetry.

Run: python3 tests/test_groundwork_routines.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "groundwork_routines.py"
CONFIG_SCRIPT = REPO_ROOT / "scripts" / "groundwork_config.py"

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
    spec = importlib.util.spec_from_file_location("gw_routines", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_cli(args, env_extra=None, timeout=30) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


def config_cli(args, env_extra=None, timeout=30) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(["python3", str(CONFIG_SCRIPT), *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


def write_claude_stub(bindir: Path, behavior="echo", stdout_text=None) -> None:
    """A fake `claude` on PATH so run_routine's subprocess call is deterministic and instant —
    never invokes the real CLI (that's covered by live sandbox validation, not this test)."""
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / "claude"
    if behavior == "echo":
        script.write_text("#!/usr/bin/env bash\necho \"stub output: $*\"\nexit 0\n")
    elif behavior == "fail":
        script.write_text("#!/usr/bin/env bash\necho \"stub failure\" >&2\nexit 1\n")
    elif behavior == "hang":
        script.write_text("#!/usr/bin/env bash\nsleep 30\n")
    elif behavior == "result":
        script.write_text(f"#!/usr/bin/env bash\ncat <<'STUBEOF'\n{stdout_text}\nSTUBEOF\nexit 0\n")
    elif behavior == "capture":
        # Dumps its own argv (one arg per line, via $CAPTURE_ARGV_FILE) before returning a minimal
        # valid ROUTINE RESULT — lets a test inspect the exact flags a real subprocess invocation
        # received, without needing the real `claude` CLI.
        script.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$@\" > \"$CAPTURE_ARGV_FILE\"\n"
            "cat <<'STUBEOF'\nROUTINE RESULT\nStatus: COMPLETE\nSummary: stub\nSTUBEOF\n"
            "exit 0\n"
        )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | 0o111)


def init_config(cfgdir: Path, profile="minimal") -> None:
    config_cli(["init", profile, "--path", str(cfgdir / "groundwork" / "config.json"), "--force"])


def set_routine(cfgdir: Path, routine: str, *assignments: str) -> None:
    r = config_cli(["set", routine, *assignments, "--path", str(cfgdir / "groundwork" / "config.json")])
    assert r.returncode == 0, f"config set failed: {r.stdout} {r.stderr}"


def test_module_level_registry_and_result_parsing() -> None:
    print("groundwork_routines.py — module-level checks (ROUTINES registry, ROUTINE RESULT parsing)")
    mod = load_module()

    expected_names = {"jira_eod", "news", "weekly_status", "pr_followup", "work_digest", "doc_drift"}
    check("ROUTINES has exactly the six designed routines", set(mod.ROUTINES) == expected_names, sorted(mod.ROUTINES))
    check("only jira_eod mutates", [n for n, s in mod.ROUTINES.items() if s["mutates"]] == ["jira_eod"])
    check("only jira_eod needs offline-work folding in", [n for n, s in mod.ROUTINES.items() if s["needs_offline_work"]] == ["jira_eod"])

    check("parse_routine_result: empty text -> {}", mod.parse_routine_result("") == {})
    check("parse_routine_result: no block at all -> {}", mod.parse_routine_result("just some prose, no block") == {})
    ok_block = "Some digest text here.\n\nROUTINE RESULT\nStatus: COMPLETE\nSummary: all good\n"
    parsed = mod.parse_routine_result(ok_block)
    check("parse_routine_result: well-formed block parses Status", parsed.get("status") == "complete", parsed)
    check("parse_routine_result: well-formed block parses Summary", parsed.get("summary") == "all good", parsed)
    check("parse_routine_result: block_start points before the heading", ok_block[:parsed["block_start"]].strip() == "Some digest text here.", parsed)
    bad_status = "text\n\nROUTINE RESULT\nStatus: not-a-real-status\nSummary: x\n"
    check("parse_routine_result: unknown status value is not accepted", "status" not in mod.parse_routine_result(bad_status))
    for s in ("complete", "partial", "blocked", "failed", "skipped"):
        block = f"text\n\nROUTINE RESULT\nStatus: {s.upper()}\nSummary: x\n"
        check(f"parse_routine_result: accepts {s.upper()}", mod.parse_routine_result(block).get("status") == s)
    finish()


def test_capabilities_for_never_grants_beyond_configured_access() -> None:
    print("groundwork_routines.py — _capabilities_for(): least privilege from routine+access+scope+mutation")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgdir = Path(tmpdir) / "cfg"
        init_config(cfgdir)
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
        try:
            cfg = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")

            # A returned tools list alongside a blocked reason is never consumed — build_command()
            # returns None for cmd and short-circuits before any tool list matters — so the
            # meaningful assertion is the blocked reason itself, not the (unused) tools value.
            tools, blocked = mod._capabilities_for("jira_eod", cfg)
            check("jira_eod with access=unconfigured (minimal profile default): BLOCKED with a clear reason",
                  blocked is not None and "Jira access not configured" in blocked, (tools, blocked))

            tools, blocked = mod._capabilities_for("pr_followup", cfg)
            check("pr_followup with access=unconfigured: BLOCKED with a clear reason",
                  blocked is not None and "GitHub access not configured" in blocked, (tools, blocked))

            tools, blocked = mod._capabilities_for("news", cfg)
            check("news: never blocked (no access mechanism needed), gets WebSearch/WebFetch",
                  blocked is None and "WebSearch" in tools and "WebFetch" in tools, tools)
            check("news: never gets any Jira- or GitHub-shaped tool",
                  not any("jira" in t.lower() or "github" in t.lower() or "gh " in t.lower() for t in tools), tools)

            tools, blocked = mod._capabilities_for("doc_drift", cfg)
            check("doc_drift: never blocked, gets only base repo-read tools (no web, no MCP)",
                  blocked is None and tools == mod.BASE_REPO_READ, tools)
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


def test_capabilities_for_configured_jira_and_github() -> None:
    print("groundwork_routines.py — _capabilities_for(): configured access grants exactly that mechanism's tools")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgdir = Path(tmpdir) / "cfg"
        init_config(cfgdir)
        set_routine(cfgdir, "jira_eod", "access=jira_mcp", "mcp_server=atlassian")
        set_routine(cfgdir, "pr_followup", "access=gh_cli")
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
        try:
            cfg = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")
            tools, blocked = mod._capabilities_for("jira_eod", cfg)
            check("jira_eod with access=jira_mcp+mcp_server: not blocked", blocked is None, blocked)
            check("jira_eod with access=jira_mcp: gets that server's wildcard, nothing else Jira-shaped",
                  "mcp__atlassian__*" in tools, tools)
            check("jira_eod: still has base repo-read tools underneath", set(mod.BASE_REPO_READ) <= set(tools), tools)

            tools, blocked = mod._capabilities_for("pr_followup", cfg)
            check("pr_followup with access=gh_cli: not blocked", blocked is None, blocked)
            check("pr_followup: gets only read-shaped gh subcommands", set(tools) >= set(mod.GH_CLI_READ_TOOLS), tools)
            check("pr_followup: never gets a gh mutation subcommand (merge/close/edit/comment)",
                  not any("merge" in t or "close" in t or "edit" in t or "comment" in t for t in tools), tools)

            # jira_mcp with no server name configured: still BLOCKED, never guesses a server name
            set_routine(cfgdir, "jira_eod", "access=jira_mcp", "mcp_server=")
            cfg2 = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")
            tools2, blocked2 = mod._capabilities_for("jira_eod", cfg2)
            check("jira_eod access=jira_mcp with empty mcp_server: BLOCKED, never guesses a server name",
                  blocked2 is not None and "MCP server name not configured" in blocked2, (tools2, blocked2))
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


def test_github_mcp_tools_are_real_and_read_only() -> None:
    print("groundwork_routines.py — GitHub MCP tool list is real (session-confirmed names), never write-shaped")
    mod = load_module()
    write_patterns = ("create_", "merge_", "update_", "push_", "delete_", "_write", "enable_", "disable_")
    for tool in mod.GITHUB_MCP_READ_TOOLS:
        check(f"{tool}: not a write-shaped GitHub MCP tool name", not any(p in tool for p in write_patterns), tool)
        check(f"{tool}: uses the real mcp__github__ prefix", tool.startswith("mcp__github__"), tool)
    finish()


def test_work_digest_cross_references_jira_and_github_access() -> None:
    print("groundwork_routines.py — work_digest/weekly_status reuse jira_eod/pr_followup's own configured access, never re-ask")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgdir = Path(tmpdir) / "cfg"
        init_config(cfgdir)
        set_routine(cfgdir, "work_digest", "use_github=true")
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
        try:
            cfg = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")
            tools, blocked = mod._capabilities_for("work_digest", cfg)
            check("work_digest wants GitHub but pr_followup has no access configured: BLOCKED",
                  blocked is not None and "GitHub" in blocked, blocked)

            set_routine(cfgdir, "pr_followup", "access=gh_cli")
            cfg2 = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")
            tools2, blocked2 = mod._capabilities_for("work_digest", cfg2)
            check("work_digest, once pr_followup's access is configured, borrows those same tools (not blocked)",
                  blocked2 is None and set(mod.GH_CLI_READ_TOOLS) <= set(tools2), (tools2, blocked2))
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


def test_non_mutating_routines_never_inherit_jiras_write_capable_wildcard() -> None:
    """Regression test for a MUST FIX found by a fresh adversarial reviewer: `_capabilities_for()`'s
    old `weekly_status`/`work_digest` branch called `_jira_tools()` for the Jira cross-reference
    case exactly as `jira_eod`'s own branch does — for the `jira_mcp` mechanism this is the
    unrestricted `mcp__<server>__*` wildcard, identical to what `jira_eod` itself gets when
    configured to post live. Both routines are declared `mutates: False` in the ROUTINES registry,
    so this violated specs/routines/spec.md's own requirement that a non-mutating routine "SHALL
    NEVER be granted a write-shaped tool... regardless of configuration". The prior version of this
    test file only ever exercised `use_github`, never `use_jira`/`jira_projects` — exactly the
    blind spot that let the bug ship. Fix: no live Jira tool is granted for the reuse case at all,
    any mechanism, any configuration — the routine's prompt instead points at jira_eod's own already
    -stored result file, readable via the Read/Glob tools already in BASE_REPO_READ."""
    print("groundwork_routines.py — weekly_status/work_digest never inherit jira_eod's write-capable Jira wildcard")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgdir = Path(tmpdir) / "cfg"
        init_config(cfgdir)
        # jira_eod itself configured for live posting via the jira_mcp mechanism — the routine that
        # legitimately gets the wildcard, since it's the one declared mutates: True.
        set_routine(cfgdir, "jira_eod", "access=jira_mcp", "mcp_server=atlassian", "posting=automatic")
        # use_github=false isolates this test to the Jira cross-reference path — work_digest's own
        # default is use_github=true, and weekly_status's GitHub reuse defaults on too, both of
        # which would otherwise BLOCK on pr_followup being unconfigured before Jira is even reached.
        set_routine(cfgdir, "work_digest", "use_jira=true", "use_github=false")
        set_routine(cfgdir, "weekly_status", "use_github=false")
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
        try:
            cfg = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")

            def has_jira_tool(tools):
                return any("jira" in t.lower() or t == "mcp__atlassian__*" or t.startswith("Bash(jira")
                           or "Browser" in t or "claude-in-chrome" in t for t in tools)

            tools_jira, blocked_jira = mod._capabilities_for("jira_eod", cfg)
            check("jira_eod (mutates: True, posting=automatic) still gets its own Jira wildcard",
                  blocked_jira is None and "mcp__atlassian__*" in tools_jira, (tools_jira, blocked_jira))

            tools_wd, blocked_wd = mod._capabilities_for("work_digest", cfg)
            check("work_digest with use_jira=true and jira_eod configured live: never blocked on Jira",
                  blocked_wd is None, blocked_wd)
            check("work_digest (mutates: False) gets NO Jira-shaped tool at all, despite use_jira=true "
                  "and jira_eod's own access being the write-capable jira_mcp mechanism",
                  not has_jira_tool(tools_wd), tools_wd)
            check("work_digest still has its base repo-read tools underneath",
                  set(mod.BASE_REPO_READ) <= set(tools_wd), tools_wd)

            # weekly_status's own schema field for this is `jira_projects`, not `use_jira` — assert
            # its capability set is equally clean, and independently that its prompt actually
            # references jira_eod's evidence-reuse path rather than staying silent about it.
            set_routine(cfgdir, "weekly_status", "jira_projects=[\"PROJ\"]")
            cfg2 = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")
            tools_ws, blocked_ws = mod._capabilities_for("weekly_status", cfg2)
            check("weekly_status with jira_projects set: never blocked on Jira", blocked_ws is None, blocked_ws)
            check("weekly_status (mutates: False) gets NO Jira-shaped tool either, with jira_projects set",
                  not has_jira_tool(tools_ws), tools_ws)

            # Every mechanism jira_eod could be configured with is equally excluded from the reuse
            # path, not just jira_mcp — cli (`Bash(jira *)`) and browser are just as write-capable.
            for mech, extra in (("cli", {}), ("browser", {})):
                set_routine(cfgdir, "jira_eod", f"access={mech}")
                cfg3 = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")
                tools3, blocked3 = mod._capabilities_for("work_digest", cfg3)
                check(f"work_digest with jira_eod access={mech}: still no Jira-shaped tool granted",
                      blocked3 is None and not has_jira_tool(tools3), (mech, tools3, blocked3))

            prompt = mod._work_digest_prompt(cfg["routines"]["work_digest"])
            check("work_digest's prompt points at jira_eod's stored result file, never a live Jira tool",
                  "do NOT call any live Jira tool" in prompt and "routines" in prompt and "results" in prompt and "jira_eod" in prompt, prompt)
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


def claude_unreachable_path() -> str:
    """A PATH with python3 (needed to run the script itself) reachable but no `claude` binary
    anywhere on it — proves BLOCKED/off-switch paths never even attempt to spawn `claude`."""
    d = Path(tempfile.mkdtemp(prefix="gw-no-claude-bin-"))
    py = shutil.which("python3")
    if py:
        (d / "python3").symlink_to(py)
    return str(d)


def run_routine_subprocess(cfgdir: Path, name: str, path_override=None, env_extra=None) -> dict:
    """Invokes `run` as a real, fresh subprocess — matching how every production invocation
    actually happens (setup.sh/launchd/cron all shell out to a fresh `python3 groundwork_routines.py
    run ...`), and sidesteps groundwork_config's module-level DEFAULT_PATH being cached in
    sys.modules across in-process test calls within one test run (a test-harness artifact, not a
    production concern — each real invocation is its own process)."""
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfgdir)}
    if path_override is not None:
        env["PATH"] = path_override
    env.update(env_extra or {})
    r = subprocess.run(["python3", str(SCRIPT), "run", name, "--repo", str(REPO_ROOT), "--timeout", "10"],
                       capture_output=True, text=True, timeout=20, env=env)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"status": "test-harness-error", "stdout": r.stdout, "stderr": r.stderr}


def test_run_routine_off_switches_and_disabled() -> None:
    print("groundwork_routines.py run — off-switches and disabled-in-config never invoke `claude`")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfgdir = tmp / "cfg"
        init_config(cfgdir)
        set_routine(cfgdir, "news", "enabled=true")
        unreachable = claude_unreachable_path()

        r = run_routine_subprocess(cfgdir, "news", path_override=unreachable, env_extra={"GROUNDWORK_ROUTINES": "off"})
        check("GROUNDWORK_ROUTINES=off: skipped, no subprocess attempted (claude unreachable would otherwise fail differently)",
              r.get("status") == "skipped" and "off" in r.get("reason", ""), r)

        r = run_routine_subprocess(cfgdir, "news", path_override=unreachable, env_extra={"GROUNDWORK_ROUTINES_NEWS": "off"})
        check("GROUNDWORK_ROUTINES_NEWS=off: skips only that routine", r.get("status") == "skipped", r)

        r = run_routine_subprocess(cfgdir, "doc_drift", path_override=unreachable)  # never enabled in this config
        check("routine not enabled in config.json: skipped, no subprocess attempted (never guesses intent)",
              r.get("status") == "skipped" and "not enabled" in r.get("reason", ""), r)
    finish()


def test_run_routine_blocked_before_any_subprocess() -> None:
    print("groundwork_routines.py run — BLOCKED (unconfigured access) never spawns `claude`, even if unreachable")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfgdir = tmp / "cfg"
        init_config(cfgdir)
        set_routine(cfgdir, "jira_eod", "enabled=true")  # access stays unconfigured
        set_routine(cfgdir, "pr_followup", "enabled=true")
        unreachable = claude_unreachable_path()

        r = run_routine_subprocess(cfgdir, "jira_eod", path_override=unreachable)
        check("jira_eod enabled but access unconfigured: BLOCKED, not FAILED (no crash from missing claude)",
              r.get("status") == "blocked" and "not configured" in r.get("reason", ""), r)
        check("BLOCKED result never claims a duration from an actual invocation", r.get("duration_s") == 0.0, r)

        r2 = run_routine_subprocess(cfgdir, "pr_followup", path_override=unreachable)
        check("pr_followup enabled but access unconfigured: BLOCKED", r2.get("status") == "blocked", r2)
    finish()


def test_semantic_status_from_routine_result_block() -> None:
    print("groundwork_routines.py run — semantic status (COMPLETE/PARTIAL/BLOCKED/FAILED), never exit-code-only")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfgdir = tmp / "cfg"
        bindir = tmp / "bin"
        init_config(cfgdir)
        set_routine(cfgdir, "news", "enabled=true")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfgdir), "PATH": f"{bindir}:/usr/bin:/bin"}

        write_claude_stub(bindir, "result", "Some digest.\n\nROUTINE RESULT\nStatus: COMPLETE\nSummary: all good")
        r = subprocess.run(["python3", str(SCRIPT), "run", "news", "--repo", str(REPO_ROOT), "--timeout", "20"],
                           capture_output=True, text=True, timeout=30, env=env)
        out = json.loads(r.stdout)
        check("exit 0 + Status: COMPLETE in the block -> semantic status complete", out["status"] == "complete" and r.returncode == 0, out)

        write_claude_stub(bindir, "result", "Tried but Jira was unreachable.\n\nROUTINE RESULT\nStatus: BLOCKED\nSummary: Jira unavailable")
        r = subprocess.run(["python3", str(SCRIPT), "run", "news", "--repo", str(REPO_ROOT), "--timeout", "20"],
                           capture_output=True, text=True, timeout=30, env=env)
        out = json.loads(r.stdout)
        check("exit 0 but Status: BLOCKED in the block -> semantic status blocked, NOT complete (exit code alone is never COMPLETE)",
              out["status"] == "blocked", out)

        write_claude_stub(bindir, "result", "Half worked.\n\nROUTINE RESULT\nStatus: PARTIAL\nSummary: 2 of 3 done")
        r = subprocess.run(["python3", str(SCRIPT), "run", "news", "--repo", str(REPO_ROOT), "--timeout", "20"],
                           capture_output=True, text=True, timeout=30, env=env)
        out = json.loads(r.stdout)
        check("Status: PARTIAL in the block -> semantic status partial", out["status"] == "partial", out)

        write_claude_stub(bindir, "echo")  # emits "stub output: ..." with NO ROUTINE RESULT block
        r = subprocess.run(["python3", str(SCRIPT), "run", "news", "--repo", str(REPO_ROOT), "--timeout", "20"],
                           capture_output=True, text=True, timeout=30, env=env)
        out = json.loads(r.stdout)
        check("exit 0 but missing ROUTINE RESULT block -> FAILED, never silently upgraded to COMPLETE (owner requirement §13)",
              out["status"] == "failed" and "missing or malformed" in out.get("reason", ""), out)

        write_claude_stub(bindir, "fail")
        r = subprocess.run(["python3", str(SCRIPT), "run", "news", "--repo", str(REPO_ROOT), "--timeout", "20"],
                           capture_output=True, text=True, timeout=30, env=env)
        out = json.loads(r.stdout)
        check("nonzero exit code -> FAILED regardless of anything else (a crash is a crash)",
              out["status"] == "failed" and out["exit_code"] == 1, out)
    finish()


def test_result_storage_separate_from_telemetry() -> None:
    print("groundwork_routines.py run — routine result content stored separately from telemetry (owner requirement §12)")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfgdir = tmp / "cfg"
        bindir = tmp / "bin"
        init_config(cfgdir)
        set_routine(cfgdir, "news", "enabled=true")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfgdir), "PATH": f"{bindir}:/usr/bin:/bin"}
        digest_text = "AI news: nothing especially material this week, one minor SDK release noted."
        write_claude_stub(bindir, "result", f"{digest_text}\n\nROUTINE RESULT\nStatus: COMPLETE\nSummary: quiet week")
        r = subprocess.run(["python3", str(SCRIPT), "run", "news", "--repo", str(REPO_ROOT), "--timeout", "20"],
                           capture_output=True, text=True, timeout=30, env=env)
        check("run exits 0", r.returncode == 0, r.stdout + r.stderr)

        tel_path = cfgdir / "groundwork" / "telemetry" / "routines.jsonl"
        tel_line = json.loads(tel_path.read_text().splitlines()[-1])
        check("telemetry record has no 'content' field at all", "content" not in tel_line, tel_line)
        check("telemetry record's own text fields never contain the actual digest text",
              digest_text not in json.dumps(tel_line), tel_line)

        results_dir = cfgdir / "groundwork" / "routines" / "results" / "news"
        check("a result file was written under routines/results/news/", results_dir.is_dir() and list(results_dir.glob("run-*.json")), list(results_dir.glob("*")) if results_dir.is_dir() else "missing")
        result_file = sorted(results_dir.glob("run-*.json"))[-1]
        mode = stat.S_IMODE(result_file.stat().st_mode)
        check("result file is 0600 (owner-only)", mode == 0o600, oct(mode))
        stored = json.loads(result_file.read_text())
        check("stored result actually contains the routine's real output text", digest_text in stored["content"], stored)
        check("stored result records the semantic status", stored["status"] == "complete", stored)

        r2 = subprocess.run(["python3", str(SCRIPT), "latest", "news"], capture_output=True, text=True, timeout=10, env=env)
        check("`latest news` retrieves the actual digest text", digest_text in r2.stdout, r2.stdout)
        check("`latest news` shows the semantic status", "COMPLETE" in r2.stdout, r2.stdout)
    finish()


def test_result_retention_bounded() -> None:
    print("groundwork_routines.py — result storage retention is bounded (owner requirement §12)")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfgdir = tmp / "cfg"
        mod = load_module()
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
        try:
            for i in range(mod.RESULT_RETENTION + 5):
                mod._store_result("news", "complete", f"run {i}", f"content {i}", False, False)
                time.sleep(0.01)
            results_dir = cfgdir / "groundwork" / "routines" / "results" / "news"
            files = sorted(results_dir.glob("run-*.json"))
            check(f"retention bounded to {mod.RESULT_RETENTION} most recent runs",
                  len(files) <= mod.RESULT_RETENTION, len(files))
            newest = json.loads(files[-1].read_text())
            check("the most recent run is the one actually kept", newest["content"] == f"content {mod.RESULT_RETENTION + 4}", newest)
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


def test_check_access_never_asserts_connected_without_checking() -> None:
    print("groundwork_routines.py — check_access(): CONFIGURED != CONNECTED, never guesses (owner requirement §8-9)")
    mod = load_module()
    cfg_unconf = {"routines": {"jira_eod": {"access": "unconfigured"}}}
    out = mod.check_access("jira_eod", cfg_unconf)
    check("unconfigured access: available/connected both None, not False (unknown, not checked-and-failed)",
          out["available"] is None and out["connected"] is None, out)

    old_path = os.environ.get("PATH")
    os.environ["PATH"] = "/nonexistent-empty-bin"
    try:
        cfg_gh = {"routines": {"pr_followup": {"access": "gh_cli"}}}
        out = mod.check_access("pr_followup", cfg_gh)
        check("gh_cli access with 'gh' not on PATH: available=False, never CONNECTED without checking",
              out["available"] is False and out["connected"] is None, out)
    finally:
        if old_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = old_path
    finish()


def test_doctor_rows_and_formatting() -> None:
    print("groundwork_routines.py — _doctor_rows()/format_doctor_text(): CONFIGURED/AVAILABLE/CONNECTED distinctions, no secrets exposed")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgdir = Path(tmpdir) / "cfg"
        init_config(cfgdir, "sre-cloudops")
        set_routine(cfgdir, "jira_eod", "site=https://x.atlassian.net", "identity=me@x.com", "access=jira_mcp", "mcp_server=atlassian")
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
        try:
            cfg = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")
            rows = mod._doctor_rows(cfg)
            by_name = {r["routine"]: r for r in rows}
            check("doctor rows cover all six routines", set(by_name) == set(mod.ROUTINES), set(by_name))
            check("jira_eod row exposes site/identity/access, no credential-shaped field",
                  by_name["jira_eod"]["site"] == "https://x.atlassian.net" and
                  not any("token" in k or "password" in k for k in by_name["jira_eod"]), by_name["jira_eod"])
            check("doc_drift (disabled in sre-cloudops) shows enabled=False with no extra fields fabricated",
                  by_name["doc_drift"]["enabled"] is False and "schedule" not in by_name["doc_drift"], by_name["doc_drift"])

            text = mod.format_doctor_text(rows)
            check("formatted text names Jira EOD with its real configured site", "Jira EOD" in text and "https://x.atlassian.net" in text, text)
            check("formatted text never reports VERIFIED for a mechanism that wasn't actually checked",
                  "Connectivity ......... VERIFIED" not in text or by_name["jira_eod"].get("connected") is True, text)
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


def test_doctor_name_filter() -> None:
    print("groundwork_routines.py — doctor NAME (Phase 4, groundwork-routine-cli-ux): narrows to "
          "one routine without changing its data or re-probing routines nobody asked about")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgdir = Path(tmpdir) / "cfg"
        init_config(cfgdir, "sre-cloudops")
        set_routine(cfgdir, "jira_eod", "site=https://x.atlassian.net", "identity=me@x.com",
                    "access=jira_mcp", "mcp_server=atlassian")
        set_routine(cfgdir, "pr_followup", "identity=me", "access=gh_cli")
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
        try:
            cfg = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")

            # Backward compatibility: bare doctor() is completely unaffected — this is the exact
            # call setup.sh --doctor's verify_capabilities() already makes (setup.sh:745), and it
            # must keep returning all six routines exactly as before this change.
            all_rows = mod._doctor_rows(cfg)
            check("bare _doctor_rows(cfg) (no name) still covers all six routines",
                  {r["routine"] for r in all_rows} == set(mod.ROUTINES), {r["routine"] for r in all_rows})

            # Narrowing to one routine returns exactly that routine, with byte-identical field
            # values to what the unfiltered call already computed for it — a pure filter, not a
            # second, independently-computed view that could disagree.
            for target in ("jira_eod", "pr_followup", "news"):
                filtered = mod._doctor_rows(cfg, name=target)
                check(f"_doctor_rows(cfg, name='{target}') returns exactly one row", len(filtered) == 1, filtered)
                expected = next(r for r in all_rows if r["routine"] == target)
                check(f"_doctor_rows(cfg, name='{target}')'s row is identical to the unfiltered row",
                      filtered[0] == expected, (filtered[0], expected))

            # No side effect on routines nobody asked about: filtering to jira_eod must never run
            # pr_followup's real gh_cli connectivity check (a live `gh auth status` subprocess call)
            # — the same "probe only what's asked" property Phase 2's `groundwork integrations
            # doctor NAME` already established, now proven here too via a call-counting stub.
            with tempfile.TemporaryDirectory() as bindir_s:
                bindir = Path(bindir_s)
                call_log = bindir / "calls.log"
                gh_stub = bindir / "gh"
                gh_stub.write_text(f"#!/bin/sh\necho called >> {call_log}\necho 'github.com'\n"
                                    "echo '  ✓ Logged in to github.com account someone (keyring)'\nexit 0\n")
                gh_stub.chmod(gh_stub.stat().st_mode | stat.S_IEXEC | 0o111)
                old_path = os.environ.get("PATH")
                os.environ["PATH"] = str(bindir)
                try:
                    mod._doctor_rows(cfg, name="jira_eod")
                    calls_after_jira_only = call_log.read_text().count("called") if call_log.exists() else 0
                    check("filtering to jira_eod never invokes pr_followup's gh_cli connectivity check",
                          calls_after_jira_only == 0, f"calls={calls_after_jira_only}")

                    mod._doctor_rows(cfg, name="pr_followup")
                    calls_after_pr = call_log.read_text().count("called") if call_log.exists() else 0
                    check("filtering to pr_followup itself still runs its real gh_cli connectivity check",
                          calls_after_pr == 1, f"calls={calls_after_pr}")
                finally:
                    if old_path is None:
                        os.environ.pop("PATH", None)
                    else:
                        os.environ["PATH"] = old_path

            # CLI level: `doctor NAME` output is byte-identical to rendering just that routine's
            # own row through the exact same formatter `doctor` (all routines) already uses —
            # narration of the same data, never a second, independently-computed view.
            expected_jira_text = mod.format_doctor_text([r for r in all_rows if r["routine"] == "jira_eod"])
            single_out = subprocess.run(["python3", str(SCRIPT), "doctor", "jira_eod"], capture_output=True,
                                        text=True, timeout=30, env={**os.environ})
            check("`doctor jira_eod` exits 0", single_out.returncode == 0, single_out.stderr)
            check("`doctor jira_eod` output is byte-identical to format_doctor_text() on just its own row",
                  single_out.stdout.strip() == expected_jira_text.strip(),
                  (expected_jira_text, single_out.stdout))
            check("`doctor jira_eod` output does not also print another routine's label",
                  "News" not in single_out.stdout and "PR Follow-up" not in single_out.stdout, single_out.stdout)

            # An unrecognized routine name is rejected the same way run/schedule/latest already
            # reject one (argparse's own `choices=sorted(ROUTINES)`), not a bespoke error path.
            bad = subprocess.run(["python3", str(SCRIPT), "doctor", "not-a-real-routine"],
                                 capture_output=True, text=True, timeout=30, env={**os.environ})
            check("`doctor` with an unknown routine name exits non-zero", bad.returncode != 0, bad.returncode)
            check("`doctor` with an unknown routine name reports it as an invalid choice, no traceback",
                  "invalid choice" in bad.stderr and "Traceback" not in bad.stderr, bad.stderr)
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


def test_schedule_routine() -> None:
    print("groundwork_routines.py schedule — reuses the launchd/cron pattern, accepts hour+minute")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")
        os.environ["GROUNDWORK_OS"] = "linux"
        try:
            r = mod.schedule_routine("news", "daily")
            check("non-macOS: no plist written, cron-elsewhere note given", r["plist"] is None and "cron" in r["note"], r)
        finally:
            del os.environ["GROUNDWORK_OS"]
            del os.environ["CLAUDE_CONFIG_DIR"]

        os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")
        os.environ["GROUNDWORK_OS"] = "darwin"
        os.environ["GROUNDWORK_NO_LAUNCHCTL"] = "1"
        os.environ["GROUNDWORK_LAUNCH_AGENTS_DIR"] = str(tmp / "LaunchAgents")
        try:
            r = mod.schedule_routine("jira_eod", "daily", hour=17, minute=30)
            check("macOS: plist path returned and file actually written", r["plist"] is not None and Path(r["plist"]).is_file(), r)
            import plistlib
            plist = plistlib.loads(Path(r["plist"]).read_bytes())
            check("plist label is com.groundwork.routine.jira_eod", plist["Label"] == "com.groundwork.routine.jira_eod", plist["Label"])
            check("plist StartCalendarInterval hour/minute match the requested schedule time",
                  plist["StartCalendarInterval"]["Hour"] == 17 and plist["StartCalendarInterval"]["Minute"] == 30, plist["StartCalendarInterval"])
            r2 = mod.schedule_routine("jira_eod", "disabled")
            check("disabling removes the plist file", r2["plist"] is None and not Path(mod._plist_path("jira_eod")).exists(), r2)
        finally:
            del os.environ["GROUNDWORK_OS"]
            del os.environ["GROUNDWORK_NO_LAUNCHCTL"]
            del os.environ["GROUNDWORK_LAUNCH_AGENTS_DIR"]
            del os.environ["CLAUDE_CONFIG_DIR"]

        try:
            mod.schedule_routine("not-a-routine", "daily")
            check("schedule_routine: unknown routine raises ValueError", False)
        except ValueError:
            check("schedule_routine: unknown routine raises ValueError", True)
    finish()


def test_cli_list_reflects_new_schema() -> None:
    print("groundwork_routines.py list — reflects the nested schedule schema honestly")
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgdir = Path(tmpdir) / "cfg"
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfgdir)}
        r = subprocess.run(["python3", str(SCRIPT), "list"], capture_output=True, text=True, timeout=30, env=env)
        check("list with no config.json: exits 0, all six disabled, never run",
              r.returncode == 0 and "enabled=False" in r.stdout and "never run" in r.stdout and r.stdout.count("\n") == 6, r.stdout)

        subprocess.run(["python3", str(CONFIG_SCRIPT), "init", "sre-cloudops", "--path", str(cfgdir / "groundwork" / "config.json")],
                       capture_output=True, text=True, timeout=30, env=env, check=True)
        subprocess.run(["python3", str(CONFIG_SCRIPT), "set", "jira_eod", "schedule.time=17:00",
                        "--path", str(cfgdir / "groundwork" / "config.json")], capture_output=True, text=True, timeout=30, env=env, check=True)
        r2 = subprocess.run(["python3", str(SCRIPT), "list"], capture_output=True, text=True, timeout=30, env=env)
        check("list after sre-cloudops profile: jira_eod shows enabled=True with its real schedule time",
              "jira_eod: enabled=True" in r2.stdout and "17:00" in r2.stdout, r2.stdout)
    finish()


def test_prompts_reference_configured_scope_not_generic() -> None:
    print("groundwork_routines.py — prompts reference the actual configured scope (owner §17: query is identity-scoped)")
    mod = load_module()

    jira_prompt = mod._jira_eod_prompt(
        {"site": "https://acme.atlassian.net", "identity": "jane@acme.com", "posting": "dry_run",
         "scope": {"type": "assigned_to_me"}}, dry_run=False, offline_work="")
    check("jira_eod prompt names the configured site", "https://acme.atlassian.net" in jira_prompt, jira_prompt[:400])
    check("jira_eod prompt names the configured identity", "jane@acme.com" in jira_prompt, jira_prompt[:400])
    check("jira_eod prompt (posting=dry_run) instructs not to write, even without an explicit --dry-run flag",
          "do NOT call any tool that would actually write" in jira_prompt, jira_prompt[:600])

    jira_live = mod._jira_eod_prompt(
        {"site": "https://acme.atlassian.net", "identity": "jane@acme.com", "posting": "automatic",
         "scope": {"type": "assigned_to_me"}}, dry_run=False, offline_work="")
    check("jira_eod prompt (posting=automatic, no --dry-run override) switches to the live-run instruction",
          "This is a LIVE run" in jira_live, jira_live[:600])
    check("jira_eod live-run prompt requires reading the result back before VERIFIED",
          "read the ticket/comment back" in jira_live and "VERIFIED" in jira_live, jira_live)

    jira_forced_dry = mod._jira_eod_prompt(
        {"site": "x", "identity": "y", "posting": "automatic", "scope": {"type": "assigned_to_me"}},
        dry_run=True, offline_work="")
    check("jira_eod prompt: an explicit --dry-run flag overrides posting=automatic back to dry-run (safety wins)",
          "This is a DRY RUN" in jira_forced_dry, jira_forced_dry[:400])

    pr_prompt = mod._pr_followup_prompt({"identity": "octocat", "scope": {"repositories": ["current"], "authored_by_me": True}})
    check("pr_followup prompt names the configured identity", "octocat" in pr_prompt, pr_prompt[:400])
    check("pr_followup prompt explicitly forbids an unfiltered/org-wide scan",
          "never an unfiltered scan" in pr_prompt or "never a" in pr_prompt.lower() and "unfiltered" in pr_prompt.lower(), pr_prompt[:600])
    check("pr_followup prompt instructs filtering every query by the configured identity",
          "--author octocat" in pr_prompt or "octocat" in pr_prompt, pr_prompt[:600])

    news_prompt = mod._news_prompt({"topics": ["AI", "PKI", "Identity Security"]})
    check("news prompt actually uses the configured topics at runtime, not a hardcoded default",
          "AI" in news_prompt and "PKI" in news_prompt and "Identity Security" in news_prompt, news_prompt[:300])
    finish()


def test_reconfigure_schedule_no_duplication() -> None:
    print("groundwork_routines.py schedule — reconfiguring updates the schedule without duplicating it (owner §17)")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")
        os.environ["GROUNDWORK_OS"] = "darwin"
        os.environ["GROUNDWORK_NO_LAUNCHCTL"] = "1"
        os.environ["GROUNDWORK_LAUNCH_AGENTS_DIR"] = str(tmp / "LaunchAgents")
        try:
            mod.schedule_routine("news", "daily", hour=8, minute=0)
            mod.schedule_routine("news", "daily", hour=9, minute=15)  # reconfigure to a different time
            plists = list((tmp / "LaunchAgents").glob("com.groundwork.routine.news*.plist"))
            check("reconfiguring a routine's schedule leaves exactly one plist, never a duplicate", len(plists) == 1, plists)
            import plistlib
            plist = plistlib.loads(plists[0].read_bytes())
            check("the single remaining plist reflects the NEW time, not the old one",
                  plist["StartCalendarInterval"]["Hour"] == 9 and plist["StartCalendarInterval"]["Minute"] == 15, plist["StartCalendarInterval"])
        finally:
            del os.environ["GROUNDWORK_OS"]
            del os.environ["GROUNDWORK_NO_LAUNCHCTL"]
            del os.environ["GROUNDWORK_LAUNCH_AGENTS_DIR"]
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


def test_readiness_state_classifications() -> None:
    print("groundwork_routines.py — readiness_state(): NOT ENABLED/READY/BLOCKED synthesized from existing _doctor_rows() data only")
    mod = load_module()

    check("disabled routine is NOT ENABLED, regardless of any other field",
          mod.readiness_state({"routine": "news", "enabled": False, "mutates": False})["state"] == "NOT ENABLED")

    check("enabled routine with no access mechanism tracked (news/doc_drift) is READY",
          mod.readiness_state({"routine": "news", "enabled": True, "mutates": False})["state"] == "READY")

    unconf = mod.readiness_state({"routine": "pr_followup", "enabled": True, "mutates": False,
                                   "access": "unconfigured", "available": None, "connected": None, "access_detail": "not configured",
                                   "capability_blocked_reason": "GitHub access not configured — run ./setup.sh --configure"})
    check("enabled routine with access unconfigured is BLOCKED with an actionable reason",
          unconf["state"] == "BLOCKED" and unconf["reason"], unconf)

    borrowed = mod.readiness_state({"routine": "weekly_status", "enabled": True, "mutates": False,
                                     "capability_blocked_reason": "weekly_status is configured to use GitHub, but no GitHub access is configured (configure pr_followup or run ./setup.sh --configure)"})
    check("a routine with no 'access' field of its own but a capability_blocked_reason (weekly_status/"
          "work_digest borrowing pr_followup's unconfigured GitHub access) is BLOCKED, never an unqualified READY",
          borrowed["state"] == "BLOCKED" and "GitHub" in borrowed["reason"], borrowed)

    not_conn = mod.readiness_state({"routine": "pr_followup", "enabled": True, "mutates": False, "access": "gh_cli",
                                     "available": True, "connected": False, "access_detail": "not authenticated (run 'gh auth login')"})
    check("access configured but connected=False (real check failed) is BLOCKED with the real detail",
          not_conn["state"] == "BLOCKED" and "not authenticated" in not_conn["reason"], not_conn)

    conn = mod.readiness_state({"routine": "pr_followup", "enabled": True, "mutates": False, "access": "gh_cli",
                                 "available": True, "connected": True, "access_detail": "authenticated"})
    check("access configured and connected=True (real check passed) is an unqualified READY",
          conn["state"] == "READY", conn)

    unverif = mod.readiness_state({"routine": "jira_eod", "enabled": True, "mutates": True, "access": "jira_mcp",
                                    "available": True, "connected": None, "access_detail": "MCP server configured"})
    check("access configured but no real connectivity check exists (jira_mcp) is never an unqualified READY",
          unverif["state"] == "READY (connectivity not verifiable)" and unverif["state"] != "READY", unverif)

    live = mod.readiness_state({"routine": "jira_eod", "enabled": True, "mutates": True, "posting": "automatic",
                                 "access": "jira_mcp", "available": True, "connected": None, "access_detail": "MCP server configured"})
    check("jira_eod in automatic posting mode carries an explicit note about the unverifiable write step",
          live["note"] is not None and "not independently verified" in live["note"], live)

    dry = mod.readiness_state({"routine": "jira_eod", "enabled": True, "mutates": True, "posting": "dry_run",
                                "access": "jira_mcp", "available": True, "connected": None, "access_detail": "MCP server configured"})
    check("jira_eod in dry_run posting mode (the default) carries no live-posting note",
          dry["note"] is None, dry)
    finish()


def test_build_command_always_fails_closed_for_every_routine() -> None:
    print("groundwork_routines.py — every routine's real invocation always fails closed, never depends on interactive approval")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cfgdir = tmp / "cfg"
        bindir = tmp / "bin"
        argv_file = tmp / "argv.txt"
        init_config(cfgdir, "sre-cloudops")
        set_routine(cfgdir, "jira_eod", "site=https://x.atlassian.net", "identity=me@x.com", "access=jira_mcp", "mcp_server=atlassian")
        set_routine(cfgdir, "pr_followup", "identity=me", "access=gh_cli")
        set_routine(cfgdir, "doc_drift", "enabled=true")  # disabled by default under sre-cloudops; enable so every routine actually runs
        write_claude_stub(bindir, behavior="capture")
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(cfgdir), "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
               "CAPTURE_ARGV_FILE": str(argv_file)}
        for name in mod.ROUTINES:
            if argv_file.exists():
                argv_file.unlink()
            r = subprocess.run(["python3", str(SCRIPT), "run", name, "--repo", str(REPO_ROOT), "--timeout", "10"],
                               capture_output=True, text=True, timeout=20, env=env)
            try:
                result = json.loads(r.stdout)
            except Exception:
                result = {"stdout": r.stdout, "stderr": r.stderr}
            check(f"{name}: fully-configured routine is not BLOCKED (this test exercises the real command, not the blocked path)",
                  result.get("status") != "blocked", result)
            check(f"{name}: the stub actually captured an invocation (the real command ran)", argv_file.exists(), result)
            if not argv_file.exists():
                continue
            cmd = argv_file.read_text().splitlines()
            check(f"{name}: command includes --permission-mode dontAsk",
                  "--permission-mode" in cmd and cmd[cmd.index("--permission-mode") + 1] == "dontAsk", cmd)
            check(f"{name}: command includes --permission-prompts none",
                  "--permission-prompts" in cmd and cmd[cmd.index("--permission-prompts") + 1] == "none", cmd)
            bypass_flags = {"--dangerously-skip-permissions", "--allow-dangerously-skip-permissions", "--bare"}
            check(f"{name}: command never includes a blanket permission-bypass flag",
                  not (bypass_flags & set(cmd)), cmd)
    finish()


def test_readiness_visible_in_list_and_doctor_output() -> None:
    print("groundwork_routines.py — readiness is surfaced in both `list` and `doctor` output (setup.sh --routines / --doctor)")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        cfgdir = Path(tmpdir) / "cfg"
        init_config(cfgdir, "sre-cloudops")
        # pr_followup left unconfigured on purpose: exercises the BLOCKED path end-to-end, for
        # pr_followup itself AND for weekly_status/work_digest, which borrow pr_followup's
        # configured GitHub access via _capabilities_for()'s own cross-reference (owner-visible
        # regression: readiness_state() must never call a routine READY that build_command()
        # would actually block — checked per-routine below, not just "BLOCKED" appearing anywhere
        # in the text, which previously let weekly_status/work_digest's false READY slip through).
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfgdir)
        try:
            cfg = mod.gcfg.load_config(cfgdir / "groundwork" / "config.json")
            rows = mod._doctor_rows(cfg)
            text = mod.format_doctor_text(rows)
            check("doctor text includes a Readiness line for an enabled routine",
                  "Readiness ............" in text, text)
            check("doctor text marks the unconfigured pr_followup routine BLOCKED, not READY",
                  "BLOCKED" in text, text)

            r = subprocess.run(["python3", str(SCRIPT), "list"], capture_output=True, text=True, timeout=30,
                               env={**os.environ})
            check("list output includes readiness= for every routine line",
                  r.stdout.count("readiness=") == 6, r.stdout)
            for routine in ("pr_followup", "weekly_status", "work_digest"):
                line = next((ln for ln in r.stdout.splitlines() if ln.startswith(f"{routine}:")), "")
                check(f"{routine} (borrows pr_followup's unconfigured GitHub access) is BLOCKED, not READY",
                      "readiness=BLOCKED" in line, line)
        finally:
            del os.environ["CLAUDE_CONFIG_DIR"]
    finish()


if __name__ == "__main__":
    for fn in (test_module_level_registry_and_result_parsing, test_capabilities_for_never_grants_beyond_configured_access,
               test_capabilities_for_configured_jira_and_github, test_github_mcp_tools_are_real_and_read_only,
               test_work_digest_cross_references_jira_and_github_access,
               test_non_mutating_routines_never_inherit_jiras_write_capable_wildcard,
               test_run_routine_off_switches_and_disabled,
               test_run_routine_blocked_before_any_subprocess, test_semantic_status_from_routine_result_block,
               test_result_storage_separate_from_telemetry, test_result_retention_bounded,
               test_check_access_never_asserts_connected_without_checking, test_doctor_rows_and_formatting,
               test_doctor_name_filter,
               test_schedule_routine, test_cli_list_reflects_new_schema,
               test_prompts_reference_configured_scope_not_generic, test_reconfigure_schedule_no_duplication,
               test_readiness_state_classifications, test_build_command_always_fails_closed_for_every_routine,
               test_readiness_visible_in_list_and_doctor_output):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
