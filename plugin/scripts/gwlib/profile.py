"""`gw profile diff | apply | revert` (safety-guards spec: the settings profile is applied only with approval and is
reversible). A profile is a fragment of user settings for its own CLAUDE_CONFIG_DIR, so the owner's existing config
directory is never touched (design D1)."""
from __future__ import annotations

import difflib
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Callable

from .util import PLUGIN_ROOT, dump_json, expand, read_json, write_atomic

PROFILES = ("work", "personal")
STATE_DIR = ".groundwork-profile"   # inside the profile's config directory


class ProfileError(Exception):
    pass


def load_profile(name: str, root: Path = PLUGIN_ROOT) -> dict:
    if name not in PROFILES:
        raise ProfileError(f"unknown profile {name!r}; expected one of {', '.join(PROFILES)}")
    doc = json.loads((root / "profile" / f"{name}.json").read_text())
    if doc.get("format") != 1:
        raise ProfileError(f"profile/{name}.json has format {doc.get('format')!r}; this gw supports 1")
    return doc


def fill(settings, values: dict):
    """Replace ${NAME} placeholders. A list entry whose placeholder has no value is dropped."""
    if isinstance(settings, dict):
        return {k: fill(v, values) for k, v in settings.items()}
    if isinstance(settings, list):
        out = []
        for v in settings:
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                if values.get(v[2:-1]):
                    out.append(values[v[2:-1]])
                continue
            out.append(fill(v, values))
        return out
    return settings


def merge(current, fragment):
    """Dicts merge key by key, lists gain the fragment's missing entries in order, scalars take the fragment's value."""
    if isinstance(current, dict) and isinstance(fragment, dict):
        out = dict(current)
        for k, v in fragment.items():
            out[k] = merge(current[k], v) if k in current else v
        return out
    if isinstance(current, list) and isinstance(fragment, list):
        return current + [v for v in fragment if v not in current]
    return fragment


def drift(current, fragment, path: str = "") -> list[str]:
    """Key paths where `current` no longer contains what `fragment` sets."""
    if isinstance(fragment, dict):
        if not isinstance(current, dict):
            return [path or "<root>"]
        out = []
        for k, v in fragment.items():
            sub = f"{path}.{k}" if path else k
            out += drift(current[k], v, sub) if k in current else [sub]
        return out
    if isinstance(fragment, list):
        return [] if isinstance(current, list) and all(v in current for v in fragment) else [path]
    return [] if current == fragment else [path]


def config_dir(doc: dict, override: str | None) -> Path:
    return expand(override or doc["config_dir"])


def plan(name: str, cfg: str | None = None, vault: str | None = None, root: Path = PLUGIN_ROOT) -> dict:
    doc = load_profile(name, root)
    cdir = config_dir(doc, cfg)
    target = cdir / "settings.json"
    before = target.read_bytes() if target.exists() else None
    current = json.loads(before) if before else {}
    fragment = fill(doc["settings"], {"VAULT": str(expand(vault)) if vault else ""})
    after = dump_json(merge(current, fragment))
    diff = "".join(difflib.unified_diff((before or b"").decode().splitlines(True), after.decode().splitlines(True),
                                        fromfile=f"{target} (now)", tofile=f"{target} (after apply)"))
    return {"profile": name, "config_dir": cdir, "target": target, "before": before, "after": after,
            "fragment": fragment, "diff": diff}


def tty_confirm(prompt: str) -> bool:
    """The owner's approval: only a person at a terminal can give it. Claude's Bash tool has no TTY on stdin."""
    if not sys.stdin.isatty():
        return False
    try:
        return input(prompt).strip() == "apply"
    except EOFError:
        return False


def apply(name: str, cfg: str | None = None, vault: str | None = None, root: Path = PLUGIN_ROOT,
          confirm: Callable[[str], bool] = tty_confirm, out=sys.stdout) -> int:
    p = plan(name, cfg, vault, root)
    if p["before"] == p["after"]:
        print(f"{p['target']} already matches profile {name}; nothing to do.", file=out)
        return 0
    print(p["diff"], file=out)
    if not confirm(f"Type 'apply' to write {p['target']}: "):
        print("Not applied: owner approval is required, from an interactive terminal.", file=out)
        return 3
    state = p["config_dir"] / STATE_DIR
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + f"-{time.time_ns() % 1_000_000:06d}"
    previous = read_json(state / "applied.json")
    if previous:   # keep the backup taken before Groundwork first changed this file, so revert returns to it
        backup = state / "backups" / previous["backup"]
    else:
        backup = state / "backups" / f"settings.json.{stamp}"
        write_atomic(backup, p["before"] if p["before"] is not None else b"")
        write_atomic(backup.with_name(backup.name + ".meta.json"),
                     dump_json({"existed": p["before"] is not None, "target": str(p["target"])}))
    write_atomic(p["target"], p["after"])
    write_atomic(state / "applied.json", dump_json({
        "format": 1, "profile": name, "at": stamp, "backup": backup.name, "fragment": p["fragment"],
        "fragment_sha256": hashlib.sha256(dump_json(p["fragment"])).hexdigest()}))
    print(f"Applied profile {name} to {p['target']}. Backup: {backup}", file=out)
    return 0


def revert(name: str, cfg: str | None = None, root: Path = PLUGIN_ROOT, out=sys.stdout) -> int:
    doc = load_profile(name, root)
    cdir = config_dir(doc, cfg)
    state = cdir / STATE_DIR
    applied = read_json(state / "applied.json")
    if not applied:
        print(f"No applied profile recorded in {state}; nothing to revert.", file=out)
        return 1
    backup = state / "backups" / applied["backup"]
    meta = json.loads(backup.with_name(backup.name + ".meta.json").read_text())
    target = Path(meta["target"])
    if meta["existed"]:
        write_atomic(target, backup.read_bytes())
    else:
        target.unlink(missing_ok=True)
    (state / "applied.json").unlink()
    print(f"Reverted {target} to the backup taken before profile {name} was applied.", file=out)
    return 0


def check_drift(name: str, cfg: str | None = None, root: Path = PLUGIN_ROOT) -> list[str] | None:
    """None when this profile was never applied in that config directory."""
    doc = load_profile(name, root)
    cdir = config_dir(doc, cfg)
    applied = read_json(cdir / STATE_DIR / "applied.json")
    if not applied:
        return None
    current = read_json(cdir / "settings.json", {})
    return drift(current, applied["fragment"])


def main(args) -> int:
    if args.action == "diff":
        p = plan(args.name, args.config_dir, args.vault)
        print(p["diff"] or f"{p['target']} already matches profile {args.name}.")
        return 0
    if args.action == "apply":
        return apply(args.name, args.config_dir, args.vault)
    return revert(args.name, args.config_dir)
