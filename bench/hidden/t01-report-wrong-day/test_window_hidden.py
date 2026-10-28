from datetime import date, datetime, timezone
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
