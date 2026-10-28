import json
from pathlib import Path


def read_record(path: Path) -> dict:
    f = open(path, encoding="utf-8")
    return json.load(f)


def import_dir(folder: Path) -> list[dict]:
    return [read_record(p) for p in sorted(folder.glob("*.json"))]
