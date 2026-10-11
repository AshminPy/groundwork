#!/usr/bin/env bash
# Groundwork uninstaller.
#
# Removes only what Groundwork added:
#   - ~/.claude/rules/groundwork/ (the rule files), ~/.claude/groundwork/playbooks/ and VERSION
#     (telemetry records under ~/.claude/groundwork/telemetry/ — including Routines' own run
#      history, routines.jsonl — dashboards under reports/, and investigation-continuity notes
#      under investigations/ are all kept — they are your data; the launchd report job
#      com.groundwork.report and any per-Routine com.groundwork.routine.* jobs are removed)
#   - ~/.claude/groundwork/config.json (Groundwork 2.1's own capability/Routines selection —
#     this is Groundwork's config, not your data, unlike telemetry/reports/investigations)
#   - ~/.claude/hooks/block_protected_push.py, require_material_review.py,
#     groundwork_session_snapshot.py, groundwork_telemetry.py, groundwork_shared.py
#   - the hook entries (four hook scripts; groundwork_telemetry.py registers three — Stop,
#     PostToolUse, PostToolUseFailure), the deny rules, and the env defaults this repo's
#     install.sh added to settings.json (via scripts/unmerge_settings.py)
#   - with --agent-teams: also env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS when it is "1"
#   - the groundwork CLI (bin/groundwork, bin/setup.sh, groundwork/env) and the marked
#     PATH-registration block install.sh appended to ~/.bashrc / ~/.zshrc / ~/.profile
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
# Same for any scheduled Routines (Groundwork 2.1) — unschedule every known one before deleting
# the script; idempotent and safe even for a routine that was never actually scheduled. Routine
# names are read from groundwork_routines.py's own ROUTINES registry (single owner for that list —
# independent-review nice-to-have: a hardcoded name list here would silently stop unscheduling a
# future routine the registry adds), falling back to the known 2.1 set only if that read fails.
if [ -f "$CLAUDE_DIR/groundwork/bin/groundwork_routines.py" ]; then
  routine_names="$(python3 -c "
import sys
sys.path.insert(0, '$CLAUDE_DIR/groundwork/bin')
import groundwork_routines as m
print('\n'.join(sorted(m.ROUTINES)))
" 2>/dev/null || true)"
  if [ -z "$routine_names" ]; then
    routine_names="jira_eod
news
weekly_status
pr_followup
work_digest
doc_drift"
  fi
  while IFS= read -r r; do
    if [ -n "$r" ]; then
      python3 "$CLAUDE_DIR/groundwork/bin/groundwork_routines.py" schedule "$r" disabled >/dev/null 2>&1 || true
    fi
  done <<< "$routine_names"
fi
rm -rf "$CLAUDE_DIR/rules/groundwork" "$CLAUDE_DIR/groundwork/playbooks" "$CLAUDE_DIR/groundwork/bin"
rm -f "$CLAUDE_DIR/groundwork/config.json" \
      "$CLAUDE_DIR/groundwork/VERSION" \
      "$CLAUDE_DIR/groundwork/env" \
      "$CLAUDE_DIR/hooks/block_protected_push.py" \
      "$CLAUDE_DIR/hooks/require_material_review.py" \
      "$CLAUDE_DIR/hooks/groundwork_session_snapshot.py" \
      "$CLAUDE_DIR/hooks/groundwork_telemetry.py" \
      "$CLAUDE_DIR/hooks/groundwork_shared.py"
# groundwork CLI PATH registration — remove exactly the marked block install.sh appended (same
# exact-match limitation already documented elsewhere in this file: a byte-identical block a user
# happened to add independently would also be removed). Never touches any other line in the file.
GW_ENV_MARK_BEGIN="# >>> groundwork CLI PATH (added by Groundwork's install.sh) >>>"
GW_ENV_MARK_END="# <<< groundwork CLI PATH <<<"
for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
  if [ -f "$rc" ] && grep -qF "$GW_ENV_MARK_BEGIN" "$rc" 2>/dev/null; then
    tmp="$(mktemp)"
    # Single pass with a one-line lookback: drops exactly the blank separator line install.sh's
    # own `echo ""` adds immediately before the marker block (present whether that block sits at
    # true end-of-file or is followed by later content), without touching any other blank line
    # already in the file.
    awk -v begin="$GW_ENV_MARK_BEGIN" -v end="$GW_ENV_MARK_END" '
      function flush() { if (have_pending) { print pending; have_pending = 0 } }
      $0 == begin {
        if (have_pending && pending == "") { have_pending = 0 } else { flush() }
        skip = 1
        next
      }
      $0 == end { skip = 0; next }
      skip { next }
      {
        flush()
        pending = $0
        have_pending = 1
      }
      END { flush() }
    ' "$rc" > "$tmp"
    mv "$tmp" "$rc"
  fi
done
# Python leaves a compiled cache behind for each hook it has run; clean up just Groundwork's own
# entries by name (never the whole __pycache__ dir — it may hold other tools' cached modules too).
rm -f "$CLAUDE_DIR"/hooks/__pycache__/block_protected_push.*.pyc \
      "$CLAUDE_DIR"/hooks/__pycache__/require_material_review.*.pyc \
      "$CLAUDE_DIR"/hooks/__pycache__/groundwork_session_snapshot.*.pyc \
      "$CLAUDE_DIR"/hooks/__pycache__/groundwork_telemetry.*.pyc \
      "$CLAUDE_DIR"/hooks/__pycache__/groundwork_shared.*.pyc 2>/dev/null || true
rmdir "$CLAUDE_DIR/hooks/__pycache__" 2>/dev/null || true
if [ -d "$CLAUDE_DIR/groundwork/telemetry" ] || [ -d "$CLAUDE_DIR/groundwork/reports" ] || [ -d "$CLAUDE_DIR/groundwork/investigations" ]; then
  for kept in telemetry reports investigations; do
    [ -d "$CLAUDE_DIR/groundwork/$kept" ] && echo "Kept $CLAUDE_DIR/groundwork/$kept/ (your data) — delete it yourself if you do not want it."
  done
else
  rmdir "$CLAUDE_DIR/groundwork" 2>/dev/null || true
fi
python3 "$HERE/scripts/unmerge_settings.py" "${UNMERGE_ARGS[@]+"${UNMERGE_ARGS[@]}"}" "$CLAUDE_DIR/settings.json"
echo "Done. ECC and OpenSpec were left untouched — see README.md if you want to remove those too."
