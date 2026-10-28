import re

_RX = re.compile(r"^\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?\s*$")


def parse_duration(text: str) -> int:
    """Return the number of seconds in a duration such as "1h30m"."""
    m = _RX.match(text or "")
    if not m or not any(m.groups()):
        raise ValueError(f"not a duration: {text!r}")
    h, mi, s = (int(g) if g else 0 for g in m.groups())
    return h * 3600 + mi * 60 + s
