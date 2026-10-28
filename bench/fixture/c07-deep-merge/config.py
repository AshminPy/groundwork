def merge(base: dict, override: dict) -> dict:
    base.update(override)
    return base
