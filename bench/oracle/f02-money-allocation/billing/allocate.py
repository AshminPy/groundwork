from decimal import Decimal, ROUND_FLOOR

from .currencies import MINOR_UNITS


def split(total: str, weights: list, currency: str) -> list:
    if currency not in MINOR_UNITS:
        raise ValueError(f"unknown currency {currency!r}")
    if not weights or any(w < 0 for w in weights) or sum(weights) == 0:
        raise ValueError("weights must be non-negative and not all zero")
    places = MINOR_UNITS[currency]
    scale = Decimal(10) ** places
    t = Decimal(total)
    sign = -1 if t < 0 else 1
    units = int((abs(t) * scale).to_integral_value())
    ws = [Decimal(str(w)) for w in weights]
    s = sum(ws)
    exact = [Decimal(units) * w / s for w in ws]
    base = [int(x.to_integral_value(rounding=ROUND_FLOOR)) for x in exact]
    left = units - sum(base)
    order = sorted(range(len(ws)), key=lambda i: (-(exact[i] - base[i]), i))
    for i in order[:left]:
        base[i] += 1
    fmt = lambda u: f"{(Decimal(sign * u) / scale):.{places}f}"
    return [fmt(u) for u in base]
