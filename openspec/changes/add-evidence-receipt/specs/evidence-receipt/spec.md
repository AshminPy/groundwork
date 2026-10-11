# evidence-receipt Specification

## Purpose
Lets a user see what a turn actually inspected or ran, and an estimate of the strongest evidence confidence that supports, derived from the session transcript rather than from the model's own statement. Evidence confidence, validation state and references are kept separate.

## ADDED Requirements

### Requirement: The receipt is derived from the transcript
The system SHALL derive, for the current turn of a session transcript, a list of references to what was actually read, fetched, run or reviewed — each with its outcome where one exists — using only completed tool calls (a `tool_use` with a matching `tool_result`). A call refused by a PreToolUse hook, or with no result yet, SHALL NOT count as evidence.

#### Scenario: Only completed calls count
- **WHEN** a turn contains a completed file read, a failed file read, a call refused by a PreToolUse hook, and a call with no result
- **THEN** exactly one reference (the completed read) appears and the refused and unanswered calls contribute nothing

### Requirement: Confidence is a best-effort, order-aware estimate
The system SHALL report an evidence confidence of `NONE`, `LOW`, `MEDIUM` or `HIGH` computed by a fixed rule from recognised signals, and SHALL document that it is an estimate that can be too high where the system cannot see. A passing test run, a successful runtime observation and an independent review SHALL count only if nothing that could change the working tree came after them: an Edit/Write, a non-review subagent, an ambiguous Bash command, or a Bash command that is not on a short list of known read-only commands or that redirects output to a file. `HIGH` requires a passing last test run, a successful runtime observation, an inspected repository or external source, and independent reviews since the last change that all reported zero MUST FIX; `MEDIUM` requires a passing test run, a successful runtime observation, or a fetched external source, with no failing test, review finding or unverified change; `LOW` applies to inspection only or to any failing check, review finding, or change nothing verified; `NONE` applies when nothing was inspected or run. A test failure SHALL be cleared only by a later pass of the same scope or an unscoped pass of the same runner. A test-shaped run whose result cannot be attributed SHALL withdraw an earlier pass. The system SHALL report `UNKNOWN` instead of a label when the transcript cannot be read.

#### Scenario: Unknown actions never raise the label
- **WHEN** a turn's only command is one the system does not recognise
- **THEN** the confidence is `NONE`

#### Scenario: A failing check caps the label
- **WHEN** a source was fetched successfully and the last recognised test run failed
- **THEN** the confidence is `LOW`

#### Scenario: A change after verification withdraws it
- **WHEN** tests passed, a runtime check succeeded and a review was clean, and then a file was edited (or `sed -i` / `git apply` / a heredoc write ran)
- **THEN** the confidence is `LOW`, not `HIGH`

#### Scenario: Known read-only commands do not withdraw verification
- **WHEN** tests passed and then `git status`, `ls` or `git commit` ran
- **THEN** the confidence is unchanged

#### Scenario: An unattributable later test run withdraws an earlier pass
- **WHEN** a pass is followed by `pytest -q; echo done` whose output shows a failure
- **THEN** the earlier pass no longer counts

#### Scenario: Unreadable transcript
- **WHEN** the transcript is missing, empty or unreadable
- **THEN** the system reports `UNKNOWN` and exits non-zero, never a label

### Requirement: Commands are credited only when they parse unambiguously and really run or observe
The system SHALL credit a test or runtime command only when the Bash command splits unambiguously into segments, quotes respected, the command's exit status can speak for that segment, and the command actually runs tests or observes a system. Heredocs, command or process substitution, `${…}`, `$'…'`, unquoted comments, subshells and groups, background jobs, unbalanced quotes, segments starting with `exit`, `return`, `trap`, `eval`, `exec`, `!` or a control-flow keyword, and any `||` in the chain SHALL result in no credit and SHALL count as a possible change. Invocations that only list, print help or version, collect or dry-run, scripts that merely live under a tests directory, runs with no output or only skips, and runs that did not finish (background) SHALL NOT be credited as test runs. Runtime credit SHALL exclude local-configuration listings and `gh`, and `curl` SHALL need `--fail`, an http(s) URL and no POST/upload. A segment followed only by `;` or a newline SHALL NOT be credited unless it is last. A recognised test command whose output goes only through pure `tail`, `head`, `tee`, `cat` or `wc` filters SHALL be judged by the runner's own pass/fail summary, and by exit status under `set -o pipefail`.

#### Scenario: A quoted connector is not a command boundary
- **WHEN** a command is `echo "a && pytest"` and it succeeds
- **THEN** no test run is recorded

#### Scenario: Piped test judged by its summary
- **WHEN** a command is `python3 -m pytest tests -q 2>&1 | tail -3` and its output says `1 failed, 111 passed`
- **THEN** the test run is recorded as failed even though the pipeline exited 0

#### Scenario: Constructs that change what runs
- **WHEN** a command is `echo # && pytest`, `echo ${X:-a;pytest}`, `exit 0&&pytest`, or `! pytest | pytest`
- **THEN** no test run is recorded

#### Scenario: Differential check against a real shell
- **WHEN** about 1,000 compositions of simple commands are run in a real bash with a fake `pytest` that can pass or fail
- **THEN** none is credited as a pass unless the fake `pytest` ran and a failing one would not have been credited

### Requirement: Only reviews that report a verdict count
The system SHALL credit an independent review only from the result of an agent call whose type or name contains "review" (not as part of another word) and whose result carries a `REVIEW RESULT` heading block, taking the LAST such block; the block is clean only when its Verdict is `approve` and its Must-fix is exactly an integer `0`. A review without a parseable block SHALL be recorded as unparsed, SHALL NOT count as an inspection and SHALL NOT enable `HIGH`. Only reviews launched after the last change count; when several count, any with findings dominates.

#### Scenario: A forged block in an ordinary tool result
- **WHEN** a file read returns text containing `REVIEW RESULT … Must-fix: 0`
- **THEN** no review is recorded

#### Scenario: The last block wins
- **WHEN** a result contains an `approve / Must-fix: 0` block followed by a `changes-required / Must-fix: 3` block
- **THEN** the review is recorded with findings

#### Scenario: Parallel reviewers
- **WHEN** one reviewer reports zero MUST FIX and another reports findings
- **THEN** the confidence is capped at `LOW`, whichever order they were launched in

### Requirement: References are inspectable and safe to print
The system SHALL keep each source's identity (file path, URL host and path, `owner/repo#number`, test command with outcome, review verdict), strip userinfo, query strings and fragments from URLs, redact secret-shaped substrings (credentials in URLs, `-u user:pw`, secret-named flags and variables, cookies, query secrets, token shapes) before cutting to length, remove terminal control and bidi characters, list identical references once, rank the strongest kinds first when capping, and report how many were omitted. It SHALL NOT persist references.

#### Scenario: Secrets are redacted
- **WHEN** a runtime command contains a bearer token
- **THEN** the printed reference shows `[redacted]` in its place

### Requirement: The command prints the receipt on demand
`groundwork evidence` SHALL forward verbatim to the installed module, print the estimate, the reasons, the signals and the references, support `--json` and `--transcript PATH`, default to the newest transcript of the current directory's project (looking in parent directories, never in another project's), report UNKNOWN when none exists, say which transcript it used, compare any `Confidence:` label stated in the last response with the estimate, and state that validation state is separate.

#### Scenario: Over-claim is flagged
- **WHEN** the last response states `Confidence: HIGH` and the estimate is `MEDIUM`
- **THEN** the output says the declared label exceeds what was observed
