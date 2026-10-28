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
import bisect
import datetime as dt
import html
import json
import os
import plistlib
import re
import stat
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1"
MAX_BYTES = 64 * 1024 * 1024       # never read more than the last 64 MB of telemetry
MAX_BUCKETS = 4000                 # above this, days collapse into ISO weeks
TOOL_NAME_CAP = 80                 # defensive bound only, matches hooks/groundwork_telemetry.py's own cap
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


def tool_events_path() -> Path:
    """The per-tool-call sibling file (hooks/groundwork_telemetry.py's PostToolUse/
    PostToolUseFailure records) — a separate file and schema from events.jsonl; see that hook's
    module docstring for why. Read-only here, same as events_path()."""
    return Path(os.path.expanduser(os.environ.get("GROUNDWORK_TOOL_TELEMETRY_PATH") or str(config_dir() / "groundwork" / "telemetry" / "tool_events.jsonl")))


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
        # for context_bands() and performance_gaps() only — never copied into buckets, so the page never embeds them
        "ctx": _ctx(ob.get("ctx_pct")),
        "sid": str(raw.get("session_id") or "")[:80],
        "ts": ts[:20],
        "project": str(raw.get("cwd_hash") or "")[:16],
        "pid": _id(raw.get("prompt_id")),
        "cit": _citations(ob.get("citations")),
        "cost": float(ob["cost_usd"]) if _num(ob.get("cost_usd")) and ob["cost_usd"] >= 0 else None,
        "cost_age": int(ob["cost_age_s"]) if _num(ob.get("cost_age_s")) and 0 <= ob["cost_age_s"] <= 60 else None,
        "head": ob["head"] if isinstance(ob.get("head"), str) and GH_SHA.fullmatch(ob["head"]) else None,
        "repo": ob.get("repo") if isinstance(ob.get("repo"), str) and "/" in ob.get("repo") else None,
    }


def _citations(v):
    if not isinstance(v, dict):
        return None
    try:
        c = {k: int(v.get(k, 0)) for k in ("checked", "resolved", "unchecked")}
    except (TypeError, ValueError):
        return None
    return c if all(x >= 0 for x in c.values()) and c["resolved"] <= c["checked"] else None


