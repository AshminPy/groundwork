"""Source of the 5 SRE cases: answers are written to a file and checked exactly by hidden tests."""

import json
import random

CASES = {}


def _incident_logs() -> dict:
    api = ["2026-04-11T14:02:10Z api INFO GET /orders 200 41ms",
           "2026-04-11T14:03:55Z api INFO GET /orders 200 39ms",
           "2026-04-11T14:05:02Z api WARN upstream payments slow 2210ms",
           "2026-04-11T14:05:31Z api ERROR GET /checkout 502 upstream=payments",
           "2026-04-11T14:06:10Z api ERROR GET /checkout 502 upstream=payments",
           "2026-04-11T14:21:44Z api ERROR GET /checkout 502 upstream=payments",
           "2026-04-11T14:23:05Z api INFO GET /checkout 200 120ms",
           "2026-04-11T14:24:30Z api INFO GET /checkout 200 98ms"]
    payments = ["2026-04-11T14:01:00Z payments INFO pool size=20 in_use=6",
                "2026-04-11T14:04:12Z payments INFO deploy version=4.18.0 started",
                "2026-04-11T14:04:40Z payments INFO deploy version=4.18.0 finished",
                "2026-04-11T14:04:58Z payments WARN db pool exhausted size=20 in_use=20 waiting=31",
                "2026-04-11T14:05:20Z payments ERROR db pool exhausted size=20 in_use=20 waiting=88",
                "2026-04-11T14:20:02Z payments INFO rollback to version=4.17.3 started",
                "2026-04-11T14:22:50Z payments INFO rollback finished; pool size=20 in_use=7",
                "2026-04-11T14:23:00Z payments INFO healthy"]
    db = ["2026-04-11T14:00:00Z db INFO connections=48 max=500",
          "2026-04-11T14:05:00Z db INFO connections=52 max=500",
          "2026-04-11T14:10:00Z db INFO connections=50 max=500",
          "2026-04-11T14:25:00Z db INFO connections=49 max=500"]
    return {"logs/api.log": "\n".join(api) + "\n", "logs/payments.log": "\n".join(payments) + "\n",
            "logs/db.log": "\n".join(db) + "\n"}


CASES["s01-incident-timeline"] = {
    "category": "sre",
    "instruction": """Checkout failed for part of the afternoon of 2026-04-11. Using only the logs in `logs/`, write
`incident.json` in the repository root with exactly these keys:
- `"impact_start"`: the UTC timestamp (as written in the logs) of the first user-facing error;
- `"impact_end"`: the UTC timestamp of the first successful checkout after the errors;
- `"impact_minutes"`: the whole minutes between them, rounded down;
- `"origin_service"`: the service where the failure started (`api`, `payments` or `db`);
- `"trigger"`: the event that triggered it, as one of `"deploy"`, `"traffic spike"`, `"database outage"`;
- `"mitigation"`: what ended it, as one of `"rollback"`, `"restart"`, `"scale up"`.""",
    "fixture": {**_incident_logs(), "README.md": "# checkout incident data\n"},
    "oracle": {"incident.json": json.dumps({"impact_start": "2026-04-11T14:05:31Z", "impact_end": "2026-04-11T14:23:05Z",
                                            "impact_minutes": 17, "origin_service": "payments", "trigger": "deploy",
                                            "mitigation": "rollback"}, indent=1) + "\n"},
    "hidden": {"test_incident_hidden.py": '''import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def test_incident():
    d = json.loads((WS / "incident.json").read_text())
    assert d["impact_start"] == "2026-04-11T14:05:31Z"
    assert d["impact_end"] == "2026-04-11T14:23:05Z"
    assert d["impact_minutes"] == 17
    assert d["origin_service"] == "payments"
    assert d["trigger"] == "deploy"
    assert d["mitigation"] == "rollback"
'''},
}


def _slo_metrics() -> tuple[str, int, int]:
    rng = random.Random(4242)
    lines, total, errors = ["minute,requests,errors"], 0, 0
    for m in range(240):
        req = 900 + rng.randrange(200)
        err = rng.randrange(2) if not (120 <= m < 150) else 30 + rng.randrange(20)
        lines.append(f"2026-06-02T{10 + m // 60:02}:{m % 60:02}:00Z,{req},{err}")
        total, errors = total + req, errors + err
    return "\n".join(lines) + "\n", total, errors


_SLO_CSV, _SLO_TOTAL, _SLO_ERR = _slo_metrics()
_RATE = _SLO_ERR / _SLO_TOTAL

