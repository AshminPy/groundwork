import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
WANT = {"first_error_utc": "2026-09-21T10:07:05Z", "first_error_host": "web-2", "root_cause_host": "db-1", "root_cause": "migration lock", "user_impact_start_utc": "2026-09-21T10:07:05Z", "recovered_utc": "2026-09-21T10:29:45Z"}


def _d():
    return json.loads((WS / "incident.json").read_text())


def test_first_error_corrected_for_skew():
    d = _d()
    assert d["first_error_utc"] == WANT["first_error_utc"] and d["first_error_host"] == WANT["first_error_host"]
    assert d["user_impact_start_utc"] == WANT["user_impact_start_utc"]


def test_recovery_corrected_for_skew():
    assert _d()["recovered_utc"] == WANT["recovered_utc"]


def test_root_cause():
    d = _d()
    assert d["root_cause_host"] == "db-1" and d["root_cause"] == "migration lock"


def test_exact_keys():
    assert set(_d()) == set(WANT)


def test_timeline_corrected_and_sorted():
    import csv
    rows = list(csv.reader((WS / "timeline.csv").open(newline="")))
    want = list(csv.reader('utc,host,level,message\n2026-09-21T10:00:00Z,web-1,INFO,GET /cart 200\n2026-09-21T10:00:00Z,web-2,INFO,GET /cart 200\n2026-09-21T10:06:30Z,db-1,WARN,replication lag 45s\n2026-09-21T10:06:58Z,db-1,ERROR,lock wait timeout on table carts (migration 0042 holding lock)\n2026-09-21T10:07:05Z,web-2,ERROR,GET /cart 504 upstream=db-1 timeout\n2026-09-21T10:07:40Z,web-1,ERROR,GET /cart 504 upstream=db-1 timeout\n2026-09-21T10:12:00Z,web-1,ERROR,GET /cart 504 upstream=db-1 timeout\n2026-09-21T10:29:30Z,db-1,INFO,migration 0042 finished; locks released\n2026-09-21T10:29:45Z,web-2,INFO,GET /cart 200\n2026-09-21T10:31:00Z,web-1,INFO,GET /cart 200\n'.splitlines()))
    assert rows == want


def test_format():
    import re
    for k in ("first_error_utc", "user_impact_start_utc", "recovered_utc"):
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", _d()[k]), k
