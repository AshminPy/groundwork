#!/bin/sh
# Terminal Copilot — local installer (EXPERIMENTAL, LOCAL ONLY).
#
# NOT a Groundwork feature, not curl-pipe-bash. Read this whole file before
# running it: `less install-local.sh`, then `sh install-local.sh`.
#
# Does NOT use sudo. Does NOT touch anything outside $HOME. Every step asks
# for confirmation before doing anything. Safe to run on a disposable/
# scratch macOS user account, as recommended in tests/MANUAL_TEST_PROCEDURE.md.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GROUNDWORK_COPILOT_DIR="$HOME/.groundwork-copilot"
HAMMERSPOON_DIR="$HOME/.hammerspoon"

confirm() {
    printf '%s [y/N] ' "$1"
    read -r reply
    case "$reply" in
        y|Y|yes|YES) return 0 ;;
        *) return 1 ;;
    esac
}

echo "== Terminal Copilot local install =="
echo "This script will, only after you confirm each step:"
echo "  1. Create $GROUNDWORK_COPILOT_DIR and copy the orchestrator there."
echo "  2. Symlink the Hammerspoon module into $HAMMERSPOON_DIR."
echo "  3. Add ONE line to $HAMMERSPOON_DIR/init.lua (idempotent, marked)."
echo "  4. Add a clearly delimited block to your shell rc file (idempotent, removable)."
echo "  5. Check for (and optionally pip-install) Python dependencies."
echo
echo "It will NOT use sudo, and will NOT touch anything outside \$HOME."
echo

if [ ! -d "/Applications/Hammerspoon.app" ]; then
    echo "WARNING: Hammerspoon does not appear to be installed at"
    echo "/Applications/Hammerspoon.app. Install it yourself first:"
    echo "https://www.hammerspoon.org/ (this script does not install it for you)."
    echo
fi

if ! command -v claude >/dev/null 2>&1; then
    echo "WARNING: 'claude' CLI not found on PATH. This prototype calls it"
    echo "directly and will not work until it's installed and authenticated."
    echo
fi

# --- Step 1: orchestrator + shell hook -----------------------------------
if confirm "Step 1: copy orchestrator + shell hook into $GROUNDWORK_COPILOT_DIR ?"; then
    mkdir -p "$GROUNDWORK_COPILOT_DIR/bin" "$GROUNDWORK_COPILOT_DIR/shell" "$GROUNDWORK_COPILOT_DIR/sessions"
    cp "$SCRIPT_DIR/bin/copilot_orchestrator.py" "$GROUNDWORK_COPILOT_DIR/bin/copilot_orchestrator.py"
    cp "$SCRIPT_DIR/shell/context-hook.sh" "$GROUNDWORK_COPILOT_DIR/shell/context-hook.sh"
    chmod +x "$GROUNDWORK_COPILOT_DIR/bin/copilot_orchestrator.py"
    echo "  done."
else
    echo "  skipped."
fi
echo

# --- Step 2: Hammerspoon module symlink ----------------------------------
if confirm "Step 2: symlink the Hammerspoon module into $HAMMERSPOON_DIR ?"; then
    mkdir -p "$HAMMERSPOON_DIR"
    ln -sf "$SCRIPT_DIR/hammerspoon/terminal_copilot.lua" "$HAMMERSPOON_DIR/terminal_copilot.lua"
    if [ -f "$SCRIPT_DIR/hammerspoon/local_config.lua" ]; then
        ln -sf "$SCRIPT_DIR/hammerspoon/local_config.lua" "$HAMMERSPOON_DIR/local_config.lua"
    fi
    echo "  done. (Copy hammerspoon/local_config.lua.example to"
    echo "  hammerspoon/local_config.lua first if you want to override the"
    echo "  default hotkey — it is gitignored, never commit it.)"
else
    echo "  skipped."
fi
echo

# --- Step 3: init.lua require line ---------------------------------------
INIT_LUA="$HAMMERSPOON_DIR/init.lua"
MARKER_START="-- BEGIN groundwork terminal-copilot (experimental, local only)"
MARKER_END="-- END groundwork terminal-copilot"
if confirm "Step 3: add a require() line to $INIT_LUA ?"; then
    touch "$INIT_LUA"
    if grep -qF "$MARKER_START" "$INIT_LUA" 2>/dev/null; then
        echo "  already present, left unchanged."
    else
        {
            echo ""
            echo "$MARKER_START"
            echo 'require("terminal_copilot").start()'
            echo "$MARKER_END"
        } >> "$INIT_LUA"
        echo "  added. Reload your Hammerspoon config (Hammerspoon menu > Reload Config)."
    fi
else
    echo "  skipped — you'll need to add"
    echo '    require("terminal_copilot").start()'
    echo "  to $INIT_LUA yourself."
fi
echo

# --- Step 4: shell rc hook -------------------------------------------------
RC_MARKER_START="# BEGIN groundwork terminal-copilot (experimental, local only)"
RC_MARKER_END="# END groundwork terminal-copilot"
for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    [ -f "$rc" ] || continue
    if confirm "Step 4: add the context hook to $rc ?"; then
        if grep -qF "$RC_MARKER_START" "$rc" 2>/dev/null; then
            echo "  already present in $rc, left unchanged."
        else
            {
                echo ""
                echo "$RC_MARKER_START"
                echo "[ -f \"$GROUNDWORK_COPILOT_DIR/shell/context-hook.sh\" ] && . \"$GROUNDWORK_COPILOT_DIR/shell/context-hook.sh\""
                echo "$RC_MARKER_END"
            } >> "$rc"
            echo "  added to $rc. Open a new terminal (or 'source $rc') for it to take effect."
        fi
    else
        echo "  skipped for $rc."
    fi
done
echo

# --- Step 5: Python dependencies ------------------------------------------
if confirm "Step 5: check Python dependencies (faster-whisper, sounddevice, numpy) ?"; then
    missing=""
    for pkg in faster_whisper sounddevice numpy; do
        python3 -c "import $pkg" >/dev/null 2>&1 || missing="$missing $pkg"
    done
    if [ -z "$missing" ]; then
        echo "  all present."
    else
        echo "  missing:$missing"
        if confirm "  pip install these now (pip3 install --user ...)?"; then
            # shellcheck disable=SC2086
            pip3 install --user faster-whisper sounddevice numpy
        else
            echo "  skipped — install them yourself before using Terminal Copilot."
        fi
    fi
else
    echo "  skipped."
fi
echo

echo "== Done. See ../tests/MANUAL_TEST_PROCEDURE.md before relying on this. =="
