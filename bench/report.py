"""Markdown report for a run: per-arm outcomes and cost, and (for held-out runs) the paired statistics and the
pre-registered decision. Counts only; nothing here is presented as a probability of being right."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from . import stats

ARMS = ("V", "E", "G")


def rows(results: Path) -> list[dict]:
    """The last row per (case, arm, rep) wins, so a retried cell replaces its failed attempt."""
    cells = {}
    for line in results.read_text().splitlines() if results.exists() else []:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        cells[(r["case"], r["arm"], r["rep"])] = r
    return list(cells.values())


def _f(x: float, pct: bool = False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x * 100:+.0f} pts" if pct else f"{x:,.0f}"


def _arm_table(rs: list[dict]) -> list[str]:
    by = defaultdict(list)
    for r in rs:
        by[r["arm"]].append(r)
    c = stats.costs(rs) if rs else {}
    out = ["| Arm | Runs | Completed | Incorrect claims | Probe pass | Errors/timeouts | Denials | Median wall s "
           "| Median tokens (out + uncached in) | Median cache read |", "|---|---|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        a = by.get(arm, [])
        if not a:
            continue
        g = [r.get("grade") or {} for r in a]
        w = [x for x in g if x.get("kind") == "write"]
        p = [x for x in g if x.get("kind") == "probe"]
        out.append(f"| {arm} | {len(a)} | {sum(bool(x.get('completed')) for x in w)}/{len(w)} | "
                   f"{sum(bool(x.get('incorrect_claim')) for x in w)} | "
                   f"{(str(sum(bool(x.get('probe_pass')) for x in p)) + '/' + str(len(p))) if p else '-'} | "
                   f"{sum(1 for r in a if not r.get('ok'))} | {sum(r.get('permission_denials', 0) for r in a)} | "
                   f"{c[arm]['median_wall_s']:.0f} | {_f(c[arm]['median_tokens'])} | {_f(c[arm]['median_cache_read'])} |")
    return out


def render(results: Path, meta: dict, frozen: dict) -> str:
    rs = rows(results)
    phase = meta.get("phase")
    lines = [f"# Benchmark report: {meta.get('run_id')} ({phase})", "",
             f"Model {meta.get('model')}/{meta.get('effort')}; grader `{(frozen.get('grader_sha256') or '')[:12]}`, "
             f"cases `{(frozen.get('cases_sha256') or '')[:12]}`; code `{meta.get('code_commit')}`."]
    if meta.get("stop_reason"):
        lines += ["", f"**Stopped early:** {meta['stop_reason']}. Re-run with the same `--run-id` to continue."]
    if meta.get("read_only_only"):
        lines += ["", "**The sandbox canary failed, so no write-capable case ran.**"]
    lines += ["", "## Outcomes and cost per arm", "", *_arm_table(rs), ""]
    lines += ["Tokens are output + uncached input + cache creation per run; cache reads are shown separately and not "
              "gated. Cost fields from Claude Code are list-price estimates and are not used."]
    if phase == "held":
        lines += _decision(rs, meta, frozen)
    elif phase == "calibration":
        lines += _calibration(rs, meta)
    lines += ["", "## Per run", "", "| Case | Arm | Rep | Completed | Claim | Wall s | Tokens | Error |",
              "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rs, key=lambda r: (r["case"], r["rep"], r["arm"])):
        g = r.get("grade") or {}
        done = g.get("completed") if g.get("kind") == "write" else ("probe pass" if g.get("probe_pass") else "probe FAIL")
        lines.append(f"| {r['case']} | {r['arm']} | {r['rep']} | {done} | {g.get('claims_complete')} | "
                     f"{r['wall_s']:.0f} | {_f(stats.run_cost(r))} | {r.get('error') or ''} |")
    return "\n".join(lines) + "\n"


def _decision(rs: list[dict], meta: dict, frozen: dict) -> list[str]:
    seed = frozen.get("bootstrap_seed", 0)
    scored = [r for r in rs if (r.get("grade") or {}).get("kind") == "write"]
    probes = [r for r in rs if (r.get("grade") or {}).get("kind") == "probe"] + meta.get("probe_rows", [])
    scores = stats.per_case(scored)
    cost = stats.costs(scored)
    out = ["", "## Decision (pre-registered, design B6)", "",
           "| Comparison | n | Mean diff | CI | W/T/L | MDD | Decision |", "|---|---|---|---|---|---|---|"]
    for a, b in stats.PRIMARY:
        c = stats.compare(scores, a, b, stats.PRIMARY_LEVEL, seed)
        out.append(f"| {a} − {b} (primary, {c['level']:.1%}) | {c['n']} | {_f(c['mean'], True)} | "
                   f"[{_f(c['ci'][0], True)}, {_f(c['ci'][1], True)}] | {c['wins']}/{c['ties']}/{c['losses']} | "
                   f"{_f(c['mdd'], True)} | {stats.decide(c, cost, stats.probes_pass(probes, a))} |")
    c = stats.compare(scores, "E", "V", stats.SECONDARY_LEVEL, seed)
    out.append(f"| E − V (secondary, 95%) | {c['n']} | {_f(c['mean'], True)} | [{_f(c['ci'][0], True)}, "
               f"{_f(c['ci'][1], True)}] | {c['wins']}/{c['ties']}/{c['losses']} | {_f(c['mdd'], True)} | reported |")
    ic = stats.per_case(scored, "incorrect_claim")
    for a, b in stats.PRIMARY:
        c = stats.compare(ic, a, b, stats.SECONDARY_LEVEL, seed)
        out.append(f"| incorrect claims {a} − {b} (lower is better, 95%) | {c['n']} | {_f(c['mean'], True)} | "
                   f"[{_f(c['ci'][0], True)}, {_f(c['ci'][1], True)}] | {c['wins']}/{c['ties']}/{c['losses']} | "
                   f"{_f(c['mdd'], True)} | reported |")
    nf = stats.noise_floor(scored, seed)
    out += ["", f"Noise floor (V repeat 1 − repeat 2, {nf['n']} cases): mean {_f(nf['mean'], True)}, 95% CI "
                f"[{_f(nf['ci'][0], True)}, {_f(nf['ci'][1], True)}].",
            "This is a screening result: 14 held-out cases can only detect large differences (see MDD)."]
    return out


def _calibration(rs: list[dict], meta: dict) -> list[str]:
    scored = [r for r in rs if (r.get("grade") or {}).get("kind") == "write"]
    cost = stats.costs(rs) if rs else {}
    planned = meta.get("planned_runs", {})
    out = ["", "## Calibration estimate for the full baseline", ""]
    total_s = 0.0
    for arm in ARMS:
        if arm in cost:
            per = sum(r["wall_s"] for r in rs if r["arm"] == arm) / max(1, sum(1 for r in rs if r["arm"] == arm))
            n = planned.get(arm, 0)
            total_s += per * n
            out.append(f"- **{arm}:** mean {per:.0f} s per run × {n} planned runs ≈ {per * n / 3600:.1f} h; "
                       f"median {_f(cost[arm]['median_tokens'])} tokens and {_f(cost[arm]['median_cache_read'])} "
                       "cache-read tokens per run.")
    out.append(f"- **All arms, sequential:** about {total_s / 3600:.1f} h of run time.")
    scores = stats.per_case(scored)
    for a, b in stats.PRIMARY:
        c = stats.compare(scores, a, b, stats.PRIMARY_LEVEL, 0)
        out.append(f"- **{a} − {b} on the {c['n']} calibration cases:** spread (SD) {_f(c['sd'], True)}; "
                   f"the minimum detectable difference at 14 cases would be about "
                   f"{_f(stats.MDD_FACTOR * c['sd'] / 14 ** 0.5, True) if c['n'] > 1 else 'n/a'}. "
                   "Three cases × one run is far too few to estimate this well; treat it as an order of magnitude.")
    return out
