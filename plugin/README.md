# Groundwork 3 (alpha)

Groundwork 3 is an on-demand agent control plane for Claude Code. It routes each request to a tier (T0 to T4), starts only the agents that tier needs, keeps run state and evidence in files, and checks work with deterministic hooks instead of approval prompts. The plan is the OpenSpec change `openspec/changes/groundwork-3-control-plane/`.

**Status:** `3.0.0-alpha.1`. Implemented so far: the plugin skeleton, the settings profiles, `gw profile` and `gw doctor`. Run state, hooks, agents and the console come in later task groups. Groundwork 2.x is untouched and still installed separately.

## What it changes on your machine

Nothing, until you apply a profile. A profile writes only to the user `settings.json` of its own config directory, `~/.claude-gw3-work` or `~/.claude-gw3-personal`. Your normal `~/.claude` is never changed.

## Try it

From a clone of this repository:

```bash
# 1. See exactly what the work profile would write (changes nothing)
plugin/scripts/gw profile diff work --vault ~/Obsidian/Work-Groundwork

# 2. Apply it. You must type "apply" in a terminal; Claude cannot approve this for you.
plugin/scripts/gw profile apply work --vault ~/Obsidian/Work-Groundwork

# 3. Start Claude Code with that config directory and the plugin
CLAUDE_CONFIG_DIR=~/.claude-gw3-work TMPDIR=/tmp claude --plugin-dir "$PWD/plugin"

# 4. Check for drift and other problems (changes nothing)
plugin/scripts/gw doctor
```

The work profile turns on:
- auto mode, with no approval prompts for routine work;
- the Bash sandbox, which fails closed;
- deny rules for reading credential files;
- `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`, which turns off nested agents;
- `opus` as the default model.

The vault path is added to the sandbox's writable paths.

## Roll back

```bash
plugin/scripts/gw profile revert work   # restores settings.json byte for byte from the backup
```

To stop using Groundwork 3, start Claude Code without `CLAUDE_CONFIG_DIR` and `--plugin-dir`.

## Known limits

- On Linux, glob patterns in `Read(...)` deny rules are not enforced by the Bash sandbox (`claude doctor` warning). The Read tool still honours them. Groundwork's pre-guard hook (later group) also blocks secret reads.
- A long `TMPDIR` can stop the sandbox from starting. Start Claude Code with `TMPDIR=/tmp`; `gw doctor` warns about this.
- Not yet tested: whether the console mod runs in claude.ai cloud sessions.

## Tests

```bash
python3 -m pytest plugin/tests -q
```

ECC components are inventoried in `toolchain/ecc-inventory.toml`. Ported content keeps ECC's MIT attribution.
