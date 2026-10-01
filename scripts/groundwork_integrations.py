#!/usr/bin/env python3
"""Groundwork 2.1 Integration Catalog — a structured, code-defined catalog of the external-system
integrations Groundwork knows about (see docs/INTEGRATIONS.md for the researched narrative this
mirrors), each with its capability ids, approved access mechanism(s), and a truthfully-observed
readiness state.

Groundwork never installs, configures, or stores credentials for any of these (docs/INTEGRATIONS.md,
docs/ARCHITECTURE.md's capability-ownership matrix) — this catalog documents and observes, never wires.
It also never claims to activate or deactivate a specific MCP server for a task: Claude Code's own
Tool Search already handles lazy, on-demand MCP tool-schema loading (see docs/ARCHITECTURE.md's
"Tool Search" note); this catalog gives capability/access-mechanism *guidance* only.

Readiness is three INDEPENDENT observations, not one lifecycle — any combination is valid and none
is forced to imply another:
  available   an approved mechanism is actually present (CLI binary on PATH, or MCP server listed
              by `claude mcp list`) — presence only, never a claim of working connectivity.
  configured  non-secret Groundwork configuration references this integration (the active capability
              profile's cloud/platform/integrations lists in config.json).
  connected   a real reachability/authentication check for a specific mechanism actually ran and
              succeeded. Only ever set true by a check that actually ran; never inferred from
              availability or configuration alone. Today two CLI mechanisms have one: GitHub's `gh`
              CLI (`gh auth status`, the same command already trusted by groundwork_routines.py's
              check_access()), and Jira's `acli` CLI (`acli jira auth status`, exit-code-only today —
              see AccessMechanism.cli_success_marker's docstring on the Jira entry for why no success
              marker is set yet). Every other mechanism's `connected` stays False, honestly, until a
              real check for it is implemented.

`used` is a separate, task/session observation (True / False / None-for-unknown), read from
Groundwork's own existing telemetry (hooks/groundwork_telemetry.py's events.jsonl) — never built as
new tracking, and never folded into the three readiness observations above.

A single display SUMMARY label (CONNECTED > CONFIGURED > AVAILABLE > NOT CONFIGURED, highest true
wins) is derived on demand for `list`/`show`'s concise line — it is never stored and is not itself
the source of truth; `show` always prints the three raw booleans too.

Usage:
  groundwork_integrations.py list          one row per catalog integration: name, access, summary state
  groundwork_integrations.py show NAME     full detail for one integration (case-insensitive name)
  groundwork_integrations.py doctor NAME   show's detail plus a one-line reason for each observation
                                            (why available/configured/connected/used is what it is) —
                                            narrates the same observation `show` already computes, never
                                            a second probe

No dependency on `hooks/groundwork_shared.py`: `hooks/` and `scripts/` install to different
directories post-install (~/.claude/hooks/ vs ~/.claude/groundwork/bin/), so a shared import between
them would break after installation. Probes here are written fresh, deliberately matching (not
sharing code with) groundwork_routines.py's check_access() pattern — see design.md Decision 3 in
openspec/changes/add-integration-catalog/.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

# Same CLAUDE_CONFIG_DIR resolution every other Groundwork script uses (groundwork_config.py,
# groundwork_routines.py, groundwork_report.py, the hooks).
CONFIG_PATH = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / "groundwork" / "config.json"
TELEMETRY_PATH = (
    Path(os.path.expanduser(os.environ.get("GROUNDWORK_TELEMETRY_PATH", "")))
    if os.environ.get("GROUNDWORK_TELEMETRY_PATH")
    else Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / "groundwork" / "telemetry" / "events.jsonl"
)
# Cache written by `refresh` and read (never written) by scripts/groundwork_statusline.py — see
# openspec/changes/add-statusline/design.md Decision 1/2: refreshed only at existing lifecycle
# points (install, configure, explicit refresh / `--doctor`), never by a scheduled/background job.
INTEGRATIONS_CACHE_PATH = (
    Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude")) / "groundwork" / "integrations" / "cache.json"
)

CLI_AUTH_TIMEOUT_S = 10   # matches check_access()'s `gh auth status` timeout precedent
MCP_LIST_TIMEOUT_S = 15   # matches check_access()'s `claude mcp list` timeout precedent


@dataclass(frozen=True)
class AccessMechanism:
    type: str  # "mcp" | "cli" | "api" — never anything else
    name: str  # display name, e.g. "GitHub MCP", "gh CLI"
    cli_binary: Optional[str] = None                  # presence check target for a "cli" mechanism
    mcp_server_name: Optional[str] = None              # presence-in-`claude mcp list` target for "mcp"
    cli_auth_cmd: Optional[Tuple[str, ...]] = None      # a REAL connectivity check; only set where one is safely known
    cli_success_marker: Optional[str] = None            # required substring in cli_auth_cmd's output; exit code 0 alone is not proof
    # (`gh auth status` was observed, live, to exit 0 while printing "Failed to log in ... token is invalid" —
    # an env-supplied GH_TOKEN it cannot validate. Exit code alone is not a trustworthy success signal for it.)


@dataclass(frozen=True)
class IntegrationEntry:
    name: str
    capabilities: Tuple[str, ...]
    mechanisms: Tuple[AccessMechanism, ...]
    trust: str
    config_requirements: str
    config_key: Optional[Tuple[str, str]] = None        # (config.json section, key) that makes `configured` true
    routine_access_values: Tuple[str, ...] = field(default_factory=tuple)  # routine "access" values that use this integration


@dataclass(frozen=True)
class IntegrationObservation:
    available: bool
    configured: bool
    connected: bool
    used: Optional[bool]  # True, False, or None ("unknown")


# ---------------------------------------------------------------------------------------------
# The catalog — mirrors docs/INTEGRATIONS.md's researched capability matrix (2026-09-28 research
# date noted there). Kept intentionally small: one entry per domain already researched there, no
# invented integrations. Capability ids are deliberately coarse (read/write per domain, plus a
# couple of concrete finer ones where genuinely useful) rather than an exhaustive taxonomy.
# ---------------------------------------------------------------------------------------------
CATALOG: Tuple[IntegrationEntry, ...] = (
    IntegrationEntry(
        name="GitHub",
        capabilities=("github.repository.read", "github.repository.write", "github.pull_request.read"),
        mechanisms=(
            AccessMechanism("mcp", "GitHub MCP", mcp_server_name="github"),
            AccessMechanism(
                "cli", "gh CLI", cli_binary="gh", cli_auth_cmd=("gh", "auth", "status"),
                cli_success_marker="Logged in to",
            ),
        ),
        trust="Vendor/official (github/github-mcp-server); full read/write including destructive — scope with --read-only/--toolsets",
        config_requirements="OAuth, PAT, or GitHub App for the MCP server; `gh auth login` for the CLI",
        config_key=("integrations", "github"),
        routine_access_values=("github_mcp", "gh_cli"),
    ),
    IntegrationEntry(
        name="Spacelift",
        capabilities=("spacelift.stack.read", "spacelift.run.write"),
        mechanisms=(
            AccessMechanism("cli", "spacectl", cli_binary="spacectl"),
            AccessMechanism("mcp", "Spacelift hosted MCP", mcp_server_name="spacelift"),
        ),
        trust="Vendor/official; mutate is a raw GraphQL pass-through (broad) — prefer spacectl for scripted/CI changes",
        config_requirements="OAuth (browser) for the MCP, or a spacectl bearer token for CI",
        config_key=("platform", "spacelift"),
    ),
    IntegrationEntry(
        name="Jira",
        capabilities=("jira.issue.read", "jira.issue.write"),
        mechanisms=(
            AccessMechanism("mcp", "Atlassian MCP", mcp_server_name="atlassian"),
            AccessMechanism(
                "cli", "acli CLI", cli_binary="acli", cli_auth_cmd=("acli", "jira", "auth", "status"),
                # UNVERIFIED success marker (documented 2026-10-01): `acli` was not installed in the
                # sandbox this mechanism was added in, and the official reference page
                # (developer.atlassian.com/cloud/acli/reference/commands/jira-auth-status/) could not
                # be fetched from here either (network egress to that host is blocked), so the exact
                # substring `acli jira auth status` prints on a real successful login has never been
                # observed and is deliberately left unset rather than guessed (see
                # AccessMechanism.cli_success_marker's own docstring: gh_cli's own marker exists
                # precisely because exit code 0 was observed to be insufficient for IT). Leaving
                # cli_success_marker unset makes _mechanism_connected() fall back to its existing
                # exit-code-only path (same fallback every other marker-less mechanism already uses),
                # so connected=True here currently means only "acli is on PATH and exited 0" — weaker
                # confidence than the gh_cli mechanism's marker-checked CONNECTED. Replace
                # cli_success_marker with a real, observed substring the first time this is run
                # against a real, authenticated `acli` install (see docs/INTEGRATIONS.md's matching
                # caveat).
            ),
        ),
        trust="Vendor/official (atlassian/atlassian-mcp-server, GA 2026-02-04); delete/admin ops off by default",
        config_requirements="OAuth 2.1 (default) or an API token",
        config_key=("integrations", "jira"),
        routine_access_values=("jira_mcp", "cli", "browser"),
    ),
    IntegrationEntry(
        name="Confluence",
        capabilities=("confluence.page.read", "confluence.page.write"),
        mechanisms=(AccessMechanism("mcp", "Atlassian MCP", mcp_server_name="atlassian"),),
        trust="Vendor/official (Cloud); community server (sooperset/mcp-atlassian) for Server/Data Center",
        config_requirements="OAuth 2.1 or an API token",
        config_key=("integrations", "confluence"),
    ),
    IntegrationEntry(
        name="AWS",
        capabilities=("aws.resource.read", "aws.resource.write"),
        mechanisms=(
            AccessMechanism("mcp", "AWS Labs MCP suite", mcp_server_name="aws"),
            AccessMechanism("cli", "aws CLI", cli_binary="aws"),
        ),
        trust="Vendor/official (awslabs/mcp); domain-dependent read/write per installed sub-server",
        config_requirements="AWS credentials, scoped per sub-server installed",
        config_key=("cloud", "aws"),
    ),
    IntegrationEntry(
        name="GCP",
        capabilities=("gcp.resource.read", "gcp.resource.write"),
        mechanisms=(
            AccessMechanism("mcp", "Google-managed GCP MCP", mcp_server_name="gcp"),
            AccessMechanism("cli", "gcloud CLI", cli_binary="gcloud"),
        ),
        trust="Vendor/official, but not Claude-specific-named by Google; managed/remote, enable per-service",
        config_requirements="Google Cloud auth",
        config_key=("cloud", "gcp"),
    ),
    IntegrationEntry(
        name="Kubernetes",
        capabilities=("kubernetes.resources.read", "kubernetes.logs.read", "kubernetes.events.read"),
        mechanisms=(
            AccessMechanism("mcp", "Kubernetes MCP", mcp_server_name="kubernetes"),
            AccessMechanism("cli", "kubectl", cli_binary="kubectl"),
        ),
        trust="Community/semi-official (containers/kubernetes-mcp-server, Red Hat org); kubectl-equivalent read/write",
        config_requirements="A kubeconfig with access to the target cluster/namespace",
        config_key=("platform", "kubernetes"),
    ),
    IntegrationEntry(
        name="Terraform",
        capabilities=("terraform.plan.read", "terraform.module.read"),
        mechanisms=(
            AccessMechanism("mcp", "Terraform MCP", mcp_server_name="terraform"),
            AccessMechanism("cli", "terraform CLI", cli_binary="terraform"),
        ),
        trust="Vendor/official (hashicorp/terraform-mcp-server); plan/module/registry access, not a replacement for `apply`'s own state safety",
        config_requirements="HashiCorp-managed auth where the MCP server needs it; local state/backend config for the CLI",
        config_key=("platform", "terraform"),
    ),
    IntegrationEntry(
        name="Grafana",
        capabilities=("observability.dashboards.read", "observability.dashboards.write"),
        mechanisms=(AccessMechanism("mcp", "Grafana MCP", mcp_server_name="grafana"),),
        trust="Vendor/official (grafana/mcp-grafana, Apache-2.0); write includes a destructive delete_dashboard — gate with --disable-write",
        config_requirements="A Grafana service-account token",
    ),
    IntegrationEntry(
        name="Datadog",
        capabilities=("observability.metrics.read", "observability.monitors.write"),
        mechanisms=(AccessMechanism("mcp", "Datadog MCP", mcp_server_name="datadog"),),
        trust="Vendor/official (Datadog-hosted + official Claude Code plugin); auth model not fully documented publicly — verify before adoption",
        config_requirements="Vendor-managed credentials",
    ),
    IntegrationEntry(
        name="PagerDuty",
        capabilities=("observability.incidents.read", "observability.incidents.write"),
        mechanisms=(AccessMechanism("mcp", "PagerDuty MCP", mcp_server_name="pagerduty"),),
        trust="Vendor/official (self-hosted variant deprecated); large surface (50 read / 22 write tools) — auth model not fully confirmed, verify before adoption",
        config_requirements="Vendor-managed credentials",
    ),
    IntegrationEntry(
        name="Sentry",
        capabilities=("observability.issues.read",),
        mechanisms=(AccessMechanism("mcp", "Sentry MCP", mcp_server_name="sentry"),),
        trust="Vendor/official (getsentry/sentry-mcp, source-available FSL license); narrow, confirmation-gated write",
        config_requirements="A Sentry token",
    ),
    IntegrationEntry(
        name="Prometheus",
        capabilities=("observability.metrics.read",),
        mechanisms=(AccessMechanism("api", "Prometheus HTTP/PromQL API"),),
        trust="No credible single official MCP found (CNCF project); prefer the stable HTTP/PromQL API directly",
        config_requirements="Network access to the Prometheus endpoint (no Groundwork-tracked config)",
    ),
)

_BY_NAME = {e.name.lower(): e for e in CATALOG}


# ---------------------------------------------------------------------------------------------
# Probes — non-mutating, timeout-bounded, fail-safe. Same spirit as groundwork_routines.py's
# check_access(): shutil.which() for presence, subprocess.run(..., timeout=...) for real checks,
# every exception swallowed into a safe negative rather than propagated.
# ---------------------------------------------------------------------------------------------
_mcp_list_cache: Optional[str] = None
_mcp_list_attempted = False


def _mcp_list_output() -> str:
    """`claude mcp list` output, fetched at most once per process — every entry with an MCP
    mechanism shares this instead of shelling out N times."""
    global _mcp_list_cache, _mcp_list_attempted
    if _mcp_list_attempted:
        return _mcp_list_cache or ""
    _mcp_list_attempted = True
    if not shutil.which("claude"):
        return ""
    try:
        r = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True, timeout=MCP_LIST_TIMEOUT_S)
        _mcp_list_cache = r.stdout or ""
    except Exception:
        _mcp_list_cache = ""
    return _mcp_list_cache


def _mechanism_available(mech: AccessMechanism) -> bool:
    if mech.type == "cli" and mech.cli_binary:
        try:
            return shutil.which(mech.cli_binary) is not None
        except Exception:
            return False
    if mech.type == "mcp" and mech.mcp_server_name:
        try:
            return mech.mcp_server_name.lower() in _mcp_list_output().lower()
        except Exception:
            return False
    return False  # "api" mechanisms and anything without a concrete probe target: no generic presence check exists


def _mechanism_connected(mech: AccessMechanism) -> bool:
    if not mech.cli_auth_cmd:
        return False  # no real check implemented for this mechanism — never guess
    try:
        r = subprocess.run(list(mech.cli_auth_cmd), capture_output=True, text=True, timeout=CLI_AUTH_TIMEOUT_S)
        if r.returncode != 0:
            return False
        if mech.cli_success_marker is None:
            return True
        # Exit code 0 alone is not proof: require the tool's own explicit success confirmation too
        # (see cli_success_marker's docstring — gh auth status can exit 0 on a failed check).
        return mech.cli_success_marker in (r.stdout or "") + (r.stderr or "")
    except Exception:
        return False  # timeout, missing binary, or any other error: fail safe, never CONNECTED


def _load_config() -> dict:
    try:
        data = json.loads(CONFIG_PATH.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}  # missing or malformed config.json: fail safe, never crash


def _configured(entry: IntegrationEntry, cfg: dict) -> bool:
    if entry.config_key is None:
        return False
    section, key = entry.config_key
    try:
        values = cfg.get(section, [])
        return isinstance(values, list) and key in values
    except Exception:
        return False


def _last_telemetry_record() -> Optional[dict]:
    try:
        if not TELEMETRY_PATH.exists():
            return None
        last_line = None
        with TELEMETRY_PATH.open("r") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line is None:
            return None
        record = json.loads(last_line)
        return record if isinstance(record, dict) else None
    except Exception:
        return None  # missing, unreadable, or malformed telemetry: unknown, never a crash


def determine_used(entry: IntegrationEntry) -> Optional[bool]:
    mcp_names = {m.mcp_server_name.lower() for m in entry.mechanisms if m.type == "mcp" and m.mcp_server_name}
    if not mcp_names:
        return None  # CLI/API-only integrations: telemetry doesn't reliably attribute Bash calls to a specific tool
    record = _last_telemetry_record()
    if record is None:
        return None
    servers = record.get("observed", {}).get("mcp_servers")
    if not isinstance(servers, list):
        return None
    servers_lower = {str(s).lower() for s in servers}
    if servers_lower & mcp_names:
        return True
    return False  # a real recent record exists and does not list this integration's MCP server


def _combine_observation(available_flags, connected_flags, configured: bool, used: Optional[bool]) -> IntegrationObservation:
    """The one place the `any(...)` combination formula lives. determine_observation() and
    _cmd_doctor() both call this rather than each writing their own `any()` — found during
    independent review: doctor previously re-derived this formula inline, which would have let the
    two silently drift if the combinator ever changed (e.g. to something other than `any`)."""
    return IntegrationObservation(
        available=any(available_flags), configured=configured, connected=any(connected_flags), used=used,
    )


def determine_observation(entry: IntegrationEntry, cfg: dict) -> IntegrationObservation:
    return _combine_observation(
        [_mechanism_available(m) for m in entry.mechanisms],
        [_mechanism_connected(m) for m in entry.mechanisms],
        _configured(entry, cfg),
        determine_used(entry),
    )


def summary_state(obs: IntegrationObservation) -> str:
    """Display-only label, derived on demand — never stored, never the source of truth."""
    if obs.connected:
        return "CONNECTED"
    if obs.configured:
        return "CONFIGURED"
    if obs.available:
        return "AVAILABLE"
    return "NOT CONFIGURED"


def _access_label(entry: IntegrationEntry) -> str:
    seen = []
    for m in entry.mechanisms:
        label = m.type.upper()
        if label not in seen:
            seen.append(label)
    return " / ".join(seen)


def _used_label(used: Optional[bool]) -> str:
    return {True: "YES", False: "NO", None: "UNKNOWN"}[used]


def _routines_using(entry: IntegrationEntry, cfg: dict) -> list:
    if not entry.routine_access_values:
        return []
    routines_cfg = cfg.get("routines", {})
    if not isinstance(routines_cfg, dict):
        return []
    out = []
    for routine_name, routine_cfg in routines_cfg.items():
        if not isinstance(routine_cfg, dict):
            continue
        if routine_cfg.get("access") in entry.routine_access_values:
            out.append(routine_name)
    return sorted(out)


def _write_cache(rows: list) -> None:
    """Atomically persist this run's observations, one entry per integration, each with its own
    checked_at — written via temp-file + os.replace so a reader never sees a partial file mid-write
    (matches scripts/merge_settings.py's write_atomic() pattern)."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload = {
        "schema": 1,
        "integrations": {
            name: {
                "available": obs.available,
                "configured": obs.configured,
                "connected": obs.connected,
                "used": obs.used,
                "summary": summary_state(obs),
                "checked_at": now,
            }
            for name, obs in rows
        },
    }
    path = INTEGRATIONS_CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + ".groundwork.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------
