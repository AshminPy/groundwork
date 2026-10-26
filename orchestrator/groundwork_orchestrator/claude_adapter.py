"""Claude Code worker adapter: one `claude -p` subprocess per call, on the user's existing subscription login.

Subscription-only rules (https://code.claude.com/docs/en/headless, verified on Claude Code 2.1.310):
- never `--bare`: bare mode "never reads OAuth credentials or the system keychain" and needs ANTHROPIC_API_KEY;
- API-key / alternate-provider variables are removed from the worker environment, and `preflight()` refuses to run
  unless `claude auth status` reports a claude.ai login on the first-party provider;
- the prompt goes on stdin (never argv, which other local users can read); argv is a list, never a shell string;
- `--permission-prompts none`: anything that would prompt is denied and Claude is told not to retry it.
Hooks and settings in ~/.claude still load (no --bare), so Groundwork's own gates keep applying to workers.

A CLI process (pid, exit code) and a conversation session (session_id, resumable with --resume) are different
things: the caller picks the session id up front, so it is known even if this process dies mid-call.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

# Removed from every worker's environment: each would move the call off the subscription login.
BILLING_ENV_VARS = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY", "AWS_BEARER_TOKEN_BEDROCK", "ANTHROPIC_BASE_URL", "ANTHROPIC_FOUNDRY_API_KEY",
)
# Workers load only user-level settings and no MCP servers: without this a `-p` session runs the hooks in an
# untrusted repository's own .claude/settings.json (verified live on 2.1.310, 2026-10-25). The user's ~/.claude
# hooks, including Groundwork's gates, still run (seen live). UNVERIFIED: whether managed (organization) settings
# are affected — the CLI reference lists only user/project/local as sources.
# The file tools (Read, Grep, Glob) refuse paths outside the worker's working directory in every permission mode, so a
# worker cannot read ~/.ssh or files beside its workspace. `--settings` still applies under `--setting-sources user`
# (verified live by the M1 canary, 2026-10-25) and is passed on every call, because resume does not restore it.
# Path-scoped Glob deny rules are not used: Claude Code never matches them (permissions docs).
READ_FENCE = {"permissions": {"blockReadsOutsideWorkingDirectories": True}}
ISOLATION_FLAGS = ["--setting-sources", "user", "--strict-mcp-config", "--settings", json.dumps(READ_FENCE)]
TERM_GRACE_S = 10
POLL_S = 0.2


class Failure(str, Enum):
    AUTH = "auth"                 # not logged in / wrong auth method
    QUOTA = "quota"               # usage or rate limit: a controlled pause, never an API fallback
    MODEL = "model_unavailable"   # model alias not available on this plan
    PERMISSION = "permission"     # a needed tool call was denied
    MALFORMED = "malformed"       # stdout was not a result object, or the required structured output is missing
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROCESS = "process"           # non-zero exit or is_error without a more specific cause
    NOT_INSTALLED = "not_installed"

    @property
    def repairable(self) -> bool:
        """Only a bad answer can be helped by asking the worker again; everything else is the environment."""
        return self is Failure.MALFORMED


@dataclass
class WorkerRequest:
    prompt: str
    cwd: str
    model: str
    effort: str
    tools: list[str]                                          # the tools the session has at all (--tools)
    allowed_tools: list[str] = field(default_factory=list)   # auto-approved rules (--allowedTools)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resume: bool = False
    json_schema: dict | None = None
    max_turns: int | None = None
    timeout_s: int = 900
    append_system_prompt: str | None = None


@dataclass
class WorkerResult:
    ok: bool
    failure: Failure | None
    reason: str
    session_id: str
    exit_code: int | None
    duration_s: float
    result_text: str = ""
    structured: dict | None = None
    usage: dict = field(default_factory=dict)
    models: list[str] = field(default_factory=list)
    cost_estimate_usd: float | None = None   # Claude Code's client-side estimate, NOT a bill
    permission_denials: list = field(default_factory=list)
    stderr_tail: str = ""
    pid: int | None = None

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["failure"] = self.failure.value if self.failure else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WorkerResult":
        d = dict(d)
        d["failure"] = Failure(d["failure"]) if d.get("failure") else None
        return cls(**d)


# Categories from the documented `system/api_retry` error field, plus the phrases the CLI prints for them.
_QUOTA = re.compile(r"usage limit|rate[ _-]?limit|limit reached|quota|billing_error|out of (extra )?usage|\b429\b", re.I)
_AUTH = re.compile(r"not logged in|/login|authentication_failed|oauth_org_not_allowed|account_on_hold|invalid api key|"
                   r"unauthori[sz]ed|\b401\b", re.I)
_MODEL = re.compile(r"model_not_found|invalid model|model\b.{0,40}\b(not found|not available|unavailable)", re.I)


def classify_error(text: str) -> Failure:
    if _QUOTA.search(text):
        return Failure.QUOTA
    if _AUTH.search(text):
        return Failure.AUTH
    if _MODEL.search(text):
        return Failure.MODEL
    return Failure.PROCESS


def worker_env(base: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    for k in BILLING_ENV_VARS:
        env.pop(k, None)
    return env


def claude_bin() -> str | None:
    return shutil.which(os.environ.get("GROUNDWORK_CLAUDE_BIN", "claude"))


def preflight(timeout_s: int = 30) -> tuple[bool, str]:
    """(True, detail) only for a claude.ai (subscription) login on the first-party provider."""
    exe = claude_bin()
    if not exe:
        return False, "the 'claude' command is not on PATH"
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=timeout_s, env=worker_env())
        status = json.loads(r.stdout or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        return False, f"could not read 'claude auth status': {e}"
    if not isinstance(status, dict) or not status.get("loggedIn"):
        return False, "Claude Code is not logged in (run 'claude' and use /login yourself)"
    if status.get("authMethod") != "claude.ai" or status.get("apiProvider") != "firstParty":
        return False, (f"Claude Code reports authMethod={status.get('authMethod')!r}, apiProvider="
                       f"{status.get('apiProvider')!r}; workers only run on a claude.ai subscription login")
    return True, f"claude.ai login, subscription={status.get('subscriptionType')}"


def build_argv(req: WorkerRequest, exe: str) -> list[str]:
    argv = [exe, "-p", "--output-format", "json", "--permission-prompts", "none", *ISOLATION_FLAGS,
            "--model", req.model, "--effort", req.effort, "--tools", ",".join(req.tools)]
    if req.allowed_tools:
        argv += ["--allowedTools", ",".join(req.allowed_tools)]
    argv += ["--resume", req.session_id] if req.resume else ["--session-id", req.session_id]
    if req.json_schema is not None:
        argv += ["--json-schema", json.dumps(req.json_schema)]
    if req.max_turns:
        argv += ["--max-turns", str(req.max_turns)]
    if req.append_system_prompt:
        argv += ["--append-system-prompt", req.append_system_prompt]
    return argv


def terminate(proc: subprocess.Popen) -> None:
    """SIGTERM the worker's process group, then SIGKILL while any member of the group is left; always reap the
    leader, so no zombie keeps its pid (an unreaped leader also makes macOS answer EPERM for the whole group)."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            break
        deadline = time.monotonic() + TERM_GRACE_S
        gone = False
        while time.monotonic() < deadline:
            proc.poll()
            try:
                os.killpg(proc.pid, 0)
            except (ProcessLookupError, PermissionError):
                gone = True
                break
            time.sleep(0.1)
        if gone:
            break
    try:
        proc.wait(timeout=TERM_GRACE_S)
    except subprocess.TimeoutExpired:
        pass