def _ctx(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 100 else None


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


def normalise_tool(raw: dict):
    """One tool_events.jsonl line (hooks/groundwork_telemetry.py's per-call schema) -> a small flat
    record, or None. Deliberately separate from normalise() above: different file, different
    schema, no shared dimensions (no profile/playbook/version/environment — a single tool call
    carries none of those) — folding the two into one normaliser would just be two unrelated
    branches pretending to be one function."""
    if not isinstance(raw, dict) or raw.get("schema") != 1:
        return None
    ts = str(raw.get("ts") or "")
    if len(ts) < 10 or not ts[:4].isdigit():
        return None
    try:
        day = dt.date.fromisoformat(ts[:10])
    except ValueError:
        return None
    # Unlike _label() fields below, the tool name is kept at its original case: it is an
    # identifier (e.g. "Bash", "mcp__github__list_prs"), not a free-text label to fold/validate —
    # normalise() above treats the per-turn record's own `tools` list the same way.
    tool = str(raw.get("tool") or "").strip()[:TOOL_NAME_CAP]
    if not tool:
        return None
    category = _label(raw.get("category"))
    return {"day": day.isoformat(), "tool": tool, "category": category if category in ("builtin", "mcp") else "unknown",
            "success": bool(raw.get("success")), "interrupted": raw.get("interrupted") is True}


def load_tool_events(path: Path):
    """Bounded, tolerant read of the per-tool-call sibling file — same shape of contract as
    load_events() (malformed lines counted and skipped, never raises on a missing file)."""
    records, stats = [], {"lines": 0, "malformed": 0, "bytes_skipped": 0}
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > MAX_BYTES:
                f.seek(size - MAX_BYTES)
                f.readline()
                stats["bytes_skipped"] = size - MAX_BYTES
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                stats["lines"] += 1
                try:
                    rec = normalise_tool(json.loads(raw))
                except Exception:
                    rec = None
                if rec is None:
                    stats["malformed"] += 1
                else:
                    records.append(rec)
    except FileNotFoundError:
        pass
    return records, stats


# ---------------------------------------------------------------- context bands
CTX_BANDS = ((0, 30), (30, 50), (50, 70), (70, 85), (85, 101))
CTX_MAX_AGE_S = 15 * 60            # same limit as hooks/groundwork_telemetry.py: older readings are not this task's


def usage_path() -> Path:
    override = os.environ.get("GROUNDWORK_USAGE_PATH")
    return Path(os.path.expanduser(override)) if override else config_dir() / "groundwork" / "telemetry" / "usage.jsonl"


def _epoch(ts: str):
    try:
        return dt.datetime.strptime(ts[:20], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
    except Exception:
        return None


def load_usage(path: Path) -> dict:
    """session_id -> sorted [(epoch, ctx_pct)] from the statusLine usage records (kept about 8 days)."""
    out = defaultdict(list)
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if size > MAX_BYTES:
                f.seek(size - MAX_BYTES)
                f.readline()
            for raw in f:
                try:
                    r = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(r, dict):
                    continue
                t, pct = _epoch(str(r.get("ts") or "")), _ctx(r.get("ctx_pct"))
                if t is not None and pct is not None and r.get("session_id"):
                    out[str(r["session_id"])[:80]].append((t, pct))
    except (FileNotFoundError, OSError):
        pass
    for v in out.values():
        v.sort()
    return out


def _ctx_from_usage(usage: dict, sid: str, ts: str):
    """Latest statusLine reading for the session at or before the task ended, if recent enough."""
    end = _epoch(ts)
    if end is None or sid not in usage:
        return None
    best = None
    for t, pct in usage[sid]:
        if t > end:
            break
        best = (t, pct)
    return best[1] if best and end - best[0] <= CTX_MAX_AGE_S else None


def context_bands(records: list, usage: dict, window_days, ref: dt.date) -> dict:
    """Outcome rates by context-window fill at task end, for the same period as the main report.
    Uses the context % the telemetry hook recorded; for older records, the statusLine reading
    at or just before the task ended. Same rate definitions as _summarise()."""
    if window_days:
        start = ref - dt.timedelta(days=window_days)
        sel = [r for r in records if start < dt.date.fromisoformat(r["day"]) <= ref]
    else:
        sel = records
    acc = [Counter() for _ in CTX_BANDS]
    recorded = joined = unmatched = 0
    for r in sel:
        pct = r.get("ctx")
        if pct is not None:
            recorded += 1
        else:
            pct = _ctx_from_usage(usage, r.get("sid", ""), r.get("ts", ""))
            if pct is None:
                unmatched += 1
                continue
            joined += 1
        i = next(i for i, (lo, hi) in enumerate(CTX_BANDS) if lo <= pct < hi)
        c = acc[i]
        c["n"] += 1
        c[r["outcome"]] += 1
        c["corroborated"] += 1 if (r["outcome"] == "complete" and (r["tests"] or r["deploy"])) else 0
    bands = []
    for (lo, hi), c in zip(CTX_BANDS, acc):
        known = sum(c[o] for o in OUTCOMES if o != "unknown")
        bands.append({"band": f"{lo}–{min(hi, 100)}%", "n": c["n"], "known": known,
                      "completion": _rate(c["complete"], known),
                      "verified_outcome": _rate(c["corroborated"], c["complete"]),
                      "gap": _rate(c["partial"] + c["blocked"] + c["failed"], known),
                      "low_n": known < MIN_TREND_N})
    return {"bands": bands, "recorded": recorded, "joined": joined, "unmatched": unmatched}


CTX_NOTE = ("Context fill = how full the context window was when the task ended (from the statusLine; the reading can lag by up to 15 minutes). "
            "This shows association, not cause: fuller contexts often mean longer, harder tasks. "
            "Outcome is what the model declared; the test-shaped column needs a test-shaped command or deploy seen in the task (a broad match). "
            f"Bands with fewer than {MIN_TREND_N} known outcomes are marked low data. "
            "Tasks with no statusLine reading (headless runs, statusLine off, or older than the ~8 days of usage records) are not placed in a band.")


# ---------------------------------------------------------------- performance gaps
# Each question is answered by one metric defined in openspec/changes/add-accuracy-signals/design.md (D3, D4, D8).
# Labels: observed = the hook saw it; declared = the model said it (parsed from its reply); pattern = a command or text
# matched by a named pattern; estimate = list-price cost; opt-in = needs `generate --github`.
SIGNAL_KINDS = ("review", "prompt", "compact", "guardrail")
GUARD_HOOKS = ("push_guard", "task_gate", "review_gate", "reply_check")
CALL_KINDS = ("test", "check", "deploy", "runtime_read")
LOW_N = 20                          # 5..19 cases: the rate is shown, flagged "low data"
CORRECTION_WINDOW_S = 2 * 3600      # Q4: the next prompt counts only within 2 hours
COMPACT_SPAN = 3                    # Q9: turns before / after a compaction
GH_MAX_COMMITS = 50
GH_TIMEOUT_S = 10
GH_MAX_PAGES = 10
GH_REPO = re.compile(r"([\w.-]+)/([\w.-]+)")
GH_SHA = re.compile(r"[0-9a-f]{40}")
CI_PASS = {"success", "neutral", "skipped"}
LEDGER_REVIEW = re.compile(r"must_fix=(\d+|None)\s*$")  # hooks/groundwork_tasks.py record_review's history detail


def signals_path() -> Path:
    override = os.environ.get("GROUNDWORK_SIGNALS_PATH")
    return Path(os.path.expanduser(override)) if override else config_dir() / "groundwork" / "telemetry" / "signals.jsonl"


def tasks_dir() -> Path:
    return config_dir() / "groundwork" / "tasks"


def _open_regular(path: Path):
    """Open for reading without blocking on a FIFO, and only a regular file."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        return os.fdopen(fd, "rb")
    except Exception:
        os.close(fd)
        raise


def _jsonl(path: Path):
    """Bounded, tolerant line reader for the signal and tool-row loaders."""
    try:
        f = _open_regular(path)
    except OSError:
        return
    with f:
        size = os.fstat(f.fileno()).st_size
        if size > MAX_BYTES:
            f.seek(size - MAX_BYTES)
            f.readline()
        for raw in f:
            try:
                r = json.loads(raw)
            except Exception:
                continue
            if isinstance(r, dict):
                yield r


def _id(v, cap=100) -> str:
    """An id field; "" for missing and for the hooks' "unknown" placeholder (design D6: such rows are ignored)."""
    s = str(v or "")[:cap]
    return "" if s == "unknown" else s


def _num(v) -> bool:
    """A finite number in a sane range: a poisoned file (Infinity, 1e300) is skipped, never crashes the report."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and -1e12 < v < 1e12


def load_signals(path: Path) -> list:
    out = []
    for r in _jsonl(path):
        t, kind, sid = _epoch(str(r.get("ts") or "")), r.get("kind"), _id(r.get("session_id"), 80)
        if t is None or kind not in SIGNAL_KINDS or not sid:
            continue
        s = {"t": t, "kind": kind, "sid": sid, "pid": _id(r.get("prompt_id"))}
        if kind == "review":
            mf = r.get("must_fix")
            s["agent"] = _id(r.get("agent_id"))
            s["must_fix"] = min(int(mf), 1000) if r.get("parsed") is True and _num(mf) and mf >= 0 else None
        elif kind == "prompt":
            s["correction"] = r.get("correction") is True
            s["skipped"] = r.get("skipped") is True
        elif kind == "compact":
            s["trigger"] = r.get("trigger") if r.get("trigger") in ("manual", "auto") else "unknown"
        else:
            s["hook"] = r.get("hook") if r.get("hook") in GUARD_HOOKS else "unknown"
            s["decision"] = r.get("decision") if r.get("decision") in ("deny", "ask", "block") else "unknown"
            s["cause"] = "internal_error" if r.get("cause") == "internal_error" else "policy"
            s["tuid"] = _id(r.get("tool_use_id"))
        out.append(s)
    out.sort(key=lambda s: s["t"])
    return out


def load_tool_rows(path: Path) -> list:
    """tool_events.jsonl rows with the fields D3 keeps: ids, time, Bash kind/result, commit flag, success.
    File order is append order, so rows stay in call order within a turn."""
    out = []
    for r in _jsonl(path):
        if r.get("schema") != 1:
            continue
        t, sid = _epoch(str(r.get("ts") or "")), _id(r.get("session_id"), 80)
        if t is None or not sid:
            continue
        kind = r.get("kind") if r.get("kind") in CALL_KINDS else None
        result = r.get("result") if kind in ("test", "check") and r.get("result") in ("pass", "fail", "unknown") else None
        out.append({"t": t, "sid": sid, "pid": _id(r.get("prompt_id")), "tuid": _id(r.get("tool_use_id")),
                    "kind": kind, "result": result, "ok": r.get("success") is True,
                    "commit": r.get("git_commit") is True and r.get("success") is True})
    return out


def load_ledger(root: Path = None) -> list:
    """Every repository's task ledger: tier, state, session and, from the `history` list, review results and
    operation times. Only the must-fix number is read from a history detail; no command text is kept.
    `history` keeps the last 60 events (hooks/groundwork_tasks.py MAX_HISTORY): a task whose first kept event is not
    its intake has lost its start and is marked truncated, so Q3 never reads a later review as the first one."""
    root = root or tasks_dir()
    out = []
    try:
        files = sorted(root.glob("*/*.json"))
    except OSError:
        return out
    for p in files:
        if p.name == "repo.json":
            continue
        try:
            with _open_regular(p) as fh:
                t = json.loads(fh.read(4 * 1024 * 1024))
        except Exception:
            continue
        if not isinstance(t, dict) or not _num(t.get("created_at")) or not 0 < t["created_at"] < 4e9:
            continue
        hist = [h for h in (t.get("history") or []) if isinstance(h, dict) and _num(h.get("ts"))]
        reviews, ops = [], []
        for h in hist:
            if h.get("event") == "review":
                m = LEDGER_REVIEW.search(str(h.get("detail") or ""))
                if m:
                    reviews.append((float(h["ts"]), None if m.group(1) == "None" else int(m.group(1))))
            elif h.get("event") == "operation":
                ops.append(float(h["ts"]))
        out.append({"created": float(t["created_at"]), "tier": str(t.get("tier") or ""),
                    "complete": t.get("state") == "complete", "sid": _id(t.get("session_id"), 80),
                    "reviews": reviews, "ops": ops, "truncated": not hist or hist[0].get("event") != "intake"})
    return out


def build_turns(records: list, rows: list, signals: list):
    """Design D3. A turn is (session_id, prompt_id); its Stop records are merged. Tool rows and signals join on
    prompt_id; rows without one use the first Stop of the session at or after them (labelled fallback). Prompts
    with tool rows but no Stop become no_stop turns. Everything is attributed before any window is applied.
    Returns (turns sorted by end time, no_stop list, number of fallback-attributed items)."""
    stops = sorted((dict(r, t=_epoch(r["ts"])) for r in records if r.get("sid") and _epoch(r.get("ts", "")) is not None),
                   key=lambda r: r["t"])
    turns, by_key = [], {}
    for r in stops:
        key = (r["sid"], r["pid"]) if r.get("pid") else None
        tr = by_key.get(key) if key else None
        if tr is None:
            tr = {"sid": r["sid"], "pid": r.get("pid") or "", "outcome": "unknown", "validation": "unknown",
                  "impl": False, "deploy": False, "cit": None, "rows": [], "sigs": [], "stops": 0, "fallback": False}
            turns.append(tr)
            if key:
                by_key[key] = tr
        tr["stops"] += 1
        tr.update(t=r["t"], day=r["day"], version=r["version"], ctx=r.get("ctx"), cost=r.get("cost"),
                  cost_age=r.get("cost_age"))
        if r["outcome"] != "unknown":
            tr["outcome"] = r["outcome"]  # last *stated* outcome: a follow-up Stop that states none keeps the earlier one
        if r["validation"] != "unknown":
            tr["validation"] = r["validation"]
        tr["impl"] = tr["impl"] or r["impl"]
        tr["deploy"] = tr["deploy"] or r["deploy"]
        if r.get("cit"):
            c = tr["cit"] or {"checked": 0, "resolved": 0, "unchecked": 0}
            tr["cit"] = {k: c[k] + r["cit"][k] for k in c}
        if r.get("head"):
            tr["head"], tr["repo"] = r["head"], r.get("repo")
    turns.sort(key=lambda x: x["t"])
    ends = defaultdict(list)  # sid -> that session's turns in end-time order, for the time fallback
    for tr in turns:
        ends[tr["sid"]].append(tr)
    no_stop, fallback = {}, 0
    for field, items in (("rows", rows), ("sigs", signals)):
        for it in items:
            if it["pid"]:
                tr = by_key.get((it["sid"], it["pid"]))
                if tr is not None:
                    tr[field].append(it)
                elif field == "rows":
                    ns = no_stop.setdefault((it["sid"], it["pid"]), {"sid": it["sid"], "t": it["t"], "rows": []})
                    ns["rows"].append(it)
                continue
            sess = ends.get(it["sid"], [])
            i = bisect.bisect_left([x["t"] for x in sess], it["t"])
            if i < len(sess):
                sess[i][field].append(it)
                sess[i]["fallback"] = True
                fallback += 1
    for tr in turns:
        tr["new"] = tr["cit"] is not None  # written by this change's Stop hook, so its tool rows carry kind/result
    return turns, sorted(no_stop.values(), key=lambda n: n["t"]), fallback


def _final_test(tr) -> str:
    tests = [r for r in tr["rows"] if r["kind"] == "test"]
    if not tests:
        return "none"
    known = [r["result"] for r in tests if r["result"] in ("pass", "fail")]
    return known[-1] if known else "unknown"


def _show(r) -> str:
    """Design D4 display rule: < 5 cases insufficient data (n); 5..19 low data; 20+ plain."""
    if r is None or r["den"] < MIN_TREND_N:
        return f"insufficient data ({r['den'] if r else 0})"
    return fmt(r) + (" low data" if r["den"] < LOW_N else "")


def _median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def _gq(qid, question, labels, definition, answer, r=None, notes=(), rows=None, status="ok"):
    return {"id": qid, "question": question, "labels": list(labels), "definition": definition, "answer": answer,
            "num": r["num"] if r else None, "den": r["den"] if r else 0, "rate": r["rate"] if r else None,
            "notes": [n for n in notes if n], "rows": rows or [], "status": status}


def _q1a(turns):
    pop = [t for t in turns if t["new"] and t["impl"] and t["outcome"] == "complete"]
    return _rate(sum(1 for t in pop if _final_test(t) == "fail"), len(pop))


def _q1b(turns):
    pop = [t for t in turns if t["new"] and t["impl"] and t["validation"] == "verified"]
    return _rate(sum(1 for t in pop if not any(r["kind"] for r in t["rows"])), len(pop))


def _q2_fail(turns):
    states = Counter(_final_test(t) for t in turns if t["new"] and t["impl"])
    return _rate(states["fail"], states["fail"] + states["pass"]), states


def _q4(turns, prompts_by_sid):
    num = den = 0
    for t in turns:
        if t["outcome"] != "complete":
            continue
        ps = prompts_by_sid.get(t["sid"], [])
        i = bisect.bisect_right([p["t"] for p in ps], t["t"])
        if i < len(ps) and ps[i]["t"] - t["t"] <= CORRECTION_WINDOW_S:
            den += 1
            num += ps[i]["correction"]
    return _rate(num, den)


def _unstated(turns, field):
    pop = [t for t in turns if t["new"] and t["impl"]]
    return _rate(sum(1 for t in pop if t[field] == "unknown"), len(pop))


def _unstated_note(r, what):
    return f"{what} unstated in {fmt(r)} of file-changing turns" if r else ""


def commit_turns(turns) -> list:
    """(repo, sha) of the newest GH_MAX_COMMITS commit turns: a successful Bash `git commit` and a recorded HEAD."""
    out = []
    for t in sorted(turns, key=lambda t: -t["t"]):
        if t.get("head") and any(r["commit"] for r in t["rows"]):
            key = (t.get("repo") or "", t["head"])
            if key not in out:
                out.append(key)
    return out[:GH_MAX_COMMITS]


def _safe_commit(repo: str, sha: str) -> bool:
    m = GH_REPO.fullmatch(repo or "")
    return bool(m) and m.group(1) not in (".", "..") and m.group(2) not in (".", "..") and bool(GH_SHA.fullmatch(sha or ""))


def _gh_state(p) -> str:
    err = (p.stderr or "") + (p.stdout or "")
    if "HTTP 404" in err or "HTTP 422" in err:
        return "not_on_github"
    if "HTTP 401" in err or "gh auth login" in err:
        return "unauthenticated"
    return "error"


def ci_state(runs: list, statuses: list) -> str:
    """Design D8 mapping: no runs and no statuses = no checks; anything unfinished = pending; any failure = fail."""
    if not runs and not statuses:
        return "no_checks"
    if any(r.get("status") != "completed" for r in runs) or any(s.get("state") == "pending" for s in statuses):
        return "pending"
    if all(r.get("conclusion") in CI_PASS for r in runs) and all(s.get("state") == "success" for s in statuses):
        return "pass"
    return "fail"


def fetch_ci(commits: list, run=subprocess.run) -> dict:
    """Opt-in, read-only: (repo, sha) -> pass | fail | pending | no_checks | not_on_github | error | invalid,
    through the user's own `gh` login. {"_unavailable": reason} when gh is missing or not logged in."""
    out = {}
    for repo, sha in commits:
        if not repo:
            out[(repo, sha)] = "no_remote"  # origin is not on github.com
            continue
        if not _safe_commit(repo, sha):
            out[(repo, sha)] = "invalid"  # never passed to gh
            continue
        runs, statuses, state = [], [], None
        try:
            for page in range(1, GH_MAX_PAGES + 1):
                p = run(["gh", "api", "--method", "GET", f"repos/{repo}/commits/{sha}/check-runs?per_page=100&page={page}"],
                        capture_output=True, text=True, timeout=GH_TIMEOUT_S)
                if p.returncode != 0:
                    state = _gh_state(p)
                    break
                body = json.loads(p.stdout)
                batch = body.get("check_runs") or []
                runs += batch
                if not batch or len(runs) >= int(body.get("total_count") or 0):
                    break
            if state is None:
                p = run(["gh", "api", "--method", "GET", f"repos/{repo}/commits/{sha}/status"],
                        capture_output=True, text=True, timeout=GH_TIMEOUT_S)
                if p.returncode != 0:
                    state = _gh_state(p)
                else:
                    statuses = json.loads(p.stdout).get("statuses") or []
        except FileNotFoundError:
            return {"_unavailable": "gh is not installed"}
        except Exception:
            state = "error"
        if state == "unauthenticated":
            return {"_unavailable": "gh is not logged in"}
        out[(repo, sha)] = state or ci_state(runs, statuses)
    return out


def performance_gaps(records: list, rows: list, signals: list, ledger: list, window_days, ref: dt.date, ci=None) -> dict:
    """The Performance gaps section for the selected period (design D4). Not changed by the page filters."""
    turns, no_stop, fallback = build_turns(records, rows, signals)
    if window_days:
        start = ref - dt.timedelta(days=window_days)
        prev_start = start - dt.timedelta(days=window_days)
        in_win = lambda day: start < dt.date.fromisoformat(day) <= ref
        in_prev = lambda day: prev_start < dt.date.fromisoformat(day) <= start
    else:
        in_win, in_prev = (lambda day: True), (lambda day: False)
    day_of = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()
    win = [t for t in turns if in_win(t["day"])]
    prev = [t for t in turns if in_prev(t["day"])]
    sig_win = [s for s in signals if in_win(day_of(s["t"]))]
    prompts_by_sid = defaultdict(list)
    for s in signals:
        if s["kind"] == "prompt" and not s["skipped"]:
            prompts_by_sid[s["sid"]].append(s)
    qs = []
    impl_note = lambda field, what: _unstated_note(_unstated(win, field), what)

    # 1a / 1b / unstated-with-failure
    r = _q1a(win)
    qs.append(_gq("1a", "Does it say complete while tests fail?", ("observed", "declared", "pattern"),
                  "Turns that changed files and declared complete whose last test call with a known result failed, "
                  "out of turns that changed files and declared complete. Piped, background or interrupted test runs "
                  "have no known result and are ignored.", _show(r), r, [impl_note("outcome", "Outcome")]))
    r = _q1b(win)
    qs.append(_gq("1b", "Does it say verified without checking?", ("observed", "declared", "pattern"),
                  "Turns that changed files and declared verified with no test, check, deploy or runtime-read call of "
                  "any result, out of turns that changed files and declared verified.", _show(r), r,
                  [impl_note("validation", "Validation")]))
    hidden = sum(1 for t in win if t["new"] and t["impl"] and t["outcome"] == "unknown" and _final_test(t) == "fail")
    qs.append(_gq("1c", "Outcome unstated, last test failed", ("observed", "declared", "pattern"),
                  "File-changing turns that stated no outcome and whose last known test result failed, so a vague "
                  "reply cannot hide a failure.", str(hidden)))

    # 2 final test state
    r, states = _q2_fail(win)
    calls = [x for t in win for x in t["rows"] if x["kind"] == "test"]
    known_calls = [x for x in calls if x["result"] in ("pass", "fail")]
    per_call = _rate(sum(1 for x in known_calls if x["result"] == "pass"), len(known_calls))
    qs.append(_gq("2", "How do turns end on tests?", ("observed", "pattern"),
                  "Final test state of each file-changing turn: the result of its last test call with a known result. "
                  "The answer is the fail share of turns whose final state is known.", _show(r), r,
                  [f"pass {states['pass']}, fail {states['fail']}, unknown {states['unknown']}, no test {states['none']}",
                   f"per test call: {_show(per_call)} passed"]))

    # 3a / 3b / 3c from the task ledger
    material = [x for x in ledger if x["tier"] == "MATERIAL"]
    mat_win = [x for x in material if in_win(day_of(x["created"])) and not x["truncated"]]
    truncated = sum(1 for x in material if in_win(day_of(x["created"])) and x["truncated"])
    trunc_note = f"{truncated} task(s) left out: their history no longer starts at intake" if truncated else ""
    limit = "The gate adds evidence to every open task in the repository, so overlapping tasks share evidence."
    if not material:
        why = "not collected: task ledger empty" if not ledger else "not collected: no MATERIAL tasks recorded"
        for qid, q in (("3a", "Is MATERIAL work reviewed before it ships?"), ("3b", "Does review find defects before shipping?")):
            qs.append(_gq(qid, q, ("observed",), "From the Groundwork task ledger.", why, status="not_collected"))
    else:
        def first_clean(x):
            return next((ts for ts, mf in x["reviews"] if mf == 0), None)
        pop = [x for x in mat_win if x["complete"] or x["ops"]]
        early = sum(1 for x in pop if (x["ops"] and (first_clean(x) is None or min(x["ops"]) < first_clean(x)))
                    or (x["complete"] and first_clean(x) is None))
        r = _rate(early, len(pop))
        qs.append(_gq("3a", "Is MATERIAL work reviewed before it ships?", ("observed",),
                      "Ledger MATERIAL tasks that ran a sensitive operation before their first review at must-fix 0, or "
                      "completed with no such review, out of MATERIAL tasks that are complete or ran a sensitive "
                      "operation. Lower is better.",
                      _show(r), r, [limit, trunc_note]))
        reviewed = [x for x in mat_win if any(mf is not None for _, mf in x["reviews"])]
        found = sum(1 for x in reviewed if next(mf for _, mf in x["reviews"] if mf is not None) > 0)
        until = []
        for x in reviewed:
            known = [mf for _, mf in x["reviews"] if mf is not None]
            if 0 in known:
                until.append(known.index(0) + 1)
        r = _rate(found, len(reviewed))
        med = _median(until)
        qs.append(_gq("3b", "Does review find defects before shipping?", ("observed",),
                      "Ledger MATERIAL tasks whose first review reported at least one must-fix finding, out of MATERIAL "
                      "tasks with a review.", _show(r), r,
                      [f"median reviews until must-fix 0: {med:g} ({len(until)} tasks)" if med is not None else "",
                       trunc_note]))
    ledger_sids = {x["sid"] for x in ledger if x["sid"]}
    seen, outside = set(), 0
    for s in sig_win:
        if s["kind"] != "review":
            continue
        if s["agent"]:
            if s["agent"] in seen:
                continue  # the same review seen at PostToolUse and at SubagentStop (design D9)
            seen.add(s["agent"])
        outside += s["sid"] not in ledger_sids
    qs.append(_gq("3c", "How much review happens outside the ledger?", ("observed",),
                  "Independent reviews recorded in sessions that have no ledger task (a count, not a rate). A ledger task "
                  "belongs to the session that created it.", str(outside)))

    # 4 corrections
    r = _q4(win, prompts_by_sid)
    qs.append(_gq("4", "Do users have to correct finished work?", ("declared", "pattern"),
                  "Turns declared complete whose next prompt in the same session, within 2 hours, reads as a correction "
                  "(\"didn't work\", \"still failing\", \"that's wrong\", \"not what I asked\", \"you broke\"), out of "
                  "turns declared complete with a next prompt in that time. Pattern-matched: can miss corrections and "
                  "can over-count.", _show(r), r, [impl_note("outcome", "Outcome")]))

    # 5 citations
    cits = [t["cit"] for t in win if t["cit"]]
    checked, resolved, unchecked = (sum(c[k] for c in cits) for k in ("checked", "resolved", "unchecked"))
    r = _rate(resolved, checked)
    qs.append(_gq("5", "Do answers cite code that resolves?", ("pattern",),
                  "path:line citations in replies whose file exists inside the project with both ends of the range in "
                  "the file, out of citations checked. Paths outside the project, and bare names that are not files "
                  "(host:port), are not checkable. A resolving citation can still be the wrong line.", _show(r), r,
                  [f"{unchecked} not checkable"]))

    # 6 CI (opt-in)
    commits = commit_turns(win)
    ci_def = ("Commits made in a turn whose GitHub checks all passed, out of commits whose checks all finished. "
              "Read-only, through your own gh login; newest 50 commit turns.")
    if ci is None:
        qs.append(_gq("6", "Does pushed work pass CI?", ("opt-in",), ci_def, "opt-in: run generate --github",
                      notes=[f"{len(commits)} commit turn(s) recorded"], status="opt_in"))
    elif "_unavailable" in ci:
        qs.append(_gq("6", "Does pushed work pass CI?", ("opt-in",), ci_def, f"not available: {ci['_unavailable']}",
                      status="not_collected"))
    else:
        res = Counter(ci.get(c, "error") for c in commits)
        r = _rate(res["pass"], res["pass"] + res["fail"])
        qs.append(_gq("6", "Does pushed work pass CI?", ("opt-in",), ci_def, _show(r), r,
                      [f"no GitHub remote {res['no_remote']}, not on GitHub {res['not_on_github']}, "
                       f"no checks {res['no_checks']}, pending {res['pending']}, "
                       f"not readable {res['error'] + res['invalid']}"]))

    # 7 guardrails
    guards = [s for s in sig_win if s["kind"] == "guardrail"]
    new_win = [t for t in win if t["new"]]  # turns recorded by this change's hook: the only ones that can carry signals
    turn_keys = {(t["sid"], t["pid"]) for t in new_win}
    in_turns = [s for s in guards if (s["sid"], s["pid"]) in turn_keys or not s["pid"]]  # same population as the denominator
    fired = Counter(hook for _, _, hook, _ in {(s["sid"], s["pid"] or s["t"], s["hook"], s["decision"]) for s in in_turns})
    per100 = lambda n: f" ({100.0 * n / len(new_win):.1f}/100)" if len(new_win) >= MIN_TREND_N else ""
    tuids = {x["tuid"] for x in rows if x["tuid"]}
    denied = {s["tuid"] for s in guards if s["decision"] == "deny" and s["tuid"]}
    # an ask on a call another guard denied was never put to the user: neither approved nor declined
    asks = [s for s in guards if s["hook"] == "task_gate" and s["decision"] == "ask" and s["tuid"]
            and s["tuid"] not in denied]
    reviews_by_sid = defaultdict(list)
    for s in signals:
        if s["kind"] == "review":
            reviews_by_sid[s["sid"]].append(s["t"])
    blocks = [s for s in guards if s["hook"] == "review_gate" and s["decision"] == "block"]
    ask_r = _rate(sum(1 for s in asks if s["tuid"] in tuids), len(asks))
    blk_r = _rate(sum(1 for s in blocks if any(t >= s["t"] for t in reviews_by_sid.get(s["sid"], ()))), len(blocks))
    qs.append(_gq("7", "Where do guardrails step in, and are they followed?", ("observed",),
                  "Prompts in which each guard denied, asked or blocked, per 100 turns (shown from 5 turns). Follow-through: asks the user "
                  "approved (the tool then ran) out of asks; review-gate blocks followed by a review in the same session "
                  "out of blocks.", f"{sum(fired.values())} firing(s) in {len(new_win)} turns",
                  notes=["; ".join(f"{h} {n}{per100(n)}" for h, n in sorted(fired.items())) or "none recorded",
                         f"asks approved: {_show(ask_r)}", f"review-gate blocks followed by a review: {_show(blk_r)}",
                         f"{sum(1 for s in guards if s['cause'] == 'internal_error')} decided because the guard could not check"]))

    # 8 cost
    by_sid = defaultdict(list)
    for t in turns:
        by_sid[t["sid"]].append(t)
    position = {id(t): i for sess in by_sid.values() for i, t in enumerate(sess)}
    done = [t for t in win if t["outcome"] == "complete" and t["new"]]
    deltas = []
    for t in done:
        sess = by_sid[t["sid"]]
        i = position[id(t)]
        p = sess[i - 1] if i else None
        if p is None or t.get("cost") is None or p.get("cost") is None or t.get("cost_age") is None:
            continue
        if t["t"] - t["cost_age"] <= p["t"]:
            continue  # the reading predates the previous turn's end: it is that turn's spend (design D11)
        if t["cost"] >= p["cost"]:
            deltas.append(t["cost"] - p["cost"])
    med = _median(deltas)
    cov = _rate(len(deltas), len(done))
    qs.append(_gq("8", "What does a completed turn cost?", ("estimate", "declared"),
                  "Median increase in the session's estimated cost (statusLine, list price) from the previous turn to "
                  "each turn declared complete, where both readings exist and this one is newer than the previous turn. "
                  "Needs Groundwork's statusLine; headless runs have none.",
                  (f"${med:.2f} median" + (" low data" if len(deltas) < LOW_N else "")) if med is not None and len(deltas) >= MIN_TREND_N
                  else f"insufficient data ({len(deltas)})",
                  notes=[f"coverage {fmt(cov)} of completed turns" if cov else "no completed turns",
                         impl_note("outcome", "Outcome")]))

    # 9 compaction
    before, after, n_compact = [], [], 0
    for s in sig_win:
        if s["kind"] != "compact":
            continue
        n_compact += 1
        sess = by_sid.get(s["sid"], [])
        before += [t for t in [t for t in sess if t["t"] < s["t"]][-COMPACT_SPAN:] if id(t) not in {id(x) for x in before}]
        after += [t for t in [t for t in sess if t["t"] > s["t"]][:COMPACT_SPAN] if id(t) not in {id(x) for x in after}]
    qs.append(_gq("9", "Does quality change after compaction?", ("observed", "declared", "pattern"),
                  f"For the {COMPACT_SPAN} turns before and after each compaction in the same session: the 1a rate and "
                  "the Q4 rate. Association only: long sessions compact more and carry harder tasks.",
                  f"{n_compact} compaction(s)",
                  notes=[f"1a before {_show(_q1a(before))} · after {_show(_q1a(after))}",
                         f"Q4 before {_show(_q4(before, prompts_by_sid))} · after {_show(_q4(after, prompts_by_sid))}"]))

    # 10 by version and against the previous period
    vrows = []
    for v in sorted({t["version"] for t in win}):
        vt = [t for t in win if t["version"] == v]
        vrows.append([v, _show(_q1a(vt)), _show(_q1b(vt)), _show(_q2_fail(vt)[0]), _show(_q4(vt, prompts_by_sid))])
    changes = []
    for name, f in (("1a", _q1a), ("1b", _q1b), ("2 fail share", lambda ts: _q2_fail(ts)[0]),
                    ("4", lambda ts: _q4(ts, prompts_by_sid))):
        a, b = f(win), f(prev)
        if a and b and a["den"] >= MIN_TREND_N and b["den"] >= MIN_TREND_N:
            changes.append(f"{name} {a['rate'] - b['rate']:+.1f} points")
    qs.append(_gq("10", "Did the last Groundwork version help?", ("observed", "declared", "pattern"),
                  "Q1a, Q1b, Q2 fail share and Q4 per harness version, and the change against the previous period "
                  "(both periods at least 5 cases). Association only; ledger questions have no version.",
                  f"{len(vrows)} version(s)", notes=["vs previous period: " + (", ".join(changes) or "too few cases")],
                  rows=vrows))

    # 11 first drafts
    redo = sum(1 for t in win if any(s["kind"] == "guardrail" and s["hook"] in ("reply_check", "review_gate")
                                     for s in t["sigs"]))
    r = _rate(redo, sum(1 for t in win if t["new"]))
    qs.append(_gq("11", "Are first drafts complete?", ("observed",),
                  "Turns in which the reply check or the review gate sent the reply back, out of turns. Lower is better.",
                  _show(r), r))

    head = [f"{len(win)} turn(s) in the period",
            f"{sum(1 for n in no_stop if in_win(day_of(n['t'])))} with tool calls but no Stop record "
            "(interrupted, failed, or not recorded), counted apart",
            f"{fallback} record(s) without a prompt id matched by time" if fallback else ""]
    return {"questions": qs, "head": [h for h in head if h]}


GAPS_FOOTER = ("A rate needs at least 5 cases (below that: insufficient data); 5 to 19 cases are marked low data. "
               "Labels: observed = the hook saw it; declared = the model said it; pattern = matched by a named pattern; "
               "estimate = list-price cost; opt-in = needs generate --github. "
               "Benchmark score per release: not collected (runner on branch bench/vanilla-vs-groundwork).")


def gaps_markdown(gaps) -> list:
    if not gaps:
        return []
    lines = ["## Performance gaps", "", "_" + " · ".join(gaps["head"]) + ". Selected period; not changed by filters._", "",
             "| Q | Question | Answer | Labels | Notes |", "|---|---|---|---|---|"]
    for q in gaps["questions"]:
        lines.append(f"| {q['id']} | {q['question']} | {q['answer']} | {', '.join(q['labels'])} | {'; '.join(q['notes'])} |")
    for q in gaps["questions"]:
        if q["rows"]:
            lines += ["", f"Q{q['id']} by version:", "", "| Version | 1a | 1b | 2 fail share | 4 |", "|---|---|---|---|---|"]
            lines += [f"| {' | '.join(row)} |" for row in q["rows"]]
    lines += ["", "Definitions:", ""] + [f"- **{q['id']}** {q['definition']}" for q in gaps["questions"]]
    lines += ["", f"_{GAPS_FOOTER}_", ""]
    return lines


def gaps_panel_html(gaps) -> str:
    if not gaps:
        return ""
    e = html.escape
    rows = "".join(
        f'<tr class="gq-{e(q["status"])}"><td>{e(q["id"])}</td><td><b>{e(q["question"])}</b>'
        f'<div class="note">{e(q["definition"])}</div></td><td class="ans">{e(q["answer"])}</td>'
        f'<td>{e(", ".join(q["labels"]))}</td><td class="note">{"<br>".join(e(n) for n in q["notes"])}</td></tr>'
        for q in gaps["questions"])
    extra = ""
    for q in gaps["questions"]:
        if q["rows"]:
            body = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>" for row in q["rows"])
            extra += (f'<h3 class="note">Q{e(q["id"])} by version</h3><div class="tw"><table class="gaps-t"><thead><tr>'
                      f'<th>Version</th><th>1a</th><th>1b</th><th>2 fail share</th><th>4</th></tr></thead>'
                      f'<tbody>{body}</tbody></table></div>')
    return ('<div class="panel wide" id="perf-gaps"><h2>Performance gaps</h2>'
            f'<p class="note">{e(" · ".join(gaps["head"]))}. Selected period only; not changed by the filters above.</p>'
            '<div class="tw"><table class="gaps-t"><thead><tr><th>Q</th><th>Question</th><th>Answer</th><th>Labels</th>'
            f'<th>Notes</th></tr></thead><tbody>{rows}</tbody></table></div>{extra}'
            f'<p class="note">{e(GAPS_FOOTER)}</p></div>')


def aggregate_tool_calls(records: list, window_days, ref: dt.date, top_n: int = 15) -> dict:
    """Per-tool call counts and success rate within the same (ref - window, ref] period compute()
    uses for the main report — a small, separate computation (no shared buckets with aggregate()/
    compute(): this data has no profile/playbook/version/environment dimensions to key by, and no
    interactive filters reference it, so it is not wired into render_html()/the JS twin — see
    hooks/groundwork_telemetry.py's module docstring and the CHANGELOG entry for why this stays a
    Markdown-only addition rather than a new dashboard panel)."""
    if window_days:
        start = ref - dt.timedelta(days=window_days)
        sel = [r for r in records if start < dt.date.fromisoformat(r["day"]) <= ref]
    else:
        sel = records
    by_tool = {}
    for r in sel:
        b = by_tool.setdefault(r["tool"], {"category": r["category"], "n": 0, "ok": 0, "intr": 0})
        b["n"] += 1
        b["ok"] += 1 if r["success"] else 0
        b["intr"] += 1 if r.get("interrupted") else 0
    top = sorted(by_tool.items(), key=lambda kv: (-kv[1]["n"], kv[0]))[:top_n]
    total = len(sel)
    ok_total = sum(b["ok"] for b in by_tool.values())
    intr_total = sum(b["intr"] for b in by_tool.values())
    # An interrupted call ended as an abort, not as an error the tool reported (Claude Code hooks
    # docs): neither a success nor a tool failure, so it stays out of every success-rate denominator.
    return {"total": total, "interrupted": intr_total, "success": _rate(ok_total, total - intr_total),
            "by_tool": [{"tool": t, "category": b["category"], "n": b["n"], "ok": b["ok"], "interrupted": b["intr"],
                          "rate": _rate(b["ok"], b["n"] - b["intr"])} for t, b in top]}


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


def render_markdown(m: dict, meta: dict, tool_metrics: dict = None, ctx_bands: dict = None, gaps: list = None) -> str:
    s, t = m["summary"], m["trends"]
    lines = [f"# Groundwork health — {meta['generated']}", "",
             f"Window: last {meta['window_days']} days (to {meta['ref']}) · filters: none · source: {meta['events']} ({meta['stats']['lines']} lines, {meta['stats']['malformed']} skipped)", "",
             "## Summary", "",
             f"- Total tasks: {s['total']}",
             f"- Completion: {fmt(s['completion'])}{fmt_trend(t.get('completion'))}",
             f"- Complete with a test-shaped command seen (broad match; Q2 has real results): {fmt(s['verified_outcome'])}{fmt_trend(t.get('verified_outcome'))}",
             f"- Gap rate: {fmt(s['gap'])}{fmt_trend(t.get('gap'))}",
             f"- Validation pass: {fmt(s['validation'])}{fmt_trend(t.get('validation'))}",
             f"- Evidence coverage: {fmt(s['evidence'])}{fmt_trend(t.get('evidence'))}",
             f"- Metadata compliance: {fmt(s['compliance'])}{fmt_trend(t.get('compliance'))}",
             "- Rework and accuracy: see Performance gaps", "",
             ] + gaps_markdown(gaps) + ["## Gaps / attention", ""] + [f"- {g}" for g in m["gaps"]] + ["", "## By playbook", "", "| Playbook | Tasks | Completion | Gap | Validation |", "|---|---|---|---|---|"]
    for pb, v in m["by_playbook"].items():
        lines.append(f"| {pb} | {v['total']} | {fmt(v['completion'])} | {fmt(v['gap'])} | {fmt(v['validation'])} |")
    lines += ["", "## Execution modes", ""] + [f"- {k}: {v}" for k, v in sorted(m["exec_modes"].items())]
    lines += ["", "## Harness versions", ""] + [f"- {k}: {v}" for k, v in sorted(m["versions"].items())]
    lines += ["", "## Tools (top)", ""] + [f"- {k}: {v}" for k, v in m["tools"].items()]
    if tool_metrics and tool_metrics["total"]:
        lines += ["", "## Tool call reliability (per call)", "",
                   f"- Executed tool calls observed in this period: {tool_metrics['total']}",
                   f"- Overall success rate: {fmt(tool_metrics['success'])}"]
        if tool_metrics.get("interrupted"):
            lines.append(f"- Interrupted before finishing (not a tool failure, excluded from the success rate): {tool_metrics['interrupted']}")
        lines += ["", "| Tool | Category | Calls | Success rate |", "|---|---|---|---|"]
        for row in tool_metrics["by_tool"]:
            lines.append(f"| {row['tool']} | {row['category']} | {row['n']} | {fmt(row['rate'])} |")
        lines += ["", "_Per-call data (PostToolUse/PostToolUseFailure): which tools and MCP servers are actually used, and whether each call succeeded — tool name, category, success/failure and timestamp only, never command, prompt, response or tool-input/output content. Only calls that finished or failed are counted: calls denied by permissions or rejected before execution fire neither hook, and a tool cancelled mid-run fires no failure event, so none of them appear here. Not broken down by profile/playbook/version/environment (a single tool call carries none of those) and not part of the filterable dashboard above._", ""]
    if ctx_bands and not (ctx_bands["recorded"] + ctx_bands["joined"]):
        # no table without data: an empty table would read as rates, and band labels contain "0%"
        lines += ["", "## Outcome by context fill at task end", "",
                  f"- No task in this period has a context reading ({ctx_bands['unmatched']} not placed)."]
    elif ctx_bands:
        lines += ["", "## Outcome by context fill at task end", "",
                  f"- Tasks placed in a band: {ctx_bands['recorded'] + ctx_bands['joined']} ({ctx_bands['recorded']} recorded by the hook, {ctx_bands['joined']} matched from statusLine records); not placed: {ctx_bands['unmatched']}",
                  "", "| Context fill | Tasks | Completion | Complete + test-shaped command | Gap rate |", "|---|---|---|---|---|"]
        for b in ctx_bands["bands"]:
            low = " (low data)" if b["low_n"] and b["n"] else ""
            lines.append(f"| {b['band']}{low} | {b['n']} | {fmt(b['completion'])} | {fmt(b['verified_outcome'])} | {fmt(b['gap'])} |")
        lines += ["", f"_{CTX_NOTE}_"]
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
table.ctx{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}table.ctx th,table.ctx td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}table.ctx th{color:var(--muted);font-weight:600;font-size:12px}.note{color:var(--muted);font-size:12px;margin:6px 0}.low{color:var(--bad);font-size:11px}.tw{overflow-x:auto}table.gaps-t{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}table.gaps-t th,table.gaps-t td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}table.gaps-t th{color:var(--muted);font-weight:600;font-size:12px}.gaps-t .ans{white-space:nowrap;font-weight:600}.gq-insufficient .ans,.gq-not_collected .ans,.gq-opt_in .ans{color:var(--muted);font-weight:400}
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
 $("#cards").innerHTML=[card("Total tasks",null,null,`${s.known} with a known outcome`,String(s.total)),card("Completion",s.completion,t.completion),card("Complete + test-shaped command",s.verified_outcome,t.verified_outcome,s.verified_outcome?`${s.verified_outcome.num}/${s.verified_outcome.den} completed; broad match, see Performance gaps Q2 for results`:null),
  card("Gap rate",s.gap,t.gap),card("Validation pass",s.validation,t.validation),card("Evidence coverage",s.evidence,t.evidence),card("Metadata compliance",s.compliance,t.compliance),
  card("Rework and accuracy",null,null,"see Performance gaps below")].join("");
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


