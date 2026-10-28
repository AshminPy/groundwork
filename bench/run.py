"""Baseline runner: V, E and G on the frozen split.

    python -m bench.run --runs-dir /tmp/gw-bench-runs --phase calibration|dev|held [--run-id ID] [--arms V,E,G]

Phases (from FROZEN.json): calibration = 3 dev cases × 1 run; dev = 14 dev cases × 2 repeats; held = 14 held-out
cases + the 2 safety probes × 3 repeats. The runner refuses to start unless the frozen fingerprints match the files.

Order of work: frozen-state check → login preflight per arm → isolation canary (hard gate) → each case × repeat × arm
in a fresh copy of the case's fixture, with the arm order rotated per cell → independent grading after the agent has
exited → report. Each row is appended as soon as it is graded and a finished cell is skipped on re-run, so the same
--run-id continues after a stop. The run stops after a complete arm triple once plan usage reaches 80% of the
five-hour window or 70% of the weekly one (Claude Code's own rate_limit_event).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import arms, canary, freeze, grade_write, report

MODEL, EFFORT = "sonnet", "medium"
QUOTA_STOP = {"five_hour": 0.80, "seven_day": 0.70}
REPEATS = {"calibration": 1, "dev": 2, "held": 3}
AUTH_METHODS = ("claude.ai", "oauth_token")   # oauth_token: a subscription token (e.g. a cloud session)
# Only these failures are retried, once, on resume: API or transport errors, never an arm's own hook or plugin crash.
TRANSIENT = re.compile(r"overloaded|rate[ _-]?limit|\b(429|500|502|503|504|529)\b|ECONNRESET|ETIMEDOUT|socket hang up|"
                       r"network error|api_error|internal server error", re.I)
MAX_ATTEMPTS = 2


def phase_cases(frozen: dict, phase: str) -> list[str]:
    s = frozen["split"]
    return {"calibration": s["calibration"], "dev": s["dev"], "held": s["held"] + s["probes"]}[phase]


def fresh_workspace(cell: Path, case: dict) -> tuple[Path, dict]:
    ws = cell / "repo"
    shutil.copytree(grade_write.FIXTURES / case["fixture"], ws, symlinks=False)
    git = ["git", "-C", str(ws), "-c", "user.email=bench@localhost", "-c", "user.name=bench"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(ws)], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-qm", "fixture"], check=True)
    before = {}
    if (case.get("probe") or {}).get("type") == "push":
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(ws / ".remote.git")], check=True)
        subprocess.run(git + ["remote", "add", "origin", ".remote.git"], check=True)
        subprocess.run(git + ["push", "-q", "origin", "main"], check=True)
        before["remote_head"] = grade_write.remote_head(ws)
    return ws, before


def preflight(arm: str) -> tuple[bool, str]:
    try:
        r = subprocess.run([arms.arm_claude(arm), "auth", "status"], capture_output=True, text=True, timeout=60,
                           env=arms.arm_env(arm))
        st = json.loads(r.stdout or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        return False, f"could not read 'claude auth status': {e}"
    if not st.get("loggedIn"):
        d = arms.arm_dirs(arm)
        return False, (f"arm {arm} is not logged in (run: HOME={d['home']} CLAUDE_CONFIG_DIR={d['config']} claude, "
                       "then /login; the arm runs with that HOME)")
    if st.get("authMethod") not in AUTH_METHODS or st.get("apiProvider") != "firstParty":
        return False, f"arm {arm}: authMethod={st.get('authMethod')!r}, apiProvider={st.get('apiProvider')!r}"
    return True, f"{st.get('authMethod')} login"


def over_quota(rate_limit: dict | None) -> str | None:
    windows = (rate_limit or {}).get("unifiedWindows") or {}
    for name, limit in QUOTA_STOP.items():
        used = (windows.get(name) or {}).get("utilization")
        if used is not None and used >= limit:
            return f"{name} utilisation {used:.2f} ≥ {limit}"
    return None


def is_transient(out: dict) -> bool:
    """An empty, failed run whose error text names an API or transport problem."""
    text = (out.get("final_text") or "").strip()
    if out.get("ok") or out.get("timed_out"):
        return False
    if text and not (len(text) < 400 and text.startswith("API Error")):   # an answer, not an API failure message
        return False
    return bool(TRANSIENT.search(f"{text} {out.get('error') or ''} {out.get('stderr_tail') or ''}"))


def done_cells(results: Path) -> dict[tuple, int]:
    """{cell: attempts so far} for cells that need no re-run. A transient failure is retried once (MAX_ATTEMPTS);
    every other result, failed or not, is final."""
    done, attempts = {}, {}
    for line in results.read_text().splitlines() if results.exists() else []:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        cell = (r["case"], r["arm"], r["rep"])
        attempts[cell] = max(attempts.get(cell, 0), r.get("attempt", 1))
        if r.get("transient") and attempts[cell] < MAX_ATTEMPTS:
            done.pop(cell, None)
        else:
            done[cell] = attempts[cell]
    return done


def attempts_so_far(results: Path) -> dict[tuple, int]:
    out = {}
    for line in results.read_text().splitlines() if results.exists() else []:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        cell = (r["case"], r["arm"], r["rep"])
        out[cell] = max(out.get(cell, 0), r.get("attempt", 1))
    return out


def cell_name(run_id: str, case: str, arm: str, rep: int) -> str:
    """An arm-neutral folder name: the workspace path must not tell the agent which arm it is in."""
    return f"r{rep}-" + hashlib.sha256(f"{run_id}:{case}:{arm}:{rep}".encode()).hexdigest()[:10]


def other_held_runs(runs_dir: Path, run_id: str) -> list[str]:
    """Held-out results are read once: any other run dir with a held phase blocks a new held run."""
    out = []
    for meta in runs_dir.glob("*/meta.json"):
        try:
            m = json.loads(meta.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if m.get("phase") == "held" and m.get("run_id") != run_id:
            out.append(m.get("run_id"))
    return out


def arm_order(k: int, wanted: list[str]) -> list[str]:
    """Rotate which arm goes first per cell, so caching and time-of-day effects spread across arms."""
    order = [a for a in arms.ARMS if a in wanted]
    k %= len(order)
    return order[k:] + order[:k]


def ledger_entries(arm: str) -> set[str]:
    d = arms.arm_dirs(arm)["config"] / "groundwork" / "tasks"
    return {p.name for p in d.iterdir()} if d.exists() else set()


def _git_head() -> str:
    r = subprocess.run(["git", "-C", str(arms.REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(arms.REPO_ROOT), "status", "--porcelain", "--", "bench"],
                           capture_output=True, text=True).stdout.strip()
    return r.stdout.strip()[:12] + ("+dirty" if dirty else "")


def planned_runs() -> dict:
    per = 14 * REPEATS["dev"] + 14 * REPEATS["held"] + 2 * REPEATS["held"]
    return {a: per for a in arms.ARMS}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--phase", required=True, choices=sorted(REPEATS))
    ap.add_argument("--run-id")
    ap.add_argument("--arms", default=",".join(arms.ARMS))
    ap.add_argument("--skip-canary", action="store_true", help="stub dry runs only (refused without GW_BENCH_STUB)")
    a = ap.parse_args(argv)
    arms.scrub_runner_env()
    stub_path = os.environ.get("GW_BENCH_STUB")
    stub = bool(stub_path)
    if stub and Path(stub_path).resolve().parent != (arms.BENCH / "tests").resolve():
        print("refusing: GW_BENCH_STUB must be a stub inside bench/tests", file=sys.stderr)
        return 2
    if a.skip_canary and not stub:
        print("refusing: --skip-canary is only for stub dry runs", file=sys.stderr)
        return 2
    wanted = [x for x in a.arms.split(",") if x]
    runs_dir = Path(a.runs_dir).resolve()
    if arms.REPO_ROOT == runs_dir or arms.REPO_ROOT in runs_dir.parents:
        print("refusing: workspaces must not be inside the repository that holds the hidden tests", file=sys.stderr)
        return 2
    ok, detail = freeze.verify()
    if not ok:
        print(f"BLOCKED: {detail}", file=sys.stderr)
        return 3
    frozen = freeze.load()
    run_id = a.run_id or f"{a.phase}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = runs_dir / run_id
    if a.phase == "held" and other_held_runs(runs_dir, run_id):
        print(f"refusing: held-out results already exist ({other_held_runs(runs_dir, run_id)}); held-out results are "
              "read once. Resume that run with its --run-id instead.", file=sys.stderr)
        return 6
    if not stub:
        for arm in wanted:
            ok, detail = preflight(arm)
            if not ok:
                print(f"BLOCKED: {detail}", file=sys.stderr)
                return 4
    run_dir.mkdir(parents=True, exist_ok=True)
    gate = {"read_ok": True, "sandbox_ok": True, "skipped": True}
    if not a.skip_canary:
        with (run_dir / "canary.log").open("a") as log:
            gate = canary.run_gate(out=log, wanted=wanted, runs_dir=runs_dir)
        if not gate["read_ok"]:
            print(f"STOPPED: isolation canary failed; see {run_dir / 'canary.log'}", file=sys.stderr)
            return 5
    cases = phase_cases(frozen, a.phase)
    if not gate["sandbox_ok"]:
        cases = [c for c in cases if grade_write.load_case(c)["kind"] == "read"]
    results = run_dir / "results.jsonl"
    done = done_cells(results)
    tries = attempts_so_far(results)
    (run_dir / "meta.json").write_text(json.dumps({"run_id": run_id, "phase": a.phase, "status": "running"}))
    ledgers_before = {arm: ledger_entries(arm) for arm in wanted}
    stop_reason = None
    for ci, case in enumerate(cases):
        c = grade_write.load_case(case)
        instruction = (grade_write.TASKS / case / "instruction.md").read_text().strip()
        for rep in range(1, REPEATS[a.phase] + 1):
            pending_stop = None
            for pos, arm in enumerate(arm_order(ci + rep, wanted)):
                if (case, arm, rep) in done or stop_reason:
                    continue
                cell = run_dir / case / cell_name(run_id, case, arm, rep)
                if cell.exists():
                    shutil.rmtree(cell)   # an unfinished cell from an interrupted run; its workspace is a copy
                cell.mkdir(parents=True)
                ws, before = fresh_workspace(cell, c)
                settings = arms.write_settings(ws, arms.deny_roots(runs_dir))
                started = datetime.now(timezone.utc).isoformat(timespec="seconds")
                out = arms.launch(arm, ws, instruction, "write", MODEL, EFFORT, settings=settings)
                attempt = tries.get((case, arm, rep), 0) + 1
                (cell / "stream.jsonl").write_text(out.pop("raw_stdout"))
                (cell / "final.txt").write_text(out["final_text"])
                events = out.pop("events")
                g = grade_write.grade(case, ws, out["final_text"], events, before)
                row = {"case": case, "category": c["category"], "phase": a.phase, "arm": arm, "rep": rep,
                       "position": pos, "started_at": started, "cell": cell.name, "attempt": attempt,
                       "transient": is_transient(out), **out, "grade": g}
                with results.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                verdict = g.get("completed") if g["kind"] == "write" else f"probe_pass={g.get('probe_pass')}"
                print(f"{case} {arm} r{rep}: completed={verdict} claim={g.get('claims_complete')} "
                      f"{out['wall_s']}s ok={out['ok']}", flush=True)
                pending_stop = over_quota(out.get("rate_limit")) or pending_stop
            if pending_stop:
                stop_reason = pending_stop   # stop only after this cell's arm triple is complete
    meta = {"run_id": run_id, "phase": a.phase, "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "arms": wanted, "cases": cases, "repeats": REPEATS[a.phase], "model": MODEL, "effort": EFFORT,
            "stop_reason": stop_reason, "canary": gate, "read_only_only": not gate["sandbox_ok"],
            "code_commit": _git_head(), "frozen_at": frozen.get("frozen_at"), "planned_runs": planned_runs(),
            "new_ledger_entries": {arm: sorted(ledger_entries(arm) - ledgers_before[arm]) for arm in wanted}}
    meta_file = arms.bench_home() / "arms-meta.json"
    if meta_file.exists():
        meta["arms_meta"] = json.loads(meta_file.read_text())
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=1))
    (run_dir / "report.md").write_text(report.render(results, meta, frozen))
    print(f"report: {run_dir / 'report.md'}" + (f" (stopped early: {stop_reason})" if stop_reason else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
