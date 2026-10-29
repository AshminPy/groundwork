from . import cache


def invalidate(tenant: str, user: str) -> None:
    cache._CACHE.pop(cache.cache_key(tenant, user), None)