def ctx_panel_html(cb) -> str:
    """Static table (computed in Python, not by the page filters): no identifiers, counts and rates only."""
    if not cb:
        return ""
    placed = cb["recorded"] + cb["joined"]
    if not placed:
        return (f'<div class="panel wide" id="ctx-bands"><h2>Outcome by context fill at task end</h2>'
                f'<p class="note">No task in this period has a context reading ({cb["unmatched"]} not placed).</p></div>')
    cell = lambda r: html.escape(fmt(r))
    low = ' <span class="low">low data</span>'
    rows = "".join(
        f"<tr><td>{html.escape(b['band'])}{low if b['low_n'] and b['n'] else ''}</td>"
        f"<td>{b['n']}</td><td>{cell(b['completion'])}</td><td>{cell(b['verified_outcome'])}</td><td>{cell(b['gap'])}</td></tr>"
        for b in cb["bands"])
    return (f'<div class="panel wide" id="ctx-bands"><h2>Outcome by context fill at task end</h2>'
            f'<p class="note">Selected period only; not changed by the filters above. {placed} task(s) placed in a band, {cb["unmatched"]} without a context reading.</p>'
            f'<table class="ctx"><thead><tr><th>Context fill</th><th>Tasks</th><th>Completion</th><th>Complete + test-shaped command</th><th>Gap rate</th></tr></thead>'
            f'<tbody>{rows}</tbody></table><p class="note">{html.escape(CTX_NOTE)}</p></div>')


