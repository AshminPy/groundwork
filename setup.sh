#!/usr/bin/env bash
# Groundwork one-click onboarding — a thin, user-friendly wrapper around the tested installer.
#
#   ./setup.sh                      first-time setup: prerequisites → backup → your choices →
#                                   install.sh → reporting schedule → verification → first dashboard
#   ./setup.sh --non-interactive [--profile NAME] [--agent-teams | --no-agent-teams] [--schedule FREQ]
#                                   [--install-prereqs | --no-install-prereqs]
#   Claude Code must already be installed. The other prerequisites (git, Node 20.19+, npm, Python 3.10+)
#   are detected per OS and, after you say yes, installed with the official packages:
#   Homebrew on macOS, apt / dnf / apk on Linux.
#   ./setup.sh --verify             read-only check of the current installation (changes nothing)
#   ./setup.sh --rollback [DIR]     restore the latest backup made by setup.sh (or the given backup DIR)
#   ./setup.sh --uninstall          delegates to uninstall.sh (telemetry and reports are kept)
#   ./setup.sh --doctor             read-only: Groundwork/ECC/OpenSpec plus configured capabilities and Routines
#   ./setup.sh --configure          re-run the optional capability/Routines selection only (no backup/reinstall)
#   ./setup.sh --routines           list configured Routines and their last-run status
#   ./setup.sh --routines NAME      print the most recent stored result for one routine
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
INSTALL_PREREQS=""   # yes | no | "" (ask)
INSTALLED_PREREQS="no"
PROFILE=""
CAP_PROFILE=""    # sre-cloudops | platform-engineering | devops | software-engineering |
                  # cloud-architecture | security-engineering | minimal | custom | "" (ask)
TEAMS=""          # yes | no | ""
SCHEDULE=""       # weekly | daily | monthly | yearly | disabled | ""
ROLLBACK_DIR=""
ROUTINE_NAME=""
BACKUP_PATH=""
CONFIG_PY="$CLAUDE_DIR/groundwork/bin/groundwork_config.py"
ROUTINES_PY="$CLAUDE_DIR/groundwork/bin/groundwork_routines.py"

while [ $# -gt 0 ]; do
  case "$1" in
    --verify) [ "$MODE" = setup ] || die "cannot combine --$MODE with --verify"; MODE=verify ;;
    --rollback) [ "$MODE" = setup ] || die "cannot combine --$MODE with --rollback"; MODE=rollback; if [ $# -gt 1 ] && [ "${2#--}" = "$2" ]; then ROLLBACK_DIR="$2"; shift; fi ;;
    --uninstall) [ "$MODE" = setup ] || die "cannot combine --$MODE with --uninstall"; MODE=uninstall ;;
    --doctor) [ "$MODE" = setup ] || die "cannot combine --$MODE with --doctor"; MODE=doctor ;;
    --configure) [ "$MODE" = setup ] || die "cannot combine --$MODE with --configure"; MODE=configure ;;
    --routines) [ "$MODE" = setup ] || die "cannot combine --$MODE with --routines"; MODE=routines; if [ $# -gt 1 ] && [ "${2#--}" = "$2" ]; then ROUTINE_NAME="$2"; shift; fi ;;
    --non-interactive) NONINT=1 ;;
    --install-prereqs) INSTALL_PREREQS=yes ;;
    --no-install-prereqs) INSTALL_PREREQS=no ;;
    --profile) [ $# -gt 1 ] && [ "${2#--}" = "$2" ] || die "--profile requires a value (e.g. --profile work)"; PROFILE="$2"; shift ;;
    --capability-profile) [ $# -gt 1 ] && [ "${2#--}" = "$2" ] || die "--capability-profile requires a value (e.g. --capability-profile sre-cloudops)"; CAP_PROFILE="$2"; shift ;;
    --agent-teams) TEAMS=yes ;;
    --no-agent-teams) TEAMS=no ;;
    --schedule) [ $# -gt 1 ] && [ "${2#--}" = "$2" ] || die "--schedule requires a value: weekly|daily|monthly|yearly|disabled"; SCHEDULE="$2"; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1 (see --help)"; exit 1 ;;
  esac
  shift
done

# ---------------------------------------------------------------- prerequisites
# OS-aware: macOS installs via Homebrew, Linux via apt / dnf / apk, always with the official
# package or installer, only after you say yes (or --install-prereqs). Nothing is changed before
# the question, and the check is repeated after installing.
OS_KIND="${GROUNDWORK_OS:-$(uname -s | tr '[:upper:]' '[:lower:]')}"   # darwin | linux (override is for tests)
PKG=""
MISSING=()
NODE_MIN_MAJOR=20; NODE_MIN_MINOR=19   # matches OpenSpec's actual engines.node (>=20.19.0), not ECC's lower floor
PY_MIN_MAJOR=3; PY_MIN_MINOR=10
LAST_VERIFIED_OPENSPEC="1.13.2"   # OpenSpec is npm-pinned by version; a mismatch here means real upstream drift
ECC_REF="${GROUNDWORK_ECC_REF:-v2.2.1}"   # Groundwork 2.1: install.sh pins ECC to this ref (see install.sh); kept in sync with it, not independently drifting

detect_pm() {
  case "$OS_KIND" in
    darwin) command -v brew >/dev/null 2>&1 && PKG=brew || PKG=none ;;
    linux)
      if command -v apt-get >/dev/null 2>&1; then PKG=apt
      elif command -v dnf >/dev/null 2>&1; then PKG=dnf
      elif command -v apk >/dev/null 2>&1; then PKG=apk
      else PKG=none; fi ;;
    *) PKG=none ;;
  esac
}

