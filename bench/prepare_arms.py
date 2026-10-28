"""Build the three arms under $GW_BENCH_HOME (default ~/gw-bench), then record what each one really contains.

    python -m bench.prepare_arms [--arms V,E,G] [--groundwork-ref v2.5.0]

V: an empty CLAUDE_CONFIG_DIR and a bin/ with claude, node, npm, npx, python3 and git, and no openspec.
E: the same, plus ECC v2.2.1 installed the way Groundwork's install.sh installs it, and OpenSpec 1.13.2 installed
   with `npm install --prefix` into the arm's own prefix (never global).
G: the same bin/ as E (OpenSpec 1.13.2 already on PATH, so install.sh skips its global npm step), then Groundwork's
   own install.sh from the given tag, with GROUNDWORK_OS=linux and GROUNDWORK_NO_LAUNCHCTL=1 so it never touches
   launchd. On macOS the owner's ~/Library/LaunchAgents/com.groundwork.report.plist is hashed before and after; any
   change fails the preparation.
Every install step runs with the allow-listed arm environment plus proxy and CA settings: no host tokens.
Writes $GW_BENCH_HOME/arms-meta.json. Safe to re-run: an arm whose meta already matches is left as it is.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import arms

ECC_REF = "v2.2.1"
OPENSPEC_VERSION = "1.13.2"
GROUNDWORK_REF = "v2.5.0"
LINKS = ("claude", "node", "npm", "npx", "python3", "git")
# Install-time extras: the proxy and CA settings git and npm need. Still no credentials.
INSTALL_ENV_KEEP = ("GIT_SSL_CAINFO", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "npm_config_https_proxy",
                    "npm_config_proxy", "npm_config_noproxy", "npm_config_cafile")
PLIST = Path("~/Library/LaunchAgents/com.groundwork.report.plist").expanduser()


def install_env(arm: str) -> dict:
    env = arms.arm_env(arm)
    env.update({k: os.environ[k] for k in INSTALL_ENV_KEEP if k in os.environ})
    return env


def sh(cmd: list[str], env: dict, cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("  $ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True, timeout=900)
    if check and r.returncode != 0:
        raise SystemExit(f"FAILED ({r.returncode}): {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def plist_hash() -> str | None:
    return hashlib.sha256(PLIST.read_bytes()).hexdigest() if PLIST.exists() else None


def make_bin(arm: str) -> None:
    b = arms.arm_dirs(arm)["bin"]
    b.mkdir(parents=True, exist_ok=True)
    for name in LINKS:
        src = shutil.which(name)
        if not src:
            raise SystemExit(f"{name} not found on PATH")
        dst = b / name
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        dst.symlink_to(os.path.realpath(src) if name != "claude" else src)


def install_openspec(arm: str) -> None:
    root = arms.arm_dirs(arm)["root"]
    prefix = root / "npm"
    env = install_env(arm)
    sh(["npm", "install", "--prefix", str(prefix), "--no-fund", "--no-audit", f"@fission-ai/openspec@{OPENSPEC_VERSION}"],
       env)
    link = arms.arm_dirs(arm)["bin"] / "openspec"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(prefix / "node_modules" / ".bin" / "openspec")
    sh(["openspec", "config", "set", "telemetry.enabled", "false"], env, check=False)


def install_ecc(arm: str) -> None:
    env = install_env(arm)
    if "ecc@ecc" in sh(["claude", "plugin", "list"], env, check=False).stdout:
        return
    sh(["claude", "plugin", "marketplace", "add", f"affaan-m/ECC#{ECC_REF}"], env)
    sh(["claude", "plugin", "install", "ecc@ecc", "--scope", "user", "--config", "hook_profile=standard"], env)


def install_groundwork(arm: str, ref: str) -> None:
    env = install_env(arm)
    env.update({"GROUNDWORK_ECC_REF": ECC_REF, "GROUNDWORK_OS": "linux", "GROUNDWORK_NO_LAUNCHCTL": "1"})
    with tempfile.TemporaryDirectory(prefix="gw-install-") as tmp:
        archive = subprocess.run(["git", "-C", str(arms.REPO_ROOT), "archive", ref], capture_output=True, check=True)
        subprocess.run(["tar", "-x", "-C", tmp], input=archive.stdout, check=True)
        sh(["bash", str(Path(tmp) / "install.sh")], env, cwd=tmp)


def describe(arm: str) -> dict:
    env = arms.arm_env(arm)
    d = arms.arm_dirs(arm)

    def out(cmd):
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
        return (r.stdout or r.stderr).strip() if r.returncode == 0 else None

    gw_version = None
    changelog = d["config"] / "groundwork" / "VERSION"
    if changelog.exists():
        gw_version = changelog.read_text().strip()
    rules = d["config"] / "rules" / "groundwork"
    return {"arm": arm, "config_dir": str(d["config"]), "claude_version": out(["claude", "--version"]),
            "plugins": out(["claude", "plugin", "list"]), "openspec_path": shutil.which("openspec", path=env["PATH"]),
            "openspec_version": out(["openspec", "--version"]) if shutil.which("openspec", path=env["PATH"]) else None,
            "groundwork_version": gw_version, "groundwork_rules": sorted(p.name for p in rules.glob("*.md")),
            "hooks_in_settings": _hook_events(d["config"] / "settings.json")}


def _hook_events(settings: Path) -> list[str]:
    try:
        return sorted((json.loads(settings.read_text()).get("hooks") or {}).keys())
    except (OSError, json.JSONDecodeError):
        return []


EXPECT = {
    "V": lambda m: m["openspec_path"] is None and "ecc@ecc" not in (m["plugins"] or "") and not m["groundwork_rules"],
    "E": lambda m: m["openspec_version"] == OPENSPEC_VERSION and "ecc@ecc" in (m["plugins"] or "")
    and not m["groundwork_rules"],
    "G": lambda m: m["openspec_version"] == OPENSPEC_VERSION and "ecc@ecc" in (m["plugins"] or "")
    and bool(m["groundwork_rules"]) and m["groundwork_version"] == GROUNDWORK_REF.lstrip("v"),
}


def check(meta: dict) -> list[str]:
    return [arm for arm, m in meta.items() if not EXPECT[arm](m)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="V,E,G")
    ap.add_argument("--groundwork-ref", default=GROUNDWORK_REF)
    a = ap.parse_args(argv)
    before = plist_hash()
    for arm in a.arms.split(","):
        print(f"== arm {arm} ==", flush=True)
        arms.arm_dirs(arm)["config"].mkdir(parents=True, exist_ok=True)
        make_bin(arm)
        if arm in ("E", "G"):
            install_openspec(arm)
            install_ecc(arm)
        if arm == "G":
            install_groundwork(arm, a.groundwork_ref)
    if plist_hash() != before:
        print("FAILED: the owner's report launchd plist changed during preparation", file=sys.stderr)
        return 3
    meta = {arm: describe(arm) for arm in arms.ARMS if arms.arm_dirs(arm)["config"].exists()}
    meta["_groundwork_ref"] = a.groundwork_ref  # type: ignore[assignment]
    path = arms.bench_home() / "arms-meta.json"
    path.write_text(json.dumps(meta, indent=1) + "\n")
    bad = check({k: v for k, v in meta.items() if k in arms.ARMS})
    print(json.dumps(meta, indent=1))
    if bad:
        print(f"FAILED: arm metadata does not match the plan for {bad}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
