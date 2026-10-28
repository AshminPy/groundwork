from lru import LRUCache


def test_put_get():
    c = LRUCache(2)
    c.put("a", 1)
    assert c.get("a") == 1