refresh_path() {  # make freshly installed tools visible in this run
  if [ "$OS_KIND" = darwin ] && [ -z "${GROUNDWORK_OS:-}" ] && ! command -v brew >/dev/null 2>&1; then
    for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" 2>/dev/null && break; done
  fi
  case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) PATH="$HOME/.local/bin:$PATH" ;; esac
  hash -r 2>/dev/null || true
}

node_ok() {
  command -v node >/dev/null 2>&1 || return 1
  local major minor
  major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  minor="$(node -p 'process.versions.node.split(".")[1]' 2>/dev/null || echo 0)"
  [ "$major" -gt "$NODE_MIN_MAJOR" ] && return 0
  [ "$major" -eq "$NODE_MIN_MAJOR" ] && [ "$minor" -ge "$NODE_MIN_MINOR" ] && return 0
  return 1
}
py_ok()   { command -v python3 >/dev/null 2>&1 && python3 -c "import sys; sys.exit(0 if sys.version_info >= ($PY_MIN_MAJOR, $PY_MIN_MINOR) else 1)" 2>/dev/null; }

find_missing() {
  MISSING=()
  command -v git >/dev/null 2>&1 || MISSING+=(git)
  node_ok || MISSING+=(node)
  command -v npm >/dev/null 2>&1 || { node_ok || true; case " ${MISSING[*]:-} " in *" node "*) ;; *) MISSING+=(npm) ;; esac; }
  py_ok || MISSING+=(python3)
  command -v claude >/dev/null 2>&1 || MISSING+=(claude)
}

describe_missing() {
  local t
  for t in "${MISSING[@]}"; do
    case "$t" in
      git) say "  - git" ;;
      node) if command -v node >/dev/null 2>&1; then say "  - Node.js >= $NODE_MIN_MAJOR.$NODE_MIN_MINOR.0 (found $(node --version 2>/dev/null))"; else say "  - Node.js >= $NODE_MIN_MAJOR.$NODE_MIN_MINOR.0 (with npm)"; fi ;;
      npm) say "  - npm" ;;
      python3) if command -v python3 >/dev/null 2>&1; then say "  - Python $PY_MIN_MAJOR.$PY_MIN_MINOR+ (found $(python3 --version 2>&1))"; else say "  - Python $PY_MIN_MAJOR.$PY_MIN_MINOR+"; fi ;;
      claude) say "  - Claude Code (https://code.claude.com/docs/en/setup)" ;;
    esac
  done
}

install_cmd() {  # prints the official command(s) for one tool on this OS / package manager
  local t="$1"
  case "$PKG:$t" in
    brew:git)      echo "brew install git" ;;
    brew:node|brew:npm) echo "brew install node" ;;
    brew:python3)  echo "brew install python@3.12" ;;
    apt:git)       echo "sudo apt-get install -y git" ;;
    apt:node|apt:npm) echo "sudo apt-get install -y nodejs npm" ;;
    apt:python3)   echo "sudo apt-get install -y python3" ;;
    dnf:git)       echo "sudo dnf install -y git" ;;
    dnf:node|dnf:npm) echo "sudo dnf install -y nodejs npm" ;;
    dnf:python3)   echo "sudo dnf install -y python3" ;;
    apk:git)       echo "sudo apk add git" ;;
    apk:node|apk:npm) echo "sudo apk add nodejs npm" ;;
    apk:python3)   echo "sudo apk add python3" ;;
    *) return 1 ;;
  esac
}

run_install() {  # run one install command; sudo is dropped when already root; apt refreshes its index first
  local cmd="$1"
  if [ "$(id -u)" = 0 ]; then cmd="${cmd#sudo }"; fi
  case "$cmd" in *apt-get\ install*) ( set +e; ${cmd%%install*}update -qq >/dev/null 2>&1 ); ;; esac
  say "  \$ $cmd"
  bash -c "$cmd"
}

