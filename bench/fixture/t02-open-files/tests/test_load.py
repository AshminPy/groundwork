import json
from pathlib import Path
from importer.load import read_record


def test_read(tmp_path=None):
    p = Path(__file__).parent / "one.json"
    assert read_record(p) == {"id": 1}
