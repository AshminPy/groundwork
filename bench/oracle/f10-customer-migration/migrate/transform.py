from . import validate


def split_name(name: str):
    words = " ".join((name or "").split()).split(" ")
    if len(words) <= 1:
        return (words[0] if words else ""), ""
    return " ".join(words[:-1]), words[-1]


class InvalidRecord(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def transform(r: dict) -> dict:
    """The version-2 record; raises InvalidRecord with the reason of the first failing check."""
    if r.get("schema_version") == 2:
        return r
    e = validate.email(r.get("email"))
    if e is None:
        raise InvalidRecord("invalid_email")
    p = validate.phone(r.get("phone"))
    if p is None:
        raise InvalidRecord("invalid_phone")
    d = validate.signup(r.get("signup"))
    if d is None:
        raise InvalidRecord("invalid_date")
    given, family = split_name(r.get("name", ""))
    return {"schema_version": 2, "id": r["id"], "given_name": given, "family_name": family, "email": e,
            "phone": p, "signup_date": d, "updated_at": r["updated_at"]}