check_prereqs() {
  detect_pm
  refresh_path
  find_missing
  if [ ${#MISSING[@]} -eq 0 ]; then
    say "Prerequisites: git, node $(node --version 2>/dev/null), npm, python3 $(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])'), claude — OK"
    return
  fi
  say "Missing prerequisites on this machine ($OS_KIND):"
  describe_missing
  # Claude Code is required but never installed by this script: it is the product being configured,
  # and its login is interactive. Everything else (git, Node, npm, Python) can be installed below.
  case " ${MISSING[*]} " in *" claude "*)
    die "Claude Code is not installed (or not on PATH). Install it first — https://code.claude.com/docs/en/setup — sign in once with 'claude', then run ./setup.sh again (nothing was changed)" ;;
  esac
  # a Node.js that exists but is too old is left alone: it is usually managed by nvm/asdf/volta
  if command -v node >/dev/null 2>&1 && ! node_ok; then
    die "Node.js $(node --version) is older than $NODE_MIN_MAJOR.$NODE_MIN_MINOR.0. Upgrade it with your Node version manager (nvm/asdf/volta) or from https://nodejs.org/en/download, then run ./setup.sh again (nothing was changed)"
  fi
  if [ "$PKG" = none ]; then
    if [ "$OS_KIND" = darwin ]; then
      say ""
      say "Homebrew is needed to install these on macOS. Install it with the official command, then run ./setup.sh again:"
      say '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
      die "Homebrew not found (nothing was changed)"
    fi
    die "no supported package manager found (apt-get, dnf or apk) — install the items above yourself, then run ./setup.sh again (nothing was changed)"
  fi
  say ""
  say "They can be installed now with $PKG using the official packages:"
  local t
  for t in "${MISSING[@]}"; do say "  $(install_cmd "$t")"; done
  if [ "$INSTALL_PREREQS" = no ]; then
    die "install them yourself, then run ./setup.sh again (--no-install-prereqs given; nothing was changed)"
  fi
  if [ "$INSTALL_PREREQS" != yes ]; then
    if [ "$NONINT" = 1 ]; then
      die "prerequisites missing and --install-prereqs not given — run the commands above, or re-run with --install-prereqs (nothing was changed)"
    fi
    local a=""; ask a "Install them now? (y/n)" "y"
    case "$a" in y|Y|yes|YES) ;; *) die "not installing — run the commands above, then ./setup.sh again (nothing was changed)" ;; esac
  fi
  if [ "$OS_KIND" = linux ] && [ "$(id -u)" != 0 ] && [ "$NONINT" = 1 ] && ! sudo -n true 2>/dev/null; then
    die "sudo needs a password, which --non-interactive cannot provide — run the commands above, then ./setup.sh again"
  fi
  say ""
  say "-- Installing prerequisites with $PKG --"
  local done_node=0
  for t in "${MISSING[@]}"; do
    case "$t" in node|npm) [ "$done_node" = 1 ] && continue; done_node=1 ;; esac
    run_install "$(install_cmd "$t")" || die "installing $t failed — fix the error above, then run ./setup.sh again (nothing else was changed)"
  done
  refresh_path
  find_missing
  if [ ${#MISSING[@]} -gt 0 ]; then
    case " ${MISSING[*]} " in
      *" node "*)
        if command -v node >/dev/null 2>&1 && ! node_ok; then
          die "Node.js is now installed ($(node --version)) but it is still older than $NODE_MIN_MAJOR.$NODE_MIN_MINOR.0 — this is expected from $PKG's default package on many Linux distros, which lags upstream Node releases. A new terminal will not fix this. Install a current Node with a version manager (nvm: https://github.com/nvm-sh/nvm, or asdf/volta) or from the NodeSource repository (https://github.com/nodesource/distributions), then run ./setup.sh again."
        fi
        ;;
    esac
    say "Still missing after installation:"; describe_missing
    die "open a new terminal (so PATH picks up the new tools) and run ./setup.sh again"
  fi
  INSTALLED_PREREQS="yes ($PKG)"
  say "Prerequisites installed. Note: open a new terminal later so your shell sees them too."
  say "Prerequisites: git, node $(node --version 2>/dev/null), npm, python3 $(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])'), claude — OK"
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

pick_cap_profile() {  # just the profile menu — shared by first-time setup and --configure option 1
  say ""
  say "Profile (a starting point, not a forced install — every capability and Routine stays"
  say "individually toggleable afterward with ./setup.sh --configure):"
  say "  1. SRE / CloudOps          5. Cloud Architecture"
  say "  2. Platform Engineering    6. Security Engineering"
  say "  3. DevOps                  7. Minimal"
  say "  4. Software Engineering    8. Custom (blank — configure entirely by hand)"
  local p=""; ask p "Choice" "1"
  case "$p" in
    1) CAP_PROFILE=sre-cloudops ;; 2) CAP_PROFILE=platform-engineering ;; 3) CAP_PROFILE=devops ;;
    4) CAP_PROFILE=software-engineering ;; 5) CAP_PROFILE=cloud-architecture ;;
    6) CAP_PROFILE=security-engineering ;; 7) CAP_PROFILE=minimal ;; 8) CAP_PROFILE=custom ;;
    *) die "invalid choice: $p" ;;
  esac
}

