"""Re-grade a finished run's saved answers with the current keys and grader. No model is called.

    python -m bench.regrade <run-dir>

Writes results.regraded.jsonl and report.md next to the original results.jsonl, which is left unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import grade, report


def main(argv: list[str]) -> int:
    run_dir = Path(argv[0]).resolve()
    src, dst = run_dir / "results.jsonl", run_dir / "results.regraded.jsonl"
    rows = []
    for line in src.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        r["grade_original"] = r["grade"]
        r["grade"] = grade.grade(grade.load_key(r["case"]), r.get("final_text") or "")
        rows.append(r)
    dst.write_text("".join(json.dumps(r) + "\n" for r in rows))
    meta = json.loads((run_dir / "meta.json").read_text())
    meta["regraded"] = True
    (run_dir / "report.md").write_text(report.render(dst, meta))
    changed = [(r["case"], r["arm"], r["rep"]) for r in rows if r["grade"]["correct"] != r["grade_original"]["correct"]]
    print(f"regraded {len(rows)} rows; correctness changed for {len(changed)}: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
