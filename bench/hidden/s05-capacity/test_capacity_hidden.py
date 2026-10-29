import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def test_capacity():
    d = json.loads((WS / "capacity.json").read_text())
    assert d["peak_rps"] == 2039
    assert d["pods_needed"] == 9
