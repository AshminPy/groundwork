"""Group 2 (tasks 2.1–2.4): plugin skeleton, settings profiles, `gw profile`, `gw doctor`.

Run: python3 -m pytest plugin/tests -q
"""
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gwlib import doctor, profile  # noqa: E402

# Keys confirmed against the settings and sandboxing docs in Phase 0 (phase0-results.md §1.5, design D1).
CONFIRMED_KEYS = {
    "permissions.defaultMode", "permissions.deny", "permissions.additionalDirectories",
    "sandbox.enabled", "sandbox.failIfUnavailable", "sandbox.allowUnsandboxedCommands",
    "sandbox.filesystem.allowWrite", "sandbox.filesystem.denyWrite", "sandbox.filesystem.denyRead",
    "sandbox.filesystem.allowRead", "model", "effortLevel", "env", "statusLine",
}


def leaf_keys(d, prefix=""):
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict) and path != "env":
            yield from leaf_keys(v, path)
        else:
            yield path


# --- 2.1 skeleton -------------------------------------------------------------------------------------------------

def test_manifest_and_layout():
    m = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert m["name"] == "groundwork"
    assert m["version"] == "3.0.0-alpha.1"
    assert m["author"]["name"]
    assert set(m["userConfig"]) == {"vault_path", "profile"}
    assert not (ROOT / "bin").exists(), "a bin/ folder stops claude.ai and Cowork installing the plugin"
    assert json.loads((ROOT / "components.json").read_text())["format"] == 1


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_plugin_validate_strict():
    r = subprocess.run(["claude", "plugin", "validate", "--strict", str(ROOT)], capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


# --- 2.2 profiles -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", profile.PROFILES)
def test_profile_keys_are_confirmed(name):
    doc = profile.load_profile(name)
    keys = set(leaf_keys(doc["settings"]))
    assert keys <= CONFIRMED_KEYS, keys - CONFIRMED_KEYS
    s = doc["settings"]
    assert s["permissions"]["defaultMode"] == "auto"
    assert s["sandbox"]["enabled"] and s["sandbox"]["failIfUnavailable"]
    assert s["sandbox"]["allowUnsandboxedCommands"] is False
    assert s["env"]["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"] == "1"
    assert doc["config_dir"].endswith(name), "each profile has its own config directory"


def test_profiles_never_target_the_default_config_dir():
    for name in profile.PROFILES:
        assert profile.config_dir(profile.load_profile(name), None) != Path(os.path.expanduser("~/.claude"))


# --- 2.3 profile apply / revert -----------------------------------------------------------------------------------

def yes(_):
    return True


def no(_):
    return False


def test_apply_without_approval_writes_nothing(tmp_path):
    out = io.StringIO()
    assert profile.apply("work", str(tmp_path), "/v", confirm=no, out=out) == 3
    assert not any(tmp_path.iterdir())
    assert "owner approval is required" in out.getvalue()


def test_tty_confirm_refuses_without_a_terminal(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("apply\n"))
    assert profile.tty_confirm("? ") is False


def test_apply_merges_and_keeps_user_keys(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"theme": "dark", "permissions": {"deny": ["Bash(rm -rf *)"]}}))
    assert profile.apply("work", str(tmp_path), str(tmp_path / "vault"), confirm=yes, out=io.StringIO()) == 0
    s = json.loads(target.read_text())
    assert s["theme"] == "dark"
    assert s["permissions"]["deny"][0] == "Bash(rm -rf *)" and "Read(~/.ssh/**)" in s["permissions"]["deny"]
    assert s["sandbox"]["filesystem"]["allowWrite"] == [str(tmp_path / "vault")]
    assert profile.apply("work", str(tmp_path), str(tmp_path / "vault"), confirm=yes, out=io.StringIO()) == 0
    assert json.loads(target.read_text()) == s, "applying twice changes nothing"


def test_missing_vault_drops_the_placeholder(tmp_path):
    profile.apply("work", str(tmp_path), None, confirm=yes, out=io.StringIO())
    s = json.loads((tmp_path / "settings.json").read_text())
    assert "allowWrite" in s["sandbox"]["filesystem"] and s["sandbox"]["filesystem"]["allowWrite"] == []
    assert "${VAULT}" not in (tmp_path / "settings.json").read_text()


def test_revert_restores_byte_for_byte(tmp_path):
    target = tmp_path / "settings.json"
    original = b'{"theme":"dark",  "odd":   "spacing"}\n'
    target.write_bytes(original)
    os.chmod(target, 0o600)
    profile.apply("personal", str(tmp_path), None, confirm=yes, out=io.StringIO())
    assert target.read_bytes() != original
    assert profile.revert("personal", str(tmp_path), out=io.StringIO()) == 0
    assert target.read_bytes() == original
    assert (target.stat().st_mode & 0o777) == 0o600


