#!/usr/bin/env python3
"""groundwork-report — deterministic Groundwork health dashboard from local telemetry.

    events.jsonl  →  this generator (aggregate, compute)  →  dashboard.html (+ dated snapshots, .md)

No server, no LLM, no network, stdlib only. The browser never parses the raw telemetry file: the
generator aggregates it into small day-level buckets (bounded), embeds those, and the page's
JavaScript recomputes every metric client-side when a filter changes. The same computation is
implemented once in Python (for the Markdown snapshot and tests) and once in JS (for filters);
tests assert the two agree.

Commands
  generate  [--window DAYS] [--snapshot] [--events PATH] [--out DIR] [--now YYYY-MM-DD]
  schedule  disabled|daily|weekly|monthly|yearly  [--hour H]      (macOS launchd, no Claude needed)
  status

Config: <config dir>/groundwork/report.json  {"schedule": "weekly", "window_days": 30, "hour": 8}
Config dir = $CLAUDE_CONFIG_DIR or ~/.claude. Reports: <config dir>/groundwork/reports/.

Failure isolation: this is a separate process run by launchd or by hand; it never runs inside a
hook, so nothing here can affect task execution or telemetry collection.
"""
import argparse
import datetime as dt
import html
import json
import os
import plistlib
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1"
MAX_BYTES = 64 * 1024 * 1024       # never read more than the last 64 MB of telemetry
MAX_BUCKETS = 4000                 # above this, days collapse into ISO weeks
MIN_TREND_N = 5                    # both periods need at least this many known outcomes
OUTCOMES = ("complete", "partial", "blocked", "failed", "unknown")
VALIDATIONS = ("verified", "partial", "not_verified", "unknown")
EXEC_MODES = ("single_agent", "subagents", "agent_team", "unknown")
FREQS = ("disabled", "daily", "weekly", "monthly", "yearly")
LABEL = "com.groundwork.report"


# ---------------------------------------------------------------- paths / config
def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))


def events_path() -> Path:
    return Path(os.path.expanduser(os.environ.get("GROUNDWORK_TELEMETRY_PATH") or str(config_dir() / "groundwork" / "telemetry" / "events.jsonl")))


def reports_dir() -> Path:
    return config_dir() / "groundwork" / "reports"


def config_path() -> Path:
    return config_dir() / "groundwork" / "report.json"


DEFAULT_CONFIG = {"schedule": "weekly", "window_days": 30, "hour": 8}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        data = json.loads(config_path().read_text())
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    except Exception:
        pass
    if cfg["schedule"] not in FREQS:
        cfg["schedule"] = "weekly"
    try:
        cfg["window_days"] = max(1, int(cfg["window_days"]))
        cfg["hour"] = min(23, max(0, int(cfg["hour"])))
    except Exception:
        cfg["window_days"], cfg["hour"] = 30, 8
    return cfg


def save_config(cfg: dict) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    config_path().write_text(json.dumps(cfg, indent=2) + "\n")


# ---------------------------------------------------------------- load + normalise
def _label(v, default="unknown") -> str:
    v = str(v or "").strip().lower()
    return v[:32] if v and v.replace("_", "").replace("-", "").replace(":", "").replace(" ", "").replace(".", "").isalnum() else default


def normalise(raw: dict):
    """One telemetry line (schema 1 flat or schema 2) → a small flat record, or None."""
    if not isinstance(raw, dict):
        return None
    ts = str(raw.get("ts") or "")
    if len(ts) < 10 or not ts[:4].isdigit():
        return None
    try:
        day = dt.date.fromisoformat(ts[:10])
    except ValueError:
        return None
    if raw.get("schema") == 2:
        ob = raw.get("observed") if isinstance(raw.get("observed"), dict) else {}
        de = raw.get("declared") if isinstance(raw.get("declared"), dict) else {}
        block = bool(de.get("block_present", True))
    else:  # schema 1: flat, always had a block
        ob = de = raw
        block = True
    outcome = _label(de.get("outcome"))
    validation = _label(de.get("validation"))
    ex = _label(de.get("execution_mode"))
    return {
        "day": day.isoformat(),
        "profile": _label(ob.get("profile")),
        "playbook": _label(de.get("playbook")).upper()[:16],
        "version": _label(raw.get("harness_version")),
        "environment": _label(de.get("environment")),
        "exec": ex if ex in EXEC_MODES else "unknown",
        "outcome": outcome if outcome in OUTCOMES else "unknown",
        "validation": validation if validation in VALIDATIONS else "unknown",
        "block": block,
        "evidence": bool(de.get("evidence_sources")) if isinstance(de.get("evidence_sources"), list) else False,
        "tests": bool(ob.get("tests_run")),
        "impl": bool(ob.get("implementation_performed")),
        "deploy": bool(ob.get("deployment_performed")),
        "clarify": bool(de.get("clarification_required")),
        "tools": [str(t)[:40] for t in (ob.get("tools") or []) if isinstance(t, str)][:40],
        "mcp": [str(t)[:40] for t in (ob.get("mcp_servers") or []) if isinstance(t, str)][:20],
    }


