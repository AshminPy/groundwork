import csv
import io
import json
import subprocess
import sys
from pathlib import Path

from notes.cli import main

HERE = Path(__file__).parent
WS = HERE.parent
DB = HERE / "db.json"
NOTES = [{"id": 2, "title": "b, with comma", "tags": ["x", "y"], "created": "2026-01-02T00:00:00+00:00"},
         {"id": 1, "title": "a", "tags": ["y"], "created": "2026-01-01T00:00:00+00:00"},
         {"id": 3, "title": "c", "tags": [], "created": "2026-01-03T00:00:00+00:00"}]


def setup_module():
    DB.write_text(json.dumps(NOTES))


def test_csv_file():
    out = HERE / "out.csv"
    assert main(["--db", str(DB), "export", "--format", "csv", "--out", str(out)], io.StringIO(), io.StringIO()) == 0
    rows = list(csv.reader(out.open(newline="")))
    assert rows == [["id", "title", "tags", "created"], ["1", "a", "y", "2026-01-01T00:00:00+00:00"],
                    ["2", "b, with comma", "x;y", "2026-01-02T00:00:00+00:00"], ["3", "c", "", "2026-01-03T00:00:00+00:00"]]


def test_json_stdout_and_tag():
    out = io.StringIO()
    assert main(["--db", str(DB), "export", "--format", "json", "--tag", "x"], out, io.StringIO()) == 0
    assert json.loads(out.getvalue()) == [NOTES[0]]


def test_unknown_format_exit_2():
    r = subprocess.run([sys.executable, "-m", "notes", "--db", str(DB), "export", "--format", "xml"], cwd=WS,
                       capture_output=True, text=True)
    assert r.returncode == 2 and r.stderr.strip()


def test_existing_commands_still_work():
    out = io.StringIO()
    assert main(["--db", str(DB), "list"], out, io.StringIO()) == 0
    assert "b, with comma" in out.getvalue()
