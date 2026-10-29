"""Focused pilot cases, part 1 (design B8): 2 coding, 2 troubleshooting, 1 SRE. Each names its trap."""
import json

CASES = {}

CASES["f01-dst-free-slots"] = {
    "category": "coding",
    "trap": "daylight-saving days: the local working window is not a fixed UTC offset; overlapping and touching busy "
            "intervals must be merged",
    "instruction": """`slots.free_slots(busy, day, tz)` in `scheduling/slots.py` returns the free meeting slots for one
person on one local calendar day. Make it correct:
- The working window is 09:00 to 17:00 local time in `tz` (an IANA name such as `America/New_York`), on `day`
  (a `datetime.date`).
- `busy` is a list of `(start, end)` pairs of timezone-aware datetimes (any zone, any order). Busy intervals may
  overlap or touch, and may extend outside the working window.
- Slots are 30 minutes long, start on the hour or half hour in local time, must lie entirely inside the working
  window, and must not overlap any busy interval (touching is fine).
- Return the slot start times as timezone-aware UTC datetimes, sorted.
- `scheduling/intervals.py` has `merge(intervals)`, which the slot code uses; it must return merged, sorted
  intervals, with overlapping or touching intervals joined.
The tests in tests/ are incomplete; your change will also be checked by other tests. Keep the function names and
signatures.""",
    "fixture": {
        "scheduling/__init__.py": "",
        "scheduling/intervals.py": '''def merge(intervals):
    """Merge (start, end) intervals."""
    out = []
    for s, e in intervals:
        if out and s < out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out
''',
        "scheduling/slots.py": '''from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .intervals import merge

SLOT = timedelta(minutes=30)


def free_slots(busy, day, tz):
    zone = ZoneInfo(tz)
    offset = datetime.combine(day, time(0), zone).utcoffset()
    start = datetime.combine(day, time(9)) - offset
    end = datetime.combine(day, time(17)) - offset
    start, end = start.replace(tzinfo=timezone.utc), end.replace(tzinfo=timezone.utc)
    blocked = merge([(s.astimezone(timezone.utc), e.astimezone(timezone.utc)) for s, e in busy])
    out, t = [], start
    while t + SLOT <= end:
        if not any(s < t + SLOT and t < e for s, e in blocked):
            out.append(t)
        t += SLOT
    return out
''',
        "tests/test_slots.py": '''from datetime import date, datetime, timezone
from scheduling.slots import free_slots


def test_empty_day_has_16_slots():
    assert len(free_slots([], date(2026, 6, 10), "UTC")) == 16
''',
    },
    "oracle": {
        "scheduling/intervals.py": '''def merge(intervals):
    """Merge (start, end) intervals: sorted, with overlapping or touching intervals joined."""
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out
''',
        "scheduling/slots.py": '''from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .intervals import merge

SLOT = timedelta(minutes=30)


def free_slots(busy, day, tz):
    zone = ZoneInfo(tz)
    blocked = merge([(s.astimezone(timezone.utc), e.astimezone(timezone.utc)) for s, e in busy])
    out = []
    for minutes in range(9 * 60, 17 * 60, 30):
        local = datetime.combine(day, time(minutes // 60, minutes % 60), zone)
        t = local.astimezone(timezone.utc)
        end_local = datetime.combine(day, time(17), zone).astimezone(timezone.utc)
        if t + SLOT > end_local:
            continue
        if not any(s < t + SLOT and t < e for s, e in blocked):
            out.append(t)
    return sorted(out)
''',
    },
    "hidden": {"test_slots_hidden.py": '''from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scheduling.intervals import merge
from scheduling.slots import free_slots

UTC = timezone.utc
NY = ZoneInfo("America/New_York")


def u(*a):
    return datetime(*a, tzinfo=UTC)


def test_spring_forward_day_uses_local_nine():
    s = free_slots([], date(2026, 3, 8), "America/New_York")
    assert s[0] == u(2026, 3, 8, 13, 0) and s[-1] == u(2026, 3, 8, 20, 30) and len(s) == 16


def test_fall_back_day_london():
    s = free_slots([], date(2026, 10, 25), "Europe/London")
    assert s[0] == u(2026, 10, 25, 9, 0) and len(s) == 16


def test_overlapping_unsorted_busy_in_other_zone():
    busy = [(datetime(2026, 6, 10, 11, 0, tzinfo=NY), datetime(2026, 6, 10, 12, 0, tzinfo=NY)),
            (u(2026, 6, 10, 17, 15), u(2026, 6, 10, 18, 0)),
            (datetime(2026, 6, 10, 10, 30, tzinfo=NY), datetime(2026, 6, 10, 11, 15, tzinfo=NY))]
    s = free_slots(busy, date(2026, 6, 10), "America/New_York")
    local = [t.astimezone(NY).strftime("%H:%M") for t in s]
    assert "10:00" in local and "10:30" not in local and "11:30" not in local and "12:00" in local
    assert "09:00" in local and "09:30" in local and "16:30" in local
    assert "13:00" not in local and "13:30" not in local and "14:00" in local
    assert all(t.tzinfo is not None and t.utcoffset() == timedelta(0) for t in s)


def test_touching_busy_and_busy_beyond_window():
    busy = [(u(2026, 6, 10, 8, 0), u(2026, 6, 10, 9, 30)), (u(2026, 6, 10, 9, 30), u(2026, 6, 10, 10, 0)),
            (u(2026, 6, 10, 16, 30), u(2026, 6, 10, 19, 0))]
    s = free_slots(busy, date(2026, 6, 10), "UTC")
    assert s[0] == u(2026, 6, 10, 10, 0) and s[-1] == u(2026, 6, 10, 16, 0) and len(s) == 13


def test_merge_sorts_and_joins_touching():
    a, b, c = u(2026, 1, 1, 9), u(2026, 1, 1, 10), u(2026, 1, 1, 11)
    assert merge([(b, c), (a, b)]) == [(a, c)]
    assert merge([(b, c), (a, a + timedelta(minutes=5))]) == [(a, a + timedelta(minutes=5)), (b, c)]
'''},
}

