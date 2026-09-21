#!/usr/bin/env bash
# Groundwork one-click onboarding — a thin, user-friendly wrapper around the tested installer.
#
#   ./setup.sh                      first-time setup: prerequisites → backup → your choices →
#                                   install.sh → reporting schedule → verification → first dashboard
#   ./setup.sh --non-interactive [--profile NAME] [--agent-teams | --no-agent-teams] [--schedule FREQ]
#   ./setup.sh --verify             read-only check of the current installation (changes nothing)
#   ./setup.sh --rollback [DIR]     restore the latest backup made by setup.sh (or the given backup DIR)
#   ./setup.sh --uninstall          delegates to uninstall.sh (telemetry and reports are kept)
#
# setup.sh never installs anything itself: install.sh installs, uninstall.sh removes,
# scripts/groundwork_report.py schedules. This file only backs up, asks, delegates and verifies.
#
# Environment: CLAUDE_CONFIG_DIR (default ~/.claude) · GROUNDWORK_BACKUP_DIR (default ~/.claude-backups)
#              GROUNDWORK_SETUP_SKIP_TESTS=1 skips the deterministic test run during setup.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
BACKUP_ROOT="${GROUNDWORK_BACKUP_DIR:-$HOME/.claude-backups}"
INSTALLER="${GROUNDWORK_INSTALLER:-$HERE/install.sh}"          # override exists for the test suite only
UNINSTALLER="${GROUNDWORK_UNINSTALLER:-$HERE/uninstall.sh}"
REPORT="$CLAUDE_DIR/groundwork/bin/groundwork_report.py"
DISABLED_PREFIX="${CLAUDE_DIR}-groundwork-disabled"

