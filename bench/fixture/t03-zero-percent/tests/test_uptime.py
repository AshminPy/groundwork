from uptime import uptime_pct


def test_full():
    assert uptime_pct(10, 10) == 100
