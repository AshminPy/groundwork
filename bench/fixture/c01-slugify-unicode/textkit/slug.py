import re


def slugify(title: str) -> str:
    """Turn a title into a URL slug."""
    s = title.lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9-]", "", s)