say()  { printf '%s\n' "$*"; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
ts()   { date +%Y%m%d-%H%M%S; }

MODE=setup
NONINT=0
PROFILE=""
TEAMS=""          # yes | no | ""
SCHEDULE=""       # weekly | daily | monthly | yearly | disabled | ""
ROLLBACK_DIR=""
BACKUP_PATH=""

while [ $# -gt 0 ]; do
  case "$1" in
    --verify) [ "$MODE" = setup ] || die "cannot combine --$MODE with --verify"; MODE=verify ;;
    --rollback) [ "$MODE" = setup ] || die "cannot combine --$MODE with --rollback"; MODE=rollback; if [ $# -gt 1 ] && [ "${2#--}" = "$2" ]; then ROLLBACK_DIR="$2"; shift; fi ;;
    --uninstall) [ "$MODE" = setup ] || die "cannot combine --$MODE with --uninstall"; MODE=uninstall ;;
    --non-interactive) NONINT=1 ;;
    --profile) [ $# -gt 1 ] && [ "${2#--}" = "$2" ] || die "--profile requires a value (e.g. --profile work)"; PROFILE="$2"; shift ;;
    --agent-teams) TEAMS=yes ;;
    --no-agent-teams) TEAMS=no ;;
    --schedule) [ $# -gt 1 ] && [ "${2#--}" = "$2" ] || die "--schedule requires a value: weekly|daily|monthly|yearly|disabled"; SCHEDULE="$2"; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)"; exit 1 ;;
  esac
  shift
done

# ---------------------------------------------------------------- prerequisites
check_prereqs() {
  local missing=()
  command -v claude  >/dev/null 2>&1 || missing+=("Claude Code ('claude' not on PATH) — https://claude.com/claude-code")
  command -v node    >/dev/null 2>&1 || missing+=("Node.js ('node' not on PATH, >= 18 needed)")
  command -v npm     >/dev/null 2>&1 || missing+=("npm")
  command -v git     >/dev/null 2>&1 || missing+=("git")
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null \
      || missing+=("Python 3.10+ (found $(python3 --version 2>&1))")
  else
    missing+=("Python 3.10+ ('python3' not on PATH)")
  fi
  if [ ${#missing[@]} -gt 0 ]; then
    say "Missing prerequisites:"
    for m in "${missing[@]}"; do say "  - $m"; done
    die "install the missing prerequisites and run ./setup.sh again (nothing was changed)"
  fi
  say "Prerequisites: claude, node, npm, git, python3 $(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])') — OK"
}

# ---------------------------------------------------------------- backup
make_backup() {
  local dest="$BACKUP_ROOT/groundwork-$(ts)" n=1
  while [ -e "$dest" ]; do dest="$BACKUP_ROOT/groundwork-$(ts)-$n"; n=$((n + 1)); done   # never overwrite
  mkdir -p "$dest"
  chmod 700 "$BACKUP_ROOT" "$dest"
  if [ -d "$CLAUDE_DIR" ]; then
    # clonefile copy on APFS (instant, space-efficient), plain recursive copy elsewhere
    cp -Rpc "$CLAUDE_DIR" "$dest/claude" 2>/dev/null || cp -Rp "$CLAUDE_DIR" "$dest/claude"
    chmod -R go-rwx "$dest" 2>/dev/null || true
    printf 'source=%s\nexisted=yes\ncreated=%s\ngroundwork_version_before=%s\n' \
      "$CLAUDE_DIR" "$(date '+%Y-%m-%d %H:%M:%S')" "$(cat "$CLAUDE_DIR/groundwork/VERSION" 2>/dev/null || echo none)" > "$dest/BACKUP-INFO.txt"
  else
    printf 'source=%s\nexisted=no\ncreated=%s\n' "$CLAUDE_DIR" "$(date '+%Y-%m-%d %H:%M:%S')" > "$dest/BACKUP-INFO.txt"
  fi
  chmod 600 "$dest/BACKUP-INFO.txt"
  BACKUP_PATH="$dest"
}

on_setup_failure() {
  local rc=$?
  trap - ERR
  say ""
  say "Setup FAILED (exit $rc). Your previous configuration was not deleted."
  [ -n "$BACKUP_PATH" ] && say "Backup:   $BACKUP_PATH"
  say "Rollback: ./setup.sh --rollback"
  exit "$rc"
}

# ---------------------------------------------------------------- questions
ask() {  # ask VAR "prompt" default  — reads one line; empty input keeps the default
  local __var="$1" prompt="$2" default="$3" reply=""
  if [ "$NONINT" = 1 ]; then printf -v "$__var" '%s' "$default"; return; fi
  printf '%s [%s]: ' "$prompt" "$default"
  IFS= read -r reply || reply=""
  printf -v "$__var" '%s' "${reply:-$default}"
}

choose_profile() {
  if [ -n "$PROFILE" ]; then return; fi
  if [ "$NONINT" = 1 ]; then return; fi
  say ""
  say "Which Groundwork profile should this machine use?"
  say "  1. Work"
  say "  2. Personal"
  say "  3. Other"
  local c=""; ask c "Choice" "1"
  case "$c" in
    1) PROFILE=work ;;
    2) PROFILE=personal ;;
    3) ask PROFILE "Profile name (letters, digits, - or _)" "" ;;
    *) die "invalid choice: $c" ;;
  esac
}

choose_teams() {
  if [ -n "$TEAMS" ]; then return; fi
  if [ "$NONINT" = 1 ]; then TEAMS=no; return; fi
  say ""
  say "Enable Claude Code Agent Teams? (experimental; interactive sessions only)"
  say "  1. No — recommended default"
  say "  2. Yes"
  local c=""; ask c "Choice" "1"
  case "$c" in 1) TEAMS=no ;; 2) TEAMS=yes ;; *) die "invalid choice: $c" ;; esac
}

choose_schedule() {
  if [ -n "$SCHEDULE" ]; then return; fi
  if [ "$NONINT" = 1 ]; then SCHEDULE=weekly; return; fi
  say ""
  say "Groundwork health dashboard schedule:"
  say "  1. Weekly — recommended"
  say "  2. Daily"
  say "  3. Monthly"
  say "  4. Yearly"
  say "  5. Disabled"
  local c=""; ask c "Choice" "1"
  case "$c" in 1) SCHEDULE=weekly ;; 2) SCHEDULE=daily ;; 3) SCHEDULE=monthly ;; 4) SCHEDULE=yearly ;; 5) SCHEDULE=disabled ;; *) die "invalid choice: $c" ;; esac
}

