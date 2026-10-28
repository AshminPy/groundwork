"""Source of the 6 troubleshooting cases: logs plus code. Completion needs the hidden tests to pass and the final
answer to name the root cause (a frozen regex per case)."""

ASK = ("Find the root cause, fix it in the code, and in your final answer state the root cause in one or two "
       "sentences. The tests in tests/ are incomplete; your fix will also be checked by other tests.")

CASES = {}

CASES["t01-report-wrong-day"] = {
    "category": "troubleshooting",
    "root_cause": [r"\b(utc|time ?zone|tz|naive)\b"],
    "instruction": f"""The nightly sales report for 2026-03-09 included orders from 2026-03-08 and missed late orders
from 2026-03-09 (see `logs/report.log`). The server runs in UTC-5; order timestamps are stored in UTC. {ASK}""",
    "fixture": {
        "logs/report.log": """2026-03-10T05:00:02Z INFO report day=2026-03-09 window_start=2026-03-09T00:00:00 window_end=2026-03-10T00:00:00
2026-03-10T05:00:02Z INFO matched orders=412
2026-03-10T05:00:03Z WARN order o-88121 ts=2026-03-09T02:10:00Z counted, customer says it was placed 2026-03-08 21:10 local
2026-03-10T05:00:03Z WARN order o-88907 ts=2026-03-10T03:55:00Z not counted, placed 2026-03-09 22:55 local
""",
        "sales/__init__.py": "",
        "sales/window.py": '''from datetime import date, datetime, timedelta


def daily_window(day: date) -> tuple[datetime, datetime]:
    """The [start, end) window of one report day, in UTC, for comparing with stored UTC order timestamps."""
    start = datetime(day.year, day.month, day.day)
    return start, start + timedelta(days=1)


def in_window(ts: datetime, day: date) -> bool:
    start, end = daily_window(day)
    return start <= ts.replace(tzinfo=None) < end
''',
        "sales/settings.py": '''REPORT_TZ_OFFSET_HOURS = -5   # the business day is local time, UTC-5 (no daylight saving in this fixture)
''',
        "tests/test_window.py": '''from datetime import date
from sales.window import daily_window


def test_one_day_long():
    s, e = daily_window(date(2026, 3, 9))
    assert (e - s).total_seconds() == 86400
''',
    },
    "oracle": {
        "sales/window.py": '''from datetime import date, datetime, timedelta, timezone

from .settings import REPORT_TZ_OFFSET_HOURS


def daily_window(day: date) -> tuple[datetime, datetime]:
    """The [start, end) window of one report day, in UTC, for comparing with stored UTC order timestamps."""
    local = timezone(timedelta(hours=REPORT_TZ_OFFSET_HOURS))
    start = datetime(day.year, day.month, day.day, tzinfo=local).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def in_window(ts: datetime, day: date) -> bool:
    start, end = daily_window(day)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return start <= ts < end
''',
    },
    "hidden": {
        "test_window_hidden.py": '''from datetime import date, datetime, timezone
from sales.window import daily_window, in_window

UTC = timezone.utc


def _utc(d):
    """A naive result is read as UTC, as the docstring says; an aware one is converted."""
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


def test_window_is_local_day_in_utc():
    s, e = daily_window(date(2026, 3, 9))
    assert _utc(s) == datetime(2026, 3, 9, 5, 0, tzinfo=UTC)
    assert _utc(e) == datetime(2026, 3, 10, 5, 0, tzinfo=UTC)


def test_log_orders():
    assert not in_window(datetime(2026, 3, 9, 2, 10, tzinfo=UTC), date(2026, 3, 9))
    assert in_window(datetime(2026, 3, 10, 3, 55, tzinfo=UTC), date(2026, 3, 9))
''',
    },
}

CASES["t02-open-files"] = {
    "category": "troubleshooting",
    "root_cause": [r"\b(clos(e|ed|ing)|leak(s|ed|ing)?|file (handle|descriptor)s?|context manager|with open)\b"],
    "instruction": f"""The importer crashes after a few thousand files with `OSError: [Errno 24] Too many open files`
(see `logs/importer.log`). {ASK}""",
    "fixture": {
        "logs/importer.log": """2026-05-02T10:11:00Z INFO import start dir=/data/inbox files=9120
2026-05-02T10:11:41Z INFO imported=4000
2026-05-02T10:11:52Z ERROR import failed file=/data/inbox/r-4093.json: OSError: [Errno 24] Too many open files: '/data/inbox/r-4093.json'
2026-05-02T10:11:52Z INFO open_fds=4096 ulimit=4096
""",
        "importer/__init__.py": "",
        "importer/load.py": '''import json
from pathlib import Path


def read_record(path: Path) -> dict:
    f = open(path, encoding="utf-8")
    return json.load(f)


def import_dir(folder: Path) -> list[dict]:
    return [read_record(p) for p in sorted(folder.glob("*.json"))]
''',
        "tests/test_load.py": '''import json
from pathlib import Path
from importer.load import read_record


def test_read(tmp_path=None):
    p = Path(__file__).parent / "one.json"
    assert read_record(p) == {"id": 1}
''',
        "tests/one.json": '{"id": 1}\n',
    },
    "oracle": {
        "importer/load.py": '''import json
from pathlib import Path


def read_record(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def import_dir(folder: Path) -> list[dict]:
    return [read_record(p) for p in sorted(folder.glob("*.json"))]
''',
    },
    "hidden": {
        "test_load_hidden.py": '''import gc
import json
import warnings
from pathlib import Path

from importer.load import import_dir, read_record

HERE = Path(__file__).parent


def test_no_unclosed_file_warning():
    p = HERE / "rec.json"
    p.write_text(json.dumps({"id": 7}))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", ResourceWarning)
        assert read_record(p) == {"id": 7}
        gc.collect()
    assert not [x for x in w if issubclass(x.category, ResourceWarning)]


def test_many_files():
    d = HERE / "many"
    d.mkdir(exist_ok=True)
    for i in range(300):
        (d / f"r{i:03}.json").write_text(json.dumps({"id": i}))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", ResourceWarning)
        out = import_dir(d)
        gc.collect()
    assert [r["id"] for r in out] == list(range(300))
    assert not [x for x in w if issubclass(x.category, ResourceWarning)]
''',
    },
}

