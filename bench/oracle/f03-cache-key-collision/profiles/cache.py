_CACHE = {}


def cache_key(tenant: str, user: str) -> tuple:
    """Unambiguous: a tuple can never collide across different (tenant, user) pairs."""
    return (tenant, user)


def get(tenant: str, user: str, load):
    k = cache_key(tenant, user)
    if k not in _CACHE:
        _CACHE[k] = load(tenant, user)
    return _CACHE[k]


def clear():
    _CACHE.clear()
