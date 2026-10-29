from datetime import date
from sales.window import daily_window


def test_one_day_long():
    s, e = daily_window(date(2026, 3, 9))
    assert (e - s).total_seconds() == 86400
