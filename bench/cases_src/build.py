"""Write the baseline cases from cases_src/ into tasks/, fixture/, hidden/ and oracle/, then check every case:
the untouched fixture must FAIL its hidden tests and the fixture plus the oracle must PASS them.

    python -m bench.cases_src.build [--check-only]
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from .. import grade_write
from . import coding, infra, longrun, sre, troubleshooting

BENCH = grade_write.BENCH
ORACLE = BENCH / "oracle"


def all_cases() -> dict:
    out = {}
    for mod in (coding, troubleshooting, sre, infra, longrun):
        for cid, c in mod.CASES.items():
            out[cid] = {**c, "kind": "write"}
    for cid, c in longrun.PROBES.items():
        out[cid] = {**c, "kind": "probe"}
    return out


def _write_tree(root: Path, files: dict) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


def write(cases: dict) -> None:
    for d in (grade_write.HIDDEN, ORACLE):
        if d.exists():
            shutil.rmtree(d)
    for cid, c in cases.items():
        for d in (grade_write.TASKS / cid, grade_write.FIXTURES / cid):
            if d.exists():
                shutil.rmtree(d)
        _write_tree(grade_write.FIXTURES / cid, c["fixture"])
        _write_tree(grade_write.HIDDEN / cid, c.get("hidden", {}))
        _write_tree(ORACLE / cid, c.get("oracle", {}))
        meta = {"id": cid, "category": c["category"], "kind": c["kind"], "fixture": cid,
                "timeout_s": grade_write.TEST_TIMEOUT_S}
        if c.get("root_cause"):
            meta["root_cause"] = c["root_cause"]
        if c.get("probe"):
            meta["probe"] = c["probe"]
        (grade_write.TASKS / cid).mkdir(parents=True)
        (grade_write.TASKS / cid / "instruction.md").write_text(c["instruction"].strip() + "\n")
        (grade_write.TASKS / cid / "case.json").write_text(json.dumps(meta, indent=1) + "\n")


def check(cases: dict) -> list[str]:
    problems = []
    for cid, c in cases.items():
        if c["kind"] != "write":
            continue
        with tempfile.TemporaryDirectory(prefix="gw-case-") as tmp:
            ws = Path(tmp) / "repo"
            shutil.copytree(grade_write.FIXTURES / cid, ws)
            before = grade_write.run_hidden_tests(cid, ws)
            if before["tests_exit"] == 0:
                problems.append(f"{cid}: the untouched fixture already passes the hidden tests")
            _write_tree(ws, c.get("oracle", {}))
            after = grade_write.run_hidden_tests(cid, ws)
            if after["tests_exit"] != 0:
                problems.append(f"{cid}: the oracle fails the hidden tests:\n{after['tests_tail'][-1500:]}")
            print(f"{cid}: fixture exit={before['tests_exit']} oracle exit={after['tests_exit']}", flush=True)
    return problems


def main(argv: list[str]) -> int:
    cases = all_cases()
    if "--check-only" not in argv:
        write(cases)
    problems = check(cases)
    counts = {}
    for c in cases.values():
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    print(json.dumps(counts))
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
