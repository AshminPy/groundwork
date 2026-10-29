from .currencies import MINOR_UNITS


def split(total: str, weights: list, currency: str) -> list:
    places = MINOR_UNITS[currency]
    t = float(total)
    s = sum(weights)
    return [f"{round(t * w / s, places):.{places}f}" for w in weights]
