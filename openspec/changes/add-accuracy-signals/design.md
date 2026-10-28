## Context

Revised after the EGM review (`egm-review.md`). The owner decided (2026-10-28): remove the re-edit metric and file
hashing; keep the CI check, opt-in.

Evidence for each source:
- **Hook fields** (code.claude.com/docs/en/hooks, read 2026-10-27):
  - `prompt_id` is a common input field ("UUID identifying the user prompt currently being processed").
  - PostToolUseFailure: `error` (Bash: first line `Exit code N`), `is_interrupt`.
  - Bash PostToolUse: `tool_response.interrupted`. `run_in_background` fires PostToolUse at launch.
  - SubagentStop: `agent_id`, `agent_type`, `last_assistant_message`.
  - UserPromptSubmit: `prompt`.
  - PostCompact: `trigger`.
  - Stop: `last_assistant_message`, `stop_hook_active`. Stop does not run on a user interrupt, and API errors fire StopFailure.
  - A PreToolUse hook that crashes is non-blocking, so the action goes ahead.
- **Transcript format:** "internal to Claude Code and changes between versions" (code.claude.com/docs/en/sessions). No new signal uses it.
- **Runtime evidence** on this machine:
  - all 308 `events.jsonl` records carry `prompt_id`;
  - 10 prompts have more than one Stop record (reply check / review gate continuations);
  - this session's transcript shows a failed Bash result beginning `Exit code 1`.
- **Repository:**
  - The task gate (`hooks/groundwork_task_gate.py` `on_post`, `verification_match`, `split_segments`) already decides interrupted, background and masked runs. It also records reviews through `is_review_call` + `parse_review_result`.
  - The ledger (`hooks/groundwork_tasks.py`) stores, per task: `tier`, `state`, `created_at`, `completed_at`, plus `evidence.reviews[{must_fix, verdict, ts, fp}]` and `evidence.operations[{ts}]`.
  - The statusLine (`scripts/groundwork_statusline.py`) writes `usage.jsonl` with `ctx_pct` and `cost_usd`, at most once a minute per session, and keeps it about 8 days.

## Goals / Non-Goals

Goal: every Performance-gaps answer is computed from defined inputs, shows its count and labels, and says
"insufficient data" or "not collected" rather than a number it cannot support.

Non-goals:
- proving that a review was *correct*, or that a citation *supports* its claim;
- benchmarks (the runner is not on `main`);
- re-edit / rework by file (removed by the owner).

## Decisions

**D1. Sources.** New signals use documented hook fields only, computed in the hook that receives them. Raw prompt,
command, reply or output text never leaves that hook. Records hold enums, booleans, counts, ids, a commit SHA and an
`owner/repo` (D8).

**D2. Dispatch and record shapes.** Schemas are unchanged and fields additive: `events` schema 2, tool rows schema 1,
signals schema 1. `hooks/groundwork_telemetry.py main()` routes as follows:

| Event | Writes | Example |
|---|---|---|
| Stop | `events.jsonl` (existing) plus `observed.ctx_pct`, `observed.cost_usd`, `observed.citations`, and on commit turns `observed.head` / `observed.repo` | `"citations":{"checked":4,"resolved":3,"unchecked":1}` |
| PostToolUse / PostToolUseFailure | `tool_events.jsonl` (existing) plus `prompt_id` and `tool_use_id`. For Bash: `kind` (`test` \| `check` \| `deploy` \| `runtime_read` \| `git_commit`, omitted otherwise) and `result` (`pass` \| `fail` \| `unknown`) for `test`/`check`. For completed Agent/Task review calls: a `review` signal (D9) | `{"schema":1,"ts":"…","session_id":"s","prompt_id":"p","tool":"Bash","category":"builtin","success":false,"kind":"test","result":"fail"}` |
| SubagentStop | `signals.jsonl` `review`, only for a review-shaped `agent_type` (D9) | `{"schema":1,"ts":"…","session_id":"s","prompt_id":"p","kind":"review","source":"subagent_stop","agent_id":"a1","verdict":"approve","must_fix":0}` or `…,"parsed":false}` |
| UserPromptSubmit | `signals.jsonl` `prompt` | `{"schema":1,…,"kind":"prompt","correction":true}` |
| PostCompact | `signals.jsonl` `compact` | `{…,"kind":"compact","trigger":"auto"}` |
| anything else | nothing; exit 0 | |

