"""M1 pilot runner: plain Claude Code (A) vs Groundwork PR #62 (B) on read-only cases.

    python -m bench.run --runs-dir /tmp/groundwork-bench [--repeats 2] [--cases q1-retry-policy,...]

Order of work: subscription preflight → isolation canary (hard gate) → each case × repeat × arm in a fresh copy of the
fixture → independent grading → report. Each row is appended as soon as it finishes, and an existing row is skipped,
so a re-run continues instead of repeating finished work. Nothing is executed from the fixture and nothing is approved.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from groundwork_orchestrator.claude_adapter import preflight

from . import arms, canary, freeze, grade, report

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


def _git_head() -> str:
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", "orchestrator"],
                           capture_output=True, text=True).stdout.strip()
    return r.stdout.strip() + ("+dirty" if dirty else "")


def _over_quota(rate_limit: dict | None) -> str | None:
    windows = (rate_limit or {}).get("unifiedWindows") or {}
    for name, limit in QUOTA_STOP.items():
        used = (windows.get(name) or {}).get("utilization")
        if used is not None and used >= limit:
            return f"{name} utilisation {used:.2f} ≥ {limit}"
    return None


RETRY_ON_RERUN = {None, "error"}   # empty-answer cells whose cause may be transient (timeout, API error)


def _done(results: Path) -> set[tuple]:
    """Cells that need no re-run. An empty answer from a transient error is retried; a harness state such as BLOCKED
    is a real result about that harness and is kept."""
    done = set()
    for line in results.read_text().splitlines() if results.exists() else []:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        transient = not (r.get("final_text") or "").strip() and r.get("state") in RETRY_ON_RERUN
        (done.discard if transient else done.add)((r["case"], r["arm"], r["rep"]))
    return done


CONFIG_ARMS = {"V": ("GW_BENCH_VANILLA", "~/gw-bench/vanilla"), "G": ("GW_BENCH_GROUNDWORK", "~/gw-bench/groundwork")}


def arm_config_dir(arm: str) -> str | None:
    """V = vanilla Claude Code, G = Groundwork 2.5.0: each a separate, logged-in CLAUDE_CONFIG_DIR. A and B: None."""
    if arm not in CONFIG_ARMS:
        return None
    var, default = CONFIG_ARMS[arm]
    return os.path.expanduser(os.environ.get(var) or default)


def pair_order(wanted: set, k: int) -> list[str]:
    """The two arms of one case x repeat, alternating which goes first so caching and timing even out."""
    pair = ["V", "G"] if wanted & set(CONFIG_ARMS) else ["A", "B"]
    return pair if k % 2 == 0 else pair[::-1]


def preflight_dir(config_dir: str) -> tuple[bool, str]:
    """The subscription preflight, run against one config dir's own login."""
    old = os.environ.get("CLAUDE_CONFIG_DIR")
    os.environ["CLAUDE_CONFIG_DIR"] = config_dir
    try:
        return preflight()
    finally:
        if old is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = old


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("m1-%Y%m%dT%H%M%SZ"))
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--cases", default="")
    ap.add_argument("--arms", default="A,B", help="which arms to run (B is whatever orchestrator code is checked out)")
    a = ap.parse_args(argv)

    run_dir = Path(a.runs_dir).resolve() / a.run_id
    if REPO_ROOT == run_dir or REPO_ROOT in run_dir.parents:
        print("refusing: workspaces must not be inside the repository that holds the answer keys", file=sys.stderr)
        return 2
    ok, detail = preflight()
    if not ok:
        print(f"BLOCKED: {detail}", file=sys.stderr)
        return 4
    for arm in sorted(set(a.arms.split(",")) & set(CONFIG_ARMS)):
        ok, detail = preflight_dir(arm_config_dir(arm))
        if not ok:
            print(f"BLOCKED: arm {arm} ({arm_config_dir(arm)}): {detail}", file=sys.stderr)
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
    wanted = set(a.arms.split(","))
    results = run_dir / "results.jsonl"
    done = _done(results)
    ledger_before = set(p.name for p in LEDGER.iterdir()) if LEDGER.exists() else set()
    stop_reason = pending_stop = None
    for ci, case in enumerate(cases):
        key = grade.load_key(case)
        instruction = (BENCH / "tasks" / case / "instruction.md").read_text().strip()
        for rep in range(1, a.repeats + 1):
            order = pair_order(wanted, ci + rep)
            pending_stop = None
            for pos, arm in enumerate(order):
                if arm not in wanted or (case, arm, rep) in done or stop_reason:
                    continue
                cell = run_dir / case / f"{arm}-r{rep}"
                if cell.exists():
                    shutil.rmtree(cell)   # an unfinished cell from an interrupted run; its workspace is a copy
                cell.mkdir(parents=True)
                ws = _fresh_workspace(cell, "payments-client")
                started = datetime.now(timezone.utc).isoformat()
                if arm in ("A", *CONFIG_ARMS):
                    out = arms.run_arm_a(ws, instruction, ARM_A_MODEL, ARM_A_EFFORT, config_dir=arm_config_dir(arm))
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
                if arm in ("A", *CONFIG_ARMS):
                    pending_stop = _over_quota(out.get("rate_limit")) or pending_stop
            if pending_stop:
                stop_reason = pending_stop          # stop only after the A/B pair for this repeat is complete
    ledger_after = set(p.name for p in LEDGER.iterdir()) if LEDGER.exists() else set()
    meta = {"run_id": a.run_id, "finished_at": datetime.now(timezone.utc).isoformat(), "repeats": a.repeats,
            "cases": cases, "stop_reason": stop_reason, "arm_a": {"model": ARM_A_MODEL, "effort": ARM_A_EFFORT},
            "new_ledger_entries": sorted(ledger_after - ledger_before), "arms": sorted(wanted),
            "grader_fingerprint": freeze.current(), "code_commit": _git_head()}
    if wanted & set(CONFIG_ARMS):
        meta["config_dirs"] = {arm: arm_config_dir(arm) for arm in sorted(wanted & set(CONFIG_ARMS))}
        meta["fairness_note"] = ("Same request text, read-only tools, read fence, model (sonnet/medium) and plain `claude -p` "
                                 "launch in both arms. The only difference is the Claude Code config dir: V is a fresh "
                                 "vanilla install; G is the same plus Groundwork 2.5.0 (rules, hooks, ECC, OpenSpec).")
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    (run_dir / "report.md").write_text(report.render(results, meta))
    print(f"report: {run_dir / 'report.md'}" + (f" (stopped early: {stop_reason})" if stop_reason else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