validate_choices() {
  if [ -n "$PROFILE" ] && ! printf '%s' "$PROFILE" | grep -Eq '^[A-Za-z0-9_-]{1,32}$'; then
    die "profile must be 1-32 letters, digits, - or _ (got: $PROFILE)"
  fi
  PROFILE="$(printf '%s' "$PROFILE" | tr '[:upper:]' '[:lower:]')"
  case "$SCHEDULE" in weekly|daily|monthly|yearly|disabled) ;; *) die "schedule must be weekly|daily|monthly|yearly|disabled (got: $SCHEDULE)" ;; esac
}

# ---------------------------------------------------------------- verification (read-only)
count_files() { if [ -d "$1" ]; then find "$1" -maxdepth 1 -name "$2" 2>/dev/null | wc -l | tr -d ' '; else echo 0; fi; }

hooks_registered() {  # prints the number of Groundwork hook commands registered in settings.json
  python3 - "$CLAUDE_DIR/settings.json" <<'PY' 2>/dev/null || echo 0
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(0); sys.exit()
n = 0
for ev in ("PreToolUse", "Stop", "SessionStart"):
    for g in d.get("hooks", {}).get(ev, []):
        for h in g.get("hooks", []):
            if "groundwork" in h.get("command", "") or "block_protected_push" in h.get("command", "") or "require_material_review" in h.get("command", ""):
                n += 1
print(n)
PY
}

settings_env() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("env",{}).get(sys.argv[2],""))' "$CLAUDE_DIR/settings.json" "$1" 2>/dev/null || true; }

VERIFY_FAILS=0
line() {  # line LABEL STATE detail
  local label="$1" state="$2" detail="${3:-}"
  [ "$state" = FAIL ] && VERIFY_FAILS=$((VERIFY_FAILS + 1))
  printf '  %-19s %-15s %s\n' "$label" "$state" "$detail"
}

verify_install() {
  VERIFY_FAILS=0
  local v rules pbs hooks reg tel sched
  v="$(cat "$CLAUDE_DIR/groundwork/VERSION" 2>/dev/null || true)"
  if [ -n "$v" ]; then line "Groundwork version" PASS "$v"; else line "Groundwork version" "NOT CONFIGURED" "no $CLAUDE_DIR/groundwork/VERSION"; VERIFY_FAILS=$((VERIFY_FAILS + 1)); fi
  rules="$(count_files "$CLAUDE_DIR/rules/groundwork" '*.md')"
  if [ "$rules" -ge 5 ]; then line "Rules" PASS "$rules rule files"; else line "Rules" FAIL "$rules of 5 rule files under rules/groundwork"; fi
  pbs="$(count_files "$CLAUDE_DIR/groundwork/playbooks" '*.md')"
  if [ "$pbs" -ge 10 ]; then line "Playbooks" PASS "$pbs playbooks"; else line "Playbooks" FAIL "$pbs of 10 playbooks"; fi
  hooks=0; for h in block_protected_push require_material_review groundwork_session_snapshot groundwork_telemetry; do [ -f "$CLAUDE_DIR/hooks/$h.py" ] && hooks=$((hooks + 1)); done
  reg="$(hooks_registered)"
  if [ "$hooks" -eq 4 ] && [ "$reg" -ge 4 ]; then line "Hooks" PASS "4 hook files, $reg registered in settings.json"; else line "Hooks" FAIL "$hooks of 4 hook files, $reg registered"; fi
  if command -v claude >/dev/null 2>&1; then
    if claude plugin list 2>/dev/null | grep -q "ecc@ecc"; then line "ECC" PASS "plugin ecc@ecc"; else line "ECC" "NOT CONFIGURED" "plugin ecc@ecc not listed by 'claude plugin list'"; VERIFY_FAILS=$((VERIFY_FAILS + 1)); fi
  else line "ECC" FAIL "'claude' not on PATH"; fi
  if command -v openspec >/dev/null 2>&1; then line "OpenSpec" PASS "$(openspec --version 2>/dev/null | head -1)"; else line "OpenSpec" "NOT CONFIGURED" "'openspec' not on PATH"; VERIFY_FAILS=$((VERIFY_FAILS + 1)); fi
  if [ -f "$CLAUDE_DIR/hooks/groundwork_telemetry.py" ] && [ "$reg" -ge 4 ]; then
    tel=0; [ -f "$CLAUDE_DIR/groundwork/telemetry/events.jsonl" ] && tel="$(wc -l < "$CLAUDE_DIR/groundwork/telemetry/events.jsonl" | tr -d ' ')"
    line "Telemetry" PASS "hook registered, ${tel:-0} records, profile: $(settings_env GROUNDWORK_PROFILE | sed 's/^$/not set/')"
  else line "Telemetry" FAIL "telemetry hook missing or not registered"; fi
  if [ -f "$CLAUDE_DIR/groundwork/reports/dashboard.html" ]; then line "Dashboard" PASS "$CLAUDE_DIR/groundwork/reports/dashboard.html"; else line "Dashboard" "NOT CONFIGURED" "not generated yet (python3 $REPORT generate)"; fi
  if [ -f "$REPORT" ]; then
    sched="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("schedule","weekly"))' "$CLAUDE_DIR/groundwork/report.json" 2>/dev/null || echo weekly)"
    line "Reporting schedule" PASS "$sched (generator installed)"
  else line "Reporting schedule" FAIL "report generator missing at $REPORT"; fi
  if [ "$VERIFY_FAILS" -eq 0 ]; then line "Overall" PASS "all checks passed"; else line "Overall" FAIL "$VERIFY_FAILS check(s) need attention"; fi
  [ "$VERIFY_FAILS" -eq 0 ]
}