CASES["f02-money-allocation"] = {
    "category": "coding",
    "trap": "float rounding makes split amounts not add up; currencies have 0, 2 or 3 minor units; refunds are "
            "negative",
    "instruction": """`billing.allocate.split(total, weights, currency)` splits an invoice total between cost centres in
proportion to `weights` (non-negative numbers). `total` is a decimal string such as `"100.00"` or `"-50.00"` (a
refund). It must return a list of decimal strings, one per weight, that:
- add up exactly to `total`;
- use the currency's minor units from `billing/currencies.py` (`USD` and `EUR`: 2, `JPY`: 0, `BHD`: 3). Add JPY and
  BHD there; an unknown currency raises `ValueError`;
- are computed by the largest-remainder method on the absolute amount: each share gets the floor of its exact
  proportional amount in minor units, then the leftover minor units go one each to the shares with the largest
  remainders, ties going to the earlier share. A negative total is split as its absolute value and every amount is
  negated;
- give a zero weight exactly zero.
All weights zero, an empty list or a negative weight raise `ValueError`. Amounts are formatted with exactly the
currency's number of decimals (`"0.00"`, `"0"`, `"0.000"`). The tests in tests/ are incomplete; your change will also
be checked by other tests.""",
    "fixture": {
        "billing/__init__.py": "",
        "billing/currencies.py": '''MINOR_UNITS = {"USD": 2, "EUR": 2}
''',
        "billing/allocate.py": '''from .currencies import MINOR_UNITS


def split(total: str, weights: list, currency: str) -> list:
    places = MINOR_UNITS[currency]
    t = float(total)
    s = sum(weights)
    return [f"{round(t * w / s, places):.{places}f}" for w in weights]
''',
        "tests/test_allocate.py": '''from billing.allocate import split


def test_even():
    assert split("10.00", [1, 1], "USD") == ["5.00", "5.00"]
''',
    },
    "oracle": {
        "billing/currencies.py": '''MINOR_UNITS = {"USD": 2, "EUR": 2, "JPY": 0, "BHD": 3}
''',
        "billing/allocate.py": '''from decimal import Decimal, ROUND_FLOOR

from .currencies import MINOR_UNITS


def split(total: str, weights: list, currency: str) -> list:
    if currency not in MINOR_UNITS:
        raise ValueError(f"unknown currency {currency!r}")
    if not weights or any(w < 0 for w in weights) or sum(weights) == 0:
        raise ValueError("weights must be non-negative and not all zero")
    places = MINOR_UNITS[currency]
    scale = Decimal(10) ** places
    t = Decimal(total)
    sign = -1 if t < 0 else 1
    units = int((abs(t) * scale).to_integral_value())
    ws = [Decimal(str(w)) for w in weights]
    s = sum(ws)
    exact = [Decimal(units) * w / s for w in ws]
    base = [int(x.to_integral_value(rounding=ROUND_FLOOR)) for x in exact]
    left = units - sum(base)
    order = sorted(range(len(ws)), key=lambda i: (-(exact[i] - base[i]), i))
    for i in order[:left]:
        base[i] += 1
    fmt = lambda u: f"{(Decimal(sign * u) / scale):.{places}f}"
    return [fmt(u) for u in base]
''',
    },
    "hidden": {"test_allocate_hidden.py": '''from decimal import Decimal

import pytest

from billing.allocate import split


def test_sums_exactly_and_largest_remainder():
    out = split("100.00", [1, 1, 1], "USD")
    assert out == ["33.34", "33.33", "33.33"]
    assert sum(Decimal(x) for x in out) == Decimal("100.00")


def test_ties_go_to_earlier_and_weights_proportional():
    assert split("0.05", [1, 1], "USD") == ["0.03", "0.02"]
    assert split("10.00", [3, 1], "EUR") == ["7.50", "2.50"]


def test_zero_minor_units_and_three():
    assert split("1000", [1, 2], "JPY") == ["333", "667"]
    assert split("1.000", [1, 1, 1], "BHD") == ["0.334", "0.333", "0.333"]


def test_refund_negative():
    out = split("-100.00", [1, 1, 1], "USD")
    assert out == ["-33.34", "-33.33", "-33.33"]


def test_zero_weight_gets_zero():
    out = split("10.00", [0, 1, 2], "USD")
    assert out[0] == "0.00" and sum(Decimal(x) for x in out) == Decimal("10.00")


@pytest.mark.parametrize("args", [("1.00", [], "USD"), ("1.00", [0, 0], "USD"), ("1.00", [1, -1], "USD"),
                                  ("1.00", [1], "XXX")])
def test_errors(args):
    with pytest.raises(ValueError):
        split(*args)


def test_many_shares_sum():
    out = split("0.07", [1] * 10, "USD")
    assert sum(Decimal(x) for x in out) == Decimal("0.07") and out.count("0.01") == 7
'''},
}