def _compute_observations(cfg: dict) -> list:
    return [(entry.name, determine_observation(entry, cfg)) for entry in CATALOG]


def _print_list_table(observations: list) -> None:
    rows = [(name, _access_label(_BY_NAME[name.lower()]), summary_state(obs)) for name, obs in observations]
    name_w = max(len(r[0]) for r in rows) + 2
    access_w = max(len(r[1]) for r in rows) + 2
    print(f"{'Integration':<{name_w}}{'Access':<{access_w}}State")
    print("-" * (name_w + access_w + 12))
    for name, access, state in rows:
        print(f"{name:<{name_w}}{access:<{access_w}}{state}")


def _cmd_list(_args) -> int:
    cfg = _load_config()
    _print_list_table(_compute_observations(cfg))
    return 0


def _cmd_refresh(_args) -> int:
    """Runs the exact same live probes `list` does, prints the identical table, and additionally
    persists the results to the Integration Catalog cache for scripts/groundwork_statusline.py to
    read later — never invoked by the statusLine itself, only from install/configure/doctor/manual
    lifecycle points (openspec/changes/add-statusline/design.md Decision 1)."""
    cfg = _load_config()
    observations = _compute_observations(cfg)
    _print_list_table(observations)
    _write_cache(observations)
    return 0


