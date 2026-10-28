import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def test_slo():
    d = json.loads((WS / "slo.json").read_text())
    assert d["requests"] == 238852
    assert d["errors"] == 1248
    assert abs(d["error_rate"] - 0.005225) <= 0.000001
    assert abs(d["burn_rate"] - 5.22) <= 0.01
    assert abs(d["budget_consumed_pct"] - 2.9) <= 0.01
