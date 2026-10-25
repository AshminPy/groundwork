"""Task contract, states and output schemas. No I/O here."""
from __future__ import annotations

from enum import Enum

CATEGORIES = ("QUESTION", "TROUBLESHOOTING", "PROJECT", "DOCUMENTATION")
RISKS = ("low", "medium", "high")
WORKFLOWS = {"QUESTION": "answer", "TROUBLESHOOTING": "investigate", "PROJECT": "implement",
             "DOCUMENTATION": "document"}
MAX_REPAIRS = 2


class State(str, Enum):
    CREATED = "CREATED"
    CLASSIFIED = "CLASSIFIED"
    PLANNED = "PLANNED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    REPAIRING = "REPAIRING"
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


FINAL_STATES = {State.PASSED, State.FAILED, State.CANCELLED}


class Evidence(str, Enum):
    VERIFIED = "VERIFIED"                      # declared checks ran and passed on the result
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"  # deterministic checks passed; the content itself is not machine-checked
    UNVERIFIED = "UNVERIFIED"                  # nothing could be checked
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "risk": {"type": "string", "enum": list(RISKS)},
        "reasoning": {"type": "string"},
    },
    "required": ["category", "risk", "reasoning"],
    "additionalProperties": False,
}


def validate_classification(obj) -> list[str]:
    """Errors in a model-produced classification; empty when valid. Checked here too, never trusted from the CLI."""
    if not isinstance(obj, dict):
        return ["classification is not an object"]
    errors = []
    if obj.get("category") not in CATEGORIES:
        errors.append(f"category {obj.get('category')!r} is not one of {', '.join(CATEGORIES)}")
    if obj.get("risk") not in RISKS:
        errors.append(f"risk {obj.get('risk')!r} is not one of {', '.join(RISKS)}")
    if not isinstance(obj.get("reasoning"), str) or not obj["reasoning"].strip():
        errors.append("reasoning is missing")
    extra = set(obj) - {"category", "risk", "reasoning"}
    if extra:
        errors.append(f"unexpected fields: {', '.join(sorted(extra))}")
    return errors


_LIST = {"type": "array", "items": {"type": "string"}}
_SOURCES = {"type": "array", "items": {"type": "string"},
            "description": "workspace-relative paths of files you actually read and relied on, optionally with :line"}

OUTPUT_SCHEMAS = {
    "answer": {
        "type": "object",
        "properties": {"answer": {"type": "string"}, "sources": _SOURCES, "unknowns": _LIST},
        "required": ["answer", "sources", "unknowns"],
    },
    "investigate": {
        "type": "object",
        "properties": {"summary": {"type": "string"}, "root_cause": {"type": "string"},
                       "confirmed": {"type": "boolean", "description": "true only if the evidence proves the cause"},
                       "evidence": _LIST, "sources": _SOURCES, "proposed_fix": {"type": "string"},
                       "files_changed": _LIST},
        "required": ["summary", "root_cause", "confirmed", "evidence", "sources", "proposed_fix"],
    },
    "plan": {
        "type": "object",
        "properties": {"steps": _LIST, "files_to_change": _LIST, "acceptance_criteria": _LIST, "risks": _LIST},
        "required": ["steps", "files_to_change", "acceptance_criteria", "risks"],
    },
    "implement": {
        "type": "object",
        "properties": {"summary": {"type": "string"}, "files_changed": _LIST, "notes": {"type": "string"}},
        "required": ["summary", "files_changed"],
    },
    "document": {
        "type": "object",
        "properties": {"document": {"type": "string", "description": "the documentation, in Markdown"},
                       "sources": _SOURCES, "unverified_claims": _LIST, "files_changed": _LIST},
        "required": ["document", "sources", "unverified_claims"],
    },
}


def new_contract(task_id: str, request: str, workspace: str, checks: list[str], allow_write: bool) -> dict:
    """The machine-readable task specification. Filled in as the workflow runs; stored as JSON."""
    return {
        "task_id": task_id, "request": request, "workspace": workspace, "checks": list(checks),
        "allow_write": bool(allow_write),
        "category": None, "risk": None, "classification": None, "workflow": None,
        "objective": request, "constraints": [], "required_evidence": [], "acceptance_criteria": [],
        "dependencies": [], "roles": [], "routing": {}, "needs_write": False,
        "approval": "not_required", "plan": None, "worktree": None, "session_id": None,
        "retry_count": 0, "symptoms": [], "validation": [], "result": None, "outcome": None,
        "evidence_status": None, "ledger_key": None,
    }
