#!/usr/bin/env python3
"""Evidence receipt — what a turn actually inspected or ran, and the highest evidence confidence
that supports. Derived deterministically from the session transcript, never from the model's tone.

Used two ways:
  * imported by groundwork_telemetry.py (Stop hook), which records only the confidence label and
    counts/booleans — never a path, URL or command (the telemetry privacy rule is unchanged);
  * run as `groundwork evidence` (forwarded here by the groundwork CLI), which prints the full
    receipt — the references — on demand for the user. Nothing here is persisted.

Why the transcript: every tool_use block has a matching tool_result carrying a boolean `is_error`
(keyed by tool_use_id), so "what was read, fetched, run, and whether it worked" is already recorded
by Claude Code itself. The hook-event route (PostToolUse) cannot supply it: those events are not
fired for calls denied or cancelled, and persisting tool inputs there would breach telemetry privacy.

Three things stay separate, as docs/FUTURE-SCOPE.md §14 requires:
  validation state      did the required activities happen (declared in Harness metadata)
  evidence confidence   how strong and complete the observed evidence is (this module)
  references            where the user can inspect that evidence (this module, on demand)

The confidence label is a CEILING built only from signals this module recognises. An unrecognised
command or tool contributes nothing, so the label can be too low, never too high. It is not a
probability and is never produced by asking the model how sure it is.

  NONE    nothing was inspected or run this turn
  LOW     files/repo were read, or a check failed, or files were edited and nothing verified them
  MEDIUM  something verified: tests passed, or a runtime observation succeeded, or an external
          source was fetched — and no failing check or review finding contradicts it
  HIGH    tests passed AND a runtime observation succeeded AND the latest independent review
          reported zero MUST FIX AND the repo or an external source was inspected
  UNKNOWN the transcript could not be read (never upgraded to a label)

Limits, stated rather than hidden: "external source" means a fetch succeeded — authority cannot be
computed, so the receipt lists the host for the user to judge; a review counts only when its
tool_result carries a parseable REVIEW RESULT block (a background agent's report arrives as a later
message, not a tool_result, so it is not credited); a forged block inside a subagent's text would be
credited, the same residual the review gate documents; a Bash command is credited only when it parses
unambiguously (no heredoc, substitution, background job or unbalanced quote) and its exit status can speak for
the test or runtime segment (all `&&`, the last segment, or `set -o pipefail`); a test piped only through
`tail`/`head`/`tee`/`cat`/`wc` is judged by the runner's own `N passed` / `N failed` summary instead.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from groundwork_shared import TEST_CMD  # same test-command pattern the other hooks use
except Exception:
    TEST_CMD = re.compile(r"(?!x)x")  # fail-open: no test detection rather than a crash

LABELS = ("NONE", "LOW", "MEDIUM", "HIGH")
RANK = {name: i for i, name in enumerate(LABELS)}
MAX_REFS = 60
REF_CAP = 140

READ_TOOLS = {"Read", "Grep", "Glob", "LS", "NotebookRead"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_VERB = re.compile(r"(?:^|_)(?:get|list|read|search|query|describe|fetch|show|view)(?:_|$)")

_PREFIX = re.compile(r"(?:\w+=\S*\s+)*(?:python3?\s+-m\s+|uv\s+run\s+|poetry\s+run\s+|npx\s+)?")
_REPO_CMD = re.compile(
    r"(?:cat|head|tail|less|sed\s+-n|grep|rg|ag|find|ls|tree|wc|"
    r"git\s+(?:log|show|diff|status|blame|ls-files|rev-parse|branch|remote))\b")
# A deliberately conservative list: a command not matched here is simply not counted as runtime.
_RUNTIME_CMD = re.compile(
    r"(?:kubectl\s+(?:get|describe|logs|top|rollout\s+status)|helm\s+(?:status|list|get)|"
    r"gcloud\s+(?:\S+\s+)*?(?:describe|list)|aws\s+\S+\s+(?:describe|list|get)\S*|"
    r"az\s+(?:\S+\s+)*?(?:show|list)|docker\s+(?:ps|logs|inspect|stats)|systemctl\s+status|"
    r"journalctl|curl|wget|claude\s+(?:-p|--print)|groundwork\s+(?:doctor|integrations|routines)|"
    r"gh\s+(?:api|run\s+(?:view|list)|pr\s+(?:view|checks)))\b")
_SECRET = re.compile(
    r"(?i)(authorization:\s*\S+(?:\s+\S+)?|bearer\s+\S+|(?:token|password|passwd|secret|api[_-]?key)\s*[=:]\s*\S+|"
    r"gh[pousr]_\w{10,}|sk-[A-Za-z0-9_-]{10,}|AKIA[0-9A-Z]{12,})")
_PIPEFAIL = re.compile(r"set\s+-[a-z]*o\s+pipefail\b")
_FILTERS = {"tail", "head", "tee", "cat", "wc"}  # pass-through filters commonly appended to a test run
_FAIL_COUNT = re.compile(r"\b[1-9]\d*\s+(?:failed|errors?)\b")
_PASS_COUNT = re.compile(r"\b[1-9]\d*\s+passed\b")
PRIORITY = {"review": 0, "test": 1, "runtime": 2, "repo": 3, "url": 4, "mcp": 5, "file": 6, "command": 7}
COLLECT_CAP = 5000  # bound memory on a huge turn; the shown list is cut to MAX_REFS by priority
_MUST_FIX = re.compile(r"Must-fix:\s*(\d+)", re.IGNORECASE)
_VERDICT = re.compile(r"Verdict:\s*(approve|changes-required)", re.IGNORECASE)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
    return ""


def _clip(s: str, n: int = REF_CAP) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _redact(s: str) -> str:
    return _SECRET.sub("[redacted]", s)


def _split(command: str):
    """(segments, connectors) or None when the command cannot be split unambiguously.

    Quotes and backslash escapes are respected. Heredocs, command substitution, process substitution,
    unbalanced quotes and background jobs return None: nothing is credited from a command this module
    cannot read with certainty, because a wrong split could credit a test that never ran."""
    text = command.strip()
    if not text or any(t in text for t in ("<<", "`", "$(", "<(", ">(")):
        return None
    pieces, cur, quote, i = [], [], None, 0

    def flush(conn):
        seg = "".join(cur).strip()
        cur.clear()
        if seg:
            pieces.append([seg, conn])
            return True
        return conn in (";", "\n")  # an empty piece is only harmless before ; or a newline

    while i < len(text):
        c = text[i]
        if quote:
            cur.append(c)
            if c == "\\" and quote == '"' and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < len(text):
            cur.append(text[i:i + 2])
            i += 2
            continue
        if c in "'\"":
            quote = c
            cur.append(c)
            i += 1
            continue
        two = text[i:i + 2]
        if two in ("&&", "||"):
            if not flush(two):
                return None
            i += 2
            continue
        if c in ";|\n":
            if not flush(c):
                return None
            i += 1
            continue
        if c == "&":
            prev, nxt = (text[i - 1] if i else ""), (text[i + 1] if i + 1 < len(text) else "")
            if prev in "<>" or nxt == ">":  # 2>&1, &>file: a redirection, not a connector
                cur.append(c)
                i += 1
                continue
            return None  # a background job has no exit status to credit
        cur.append(c)
        i += 1
    if quote:
        return None
    last = "".join(cur).strip()
    if last:
        pieces.append([last, None])
    elif pieces:
        pieces[-1][1] = None  # a trailing ; or newline
    if not pieces:
        return None
    return [p[0] for p in pieces], [p[1] for p in pieces[:-1]]


def _runner_verdict(text: str):
    """True/False from a test runner's own summary line, else None. Used only when a recognised test
    command's output went through a pass-through filter such as `| tail`, whose exit status says nothing."""
    if _FAIL_COUNT.search(text) or "FAILED" in text:
        return False
    return True if _PASS_COUNT.search(text) else None