CASES["f03-cache-key-collision"] = {
    "category": "troubleshooting",
    "root_cause": [r"collision|collide|ambiguous|delimiter|separator|concatenat|same (cache )?key"],
    "trap": "cache keys built by joining strings collide across tenants; the same key logic is duplicated in the "
            "invalidation path",
    "instruction": """Security incident: a user was shown another tenant's profile (see `logs/profile.log`). Find the
root cause, fix it everywhere it occurs, and in your final answer state the root cause in one or two sentences.
Profiles are cached by `(tenant, user)`; tenant and user ids may contain any characters. Invalidation must remove
exactly the entry for one `(tenant, user)` and nothing else. Keep the existing function names and signatures
(`cache_key`, `get`, `clear`, `invalidate`). The tests in tests/ are incomplete; your fix will also be
checked by other tests.""",
    "fixture": {
        "logs/profile.log": """2026-07-14T10:02:11Z INFO cache miss tenant=ab user=c key=abc
2026-07-14T10:02:11Z INFO cache store tenant=ab user=c key=abc
2026-07-14T10:05:40Z INFO cache hit tenant=a user=bc key=abc
2026-07-14T10:05:40Z WARN support ticket: user bc (tenant a) saw profile of c@ab
2026-07-14T10:09:02Z INFO invalidate tenant=a:b user=x key=a:bx
""",
        "profiles/__init__.py": "",
        "profiles/cache.py": '''_CACHE = {}


def cache_key(tenant: str, user: str) -> str:
    return tenant + user


def get(tenant: str, user: str, load):
    k = cache_key(tenant, user)
    if k not in _CACHE:
        _CACHE[k] = load(tenant, user)
    return _CACHE[k]


def clear():
    _CACHE.clear()
''',
        "profiles/invalidation.py": '''from . import cache


def invalidate(tenant: str, user: str) -> None:
    key = tenant + ":" + user if ":" in tenant else tenant + user
    cache._CACHE.pop(key, None)
''',
        "tests/test_cache.py": '''from profiles import cache


def test_hit():
    cache.clear()
    calls = []
    load = lambda t, u: calls.append((t, u)) or f"{u}@{t}"
    assert cache.get("t1", "u1", load) == "u1@t1"
    assert cache.get("t1", "u1", load) == "u1@t1"
    assert calls == [("t1", "u1")]
''',
    },
    "oracle": {
        "profiles/cache.py": '''_CACHE = {}


def cache_key(tenant: str, user: str) -> tuple:
    """Unambiguous: a tuple can never collide across different (tenant, user) pairs."""
    return (tenant, user)


def get(tenant: str, user: str, load):
    k = cache_key(tenant, user)
    if k not in _CACHE:
        _CACHE[k] = load(tenant, user)
    return _CACHE[k]


def clear():
    _CACHE.clear()
''',
        "profiles/invalidation.py": '''from . import cache


def invalidate(tenant: str, user: str) -> None:
    cache._CACHE.pop(cache.cache_key(tenant, user), None)
''',
    },
    "hidden": {"test_cache_hidden.py": '''import itertools

from profiles import cache
from profiles.invalidation import invalidate

PAIRS = [("ab", "c"), ("a", "bc"), ("a:b", "x"), ("a", "b:x"), ("a:", "bx"), ("", "abc"), ("abc", ""),
         ("t|1", "u"), ("t", "|1u"), ("é", "x"), ("e\\u0301", "x")]


def load(t, u):
    return f"{u!r}@{t!r}"


def test_no_cross_tenant_hits():
    cache.clear()
    for t, u in PAIRS:
        assert cache.get(t, u, load) == load(t, u), (t, u)


def test_keys_distinct():
    keys = [cache.cache_key(t, u) for t, u in PAIRS]
    assert len(set(keys)) == len(keys)


def test_invalidate_only_that_entry():
    cache.clear()
    for t, u in PAIRS:
        cache.get(t, u, load)
    invalidate("a:b", "x")
    calls = []
    for t, u in PAIRS:
        cache.get(t, u, lambda t, u: calls.append((t, u)) or load(t, u))
    assert calls == [("a:b", "x")]


def test_reload_after_invalidate_and_keys_hashable():
    cache.clear()
    n = {"c": 0}

    def counting(t, u):
        n["c"] += 1
        return load(t, u)
    cache.get("ab", "c", counting)
    invalidate("ab", "c")
    cache.get("ab", "c", counting)
    cache.get("a", "bc", counting)
    assert n["c"] == 3
    assert hash(cache.cache_key("a", "b")) is not None


def test_invalidate_unknown_is_noop():
    cache.clear()
    cache.get("x", "y", load)
    invalidate("nope", "y")
    calls = []
    cache.get("x", "y", lambda t, u: calls.append(1) or load(t, u))
    assert calls == []
'''},
}

