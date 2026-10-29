import pytest
from backoff import delays


def test_sequence_and_cap():
    assert delays(0.5, 3, 6) == [0.5, 1, 2, 3, 3, 3]


def test_no_cap_hit():
    assert delays(1, 100, 4) == [1, 2, 4, 8]


@pytest.mark.parametrize("args", [(-1, 5, 2), (1, -5, 2), (1, 5, -2)])
def test_negative(args):
    with pytest.raises(ValueError):
        delays(*args)