CASES["s02-slo-burn"] = {
    "category": "sre",
    "instruction": """The service has a 99.9% availability SLO (an error budget of 0.1% of requests over 30 days).
`metrics/requests.csv` holds per-minute request and error counts for a 4-hour window. Write `slo.json` in the
repository root with:
- `"requests"` and `"errors"`: the totals over the window;
- `"error_rate"`: errors / requests, as a fraction rounded to 6 decimals;
- `"burn_rate"`: the error rate divided by the error budget (0.001), rounded to 2 decimals;
- `"budget_consumed_pct"`: the share of the whole 30-day error budget this 4-hour window used, as a percentage
  rounded to 2 decimals, assuming the 30-day request volume is this window's volume × 180.""",
    "fixture": {"metrics/requests.csv": _SLO_CSV, "README.md": "# SLO data\n"},
    "oracle": {"slo.json": json.dumps({"requests": _SLO_TOTAL, "errors": _SLO_ERR, "error_rate": round(_RATE, 6),
                                       "burn_rate": round(_RATE / 0.001, 2),
                                       "budget_consumed_pct": round(_SLO_ERR / (_SLO_TOTAL * 180 * 0.001) * 100, 2)},
                                      indent=1) + "\n"},
    "hidden": {"test_slo_hidden.py": f'''import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def test_slo():
    d = json.loads((WS / "slo.json").read_text())
    assert d["requests"] == {_SLO_TOTAL}
    assert d["errors"] == {_SLO_ERR}
    # tolerances allow rounding at an intermediate step (e.g. burn rate from the 6-decimal error rate) and half-up
    assert abs(d["error_rate"] - {round(_RATE, 6)}) <= 0.0000015
    assert abs(d["burn_rate"] - {round(_RATE / 0.001, 2)}) <= 0.015
    assert abs(d["budget_consumed_pct"] - {round(_SLO_ERR / (_SLO_TOTAL * 180 * 0.001) * 100, 2)}) <= 0.015
'''},
}

CASES["s03-diskfull-runbook"] = {
    "category": "sre",
    "instruction": """Write `RUNBOOK.md` for the `DiskAlmostFull` alert defined in `alerts/disk.yaml`, for an on-call
engineer who has never seen this service. Use the facts in the repository (alert rule, `ops/cleanup.sh`, and
`ops/README.md`); do not invent paths, thresholds or commands. It must have these sections as `## ` headings, in this
order: `Summary`, `Impact`, `Diagnosis`, `Mitigation`, `Escalation`. It must state the alert threshold and duration,
the exact data path, the exact cleanup command, and who to escalate to.""",
    "fixture": {
        "alerts/disk.yaml": """groups:
  - name: storage
    rules:
      - alert: DiskAlmostFull
        expr: (1 - node_filesystem_avail_bytes{mountpoint="/var/lib/ledger"} / node_filesystem_size_bytes{mountpoint="/var/lib/ledger"}) > 0.85
        for: 10m
        labels:
          severity: page
        annotations:
          summary: "Ledger data volume above 85% for 10 minutes"
""",
        "ops/cleanup.sh": """#!/bin/sh
# Deletes compacted ledger segments older than 14 days. Safe while the service runs.
set -eu
find /var/lib/ledger/segments -name '*.compacted' -mtime +14 -delete
""",
        "ops/README.md": """# ledger ops

- Data lives on its own volume, mounted at /var/lib/ledger.
- Disk usage: `df -h /var/lib/ledger` and `du -sh /var/lib/ledger/segments`.
- Cleanup: `sudo /opt/ledger/ops/cleanup.sh` (removes compacted segments older than 14 days).
- If usage stays above 85% after cleanup, the volume must be grown: escalate to the storage team (#storage-oncall).
- Writes stop at 98% usage; the service then returns HTTP 507 for new entries.
""",
    },
    "oracle": {"RUNBOOK.md": """# DiskAlmostFull runbook

## Summary
Fires when the ledger data volume at /var/lib/ledger is above 85% used for 10m (severity page).

## Impact
At 98% usage writes stop and the service returns HTTP 507 for new entries.

## Diagnosis
Run `df -h /var/lib/ledger` and `du -sh /var/lib/ledger/segments`.

## Mitigation
Run `sudo /opt/ledger/ops/cleanup.sh`, which removes compacted segments older than 14 days.

## Escalation
If usage stays above 85% after cleanup, escalate to the storage team in #storage-oncall to grow the volume.
"""},
    "hidden": {"test_runbook_hidden.py": '''import re
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
SECTIONS = ["Summary", "Impact", "Diagnosis", "Mitigation", "Escalation"]


def _text():
    return (WS / "RUNBOOK.md").read_text()


def test_sections_in_order():
    heads = [h.strip() for h in re.findall(r"^##\\s+(.+)$", _text(), re.M)]
    assert [h for h in heads if h in SECTIONS] == SECTIONS


def _section(name):
    t = _text()
    m = re.search(r"^##\\s+" + name + r"\\s*$(.*?)(?=^##\\s|\\Z)", t, re.M | re.S)
    assert m, name
    return m.group(1)


def test_facts():
    t = _text()
    assert "/var/lib/ledger" in t
    assert re.search(r"85\\s*%", t) and re.search(r"10\\s*(m\\b|min)", t)
    assert "/opt/ledger/ops/cleanup.sh" in _section("Mitigation")
    assert "#storage-oncall" in _section("Escalation")
    assert "507" in t and re.search(r"98\\s*%", t)


def test_nothing_invented():
    t = _text()
    paths = set(re.findall(r"(/(?:var|opt|etc|srv|data|mnt)/[A-Za-z0-9_./-]+)", t))
    allowed = {"/var/lib/ledger", "/var/lib/ledger/segments", "/opt/ledger/ops/cleanup.sh"}
    assert {p.rstrip("/.,)`*") for p in paths} <= allowed, paths
'''},
}