CASES["t03-zero-percent"] = {
    "category": "troubleshooting",
    "root_cause": [r"(integer|floor) division|//|\bint(eger)? (math|arithmetic)|truncat"],
    "instruction": f"""The uptime dashboard shows 0% for every service that had any downtime, and 100% only for perfect
ones (see `logs/dashboard.log`). {ASK} Percentages are rounded to 2 decimals.""",
    "fixture": {
        "logs/dashboard.log": """2026-07-01T00:00:05Z INFO uptime service=api up_minutes=43170 total_minutes=43200 pct=0
2026-07-01T00:00:05Z INFO uptime service=web up_minutes=43200 total_minutes=43200 pct=100
2026-07-01T00:00:05Z INFO uptime service=jobs up_minutes=40000 total_minutes=43200 pct=0
""",
        "uptime.py": '''def uptime_pct(up_minutes: int, total_minutes: int) -> float:
    if total_minutes <= 0:
        raise ValueError("total_minutes must be positive")
    return round(up_minutes // total_minutes * 100, 2)
''',
        "tests/test_uptime.py": '''from uptime import uptime_pct


def test_full():
    assert uptime_pct(10, 10) == 100
''',
    },
    "oracle": {
        "uptime.py": '''def uptime_pct(up_minutes: int, total_minutes: int) -> float:
    if total_minutes <= 0:
        raise ValueError("total_minutes must be positive")
    return round(up_minutes / total_minutes * 100, 2)
''',
    },
    "hidden": {
        "test_uptime_hidden.py": '''import pytest
from uptime import uptime_pct


def test_values():
    assert uptime_pct(43170, 43200) == 99.93
    assert uptime_pct(40000, 43200) == 92.59
    assert uptime_pct(0, 100) == 0


def test_bad_total():
    with pytest.raises(ValueError):
        uptime_pct(1, 0)
''',
    },
}

CASES["t04-duplicate-recipients"] = {
    "category": "troubleshooting",
    "root_cause": [r"mutable default|default (argument|parameter|value|list)|shared (list|default)|"
                   r"(created|evaluated|defined) (only )?once|reused (between|across) calls|extra=\[\]"],
    "instruction": f"""Each alert email goes to more and more people over the day: the second alert also goes to the first
alert's recipients, and so on (see `logs/notify.log`). {ASK}""",
    "fixture": {
        "logs/notify.log": """2026-08-14T09:00:00Z INFO alert=disk-api recipients=['oncall-api@example.com']
2026-08-14T09:20:00Z INFO alert=cpu-web recipients=['oncall-api@example.com', 'oncall-web@example.com']
2026-08-14T09:45:00Z INFO alert=queue-jobs recipients=['oncall-api@example.com', 'oncall-web@example.com', 'oncall-jobs@example.com']
""",
        "notify.py": '''ONCALL = {"api": "oncall-api@example.com", "web": "oncall-web@example.com", "jobs": "oncall-jobs@example.com"}


def recipients(team: str, extra=[]) -> list:
    extra.append(ONCALL[team])
    return extra
''',
        "tests/test_notify.py": '''from notify import recipients


def test_extra():
    assert recipients("web", ["boss@example.com"]) == ["boss@example.com", "oncall-web@example.com"]
''',
    },
    "oracle": {
        "notify.py": '''ONCALL = {"api": "oncall-api@example.com", "web": "oncall-web@example.com", "jobs": "oncall-jobs@example.com"}


def recipients(team: str, extra=None) -> list:
    return [*(extra or []), ONCALL[team]]
''',
    },
    "hidden": {
        "test_notify_hidden.py": '''from notify import recipients


def test_calls_independent():
    assert recipients("api") == ["oncall-api@example.com"]
    assert recipients("web") == ["oncall-web@example.com"]
    assert recipients("jobs") == ["oncall-jobs@example.com"]


def test_caller_list_not_modified():
    mine = ["boss@example.com"]
    assert recipients("api", mine) == ["boss@example.com", "oncall-api@example.com"]
    assert mine == ["boss@example.com"]
''',
    },
}

