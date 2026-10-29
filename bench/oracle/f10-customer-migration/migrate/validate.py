import re
from datetime import date


def email(v: str):
    e = (v or "").strip().lower()
    local, _, domain = e.partition("@")
    if e.count("@") != 1 or not local or "." not in domain:
        return None
    return e


def phone(v: str):
    s = (v or "").strip()
    digits = re.sub(r"\D", "", s)
    if s.startswith("+"):
        return "+" + digits if 8 <= len(digits) <= 15 else None
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def signup(v: str):
    s = (v or "").strip()
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s) or None
    try:
        if m:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None
    return None
