from lru import LRUCache


def test_get_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)
    assert c.get("b") is None
    assert c.get("a") == 1 and c.get("c") == 3


def test_put_existing_refreshes():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert c.get("b") is None and c.get("a") == 10


def test_miss_does_not_insert():
    c = LRUCache(1)
    assert c.get("x") is None
    c.put("y", 1)
    assert c.get("y") == 1
