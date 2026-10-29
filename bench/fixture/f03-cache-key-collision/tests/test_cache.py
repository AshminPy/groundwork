from profiles import cache


def test_hit():
    cache.clear()
    calls = []
    load = lambda t, u: calls.append((t, u)) or f"{u}@{t}"
    assert cache.get("t1", "u1", load) == "u1@t1"
    assert cache.get("t1", "u1", load) == "u1@t1"
    assert calls == [("t1", "u1")]
