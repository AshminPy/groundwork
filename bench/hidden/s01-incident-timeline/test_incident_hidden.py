import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def test_incident():
    d = json.loads((WS / "incident.json").read_text())
    assert d["impact_start"] == "2026-04-11T14:05:31Z"
    assert d["impact_end"] == "2026-04-11T14:23:05Z"
    assert d["impact_minutes"] == 17
    assert d["origin_service"] == "payments"
    assert d["trigger"] == "deploy"
    assert d["mitigation"] == "rollback"