CASES["f04-out-of-order-events"] = {
    "category": "troubleshooting",
    "root_cause": [r"out[- ]of[- ]order|sequence|ordering|stale|arriv(e|ed|al) late|reorder"],
    "trap": "webhooks arrive out of order and are redelivered; state must follow per-order sequence numbers and be "
            "idempotent",
    "instruction": """Some orders end up `paid` although they were refunded, and refund totals are sometimes counted
twice (see `logs/webhooks.log`). Find the root cause, fix it in `orders/`, and in your final answer state the root
cause in one or two sentences. Each webhook event has an `id`, an `order_id`, a per-order `sequence` (1, 2, 3, ...)
and a `type`; the provider may deliver events late, out of order, or more than once. The final state of an order must
be the one from its highest sequence seen, an event with a sequence lower than or equal to the last applied one for
that order must change nothing, and redelivering the same event must change nothing. The tests in tests/ are
incomplete; your fix will also be checked by other tests.""",
    "fixture": {
        "logs/webhooks.log": """2026-08-02T12:00:01Z INFO event id=e1 order=o-9 seq=1 type=created
2026-08-02T12:00:09Z INFO event id=e3 order=o-9 seq=3 type=refunded amount=40.00
2026-08-02T12:00:10Z INFO event id=e2 order=o-9 seq=2 type=paid amount=40.00
2026-08-02T12:00:10Z INFO order o-9 state=paid refunded_total=40.00
2026-08-02T12:03:00Z INFO event id=e3 order=o-9 seq=3 type=refunded amount=40.00 (redelivery)
2026-08-02T12:03:00Z INFO order o-9 state=refunded refunded_total=80.00
""",
        "orders/__init__.py": "",
        "orders/store.py": '''class Store:
    def __init__(self):
        self.orders = {}

    def get(self, order_id):
        return self.orders.setdefault(order_id, {"state": None, "refunded_total": 0.0})
''',
        "orders/processor.py": '''STATES = {"created": "created", "paid": "paid", "refunded": "refunded", "cancelled": "cancelled"}


def apply(store, event: dict) -> None:
    order = store.get(event["order_id"])
    order["state"] = STATES[event["type"]]
    if event["type"] == "refunded":
        order["refunded_total"] += float(event.get("amount", 0))
''',
        "tests/test_processor.py": '''from orders.processor import apply
from orders.store import Store


def test_in_order():
    s = Store()
    apply(s, {"id": "e1", "order_id": "o", "sequence": 1, "type": "created"})
    apply(s, {"id": "e2", "order_id": "o", "sequence": 2, "type": "paid", "amount": "5.00"})
    assert s.get("o")["state"] == "paid"
''',
    },
    "oracle": {
        "orders/store.py": '''class Store:
    def __init__(self):
        self.orders = {}
        self.seen_events = set()

    def get(self, order_id):
        return self.orders.setdefault(order_id, {"state": None, "refunded_total": 0.0, "last_sequence": 0})
''',
        "orders/processor.py": '''STATES = {"created": "created", "paid": "paid", "refunded": "refunded", "cancelled": "cancelled"}


def apply(store, event: dict) -> None:
    if event["id"] in store.seen_events:
        return
    store.seen_events.add(event["id"])
    order = store.get(event["order_id"])
    if event["sequence"] <= order["last_sequence"]:
        return
    order["last_sequence"] = event["sequence"]
    order["state"] = STATES[event["type"]]
    if event["type"] == "refunded":
        order["refunded_total"] += float(event.get("amount", 0))
''',
    },
    "hidden": {"test_processor_hidden.py": '''from orders.processor import apply
from orders.store import Store


def ev(i, order, seq, typ, amount=None):
    e = {"id": i, "order_id": order, "sequence": seq, "type": typ}
    if amount is not None:
        e["amount"] = amount
    return e


def test_late_paid_does_not_override_refund():
    s = Store()
    for e in [ev("late-1", "o9", 1, "created"), ev("late-3", "o9", 3, "refunded", "40.00"), ev("late-2", "o9", 2, "paid", "40.00")]:
        apply(s, e)
    assert s.get("o9")["state"] == "refunded" and s.get("o9")["refunded_total"] == 40.0


def test_redelivery_is_idempotent():
    s = Store()
    for e in [ev("redeliver-1", "o1", 1, "created"), ev("redeliver-2", "o1", 2, "refunded", "10.00"), ev("redeliver-2", "o1", 2, "refunded", "10.00")]:
        apply(s, e)
    assert s.get("o1")["refunded_total"] == 10.0


def test_equal_sequence_other_event_ignored():
    s = Store()
    apply(s, ev("eq-a", "o2", 1, "created"))
    apply(s, ev("eq-b", "o2", 2, "paid", "1.00"))
    apply(s, ev("eq-c", "o2", 2, "cancelled"))
    assert s.get("o2")["state"] == "paid"


def test_sequences_are_per_order():
    s = Store()
    apply(s, ev("per-x1", "A", 5, "paid", "1.00"))
    apply(s, ev("per-y1", "B", 1, "created"))
    assert s.get("B")["state"] == "created" and s.get("A")["state"] == "paid"


def test_all_permutations_same_final_state():
    import itertools
    for n, order in enumerate(itertools.permutations(range(3))):
        oid = f"perm{n}"
        events = [ev(f"{oid}-1", oid, 1, "created"), ev(f"{oid}-2", oid, 2, "paid", "9.00"),
                  ev(f"{oid}-3", oid, 3, "refunded", "9.00")]
        s = Store()
        for i in order:
            apply(s, events[i])
        apply(s, events[2])
        assert s.get(oid)["state"] == "refunded"
        assert s.get(oid)["refunded_total"] == 9.0
'''},
}


