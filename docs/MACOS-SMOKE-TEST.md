# macOS smoke test for Groundwork 2.4

About 10 minutes. It checks on a real Mac what could only be checked on Linux so far. Everything installs into a **throwaway HOME**, so your own `~/.claude` is not touched. Run it from Terminal.app or iTerm2 in a **bash** shell (type `bash`; macOS's own `/bin/bash` is 3.2, which is the point of step 1). The commands were run here with bash on Linux; zsh was not tried. One optional step makes one small model call (the tool caps it at USD 0.25).

**Needs:** a clone of this repo at the 2.4.0 commit, `git`, `python3` 3.10+, Node 20.19+ with `npm`, Claude Code 2.1+ on your PATH, OpenSpec already installed (`openspec --version`; if it is missing, `setup.sh` would install it globally with npm), and `tmux` for step 5 (`brew install tmux`).

## Setup

```bash
REPO=$PWD                         # your clone of this repo
SB=$(mktemp -d)                   # the throwaway HOME
mkdir -p "$SB/bin" "$SB/.claude"
echo '{"model":"smoke"}' > "$SB/.claude/settings.json"
REAL=$(command -v claude)
cat > "$SB/bin/claude" <<EOF
#!/bin/sh
# stub: do not fetch the ECC plugin during this test; everything else goes to the real claude
if [ "\$1" = "plugin" ] && [ "\$2" = "list" ]; then echo "ecc@ecc (v2.2.1) enabled"; exit 0; fi
if [ "\$1" = "plugin" ]; then exit 0; fi
exec "$REAL" "\$@"
EOF
chmod +x "$SB/bin/claude"
```

## 1. Install (bash 3.2 and BSD tools are the macOS risk)

```bash
(cd "$REPO" && HOME="$SB" PATH="$SB/bin:$PATH" ./setup.sh --non-interactive --profile personal --no-agent-teams --schedule disabled --no-install-prereqs >"$SB/install.out" 2>&1; echo "install exit=$?")
(cd "$REPO" && HOME="$SB" PATH="$SB/bin:$PATH" ./setup.sh --verify | tail -2)
cat "$SB/.claude/groundwork/VERSION"
```
Pass: `install exit=0`, the verify output ends with `Overall PASS`, and VERSION prints `2.4.0`.

## 2. Per-tool-call telemetry

```bash
H="$SB/.claude/hooks/groundwork_telemetry.py"; F="$SB/.claude/groundwork/telemetry/tool_events.jsonl"
echo '{"hook_event_name":"PostToolUse","session_id":"smoke","tool_name":"Bash","tool_input":{"command":"echo SECRETWORD"}}' | HOME="$SB" python3 "$H"
echo '{"hook_event_name":"PostToolUseFailure","session_id":"smoke","tool_name":"Read","error":"SECRETWORD"}' | HOME="$SB" python3 "$H"
cat "$F"; echo "SECRETWORD count: $(grep -c SECRETWORD "$F")"; ls -l "$F"
```
Pass: two rows (`"success": true`, then `"success": false`), `SECRETWORD count: 0`, and file mode `-rw-------`.

## 3. StatusLine presets (the emoji preset has never been seen in a real terminal)

```bash
python3 - "$SB/.claude/groundwork/integrations/cache.json" <<'EOF'
import json, sys, datetime
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
e = lambda s: {"available": True, "configured": s != "AVAILABLE", "connected": s == "CONNECTED", "used": None, "summary": s, "checked_at": now}
open(sys.argv[1], "w").write(json.dumps({"schema": 1, "integrations": {"GitHub": e("CONNECTED"), "Jira": e("CONFIGURED"), "Spacelift": e("AVAILABLE")}}))
EOF
IN='{"model":{"display_name":"Sonnet"},"session_id":"smoke","workspace":{"current_dir":"/tmp"},"context_window":{"used_percentage":42}}'
for c in '{}' '{"symbol_set":"ascii","separator":"ascii"}' '{"symbol_set":"emoji"}'; do
  echo "$c" > "$SB/.claude/groundwork/statusline-config.json"
  echo "$IN" | HOME="$SB" CLAUDE_CONFIG_DIR="$SB/.claude" python3 "$SB/.claude/groundwork/bin/groundwork_statusline.py"; echo
done
```
Pass: three lines. The first uses `● ◐ ○` and `│`; the second uses `+ ~ -` and `|`; the third shows `✅ 🟡 ⚪` and **you can see them drawn correctly** in your terminal (this is the part only your eyes can check).

## 4. Worktree awareness

```bash
W=$(mktemp -d); git init -q "$W/r"; git -C "$W/r" -c user.email=a@b -c user.name=s commit -q --allow-empty -m base
git -C "$W/r" worktree add -q -b wip "$W/wip"; echo x > "$W/wip/f.txt"
(cd "$W/r" && echo '{"hook_event_name":"SessionStart","source":"startup","cwd":"'"$W/r"'","session_id":"smoke"}' | HOME="$SB" CLAUDE_CONFIG_DIR="$SB/.claude" python3 "$SB/.claude/hooks/groundwork_session_snapshot.py") | python3 -c 'import json,sys; print(json.load(sys.stdin)["hookSpecificOutput"]["additionalContext"])' | grep -A2 "other worktrees"
```
Pass: a line starting `other worktrees of this repository: 1 with uncommitted changes` and one row for the `wip` worktree (`/private/var/...` and `/var/...` are the same place on macOS).

## 5. Groundwork Copilot in tmux (read-only)

```bash
tmux new-session -d -s smoke -x 120 -y 30
tmux send-keys -t smoke "echo MARKER_IN_THIS_PANE; ls /no/such/dir" Enter; sleep 1
tmux send-keys -t smoke "python3 $REPO/scripts/groundwork_copilot.py explain --dry-run > $SB/copilot.out 2>&1" Enter; sleep 3
tmux kill-session -t smoke
head -6 "$SB/copilot.out"; grep -c MARKER_IN_THIS_PANE "$SB/copilot.out"
```
Pass: the first two lines say `Source: tmux pane` and `Nothing was sent`, and the marker count is 2 or more (your command line and its output). Optional, one small model call:

```bash
# OPTIONAL: one real call
echo "ls: cannot access '/var/data/exports': No such file or directory" | python3 "$REPO/scripts/groundwork_copilot.py" explain --stdin
```
Pass: a short explanation that ends with `No command was run.`

## 6. Uninstall, then rollback

```bash
(cd "$REPO" && HOME="$SB" PATH="$SB/bin:$PATH" ./uninstall.sh | tail -2)
BK=$(ls -d "$SB"/.claude-backups/groundwork-* | head -1)
(cd "$REPO" && HOME="$SB" PATH="$SB/bin:$PATH" ./setup.sh --rollback "$BK" | tail -2)
cat "$SB/.claude/settings.json"
```
Pass: uninstall ends with `Done.`, rollback ends with `Restart Claude Code.`, and `settings.json` is back to `{"model":"smoke"}`.

When you are done, delete the two throwaway folders yourself (`echo "$SB" "$W"` prints them). Report each step as pass or fail, and paste the exact output of any step that fails.
