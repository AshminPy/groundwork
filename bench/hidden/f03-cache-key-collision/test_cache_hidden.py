import itertools

from profiles import cache
from profiles.invalidation import invalidate

PAIRS = [("ab", "c"), ("a", "bc"), ("a:b", "x"), ("a", "b:x"), ("a:", "bx"), ("", "abc"), ("abc", ""),
         ("t|1", "u"), ("t", "|1u"), ("é", "x"), ("e\u0301", "x")]


def load(t, u):
    return f"{u!r}@{t!r}"


def test_no_cross_tenant_hits():
    cache.clear()
    for t, u in PAIRS:
        assert cache.get(t, u, load) == load(t, u), (t, u)


def test_keys_distinct():
    keys = [cache.cache_key(t, u) for t, u in PAIRS]
    assert len(set(keys)) == len(keys)


def test_invalidate_only_that_entry():
    cache.clear()
    for t, u in PAIRS:
        cache.get(t, u, load)
    invalidate("a:b", "x")
    calls = []
    for t, u in PAIRS:
        cache.get(t, u, lambda t, u: calls.append((t, u)) or load(t, u))
    assert calls == [("a:b", "x")]


def test_reload_after_invalidate_and_keys_hashable():
    cache.clear()
    n = {"c": 0}

    def counting(t, u):
        n["c"] += 1
        return load(t, u)
    cache.get("ab", "c", counting)
    invalidate("ab", "c")
    cache.get("ab", "c", counting)
    cache.get("a", "bc", counting)
    assert n["c"] == 3
    assert hash(cache.cache_key("a", "b")) is not None


def test_invalidate_unknown_is_noop():
    cache.clear()
    cache.get("x", "y", load)
    invalidate("nope", "y")
    calls = []
    cache.get("x", "y", lambda t, u: calls.append(1) or load(t, u))
    assert calls == []
