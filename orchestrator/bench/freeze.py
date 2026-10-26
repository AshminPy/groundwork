"""Fingerprint of everything that decides a grade: grade.py, every answer key, and the fixture.

The M2 baseline and the post-change run must carry the same fingerprint, or the comparison is invalid.
    python -m bench.freeze          print the current fingerprint
    python -m bench.freeze --write  record it in FROZEN.json
"""
from __future__ import annotations

import hashlib
import json
import sys

from . import grade


def current() -> str:
    h = hashlib.sha256()
    files = [grade.BENCH / "grade.py", *sorted(grade.KEYS.glob("*.json")), *sorted(grade.FIXTURES.rglob("*"))]
    for p in files:
        if p.is_file():
            h.update(str(p.relative_to(grade.BENCH)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


if __name__ == "__main__":
    fp = current()
    if "--write" in sys.argv:
        (grade.BENCH / "FROZEN.json").write_text(json.dumps({"sha256": fp}, indent=1) + "\n")
    print(fp)
