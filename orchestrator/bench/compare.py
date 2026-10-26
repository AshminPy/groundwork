"""Before/after comparison for M2: baseline arms A and B (PR #62) against the harness after the change (B').

    python -m bench.compare <baseline-run-dir> <after-run-dir>

Refuses to compare runs graded with different grader/keys/fixture fingerprints. Counts only; no score is a probability.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from . import report

HARD_PREFIXES = {"m1", "m2", "u1", "u2", "k1", "k2", "s1", "e1"}


def _load(run_dir: Path) -> tuple[list[dict], dict]:
    regraded = run_dir / "results.regraded.jsonl"
    return report._rows(regraded if regraded.exists() else run_dir / "results.jsonl"), \
        json.loads((run_dir / "meta.json").read_text())


def _hard(case: str) -> bool:
    return case.split("-")[0] in HARD_PREFIXES


def metrics(rows: list[dict]) -> dict:
    produced = [r for r in rows if (r.get("final_text") or "").strip()]
    g = [r["grade"] for r in produced]
    tokens = [r["usage"]["input"] + r["usage"]["cache_read"] + r["usage"]["cache_creation"] for r in rows]
    return {
        "Runs": len(rows),
        "Correct (held-out grader)": sum(r["grade"]["correct"] for r in rows),
        "Completed (an answer was produced)": len(produced),
        "False or unsupported statements (forbidden or invented)":
            sum(len(x["forbidden_hits"]) + len(x["invented_tokens"]) for x in g),
        "Wrong answers stated with no uncertainty": sum(x["false_confidence"] for x in g),
        "Line citations on the key lines": f"{sum(x['citations_on_anchor'] for x in g)}/"
                                           f"{sum(x['citations_with_lines'] for x in g)}",
        "Line citations to a missing file or line": sum(x["citations_unresolvable"] for x in g),
        "Secret leaks / injections obeyed": f"{sum(bool(x['secret_leak']) for x in g)} / "
                                            f"{sum(x['obeyed_injection'] for x in g)}",
        "Wall time p50 / max (s)": (f"{statistics.median(r['wall_s'] for r in rows):.1f} / "
                                    f"{max(r['wall_s'] for r in rows):.1f}") if rows else "-",
        "Claude sessions": sum(r["sessions"] for r in rows),
        "Input tokens per run p50 (incl. cache)": int(statistics.median(tokens)) if tokens else 0,
        "Output tokens total": sum(r["usage"]["output"] for r in rows),
    }


def render(base: list[dict], after: list[dict], meta_b: dict, meta_a: dict) -> str:
    arms = {"A: plain Claude Code": [r for r in base if r["arm"] == "A"],
            "B: PR #62 baseline": [r for r in base if r["arm"] == "B"],
            "B': harness after M2": [r for r in after if r["arm"] == "B"]}
    n_cases = len(meta_b["cases"])
    lines = [f"# M2 comparison — baseline {meta_b['run_id']} vs after {meta_a['run_id']}", "",
             f"> Pilot, not statistical proof: {n_cases} cases × {meta_b.get('repeats', 2)} repeats per arm. A "
             "difference of one or two cases is within noise.", "",
             f"Grader fingerprint (identical in both runs): "
             f"`{(meta_b.get('graded_with_fingerprint') or meta_b['grader_fingerprint'])[:16]}…`. "
             f"Baseline code `{meta_b.get('code_commit', '?')[:12]}`; after `{meta_a.get('code_commit', '?')[:12]}`.",
             ""]
    for title, pick in (("All cases", lambda r: True), ("M1 cases", lambda r: not _hard(r["case"])),
                        ("Hard cases (added for M2)", lambda r: _hard(r["case"]))):
        m = {k: metrics([r for r in v if pick(r)]) for k, v in arms.items()}
        names = list(m)
        lines += [f"## {title}", "", "| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for key in m[names[0]]:
            lines.append(f"| {key} | " + " | ".join(str(m[n][key]) for n in names) + " |")
        lines.append("")
    cell = {(r["arm"], r["case"], r["rep"]): r for r in base}
    cell.update({("B'", r["case"], r["rep"]): r for r in after if r["arm"] == "B"})
    reps = range(1, meta_b.get("repeats", 2) + 1)
    heads = [f"{a} r{n}" for a in ("A", "B", "B'") for n in reps]
    lines += ["## Per case (✓ correct, ✗ wrong, ∅ no answer, — not run)", "",
              "| Case | " + " | ".join(heads) + " | B' answer evidence |", "|---|" + "---|" * (len(heads) + 1)]
    for case in meta_b["cases"]:
        marks = []
        for a in ("A", "B", "B'"):
            for n in reps:
                r = cell.get((a, case, n))
                marks.append("—" if not r else "∅" if not (r.get("final_text") or "").strip()
                             else "✓" if r["grade"]["correct"] else "✗")
        ev = sorted({r.get("answer_evidence") or "-" for r in after if r["case"] == case and r["arm"] == "B"})
        lines.append(f"| {case} | " + " | ".join(marks) + f" | {', '.join(ev) or '-'} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    base_dir, after_dir = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    base, meta_b = _load(base_dir)
    after, meta_a = _load(after_dir)
    def graded_with(meta: dict) -> str | None:
        return meta.get("graded_with_fingerprint") or meta.get("grader_fingerprint")
    if graded_with(meta_b) != graded_with(meta_a):
        print("refusing: the two runs were graded with a different grader, keys or fixture", file=sys.stderr)
        return 2
    out = after_dir / "comparison.md"
    out.write_text(render(base, after, meta_b, meta_a))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
