import re

_RX = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
                 r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")


def _parse(v):
    m = _RX.match(v or "")
    if not m:
        raise ValueError(f"invalid version {v!r}")
    pre = m.group(4)
    return tuple(int(x) for x in m.group(1, 2, 3)), (pre.split(".") if pre else None)


def _cmp_id(x, y):
    xn, yn = x.isdigit(), y.isdigit()
    if xn and yn:
        return (int(x) > int(y)) - (int(x) < int(y))
    if xn != yn:
        return -1 if xn else 1
    return (x > y) - (x < y)


def compare(a: str, b: str) -> int:
    (na, pa), (nb, pb) = _parse(a), _parse(b)
    if na != nb:
        return 1 if na > nb else -1
    if pa is None or pb is None:
        return 0 if pa is pb else (1 if pa is None else -1)
    for x, y in zip(pa, pb):
        c = _cmp_id(x, y)
        if c:
            return c
    return (len(pa) > len(pb)) - (len(pa) < len(pb))
