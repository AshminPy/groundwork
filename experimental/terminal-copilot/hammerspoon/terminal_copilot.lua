--[[
Terminal Copilot — Hammerspoon module (EXPERIMENTAL, LOCAL ONLY)

NOT a Groundwork feature. See ../README.md and ../docs/DECISIONS.md.

This module was written without a running Hammerspoon instance available to
test against (remote Linux container, no macOS). The hs.* API calls below
(hs.hotkey, hs.application, hs.osascript, hs.task, hs.pasteboard, hs.webview,
hs.alert, hs.json) are Hammerspoon's long-standing, documented APIs, but
their exact current behavior has NOT been verified by running this code.
Before relying on this, check it against https://www.hammerspoon.org/docs/
for the Hammerspoon version actually installed, and watch the Hammerspoon
Console (cmd-opt-ctrl-return default, or Hammerspoon menu) for errors on
first load.

Usage (see install-local.sh): this file is loaded from ~/.hammerspoon/init.lua
via:
    local copilot = require("terminal_copilot")
    copilot.start()

Configuration: copy local_config.lua.example to local_config.lua in this same
directory (gitignored — never commit machine-specific paths) to override
defaults such as the hotkey and script paths.
--]]

local M = {}

-- ---------------------------------------------------------------------
-- Configuration (safe defaults; override via local_config.lua)
-- ---------------------------------------------------------------------

local defaultConfig = {
    -- Default activation hotkey: cmd+alt+ctrl+C. Chosen to be unlikely to
    -- collide with existing macOS/app shortcuts. Override in local_config.lua
    -- if it conflicts with something on your machine.
    hotkeyMods = { "cmd", "alt", "ctrl" },
    hotkeyKey = "c",

    -- Path to the orchestrator script. Defaults to a path relative to this
    -- repo checkout; override in local_config.lua for your own machine.
    orchestratorPath = os.getenv("HOME") .. "/.groundwork-copilot/bin/copilot_orchestrator.py",

    -- Python interpreter to use (the one with faster-whisper installed).
    pythonPath = "/usr/bin/env",
    pythonArgs = { "python3" },

    -- Max seconds to wait for the orchestrator before giving up.
    timeoutSeconds = 30,
}

local config = {}
for k, v in pairs(defaultConfig) do config[k] = v end

local ok, localConfig = pcall(require, "local_config")
if ok and type(localConfig) == "table" then
    for k, v in pairs(localConfig) do config[k] = v end
end

-- ---------------------------------------------------------------------
-- Terminal identity: TTY of the frontmost window, per supported terminal.
-- See docs/DECISIONS.md #1 for why TTY is the binding key.
-- ---------------------------------------------------------------------

