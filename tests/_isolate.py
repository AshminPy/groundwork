"""Imported first by every test file (and by conftest.py): guard and telemetry hooks run by the tests write their
signals.jsonl records to a temporary file, never to the real ~/.claude/groundwork/telemetry/signals.jsonl
(openspec/changes/add-accuracy-signals task 0.2). A test that needs its own path sets GROUNDWORK_SIGNALS_PATH itself;
subprocesses inherit this default through os.environ."""
import os
import tempfile

if not os.environ.get("GROUNDWORK_SIGNALS_PATH"):
    _dir = tempfile.mkdtemp(prefix="gw-test-signals-")
    os.environ["GROUNDWORK_SIGNALS_PATH"] = os.path.join(_dir, "signals.jsonl")
