from datetime import date, datetime, timezone
from scheduling.slots import free_slots


def test_empty_day_has_16_slots():
    assert len(free_slots([], date(2026, 6, 10), "UTC")) == 16
