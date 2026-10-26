"""Turns results.jsonl into a short Markdown report. Counts only; no score is presented as a probability."""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

PILOT_NOTE = ("Initial pilot, not statistical proof: 12 cases × 2 repeats per arm. A difference of one or two cases "
              "is within noise. Use it to find grader bugs, size usage, and spot large gaps only.")
FAIRNESS_NOTE = ("Same request text, tools, read fence, settings and answer model (sonnet/medium) in both arms. Arm B "
                 "also runs its own classifier (haiku, only on a rule tie), a JSON output schema and its own worker "
                 "prompt: that is the system under test, not a bias. 'No answer produced' counts a harness failure "
                 "or misrouting; 'correct among produced answers' isolates answer quality.")


def _rows(results: Path) -> list[dict]:
    """The last row per (case, arm, rep) wins, so a retried cell replaces its failed attempt."""
    cells = {}
    for line in results.read_text().splitlines() if results.exists() else []:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        cells[(r["case"], r["arm"], r["rep"])] = r
    return list(cells.values())


def summarize(rows: list[dict]) -> dict:
    by = defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    out = {}
    for arm, rs in sorted(by.items()):
        g = [r["grade"] for r in rs if (r.get("final_text") or "").strip()]   # answer quality: produced answers only
        tokens_in = [r["usage"]["input"] + r["usage"]["cache_read"] + r["usage"]["cache_creation"] for r in rs]
        produced = [r for r in rs if (r.get("final_text") or "").strip()]
        out[arm] = {
            "runs": len(rs),
            "correct": sum(r["grade"]["correct"] for r in rs),
            "no_answer": len(rs) - len(produced),
            "correct_among_produced": f"{sum(r['grade']['correct'] for r in produced)}/{len(produced)}",
            "facts": f"{sum(x['facts_found'] for x in g)}/{sum(x['facts_required'] for x in g)}",
            "wrong_without_hedging": sum(x["false_confidence"] for x in g),
            "citations_with_lines": sum(x["citations_with_lines"] for x in g),
            "citations_on_anchor": sum(x["citations_on_anchor"] for x in g),
            "citations_unresolvable": sum(x["citations_unresolvable"] for x in g),
            "anchor_files_cited": f"{sum(x['anchor_files_cited'] for x in g)}/{sum(x['anchor_files'] for x in g)}",
            "secret_leaks": sum(bool(x["secret_leak"]) for x in g),
            "obeyed_injection": sum(x["obeyed_injection"] for x in g),
            "outside_read_attempts": sum(r.get("outside_read_attempts") or 0 for r in rs),
            "lists_unknowns": sum(x.get("lists_unknowns", False) for x in g),
            "harness_failures": sum(not r["ok"] for r in rs),
            "harness_states": dict(sorted(Counter(r.get("state") or ("ok" if r["ok"] else "error") for r in rs).items())),
            "harness_categories": dict(sorted(Counter(r["harness_category"] for r in rs if r.get("harness_category")).items())),
            "wall_s_p50": statistics.median(r["wall_s"] for r in rs),
            "wall_s_max": max(r["wall_s"] for r in rs),
            "sessions": sum(r["sessions"] for r in rs),
            "input_tokens_p50": statistics.median(tokens_in),
            "output_tokens_total": sum(r["usage"]["output"] for r in rs),
            "models": sorted({m for r in rs for m in r.get("models") or []}),
        }
    return out


LABELS = [("runs", "Runs"), ("correct", "Correct (held-out grader), all runs"), ("no_answer", "No answer produced"),
          ("correct_among_produced", "Correct among produced answers"),
          ("facts", "Required facts found (produced answers; rows below likewise)"),
          ("wrong_without_hedging", "Wrong answers with no uncertainty stated"),
          ("citations_with_lines", "Citations with line numbers"),
          ("citations_on_anchor", "…of which on the key lines (±2)"),
          ("citations_unresolvable", "Unresolvable citations"),
          ("anchor_files_cited", "Key files cited on a key line"),
          ("secret_leaks", "Secret or canary leaks"), ("obeyed_injection", "Obeyed a prompt injection"),
          ("outside_read_attempts", "Reads attempted outside the workspace (A only; refused)"),
          ("lists_unknowns", "Runs that list unknowns in a structured field"),
          ("harness_failures", "Harness failures (not PASSED / error)"),
          ("harness_states", "Final states"), ("harness_categories", "B's own task category"),
          ("wall_s_p50", "Wall time p50 (s)"), ("wall_s_max", "Wall time max (s)"),
          ("sessions", "Claude sessions"), ("input_tokens_p50", "Input tokens per run p50 (incl. cache)"),
          ("output_tokens_total", "Output tokens total"), ("models", "Models used")]


def render(results: Path, meta: dict) -> str:
    rows = _rows(results)
    s = summarize(rows)
    arms = sorted(s)
    lines = [f"# M1 pilot report — {meta['run_id']}", "", f"> {PILOT_NOTE}", "", f"> {meta.get('fairness_note') or FAIRNESS_NOTE}", ""]
    if meta.get("stop_reason"):
        lines += [f"[!] Stopped early: {meta['stop_reason']}", ""]
    lines += ["| Metric | " + " | ".join(f"Arm {a}" for a in arms) + " |", "|---|" + "---|" * len(arms)]
    for k, label in LABELS:
        lines.append(f"| {label} | " + " | ".join(str(s[a][k]) for a in arms) + " |")
    reps = range(1, meta.get("repeats", 2) + 1)
    run_arms = meta.get("arms") or ["A", "B"]
    heads = [f"{arm} r{rep}" for arm in run_arms for rep in reps]
    lines += ["", "## Per case (✓ correct, ✗ wrong, ∅ no answer, — not run)", "",
              "| Case | Cat | " + " | ".join(heads) + " |", "|---|---|" + "---|" * len(heads)]
    cell = {(r["case"], r["arm"], r["rep"]): r for r in rows}
    for case in meta["cases"]:
        cat = next((r["category"] for r in rows if r["case"] == case), "")
        marks = []
        for arm in run_arms:
            for rep in reps:
                r = cell.get((case, arm, rep))
                if not r:
                    marks.append("—")
                elif not (r.get("final_text") or "").strip():
                    marks.append(f"∅ {r.get('state') or 'error'}")
                else:
                    marks.append(("✓" if r["grade"]["correct"] else "✗") + ("" if r["ok"] else " (fail)"))
        lines.append(f"| {case} | {cat} | " + " | ".join(marks) + " |")
    lines += ["", f"New Groundwork ledger entries created during the run: {len(meta.get('new_ledger_entries') or [])}"]
    return "\n".join(lines) + "\n"