def _outcome(i: int, segs: list, conns: list, pipefail: bool, is_error: bool, text: str):
    """Did segment i succeed? True/False when the command's exit status (or the runner's own summary)
    speaks for it, None when it cannot be attributed."""
    if "||" in conns:
        return None
    after = conns[i:]
    if all(c == "&&" or (pipefail and c == "|") for c in after):
        return not is_error
    if (not is_error and all(c == "|" for c in after)
            and all(segs[j].split()[0] in _FILTERS for j in range(i + 1, len(segs)))):
        return _runner_verdict(text)
    return None


def _starts(pattern, segment: str) -> bool:
    return pattern.match(segment, _PREFIX.match(segment).end()) is not None


def _blocked_by_policy(text: str) -> bool:
    """A PreToolUse hook (e.g. a fact-forcing gate) refused the call: it never ran, so it is not evidence."""
    return text.startswith("PreToolUse:") and "hook error" in text[:120]


def _gh_ref(name: str, inp: dict) -> str:
    owner, repo = inp.get("owner"), inp.get("repo")
    base = f"{owner}/{repo}" if owner and repo else "github"
    for key in ("pullNumber", "issue_number", "number"):
        if inp.get(key) is not None:
            return f"{base}#{inp[key]}"
    for key in ("sha", "ref", "path"):
        if inp.get(key):
            return f"{base}:{inp[key]}"
    return f"{base} ({name.split('__')[-1]})"


