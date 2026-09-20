#!/usr/bin/env bash
# Groundwork uninstaller.
#
# Removes only what Groundwork added:
#   - ~/.claude/rules/groundwork/ (the rule files)
#   - ~/.claude/hooks/block_protected_push.py, require_material_review.py,
#     groundwork_session_snapshot.py
#   - the three hook entries, the deny rules, and the env defaults this repo's
#     install.sh added to settings.json (via scripts/unmerge_settings.py)
#   - with --agent-teams: also env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS when it is "1"
#
# Does NOT uninstall ECC or OpenSpec (they're independent, official projects —
# use their own uninstall paths if you want them gone too, see README.md), and
# does NOT restore a legacy rules/harness copy (see ~/.claude/backups/).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
UNMERGE_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --agent-teams) UNMERGE_ARGS+=("--agent-teams") ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

echo "== Groundwork uninstaller =="
rm -rf "$CLAUDE_DIR/rules/groundwork"
rm -f "$CLAUDE_DIR/hooks/block_protected_push.py" \
      "$CLAUDE_DIR/hooks/require_material_review.py" \
      "$CLAUDE_DIR/hooks/groundwork_session_snapshot.py"
python3 "$HERE/scripts/unmerge_settings.py" "${UNMERGE_ARGS[@]+"${UNMERGE_ARGS[@]}"}" "$CLAUDE_DIR/settings.json"
echo "Done. ECC and OpenSpec were left untouched — see README.md if you want to remove those too."
