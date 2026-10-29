import json
from pathlib import Path


def read_record(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def import_dir(folder: Path) -> list[dict]:
    return [read_record(p) for p in sorted(folder.glob("*.json"))]