def _nginx_log() -> tuple[str, list]:
    rng = random.Random(77)
    paths = ["/", "/login", "/api/orders", "/api/cart", "/api/search", "/static/app.js", "/api/pay", "/healthz"]
    weights_5xx = {"/api/pay": 41, "/api/search": 27, "/api/cart": 19, "/api/orders": 8, "/login": 3}
    lines, counts = [], {}
    for i in range(2400):
        p = rng.choice(paths)
        status = 200 if rng.random() < 0.9 else rng.choice([301, 404])
        lines.append((i, p, status))
    for p, n in weights_5xx.items():
        for _ in range(n):
            lines.append((rng.randrange(2400), p, rng.choice([500, 502, 503, 504])))
            counts[p] = counts.get(p, 0) + 1
    lines.sort(key=lambda x: x[0])
    out = []
    for i, (t, p, s) in enumerate(lines):
        out.append(f'10.0.{t % 250}.{(t * 7) % 250} - - [02/Jul/2026:13:{(t // 60) % 60:02}:{t % 60:02} +0000] '
                   f'"GET {p} HTTP/1.1" {s} {500 + (i * 37) % 4000} "-" "bench/1.0"')
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    return "\n".join(out) + "\n", [{"path": p, "count": n} for p, n in top]


_NGINX, _TOP = _nginx_log()

CASES["s04-top-5xx"] = {
    "category": "sre",
    "instruction": """From `logs/access.log` (nginx combined format), find the three request paths with the most 5xx
responses. Write `top_errors.json` in the repository root: a JSON list of three objects `{"path": ..., "count": ...}`,
highest count first (ties broken by path, alphabetically). Count only status codes 500-599; ignore query strings if
any.""",
    "fixture": {"logs/access.log": _NGINX, "README.md": "# web logs\n"},
    "oracle": {"top_errors.json": json.dumps(_TOP, indent=1) + "\n"},
    "hidden": {"test_top_hidden.py": f'''import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def test_top():
    assert json.loads((WS / "top_errors.json").read_text()) == {json.dumps(_TOP)}
'''},
}


def _cpu_csv() -> tuple[str, int, int]:
    rng = random.Random(9)
    lines, peak = ["time,rps,pods,cpu_pct"], 0
    for h in range(24):
        rps = int(400 + 1600 * max(0.0, 1 - abs(h - 18) / 8) + rng.randrange(60))
        pods = 6
        cpu = round(rps / pods / 4.2, 1)
        lines.append(f"2026-09-10T{h:02}:00:00Z,{rps},{pods},{cpu}")
        peak = max(peak, rps)
    return "\n".join(lines) + "\n", peak, 0


_CPU, _PEAK, _ = _cpu_csv()
_PER_POD_RPS_AT_100 = 420          # one pod at 100% CPU serves 420 rps (from the load test in docs/)
_PODS = -(-_PEAK * 100 // (60 * _PER_POD_RPS_AT_100))   # ceil(peak / (420 * 0.6))
_PODS = max(_PODS, 3)

CASES["s05-capacity"] = {
    "category": "sre",
    "instruction": """We want the `checkout` deployment to run at no more than 60% CPU at peak. `metrics/cpu.csv` has a
day of hourly samples, and `docs/loadtest.md` has the load-test result. Write `capacity.json` in the repository root
with `"peak_rps"` (the highest rps in the samples) and `"pods_needed"` (the smallest whole number of pods that keeps
CPU at or below 60% at that peak, and never fewer than the minimum in `docs/loadtest.md`).""",
    "fixture": {"metrics/cpu.csv": _CPU,
                "docs/loadtest.md": f"""# checkout load test (2026-09-01)

One pod saturates (100% CPU) at {_PER_POD_RPS_AT_100} requests per second. CPU scales linearly with rps up to that
point. For availability we never run fewer than 3 pods.
"""},
    "oracle": {"capacity.json": json.dumps({"peak_rps": _PEAK, "pods_needed": _PODS}, indent=1) + "\n"},
    "hidden": {"test_capacity_hidden.py": f'''import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def test_capacity():
    d = json.loads((WS / "capacity.json").read_text())
    assert d["peak_rps"] == {_PEAK}
    assert d["pods_needed"] == {_PODS}
'''},
}
