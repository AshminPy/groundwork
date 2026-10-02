#!/bin/sh
# Terminal Copilot — local uninstaller (EXPERIMENTAL, LOCAL ONLY).
# Removes exactly what install-local.sh added. No sudo. Asks before each step.

set -eu

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

remove_marked_block() {
    file="$1"; start="$2"; end="$3"
    [ -f "$file" ] || return 0
    grep -qF "$start" "$file" 2>/dev/null || return 0
    tmp="${file}.tmp.$$"
    awk -v s="$start" -v e="$end" '
        $0 == s { skip = 1; next }
        $0 == e { skip = 0; next }
        !skip { print }
    ' "$file" > "$tmp" && mv "$tmp" "$file"
    echo "  removed marked block from $file."
}

if confirm "Remove $HAMMERSPOON_DIR/terminal_copilot.lua and local_config.lua symlinks?"; then
    rm -f "$HAMMERSPOON_DIR/terminal_copilot.lua" "$HAMMERSPOON_DIR/local_config.lua"
    echo "  done."
fi

if confirm "Remove the require() block from $HAMMERSPOON_DIR/init.lua ?"; then
    remove_marked_block "$HAMMERSPOON_DIR/init.lua" \
        "-- BEGIN groundwork terminal-copilot (experimental, local only)" \
        "-- END groundwork terminal-copilot"
fi

for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    [ -f "$rc" ] || continue
    if confirm "Remove the context-hook block from $rc ?"; then
        remove_marked_block "$rc" \
            "# BEGIN groundwork terminal-copilot (experimental, local only)" \
            "# END groundwork terminal-copilot"
    fi
done

if confirm "Delete $GROUNDWORK_COPILOT_DIR (orchestrator, shell hook copy, and all saved session context files)?"; then
    rm -rf "$GROUNDWORK_COPILOT_DIR"
    echo "  done."
fi

echo "Reload your Hammerspoon config and open a new shell for changes to take effect."
