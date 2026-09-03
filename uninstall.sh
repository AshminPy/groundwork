#!/usr/bin/env bash
# Groundwork uninstaller.
#
# Removes only what Groundwork added:
#   - ~/.claude/rules/groundwork/ (the two rule files)
#   - ~/.claude/hooks/block_protected_push.py, require_material_review.py
#   - the two hook entries, the deny rules, and the two env vars this repo's
#     install.sh added to settings.json (via scripts/unmerge_settings.py)
#
# Does NOT uninstall ECC or OpenSpec (they're independent, official projects —
# use their own uninstall paths if you want them gone too, see README.md).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

echo "== Groundwork uninstaller =="
rm -rf "$CLAUDE_DIR/rules/groundwork"
rm -f "$CLAUDE_DIR/hooks/block_protected_push.py" "$CLAUDE_DIR/hooks/require_material_review.py"
python3 "$HERE/scripts/unmerge_settings.py" "$CLAUDE_DIR/settings.json"
echo "Done. ECC and OpenSpec were left untouched — see README.md if you want to remove those too."
