from . import cache


def invalidate(tenant: str, user: str) -> None:
    key = tenant + ":" + user if ":" in tenant else tenant + user
    cache._CACHE.pop(key, None)
