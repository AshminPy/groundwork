#!/bin/sh
# Terminal Copilot — shell context hook (EXPERIMENTAL, LOCAL ONLY)
#
# NOT a Groundwork feature. See ../README.md and ../docs/DECISIONS.md.
#
# Sourced from .zshrc or .bashrc (install-local.sh does this for you, inside
# a clearly delimited, removable block). Writes one small, bounded JSON
# context file per prompt, named by this shell's own TTY, so the Hammerspoon
# side can find it by the TTY it reads from the frontmost terminal window.
#
# Captured fields ONLY: tty, cwd, repo_root, git_branch, shell, last_command
# (truncated), last_exit_code, updated_at.
# Deliberately NEVER captured: environment variables, command output,
# full shell history, credentials. See docs/DECISIONS.md #3 for why.

GROUNDWORK_COPILOT_DIR="${GROUNDWORK_COPILOT_DIR:-$HOME/.groundwork-copilot}"
GROUNDWORK_COPILOT_SESSIONS_DIR="$GROUNDWORK_COPILOT_DIR/sessions"
mkdir -p -m 700 "$GROUNDWORK_COPILOT_SESSIONS_DIR" 2>/dev/null
chmod 700 "$GROUNDWORK_COPILOT_SESSIONS_DIR" 2>/dev/null

# Escapes a string for embedding in a JSON string value: backslash, double
# quote, and control characters. Pure shell, no subprocess, so this stays
# cheap enough to run on every prompt.
_groundwork_copilot_json_escape() {
    printf '%s' "$1" | awk '
        BEGIN { ORS="" }
        {
            gsub(/\\/, "\\\\")
            gsub(/"/, "\\\"")
            gsub(/\t/, "\\t")
            print
            if (NR < NF+1) print "\\n"
        }
    ' | sed 's/\\n$//'
}

# Truncates a string to at most N characters (bounded context — see
# docs/DECISIONS.md #3; "unbounded terminal buffers" must never be captured).
_groundwork_copilot_truncate() {
    _str="$1"
    _max="$2"
    printf '%s' "$_str" | cut -c1-"$_max"
}

_groundwork_copilot_write_context() {
    _exit_code="$1"
    _last_command_raw="$2"

    _tty="$(tty 2>/dev/null)"
    # If there's no controlling TTY (e.g. running inside some non-interactive
    # wrapper), there's nothing useful to bind to — skip silently.
    case "$_tty" in
        /dev/*) ;;
        *) return 0 ;;
    esac

    _tty_filename="$(printf '%s' "$_tty" | sed 's#/#_#g')"
    _context_file="$GROUNDWORK_COPILOT_SESSIONS_DIR/${_tty_filename}.json"
    _tmp_file="${_context_file}.tmp.$$"

    _cwd="$(pwd 2>/dev/null)"

    _repo_root=""
    _git_branch=""
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        _repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
        _git_branch="$(git branch --show-current 2>/dev/null)"
    fi

    _shell_name="$(basename "${SHELL:-unknown}")"

    _last_command="$(_groundwork_copilot_truncate "$_last_command_raw" 500)"

    _updated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"

    # umask 077 for the write itself: the temp file must never be created
    # world/group-readable even momentarily, not fixed up after the fact
    # with a trailing chmod (that leaves a real, confirmed TOCTOU window —
    # see docs/DECISIONS.md and the independent review that found it).
    (
        umask 077
        {
            printf '{'
            printf '"tty":"%s",'          "$(_groundwork_copilot_json_escape "$_tty")"
            printf '"cwd":"%s",'          "$(_groundwork_copilot_json_escape "$_cwd")"
            printf '"repo_root":"%s",'    "$(_groundwork_copilot_json_escape "$_repo_root")"
            printf '"git_branch":"%s",'   "$(_groundwork_copilot_json_escape "$_git_branch")"
            printf '"shell":"%s",'        "$(_groundwork_copilot_json_escape "$_shell_name")"
            printf '"last_command":"%s",' "$(_groundwork_copilot_json_escape "$_last_command")"
            printf '"last_exit_code":%s,' "${_exit_code:-0}"
            printf '"updated_at":"%s"'    "$(_groundwork_copilot_json_escape "$_updated_at")"
            printf '}'
        } > "$_tmp_file" 2>/dev/null
    )
    # mv preserves the source file's already-correct mode (0600 from the
    # umask above) rather than inheriting the destination directory's
    # default — no window where the final file is world-readable.
    mv "$_tmp_file" "$_context_file" 2>/dev/null
}

# --- zsh wiring ---------------------------------------------------------
if [ -n "${ZSH_VERSION:-}" ]; then
    _groundwork_copilot_zsh_precmd() {
        _gw_exit=$?
        _gw_last="$(fc -ln -1 2>/dev/null)"
        _groundwork_copilot_write_context "$_gw_exit" "$_gw_last"
    }
    # Idempotent: only add once even if this file is sourced twice.
    if [ -z "${precmd_functions:-}" ]; then
        precmd_functions=()
    fi
    case " ${precmd_functions[*]} " in
        *" _groundwork_copilot_zsh_precmd "*) ;;
        *) precmd_functions+=(_groundwork_copilot_zsh_precmd) ;;
    esac
fi

# --- bash wiring ---------------------------------------------------------
if [ -n "${BASH_VERSION:-}" ]; then
    _groundwork_copilot_bash_precmd() {
        _gw_exit=$?
        _gw_last="$(HISTTIMEFORMAT= history 1 2>/dev/null | sed -E 's/^[ ]*[0-9]+[ ]*//')"
        _groundwork_copilot_write_context "$_gw_exit" "$_gw_last"
    }
    case ";${PROMPT_COMMAND:-};" in
        *";_groundwork_copilot_bash_precmd;"*) ;;
        *) PROMPT_COMMAND="_groundwork_copilot_bash_precmd;${PROMPT_COMMAND:-}" ;;
    esac
fi