def _cmd_show(args) -> int:
    entry = _BY_NAME.get(args.name.lower())
    if entry is None:
        print(f"'{args.name}' is not a known integration. Run 'groundwork_integrations.py list' for the catalog.")
        return 1
    cfg = _load_config()
    obs = determine_observation(entry, cfg)
    routines = _routines_using(entry, cfg)
    print(entry.name)
    print(f"  Purpose ............ {entry.trust}")
    print(f"  Capabilities ....... {', '.join(entry.capabilities)}")
    print(f"  Approved access .... {', '.join(m.name for m in entry.mechanisms)}")
    print(f"  Configuration ...... {entry.config_requirements}")
    print(f"  Available .......... {'YES' if obs.available else 'NO'}")
    print(f"  Configured ......... {'YES' if obs.configured else 'NO'}")
    print(f"  Connected .......... {'YES' if obs.connected else 'NO'}")
    print(f"  Used ............... {_used_label(obs.used)}")
    print(f"  Summary state ...... {summary_state(obs)}")
    print(f"  Used by Routines ... {', '.join(routines) if routines else '(none currently)'}")
    return 0


# ---------------------------------------------------------------------------------------------
# `doctor NAME` — a narration layer only. Every reason below explains a boolean that
# determine_observation() (unchanged, already covered by the tests above) already computed; no
# probe is ever re-run here, so `doctor` can never disagree with `show`/`list` about the state
# itself, only add a one-line "why".
# ---------------------------------------------------------------------------------------------
def _availability_reason(mech: AccessMechanism, available: bool) -> str:
    if mech.type == "cli":
        return f"'{mech.cli_binary}' {'found' if available else 'not found'} on PATH"
    if mech.type == "mcp":
        return (f"'{mech.mcp_server_name}' {'is' if available else 'is not'} listed by 'claude mcp list'"
                + ("" if available else " (or 'claude' is not on PATH / did not respond)"))
    return "no presence probe exists for this access type (e.g. a plain HTTP API)"


