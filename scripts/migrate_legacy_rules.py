#!/usr/bin/env python3
"""Move a pre-Groundwork copy of the rules out of the way so they are not loaded twice.

Groundwork 1.0.0 was extracted from a personal harness that installed the same two
rule files under ~/.claude/rules/harness/. Claude Code loads every *.md under
~/.claude/rules/ recursively (docs/en/memory), so installing Groundwork's copy under
rules/groundwork/ next to the legacy copy would load each rule twice.

This script moves (never deletes) rules/harness/engineering-workflow.md and
rules/harness/evidence-policy.md into ~/.claude/backups/groundwork-legacy-<timestamp>/,
removes rules/harness/ only if that leaves it empty, and prints a notice when
~/.claude/CLAUDE.md still points at the old path (the installer must not edit a
user-authored file). Silent no-op when the legacy files are absent.

Usage: python3 migrate_legacy_rules.py [CLAUDE_DIR]   (default ~/.claude)
"""
import os
import shutil
import sys
import time
from pathlib import Path

LEGACY_FILES = ("engineering-workflow.md", "evidence-policy.md")


def migrate(claude_dir: Path) -> list[str]:
    legacy_dir = claude_dir / "rules" / "harness"
    present = [name for name in LEGACY_FILES
               if (legacy_dir / name).is_file() and not (legacy_dir / name).is_symlink()]
    if not present:
        return []
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = claude_dir / "backups" / f"groundwork-legacy-{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    moved = []
    for name in present:
        shutil.move(str(legacy_dir / name), str(backup / name))
        moved.append(str(backup / name))
    try:
        if not any(legacy_dir.iterdir()):
            legacy_dir.rmdir()
    except OSError:
        pass
    return moved


def main() -> None:
    claude_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.path.expanduser("~/.claude"))
    moved = migrate(claude_dir)
    if not moved:
        return
    print("Legacy pre-Groundwork rules found under rules/harness/ — moved (not deleted) to:")
    for path in moved:
        print(f"  {path}")
    claude_md = claude_dir / "CLAUDE.md"
    try:
        if claude_md.is_file() and "rules/harness" in claude_md.read_text(errors="ignore"):
            print(f"NOTE: {claude_md} still mentions rules/harness — update that pointer to ~/.claude/rules/groundwork/.")
    except Exception:
        pass


if __name__ == "__main__":
    main()
