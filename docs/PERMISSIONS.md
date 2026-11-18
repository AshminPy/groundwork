# Permission tiers

Groundwork sorts every action into one of three tiers. Each tier uses Claude Code's native mechanism first:
permission rules, then a PreToolUse hook decision (`permissionDecision`: `deny` or `ask`), which applies in every
permission mode, auto mode included (code.claude.com/docs/en/hooks, code.claude.com/docs/en/permissions).
`tests/test_permission_boundaries.py` probes each tier through the real hooks.

| Tier | What happens | Enforced by |
|---|---|---|
| HARD DENY | The action never runs, whatever the mode or approval. Claude reads the reason and changes course. | Native `permissions.deny` rules from the installer (`scripts/merge_settings.py`, `GROUNDWORK_DENY`); `hooks/block_protected_push.py`; the review check before `gh pr create` |
| HUMAN APPROVAL | Claude Code's own permission prompt asks the owner. In a non-interactive run nobody can answer, so the call is denied. | `hooks/groundwork_task_gate.py` (`permissionDecision: ask`), plus the owner's own `ask` rules |
| AUTONOMOUS | Runs without a prompt, still subject to the owner's own settings and the evidence and review gates at completion. | Nothing to approve: no rule or hook matches |

## HARD DENY

- `sudo`, `rm -rf /*`, `rm -rf ~*`, `chmod 777`, `dd`, `mkfs`, `diskutil erase`, and `git push --force` / `-f`
  (native deny rules).
- A push to `main`, `master`, `production`, `prod` or `release`, any force push (`--force`, `-f`, `+refspec`,
  `--force-with-lease`), `--all`, `--mirror`, and pushes the hook cannot resolve (`block_protected_push.py`).
- A non-draft `gh pr create` unless the most recent reviewer subagent in the session reported `Must-fix: 0` on
  exactly the commit being published (`require_material_review.py` `pr_review_problem`, called by the task gate).
  `gh pr new` is the same command. A draft PR may open before the review, and `gh pr ready` is not checked locally;
  the GitHub `review-check` workflow checks every PR update, including `ready_for_review`.

## HUMAN APPROVAL

- Cloud, cluster, infrastructure, production or data changes (`gcloud`/`aws`/`az` mutations, `kubectl` mutations,
  `terraform apply`/`destroy`, `helm` changes, database writes).
- Deletes outside the working tree and temporary directories.
- Discarding Git history or work (`git reset --hard`, `git clean -f`, `git checkout -- .`, `git branch -D`,
  `git stash drop`, forced or deleting pushes).
- Credential access: reading a credential file with the Read tool or a shell reader (`cat .env`,
  `~/.aws/credentials`, `~/.ssh/`), and credential commands (`gh auth`, `gcloud auth`, `kubectl get secret`).
- Elevated privileges (`sudo` also has a deny rule).
- Changes to Claude Code settings, Groundwork's hooks or the task ledger, including `disableAllHooks`.
- Any command the gate cannot parse.

## AUTONOMOUS

Reading and searching the repository, editing files in the working tree, running tests and linters, local Git
(`status`, `diff`, `add`, `commit`, branch creation), pushing a feature branch, opening a draft PR, and running the
Groundwork task CLI.

## Decisions

- Secrets stay in HUMAN APPROVAL, not HARD DENY. The owner sometimes has to check a secret file's metadata or rotate
  a credential, and a deny rule cannot be approved case by case. The owner's rule "never print secret values" still
  applies to what Claude does after approval.
- Exit code 2 is not used. JSON `permissionDecision` and `decision: block` are documented, carry a reason Claude can
  act on, and work in every mode. Every Groundwork hook fails open on unreadable input, so a broken hook never
  locks a session; the review checks fail open only when git or the transcript cannot be read.
- No new deny rules were needed for this change: every tier above was already enforced, except the review check
  before a PR.

## Limits

- Hooks and permission rules load only where Claude Code loads the user's settings: local sessions, background
  sessions and Remote Control. Claude Projects cloud threads do not load repository hooks or permission rules
  (code.claude.com/docs/en/claude-projects), so governed work does not run there.
- `disableAllHooks` can switch every hook off, and only a managed policy can prevent that. The task gate asks before
  a settings change, but a setting changed outside Claude Code is not seen.
- Auto mode ignores broad allow rules such as a bare `Bash` (code.claude.com/docs/en/auto-mode-config); deny rules
  and hook decisions still apply.
- The gate does not inspect programs such as `python -c`; see `docs/TASK-LIFECYCLE.md`.