def load_events(path: Path):
    """Bounded, tolerant read: malformed lines are counted and skipped."""
    records, stats = [], {"lines": 0, "malformed": 0, "bytes_skipped": 0}
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > MAX_BYTES:
                f.seek(size - MAX_BYTES)
                f.readline()  # drop the partial line
                stats["bytes_skipped"] = size - MAX_BYTES
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                stats["lines"] += 1
                try:
                    rec = normalise(json.loads(raw))
                except Exception:
                    rec = None
                if rec is None:
                    stats["malformed"] += 1
                else:
                    records.append(rec)
    except FileNotFoundError:
        pass
    return records, stats


# ---------------------------------------------------------------- aggregate
def aggregate(records: list):
    """Day-level buckets keyed by the filterable dimensions; counters only, no identifiers."""
    def build(day_of):
        acc = {}
        for r in records:
            k = (day_of(r["day"]), r["profile"], r["playbook"], r["version"], r["environment"], r["exec"])
            b = acc.get(k)
            if b is None:
                b = acc[k] = {"n": 0, "outcome": Counter(), "validation": Counter(), "block": 0, "evidence": 0,
                              "tests": 0, "impl": 0, "deploy": 0, "clarify": 0, "corroborated": 0,
                              "impl_unverified": 0, "tools": Counter(), "mcp": Counter()}
            b["n"] += 1
            b["outcome"][r["outcome"]] += 1
            b["validation"][r["validation"]] += 1
            b["block"] += r["block"]
            b["evidence"] += r["evidence"]
            b["tests"] += r["tests"]
            b["impl"] += r["impl"]
            b["deploy"] += r["deploy"]
            b["clarify"] += r["clarify"]
            b["corroborated"] += 1 if (r["outcome"] == "complete" and (r["tests"] or r["deploy"])) else 0
            b["impl_unverified"] += 1 if (r["impl"] and r["validation"] != "verified") else 0
            for t in r["tools"]:
                b["tools"][t] += 1
            for t in r["mcp"]:
                b["mcp"][t] += 1
        return acc

    acc = build(lambda d: d)
    granularity = "day"
    if len(acc) > MAX_BUCKETS:
        acc = build(lambda d: (dt.date.fromisoformat(d) - dt.timedelta(days=dt.date.fromisoformat(d).weekday())).isoformat())
        granularity = "week"
    out = []
    for (day, profile, playbook, version, env, ex), b in sorted(acc.items()):
        out.append({"day": day, "profile": profile, "playbook": playbook, "version": version, "environment": env, "exec": ex,
                    "n": b["n"], "outcome": dict(b["outcome"]), "validation": dict(b["validation"]), "block": b["block"],
                    "evidence": b["evidence"], "tests": b["tests"], "impl": b["impl"], "deploy": b["deploy"],
                    "clarify": b["clarify"], "corroborated": b["corroborated"], "impl_unverified": b["impl_unverified"],
                    "tools": dict(b["tools"].most_common(40)), "mcp": dict(b["mcp"].most_common(20))})
    return out, granularity


# ---------------------------------------------------------------- compute (Python twin of the JS)
def pct0(rate: float) -> int:
    """Whole percent, round half up — identical to the JS pct0 so both renderers print the same digits."""
    return int(rate + 0.5)


def _rate(num: int, den: int):
    # one decimal, round half up — the same rule as the JS rate(), so the two twins never differ
    return None if den <= 0 else {"rate": int(1000.0 * num / den + 0.5) / 10.0, "num": num, "den": den}


def _in(b: dict, f: dict) -> bool:
    for k in ("profile", "playbook", "version", "environment"):
        v = f.get(k, "all")
        if v != "all" and b[k] != v:
            return False
    return True


def _summarise(buckets: list) -> dict:
    n = sum(b["n"] for b in buckets)
    oc = Counter()
    vc = Counter()
    for b in buckets:
        oc.update(b["outcome"])
        vc.update(b["validation"])
    known = sum(oc[o] for o in OUTCOMES if o != "unknown")
    vknown = sum(vc[v] for v in VALIDATIONS if v != "unknown")
    block = sum(b["block"] for b in buckets)
    return {
        "total": n,
        "completion": _rate(oc["complete"], known),
        "gap": _rate(oc["partial"] + oc["blocked"] + oc["failed"], known),
        "verified_outcome": _rate(sum(b["corroborated"] for b in buckets), oc["complete"]),
        "validation": _rate(vc["verified"], vknown),
        "evidence": _rate(sum(b["evidence"] for b in buckets), block),
        "compliance": _rate(block, n),
        "outcomes": {o: oc[o] for o in OUTCOMES},
        "validations": {v: vc[v] for v in VALIDATIONS},
        "impl_unverified": sum(b["impl_unverified"] for b in buckets),
        "clarify": sum(b["clarify"] for b in buckets),
        "known": known,
    }


