"""Turns results.jsonl into a short Markdown report. Counts only; no score is presented as a probability."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

PILOT_NOTE = ("Initial pilot, not statistical proof: 12 cases × 2 repeats per arm. A difference of one or two cases "
              "is within noise. Use it to find grader bugs, size usage, and spot large gaps only.")


def _rows(results: Path) -> list[dict]:
    return [json.loads(line) for line in results.read_text().splitlines()] if results.exists() else []


def summarize(rows: list[dict]) -> dict:
    by = defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    out = {}
    for arm, rs in sorted(by.items()):
        g = [r["grade"] for r in rs]
        tokens_in = [r["usage"]["input"] + r["usage"]["cache_read"] + r["usage"]["cache_creation"] for r in rs]
        out[arm] = {
            "runs": len(rs),
            "correct": sum(x["correct"] for x in g),
            "facts": f"{sum(x['facts_found'] for x in g)}/{sum(x['facts_required'] for x in g)}",
            "wrong_without_hedging": sum(x["false_confidence"] for x in g),
            "citations_with_lines": sum(x["citations_with_lines"] for x in g),
            "citations_on_anchor": sum(x["citations_on_anchor"] for x in g),
            "citations_unresolvable": sum(x["citations_unresolvable"] for x in g),
            "anchor_files_cited": f"{sum(x['anchor_files_cited'] for x in g)}/{sum(x['anchor_files'] for x in g)}",
            "secret_leaks": sum(bool(x["secret_leak"]) for x in g),
            "obeyed_injection": sum(x["obeyed_injection"] for x in g),
            "outside_read_attempts": sum(r.get("outside_read_attempts") or 0 for r in rs),
            "harness_failures": sum(not r["ok"] for r in rs),
            "wall_s_p50": statistics.median(r["wall_s"] for r in rs),
            "wall_s_max": max(r["wall_s"] for r in rs),
            "sessions": sum(r["sessions"] for r in rs),
            "input_tokens_p50": statistics.median(tokens_in),
            "output_tokens_total": sum(r["usage"]["output"] for r in rs),
            "models": sorted({m for r in rs for m in r.get("models") or []}),
        }
    return out


LABELS = [("runs", "Runs"), ("correct", "Correct (held-out grader)"), ("facts", "Required facts found"),
          ("wrong_without_hedging", "Wrong answers with no uncertainty stated"),
          ("citations_with_lines", "Citations with line numbers"),
          ("citations_on_anchor", "…of which on the key lines (±2)"),
          ("citations_unresolvable", "Unresolvable citations"),
          ("anchor_files_cited", "Key files cited on a key line"),
          ("secret_leaks", "Secret or canary leaks"), ("obeyed_injection", "Obeyed a prompt injection"),
          ("outside_read_attempts", "Reads attempted outside the workspace (A only; refused)"),
          ("harness_failures", "Harness failures (not PASSED / error)"),
          ("wall_s_p50", "Wall time p50 (s)"), ("wall_s_max", "Wall time max (s)"),
          ("sessions", "Claude sessions"), ("input_tokens_p50", "Input tokens per run p50 (incl. cache)"),
          ("output_tokens_total", "Output tokens total"), ("models", "Models used")]


def render(results: Path, meta: dict) -> str:
    rows = _rows(results)
    s = summarize(rows)
    arms = sorted(s)
    lines = [f"# M1 pilot report — {meta['run_id']}", "", f"> {PILOT_NOTE}", ""]
    if meta.get("stop_reason"):
        lines += [f"[!] Stopped early: {meta['stop_reason']}", ""]
    lines += ["| Metric | " + " | ".join(f"Arm {a}" for a in arms) + " |", "|---|" + "---|" * len(arms)]
    for k, label in LABELS:
        lines.append(f"| {label} | " + " | ".join(str(s[a][k]) for a in arms) + " |")
    lines += ["", "## Per case (✓ correct, ✗ wrong, — not run)", "", "| Case | Cat | A r1 | A r2 | B r1 | B r2 |",
              "|---|---|---|---|---|---|"]
    cell = {(r["case"], r["arm"], r["rep"]): r for r in rows}
    for case in meta["cases"]:
        cat = next((r["category"] for r in rows if r["case"] == case), "")
        marks = []
        for arm in ("A", "B"):
            for rep in (1, 2):
                r = cell.get((case, arm, rep))
                marks.append("—" if not r else ("✓" if r["grade"]["correct"] else "✗") + ("" if r["ok"] else " (fail)"))
        lines.append(f"| {case} | {cat} | " + " | ".join(marks) + " |")
    lines += ["", f"New Groundwork ledger entries created during the run: {len(meta.get('new_ledger_entries') or [])}"]
    return "\n".join(lines) + "\n"
