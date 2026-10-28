import pytest
from timeparse import parse_duration


@pytest.mark.parametrize("text,want", [("1h30m", 5400), ("45s", 45), ("2h", 7200), ("1h 5m 10s", 3910),
                                       ("0m", 0), ("10m5s", 605)])
def test_valid(text, want):
    assert parse_duration(text) == want


@pytest.mark.parametrize("text", ["", "   ", "5", "3d", "1m1h", "1h1h", "h", "1.5h", "-2m"])
def test_invalid(text):
    with pytest.raises(ValueError):
        parse_duration(text)