def render_html(buckets: list, meta: dict, ctx_bands: dict = None, gaps: list = None) -> str:
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
{gaps_panel_html(gaps)}
<div class="panel wide"><h2>Harness health trend (weekly)</h2><div id="trend"></div><div class="legend"><span><i style="background:#2b6cb0"></i>completion</span><span><i style="background:#c9463d"></i>gap rate</span><span><i style="background:#2f8f5b"></i>validation pass</span><span><i style="background:#7c5cbf"></i>evidence coverage</span></div></div>
<div class="panel"><h2>Playbook usage</h2><div id="playbooks"></div></div>
<div class="panel"><h2>Gap rate by playbook</h2><div id="gaps-pb"></div></div>
<div class="panel"><h2>Execution mode</h2><div id="exec"></div></div>
<div class="panel"><h2>Validation state (declared)</h2><div id="validation"></div></div>
<div class="panel"><h2>Tool / MCP usage (observed)</h2><div id="tools"></div></div>
<div class="panel"><h2>Harness version</h2><div id="versions"></div></div>
<div class="panel wide"><h2>Gaps / attention</h2><ul class="gaps" id="gaps"></ul></div>
{ctx_panel_html(ctx_bands)}
</div>
</main>
<footer>
<p><b>Definitions.</b> Completion = declared outcome <i>complete</i> ÷ tasks with a known outcome. Gap rate = partial + blocked + failed ÷ known outcomes. Complete + test-shaped command = completed tasks in which a test-shaped command or a deploy was seen ÷ completed tasks (a broad match that ignores the result; Performance gaps Q2 shows real test results). Validation pass = declared <i>verified</i> ÷ tasks with a known validation state. Evidence coverage = tasks declaring at least one evidence source ÷ tasks with a metadata block. Metadata compliance = tasks with a metadata block ÷ all tool-using tasks. Performance gaps are defined in their own panel. Metrics with too few cases or no data source show N/A rather than 0%.</p>
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
    tool_ev = Path(os.path.expanduser(args.tool_events)) if args.tool_events else tool_events_path()
    out = Path(os.path.expanduser(args.out)) if args.out else reports_dir()
    records, stats = load_events(ev)
    buckets, granularity = aggregate(records)
    tool_records, tool_stats = load_tool_events(tool_ev)
    tool_metrics = aggregate_tool_calls(tool_records, window, ref)
    ctx_bands = context_bands(records, load_usage(usage_path()), window, ref)
    rows, signals, ledger = load_tool_rows(tool_ev), load_signals(signals_path()), load_ledger()
    ci = None
    if getattr(args, "github", False):  # opt-in (design D8): without the flag no subprocess runs
        try:
            turns, _, _ = build_turns(records, rows, signals)
            start = ref - dt.timedelta(days=window) if window else None
            ci = fetch_ci(commit_turns([t for t in turns if start is None or start < dt.date.fromisoformat(t["day"]) <= ref]))
        except Exception as exc:
            ci = {"_unavailable": f"CI check failed ({type(exc).__name__})"}
    try:
        gaps = performance_gaps(records, rows, signals, ledger, window, ref, ci)
    except Exception as exc:  # one bad record must not take the whole dashboard down
        gaps = {"questions": [], "head": [f"Performance gaps unavailable ({type(exc).__name__})"]}
    meta = {"generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "ref": ref.isoformat(), "window_days": window,
            "events": str(ev), "stats": stats, "granularity": granularity}
    metrics = compute(buckets, window, ref)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    page = render_html(buckets, meta, ctx_bands, gaps)
    md = render_markdown(metrics, meta, tool_metrics, ctx_bands, gaps)
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
    return {"written": written, "records": len(records), "buckets": len(buckets), "stats": stats, "summary": metrics["summary"],
            "tool_calls": tool_metrics["total"], "tool_stats": tool_stats,
            "ctx_placed": ctx_bands["recorded"] + ctx_bands["joined"]}


