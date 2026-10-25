"""Fixtures: isolated Claude/Groundwork config, a stub `claude`, a small git repo, and an orchestrator home."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from groundwork_orchestrator import workspace  # noqa: E402
from groundwork_orchestrator.graph import Orchestrator  # noqa: E402

BUGGY_APP = "def add(a, b):\n    return a - b\n"
FIXED_APP = "def add(a, b):\n    return a + b\n"
CHECK = "import app\nassert app.add(2, 3) == 5, f'add(2, 3) returned {app.add(2, 3)}'\nprint('check ok')\n"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-config"))
    monkeypatch.setenv("GROUNDWORK_HOOKS_DIR", str(tmp_path / "no-hooks"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-must-not-reach-workers")
    monkeypatch.delenv("GROUNDWORK_ORCH_TELEMETRY", raising=False)


class Fake:
    def __init__(self, tmp: Path, monkeypatch):
        self.dir = tmp / "fake"
        self.dir.mkdir()
        self.plan_path, self.log = self.dir / "plan.json", self.dir / "calls.jsonl"
        self.log.touch()
        exe = self.dir / "claude"
        exe.write_text(f"#!/bin/sh\nexec {sys.executable} {HERE / 'fake_claude.py'} \"$@\"\n")
        exe.chmod(0o755)
        monkeypatch.setenv("GROUNDWORK_CLAUDE_BIN", str(exe))
        monkeypatch.setenv("FAKE_CLAUDE_PLAN", str(self.plan_path))
        monkeypatch.setenv("FAKE_CLAUDE_LOG", str(self.log))
        self.plan([{"result": {}}])

    def plan(self, steps: list[dict]) -> None:
        """Steps for the calls made from now on (calls already made are not counted)."""
        self.plan_path.write_text(json.dumps({"base": len(self.calls()), "steps": steps}))

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text().splitlines() if line.strip()]


@pytest.fixture
def fake(tmp_path, monkeypatch):
    return Fake(tmp_path, monkeypatch)


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    (r / "app.py").write_text(BUGGY_APP)
    (r / "check.py").write_text(CHECK)
    (r / "README.md").write_text("# demo\nA tiny calculator.\n")
    (r / ".gitignore").write_text("__pycache__/\n")
    git(r, "init", "-q", "-b", "main")
    git(r, "-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".")
    git(r, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "-m", "init")
    return r


@pytest.fixture
def home(tmp_path, repo):
    h = tmp_path / "orch-home"
    workspace.allow(h, str(repo))
    return h


@pytest.fixture
def orch(home):
    o = Orchestrator(home)
    yield o
    o.close()
