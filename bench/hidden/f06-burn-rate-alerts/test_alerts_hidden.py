import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def _d():
    return json.loads((WS / "alerts.json").read_text())


def test_page_needs_both_windows():
    assert _d()["page_first"] == "2026-05-05T05:43:00Z"


def test_page_is_not_the_short_spike():
    assert _d()["page_first"] != "2026-05-05T02:02:00Z"


def test_ticket_needs_full_six_hour_window():
    assert _d()["ticket_first"] == "2026-05-05T07:49:00Z"


def test_keys():
    assert set(_d()) == {"page_first", "ticket_first"}


def test_types():
    d = _d()
    assert all(v is None or isinstance(v, str) for v in d.values())


def test_firing_intervals():
    f = json.loads((WS / "firing.json").read_text())
    assert f == {"page": [["2026-05-05T05:43:00Z", "2026-05-05T06:00:00Z"]], "ticket": [["2026-05-05T07:49:00Z", "2026-05-05T07:59:00Z"]]}
    assert f["page"][0][0] == _d()["page_first"] and f["ticket"][0][0] == _d()["ticket_first"]
