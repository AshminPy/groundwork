from timeparse import parse_duration


def test_minutes():
    assert parse_duration("5m") == 300
