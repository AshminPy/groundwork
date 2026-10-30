"""Shared helpers for the `gw` state script. Python 3.11 standard library only."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def write_atomic(path: Path, data: bytes) -> None:
    """Write through a temp file and os.replace, keeping an existing file's permission bits (ported from 2.x
    scripts/merge_settings.py write_atomic)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".gw.tmp")
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        mode = 0o600
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.fchmod(fd, mode)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def dump_json(obj) -> bytes:
    return (json.dumps(obj, indent=2) + "\n").encode()


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path))
