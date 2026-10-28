import pytest
from uptime import uptime_pct


def test_values():
    assert uptime_pct(43170, 43200) == 99.93
    assert uptime_pct(40000, 43200) == 92.59
    assert uptime_pct(0, 100) == 0


def test_bad_total():
    with pytest.raises(ValueError):
        uptime_pct(1, 0)