choose_capabilities() {  # Groundwork 2.1: optional profile-driven capability/Routines selection
  if [ -n "$CAP_PROFILE" ]; then return; fi
  if [ "$NONINT" = 1 ]; then return; fi   # non-interactive: config.json stays absent, minimal profile, everything disabled
  say ""
  say "Configure optional capabilities and Routines (cloud/platform/integrations/skills/scheduled"
  say "automation like a Jira end-of-day update or a daily news digest)? This is entirely optional —"
  say "Groundwork's core governance works identically either way."
  say "  1. No — skip (recommended if you're not sure; revisit any time with ./setup.sh --configure)"
  say "  2. Yes — pick a profile"
  local c=""; ask c "Choice" "1"
  case "$c" in
    1) return ;;
    2) pick_cap_profile ;;
    *) die "invalid choice: $c" ;;
  esac
}

# ---------------------------------------------------------------- routine configuration contract
# Configure once, run automatically (owner requirement, added after the first release candidate):
# a routine's identity/scope/access/mutation-permission/schedule are collected ONCE here and saved
# to config.json — a scheduled run (scripts/groundwork_routines.py) never re-asks any of it. Only
# routines the user actually enabled are ever asked about (§14: no dumping every question on
# every user). All helpers below shell out to groundwork_config.py so the schema/validation logic
# lives in exactly one place (Python), never duplicated in bash.
cfg_get() { python3 "$CONFIG_PY" get "$1" "$2" --path "$CLAUDE_DIR/groundwork/config.json" 2>/dev/null || true; }
cfg_get_csv() {  # a list-typed field (e.g. news.topics) as a comma-joined string, for pre-filling `ask`
  python3 -c "
import json, sys
raw = sys.argv[1]
try:
    val = json.loads(raw) if raw else []
except Exception:
    val = []
print(', '.join(val) if isinstance(val, list) else '')
" "$(cfg_get "$1" "$2")" 2>/dev/null || true
}
csv_to_json() {  # comma-separated free text -> a JSON array of trimmed, non-empty strings
  python3 -c "
import json, sys
items = [s.strip() for s in sys.argv[1].split(',') if s.strip()]
print(json.dumps(items))
" "$1" 2>/dev/null || echo "[]"
}
cfg_set() {  # cfg_set ROUTINE KEY=VALUE [KEY=VALUE...] — validates before writing; a rejected
             # assignment (invalid enum value, bad JSON) leaves the previously-saved file untouched.
  local routine="$1"; shift
  if ! python3 "$CONFIG_PY" set "$routine" "$@" --path "$CLAUDE_DIR/groundwork/config.json" >/dev/null; then
    say "  (could not save that — kept the previous value)"
  fi
}

configure_routine_jira_eod() {
  say ""
  say "Jira end-of-day update — reviews today's evidenced work, drafts (and optionally posts) a Jira comment."
  local en=""; say "Enable? 1. No  2. Yes"
  ask en "Choice" "$([ "$(cfg_get jira_eod enabled)" = "True" ] && echo 2 || echo 1)"
  if [ "$en" != "2" ]; then cfg_set jira_eod enabled=false; return; fi
  local site="" identity="" acc="" mcp_server="" scope_choice="" projects="" jql="" posting_choice="" time=""
  ask site "Jira URL / site" "$(cfg_get jira_eod site)"
  ask identity "Jira identity (your email/username)" "$(cfg_get jira_eod identity)"
  say "Access:"
  say "  1. Existing Atlassian/Jira MCP"
  say "  2. CLI/API if supported"
  say "  3. Browser/Chrome"
  say "  4. Configure later"
  ask acc "Choice" "4"
  case "$acc" in
    1) acc=jira_mcp; ask mcp_server "MCP server name (as configured in Claude Code)" "$(cfg_get jira_eod mcp_server)"
       [ -n "$mcp_server" ] || mcp_server=atlassian ;;
    2) acc=cli ;;
    3) acc=browser ;;
    4) acc=unconfigured ;;
    *) die "invalid choice: $acc" ;;
  esac
  say "Ticket scope:"
  say "  1. Assigned to me"
  say "  2. Created by me"
  say "  3. Selected projects"
  say "  4. Custom JQL"
  ask scope_choice "Choice" "1"
  say "Posting:"
  say "  1. Dry-run only — recommended until you've reviewed a few drafts"
  say "  2. Post comments automatically"
  ask posting_choice "Choice" "1"
  local posting=dry_run; [ "$posting_choice" = "2" ] && posting=automatic
  local cur_time; cur_time="$(cfg_get jira_eod schedule.time)"
  ask time "Schedule time (HH:MM, 24h)" "${cur_time:-17:00}"
  [ -n "$time" ] || time="17:00"
  if [ "$acc" = "jira_mcp" ]; then
    cfg_set jira_eod enabled=true site="$site" identity="$identity" access="$acc" mcp_server="$mcp_server" \
      posting="$posting" schedule.frequency=daily "schedule.time=$time"
  else
    cfg_set jira_eod enabled=true site="$site" identity="$identity" access="$acc" \
      posting="$posting" schedule.frequency=daily "schedule.time=$time"
  fi
  case "$scope_choice" in
    1) cfg_set jira_eod scope.type=assigned_to_me ;;
    2) cfg_set jira_eod scope.type=created_by_me ;;
    3) ask projects "Comma-separated project keys" ""
       cfg_set jira_eod scope.type=projects "scope.projects=$(csv_to_json "$projects")" ;;
    4) ask jql "JQL" ""
       cfg_set jira_eod scope.type=custom_jql "scope.jql=$jql" ;;
    *) die "invalid choice: $scope_choice" ;;
  esac
}

