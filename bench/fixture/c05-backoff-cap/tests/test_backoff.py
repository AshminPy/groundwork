from backoff import delays


def test_zero():
    assert delays(1, 10, 0) == []
