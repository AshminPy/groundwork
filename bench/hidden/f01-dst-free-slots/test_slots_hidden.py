from datetime import date, datetime, timedelta, timezone
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
