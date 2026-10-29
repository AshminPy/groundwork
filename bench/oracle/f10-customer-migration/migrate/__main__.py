import json
import sys
from collections import Counter
from pathlib import Path

from .transform import InvalidRecord, transform


def main(argv=None) -> int:
    src, out = (argv or sys.argv[1:])[:2]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in Path(src).read_text().splitlines() if l.strip()]
    good, bad = [], []
    for r in rows:
        try:
            good.append(transform(r))
        except InvalidRecord as e:
            bad.append({"id": r.get("id"), "reason": e.reason})
    best = {}
    for rec in good:
        k = rec["email"]
        if k not in best or rec["updated_at"] > best[k]["updated_at"]:
            best[k] = rec
    keep = {id(r) for r in best.values()}
    for rec in good:
        if id(rec) not in keep:
            bad.append({"id": rec["id"], "reason": "duplicate"})
    migrated = sorted(best.values(), key=lambda r: r["id"])
    bad.sort(key=lambda r: r["id"])
    (out / "migrated.jsonl").write_text("".join(json.dumps(r) + "\n" for r in migrated))
    (out / "quarantine.jsonl").write_text("".join(json.dumps(r) + "\n" for r in bad))
    report = {"read": len(rows), "migrated": len(migrated), "quarantined": len(bad),
              "by_reason": dict(Counter(r["reason"] for r in bad))}
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    return 0


sys.exit(main())