def _url_ref(url: str) -> str:
    p = urlsplit(str(url))  # drop query and fragment: they can carry tokens
    return f"{p.scheme}://{p.netloc}{p.path}" if p.netloc else _clip(url, 60)


def derive_evidence(entries: list) -> dict:
    """entries: the transcript entries of one turn. Returns {confidence, signals, references, reasons}."""
    uses = {}      # tool_use_id -> (name, input)
    order = []     # tool_use_ids in call order
    results = {}   # tool_use_id -> (is_error, text)
    for e in entries:
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and b.get("id"):
                uses[b["id"]] = (str(b.get("name", "")), b.get("input") if isinstance(b.get("input"), dict) else {})
                order.append(b["id"])
            elif b.get("type") == "tool_result" and b.get("tool_use_id"):
                results[b["tool_use_id"]] = (bool(b.get("is_error")), _text(b.get("content")))

    refs = []
    sig = {"repo_inspected": False, "external_source": False, "searches": 0, "tests_ran": 0,
           "tests_last_ok": None, "runtime_observed": False, "review": "none", "edits": 0, "tool_errors": 0}
    edited = set()

    def add(kind, ref, ok=None):
        if len(refs) < COLLECT_CAP:
            item = {"kind": kind, "ref": _clip(ref)}
            if ok is not None:
                item["ok"] = ok
            refs.append(item)

    for uid in order:
        name, inp = uses[uid]
        if uid not in results:
            continue  # still running, or never answered: no outcome, no evidence
        is_error, text = results[uid]
        if _blocked_by_policy(text):
            continue
        if is_error:
            sig["tool_errors"] += 1
        if name in EDIT_TOOLS:
            fp = str(inp.get("file_path") or inp.get("notebook_path") or "")
            if fp and not is_error:
                edited.add(fp)
        elif name in READ_TOOLS:
            if not is_error:
                sig["repo_inspected"] = True
                add("file", inp.get("file_path") or inp.get("path") or inp.get("pattern") or name)
        elif name == "WebFetch":
            if not is_error:
                sig["external_source"] = True
                add("url", _url_ref(inp.get("url", "")))
        elif name == "WebSearch":
            sig["searches"] += 1  # search snippets are not an inspected source
        elif name in ("Agent", "Task"):
            kind = f"{inp.get('subagent_type', '')} {inp.get('name', '')}".lower()
            if "review" in kind and not is_error:
                mf, vd = _MUST_FIX.search(text), _VERDICT.search(text)
                label = str(inp.get("subagent_type") or inp.get("name") or "agent")
                if mf and vd:
                    clean = int(mf.group(1)) == 0 and vd.group(1).lower() == "approve"
                    sig["review"] = "clean" if clean else "findings"
                    add("review", f"{label} → {vd.group(1).lower()}, must-fix {mf.group(1)}", clean)
                else:
                    sig["review"] = "unparsed"
                    add("review", f"{label} → no REVIEW RESULT block in its result", False)
        elif name.startswith("mcp__"):
            parts = name.split("__")
            server, tool = parts[1] if len(parts) > 1 else "?", parts[-1]
            if not is_error and READ_VERB.search(tool):
                if server == "github":
                    sig["repo_inspected"] = True
                    add("repo", _gh_ref(name, inp))
                else:
                    sig["external_source"] = True
                    add("mcp", f"{server}/{tool}")
        elif name == "Bash":
            parsed = _split(str(inp.get("command") or ""))
            if parsed is None:
                continue  # ambiguous command: nothing is credited
            segs, conns = parsed
            pipefail = bool(_PIPEFAIL.match(segs[0]))
            for i, segment in enumerate(segs):
                if _starts(TEST_CMD, segment):
                    ok = _outcome(i, segs, conns, pipefail, is_error, text)
                    if ok is not None:
                        sig["tests_ran"] += 1
                        sig["tests_last_ok"] = ok
                        add("test", _redact(_clip(segment, 100)), ok)
                elif _starts(_RUNTIME_CMD, segment):
                    if _outcome(i, segs, conns, pipefail, is_error, text) is True:
                        sig["runtime_observed"] = True
                        add("runtime", _redact(_clip(segment, 100)), True)
                elif i == 0 and _starts(_REPO_CMD, segment) and not is_error:
                    sig["repo_inspected"] = True  # only the command itself, not a filter later in a pipeline
                    add("command", _redact(_clip(segment, 100)))
    sig["edits"] = len(edited)
    label, reasons = _confidence(sig)
    seen, unique = set(), []
    for r in refs:
        key = (r["kind"], r["ref"], r.get("ok"))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda r: PRIORITY.get(r["kind"], 9))  # stable: the strongest kinds survive the cut
    return {"confidence": label, "signals": sig, "references": unique[:MAX_REFS],
            "references_omitted": max(0, len(unique) - MAX_REFS), "reasons": reasons}