configure_routine_pr_followup() {
  say ""
  say "GitHub PR follow-up — the configured identity's OWN pull requests needing attention (never"
  say "an unfiltered scan of every PR the account can see)."
  local en=""; say "Enable? 1. No  2. Yes"
  ask en "Choice" "$([ "$(cfg_get pr_followup enabled)" = "True" ] && echo 2 || echo 1)"
  if [ "$en" != "2" ]; then cfg_set pr_followup enabled=false; return; fi
  local suggested=""
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    suggested="$(gh api user --jq .login 2>/dev/null || true)"
  fi
  local identity=""
  ask identity "GitHub identity (username) — confirm this is right" "${suggested:-$(cfg_get pr_followup identity)}"
  say "Access:"
  say "  1. gh CLI"
  say "  2. GitHub MCP"
  say "  3. Configure later"
  local acc=""; ask acc "Choice" "$([ -n "$suggested" ] && echo 1 || echo 3)"
  case "$acc" in 1) acc=gh_cli ;; 2) acc=github_mcp ;; 3) acc=unconfigured ;; *) die "invalid choice: $acc" ;; esac
  say "Repository scope:"
  say "  1. Current repository"
  say "  2. Selected repositories"
  local repo_choice=""; ask repo_choice "Choice" "1"
  local repos_json='["current"]'
  if [ "$repo_choice" = "2" ]; then
    local repos=""; ask repos "Comma-separated owner/repo list" ""
    repos_json="$(csv_to_json "$repos")"
  fi
  local time=""; ask time "Schedule time (HH:MM, 24h)" "$(cfg_get pr_followup schedule.time)"
  [ -n "$time" ] || time="08:00"
  cfg_set pr_followup enabled=true identity="$identity" access="$acc" "scope.repositories=$repos_json" \
    schedule.frequency=daily "schedule.time=$time"
}

configure_routine_news() {
  say ""
  local en=""; say "Enable daily technical news digest? 1. No  2. Yes"
  ask en "Choice" "$([ "$(cfg_get news enabled)" = "True" ] && echo 2 || echo 1)"
  if [ "$en" != "2" ]; then cfg_set news enabled=false; return; fi
  say "Suggested topics: AI, Claude, Agentic AI, PKI, Cybersecurity, GCP, AWS, Kubernetes, Terraform, SRE"
  local topics=""
  ask topics "Topics (comma-separated; edit freely, arbitrary custom topics allowed)" \
    "$(cfg_get_csv news topics || echo 'AI, Claude, Kubernetes, AWS, GCP')"
  local time=""; ask time "Schedule time (HH:MM, 24h)" "$(cfg_get news schedule.time)"
  [ -n "$time" ] || time="08:00"
  cfg_set news enabled=true "topics=$(csv_to_json "$topics")" schedule.frequency=daily "schedule.time=$time"
}

configure_routine_weekly_status() {
  say ""
  local en=""; say "Enable weekly status summary? 1. No  2. Yes"
  ask en "Choice" "$([ "$(cfg_get weekly_status enabled)" = "True" ] && echo 2 || echo 1)"
  if [ "$en" != "2" ]; then cfg_set weekly_status enabled=false; return; fi
  local time=""; ask time "Schedule time (HH:MM, 24h)" "$(cfg_get weekly_status schedule.time)"
  [ -n "$time" ] || time="08:00"
  cfg_set weekly_status enabled=true schedule.frequency=weekly "schedule.time=$time"
  say "  (repository scope defaults to the current repository — edit $CLAUDE_DIR/groundwork/config.json directly for a multi-repo scope)"
}

configure_routine_work_digest() {
  say ""
  local en=""; say "Enable daily work/TODO digest? 1. No  2. Yes"
  ask en "Choice" "$([ "$(cfg_get work_digest enabled)" = "True" ] && echo 2 || echo 1)"
  if [ "$en" != "2" ]; then cfg_set work_digest enabled=false; return; fi
  local time=""; ask time "Schedule time (HH:MM, 24h)" "$(cfg_get work_digest schedule.time)"
  [ -n "$time" ] || time="08:00"
  # Reuses whichever GitHub/Jira access pr_followup/jira_eod already have configured — never asks
  # for a third, separate identity/access mechanism for the same external systems (§4 of the brief).
  local use_github=false use_jira=false
  [ "$(cfg_get pr_followup access)" != "unconfigured" ] && [ -n "$(cfg_get pr_followup access)" ] && use_github=true
  [ "$(cfg_get jira_eod access)" != "unconfigured" ] && [ -n "$(cfg_get jira_eod access)" ] && use_jira=true
  cfg_set work_digest enabled=true "use_github=$use_github" "use_jira=$use_jira" schedule.frequency=daily "schedule.time=$time"
}

