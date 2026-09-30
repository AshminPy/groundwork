#!/usr/bin/env python3
"""Deterministic checks for scripts/groundwork_integrations.py (Groundwork 2.1) — the Integration
Catalog: structured catalog data, independent available/configured/connected observations (never
collapsed into a forced lifecycle), the derived display-only summary label, the separate `used`
observation read from existing telemetry, and the CLI (`list`/`show`).

Run: python3 tests/test_groundwork_integrations.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import json
import os
import stat
import sys
import tempfile
from io import StringIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "groundwork_integrations.py"
DOC = REPO_ROOT / "docs" / "INTEGRATIONS.md"

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
    spec = importlib.util.spec_from_file_location("gw_integrations", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub_bin(dirpath: Path, name: str, exit_code: int, sleep_s: float = 0) -> None:
    """Writes an executable shell stub standing in for a real CLI binary — same technique
    test_groundwork_routines.py uses for gh/claude, prepended onto PATH by the caller."""
    script = dirpath / name
    body = "#!/bin/sh\n"
    if sleep_s:
        body += f"sleep {sleep_s}\n"
    body += f"exit {exit_code}\n"
    script.write_text(body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _capture(fn, *a, **kw) -> str:
    old = sys.stdout
    sys.stdout = StringIO()
    try:
        fn(*a, **kw)
        return sys.stdout.getvalue()
    finally:
        sys.stdout = old


# ---------------------------------------------------------------------------------------------
def test_catalog_structural_validity() -> None:
    print("groundwork_integrations.py — every catalog entry has the required fields")
    mod = load_module()
    for entry in mod.CATALOG:
        check(f"{entry.name}: non-empty name", bool(entry.name.strip()), entry)
        check(f"{entry.name}: at least one capability id", len(entry.capabilities) >= 1, entry)
        check(f"{entry.name}: at least one typed access mechanism", len(entry.mechanisms) >= 1, entry)
        check(f"{entry.name}: mechanism types are all mcp/cli/api",
              all(m.type in ("mcp", "cli", "api") for m in entry.mechanisms), entry.mechanisms)
        check(f"{entry.name}: non-empty trust/access description", bool(entry.trust.strip()), entry)
    names = [e.name for e in mod.CATALOG]
    check("no duplicate integration names", len(names) == len(set(names)), names)
    finish()


def test_summary_state_combinations() -> None:
    print("groundwork_integrations.py — summary_state(): the 5 required available/configured/connected combinations")
    mod = load_module()
    Obs = mod.IntegrationObservation
    cases = [
        (Obs(available=False, configured=False, connected=False, used=None), "NOT CONFIGURED"),
        (Obs(available=True, configured=False, connected=False, used=None), "AVAILABLE"),
        (Obs(available=False, configured=True, connected=False, used=None), "CONFIGURED"),
        (Obs(available=True, configured=True, connected=False, used=None), "CONFIGURED"),
        (Obs(available=True, configured=True, connected=True, used=None), "CONNECTED"),
    ]
    for obs, expected in cases:
        check(f"available={obs.available},configured={obs.configured},connected={obs.connected} -> {expected}",
              mod.summary_state(obs) == expected, mod.summary_state(obs))
    # The specific case the owner called out: configured=true while available=false must be
    # preserved, never forced to match — summary_state must not silently promote or demote it.
    kube_like = Obs(available=False, configured=True, connected=False, used=None)
    check("configured-without-available is preserved as independent facts, not collapsed",
          kube_like.available is False and kube_like.configured is True, kube_like)
    finish()


def test_presence_alone_never_yields_connected() -> None:
    print("groundwork_integrations.py — presence (mcp listed or cli on PATH) alone never sets connected=True")
    mod = load_module()
    entry = next(e for e in mod.CATALOG if e.name == "GitHub")

    # (a) mcp mechanism "present" (claude mcp list lists it), but that alone never checks
    # connectivity — connected must stay False.
    mod._mcp_list_cache = "github  connected"
    mod._mcp_list_attempted = True
    try:
        mech = next(m for m in entry.mechanisms if m.type == "mcp")
        check("mcp server listed => available True", mod._mechanism_available(mech) is True)
        check("mcp presence alone never implies connected", mod._mechanism_connected(mech) is False)
    finally:
        mod._mcp_list_cache = None
        mod._mcp_list_attempted = False

    # (b) cli binary present on PATH, but with no auth check defined for it, connected stays False.
    with tempfile.TemporaryDirectory() as tmpdir:
        _stub_bin(Path(tmpdir), "spacectl", 0)
        old_path = os.environ.get("PATH")
        os.environ["PATH"] = tmpdir
        try:
            spacelift = next(e for e in mod.CATALOG if e.name == "Spacelift")
            cli_mech = next(m for m in spacelift.mechanisms if m.type == "cli")
            check("spacectl on PATH => available True", mod._mechanism_available(cli_mech) is True)
            check("no cli_auth_cmd defined => connected stays False even though available",
                  mod._mechanism_connected(cli_mech) is False)
        finally:
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path
    finish()


def test_successful_real_check_yields_connected() -> None:
    print("groundwork_integrations.py — a real check that succeeds sets connected=True")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        _stub_bin(Path(tmpdir), "gh", 0)
        old_path = os.environ.get("PATH")
        os.environ["PATH"] = tmpdir
        try:
            github = next(e for e in mod.CATALOG if e.name == "GitHub")
            cli_mech = next(m for m in github.mechanisms if m.type == "cli")
            check("gh present and 'gh auth status' stub succeeds => connected True",
                  mod._mechanism_connected(cli_mech) is True)
            cfg = {}
            mod._mcp_list_cache, mod._mcp_list_attempted = "", True
            try:
                obs = mod.determine_observation(github, cfg)
                check("end-to-end determine_observation reflects the successful check",
                      obs.available is True and obs.connected is True, obs)
                check("summary_state is CONNECTED for a real successful check", mod.summary_state(obs) == "CONNECTED")
            finally:
                mod._mcp_list_cache, mod._mcp_list_attempted = None, False
        finally:
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path
    finish()


def test_failed_check_never_yields_connected() -> None:
    print("groundwork_integrations.py — a real check that fails (or the binary is missing) never sets connected=True")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        _stub_bin(Path(tmpdir), "gh", 1)  # exits non-zero: auth failed
        old_path = os.environ.get("PATH")
        os.environ["PATH"] = tmpdir
        try:
            github = next(e for e in mod.CATALOG if e.name == "GitHub")
            cli_mech = next(m for m in github.mechanisms if m.type == "cli")
            check("gh present but 'gh auth status' stub fails => connected False",
                  mod._mechanism_connected(cli_mech) is False)
        finally:
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path

    old_path = os.environ.get("PATH")
    os.environ["PATH"] = "/nonexistent-empty-bin"
    try:
        github = next(e for e in mod.CATALOG if e.name == "GitHub")
        cli_mech = next(m for m in github.mechanisms if m.type == "cli")
        check("gh missing entirely => available False, connected False, no crash",
              mod._mechanism_available(cli_mech) is False and mod._mechanism_connected(cli_mech) is False)
    finally:
        if old_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = old_path
    finish()


def test_timeout_never_yields_connected() -> None:
    print("groundwork_integrations.py — a check that times out never sets connected=True")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        _stub_bin(Path(tmpdir), "gh", 0, sleep_s=5)
        old_path = os.environ.get("PATH")
        old_timeout = mod.CLI_AUTH_TIMEOUT_S
        # Prepend (not replace) PATH: the stub script's own `sleep` call must still resolve.
        os.environ["PATH"] = tmpdir + os.pathsep + (old_path or "")
        mod.CLI_AUTH_TIMEOUT_S = 0.5  # shrink the timeout so the test stays fast
        try:
            github = next(e for e in mod.CATALOG if e.name == "GitHub")
            cli_mech = next(m for m in github.mechanisms if m.type == "cli")
            check("a hanging check times out safely and never sets connected=True",
                  mod._mechanism_connected(cli_mech) is False)
        finally:
            mod.CLI_AUTH_TIMEOUT_S = old_timeout
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path
    finish()


def test_malformed_or_missing_config_fails_safe() -> None:
    print("groundwork_integrations.py — malformed or missing config.json fails safe, never crashes")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "groundwork" / "config.json"
        cfg_path.parent.mkdir(parents=True)
        cfg_path.write_text("{not valid json")
        old = mod.CONFIG_PATH
        mod.CONFIG_PATH = cfg_path
        try:
            cfg = mod._load_config()
            check("malformed config.json yields {} rather than raising", cfg == {}, cfg)
            github = next(e for e in mod.CATALOG if e.name == "GitHub")
            obs = mod.determine_observation(github, cfg)
            check("determine_observation on malformed config doesn't crash and reports configured=False",
                  obs.configured is False, obs)
        finally:
            mod.CONFIG_PATH = old

    # Missing file entirely
    old = mod.CONFIG_PATH
    mod.CONFIG_PATH = Path(tempfile.mkdtemp()) / "does-not-exist" / "config.json"
    try:
        cfg = mod._load_config()
        check("missing config.json yields {} rather than raising", cfg == {}, cfg)
    finally:
        mod.CONFIG_PATH = old
    finish()


def test_used_observation() -> None:
    print("groundwork_integrations.py — used: true only with reliable telemetry, unknown without it, never guessed")
    mod = load_module()
    github = next(e for e in mod.CATALOG if e.name == "GitHub")
    prometheus = next(e for e in mod.CATALOG if e.name == "Prometheus")

    # No telemetry file at all -> unknown (None)
    old = mod.TELEMETRY_PATH
    mod.TELEMETRY_PATH = Path(tempfile.mkdtemp()) / "does-not-exist" / "events.jsonl"
    try:
        check("no telemetry file => used is unknown (None)", mod.determine_used(github) is None)
    finally:
        mod.TELEMETRY_PATH = old

    with tempfile.TemporaryDirectory() as tmpdir:
        events = Path(tmpdir) / "events.jsonl"
        events.write_text(json.dumps({"observed": {"mcp_servers": ["github", "jira"]}}) + "\n")
        old = mod.TELEMETRY_PATH
        mod.TELEMETRY_PATH = events
        try:
            check("most recent record lists the mcp server => used True", mod.determine_used(github) is True)
        finally:
            mod.TELEMETRY_PATH = old

    with tempfile.TemporaryDirectory() as tmpdir:
        events = Path(tmpdir) / "events.jsonl"
        events.write_text(json.dumps({"observed": {"mcp_servers": ["jira"]}}) + "\n")
        old = mod.TELEMETRY_PATH
        mod.TELEMETRY_PATH = events
        try:
            check("most recent record has a reliable mcp_servers list without this one => used False",
                  mod.determine_used(github) is False)
        finally:
            mod.TELEMETRY_PATH = old

        # A CLI/API-only integration (no mcp mechanism at all) can never get a reliable used signal.
        old = mod.TELEMETRY_PATH
        mod.TELEMETRY_PATH = events
        try:
            check("integration with no MCP mechanism => used is always unknown (None), never guessed",
                  mod.determine_used(prometheus) is None)
        finally:
            mod.TELEMETRY_PATH = old
    finish()


def test_list_command() -> None:
    print("groundwork_integrations.py — list: every catalog integration appears exactly once")
    mod = load_module()
    out = _capture(mod._cmd_list, None)
    lines = [l for l in out.splitlines() if l.strip()]
    for entry in mod.CATALOG:
        matches = [l for l in lines if l.startswith(entry.name + " ") or l.split()[0:1] == [entry.name]]
        check(f"list output includes {entry.name} exactly once",
              sum(1 for l in lines if l.split(None, 1)[0] == entry.name) == 1, out)
    finish()


def test_show_command() -> None:
    print("groundwork_integrations.py — show: known integration includes required fields; unknown fails clean")
    mod = load_module()

    class Args:
        name = "github"

    out = _capture(mod._cmd_show, Args())
    for label in ("Purpose", "Capabilities", "Approved access", "Configuration",
                  "Available", "Configured", "Connected", "Used", "Summary state"):
        check(f"show output includes '{label}'", label in out, out)

    class UnknownArgs:
        name = "totally-not-a-real-integration"

    old = sys.stdout
    sys.stdout = StringIO()
    try:
        rc = mod._cmd_show(UnknownArgs())
        out2 = sys.stdout.getvalue()
    finally:
        sys.stdout = old
    check("unknown integration name returns non-zero exit, no traceback", rc == 1, rc)
    check("unknown integration name reports 'not a known integration'", "not a known integration" in out2, out2)
    finish()


def test_routines_dependency_is_deterministic() -> None:
    print("groundwork_integrations.py — Used by Routines only lists a Routine whose stored config explicitly declares that mechanism")
    mod = load_module()
    github = next(e for e in mod.CATALOG if e.name == "GitHub")
    jira = next(e for e in mod.CATALOG if e.name == "Jira")
    kubernetes = next(e for e in mod.CATALOG if e.name == "Kubernetes")
    cfg = {"routines": {"pr_followup": {"access": "gh_cli"}, "jira_eod": {"access": "jira_mcp"}}}
    check("pr_followup (access=gh_cli) is listed for GitHub", "pr_followup" in mod._routines_using(github, cfg), cfg)
    check("jira_eod is not listed for GitHub", "jira_eod" not in mod._routines_using(github, cfg), cfg)
    check("jira_eod (access=jira_mcp) is listed for Jira", "jira_eod" in mod._routines_using(jira, cfg), cfg)
    check("Kubernetes has no routine_access_values declared, so nothing is ever inferred for it",
          mod._routines_using(kubernetes, cfg) == [], mod._routines_using(kubernetes, cfg))

    for access_value in ("cli", "browser"):
        cfg_alt = {"routines": {"jira_eod": {"access": access_value}}}
        check(f"jira_eod (access={access_value}) is also listed for Jira",
              "jira_eod" in mod._routines_using(jira, cfg_alt), cfg_alt)
    finish()


def test_no_secret_exposure() -> None:
    print("groundwork_integrations.py — no command output ever echoes a secret-shaped config value")
    mod = load_module()
    planted_secret = "ghp_FAKESECRETVALUE1234567890abcdefgh"
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "groundwork" / "config.json"
        cfg_path.parent.mkdir(parents=True)
        cfg_path.write_text(json.dumps({
            "integrations": ["github"],
            "routines": {"pr_followup": {"access": "gh_cli", "token": planted_secret}},
        }))
        old = mod.CONFIG_PATH
        mod.CONFIG_PATH = cfg_path
        try:
            list_out = _capture(mod._cmd_list, None)

            class Args:
                name = "github"

            show_out = _capture(mod._cmd_show, Args())
            check("planted secret value never appears in list output", planted_secret not in list_out, list_out)
            check("planted secret value never appears in show output", planted_secret not in show_out, show_out)
        finally:
            mod.CONFIG_PATH = old
    finish()


def test_doc_consistency_with_integrations_md() -> None:
    print("groundwork_integrations.py — every catalog integration name has a corresponding row in docs/INTEGRATIONS.md")
    mod = load_module()
    doc_text = DOC.read_text()
    for entry in mod.CATALOG:
        check(f"docs/INTEGRATIONS.md mentions '{entry.name}'", entry.name in doc_text, entry.name)
    finish()


if __name__ == "__main__":
    for fn in (test_catalog_structural_validity, test_summary_state_combinations,
               test_presence_alone_never_yields_connected, test_successful_real_check_yields_connected,
               test_failed_check_never_yields_connected, test_timeout_never_yields_connected,
               test_malformed_or_missing_config_fails_safe, test_used_observation,
               test_list_command, test_show_command, test_routines_dependency_is_deterministic,
               test_no_secret_exposure, test_doc_consistency_with_integrations_md):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