def _connected_reason(mech: AccessMechanism, connected: bool) -> str:
    if mech.cli_auth_cmd is None:
        return "no real connectivity check is implemented for this mechanism yet — never guessed"
    cmd = " ".join(mech.cli_auth_cmd)
    return f"'{cmd}' {'confirmed a successful login' if connected else 'did not confirm a successful login'}"


def _configured_reason(entry: IntegrationEntry, cfg: dict, configured: bool) -> str:
    if entry.config_key is None:
        return "this integration has no config.json key defined — configured is never set for it"
    section, key = entry.config_key
    if not cfg:
        return "no config.json found (or it is empty) — falls back to not configured"
    return f"'{key}' {'is' if configured else 'is not'} listed in config.json's '{section}' section"


def _used_reason(entry: IntegrationEntry, used: Optional[bool]) -> str:
    has_mcp = any(m.type == "mcp" for m in entry.mechanisms)
    if not has_mcp:
        return "no MCP mechanism — usage cannot be reliably attributed from telemetry for a CLI/API-only integration"
    if used is None:
        return "no telemetry records found yet" if not TELEMETRY_PATH.exists() else "the most recent telemetry record has no usable MCP server list"
    return "found in the most recent telemetry record's MCP server list" if used else "not found in the most recent telemetry record's MCP server list"