# ---------------------------------------------------------------- modes
run_setup() {
  say "== Groundwork setup =="
  say "Target: $CLAUDE_DIR"
  check_prereqs
  [ -f "$INSTALLER" ] || die "installer not found: $INSTALLER"
  say ""
  say "Backing up the current Claude configuration (complete $CLAUDE_DIR)..."
  make_backup
  say "Backup: $BACKUP_PATH"
  trap on_setup_failure ERR
  choose_profile; choose_teams; choose_schedule; validate_choices
  say ""
  say "-- Running install.sh (the actual installer) --"
  local install_args=()
  [ "$TEAMS" = yes ] && install_args+=("--agent-teams")
  bash "$INSTALLER" "${install_args[@]+"${install_args[@]}"}"
  if [ -n "$PROFILE" ]; then
    python3 "$HERE/scripts/merge_settings.py" --profile "$PROFILE" "$CLAUDE_DIR/settings.json" >/dev/null
  fi
  say ""
  say "-- Reporting schedule: $SCHEDULE --"
  [ -f "$REPORT" ] || die "report generator was not installed at $REPORT"
  python3 "$REPORT" schedule "$SCHEDULE" >/dev/null
  say ""
  say "-- First dashboard --"
  python3 "$REPORT" generate --snapshot | tail -1
  say ""
  say "-- Verification --"
  local validation=passed
  if [ "${GROUNDWORK_SETUP_SKIP_TESTS:-0}" != 1 ]; then
    if python3 "$HERE/tests/test_hooks.py" >/dev/null 2>&1 && python3 "$HERE/tests/test_telemetry.py" >/dev/null 2>&1; then
      say "Deterministic tests: passed (tests/test_hooks.py, tests/test_telemetry.py)"
    else
      validation=failed; say "Deterministic tests: FAILED — run python3 tests/test_hooks.py and python3 tests/test_telemetry.py to see why"
    fi
  else
    validation=skipped; say "Deterministic tests: skipped (GROUNDWORK_SETUP_SKIP_TESTS=1)"
  fi
  verify_install || validation=failed
  trap - ERR
  say ""
  say "Groundwork $(cat "$CLAUDE_DIR/groundwork/VERSION") installed successfully."
  say "Profile:       ${PROFILE:-not set (telemetry records 'unknown'; set later: python3 scripts/merge_settings.py --profile NAME $CLAUDE_DIR/settings.json)}"
  say "Agent Teams:   $([ "$TEAMS" = yes ] && echo enabled || echo disabled)"
  say "Reports:       $SCHEDULE"
  say "Validation:    $validation"
  say "Backup:"
  say "  $BACKUP_PATH"
  say "Dashboard:"
  say "  $CLAUDE_DIR/groundwork/reports/dashboard.html"
  say "Start Claude:"
  say "  claude"
  say "Verify later:"
  say "  ./setup.sh --verify"
  say "Rollback:"
  say "  ./setup.sh --rollback"
  [ "$validation" != failed ]
}