configure_routine_doc_drift() {
  say ""
  local en=""; say "Enable documentation-drift check? 1. No  2. Yes"
  ask en "Choice" "$([ "$(cfg_get doc_drift enabled)" = "True" ] && echo 2 || echo 1)"
  if [ "$en" != "2" ]; then cfg_set doc_drift enabled=false; return; fi
  local time=""; ask time "Schedule time (HH:MM, 24h)" "$(cfg_get doc_drift schedule.time)"
  [ -n "$time" ] || time="08:00"
  cfg_set doc_drift enabled=true schedule.frequency=weekly "schedule.time=$time"
  say "  (documentation/implementation paths default to README.md, docs/ — edit $CLAUDE_DIR/groundwork/config.json directly to narrow them)"
}

configure_routines_interactive() {  # per-routine follow-up, only for routines actually enabled (§14)
  if [ "$NONINT" = 1 ]; then return; fi
  [ -f "$CONFIG_PY" ] || return
  [ -f "$CLAUDE_DIR/groundwork/config.json" ] || return
  say ""
  say "-- Routine configuration (only for what you enabled; press Enter to accept each default) --"
  if [ "$(cfg_get jira_eod enabled)" = "True" ]; then configure_routine_jira_eod; fi
  if [ "$(cfg_get pr_followup enabled)" = "True" ]; then configure_routine_pr_followup; fi
  if [ "$(cfg_get news enabled)" = "True" ]; then configure_routine_news; fi
  if [ "$(cfg_get weekly_status enabled)" = "True" ]; then configure_routine_weekly_status; fi
  if [ "$(cfg_get work_digest enabled)" = "True" ]; then configure_routine_work_digest; fi
  if [ "$(cfg_get doc_drift enabled)" = "True" ]; then configure_routine_doc_drift; fi
}

schedule_all_enabled_routines() {
  [ -f "$ROUTINES_PY" ] || return 0
  [ -f "$CLAUDE_DIR/groundwork/config.json" ] || return 0
  local cfgfile="$CLAUDE_DIR/groundwork/config.json"
  local enabled_routines
  enabled_routines="$(python3 -c "
import json
cfg = json.load(open('$cfgfile'))
names = [n for n, r in cfg.get('routines', {}).items() if r.get('enabled')]
print(', '.join(sorted(names)) or 'none')
" 2>/dev/null || echo "none")"
  say "  routines enabled: $enabled_routines"
  if [ "$enabled_routines" != "none" ]; then
    # `|| true` on the whole pipe, not just the loop body: under set -e/pipefail, a failure in the
    # inline Python here would otherwise abort setup entirely right after telling the user their
    # profile was applied — this step is best-effort scheduling, not a reason to fail an
    # already-successful capability-config write.
    python3 -c "
import json
cfg = json.load(open('$cfgfile'))
for name, r in cfg.get('routines', {}).items():
    if r.get('enabled'):
        sched = r.get('schedule', {})
        freq = sched.get('frequency', 'daily')
        time_ = sched.get('time', '08:00') or '08:00'
        hour, _, minute = time_.partition(':')
        print(name, freq, hour or '8', minute or '0')
" 2>/dev/null | while read -r rname rfreq rhour rminute; do
      python3 "$ROUTINES_PY" schedule "$rname" "$rfreq" --hour "$rhour" --minute "$rminute" >/dev/null 2>&1 || true
    done || true
    say "  (each enabled routine's schedule was applied the same way the dashboard's is — macOS launchd,"
    say "   cron elsewhere; verify any time with ./setup.sh --routines)"
  fi
}