def test_revert_after_two_applies_returns_to_the_original(tmp_path):
    target = tmp_path / "settings.json"
    original = b'{"theme": "light"}\n'
    target.write_bytes(original)
    profile.apply("work", str(tmp_path), str(tmp_path / "v1"), confirm=yes, out=io.StringIO())
    profile.apply("work", str(tmp_path), str(tmp_path / "v2"), confirm=yes, out=io.StringIO())
    profile.revert("work", str(tmp_path), out=io.StringIO())
    assert target.read_bytes() == original


def test_revert_removes_a_file_that_did_not_exist(tmp_path):
    profile.apply("work", str(tmp_path), None, confirm=yes, out=io.StringIO())
    profile.revert("work", str(tmp_path), out=io.StringIO())
    assert not (tmp_path / "settings.json").exists()


def test_cli_apply_refuses_without_tty(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gw"), "profile", "apply", "work", "--config-dir",
                        str(tmp_path)], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert r.returncode == 3 and not (tmp_path / "settings.json").exists()


# --- 2.4 doctor ---------------------------------------------------------------------------------------------------

def tree(p: Path):
    return {str(f.relative_to(p)): f.read_bytes() for f in p.rglob("*") if f.is_file()}


def test_doctor_reports_drift_with_fix_and_changes_nothing(tmp_path):
    profile.apply("work", str(tmp_path), None, confirm=yes, out=io.StringIO())
    s = json.loads((tmp_path / "settings.json").read_text())
    s["permissions"]["defaultMode"] = "default"
    (tmp_path / "settings.json").write_text(json.dumps(s))
    before = tree(tmp_path)
    out = io.StringIO()
    rc = doctor.run({"config_dirs": {"work": str(tmp_path), "personal": str(tmp_path / "none")},
                     "env": {"TMPDIR": "/tmp"}}, out=out)
    assert rc == 1
    assert "permissions.defaultMode differs" in out.getvalue() and "gw profile apply work" in out.getvalue()
    assert tree(tmp_path) == before


def test_doctor_flags_long_tmpdir():
    out = io.StringIO()
    doctor.run({"config_dirs": {"work": "/nonexistent-w", "personal": "/nonexistent-p"},
                "env": {"TMPDIR": "/tmp/" + "x" * 80}}, out=out)
    assert "TMPDIR is" in out.getvalue() and "export TMPDIR=/tmp" in out.getvalue()


def test_doctor_reports_missing_openspec(monkeypatch):
    def boom(*a, **k):
        raise OSError("not found")
    monkeypatch.setattr(doctor.subprocess, "run", boom)
    out = io.StringIO()
    doctor.run({"config_dirs": {"work": "/nonexistent-w", "personal": "/nonexistent-p"}, "env": {}}, out=out)
    assert "OpenSpec CLI not found" in out.getvalue() and "@fission-ai/openspec@" in out.getvalue()


def test_doctor_reports_bad_version(tmp_path):
    root = tmp_path / "plugin"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    m = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
    m["version"] = "three"
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(m))
    out = io.StringIO()
    doctor.run({"root": root, "config_dirs": {"work": "/nonexistent-w", "personal": "/nonexistent-p"},
                "env": {}}, out=out)
    assert "is not semver" in out.getvalue()


# --- 2.5 README commands ------------------------------------------------------------------------------------------

def test_readme_commands_run_on_a_clean_config_dir(tmp_path):
    readme = (ROOT / "README.md").read_text()
    for cmd in ("gw profile diff work", "gw profile apply work", "gw profile revert work", "gw doctor"):
        assert cmd in readme
    gw = [sys.executable, str(ROOT / "scripts" / "gw")]
    cfg = str(tmp_path / "cfg")
    r = subprocess.run(gw + ["profile", "diff", "work", "--config-dir", cfg, "--vault", str(tmp_path / "v")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and '"defaultMode": "auto"' in r.stdout
    r = subprocess.run(gw + ["profile", "apply", "work", "--config-dir", cfg], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True)
    assert r.returncode == 3, "apply without a terminal must refuse"
    r = subprocess.run(gw + ["profile", "revert", "work", "--config-dir", cfg], capture_output=True, text=True)
    assert r.returncode == 1 and "nothing to revert" in r.stdout
    r = subprocess.run(gw + ["doctor"], capture_output=True, text=True, env={**os.environ, "TMPDIR": "/tmp"})
    assert r.returncode in (0, 1) and ("No problems found." in r.stdout or "problem(s) found." in r.stdout)
    assert not Path(cfg).exists(), "none of the read-only commands may create the config dir"