def _skew_logs():
    web1 = ["2026-09-21T10:00:00Z web-1 INFO GET /cart 200",
            "2026-09-21T10:07:40Z web-1 ERROR GET /cart 504 upstream=db-1 timeout",
            "2026-09-21T10:12:00Z web-1 ERROR GET /cart 504 upstream=db-1 timeout",
            "2026-09-21T10:31:00Z web-1 INFO GET /cart 200"]
    web2 = ["2026-09-21T10:01:35Z web-2 INFO GET /cart 200",
            "2026-09-21T10:08:40Z web-2 ERROR GET /cart 504 upstream=db-1 timeout",
            "2026-09-21T10:31:20Z web-2 INFO GET /cart 200"]
    db1 = ["2026-09-21T10:06:30Z db-1 WARN replication lag 45s",
           "2026-09-21T10:06:58Z db-1 ERROR lock wait timeout on table carts (migration 0042 holding lock)",
           "2026-09-21T10:29:30Z db-1 INFO migration 0042 finished; locks released"]
    ntp = ["2026-09-21T09:00:00Z ntp INFO web-1 offset=+0.002s",
           "2026-09-21T09:00:00Z ntp WARN web-2 offset=+95.000s (web-2 clock ahead of true time by 95 s)",
           "2026-09-21T09:00:00Z ntp INFO db-1 offset=-0.001s",
           "2026-09-21T11:00:00Z ntp INFO web-2 resynced; offsets before this line still apply to earlier logs"]
    return {"logs/web-1.log": "\n".join(web1) + "\n", "logs/web-2.log": "\n".join(web2) + "\n",
            "logs/db-1.log": "\n".join(db1) + "\n", "logs/ntp.log": "\n".join(ntp) + "\n"}


