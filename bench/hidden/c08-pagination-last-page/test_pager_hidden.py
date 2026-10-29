import pytest
import pager


def iter_items(fetch_page, limit=50):
    """The function under test, with a call limit so a looping implementation fails fast instead of hanging."""
    calls = {"n": 0}

    def guarded(cursor):
        calls["n"] += 1
        if calls["n"] > limit:
            raise AssertionError("fetch_page called too many times: the pager loops")
        return fetch_page(cursor)
    return pager.iter_items(guarded)


def test_last_page_kept():
    pages = {None: ([1, 2], "p2"), "p2": ([3, 4], None)}
    assert list(iter_items(lambda c: pages[c])) == [1, 2, 3, 4]


def test_single_page():
    assert list(iter_items(lambda c: (["a"], None))) == ["a"]


def test_repeated_cursor_stops():
    pages = {None: ([1], "x"), "x": ([], "x")}
    with pytest.raises(RuntimeError):
        list(iter_items(lambda c: pages[c]))


def test_cycle_stops():
    pages = {None: ([1], "a"), "a": ([2], "b"), "b": ([3], "a")}
    with pytest.raises(RuntimeError):
        list(iter_items(lambda c: pages[c]))