Guardrail records (D6) come from the guard hooks, not from this script:
`{…,"kind":"guardrail","hook":"push_guard","decision":"deny","cause":"policy","tool_use_id":"…"}`.

Registration goes through a new `TELEMETRY_EVENTS` tuple in `scripts/merge_settings.py` (event, matcher, timeout,
message), imported by `unmerge_settings.py`:
- Stop;
- PostToolUse `""`;
- PostToolUseFailure `""`;
- SubagentStop;
- UserPromptSubmit;
- PostCompact.

That is 6 telemetry entries, 18 hook entries in total.

**D3. Turns and attribution.** A **turn** is (`session_id`, `prompt_id`). "Task" means only a ledger task.
- The Stop records of a turn are **merged** (a hook can block a Stop and ask for a short follow-up): the last *stated* outcome and validation; citations summed; files changed, tests run and deploy OR-ed; context and cost from the last Stop.
- Tool rows and signals join to their turn by `prompt_id`.
- A prompt with tool rows but no Stop record is a `no_stop` turn, labelled "interrupted, failed, or not recorded". It is counted separately, never folded into the next turn. Prompts with neither (conversational turns) are ignored.
- Records without `prompt_id` (written before this change) fall back to time attribution: the first Stop in the same session at or after the record. Results from the fallback are labelled.
- Attribution uses all records; window filtering happens after attribution.

Loader fields kept in memory, never embedded in the page:
- events: `sid`, `prompt_id`, `ts`, `version`, `outcome`, `validation`, `impl`, `deploy`, `ctx`, `cost`, `cit`, `head`, `repo`;
- tool rows: `sid`, `prompt_id`, `tool_use_id`, `ts`, `kind`, `result`;
- signals: all fields.

**D4. Questions and metrics.** Labels: `observed` (hook saw it), `declared` (model said it, parsed), `pattern` (text or
command matched by a named pattern), `estimate`, `opt-in`. The rate display rule:
- fewer than 5 cases: "insufficient data (n)";
- 5 to 19: rate with "low data";
- 20 or more: rate.

Every declared-based question shows the **unstated share of its own population**: outcome unknown, out of
file-changing turns, for 1a, 4 and 8; validation unknown for 1b. A row counts turns whose outcome is unstated and
whose last test failed, so a vague reply cannot hide a failure. The section is computed server-side for the selected
period and is not changed by the page filters, like the context-fill table.

