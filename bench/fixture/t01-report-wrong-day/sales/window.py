from datetime import date, datetime, timedelta


def daily_window(day: date) -> tuple[datetime, datetime]:
    """The [start, end) window of one report day, in UTC, for comparing with stored UTC order timestamps."""
    start = datetime(day.year, day.month, day.day)
    return start, start + timedelta(days=1)


def in_window(ts: datetime, day: date) -> bool:
    start, end = daily_window(day)
    return start <= ts.replace(tzinfo=None) < end