run_verify() {
  say "== Groundwork verification (read-only) =="
  say "Target: $CLAUDE_DIR"
  verify_install
}

latest_backup() {  # prints the newest unambiguous backup dir, or fails
  local dirs=() d
  [ -d "$BACKUP_ROOT" ] || die "no backups directory at $BACKUP_ROOT — nothing to roll back to"
  while IFS= read -r d; do dirs+=("$d"); done < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'groundwork-*' | sort)
  [ ${#dirs[@]} -gt 0 ] || die "no setup.sh backups under $BACKUP_ROOT — nothing to roll back to"
  local newest="${dirs[${#dirs[@]}-1]}" stamp
  stamp="$(basename "$newest" | grep -oE '[0-9]{8}-[0-9]{6}' || true)"
  local same=0
  for d in "${dirs[@]}"; do case "$(basename "$d")" in "groundwork-$stamp"|"groundwork-$stamp-"*) same=$((same + 1)) ;; esac; done
  if [ "$same" -gt 1 ]; then
    die "ambiguous: $same backups share the timestamp $stamp — pass the one you want explicitly: ./setup.sh --rollback <backup dir>"
  fi
  [ -f "$newest/BACKUP-INFO.txt" ] || die "newest backup $newest has no BACKUP-INFO.txt — not a setup.sh backup; pass a backup dir explicitly"
  printf '%s\n' "$newest"
}

run_rollback() {
  say "== Groundwork rollback =="
  local b="$ROLLBACK_DIR"
  [ -n "$b" ] || b="$(latest_backup)"
  [ -d "$b" ] || die "backup directory not found: $b"
  [ -f "$b/BACKUP-INFO.txt" ] || die "$b is not a setup.sh backup (no BACKUP-INFO.txt)"
  local src existed
  src="$(sed -n 's/^source=//p' "$b/BACKUP-INFO.txt")"
  existed="$(sed -n 's/^existed=//p' "$b/BACKUP-INFO.txt")"
  [ "$src" = "$CLAUDE_DIR" ] || die "backup $b was taken from $src, not $CLAUDE_DIR — refusing to guess"
  if [ -f "$REPORT" ]; then python3 "$REPORT" schedule disabled >/dev/null 2>&1 || true; fi   # no orphaned launchd job
  local disabled="$DISABLED_PREFIX-$(ts)" n=1
  while [ -e "$disabled" ]; do disabled="$DISABLED_PREFIX-$(ts)-$n"; n=$((n + 1)); done
  if [ -d "$CLAUDE_DIR" ]; then
    mv "$CLAUDE_DIR" "$disabled"
    say "Current setup saved to:"
    say "  $disabled/"
  fi
  if [ "$existed" = yes ]; then
    if [ ! -d "$b/claude" ]; then
      die "restore failed: $b has no claude/ copy to restore (your current setup is intact at $disabled)"
    fi
    if ! cp -Rpc "$b/claude" "$CLAUDE_DIR" 2>/dev/null && ! cp -Rp "$b/claude" "$CLAUDE_DIR"; then
      die "restore failed: could not copy $b/claude to $CLAUDE_DIR (your current setup is intact at $disabled)"
    fi
    [ -d "$CLAUDE_DIR" ] && [ -r "$CLAUDE_DIR" ] || die "restore failed: $CLAUDE_DIR is missing or unreadable (your current setup is intact at $disabled)"
    if [ -f "$b/claude/settings.json" ]; then [ -r "$CLAUDE_DIR/settings.json" ] || die "restore failed: settings.json unreadable"; fi
    say "Restored:"
    say "  $b/"
  else
    say "Restored:"
    say "  (no Claude configuration existed before Groundwork — $CLAUDE_DIR left absent)"
  fi
  say "Rollback complete."
  say "Restart Claude Code."
}

run_uninstall() {
  [ -f "$UNINSTALLER" ] || die "uninstaller not found: $UNINSTALLER"
  bash "$UNINSTALLER"
}

case "$MODE" in
  setup) run_setup ;;
  verify) run_verify ;;
  rollback) run_rollback ;;
  uninstall) run_uninstall ;;
esac