def compute(buckets: list, window_days, ref: dt.date, filters=None) -> dict:
    """window_days: int or None (all data). Current period = (ref - window, ref]; previous = the
    equivalent period before it. Everything is derived from bucket counters only."""
    f = filters or {}
    sel = [b for b in buckets if _in(b, f)]
    if window_days:
        start = ref - dt.timedelta(days=window_days)
        prev_start = start - dt.timedelta(days=window_days)
        cur = [b for b in sel if start < dt.date.fromisoformat(b["day"]) <= ref]
        prev = [b for b in sel if prev_start < dt.date.fromisoformat(b["day"]) <= start]
    else:
        cur, prev = sel, []
    s = _summarise(cur)
    p = _summarise(prev) if prev else None
    trends = {}
    for m in ("completion", "gap", "verified_outcome", "validation", "evidence", "compliance"):
        a, b = s.get(m), (p or {}).get(m)
        if a and b and a["den"] >= MIN_TREND_N and b["den"] >= MIN_TREND_N:
            trends[m] = round(a["rate"] - b["rate"], 1)
    by_playbook = {}
    for pb in sorted({b["playbook"] for b in cur}):
        by_playbook[pb] = _summarise([b for b in cur if b["playbook"] == pb])
    exec_modes = Counter()
    versions = Counter()
    tools = Counter()
    mcp = Counter()
    for b in cur:
        exec_modes[b["exec"]] += b["n"]
        versions[b["version"]] += b["n"]
        tools.update(b["tools"])
        mcp.update(b["mcp"])
    weeks = defaultdict(list)
    for b in cur:
        d = dt.date.fromisoformat(b["day"])
        weeks[(d - dt.timedelta(days=d.weekday())).isoformat()].append(b)
    series = []
    for wk in sorted(weeks):
        ws = _summarise(weeks[wk])
        series.append({"week": wk, "n": ws["total"], "completion": ws["completion"], "gap": ws["gap"],
                       "validation": ws["validation"], "evidence": ws["evidence"]})
    top = lambda c, k: dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:k])
    return {"summary": s, "previous": p, "trends": trends, "by_playbook": by_playbook,
            "exec_modes": dict(exec_modes), "versions": dict(versions), "tools": top(tools, 12),
            "mcp": top(mcp, 12), "series": series, "gaps": gap_findings(s, by_playbook),
            "rework": None, "accuracy": None}  # not collected by telemetry → insufficient data


def gap_findings(s: dict, by_playbook: dict) -> list:
    """Deterministic attention items — sentences built only from counts."""
    out = []
    if s["total"] == 0:
        return ["No tasks recorded in this period."]
    worst = None
    for pb, v in by_playbook.items():
        g = v["gap"]
        if g and g["den"] >= 3 and (worst is None or g["rate"] > worst[1]["rate"]):
            worst = (pb, g)
    if worst and worst[1]["rate"] > 0:
        pb, g = worst
        out.append(f"{pb} has the highest gap rate: {pct0(g['rate'])}% ({g['num']}/{g['den']} known outcomes not complete).")
    if s["compliance"] and s["compliance"]["rate"] < 100:
        out.append(f"Metadata compliance is {pct0(s['compliance']['rate'])}% ({s['compliance']['den'] - s['compliance']['num']} of {s['compliance']['den']} tool-using tasks had no Harness metadata block).")
    if s["impl_unverified"]:
        out.append(f"{s['impl_unverified']} task(s) that changed files did not declare verified validation.")
    unk = s["outcomes"]["unknown"]
    if unk:
        out.append(f"{unk} task(s) had no recognisable outcome (status sentence missing or ambiguous).")
    if s["outcomes"]["blocked"]:
        out.append(f"{s['outcomes']['blocked']} task(s) ended blocked; {s['clarify']} asked a clarifying question.")
    if s["outcomes"]["failed"]:
        out.append(f"{s['outcomes']['failed']} task(s) ended failed.")
    if s["verified_outcome"] and s["verified_outcome"]["rate"] < 100:
        out.append(f"{s['verified_outcome']['den'] - s['verified_outcome']['num']} of {s['verified_outcome']['den']} completed tasks had no observed test or deploy run backing the outcome.")
    return out or ["No gaps detected in this period."]


# ---------------------------------------------------------------- render: markdown
def fmt(r) -> str:
    return f"{pct0(r['rate'])}% ({r['num']}/{r['den']})" if r else "N/A (insufficient data)"


def fmt_trend(v) -> str:
    return "" if v is None else f" {'↑' if v > 0 else '↓' if v < 0 else '→'}{pct0(abs(v))}%"


