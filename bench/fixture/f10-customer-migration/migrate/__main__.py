import json
import sys
from pathlib import Path

from .transform import transform


def main(argv=None) -> int:
    src, out = (argv or sys.argv[1:])[:2]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in Path(src).read_text().splitlines() if l.strip()]
    migrated = [transform(r) for r in rows]
    (out / "migrated.jsonl").write_text("".join(json.dumps(r) + "\n" for r in migrated))
    return 0


sys.exit(main())