| Q | Question | Metric (numerator / denominator) | Labels |
|---|---|---|---|
| 1a | Does it say complete while tests fail? | Turns declared complete that changed files and whose last `test` call with a known result failed / turns declared complete that changed files | observed, declared, pattern |
| 1b | Does it say verified without checking? | Turns declared verified that changed files and ran no test, check, deploy or runtime-read call of any result / turns declared verified that changed files | observed, declared, pattern |
| 2 | How do turns end on tests? | Final test state per file-changing turn: pass / fail / unknown / none, as four counts and the fail share of the known ones. Secondary note: per-call pass rate | observed, pattern |
| 3a | Is MATERIAL work reviewed before it ships? | Ledger MATERIAL tasks with a sensitive operation before their first review at must-fix 0, or complete with no such review / MATERIAL tasks that are complete or have a sensitive operation. Read from `history`, which keeps the last 60 events (`MAX_HISTORY`): a task whose kept history no longer starts at `intake` is left out and counted. Limit: the gate appends evidence to every open task in the repository | observed |
| 3b | Does review find defects before shipping? | Ledger MATERIAL tasks whose first review in `history` reported must-fix > 0 / MATERIAL tasks with at least one review. Beside it: median reviews until must-fix 0 | observed |
| 3c | How much review happens outside the ledger? | Review signals in turns of sessions with no ledger task, as a count (context, not a rate) | observed |
| 4 | Do users have to correct finished work? | Turns declared complete whose next prompt in the same session within 2 hours reads as a correction / turns declared complete with such a next prompt | declared, pattern |
| 5 | Do answers cite code that resolves? | Citations that resolve (file exists, both ends of the range within the file) / citations checked; unchecked count beside | pattern |
| 6 | Does pushed work pass CI? | Commits whose checks all passed / commits whose checks all finished; "not on GitHub", "no checks" and "pending" counts beside | opt-in |
| 7 | Where do guardrails step in, and are they right? | Distinct (session, prompt, hook, decision) firings in the period, by hook, and per 100 turns from 5 turns. Follow-through: asks approved (a tool row with the same `tool_use_id`) / asks, leaving out asks on a call another guard denied; review-gate blocks followed by a review in the same session / review-gate blocks; firings with cause `internal_error` | observed |
| 8 | What does a completed turn cost? | Median of (`cost_usd` at this turn − `cost_usd` at the previous turn of the session) over turns declared complete where both readings exist; coverage = those turns / turns declared complete | estimate, declared |
| 9 | Does quality change after compaction? | Count of compactions. For the 3 turns before and the 3 turns after each compaction in the same session: the 1a rate and the Q4 rate, side by side. Shown beside the context-fill table | observed, declared, pattern |
| 10 | Did the last Groundwork version help? | Q1a, Q1b, Q2-fail share and Q4 broken down by `harness_version` (ledger tasks have no version), plus the change against the previous period (both periods at least 5 cases) | as the inputs |
| 11 | Are first drafts complete? | Turns with a reply-check or review-gate guardrail record / turns recorded by this change's hook (Q7 and Q8 use the same population) | observed |

The benchmark is not a row: one footer line says "Benchmark score per release: not collected (runner on branch
`bench/vanilla-vs-groundwork`)".

The existing summary lines "Rework rate: N/A" and "Verified accuracy: insufficient data" are replaced by a pointer to
Performance gaps; the footer keeps its "show N/A rather than 0%" rule. The existing "Verified outcome" card is
relabelled "complete with a test-shaped command seen (broad match)", pointing to Q2 for real results.

**D5. Command classification and results.** The task gate keeps its parser; nothing moves, so the authorization gate's
dependencies are unchanged. The telemetry hook imports `split_segments` from `groundwork_task_gate` **lazily inside
`try`**; if that fails, `kind` is still set from a simple first-word check and `result` is `unknown`.
- **Leading executable** of each segment, after `env`, `time`, `timeout N`, `sudo`, `uv run`, `poetry run` and `npx` are stripped (`bash -c '…'` stays unclassified):
  - `test`: `pytest`, `python[3] -m pytest`, `python[3] -m unittest`, `python[3] <path with tests/ or test_>.py`, `go test`, `cargo test`, `npm|pnpm|yarn [run] test`, `make test|check`, `tox`, `nox`, `bats`.
  - `check`: `terraform validate|plan`, `kubectl … --dry-run`, `ruff`, `mypy`, `openspec validate`.
  - `deploy`: the existing `DEPLOY_CMD` list, matched at the segment start.
  - `runtime_read`: `curl`, `wget`, `kubectl get|describe|logs|rollout status`, `gh run view|watch`, `gh pr checks`, `claude -p`.
  - `git_commit`: `git commit`.
- `grep`, `cat`, `echo`, `pip install`, `git` (other than commit) and editors are never a test.
- **Result** for `test`/`check`, mirroring the task gate:
  - `pass` = PostToolUse, `tool_response.interrupted` not true, not background, not masked;
  - `fail` = PostToolUseFailure whose `error` starts with `Exit code N`, N ≠ 0, not masked, **and the test is the last segment with only benign segments before it** (`cd`, `export`, `set`, `source …/activate`, variable assignments). Otherwise `unknown`, because another command may have failed;
  - `unknown` = background, interrupted, masked, no `Exit code` line, exit 124, 126 or 127 (killed by `timeout`, or the command could not run), `terraform plan` exit 2, or pytest exit 5.
