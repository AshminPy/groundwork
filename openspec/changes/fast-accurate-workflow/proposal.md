## Why

The accuracy-signals change needed four review rounds and a rebuild:
- the plan stated a fact about existing code that was wrong (the task ledger keeps 60 history events, not all of them);
- reviewers had no agreed bar, so each round surfaced new heuristic edge cases;
- unpushed work was lost when the cloud container restarted;
- the fresh container lacked pytest and the OpenSpec CLI.

The owner's aim is faster, accurate results for everything that runs through Groundwork.

## What Changes

- `rules/engineering-workflow.md` gains three rules:
  - §2.3, fact-check the plan: claims about existing code cite `path:line` and are checked before review;
  - §2.6, state the MUST FIX bar in the reviewer's brief before the review;
  - §4, push the feature branch after each green step when the task includes pushing or runs in an ephemeral container.
- A project SessionStart hook for cloud sessions (`.claude/hooks/session-start.sh`, registered in
  `.claude/settings.json`) installs pytest and OpenSpec 1.13.2 (the repo's last verified version) when missing and sets
  `PYTHONDONTWRITEBYTECODE=1`. It does nothing outside cloud sessions and is not installed to users' machines.

## Capabilities

### New Capabilities
- `engineering-workflow`: the three rules above, and repository tooling for cloud sessions.

## Impact

- One rule file: 713 more bytes (measured), loaded in every session.
- Two new repository files under `.claude/`; `install.sh` does not copy them.
- No code or hook behaviour changes for installed Groundwork.
