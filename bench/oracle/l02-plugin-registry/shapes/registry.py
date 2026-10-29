_REGISTRY = {}


def register(name: str):
    def deco(cls):
        if name in _REGISTRY:
            raise ValueError(f"exporter {name!r} is already registered")
        _REGISTRY[name] = cls
        return cls
    return deco


def get(name: str):
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise KeyError(f"unknown exporter {name!r}; known: {', '.join(names())}") from None


def names() -> list:
    return sorted(_REGISTRY)