def _confidence(sig: dict):
    """(label, reasons) — the rule documented in the module docstring, in one place."""
    inspected = (sig["repo_inspected"] or sig["external_source"] or sig["tests_ran"]
                 or sig["runtime_observed"] or sig["review"] != "none")
    if not inspected:
        return "NONE", ["nothing was inspected or run this turn"]
    verified = sig["tests_last_ok"] is True or sig["runtime_observed"]
    reasons, capped = [], False
    if sig["tests_last_ok"] is False:
        capped = True
        reasons.append("the last recognised test run failed")
    if sig["review"] == "findings":
        capped = True
        reasons.append("the latest independent review reported MUST FIX findings")
    if sig["edits"] and not verified:
        capped = True
        reasons.append(f"{sig['edits']} file(s) edited and no passing test or runtime observation verifies them")
    if capped:
        return "LOW", reasons
    if sig["tests_last_ok"] is True and sig["runtime_observed"] and sig["review"] == "clean" \
            and (sig["repo_inspected"] or sig["external_source"]):
        return "HIGH", ["tests passed, a runtime observation succeeded, and the latest review reported zero MUST FIX"]
    if verified or sig["external_source"]:
        if sig["tests_last_ok"] is not True:
            reasons.append("no passing test run recognised")
        if not sig["runtime_observed"]:
            reasons.append("no runtime observation recognised")
        if sig["review"] != "clean":
            reasons.append("no independent review with a parsed REVIEW RESULT of zero MUST FIX")
        return "MEDIUM", reasons
    return "LOW", ["only files or the repository were read; nothing verified, fetched or ran"]


