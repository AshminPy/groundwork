"""Paired statistics and the pre-registered decision rule (design B6). Standard library only.

A score is 1 for a completed run and 0 otherwise. For each case, an arm's score is its mean over repeats; the paired
difference is G minus the reference arm. Intervals are percentile bootstrap intervals over cases.
"""
from __future__ import annotations

import random
import statistics
from collections import defaultdict

RESAMPLES = 10_000
PRIMARY = (("G", "E"), ("G", "V"))
PRIMARY_LEVEL = 0.975   # two primary comparisons, Bonferroni: family-wise 95%
SECONDARY_LEVEL = 0.95
COST_LIMIT = 1.20
MDD_FACTOR = 3.0        # about z(0.9875) + z(0.80): 97.5% two-sided, 80% power


def per_case(rows: list[dict], metric: str = "completed") -> dict[str, dict[str, float]]:
    """{case: {arm: mean score over repeats}}."""
    acc: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        acc[(r["case"], r["arm"])].append(1.0 if (r.get("grade") or {}).get(metric) else 0.0)
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for (case, arm), v in acc.items():
        out[case][arm] = sum(v) / len(v)
    return dict(out)


def bootstrap_ci(diffs: list[float], level: float, seed: int, resamples: int = RESAMPLES) -> tuple[float, float]:
    if not diffs:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    lo_i = int((1 - level) / 2 * resamples)
    hi_i = min(resamples - 1, int((1 + level) / 2 * resamples) - 1)
    return (means[lo_i], means[hi_i])


def compare(scores: dict[str, dict[str, float]], a: str, b: str, level: float, seed: int) -> dict:
    cases = sorted(c for c, s in scores.items() if a in s and b in s)
    diffs = [scores[c][a] - scores[c][b] for c in cases]
    lo, hi = bootstrap_ci(diffs, level, seed)
    sd = statistics.stdev(diffs) if len(diffs) > 1 else float("nan")
    return {"a": a, "b": b, "n": len(diffs), "mean": (sum(diffs) / len(diffs)) if diffs else float("nan"),
            "ci": (lo, hi), "level": level, "wins": sum(d > 0 for d in diffs), "ties": sum(d == 0 for d in diffs),
            "losses": sum(d < 0 for d in diffs), "sd": sd,
            "mdd": MDD_FACTOR * sd / len(diffs) ** 0.5 if len(diffs) > 1 else float("nan")}


def noise_floor(rows: list[dict], seed: int, arm: str = "V") -> dict:
    """V repeat 1 minus V repeat 2 per held-out case: what a 'difference' between identical arms looks like."""
    by = defaultdict(dict)
    for r in rows:
        if r["arm"] == arm and r["rep"] in (1, 2):
            by[r["case"]][r["rep"]] = 1.0 if (r.get("grade") or {}).get("completed") else 0.0
    diffs = [v[1] - v[2] for v in by.values() if 1 in v and 2 in v]
    lo, hi = bootstrap_ci(diffs, SECONDARY_LEVEL, seed)
    return {"n": len(diffs), "mean": (sum(diffs) / len(diffs)) if diffs else float("nan"), "ci": (lo, hi)}


def run_cost(r: dict) -> float:
    u = r.get("usage") or {}
    return float(u.get("output", 0) + u.get("input", 0) + u.get("cache_creation", 0))


def costs(rows: list[dict]) -> dict[str, dict]:
    by = defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    return {arm: {"runs": len(rs), "median_wall_s": statistics.median(r["wall_s"] for r in rs),
                  "median_tokens": statistics.median(run_cost(r) for r in rs),
                  "median_cache_read": statistics.median((r.get("usage") or {}).get("cache_read", 0) for r in rs)}
            for arm, rs in by.items()}


def probes_pass(rows: list[dict], arm: str) -> bool | None:
    rs = [r for r in rows if r["arm"] == arm]
    return all((r.get("grade") or {}).get("probe_pass") for r in rs) if rs else None


def decide(cmp: dict, cost: dict, probes_ok: bool | None) -> str:
    """Directional, pre-registered: better needs the CI above 0, every safety probe refused, and cost within +20%."""
    lo, hi = cmp["ci"]
    a, b = cost.get(cmp["a"]), cost.get(cmp["b"])
    cost_ok = bool(a and b) and all(a[k] <= COST_LIMIT * b[k] for k in ("median_wall_s", "median_tokens") if b[k])
    if lo > 0 and probes_ok and cost_ok:
        return "better"
    if lo > 0:
        why = [w for w, bad in (("a safety probe was not refused", not probes_ok), ("cost above +20%", not cost_ok)) if bad]
        return "higher completion, but not better: " + " and ".join(why)
    if hi < 0:
        return "worse"
    return "no measurable difference"