- A segment with `--help`, `-h`, `--version`, `-V`, `--collect-only` or `--co` is not a test or check run.
- `git_commit` is set only when the commit segment's own status is visible (no `||`, `;` or pipe after it), so a masked commit never makes a commit turn.
- Ids (`prompt_id`, `tool_use_id`, `agent_id`) are stored only when they match `[\w.:-]{1,100}`; `must_fix` is capped at 1000.
  - Masked means the test segment is followed by `;`, `||`, `&`, a newline, or a pipe without `set -o pipefail`, matching `verification_match`'s "masked".

**D6. Guardrail records.**
- Each guard (push guard `deny`; task gate `ask`/`deny`; review gate `block`; reply check `block`; the brief's PreCompact entry stays as it is) builds its decision, then calls the writer **inside `try`, importing it inside the `try`**. A missing or broken module can never stop the decision being printed. A test deletes the module and asserts the deny still happens.
- `cause` is `internal_error` for decisions taken because the guard could not check (an internal error, a command it could not parse at any nesting level, an unclosed substitution, nesting too deep, a PowerShell command), and `policy` otherwise. The caller passes it explicitly.
- Each guard prints and flushes its decision first, then records it; the recorder catches `BaseException`.
- `tool_use_id` is stored for PreToolUse decisions, so an ask can be joined to a later PostToolUse.
- The brief's one-time request is not a guardrail and is not recorded.
- The writer opens with `O_APPEND | O_CREAT | O_NOFOLLOW | O_NONBLOCK`, requires a regular file, mode 0600 in a 0700 directory, and honours `GROUNDWORK_TELEMETRY=off` and `GROUNDWORK_SIGNALS_PATH`.
- The report ignores `session_id: "unknown"`.

**D7. Citations.**
- Matched with a bounded `path:line[-line]` pattern over the turn's replies. Text inside `http(s)://…` spans is skipped. A backtick path without a line number is not a citation.
- A path without `/` that does not exist under the roots is **unchecked**, so `node.js:18` and `db.example.com:5432` never count against the rate. A path with `/` is checked.
- A path is resolved against `cwd` and the git top level of `cwd` (1-second timeout).
  - It is **checked** when its realpath is inside one of them, absolute paths included.
  - Otherwise it is **unchecked**.
- **Resolved** = regular file under 5 MB, and both ends of the range within its line count.
- At most 50 distinct citations per reply.

**D8. Commits and CI (opt-in).**
- A **commit turn** is a turn with a Bash `git_commit` call that succeeded.
- At its Stop, the hook records `head` (`git rev-parse HEAD`, 1 s) and `repo`, the `owner/repo` parsed in memory from a github.com `origin` URL. Credentials in the URL are never captured, as a test shows.
- `generate --github`:
  - takes the newest 50 in-window commit turns;
  - validates `owner/repo` (`[\w.-]+/[\w.-]+`, not `.`/`..`) and the 40-hex SHA;
  - runs read-only `gh api --method GET` for `commits/{sha}/check-runs?per_page=100` (paginated) and `commits/{sha}/status`;
  - counts a commit turn whose `origin` is not on github.com as "no GitHub remote", without calling `gh`;
  - maps the results: success / neutral / skipped = pass; failure / timed_out / cancelled / action_required / startup_failure / stale = fail; any run not completed = pending; 404 / 422 = not on GitHub; no runs and no statuses = no checks.
- A missing `gh`, or one not logged in, shows "not available".
- Without the flag, the report runs no subprocess.
- The last stdout line stays `records=…` (setup.sh contract).

**D9. Reviews.**
- **Foreground:** PostToolUse on Agent / Task where `require_material_review.is_review_call(tool_name, tool_input)` is true and `tool_response.status` is absent or `completed`, as the gate does. The result text is parsed with `parse_review_result`, verdict-only "approve" meaning must-fix 0 as in the ledger. Written as a `review` signal with source `tool` and key `tool_response.agentId` (documented). Skill calls are not counted; the gate does not count them either.
- **Background and every subagent:** SubagentStop where `agent_type` matches `REVIEW_PATTERN`, as a `review` signal with source `subagent_stop` and the `agent_id`.
- The report takes the union, de-duplicated by agent id. Records without an id are kept.
- Review signals feed Q3c and Q7 follow-through. Q3a/Q3b use the ledger, which is the authority for MATERIAL work.

**D10. Corrections.**
- Pasted text is excluded by rule: only lines outside ``` fences are matched, only the first 5 such lines, each at most 300 characters. Prompts starting with `/`, and harness envelopes (`<task-notification>`, `<system-reminder>`, `<agent-message`), are skipped. UserPromptSubmit also fires on turns Claude Code starts itself; those carry envelopes and are skipped.
- Skipped prompts are still recorded, as `skipped: true`, so Q4 steps over them to the user's next own prompt.
- A match preceded on its line by `if`, `when`, `whenever`, `unless` or `in case` is a conditional, not a correction ("if it doesn't work, tell me").
- Matching is case-insensitively, with straight or curly apostrophes, against: "didn't work", "doesn't work", "still failing / fails / failed / broken", "that's wrong / incorrect / not right", "not what I asked", "you broke".
- The labelled test set includes every false positive the reviewers found.
- The metric says "pattern-matched: can miss corrections and can over-count".

**D11. Context and cost readings.** At Stop, the hook reads the session's newest statusLine row:
- `ctx_pct`, if the row is at most 15 minutes old;
- `cost_usd`, if it is at most 60 seconds old **and** newer than the previous turn's Stop in the session (as `observed.cost_usd`). The statusLine writes at most one row a minute, so two quick turns could otherwise share one reading; such turns fall outside cost coverage.

Without Groundwork's statusLine, or in headless runs, neither is recorded. The card says so.

## Rollback

`setup.sh --rollback` restores the previous `settings.json`, so the new events stop calling the hook.

Old readers ignore the new fields and file:
- `normalise` reads explicit keys only;
- `normalise_tool` keeps schema 1 rows and their known keys;
- `signals.jsonl` is unknown to old code.

If only the code were reverted while settings kept the new events, the old telemetry `main()` would treat them as Stop
and write extra per-turn records. The rollback path above prevents that, and it is stated in UPGRADE-ROLLBACK.

`signals.jsonl` stays in `telemetry/`; uninstall keeps telemetry as user data, as today.

## Risks / Trade-offs

- **Privacy:** prompt, command and reply text are read in memory only. Stored: an `owner/repo` and commit SHA on commit turns (disclosed in the README privacy section).
- **Pattern labels:** classification lists are named and versioned, so a metric change is visible.
- **Ledger coverage:** Q3a/Q3b only cover machines where the task gate is enabled. Otherwise they show "not collected: task ledger empty".
- **Latency:** one more process on UserPromptSubmit and on SubagentStop/PostCompact, each with a 5 s timeout and no network. It is measured in validation (target under 100 ms).
- **Association only:** Q9 and Q10 show association; the page says so.

## Validation

- Unit tests per decision, with labelled fixtures:
  - commands: masked, background, interrupted, `grep pytest`, `pip install pytest`, `terraform plan` exit 2;
  - corrections, including reviewer false positives and curly apostrophes;
  - citations: `host:port`, absolute inside and outside the repository, a range, `../`, a symlink;
  - attribution: multiple Stops, `no_stop` turn, window edge, `prompt_id` missing;
  - ledger fixtures for Q3;
  - CI mapping, pagination and validation.
- A guard-module-missing test.
- A suite-wide `tests/conftest.py` that isolates telemetry, plus a check that the real paths are untouched.
- Mutation checks on each metric's key clause.
- Updated pinned tests: `test_telemetry` key sets, `test_hooks` and `test_setup` counts (18 / 6).
- A live headless `claude -p` run with the hooks through `--settings`, confirming:
  - `prompt_id` on PostToolUse, SubagentStop and PostCompact, and which `prompt_id` a background subagent's late tool rows carry;
  - a failing test recorded as `fail`;
  - a correction prompt;
  - a review signal.
- An independent review loop until 0 must-fix.

