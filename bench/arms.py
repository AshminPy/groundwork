"""The three benchmark arms, launched the same way apart from their Claude Code config dir and PATH prefix.

V = plain Claude Code, E = Claude Code + ECC v2.2.1 + OpenSpec 1.13.2, G = Groundwork 2.5.0 (its install.sh also
installs ECC, so G = E + Groundwork). Every arm gets the same model, effort, tools, settings, time limit and an
allow-listed environment: host credentials (GitHub, cloud, API keys) never reach an agent or its Bash commands.
Read-only cases keep the original ISOLATION_FLAGS byte for byte; write-capable cases add Claude Code's Bash sandbox
(no network, reads outside the run's own workspace denied, no unsandboxed retry).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from ._adapter import ISOLATION_FLAGS, READ_FENCE, claude_bin, terminate

BENCH = Path(__file__).resolve().parent
REPO_ROOT = BENCH.parent
ARMS = ("V", "E", "G")
READ_TOOLS = "Read,Grep,Glob"
WRITE_TOOLS = "Read,Grep,Glob,Edit,Write,Bash,Agent,Skill"
TIMEOUT_S = 1200   # the same wall-clock limit for every arm
# The only host variables an arm inherits: locale, temp dir, and the network proxy and CA bundle Claude Code itself
# needs to reach the API. Tokens such as GH_TOKEN or AWS_* are never passed. HOME is replaced by a per-arm home.
ENV_KEEP = ("USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ", "TMPDIR",
            "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy",
            "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE")
SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def bench_home() -> Path:
    return Path(os.path.expanduser(os.environ.get("GW_BENCH_HOME") or "~/gw-bench"))


def arm_dirs(arm: str) -> dict[str, Path]:
    """Each arm: its own CLAUDE_CONFIG_DIR, its own HOME, and its own bin/ (symlinks to claude, node, python3 and,
    for E and G, the arm's OpenSpec), which is the whole PATH prefix. V's PATH has no openspec. The separate HOME
    matters: ECC's hooks keep their data under $HOME/.claude and ~/.gateguard whatever CLAUDE_CONFIG_DIR says, and
    Groundwork's install.sh edits ~/.bashrc, ~/.zshrc and ~/.profile; with the owner's HOME, both would touch the
    owner's real files and E and G would share one ECC store."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    root = bench_home() / arm
    return {"root": root, "config": root / "config", "bin": root / "bin", "home": root / "home"}


def arm_env(arm: str) -> dict:
    env = {k: os.environ[k] for k in ENV_KEEP if k in os.environ}
    d = arm_dirs(arm)
    env["PATH"] = f"{d['bin']}:{SYSTEM_PATH}"
    env["CLAUDE_CONFIG_DIR"] = str(d["config"])
    home = d["home"]
    env.update({"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_CACHE_HOME": str(home / ".cache"), "ECC_AGENT_DATA_HOME": str(d["config"]),
                "GATEGUARD_STATE_DIR": str(home / ".gateguard"), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                # the sandbox hides HOME from Bash, so git takes its identity from the environment
                "GIT_CONFIG_GLOBAL": "/dev/null",   # macOS's sandbox answers EPERM on a denied ~/.gitconfig
                "GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@localhost",
                "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@localhost"})
    return env


OWNER_ROOTS = (".claude", ".gateguard", ".config/openspec", ".npm/_logs")
# The owner's own Claude Code sessions (including the one driving the benchmark) write transcripts and task lists
# here, and those name bench paths; they are not bench writes.
OWNER_SKIP = (".claude/projects", ".claude/tasks", ".claude/todos", ".claude/sessions", ".claude/shell-snapshots",
              ".claude/session-env", ".claude/file-history")
OWNER_RC = (".bashrc", ".bash_profile", ".zshrc", ".zprofile", ".profile")


def owner_rc_hashes() -> dict:
    import hashlib
    h = Path.home()
    return {n: hashlib.sha256((h / n).read_bytes()).hexdigest() for n in OWNER_RC if (h / n).is_file()}


def owner_touched(since: float, markers: list[str]) -> list[str]:
    """Files under the owner's real ~/.claude, ~/.gateguard and ~/.config/openspec changed since `since` whose content
    names a bench path (a run workspace, the canary root or the bench home). Content-based, so the owner's own Claude
    sessions running at the same time are not counted."""
    hits = []
    for r in OWNER_ROOTS:
        root = Path.home() / r
        if not root.exists():
            continue
        skip = [Path.home() / s for s in OWNER_SKIP]
        for p in root.rglob("*"):
            if any(p == s or s in p.parents for s in skip):
                continue
            try:
                if not p.is_file() or p.stat().st_mtime < since or p.stat().st_size > 2_000_000:
                    continue
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            if any(m and m in text for m in markers):
                hits.append(str(p))
    return sorted(hits)


def scrub_runner_env() -> None:
    """Drop host credentials from the runner itself, so no child (agent, hook, sandboxed Bash via /proc) can find them
    in an ancestor's environment."""
    keep = set(ENV_KEEP) | {"HOME", "PATH", "GW_BENCH_HOME", "GW_BENCH_STUB"}
    for k in list(os.environ):
        if k not in keep:
            del os.environ[k]


def make_home(arm: str) -> None:
    """Create the arm's HOME with a bench git identity, so commits work the same way in every arm."""
    home = arm_dirs(arm)["home"]
    home.mkdir(parents=True, exist_ok=True)
    gitconfig = home / ".gitconfig"
    if not gitconfig.exists():
        gitconfig.write_text("[user]\n\tname = bench\n\temail = bench@localhost\n[init]\n\tdefaultBranch = main\n")


def arm_claude(arm: str) -> str:
    if os.environ.get("GW_BENCH_STUB"):   # dry runs: a stub CLI that prints a canned stream
        return os.environ["GW_BENCH_STUB"]
    exe = arm_dirs(arm)["bin"] / "claude"
    return str(exe) if exe.exists() else (claude_bin() or "claude")


def write_settings(ws: Path, deny_read: list[str]) -> dict:
    """Read fence for the file tools plus the Bash sandbox. Key names verified against
    code.claude.com/docs/en/sandboxing on 2026-10-28; the canary proves the effect on each arm before any case."""
    ws_s = str(ws.resolve())
    return {
        "permissions": {**READ_FENCE["permissions"], "deny": ["WebFetch", "WebSearch"]},
        "sandbox": {
            "enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
            "autoAllowBashIfSandboxed": True,
            "network": {"allowedDomains": [], "strictAllowlist": True},
            "filesystem": {"denyRead": sorted(set(deny_read)), "allowRead": [ws_s], "allowWrite": [ws_s]},
        },
    }


def deny_roots(runs_dir: Path) -> list[str]:
    """Paths no agent may read: home (config dirs, logins), this repository (keys and hidden tests), every other run's
    workspace, and the shared temp root. Only paths that exist are listed."""
    cands = [Path.home(), bench_home(), REPO_ROOT, runs_dir, Path("/home"), Path("/Users"), Path("/tmp"),
             Path("/private/tmp")]
    return [str(p.resolve()) for p in cands if p.exists()]


def argv(arm: str, kind: str, model: str, effort: str, settings: dict | None = None,
         max_turns: int | None = None, tools: str | None = None) -> list[str]:
    if kind == "read":
        flags, tools = ISOLATION_FLAGS, tools or READ_TOOLS
    else:
        flags = ["--setting-sources", "user", "--strict-mcp-config", "--settings", json.dumps(settings)]
        tools = tools or WRITE_TOOLS
    out = [arm_claude(arm), "-p", "--output-format", "stream-json", "--verbose", "--include-hook-events",
           "--permission-prompts", "none", *flags, "--model", model, "--effort", effort,
           "--tools", tools, "--allowedTools", tools, "--no-session-persistence"]
    return out + (["--max-turns", str(max_turns)] if max_turns else [])


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def parse_stream(stdout: str) -> dict:
    ev = {"tool_uses": [], "tool_results": [], "hook_events": set(), "result": None, "rate_limit": None,
          "compact_boundaries": 0}
    for line in stdout.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        t, st = d.get("type"), d.get("subtype")
        if st == "hook_started":
            ev["hook_events"].add(d.get("hook_event"))
        elif st == "compact_boundary":
            ev["compact_boundaries"] += 1
        elif t == "rate_limit_event":
            ev["rate_limit"] = d.get("rate_limit_info")
        elif t == "assistant":
            for c in (d.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    ev["tool_uses"].append({"id": c.get("id"), "name": c.get("name"), "input": c.get("input") or {}})
        elif t == "user" and isinstance((d.get("message") or {}).get("content"), list):
            for c in d["message"]["content"]:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    ev["tool_results"].append({"id": c.get("tool_use_id"), "is_error": bool(c.get("is_error")),
                                               "text": _text(c.get("content"))[:20000]})
        elif t == "result":
            ev["result"] = d
    return ev


def usage(u: dict | None) -> dict:
    u = u or {}
    return {"input": u.get("input_tokens", 0), "cache_read": u.get("cache_read_input_tokens", 0),
            "cache_creation": u.get("cache_creation_input_tokens", 0), "output": u.get("output_tokens", 0)}


def _outside(ws: Path, tool_input: dict) -> bool:
    path = tool_input.get("file_path") or tool_input.get("path")
    if not path:
        return False
    p = Path(path) if os.path.isabs(path) else ws / path
    return not str(p.resolve()).startswith(str(ws.resolve()))


def launch(arm: str, ws: Path, instruction: str, kind: str, model: str, effort: str, settings: dict | None = None,
           timeout_s: int = TIMEOUT_S, max_turns: int | None = None, tools: str | None = None) -> dict:
    """One `claude -p` run in its own process group; on timeout the whole group (subagents included) is stopped."""
    start = time.monotonic()
    proc = subprocess.Popen(argv(arm, kind, model, effort, settings, max_turns, tools), cwd=ws, env=arm_env(arm),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            errors="replace", start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(input=instruction, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate(proc)
        stdout, stderr = proc.communicate()
    except BaseException:
        terminate(proc)
        raise
    wall = round(time.monotonic() - start, 1)
    ev = parse_stream(stdout or "")
    r = ev["result"] or {}
    ok = not timed_out and proc.returncode == 0 and r.get("subtype") == "success" and not r.get("is_error")
    err = None if ok else ("timeout" if timed_out else (r.get("subtype") or (stderr or "no result")[-300:]))
    return {"ok": ok, "error": err, "timed_out": timed_out, "exit_code": proc.returncode, "wall_s": wall,
            "final_text": r.get("result") or "", "usage": usage(r.get("usage")),
            "models": sorted((r.get("modelUsage") or {}).keys()), "num_turns": r.get("num_turns"),
            "tool_calls": len(ev["tool_uses"]),
            "tool_names": sorted({t["name"] for t in ev["tool_uses"] if t["name"]}),
            "permission_denials": len(r.get("permission_denials") or []),
            "outside_read_attempts": sum(1 for t in ev["tool_uses"] if _outside(ws, t["input"])),
            "hooks": sorted(h for h in ev["hook_events"] if h), "compact_boundaries": ev["compact_boundaries"],
            "rate_limit": ev["rate_limit"], "events": ev, "raw_stdout": stdout or "",
            "stderr_tail": (stderr or "")[-2000:]}
