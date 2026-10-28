import re
import unicodedata


def slugify(title: str) -> str:
    """Turn a title into a URL slug."""
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")
