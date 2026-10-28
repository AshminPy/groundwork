from pager import iter_items


def test_two_pages():
    pages = {None: ([1, 2], "p2"), "p2": ([3], "p3"), "p3": ([], None)}
    assert list(iter_items(lambda c: pages[c])) == [1, 2, 3]