apply_capabilities() {  # writes config.json from CAP_PROFILE, if one was chosen; safe to call when absent
  [ -n "$CAP_PROFILE" ] || return 0
  [ -f "$CONFIG_PY" ] || { say "  (capability configurator not installed — skipping)"; return 0; }
  python3 "$CONFIG_PY" init "$CAP_PROFILE" --force >/dev/null
  say "  capability profile: $CAP_PROFILE (edit $CLAUDE_DIR/groundwork/config.json to fine-tune, or run ./setup.sh --configure again)"
  configure_routines_interactive
  schedule_all_enabled_routines
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
    local ecc_list ecc_v
    ecc_list="$(claude plugin list 2>/dev/null)" || true
    if printf '%s\n' "$ecc_list" | grep -q "ecc@ecc"; then
      # `|| true` on the *statement*: under pipefail, a `grep 'Version:'` with no match (e.g. an
      # older/differently-formatted `claude plugin list`) fails the whole pipeline and would
      # otherwise silently abort --verify under set -e (same class of bug as the OpenSpec row above).
      ecc_v="$(printf '%s\n' "$ecc_list" | grep -A1 'ecc@ecc' | grep 'Version:' | head -1 | awk '{print $2}')" || true
      if [ -z "$ecc_v" ]; then
        line "ECC" PASS "plugin ecc@ecc installed (version not parsed from 'claude plugin list' output — run 'claude plugin details ecc@ecc' to see it)"
      elif [ "v$ecc_v" != "$ECC_REF" ] && [ "$ecc_v" != "$ECC_REF" ]; then
        # Groundwork 2.1 pins ECC to $ECC_REF (install.sh) rather than floating main — a mismatch
        # here usually means `claude plugin update ecc@ecc` was run manually outside that pin, or
        # GROUNDWORK_ECC_REF was overridden at install time; still PASS (not a broken install),
        # but surfaced distinctly from the expected, pinned-match case below.
        line "ECC" PASS "plugin ecc@ecc $ecc_v (pinned to $ECC_REF — this differs, likely from a manual 'claude plugin update' outside the pin)"
      else
        line "ECC" PASS "plugin ecc@ecc $ecc_v (pinned to $ECC_REF)"
      fi
    else line "ECC" "NOT CONFIGURED" "plugin ecc@ecc not listed by 'claude plugin list'"; VERIFY_FAILS=$((VERIFY_FAILS + 1)); fi
  else line "ECC" FAIL "'claude' not on PATH"; fi
  line "Node" $(node_ok && echo PASS || echo FAIL) "$(command -v node >/dev/null 2>&1 && node --version || echo 'not found'), need >= $NODE_MIN_MAJOR.$NODE_MIN_MINOR.0 (OpenSpec's own requirement)"
  if command -v openspec >/dev/null 2>&1; then
    local os_v
    os_v="$(openspec --version 2>/dev/null | head -1)" || true   # under set -e this command substitution's own
    # failure would otherwise abort --verify entirely (found by independent review of Phase 1) —
    # `|| true` on the *statement* neutralises that; os_v itself still correctly ends up empty.
    if [ -z "$os_v" ]; then
      line "OpenSpec" FAIL "'openspec' is on PATH but did not report a version — often means Node is too old to run it ($(node --version 2>/dev/null || echo 'no node')); see the Node row above"
      VERIFY_FAILS=$((VERIFY_FAILS + 1))
    elif [ "$os_v" != "$LAST_VERIFIED_OPENSPEC" ]; then
      line "OpenSpec" PASS "$os_v (last verified here: $LAST_VERIFIED_OPENSPEC — no network check performed; if OpenSpec commands misbehave, compare against its current release notes)"
    else
      line "OpenSpec" PASS "$os_v"
    fi
  else line "OpenSpec" "NOT CONFIGURED" "'openspec' not on PATH"; VERIFY_FAILS=$((VERIFY_FAILS + 1)); fi
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

verify_capabilities() {  # Groundwork 2.1: capability/Routines rows, additive to verify_install()
  if [ ! -f "$CLAUDE_DIR/groundwork/config.json" ]; then
    line "Capabilities" "NOT CONFIGURED" "no config.json — nothing selected (./setup.sh --configure to set one up)"
    return
  fi
  local cfg="$CLAUDE_DIR/groundwork/config.json"
  # Declared separately from the assignment (matches verify_install()'s own ecc_v pattern above):
  # `local x=$(cmd)` always returns `local`'s own exit status, masking a real command failure —
  # the exact class of bug independent-review finding M1 already fixed once in this file. A
  # malformed hand-edit of config.json (it's explicitly documented as hand-editable) must degrade
  # to one INVALID row, not silently abort the rest of --doctor under set -e.
  local cap_rows=""
  cap_rows="$(python3 -c "
import json
cfg = json.load(open('$cfg'))
print('PROFILE\t' + cfg.get('profile', 'unknown'))
for k in ('cloud', 'platform', 'integrations'):
    vals = cfg.get(k, [])
    print(k.upper() + '\t' + (', '.join(vals) if vals else '(none selected)'))
for name, s in cfg.get('skills', {}).items():
    print('SKILL\t' + name + '\t' + ('enabled' if s else 'disabled'))
" 2>/dev/null)" || cap_rows=""
  if [ -z "$cap_rows" ]; then
    line "Capabilities" "INVALID" "$cfg is not valid JSON (or is empty) — fix by hand or re-run ./setup.sh --configure"
  else
    printf '%s\n' "$cap_rows" | while IFS="$(printf '\t')" read -r kind a b; do
      case "$kind" in
        PROFILE) line "Capability profile" CONFIGURED "$a" ;;
        CLOUD) line "Cloud" CONFIGURED "$a — availability not connectivity-checked here; wire your own MCP/CLI per docs/INTEGRATIONS.md" ;;
        PLATFORM) line "Platform" CONFIGURED "$a" ;;
        INTEGRATIONS) line "Integrations" CONFIGURED "$a" ;;
        SKILL) line "Skill: $a" "$([ "$b" = enabled ] && echo AVAILABLE || echo DISABLED)" "" ;;
      esac
    done
  fi
  if [ -f "$ROUTINES_PY" ]; then
    say ""
    say "  -- Routines --"
    # Formatting lives entirely in groundwork_routines.py (format_doctor_text) so it's testable in
    # one place; this just indents and prints it. `|| true` — a routine-status failure must not
    # abort the rest of --doctor (same discipline as the Capabilities section above).
    python3 "$ROUTINES_PY" doctor 2>/dev/null | while IFS= read -r row; do say "  $row"; done || true
  fi
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
  choose_profile; choose_teams; choose_schedule; choose_capabilities; validate_choices
  say ""
  say "-- Running install.sh (the actual installer) --"
  local install_args=()
  [ "$TEAMS" = yes ] && install_args+=("--agent-teams")
  bash "$INSTALLER" "${install_args[@]+"${install_args[@]}"}"
  if [ -n "$PROFILE" ]; then
    python3 "$HERE/scripts/merge_settings.py" --profile "$PROFILE" "$CLAUDE_DIR/settings.json" >/dev/null
  fi
  if [ -n "$CAP_PROFILE" ]; then
    say ""
    say "-- Capabilities and Routines --"
    apply_capabilities
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
  say "Prereqs added: $INSTALLED_PREREQS"
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

