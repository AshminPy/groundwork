from config import merge


def test_top_level():
    assert merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
