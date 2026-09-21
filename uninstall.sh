#!/usr/bin/env bash
# Groundwork uninstaller.
#
# Removes only what Groundwork added:
#   - ~/.claude/rules/groundwork/ (the rule files), ~/.claude/groundwork/playbooks/ and VERSION
#     (telemetry records under ~/.claude/groundwork/telemetry/ and dashboards under reports/ are kept — they are your data;
#      the launchd report job com.groundwork.report is removed)
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
# Report schedule: remove the launchd job (the generator itself does it) before deleting the script.
if [ -f "$CLAUDE_DIR/groundwork/bin/groundwork_report.py" ]; then
  python3 "$CLAUDE_DIR/groundwork/bin/groundwork_report.py" schedule disabled >/dev/null 2>&1 || true
fi
rm -rf "$CLAUDE_DIR/rules/groundwork" "$CLAUDE_DIR/groundwork/playbooks" "$CLAUDE_DIR/groundwork/bin"
rm -f "$CLAUDE_DIR/groundwork/VERSION" \
      "$CLAUDE_DIR/hooks/block_protected_push.py" \
      "$CLAUDE_DIR/hooks/require_material_review.py" \
      "$CLAUDE_DIR/hooks/groundwork_session_snapshot.py" \
      "$CLAUDE_DIR/hooks/groundwork_telemetry.py"
if [ -d "$CLAUDE_DIR/groundwork/telemetry" ] || [ -d "$CLAUDE_DIR/groundwork/reports" ]; then
  for kept in telemetry reports; do
    [ -d "$CLAUDE_DIR/groundwork/$kept" ] && echo "Kept $CLAUDE_DIR/groundwork/$kept/ (your data) — delete it yourself if you do not want it."
  done
else
  rmdir "$CLAUDE_DIR/groundwork" 2>/dev/null || true
fi
python3 "$HERE/scripts/unmerge_settings.py" "${UNMERGE_ARGS[@]+"${UNMERGE_ARGS[@]}"}" "$CLAUDE_DIR/settings.json"
echo "Done. ECC and OpenSpec were left untouched — see README.md if you want to remove those too."