run_doctor() {  # Groundwork 2.1: verify_install() plus capability/Routines status, still read-only
  say "== Groundwork doctor (read-only) =="
  say "Target: $CLAUDE_DIR"
  # verify_install's own failing checks must not short-circuit this function under `set -e` —
  # capability/Routines status is exactly what you need to see when core checks are already
  # failing, not something to silently drop. Exit code still reflects core health, same as --verify.
  local core_ok=0
  verify_install || core_ok=1
  say ""
  verify_capabilities
  [ "$core_ok" -eq 0 ]
}

run_configure() {  # Groundwork 2.1: re-run capability/Routines selection — no backup, no reinstall.
                    # Never requires reinstalling Groundwork (owner requirement §15).
  say "== Groundwork configure =="
  [ -d "$CLAUDE_DIR/groundwork" ] || die "Groundwork is not installed at $CLAUDE_DIR — run ./setup.sh first"
  if [ -n "$CAP_PROFILE" ]; then
    # --capability-profile passed explicitly: unchanged behavior, re-applies that profile then
    # runs the per-routine wizard for whatever it enables.
    apply_capabilities
    say ""
    say "Done. Check anytime with ./setup.sh --doctor or ./setup.sh --routines."
    return 0
  fi
  if [ "$NONINT" = 1 ]; then
    say "No change made (--non-interactive with no --capability-profile)."
    return 0
  fi
  say ""
  say "What would you like to change?"
  say "  1. Change capability profile (re-applies a profile's defaults, then asks about its routines)"
  say "  2. Reconfigure one routine (Jira URL, GitHub identity, scope, schedule, ...)"
  say "  3. Cancel — no change"
  local c=""; ask c "Choice" "3"
  case "$c" in
    1)
      [ -f "$CLAUDE_DIR/groundwork/config.json" ] || { say ""; say "No capability profile is configured yet."; }
      pick_cap_profile
      apply_capabilities
      say ""
      say "Done. Check anytime with ./setup.sh --doctor or ./setup.sh --routines."
      ;;
    2)
      [ -f "$CLAUDE_DIR/groundwork/config.json" ] || die "No capability profile is configured yet — choose option 1 first (or ./setup.sh --capability-profile NAME)."
      say ""
      say "Which routine?"
      say "  1. Jira EOD          4. PR Follow-up"
      say "  2. News              5. Work Digest"
      say "  3. Weekly Status     6. Doc Drift"
      local r=""; ask r "Choice" ""
      case "$r" in
        1) configure_routine_jira_eod ;;
        2) configure_routine_news ;;
        3) configure_routine_weekly_status ;;
        4) configure_routine_pr_followup ;;
        5) configure_routine_work_digest ;;
        6) configure_routine_doc_drift ;;
        *) die "invalid choice: $r" ;;
      esac
      schedule_all_enabled_routines
      say ""
      say "Done. Check anytime with ./setup.sh --doctor or ./setup.sh --routines."
      ;;
    3) say "No change made." ;;
    *) die "invalid choice: $c" ;;
  esac
}

run_routines() {  # Groundwork 2.1: list configured Routines and last-run status, read-only.
                   # A routine name shows its latest stored result instead (owner requirement §12).
  say "== Groundwork Routines =="
  [ -f "$ROUTINES_PY" ] || die "Routines are not installed at $ROUTINES_PY — run ./setup.sh first"
  if [ -n "${ROUTINE_NAME:-}" ]; then
    python3 "$ROUTINES_PY" latest "$ROUTINE_NAME"
    return
  fi
  python3 "$ROUTINES_PY" list
}

case "$MODE" in
  setup) run_setup ;;
  verify) run_verify ;;
  rollback) run_rollback ;;
  uninstall) run_uninstall ;;
  doctor) run_doctor ;;
  configure) run_configure ;;
  routines) run_routines ;;
esac