def parse_output(stdout: str, req: WorkerRequest, exit_code: int | None, stderr: str, duration: float,
                 pid: int | None) -> WorkerResult:
    base = dict(session_id=req.session_id, exit_code=exit_code, duration_s=round(duration, 2),
                stderr_tail=(stderr or "")[-2000:], pid=pid)
    try:
        d = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        d = None
    if not isinstance(d, dict) or d.get("type") != "result":
        text = ((stderr or "") + " " + (stdout or "")).strip()
        failure = classify_error(text) if exit_code else Failure.MALFORMED
        return WorkerResult(ok=False, failure=failure, reason=(text.splitlines() or ["no output"])[0][:300], **base)
    common = dict(result_text=d.get("result") or "", structured=d.get("structured_output"),
                  usage=d.get("usage") or {}, models=sorted((d.get("modelUsage") or {}).keys()),
                  cost_estimate_usd=d.get("total_cost_usd"), permission_denials=d.get("permission_denials") or [])
    base["session_id"] = d.get("session_id") or req.session_id
    if d.get("is_error") or exit_code != 0 or d.get("subtype") != "success":
        text = " ".join(str(x) for x in (d.get("result"), d.get("subtype"), d.get("api_error_status"), stderr) if x)
        return WorkerResult(ok=False, failure=classify_error(text), reason=text[:300], **base, **common)
    if req.json_schema is not None and not isinstance(d.get("structured_output"), dict):
        failure = Failure.PERMISSION if common["permission_denials"] else Failure.MALFORMED
        return WorkerResult(ok=False, failure=failure, reason="the result has no structured_output", **base, **common)
    return WorkerResult(ok=True, failure=None, reason="success", **base, **common)


def run_worker(req: WorkerRequest, on_start: Callable[[int], None] | None = None,
               cancel: Callable[[], bool] | None = None) -> WorkerResult:
    """Run one worker call. Exit code 0 is necessary, never sufficient: callers still validate the outcome."""
    exe = claude_bin()
    if not exe:
        return WorkerResult(ok=False, failure=Failure.NOT_INSTALLED, reason="the 'claude' command is not on PATH",
                            session_id=req.session_id, exit_code=None, duration_s=0.0)
    start = time.monotonic()
    proc = subprocess.Popen(build_argv(req, exe), cwd=req.cwd, env=worker_env(), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace",
                            start_new_session=True)  # own process group: a timeout or cancel ends all of it

    def stopped(failure: Failure, reason: str) -> WorkerResult:
        terminate(proc)
        return WorkerResult(ok=False, failure=failure, reason=reason, session_id=req.session_id,
                            exit_code=proc.returncode, duration_s=round(time.monotonic() - start, 2), pid=proc.pid)

    try:
        if on_start:
            on_start(proc.pid)
        deadline = start + req.timeout_s
        pending_input: str | None = req.prompt  # sent once; later polls only collect output
        while True:
            try:
                out, err = proc.communicate(input=pending_input, timeout=POLL_S)
                break
            except subprocess.TimeoutExpired:
                pending_input = None
            if cancel and cancel():
                return stopped(Failure.CANCELLED, "cancelled by the owner")
            if time.monotonic() > deadline:
                return stopped(Failure.TIMEOUT, f"no result within {req.timeout_s}s")
    except BaseException:  # Ctrl-C or a crash in the orchestrator: never leave the worker running
        terminate(proc)
        raise
    return parse_output(out or "", req, proc.returncode, err or "", time.monotonic() - start, proc.pid)
