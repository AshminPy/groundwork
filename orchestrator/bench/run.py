"""M1 pilot runner: plain Claude Code (A) vs Groundwork PR #62 (B) on read-only cases.

    python -m bench.run --runs-dir /tmp/groundwork-bench [--repeats 2] [--cases q1-retry-policy,...]

Order of work: subscription preflight → isolation canary (hard gate) → each case × repeat × arm in a fresh copy of the
fixture → independent grading → report. Each row is appended as soon as it finishes, and an existing row is skipped,
so a re-run continues instead of repeating finished work. Nothing is executed from the fixture and nothing is approved.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from groundwork_orchestrator.claude_adapter import preflight

from . import arms, canary, grade, report

BENCH = Path(__file__).resolve().parent
REPO_ROOT = BENCH.parents[1]
ARM_A_MODEL, ARM_A_EFFORT = "sonnet", "medium"   # PR #62's routing.json "answer" and "document" roles
QUOTA_STOP = {"five_hour": 0.80, "seven_day": 0.70}
LEDGER = Path.home() / ".claude" / "groundwork" / "tasks"


def _fresh_workspace(dest: Path, fixture: str) -> Path:
    ws = dest / "repo"
    shutil.copytree(grade.FIXTURES / fixture, ws)
    git = ["git", "-C", str(ws), "-c", "user.email=bench@localhost", "-c", "user.name=bench"]
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-qm", "fixture"], check=True)
    return ws


def _over_quota(rate_limit: dict | None) -> str | None:
    windows = (rate_limit or {}).get("unifiedWindows") or {}
    for name, limit in QUOTA_STOP.items():
        used = (windows.get(name) or {}).get("utilization")
        if used is not None and used >= limit:
            return f"{name} utilisation {used:.2f} ≥ {limit}"
    return None


def _done(results: Path) -> set[tuple]:
    if not results.exists():
        return set()
    return {(r["case"], r["arm"], r["rep"]) for r in map(json.loads, results.read_text().splitlines())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("m1-%Y%m%dT%H%M%SZ"))
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--cases", default="")
    a = ap.parse_args(argv)

    run_dir = Path(a.runs_dir).resolve() / a.run_id
    if REPO_ROOT == run_dir or REPO_ROOT in run_dir.parents:
        print("refusing: workspaces must not be inside the repository that holds the answer keys", file=sys.stderr)
        return 2
    ok, detail = preflight()
    if not ok:
        print(f"BLOCKED: {detail}", file=sys.stderr)
        return 4
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "canary.log").open("a") as log:
        passed = canary.run_gate(out=log)
    if not passed:
        print(f"STOPPED: isolation canary failed; see {run_dir / 'canary.log'}", file=sys.stderr)
        return 5

    cases = sorted(p.name for p in (BENCH / "tasks").iterdir() if p.is_dir())
    if a.cases:
        cases = [c for c in cases if c in a.cases.split(",")]
    results = run_dir / "results.jsonl"
    done = _done(results)
    ledger_before = set(p.name for p in LEDGER.iterdir()) if LEDGER.exists() else set()
    stop_reason = None
    for ci, case in enumerate(cases):
        key = grade.load_key(case)
        instruction = (BENCH / "tasks" / case / "instruction.md").read_text().strip()
        for rep in range(1, a.repeats + 1):
            order = ["A", "B"] if (ci + rep) % 2 == 0 else ["B", "A"]
            for pos, arm in enumerate(order):
                if (case, arm, rep) in done or stop_reason:
                    continue
                cell = run_dir / case / f"{arm}-r{rep}"
                if cell.exists():
                    shutil.rmtree(cell)   # an unfinished cell from an interrupted run; its workspace is a copy
                cell.mkdir(parents=True)
                ws = _fresh_workspace(cell, "payments-client")
                started = datetime.now(timezone.utc).isoformat()
                if arm == "A":
                    out = arms.run_arm_a(ws, instruction, ARM_A_MODEL, ARM_A_EFFORT)
                    (cell / "stream.jsonl").write_text(out.pop("raw_stdout"))
                else:
                    out = arms.run_arm_b(ws, instruction, cell / "orch-home")
                (cell / "final.txt").write_text(out["final_text"])
                row = {"case": case, "category": key["category"], "arm": arm, "rep": rep, "position": pos,
                       "started_at": started, **out, "grade": grade.grade(key, out["final_text"])}
                with results.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                g = row["grade"]
                print(f"{case} {arm} r{rep}: {'correct' if g['correct'] else 'WRONG'} "
                      f"({g['facts_found']}/{g['facts_required']} facts, {out['wall_s']}s, ok={out['ok']})", flush=True)
                if arm == "A":
                    stop_reason = _over_quota(out.get("rate_limit"))
    ledger_after = set(p.name for p in LEDGER.iterdir()) if LEDGER.exists() else set()
    meta = {"run_id": a.run_id, "finished_at": datetime.now(timezone.utc).isoformat(), "repeats": a.repeats,
            "cases": cases, "stop_reason": stop_reason, "arm_a": {"model": ARM_A_MODEL, "effort": ARM_A_EFFORT},
            "new_ledger_entries": sorted(ledger_after - ledger_before)}
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    (run_dir / "report.md").write_text(report.render(results, meta))
    print(f"report: {run_dir / 'report.md'}" + (f" (stopped early: {stop_reason})" if stop_reason else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