# ------------------------------------------------------------------ hook-facing summary
def telemetry_summary(entries: list) -> dict:
    """What the Stop hook may persist: the label and counts/booleans. No path, URL or command."""
    ev = derive_evidence(entries)
    s = ev["signals"]
    return {"confidence": ev["confidence"],
            "signals": {"repo_inspected": s["repo_inspected"], "external_source": s["external_source"],
                        "tests_ran": s["tests_ran"], "tests_last_ok": s["tests_last_ok"],
                        "runtime_observed": s["runtime_observed"], "review": s["review"],
                        "edits": s["edits"], "tool_errors": s["tool_errors"]}}


def declared_exceeds(declared: str, observed: str):
    """True/False when both are known labels, else None — the model's stated label vs the ceiling."""
    d, o = (declared or "").strip().upper(), (observed or "").strip().upper()
    if d in RANK and o in RANK:
        return RANK[d] > RANK[o]
    return None


# ------------------------------------------------------------------ CLI
def _default_transcript() -> Path | None:
    cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    projects = cfg / "projects"
    slug = re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
    for base in (projects / slug, projects):
        files = sorted(base.glob("*.jsonl") if base.name == slug else base.glob("*/*.jsonl"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return files[0]
    return None


def _last_assistant_text(entries: list) -> str:
    for e in reversed(entries):
        if e.get("type") == "assistant":
            t = _text((e.get("message") or {}).get("content"))
            if t.strip():
                return t
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="groundwork evidence",
        description="Print the evidence receipt for the last turn of a session: what was actually "
                    "inspected or run, and the evidence-confidence ceiling that supports. Read-only.")
    ap.add_argument("--transcript", help="transcript .jsonl to read (default: the newest for this directory)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    path = Path(args.transcript).expanduser() if args.transcript else _default_transcript()
    if path is None or not path.is_file():
        out = {"confidence": "UNKNOWN", "reasons": ["no readable transcript found"], "references": [], "transcript": None}
        print(json.dumps(out) if args.json else "Evidence confidence: UNKNOWN — no readable transcript found.")
        return 1
    try:
        from groundwork_telemetry import current_turn, parse_metadata  # lazy: telemetry imports this module
        entries = current_turn(str(path))
    except Exception:
        entries = []
    if not entries:
        out = {"confidence": "UNKNOWN", "reasons": ["the transcript could not be read"], "references": [], "transcript": str(path)}
        print(json.dumps(out) if args.json else f"Evidence confidence: UNKNOWN — could not read {path}.")
        return 1
    ev = derive_evidence(entries)
    declared = ""
    try:
        declared = parse_metadata(_last_assistant_text(entries)).get("confidence", "")
    except Exception:
        pass
    over = declared_exceeds(declared, ev["confidence"])
    ev.update({"transcript": str(path), "declared_confidence": declared or None, "declared_exceeds_observed": over})
    if args.json:
        print(json.dumps(ev, indent=2))
        return 0
    print(f"Evidence confidence (ceiling): {ev['confidence']}")
    for r in ev["reasons"]:
        print(f"  - {r}")
    if declared:
        verdict = "EXCEEDS what was observed" if over else "within the observed ceiling" if over is False else "not a recognised label"
        print(f"Declared in the last response: {declared} — {verdict}")
    s = ev["signals"]
    print(f"Signals: repo_inspected={s['repo_inspected']} external_source={s['external_source']} tests_ran={s['tests_ran']} "
          f"tests_last_ok={s['tests_last_ok']} runtime_observed={s['runtime_observed']} review={s['review']} "
          f"edits={s['edits']} tool_errors={s['tool_errors']}")
    omitted = ev.get("references_omitted", 0)
    print(f"References ({len(ev['references'])}{f' shown, {omitted} more omitted — strongest kinds first' if omitted else ''}, from {path.name}):")
    for r in ev["references"]:
        mark = "" if "ok" not in r else " [ok]" if r["ok"] else " [failed]"
        print(f"  {r['kind']:<8} {r['ref']}{mark}")
    print("Validation state is separate: this is evidence quality, not a statement that required checks were done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
