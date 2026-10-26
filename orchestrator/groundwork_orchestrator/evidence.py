"""Question Evidence Engine, M2 (design: openspec/changes/meta-harness-architecture/design.md §5).

Code decides; the worker only proposes claims. For each claim the engine checks, deterministically:
- **located**: the quote occurs verbatim (after whitespace normalisation) in the cited line range of a workspace file;
- **provenance**: repository commit, the file's git blob hash, whether it is dirty, and when it was checked;
- **fresh**: the file still has the same blob hash when the final status is assigned;
- **requirement policy**: a repository claim needs a located code/config source, and a vendor claim needs a located
  doc source for the API version the repository uses;
- **contradiction**: only when applicable, fresh evidence demonstrably states the opposite. A version mismatch, a
  stale source, or two sources that disagree leave the claim UNVERIFIED with a reason.

Not in M2: the independent support reviewer (M3), so no claim reaches SOURCE_SUPPORTED; and command probes, so no
claim reaches VERIFIED. A claim whose quote is located is UNVERIFIED with reason `not_reviewed`, which is shown to
the user as "quote located; support not reviewed". No numeric confidence is ever produced.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MIN_QUOTE = 8
DOC_SUFFIXES = (".md", ".rst", ".txt", ".adoc")
_VERSION = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b|\bv?\d+\.\d+\.\d+\b")
_NUMBER = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w.]?\d)|(?<![\w.])\d+(?:\.\d+)?(?![\w.]?\d)")
_DOC_VERSION = re.compile(r"\bversion\s+(\d{4}-\d{2}(?:-\d{2})?|v?\d+\.\d+(?:\.\d+)?)", re.I)

CLAIM_SCHEMA = {
    "type": "array",
    "description": "every factual statement the answer relies on, each with the exact source text that shows it",
    "items": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "the claim, one statement"},
            "domain": {"type": "string", "enum": ["repo_code", "repo_doc", "vendor_doc", "other"],
                       "description": "repo_code: what this repository's code or config does; repo_doc: what this "
                                      "repository's own docs (README, CHANGELOG, docs/) say; vendor_doc: what a "
                                      "vendor's documentation says; other: anything else"},
            "value": {"type": "string", "description": "the specific value the claim asserts (a number, version, "
                                                       "name), exactly as it appears in the source; omit if none"},
            "refs": {"type": "array", "items": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "workspace-relative path"},
                               "line_start": {"type": "integer"}, "line_end": {"type": "integer"},
                               "quote": {"type": "string", "description": "verbatim text from those lines"}},
                "required": ["path", "line_start", "line_end", "quote"]}},
        },
        "required": ["text", "domain", "refs"],
    },
}

STATUS_LABEL = {"CONTRADICTED": "contradicted", "VERIFIED": "verified", "SOURCE_SUPPORTED": "source-supported"}
REASON_LABEL = {
    "not_reviewed": "quote located; support not reviewed",
    "not_located": "quote not found at the cited lines",
    "no_refs": "no source cited",
    "stale": "source changed after it was quoted",
    "version_mismatch": "source is for a different API version than the one in use",
    "missing_required_source": "no source of the required kind",
    "value_not_in_quote": "the cited text does not show the stated value",
}


def _norm(text: str) -> str:
    return " ".join(str(text).split())


def _git(root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _blob(root: Path, rel: str) -> str | None:
    return _git(root, "hash-object", "--", rel)


def _is_doc(rel: str) -> bool:
    return rel.lower().endswith(DOC_SUFFIXES)


def _doc_version(path: Path) -> str | None:
    head = "\n".join(path.read_text(errors="replace").splitlines()[:5])
    m = _DOC_VERSION.search(head)
    return m.group(1) if m else None


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def _ver(v: str) -> str:
    return v.lower().removeprefix("v")


_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}")
# Words that qualify a value rather than name what it is; they do not identify a setting.
_QUALIFIERS = {"max", "maximum", "min", "minimum", "default", "limit", "the", "and", "for", "are", "its", "per",
               "set", "sets", "value", "env", "environ", "get", "int", "float", "str", "seconds", "secs"}
# A range or bound, not one exact value ("python_requires >=3.9", "3.9 or later", "at least 2").
_BOUND = re.compile(r">=|<=|~=|\^|[<>]\s*\d|\bat (least|most)\b|\bor (later|newer|higher|above|more)\b", re.I)


def _name_words(text: str) -> set[str]:
    """Name-like words of three or more letters, split on underscores and camel case, lowercased."""
    parts = re.split(r"[_\W\d]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text))
    return {w.lower() for part in parts for w in _WORD.findall(part)} - _QUALIFIERS


def _same_subject(claim_text: str, quote: str) -> bool:
    """The quote names nothing the claim does not: every name word of the quote also appears in the claim.
    "Maximum page size: 100." is about the claim "page size is 500"; "CONNECT_TIMEOUT = 10" is not about
    "the request timeout is 30", because the claim never says "connect"."""
    words = _name_words(quote)
    return bool(words) and words <= _name_words(claim_text)


def locate(ref: dict, root: Path) -> dict:
    """One ref → provenance plus `located` and, when it fails, `reason` and `detail`."""
    raw = str(ref.get("path") or "").strip()
    rel = raw[2:] if raw.startswith("./") else raw
    out = {"path": rel, "line_start": ref.get("line_start"), "line_end": ref.get("line_end"),
           "quote": str(ref.get("quote") or ""), "located": False, "reason": None,
           "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    p = (root / rel).resolve()
    if root not in p.parents or not p.is_file():
        return {**out, "reason": "not_located", "detail": "file is not inside the workspace"}
    lines = p.read_text(errors="replace").splitlines()
    try:
        start = int(ref.get("line_start"))
        end = int(ref.get("line_end") or start)
    except (TypeError, ValueError):
        return {**out, "reason": "not_located", "detail": "no valid line range"}
    if not 1 <= start <= end <= len(lines):
        return {**out, "reason": "not_located", "detail": f"lines {start}-{end} are outside 1-{len(lines)}"}
    quote = _norm(out["quote"])
    if len(quote) < MIN_QUOTE:
        return {**out, "reason": "not_located", "detail": f"quote is shorter than {MIN_QUOTE} characters"}
    if quote not in _norm(" ".join(lines[start - 1:end])):
        return {**out, "reason": "not_located", "detail": "quote is not in the cited lines"}
    rel = str(p.relative_to(root))
    return {**out, "path": rel, "located": True, "blob_sha": _blob(root, rel),
            "dirty": bool(_git(root, "status", "--porcelain", "--", rel)),
            "doc_version": _doc_version(p) if _is_doc(rel) else None}


def _pinned_versions(claims: list[dict]) -> set[str]:
    """API versions the repository itself states, from located quotes of code or config files."""
    return {v for c in claims for r in c["refs"] if r["located"] and not _is_doc(r["path"])
            for v in _VERSION.findall(r["quote"])}


def _value_check(text: str, value: str, refs: list[dict]) -> tuple[str | None, dict | None]:
    """(reason, contradiction). The value must appear in a located quote. A contradiction needs a located quote that is
    about the same subject (it shares a name-like word with the claim) and states exactly one value of the same kind,
    and that value differs. A quote about something else is a mis-citation (value_not_in_quote), never a
    contradiction."""
    v = _norm(value)
    if not v or not refs:
        return None, None
    if _VERSION.fullmatch(v):
        kind, want = "version", _ver(v)
        if any(want in {_ver(x) for x in _VERSION.findall(r["quote"])} or v.lower() in r["quote"].lower()
               for r in refs):
            return None, None
    elif _numbers(v) == {v.replace(",", "")}:
        kind, want = "number", v.replace(",", "")
        if any(want in _numbers(r["quote"]) for r in refs):
            return None, None
    else:
        return (None, None) if any(v.lower() in _norm(r["quote"]).lower() for r in refs) else ("value_not_in_quote", None)
    for r in refs:
        found = {_ver(x) for x in _VERSION.findall(r["quote"])} if kind == "version" else _numbers(r["quote"])
        if len(found) != 1 or _BOUND.search(r["quote"]) or not _same_subject(text, r["quote"]):
            continue
        other = next(iter(found))
        # A version that is only a shorter or longer form of the claim's (2024-06 vs 2024-06-01) is not opposite.
        if kind == "version" and (want.startswith(other) or other.startswith(want)):
            continue
        if other != want:
            return None, {"path": r["path"], "line_start": r["line_start"], "quote": r["quote"],
                          "states": other, "claim_value": v, "detected_by": "rule:value_differs"}
    return "value_not_in_quote", None


def assess(claims: list[dict] | None, workspace: str) -> dict:
    """Locate every ref and give each claim exactly one status, first match wins:
    CONTRADICTED → (VERIFIED: not in M2) → (SOURCE_SUPPORTED: not in M2, needs the reviewer) → UNVERIFIED(reason)."""
    root = Path(workspace).resolve()
    out = []
    for i, c in enumerate(claims or []):
        if not isinstance(c, dict):
            continue
        refs = [locate(r, root) for r in (c.get("refs") or []) if isinstance(r, dict)]
        out.append({"id": f"C{i + 1}", "text": str(c.get("text") or ""), "domain": c.get("domain") or "other",
                    "value": c.get("value"), "refs": refs, "material": True, "material_by": "default"})
    pinned = _pinned_versions(out)
    for c in out:
        located = [r for r in c["refs"] if r["located"]]
        reason, contradiction = None, None
        if not c["refs"]:
            reason = "no_refs"
        elif not located:
            reason = "not_located"
        if not reason and c["domain"] == "vendor_doc":
            docs = [r for r in located if _is_doc(r["path"])]
            for r in docs:
                r["applicable"] = not (len(pinned) == 1 and r.get("doc_version") and r["doc_version"] not in pinned)
            if not docs:
                reason = "missing_required_source"
            elif not any(r["applicable"] for r in docs):
                reason = "version_mismatch"
        if not reason and c["domain"] == "repo_code" and all(_is_doc(r["path"]) for r in located):
            reason = "missing_required_source"
        if not reason and c["domain"] == "repo_doc" and not any(_is_doc(r["path"]) for r in located):
            reason = "missing_required_source"
        if not reason and c.get("value"):
            # A vendor claim's value is checked against the applicable documentation only, never against code.
            usable = [r for r in located if r.get("applicable")] if c["domain"] == "vendor_doc" else located
            reason, contradiction = _value_check(c["text"], str(c["value"]), usable)
        c["contradictions"] = [contradiction] if contradiction else []
        c["status"], c["reason"] = ("CONTRADICTED", None) if contradiction else ("UNVERIFIED", reason or "not_reviewed")
    return {"repo_commit": _git(root, "rev-parse", "HEAD"), "pinned_versions": sorted(pinned), "claims": out}


def refresh(assessment: dict, workspace: str) -> dict:
    """Freshness: a located source whose blob hash changed since it was quoted makes its claim UNVERIFIED (stale)
    until it is revalidated. Run just before the final status is assigned."""
    root = Path(workspace).resolve()
    for c in assessment.get("claims") or []:
        for r in c["refs"]:
            if r.get("located") and r.get("blob_sha") and _blob(root, r["path"]) != r["blob_sha"]:
                r["stale"] = True
        if any(r.get("stale") for r in c["refs"]):
            c["status"], c["reason"], c["contradictions"] = "UNVERIFIED", "stale", []
    return assessment


def repair_needed(assessment: dict) -> list[dict]:
    """Claims a worker can fix: quote correctly, use the applicable source, or drop the claim."""
    return [c for c in assessment.get("claims") or [] if c["status"] == "CONTRADICTED" or c["reason"] != "not_reviewed"]


def repair_detail(assessment: dict) -> str:
    lines = []
    for c in repair_needed(assessment):
        if c["status"] == "CONTRADICTED":
            x = c["contradictions"][0]
            why = f"contradicted: {x['path']} line {x['line_start']} states {x['states']!r}, not {x['claim_value']!r}"
        else:
            why = REASON_LABEL.get(c["reason"], c["reason"])
        refs = "; ".join(f"{r['path']}:{r['line_start']}-{r['line_end']}"
                         + (f" ({r['detail']})" if r.get("detail") else "") for r in c["refs"]) or "no refs"
        lines.append(f"- {c['id']} \"{c['text']}\": {why}. Refs: {refs}")
    return ("These claims are not backed by the sources as cited. For each one, either cite the exact lines that show "
            "it (quote them verbatim, from the source for the API version this repository uses), or remove the claim "
            "from both `claims` and `answer` and list it in `unknowns`. Never keep a statement the sources do not "
            "show.\n" + "\n".join(lines))


def answer_status(assessment: dict) -> str:
    """Answer-level ladder (design §5.1 step 8, first match wins). VERIFIED and SOURCE_SUPPORTED cannot occur in M2."""
    claims = [c for c in assessment.get("claims") or [] if c["material"]]
    if any(c["status"] == "CONTRADICTED" for c in claims):
        return "CONTRADICTED"
    if not any(c["reason"] == "not_reviewed" for c in claims):
        return "UNVERIFIED"
    return "PARTIALLY_SUPPORTED"


def render(assessment: dict | None) -> str:
    """The evidence section shown to the user under the answer."""
    if not assessment:
        return ""
    claims = assessment.get("claims") or []
    status = assessment.get("answer_status") or answer_status(assessment)
    located = sum(1 for c in claims if c["reason"] == "not_reviewed")
    lines = [f"Evidence: {status} ({located} of {len(claims)} claims have a located quote; "
             "no independent support review in this version)"]
    for c in claims:
        label = STATUS_LABEL.get(c["status"]) or f"unverified: {REASON_LABEL.get(c['reason'], c['reason'])}"
        where = ", ".join(f"{r['path']}:{r['line_start']}" + (f"-{r['line_end']}" if r.get("line_end") not in
                                                                (None, r["line_start"]) else "")
                          for r in c["refs"]) or "no source"
        lines.append(f"- [{label}] {c['text']} ({where})")
    uncertain = [c for c in claims if c["status"] == "CONTRADICTED" or c["reason"] != "not_reviewed"]
    if uncertain:
        lines.append("Uncertain: " + "; ".join(f"{c['id']} {c['text']}" for c in uncertain))
    if not claims:
        lines.append("Uncertain: the answer makes no claim backed by a located source.")
    return "\n".join(lines)