-- Bundle IDs for the two terminals this MVP supports. Anything else is
-- refused rather than guessed at (see docs/DECISIONS.md #5).
local SUPPORTED_TERMINALS = {
    ["com.apple.Terminal"] = "Terminal",
    ["com.googlecode.iterm2"] = "iTerm2",
}

-- Returns (ttyPath, humanName) or (nil, errorMessage).
local function getFrontmostTerminalTTY()
    local app = hs.application.frontmostApplication()
    if not app then
        return nil, "Could not determine the frontmost application."
    end

    local bundleID = app:bundleID()
    local terminalName = SUPPORTED_TERMINALS[bundleID]
    if not terminalName then
        return nil, string.format(
            "Terminal Copilot only supports Terminal.app and iTerm2. " ..
            "The frontmost app is '%s' (%s). Focus a supported terminal and try again.",
            app:name() or "unknown", bundleID or "unknown bundle id"
        )
    end

    local script
    if terminalName == "Terminal" then
        -- Terminal.app: AppleScript dictionary exposes `tty` on a tab.
        script = [[
            tell application "Terminal"
                return tty of front window
            end tell
        ]]
    else
        -- iTerm2: AppleScript dictionary exposes `tty` on a session.
        script = [[
            tell application "iTerm2"
                tell current window
                    tell current session
                        return tty
                    end tell
                end tell
            end tell
        ]]
    end

    local success, result = hs.osascript.applescript(script)
    if not success or not result or result == "" then
        return nil, string.format(
            "Could not read the TTY for the frontmost %s window. " ..
            "(AppleScript result: %s)", terminalName, tostring(result)
        )
    end

    return result, terminalName
end

-- ---------------------------------------------------------------------
-- Activation: hotkey pressed -> resolve TTY -> invoke orchestrator async
-- ---------------------------------------------------------------------

-- Sanitizes a TTY path into a safe filename component (used by the shell
-- hook too; duplicated here only as a comment for clarity — the actual
-- sanitization happens identically in both places by replacing "/" with "_").
local function ttyToFilenameComponent(tty)
    return (tty:gsub("/", "_"))
end

local function showError(message)
    hs.alert.show("Terminal Copilot: " .. message, 4)
end

-- Displays the result in a small overlay. Both buttons copy the command to
-- the clipboard (see docs/DECISIONS.md #2 for why there is no direct-send
-- action in this MVP) and then close the overlay. There is no action that
-- causes anything to execute.
local function showResultOverlay(ttyPath, terminalName, cwd, explanation, suggestedCommand)
    local webview = hs.webview.new(hs.geometry.rect(0, 0, 520, 320))
    webview:windowTitle("Terminal Copilot")
    webview:allowGestures(false)
    webview:level(hs.drawing.windowLevels.floating)

    local function escapeHTML(s)
        if not s then return "" end
        return (s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"))
    end

    local commandBlock = ""
    if suggestedCommand and suggestedCommand ~= "" then
        commandBlock = string.format(
            "<pre id='cmd' style='background:#1e1e1e;color:#eee;padding:10px;" ..
            "border-radius:6px;white-space:pre-wrap;'>%s</pre>" ..
            "<button onclick=\"window.location.href='copilot://copy'\" " ..
            "style='padding:8px 16px;margin-right:8px;'>Copy to clipboard (RUN/EDIT)</button>",
            escapeHTML(suggestedCommand)
        )
    end

    local html = string.format([[
        <html><body style="font-family: -apple-system, sans-serif; padding: 14px;">
            <div style="color:#666; font-size: 12px; margin-bottom: 10px;">
                %s &middot; %s
            </div>
            <div style="margin-bottom: 14px;">%s</div>
            %s
            <div style="margin-top:12px;">
                <button onclick="window.location.href='copilot://dismiss'">Dismiss (IGNORE)</button>
            </div>
        </body></html>
    ]], escapeHTML(terminalName .. " (" .. ttyPath .. ")"), escapeHTML(cwd or ""),
        escapeHTML(explanation or "(no explanation returned)"), commandBlock)

    webview:html(html)

    webview:navigationCallback(function(action, webviewObj, navID, navAction)
        -- hs.webview's URL-scheme interception varies by Hammerspoon version;
        -- verify this callback shape against the installed version's docs.
        local url = navAction and navAction.request and navAction.request.URL
        if url == "copilot://copy" then
            hs.pasteboard.setContents(suggestedCommand or "")
            hs.alert.show("Copied. Paste into " .. terminalName .. " (" .. ttyPath .. ").")
            webviewObj:delete()
        elseif url == "copilot://dismiss" then
            webviewObj:delete()
        end
        return false -- block actual navigation
    end)

    webview:show()
end

local function activate()
    local ttyPath, terminalNameOrError = getFrontmostTerminalTTY()
    if not ttyPath then
        showError(terminalNameOrError)
        return
    end
    local terminalName = terminalNameOrError

    hs.alert.show("Terminal Copilot: listening... (" .. terminalName .. ")", 2)

    local args = {}
    for _, a in ipairs(config.pythonArgs) do table.insert(args, a) end
    table.insert(args, config.orchestratorPath)
    table.insert(args, "--tty")
    table.insert(args, ttyPath)

    local stdoutChunks = {}

    local task = hs.task.new(config.pythonPath, function(exitCode, stdOut, stdErr)
        if exitCode ~= 0 then
            showError(string.format(
                "Orchestrator exited with code %d.\n%s", exitCode, stdErr or ""
            ))
            return
        end

        local decoded, err = hs.json.decode(stdOut or "")
        if not decoded then
            showError("Could not parse orchestrator response: " .. tostring(err))
            return
        end
        if decoded.error then
            showError(decoded.error)
            return
        end

        showResultOverlay(
            ttyPath, terminalName, decoded.cwd,
            decoded.explanation, decoded.suggested_command
        )
    end, args)

    task:setTimeout(config.timeoutSeconds)
    task:start()
end

-- ---------------------------------------------------------------------
-- Public API
-- ---------------------------------------------------------------------

function M.start()
    M.hotkey = hs.hotkey.bind(config.hotkeyMods, config.hotkeyKey, activate)
    hs.alert.show("Terminal Copilot (experimental) ready.", 2)
end

function M.stop()
    if M.hotkey then
        M.hotkey:delete()
        M.hotkey = nil
    end
end

return M