def render_markdown(m: dict, meta: dict) -> str:
    s, t = m["summary"], m["trends"]
    lines = [f"# Groundwork health — {meta['generated']}", "",
             f"Window: last {meta['window_days']} days (to {meta['ref']}) · filters: none · source: {meta['events']} ({meta['stats']['lines']} lines, {meta['stats']['malformed']} skipped)", "",
             "## Summary", "",
             f"- Total tasks: {s['total']}",
             f"- Completion: {fmt(s['completion'])}{fmt_trend(t.get('completion'))}",
             f"- Verified outcome (complete + observed test/deploy): {fmt(s['verified_outcome'])}{fmt_trend(t.get('verified_outcome'))}",
             f"- Gap rate: {fmt(s['gap'])}{fmt_trend(t.get('gap'))}",
             f"- Validation pass: {fmt(s['validation'])}{fmt_trend(t.get('validation'))}",
             f"- Evidence coverage: {fmt(s['evidence'])}{fmt_trend(t.get('evidence'))}",
             f"- Metadata compliance: {fmt(s['compliance'])}{fmt_trend(t.get('compliance'))}",
             "- Rework rate: N/A (not collected)",
             "- Verified accuracy: Insufficient data (no objective ground truth collected)", "",
             "## Gaps / attention", ""] + [f"- {g}" for g in m["gaps"]] + ["", "## By playbook", "", "| Playbook | Tasks | Completion | Gap | Validation |", "|---|---|---|---|---|"]
    for pb, v in m["by_playbook"].items():
        lines.append(f"| {pb} | {v['total']} | {fmt(v['completion'])} | {fmt(v['gap'])} | {fmt(v['validation'])} |")
    lines += ["", "## Execution modes", ""] + [f"- {k}: {v}" for k, v in sorted(m["exec_modes"].items())]
    lines += ["", "## Harness versions", ""] + [f"- {k}: {v}" for k, v in sorted(m["versions"].items())]
    lines += ["", "## Tools (top)", ""] + [f"- {k}: {v}" for k, v in m["tools"].items()]
    lines += ["", "_Declared fields (outcome, validation, evidence, playbook) are what the model stated; observed fields (tools, files, tests, deploys, profile) were determined by the hook. No prompts, responses, code or secrets are stored._", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- render: html
CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--muted:#66717f;--line:#e3e7ec;--ok:#2f8f5b;--bad:#c9463d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
header{background:var(--card);border-bottom:1px solid var(--line);padding:14px 22px;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
header h1{font-size:17px;margin:0 14px 0 0;font-weight:650}header .meta{color:var(--muted);font-size:12px;margin-left:auto}
label.f{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}select{font:inherit;font-size:13px;padding:4px 6px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink)}
main{padding:18px 22px;max-width:1280px;margin:0 auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card .k{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}.card .v{font-size:24px;font-weight:650;margin:4px 0 2px}
.card .s{font-size:11.5px;color:var(--muted)}.card .t{font-size:12px;font-weight:600;margin-left:6px}.up{color:var(--ok)}.down{color:var(--bad)}.flat{color:var(--muted)}.na .v{color:var(--muted);font-size:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px;margin-bottom:18px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-height:120px}.panel h2{font-size:13.5px;margin:0 0 8px;font-weight:650}
.panel.wide{grid-column:1/-1}svg{width:100%;height:auto;display:block}.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--muted);margin-top:6px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.empty{color:var(--muted);font-size:13px;padding:20px 0;text-align:center}
ul.gaps{margin:0;padding-left:18px}ul.gaps li{margin:4px 0}
footer{color:var(--muted);font-size:12px;padding:8px 22px 26px;max-width:1280px;margin:0 auto}footer p{margin:4px 0}
@media (max-width:600px){header{padding:12px}main{padding:12px}.card .v{font-size:20px}}
"""

# The JS twin of compute(): same inputs (buckets, window, ref, filters), same numbers.
JS = r"""
const OUTCOMES=["complete","partial","blocked","failed","unknown"],VALS=["verified","partial","not_verified","unknown"],MIN_TREND_N=5;
function rate(n,d){return d>0?{rate:Math.round(1000*n/d)/10,num:n,den:d}:null}
function pct0(r){return Math.floor(r+0.5)}
function count(bs,key){const c={};for(const b of bs)for(const k in b[key])c[k]=(c[k]||0)+b[key][k];return c}
function sum(bs,k){let s=0;for(const b of bs)s+=b[k];return s}
function summarise(bs){const n=sum(bs,"n"),oc=count(bs,"outcome"),vc=count(bs,"validation");const g=k=>oc[k]||0,v=k=>vc[k]||0;
 const known=g("complete")+g("partial")+g("blocked")+g("failed"),vknown=v("verified")+v("partial")+v("not_verified"),block=sum(bs,"block");
 return{total:n,completion:rate(g("complete"),known),gap:rate(g("partial")+g("blocked")+g("failed"),known),verified_outcome:rate(sum(bs,"corroborated"),g("complete")),
 validation:rate(v("verified"),vknown),evidence:rate(sum(bs,"evidence"),block),compliance:rate(block,n),outcomes:Object.fromEntries(OUTCOMES.map(o=>[o,g(o)])),
 validations:Object.fromEntries(VALS.map(x=>[x,v(x)])),impl_unverified:sum(bs,"impl_unverified"),clarify:sum(bs,"clarify"),known}}
function dstr(d){return d.toISOString().slice(0,10)}
function addDays(d,n){const x=new Date(d.getTime());x.setUTCDate(x.getUTCDate()+n);return x}
function weekStart(s){const d=new Date(s+"T00:00:00Z");return dstr(addDays(d,-((d.getUTCDay()+6)%7)))}
function gapFindings(s,byPb){const out=[];if(s.total===0)return["No tasks recorded in this period."];
 let worst=null;for(const pb in byPb){const g=byPb[pb].gap;if(g&&g.den>=3&&(!worst||g.rate>worst[1].rate))worst=[pb,g]}
 if(worst&&worst[1].rate>0)out.push(`${worst[0]} has the highest gap rate: ${pct0(worst[1].rate)}% (${worst[1].num}/${worst[1].den} known outcomes not complete).`);
 if(s.compliance&&s.compliance.rate<100)out.push(`Metadata compliance is ${pct0(s.compliance.rate)}% (${s.compliance.den-s.compliance.num} of ${s.compliance.den} tool-using tasks had no Harness metadata block).`);
 if(s.impl_unverified)out.push(`${s.impl_unverified} task(s) that changed files did not declare verified validation.`);
 if(s.outcomes.unknown)out.push(`${s.outcomes.unknown} task(s) had no recognisable outcome (status sentence missing or ambiguous).`);
 if(s.outcomes.blocked)out.push(`${s.outcomes.blocked} task(s) ended blocked; ${s.clarify} asked a clarifying question.`);
 if(s.outcomes.failed)out.push(`${s.outcomes.failed} task(s) ended failed.`);
 if(s.verified_outcome&&s.verified_outcome.rate<100)out.push(`${s.verified_outcome.den-s.verified_outcome.num} of ${s.verified_outcome.den} completed tasks had no observed test or deploy run backing the outcome.`);
 return out.length?out:["No gaps detected in this period."]}
function computeMetrics(buckets,windowDays,refStr,filters){const f=filters||{};const ref=new Date(refStr+"T00:00:00Z");
 const sel=buckets.filter(b=>["profile","playbook","version","environment"].every(k=>!f[k]||f[k]==="all"||b[k]===f[k]));
 let cur=sel,prev=[];if(windowDays){const start=dstr(addDays(ref,-windowDays)),pstart=dstr(addDays(ref,-2*windowDays));cur=sel.filter(b=>b.day>start&&b.day<=refStr);prev=sel.filter(b=>b.day>pstart&&b.day<=start)}
 const s=summarise(cur),p=prev.length?summarise(prev):null,trends={};
 for(const m of["completion","gap","verified_outcome","validation","evidence","compliance"]){const a=s[m],b=p&&p[m];if(a&&b&&a.den>=MIN_TREND_N&&b.den>=MIN_TREND_N)trends[m]=Math.round(10*(a.rate-b.rate))/10}
 const byPb={};for(const pb of[...new Set(cur.map(b=>b.playbook))].sort())byPb[pb]=summarise(cur.filter(b=>b.playbook===pb));
 const ex={},ver={},tools={},mcp={};for(const b of cur){ex[b.exec]=(ex[b.exec]||0)+b.n;ver[b.version]=(ver[b.version]||0)+b.n;for(const t in b.tools)tools[t]=(tools[t]||0)+b.tools[t];for(const t in b.mcp)mcp[t]=(mcp[t]||0)+b.mcp[t]}
 const top=(o,k)=>Object.fromEntries(Object.entries(o).sort((a,b)=>b[1]-a[1]||(a[0]<b[0]?-1:1)).slice(0,k));
 const weeks={};for(const b of cur){const w=weekStart(b.day);(weeks[w]=weeks[w]||[]).push(b)}
 const series=Object.keys(weeks).sort().map(w=>{const ws=summarise(weeks[w]);return{week:w,n:ws.total,completion:ws.completion,gap:ws.gap,validation:ws.validation,evidence:ws.evidence}});
 return{summary:s,previous:p,trends,by_playbook:byPb,exec_modes:ex,versions:ver,tools:top(tools,12),mcp:top(mcp,12),series,gaps:gapFindings(s,byPb),rework:null,accuracy:null}}
if(typeof module!=="undefined")module.exports={computeMetrics};
"""

JS_UI = r"""
const D=JSON.parse(document.getElementById("gw-data").textContent);
const $=s=>document.querySelector(s),esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const C={completion:"#2b6cb0",gap:"#c9463d",validation:"#2f8f5b",evidence:"#7c5cbf"};
function pct(r){return r?`${pct0(r.rate)}%`:"N/A"}
function card(k,r,t,sub,raw){const na=!r&&raw==null;const tr=t==null?"":`<span class="t ${t>0?"up":t<0?"down":"flat"}">${t>0?"↑":t<0?"↓":"→"}${pct0(Math.abs(t))}%</span>`;
 return`<div class="card${na?" na":""}"><div class="k">${esc(k)}</div><div class="v">${raw!=null?esc(raw):na?"N/A":pct(r)}${tr}</div><div class="s">${esc(sub||(r?`${r.num}/${r.den}`:"insufficient data"))}</div></div>`}
function bars(obj,color,fmtv){const es=Object.entries(obj);if(!es.length)return'<div class="empty">No data</div>';const val=v=>v!=null&&v.v!=null?v.v:+v;const max=Math.max(...es.map(e=>val(e[1])),1),h=22,w=520;
 let s=`<svg viewBox="0 0 ${w} ${es.length*h+4}" role="img">`;es.forEach(([k,v],i)=>{const x=val(v),y=i*h+2,bw=Math.max(2,(w-190)*x/max);
 s+=`<text x="0" y="${y+15}" font-size="12" fill="#66717f">${esc(k.length>22?k.slice(0,21)+"…":k)}</text><rect x="150" y="${y+4}" width="${bw.toFixed(1)}" height="${h-8}" rx="3" fill="${(v&&v.c)||color}"/><text x="${(154+bw).toFixed(1)}" y="${y+15}" font-size="12" fill="#1c2430">${esc(fmtv?fmtv(v):x)}</text>`});return s+"</svg>"}
function donut(obj,colors){const es=Object.entries(obj).filter(e=>e[1]>0),tot=es.reduce((a,e)=>a+e[1],0);if(!tot)return'<div class="empty">No data</div>';let a=-Math.PI/2,s=`<svg viewBox="0 0 320 130"><g transform="translate(65,65)">`;
 es.forEach(([k,v],i)=>{const t=a+2*Math.PI*v/tot,x1=55*Math.cos(a),y1=55*Math.sin(a),x2=55*Math.cos(t),y2=55*Math.sin(t),lg=t-a>Math.PI?1:0;
 s+=es.length===1?`<circle r="55" fill="${colors[i%colors.length]}"/>`:`<path d="M${x1.toFixed(2)},${y1.toFixed(2)} A55,55 0 ${lg},1 ${x2.toFixed(2)},${y2.toFixed(2)} L0,0Z" fill="${colors[i%colors.length]}"/>`;a=t});
 s+=`<circle r="34" fill="#fff"/><text text-anchor="middle" y="5" font-size="16" font-weight="600" fill="#1c2430">${tot}</text></g>`;
 es.forEach(([k,v],i)=>{s+=`<rect x="140" y="${18+i*22}" width="10" height="10" rx="2" fill="${colors[i%colors.length]}"/><text x="156" y="${28+i*22}" font-size="12" fill="#1c2430">${esc(k)} · ${v} (${Math.round(100*v/tot)}%)</text>`});return s+"</svg>"}
function lines(series){const pts=series.filter(p=>p.n>0);if(pts.length<2)return'<div class="empty">Not enough weeks in this period for a trend (need 2+)</div>';const w=860,h=200,l=40,r=10,t=10,b=28,iw=w-l-r,ih=h-t-b;
 let s=`<svg viewBox="0 0 ${w} ${h}">`;for(let g=0;g<=4;g++){const y=t+ih*g/4;s+=`<line x1="${l}" x2="${w-r}" y1="${y}" y2="${y}" stroke="#e3e7ec"/><text x="${l-6}" y="${y+4}" font-size="11" text-anchor="end" fill="#66717f">${100-25*g}%</text>`}
 const x=i=>l+iw*(i/(pts.length-1));const step=Math.ceil(pts.length/8);pts.forEach((p,i)=>{if(i%step===0||i===pts.length-1)s+=`<text x="${x(i).toFixed(1)}" y="${h-8}" font-size="11" text-anchor="middle" fill="#66717f">${p.week.slice(5)}</text>`});
 for(const m of["completion","gap","validation","evidence"]){let d="",on=false;pts.forEach((p,i)=>{const v=p[m];if(!v){on=false;return}const y=t+ih*(1-v.rate/100);d+=(on?"L":"M")+x(i).toFixed(1)+","+y.toFixed(1);on=true;s+=`<circle cx="${x(i).toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${C[m]}"><title>${p.week} ${m}: ${v.rate}% (${v.num}/${v.den})</title></circle>`});s+=`<path d="${d}" fill="none" stroke="${C[m]}" stroke-width="2"/>`}
 return s+"</svg>"}
function render(){const win=$("#win").value,f={profile:$("#profile").value,playbook:$("#playbook").value,version:$("#version").value,environment:$("#environment").value};
 const m=computeMetrics(D.buckets,win==="all"?null:+win,D.ref,f),s=m.summary,t=m.trends;
 $("#cards").innerHTML=[card("Total tasks",null,null,`${s.known} with a known outcome`,String(s.total)),card("Completion",s.completion,t.completion),card("Verified outcome",s.verified_outcome,t.verified_outcome,s.verified_outcome?`${s.verified_outcome.num}/${s.verified_outcome.den} completed, test or deploy observed`:null),
  card("Gap rate",s.gap,t.gap),card("Validation pass",s.validation,t.validation),card("Evidence coverage",s.evidence,t.evidence),card("Metadata compliance",s.compliance,t.compliance),
  card("Rework rate",null,null,"not collected"),card("Verified accuracy",null,null,"insufficient data — no ground truth")].join("");
 $("#trend").innerHTML=lines(m.series);
 const pbs={};for(const pb in m.by_playbook)pbs[pb]=m.by_playbook[pb].total;$("#playbooks").innerHTML=bars(pbs,"#2b6cb0");
 const gp={};for(const pb in m.by_playbook){const g=m.by_playbook[pb].gap;if(g)gp[pb]={v:g.rate,c:g.rate>=50?"#c9463d":g.rate>0?"#c98a1b":"#2f8f5b",num:g.num,den:g.den}}$("#gaps-pb").innerHTML=Object.keys(gp).length?bars(gp,"#c98a1b",v=>`${pct0(v.v)}% (${v.num}/${v.den})`):'<div class="empty">No known outcomes yet</div>';
 $("#exec").innerHTML=bars(m.exec_modes,"#7c5cbf");$("#tools").innerHTML=bars(Object.assign({},m.tools,Object.fromEntries(Object.entries(m.mcp).map(([k,v])=>["mcp:"+k,v]))),"#2f8f5b");
 $("#versions").innerHTML=bars(m.versions,"#2b6cb0");$("#validation").innerHTML=donut(s.validations,["#2f8f5b","#c98a1b","#c9463d","#9aa4b1"]);
 $("#gaps").innerHTML=m.gaps.map(g=>`<li>${esc(g)}</li>`).join("");
 const pn=m.previous?`previous ${win==="all"?"":win+"-day "}period: ${m.previous.total} tasks`:"no previous period";$("#period").textContent=`${s.total} tasks in period · ${pn} · trends shown only when both periods have ≥${MIN_TREND_N} known outcomes`}
function fill(id,vals){const el=$(id);for(const v of vals){const o=document.createElement("option");o.value=v;o.textContent=v;el.appendChild(o)}}
fill("#profile",D.dims.profile);fill("#playbook",D.dims.playbook);fill("#version",D.dims.version);fill("#environment",D.dims.environment);$("#win").value=String(D.window_days);
for(const id of["#win","#profile","#playbook","#version","#environment"])$(id).addEventListener("change",render);render();
"""


def render_html(buckets: list, meta: dict) -> str:
    dims = {k: sorted({b[k] for b in buckets}) for k in ("profile", "playbook", "version", "environment")}
    data = {"buckets": buckets, "dims": dims, "ref": meta["ref"], "window_days": meta["window_days"], "granularity": meta["granularity"]}
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    sel = lambda i, label: f'<label class="f">{label} <select id="{i}"><option value="all">all</option></select></label>'
    win_opts = "".join(f'<option value="{v}">{l}</option>' for v, l in ((7, "7 days"), (30, "30 days"), (90, "90 days"), (365, "year"), ("all", "all data")))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Groundwork health</title>
<style>{CSS}</style></head>
<body>
<header><h1>Groundwork health</h1>
<label class="f">Period <select id="win">{win_opts}</select></label>
{sel("profile", "Profile")}{sel("playbook", "Playbook")}{sel("version", "Version")}{sel("environment", "Environment")}
<span class="meta">generated {html.escape(meta["generated"])} · {meta["stats"]["lines"]} records ({meta["stats"]["malformed"]} skipped) · {html.escape(meta["granularity"])} buckets · local only</span></header>
<main>
<div id="period" class="empty" style="text-align:left;padding:0 0 10px"></div>
<div class="cards" id="cards"></div>
<div class="grid">
<div class="panel wide"><h2>Harness health trend (weekly)</h2><div id="trend"></div><div class="legend"><span><i style="background:#2b6cb0"></i>completion</span><span><i style="background:#c9463d"></i>gap rate</span><span><i style="background:#2f8f5b"></i>validation pass</span><span><i style="background:#7c5cbf"></i>evidence coverage</span></div></div>
<div class="panel"><h2>Playbook usage</h2><div id="playbooks"></div></div>
<div class="panel"><h2>Gap rate by playbook</h2><div id="gaps-pb"></div></div>
<div class="panel"><h2>Execution mode</h2><div id="exec"></div></div>
<div class="panel"><h2>Validation state (declared)</h2><div id="validation"></div></div>
<div class="panel"><h2>Tool / MCP usage (observed)</h2><div id="tools"></div></div>
<div class="panel"><h2>Harness version</h2><div id="versions"></div></div>
<div class="panel wide"><h2>Gaps / attention</h2><ul class="gaps" id="gaps"></ul></div>
</div>
</main>
<footer>
<p><b>Definitions.</b> Completion = declared outcome <i>complete</i> ÷ tasks with a known outcome. Gap rate = partial + blocked + failed ÷ known outcomes. Verified outcome = completed tasks with an observed test or deploy run ÷ completed tasks. Validation pass = declared <i>verified</i> ÷ tasks with a known validation state. Evidence coverage = tasks declaring at least one evidence source ÷ tasks with a metadata block. Metadata compliance = tasks with a metadata block ÷ all tool-using tasks. Rework rate and verified accuracy need ground truth the telemetry does not collect, so they show N/A rather than 0%.</p>
<p><b>Observed vs declared.</b> Tools, files, tests, deploys, profile and version were determined by the hook; outcome, validation, evidence and playbook are what the model stated and are not independently verified.</p>
<p><b>Privacy.</b> This page embeds only aggregated counters (no prompts, responses, code, paths, identifiers or secrets) and makes no network requests.</p>
</footer>
<script id="gw-data" type="application/json">{payload}</script>
<script>{JS}</script>
<script>{JS_UI}</script>
</body></html>
"""


# ---------------------------------------------------------------- generate
def generate(args) -> dict:
    cfg = load_config()
    window = int(args.window) if args.window else cfg["window_days"]
    ref = dt.date.fromisoformat(args.now) if args.now else dt.date.today()
    ev = Path(os.path.expanduser(args.events)) if args.events else events_path()
    out = Path(os.path.expanduser(args.out)) if args.out else reports_dir()
    records, stats = load_events(ev)
    buckets, granularity = aggregate(records)
    meta = {"generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "ref": ref.isoformat(), "window_days": window,
            "events": str(ev), "stats": stats, "granularity": granularity}
    metrics = compute(buckets, window, ref)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    page = render_html(buckets, meta)
    md = render_markdown(metrics, meta)
    written = []
    targets = [("dashboard.html", page)]
    if args.snapshot:
        targets += [(f"{ref.isoformat()}.html", page), (f"{ref.isoformat()}.md", md)]
    for name, text in targets:
        tmp = out / (name + ".tmp")
        tmp.write_text(text)
        os.chmod(tmp, 0o600)
        os.replace(tmp, out / name)
        written.append(str(out / name))
    return {"written": written, "records": len(records), "buckets": len(buckets), "stats": stats, "summary": metrics["summary"]}


# ---------------------------------------------------------------- schedule (macOS launchd)
def launch_agents_dir() -> Path:
    return Path(os.path.expanduser(os.environ.get("GROUNDWORK_LAUNCH_AGENTS_DIR") or "~/Library/LaunchAgents"))


def plist_path() -> Path:
    return launch_agents_dir() / f"{LABEL}.plist"


def calendar(freq: str, hour: int) -> dict:
    return {"daily": {"Hour": hour, "Minute": 0}, "weekly": {"Weekday": 1, "Hour": hour, "Minute": 0},
            "monthly": {"Day": 1, "Hour": hour, "Minute": 0}, "yearly": {"Month": 1, "Day": 1, "Hour": hour, "Minute": 0}}[freq]


def launchctl(*argv) -> int:
    if os.environ.get("GROUNDWORK_NO_LAUNCHCTL"):
        return 0
    try:
        return subprocess.run(["launchctl", *argv], capture_output=True, text=True, timeout=30).returncode
    except Exception:
        return 1


def schedule(freq: str, hour=None) -> dict:
    cfg = load_config()
    if hour is not None:
        cfg["hour"] = min(23, max(0, int(hour)))
    cfg["schedule"] = freq
    save_config(cfg)
    domain = f"gui/{os.getuid()}"
    launchctl("bootout", f"{domain}/{LABEL}")  # remove any previous job first: never two jobs
    p = plist_path()
    if freq == "disabled":
        if p.exists():
            p.unlink()
        return {"schedule": "disabled", "plist": None}
    logs = reports_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        env["CLAUDE_CONFIG_DIR"] = os.environ["CLAUDE_CONFIG_DIR"]
    plist = {"Label": LABEL, "ProgramArguments": ["/usr/bin/env", "python3", str(Path(__file__).resolve()), "generate", "--snapshot"],
             "StartCalendarInterval": calendar(freq, cfg["hour"]), "RunAtLoad": False,
             "StandardOutPath": str(logs / "report.log"), "StandardErrorPath": str(logs / "report.err"),
             "EnvironmentVariables": env, "ProcessType": "Background"}
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        plistlib.dump(plist, f)
    rc = launchctl("bootstrap", domain, str(p))
    if rc != 0:  # older launchctl
        launchctl("load", "-w", str(p))
    return {"schedule": freq, "plist": str(p), "hour": cfg["hour"]}


def status() -> dict:
    cfg = load_config()
    p = plist_path()
    return {"config": cfg, "plist_present": p.exists(), "plist": str(p), "events": str(events_path()),
            "reports_dir": str(reports_dir()), "dashboard_present": (reports_dir() / "dashboard.html").exists()}


# ---------------------------------------------------------------- cli
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="groundwork-report", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("generate", help="write dashboard.html (and dated snapshots with --snapshot)")
    g.add_argument("--window", type=int, help="health window in days (default from report.json, 30)")
    g.add_argument("--snapshot", action="store_true", help="also write YYYY-MM-DD.html and YYYY-MM-DD.md")
    g.add_argument("--events", help="telemetry file (default ~/.claude/groundwork/telemetry/events.jsonl)")
    g.add_argument("--out", help="output directory (default ~/.claude/groundwork/reports)")
    g.add_argument("--now", help="reference date YYYY-MM-DD (default today)")
    s = sub.add_parser("schedule", help="set the launchd schedule")
    s.add_argument("frequency", choices=FREQS)
    s.add_argument("--hour", type=int, help="hour of day, 0-23 (default 8)")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if args.cmd == "generate":
        res = generate(args)
        for w in res["written"]:
            print(w)
        print(f"records={res['records']} buckets={res['buckets']} skipped={res['stats']['malformed']}")
        return 0
    if args.cmd == "schedule":
        print(json.dumps(schedule(args.frequency, args.hour)))
        return 0
    if args.cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # report failures are isolated: print and exit non-zero; nothing else runs here
        print(f"groundwork-report: {e}", file=sys.stderr)
        sys.exit(1)