def _timeline():
    """All web and db log lines in true UTC (web-2 minus 95 s), sorted by time then host."""
    from datetime import datetime, timedelta
    rows = []
    for name, text in _skew_logs().items():
        if "ntp" in name:
            continue
        for line in text.splitlines():
            ts, host, level, msg = line.split(" ", 3)
            t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
            if host == "web-2":
                t -= timedelta(seconds=95)
            rows.append((t.strftime("%Y-%m-%dT%H:%M:%SZ"), host, level, msg))
    rows.sort(key=lambda r: (r[0], r[1]))
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["utc", "host", "level", "message"])
    w.writerows(rows)
    return buf.getvalue()


_TIMELINE = _timeline()

_SKEW_ANSWER = {"first_error_utc": "2026-09-21T10:07:05Z", "first_error_host": "web-2",
                "root_cause_host": "db-1", "root_cause": "migration lock",
                "user_impact_start_utc": "2026-09-21T10:07:05Z", "recovered_utc": "2026-09-21T10:29:45Z"}

CASES["f05-clock-skew-timeline"] = {
    "category": "sre",
    "trap": "one host's clock is 95 s ahead; corrected, the first user-facing error and the recovery come from that "
            "host, and naive timestamps give the wrong order",
    "instruction": """Cart requests failed this morning. Using only the files in `logs/` (including `logs/ntp.log`,
which gives each host's clock offset from true time during the incident), write `incident.json` in the repository
root with exactly these keys, all times in true UTC as `YYYY-MM-DDTHH:MM:SSZ`:
- `"first_error_utc"`: the true time of the first user-facing error (a 5xx on a web host);
- `"first_error_host"`: which host logged it;
- `"user_impact_start_utc"`: the same as `first_error_utc`;
- `"recovered_utc"`: the true time of the first successful (200) request after the errors, on any web host;
- `"root_cause_host"`: the host where the failure started;
- `"root_cause"`: one of `"replication lag"`, `"migration lock"`, `"network partition"`.
Also write `timeline.csv` in the repository root: a CSV with the header `utc,host,level,message` and one row per line
of the web and db logs (not the ntp log), with `utc` in true UTC, sorted by `utc` and then by `host`; `message` is
the rest of the line after the level, unchanged.
A host whose clock is ahead logged timestamps later than true time. Round corrected times to the nearest second.""",
    "fixture": {**_skew_logs(), "README.md": "# cart incident logs\n"},
    "oracle": {"incident.json": json.dumps(_SKEW_ANSWER, indent=1) + "\n", "timeline.csv": _TIMELINE},
    "hidden": {"test_skew_hidden.py": f'''import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
WANT = {json.dumps(_SKEW_ANSWER)}


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
    want = list(csv.reader({_TIMELINE!r}.splitlines()))
    assert rows == want


def test_format():
    import re
    for k in ("first_error_utc", "user_impact_start_utc", "recovered_utc"):
        assert re.fullmatch(r"\\d{{4}}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\dZ", _d()[k]), k
'''},
}
