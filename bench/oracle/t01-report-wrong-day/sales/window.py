from datetime import date, datetime, timedelta, timezone

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