def _cmd_doctor(args) -> int:
    entry = _BY_NAME.get(args.name.lower())
    if entry is None:
        print(f"'{args.name}' is not a known integration. Run 'groundwork_integrations.py list' for the catalog.")
        return 1
    cfg = _load_config()
    # Probe each mechanism exactly once — the boolean feeds both the top-line YES/NO and its own
    # "why" line, rather than calling determine_observation() and then re-probing for reasons
    # (which would run every connectivity check, e.g. `gh auth status`, a second time). The
    # combination formula itself still lives in exactly one place (_combine_observation, shared
    # with determine_observation) — only the per-mechanism probing is done here, not the decision
    # of how those booleans combine into available/connected.
    avail_by_mech = [(m, _mechanism_available(m)) for m in entry.mechanisms]
    conn_by_mech = [(m, _mechanism_connected(m)) for m in entry.mechanisms]
    configured = _configured(entry, cfg)
    used = determine_used(entry)
    obs = _combine_observation(
        [a for _, a in avail_by_mech], [c for _, c in conn_by_mech], configured, used,
    )
    routines = _routines_using(entry, cfg)
    print(entry.name)
    print(f"  Purpose ............ {entry.trust}")
    print(f"  Capabilities ....... {', '.join(entry.capabilities)}")
    print(f"  Approved access .... {', '.join(m.name for m in entry.mechanisms)}")
    print(f"  Configuration ...... {entry.config_requirements}")
    print(f"  Available .......... {'YES' if obs.available else 'NO'}")
    for m, a in avail_by_mech:
        print(f"    - why ............ {m.name}: {_availability_reason(m, a)}")
    print(f"  Configured ......... {'YES' if obs.configured else 'NO'}")
    print(f"    - why ............ {_configured_reason(entry, cfg, obs.configured)}")
    print(f"  Connected .......... {'YES' if obs.connected else 'NO'}")
    for m, c in conn_by_mech:
        print(f"    - why ............ {m.name}: {_connected_reason(m, c)}")
    print(f"  Used ............... {_used_label(obs.used)}")
    print(f"    - why ............ {_used_reason(entry, obs.used)}")
    print(f"  Summary state ...... {summary_state(obs)}")
    print(f"  Used by Routines ... {', '.join(routines) if routines else '(none currently)'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list every catalog integration with its access mechanism(s) and state")
    p_show = sub.add_parser("show", help="show full detail for one integration")
    p_show.add_argument("name")
    sub.add_parser(
        "refresh",
        help="re-run every live probe and persist the results to the Integration Catalog cache "
             "(for scripts/groundwork_statusline.py — never run this from a scheduled/background job)",
    )
    p_doctor = sub.add_parser("doctor", help="show's detail plus a one-line reason for each observation")
    p_doctor.add_argument("name")
    args = ap.parse_args()
    return {"list": _cmd_list, "show": _cmd_show, "refresh": _cmd_refresh, "doctor": _cmd_doctor}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
