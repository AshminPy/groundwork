"""Freeze the baseline before any run: grader fingerprint, case-file hash, seeded stratified split, bootstrap seed.

    python -m bench.freeze            print the current fingerprints and the split the seed gives
    python -m bench.freeze --write    record them in FROZEN.json (refuses if FROZEN.json already holds a split,
                                      unless --refreeze; a re-freeze means every dev result must be re-run)

The split covers the 28 scored write-capable cases (kind "write"), stratified by category: an even category splits
evenly; the odd categories alternate which side gets the extra case (the first one by a seeded coin), so dev and
held-out end up the same size. The 2 safety probes are not split: every arm runs them in every pass. Calibration uses
three dev cases only (the first dev case of coding, SRE and long-running, by id).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import grade, grade_write

BENCH = grade.BENCH
FROZEN = BENCH / "FROZEN.json"
SEED = 20261028
BOOTSTRAP_SEED = 7331
CALIBRATION_CATEGORIES = ("coding", "sre", "long-running")


def _hash(files: list[Path]) -> str:
    h = hashlib.sha256()
    for p in files:
        if p.is_file():
            h.update(str(p.relative_to(BENCH)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def grader_fingerprint() -> str:
    """Everything that decides a score: both graders, every key, every fixture and every hidden test."""
    files = [BENCH / "grade.py", BENCH / "grade_write.py", BENCH / "grader_sandbox.py", *sorted(grade.KEYS.glob("*.json")),
             *sorted(grade.FIXTURES.rglob("*")), *sorted(grade_write.HIDDEN.rglob("*"))]
    return _hash(files)


def cases_fingerprint() -> str:
    return _hash(sorted(grade_write.TASKS.rglob("*")))


PROTOCOL_FILES = ("arms.py", "run.py", "stats.py", "report.py", "canary.py", "_adapter.py", "prepare_arms.py")


def protocol_fingerprint() -> str:
    """The arm setup, run order, statistics and decision rule: changing any of them after the freeze is detected."""
    return _hash([BENCH / f for f in PROTOCOL_FILES])


def split(seed: int = SEED) -> dict:
    by_cat: dict[str, list[str]] = defaultdict(list)
    probes = []
    focused = []
    for case in grade_write.baseline_cases():
        c = grade_write.load_case(case)
        if c.get("suite") == "focused":
            focused.append(case)
            continue
        (probes if c["kind"] == "probe" else by_cat[c["category"]]).append(case)
    rng = random.Random(seed)
    dev, held = [], []
    extra_to_dev = rng.random() < 0.5
    for cat in sorted(by_cat):
        ids = sorted(by_cat[cat])
        random.Random(f"{seed}:{cat}").shuffle(ids)
        n_dev = len(ids) // 2
        if len(ids) % 2:
            n_dev += 1 if extra_to_dev else 0
            extra_to_dev = not extra_to_dev
        dev += ids[:n_dev]
        held += ids[n_dev:]
    calibration = []
    for cat in CALIBRATION_CATEGORIES:
        first = sorted(c for c in dev if grade_write.load_case(c)["category"] == cat)[:1]
        calibration += first
    return {"dev": sorted(dev), "held": sorted(held), "probes": sorted(probes), "calibration": calibration,
            "focused": sorted(focused)}


def current() -> dict:
    return {"grader_sha256": grader_fingerprint(), "cases_sha256": cases_fingerprint(),
            "protocol_sha256": protocol_fingerprint(), "seed": SEED,
            "bootstrap_seed": BOOTSTRAP_SEED, "split": split(SEED)}


def load() -> dict:
    return json.loads(FROZEN.read_text()) if FROZEN.exists() else {}


def verify() -> tuple[bool, str]:
    f, c = load(), current()
    if "split" not in f:
        return False, "FROZEN.json has no frozen split: run `python -m bench.freeze --write` first"
    for k in ("grader_sha256", "cases_sha256", "protocol_sha256", "seed", "bootstrap_seed", "split"):
        if f.get(k) != c[k]:
            return False, f"FROZEN.json {k} does not match the current files: re-freeze and re-run dev"
    return True, "frozen state matches"


def main(argv: list[str]) -> int:
    c = current()
    if "--write" in argv:
        old = load()
        if "split" in old and "--refreeze" not in argv:
            print("refusing: FROZEN.json already holds a split (pass --refreeze; dev must then be re-run)",
                  file=sys.stderr)
            return 2
        legacy = {k: old[k] for k in ("sha256", "m2_legacy_sha256") if k in old}
        out = {**c, "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "m2_legacy_sha256": legacy.get("m2_legacy_sha256") or legacy.get("sha256")}
        FROZEN.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(c, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
