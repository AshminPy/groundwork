#!/usr/bin/env python3
"""Deterministic checks for scripts/groundwork_config.py (Groundwork 2.1) — the capability/Routines
config file setup.sh's optional flow writes and reads.

Run: python3 tests/test_groundwork_config.py   (or: python3 -m pytest tests -q)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "groundwork_config.py"

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
    spec = importlib.util.spec_from_file_location("gw_config", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_cli(args, env_extra=None, timeout=30) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(["python3", str(SCRIPT), *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


def test_default_config_and_validate() -> None:
    print("groundwork_config.py — default_config()/validate_config() for every profile")
    mod = load_module()
    for profile in mod.PROFILES:
        cfg = mod.default_config(profile)
        problems = mod.validate_config(cfg)
        check(f"{profile}: default_config() is valid (no problems)", problems == [], problems)
        check(f"{profile}: profile field round-trips", cfg["profile"] == profile)
        check(f"{profile}: every known routine present with an 'enabled' bool", set(cfg["routines"]) == mod.KNOWN_ROUTINES and all(isinstance(r["enabled"], bool) for r in cfg["routines"].values()), cfg["routines"])
        check(f"{profile}: news topics only present when news is enabled", (cfg["routines"]["news"]["topics"] != []) == cfg["routines"]["news"]["enabled"], cfg["routines"]["news"])

    minimal = mod.default_config("minimal")
    check("minimal profile: no cloud/platform/integrations selected", minimal["cloud"] == [] and minimal["platform"] == [] and minimal["integrations"] == [])
    check("minimal profile: every routine disabled", not any(r["enabled"] for r in minimal["routines"].values()), minimal["routines"])
    check("minimal profile: every skill disabled", not any(minimal["skills"].values()), minimal["skills"])

    unknown = mod.default_config("not-a-real-profile")
    check("unknown profile name falls back to minimal's shape (fail-open, not a crash)", unknown["cloud"] == [] and not any(unknown["routines"][n]["enabled"] for n in mod.KNOWN_ROUTINES))
    finish()


def test_validate_config_catches_problems() -> None:
    print("groundwork_config.py — validate_config() flags real problems, never silently drops them")
    mod = load_module()
    check("not a dict -> flagged", mod.validate_config([1, 2, 3]) != [])
    check("unknown cloud value flagged", any("unknown value" in p for p in mod.validate_config({"cloud": ["not-a-real-cloud"]})))
    check("unknown platform value flagged", any("unknown value" in p for p in mod.validate_config({"platform": ["not-a-real-platform"]})))
    check("unknown integration value flagged", any("unknown value" in p for p in mod.validate_config({"integrations": ["not-a-real-integration"]})))
    check("cloud as non-list flagged", any("must be a list" in p for p in mod.validate_config({"cloud": "gcp"})))
    check("unknown routine name flagged", any("unknown routine" in p for p in mod.validate_config({"routines": {"not-a-real-routine": {"enabled": True}}})))
    check("routines as non-dict flagged", any("routines must be an object" in p for p in mod.validate_config({"routines": ["x"]})))
    for secret_key in ("token", "password", "secret", "api_key", "credential"):
        problems = mod.validate_config({"jira_token": "abc123"} if secret_key == "token" else {secret_key: "x"})
        check(f"config containing a '{secret_key}'-like key is flagged (never store credentials here)",
              any("credentials" in p for p in problems), problems)
    check("a genuinely valid config has zero problems", mod.validate_config(mod.default_config("sre-cloudops")) == [])
    finish()


def test_load_save_roundtrip_and_fail_open() -> None:
    print("groundwork_config.py — load_config()/save_config() round-trip, fail-open on missing/corrupt files")
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.json"
        check("load_config() on a missing file falls back to the minimal profile, never raises",
              mod.load_config(path)["profile"] == "minimal")

        cfg = mod.default_config("devops")
        mod.save_config(cfg, path)
        check("save_config() writes the file", path.is_file())
        loaded = mod.load_config(path)
        check("load_config() round-trips exactly what was saved", loaded == cfg, loaded)
        check("saved file is pretty-printed JSON (human-readable, matches Groundwork's other config files)",
              "\n" in path.read_text() and path.read_text().endswith("\n"))

        path.write_text("{ not valid json ][")
        check("load_config() on corrupt JSON falls back to minimal, never raises", mod.load_config(path)["profile"] == "minimal")

        path.write_text(json.dumps([1, 2, 3]))
        check("load_config() on valid JSON that isn't an object falls back to minimal", mod.load_config(path)["profile"] == "minimal")
    finish()


def test_default_path_respects_claude_config_dir() -> None:
    print("groundwork_config.py — DEFAULT_PATH respects CLAUDE_CONFIG_DIR (regression: 2.1 doctor/routines bug)")
    # Before the fix, DEFAULT_PATH was a bare Path.home()/.claude/... constant that ignored
    # CLAUDE_CONFIG_DIR entirely — setup.sh's apply_capabilities() (which calls this CLI without
    # --path) would silently write config.json into the real ~/.claude even when CLAUDE_CONFIG_DIR
    # pointed somewhere else (as setup.sh's own tests, and any non-default install, do). Confirmed
    # live: a real sandboxed setup.sh --non-interactive --capability-profile sre-cloudops run wrote
    # to /root/.claude/groundwork/config.json instead of the target config dir, and setup.sh's own
    # "routines enabled: ..." summary silently read back 'none' because it looked in the (correct,
    # but never-written) target path. This test pins the fix at the module level, independent of
    # setup.sh's own control flow.
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "target-config-dir"
        other = Path(tmpdir) / "must-not-be-touched"
        old_home_marker = other / "groundwork" / "config.json"

        r = run_cli(["init", "sre-cloudops"], env_extra={"CLAUDE_CONFIG_DIR": str(target)})
        check("`init` with no --path, under CLAUDE_CONFIG_DIR, exits 0", r.returncode == 0, r.stdout + r.stderr)
        check("`init` wrote config.json under CLAUDE_CONFIG_DIR, not elsewhere",
              (target / "groundwork" / "config.json").is_file(), list(target.rglob("*")))
        check("nothing was written under the unrelated 'other' dir", not old_home_marker.exists())

        r2 = run_cli(["show"], env_extra={"CLAUDE_CONFIG_DIR": str(target)})
        check("`show` with no --path, under the same CLAUDE_CONFIG_DIR, reads back what `init` wrote",
              r2.returncode == 0 and json.loads(r2.stdout)["profile"] == "sre-cloudops", r2.stdout)

        r3 = run_cli(["validate"], env_extra={"CLAUDE_CONFIG_DIR": str(target)})
        check("`validate` with no --path finds the same file and reports it valid", r3.returncode == 0 and "valid" in r3.stdout, r3.stdout)
    finish()


def test_cli_init_show_validate() -> None:
    print("groundwork_config.py — CLI: init/show/profiles/validate")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.json"

        r = run_cli(["profiles"])
        check("`profiles` exits 0 and lists all 8 profiles", r.returncode == 0 and r.stdout.count("\n") == 8, r.stdout)

        r = run_cli(["init", "minimal", "--path", str(path)])
        check("`init minimal` exits 0 and writes the file", r.returncode == 0 and path.is_file(), r.stdout + r.stderr)

        r2 = run_cli(["init", "sre-cloudops", "--path", str(path)])
        check("`init` again without --force refuses to overwrite (exit 1)", r2.returncode == 1, r2.stdout + r2.stderr)
        check("refused init left the original minimal config untouched",
              json.loads(path.read_text())["profile"] == "minimal")

        r3 = run_cli(["init", "sre-cloudops", "--path", str(path), "--force"])
        check("`init --force` overwrites (exit 0)", r3.returncode == 0, r3.stdout + r3.stderr)
        check("forced init actually replaced the profile", json.loads(path.read_text())["profile"] == "sre-cloudops")

        r4 = run_cli(["show", "--path", str(path)])
        check("`show` prints the current config as JSON", r4.returncode == 0 and json.loads(r4.stdout)["profile"] == "sre-cloudops", r4.stdout)

        r5 = run_cli(["init", "not-a-real-profile", "--path", str(Path(tmpdir) / "other.json")])
        check("`init` with an unknown profile name is refused, exit 1", r5.returncode == 1, r5.stdout + r5.stderr)

        r6 = run_cli(["validate", "--path", str(path)])
        check("`validate` on the valid file exits 0", r6.returncode == 0 and "valid" in r6.stdout, r6.stdout)

        missing = Path(tmpdir) / "does-not-exist.json"
        r7 = run_cli(["validate", "--path", str(missing)])
        check("`validate` on a missing file is not an error (falls back to minimal profile)", r7.returncode == 0, r7.stdout + r7.stderr)

        bad = Path(tmpdir) / "bad.json"
        bad.write_text("not json at all {{{")
        r8 = run_cli(["validate", "--path", str(bad)])
        check("`validate` on invalid JSON exits 1 with a clear message", r8.returncode == 1 and "invalid JSON" in r8.stderr, r8.stdout + r8.stderr)

        bad2 = Path(tmpdir) / "bad2.json"
        bad2.write_text(json.dumps({"cloud": ["not-real"], "github_token": "leaked"}))
        r9 = run_cli(["validate", "--path", str(bad2)])
        check("`validate` on a config with an unknown value AND a secret-like key exits 1 and reports both",
              r9.returncode == 1 and "unknown value" in r9.stderr and "credentials" in r9.stderr, r9.stderr)
    finish()


def test_never_stores_secrets_by_construction() -> None:
    print("groundwork_config.py — the shipped default configs never contain secret-like keys, for every profile")
    mod = load_module()
    for profile in mod.PROFILES:
        cfg = mod.default_config(profile)
        blob = json.dumps(cfg).lower()
        for secret_word in ("token", "password", "secret", "api_key", "credential"):
            check(f"{profile}: default config has no '{secret_word}'-like content", secret_word not in blob, blob)
    finish()


if __name__ == "__main__":
    for fn in (test_default_config_and_validate, test_validate_config_catches_problems,
               test_load_save_roundtrip_and_fail_open, test_default_path_respects_claude_config_dir,
               test_cli_init_show_validate, test_never_stores_secrets_by_construction):
        try:
            fn()
        except AssertionError:
            pass
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