CASES["t05-retry-count"] = {
    "category": "troubleshooting",
    "root_cause": [r"off[- ]by[- ]one|range\(|one (attempt|retry) (too )?(few|short|less)|fencepost|"
                   r"max_retries ?\+ ?1|one fewer"],
    "instruction": f"""`max_retries=3` is configured, which should mean 1 attempt plus up to 3 retries, but the logs show
a failing upload giving up after 3 attempts in total (see `logs/upload.log`). {ASK}""",
    "fixture": {
        "logs/upload.log": """2026-09-03T12:00:00Z INFO upload id=u-17 attempt=1 status=503
2026-09-03T12:00:01Z INFO upload id=u-17 attempt=2 status=503
2026-09-03T12:00:03Z INFO upload id=u-17 attempt=3 status=503
2026-09-03T12:00:03Z ERROR upload id=u-17 giving up after 3 attempts (max_retries=3)
""",
        "uploader.py": '''class UploadError(Exception):
    pass


def upload_with_retries(send, max_retries: int = 3):
    """Call send() until it returns True: one attempt plus up to max_retries retries."""
    for attempt in range(max_retries):
        if send():
            return attempt + 1
    raise UploadError(f"giving up after {max_retries} attempts")
''',
        "tests/test_uploader.py": '''from uploader import upload_with_retries


def test_first_try():
    assert upload_with_retries(lambda: True) == 1
''',
    },
    "oracle": {
        "uploader.py": '''class UploadError(Exception):
    pass


def upload_with_retries(send, max_retries: int = 3):
    """Call send() until it returns True: one attempt plus up to max_retries retries."""
    for attempt in range(max_retries + 1):
        if send():
            return attempt + 1
    raise UploadError(f"giving up after {max_retries + 1} attempts")
''',
    },
    "hidden": {
        "test_uploader_hidden.py": '''import pytest
from uploader import UploadError, upload_with_retries


def _sender(succeed_on):
    calls = {"n": 0}

    def send():
        calls["n"] += 1
        return calls["n"] == succeed_on
    return send, calls


def test_succeeds_on_last_retry():
    send, calls = _sender(4)
    assert upload_with_retries(send, max_retries=3) == 4


def test_gives_up_after_all_retries():
    send, calls = _sender(99)
    with pytest.raises(UploadError):
        upload_with_retries(send, max_retries=3)
    assert calls["n"] == 4


def test_zero_retries():
    send, calls = _sender(99)
    with pytest.raises(UploadError):
        upload_with_retries(send, max_retries=0)
    assert calls["n"] == 1
''',
    },
}

CASES["t06-flag-false"] = {
    "category": "troubleshooting",
    "root_cause": [r"bool\(|non-?empty string|truthy|any string|string ['\"]?false['\"]? (is|evaluates)"],
    "instruction": f"""Setting `NEW_CHECKOUT=false` in the environment still turns the new checkout on (see
`logs/flags.log`). {ASK} Accept `1, true, yes, on` and `0, false, no, off` in any letter case, with surrounding
spaces ignored; an unset or empty variable uses the default; anything else raises `ValueError`.""",
    "fixture": {
        "logs/flags.log": """2026-10-01T08:00:00Z INFO env NEW_CHECKOUT='false'
2026-10-01T08:00:00Z INFO flag new_checkout=True
""",
        "flags.py": '''import os


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return bool(value)
''',
        "tests/test_flags.py": '''from flags import env_flag


def test_default(monkeypatch):
    monkeypatch.delenv("X_FLAG", raising=False)
    assert env_flag("X_FLAG", True) is True
''',
    },
    "oracle": {
        "flags.py": '''import os

_TRUE, _FALSE = {"1", "true", "yes", "on"}, {"0", "false", "no", "off"}


def env_flag(name: str, default: bool = False) -> bool:
    value = (os.environ.get(name) or "").strip().lower()
    if not value:
        return default
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{name}={value!r} is not a boolean")
''',
    },
    "hidden": {
        "test_flags_hidden.py": '''import pytest
from flags import env_flag


@pytest.mark.parametrize("raw,want", [("false", False), ("FALSE", False), (" off ", False), ("0", False),
                                      ("no", False), ("true", True), ("Yes", True), ("1", True), ("ON", True)])
def test_values(monkeypatch, raw, want):
    monkeypatch.setenv("NEW_CHECKOUT", raw)
    assert env_flag("NEW_CHECKOUT", default=not want) is want


def test_empty_uses_default(monkeypatch):
    monkeypatch.setenv("NEW_CHECKOUT", "")
    assert env_flag("NEW_CHECKOUT", default=True) is True


def test_invalid(monkeypatch):
    monkeypatch.setenv("NEW_CHECKOUT", "maybe")
    with pytest.raises(ValueError):
        env_flag("NEW_CHECKOUT")
''',
    },
}