# ---------------------------------------------------------------- schedule (macOS launchd)
def launch_agents_dir() -> Path:
    return Path(os.path.expanduser(os.environ.get("GROUNDWORK_LAUNCH_AGENTS_DIR") or "~/Library/LaunchAgents"))


def plist_path() -> Path:
    return launch_agents_dir() / f"{LABEL}.plist"


def calendar(freq: str, hour: int) -> dict:
    return {"daily": {"Hour": hour, "Minute": 0}, "weekly": {"Weekday": 1, "Hour": hour, "Minute": 0},
            "monthly": {"Day": 1, "Hour": hour, "Minute": 0}, "yearly": {"Month": 1, "Day": 1, "Hour": hour, "Minute": 0}}[freq]


def is_macos() -> bool:
    override = os.environ.get("GROUNDWORK_OS")  # test/CI override, mirrors setup.sh's own OS_KIND pattern
    if override:
        return override.strip().lower() == "darwin"
    return sys.platform == "darwin"


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
    if not is_macos():  # scheduling uses launchd; elsewhere the config is kept and generation stays manual
        return {"schedule": freq, "plist": None, "note": "launchd is macOS-only: run 'generate --snapshot' manually or from cron"}
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
    # The interpreter that scheduled the job, not `env python3`: launchd's PATH puts /usr/bin
    # first, which on macOS is Apple's Python 3.9 (below the 3.10 minimum).
    plist = {"Label": LABEL, "ProgramArguments": [sys.executable, str(Path(__file__).resolve()), "generate", "--snapshot"],
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
    return {"config": cfg, "launchd": is_macos(), "plist_present": p.exists(), "plist": str(p), "events": str(events_path()),
            "reports_dir": str(reports_dir()), "dashboard_present": (reports_dir() / "dashboard.html").exists()}


# ---------------------------------------------------------------- cli
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="groundwork-report", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("generate", help="write dashboard.html (and dated snapshots with --snapshot)")
    g.add_argument("--window", type=int, help="health window in days (default from report.json, 30)")
    g.add_argument("--snapshot", action="store_true", help="also write YYYY-MM-DD.html and YYYY-MM-DD.md")
    g.add_argument("--events", help="telemetry file (default ~/.claude/groundwork/telemetry/events.jsonl)")
    g.add_argument("--tool-events", help="per-tool-call telemetry file (default ~/.claude/groundwork/telemetry/tool_events.jsonl)")
    g.add_argument("--out", help="output directory (default ~/.claude/groundwork/reports)")
    g.add_argument("--now", help="reference date YYYY-MM-DD (default today)")
    g.add_argument("--github", action="store_true", help="opt-in: check CI of recorded commits with your gh login (read-only)")
    s = sub.add_parser("schedule", help="set the launchd schedule")
    s.add_argument("frequency", choices=FREQS)
    s.add_argument("--hour", type=int, help="hour of day, 0-23 (default 8)")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    if args.cmd == "generate":
        res = generate(args)
        for w in res["written"]:
            print(w)
        # tool-call line first: setup.sh shows `generate | tail -1`, which must stay the records= summary line
        print(f"tool_calls={res['tool_calls']} tool_lines={res['tool_stats']['lines']} tool_skipped={res['tool_stats']['malformed']}")
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
