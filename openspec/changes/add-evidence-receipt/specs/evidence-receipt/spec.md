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
- **WHEN** a turn's only action is a command, subagent, skill or tool the system does not recognise
- **THEN** the confidence is `LOW` (it may have changed the tree and nothing verified it), never `NONE` and never higher

#### Scenario: Every possible change is counted
- **WHEN** a web page was fetched, tests passed, and then a heredoc write, an unparseable command, a non-review subagent, a local MCP writer or editor, a skill or an unknown tool ran
- **THEN** the confidence is `LOW`, exactly as for an `Edit`

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

### Requirement: The estimate gates nothing
No permission, hook decision, block or approval SHALL depend on the estimate or on the comparison with the stated label; they are shown to the user and recorded only.

#### Scenario: A stated label above the estimate
- **WHEN** the response states a label above the estimate
- **THEN** the Stop hook records that fact and does not block the stop

### Requirement: Commands are credited only when they parse unambiguously and really run or observe
The system SHALL credit a test or runtime command only when the Bash command splits unambiguously into segments, quotes respected, the command's exit status can speak for that segment, and the command actually runs tests or observes a system. Heredocs, command or process substitution, `${…}`, `$'…'`, unquoted comments, a backslash-newline continuation, text over 20,000 characters, subshells and groups, background jobs, unbalanced quotes, segments starting with `exit`, `return`, `trap`, `eval`, `exec`, `!` or a control-flow keyword (also when the word is quoted or escaped), and a test or runtime segment in a chain with `||` SHALL NOT be credited (the other segments of the chain are judged on their own). Invocations that only list, print help or version, collect (`--collect-only`, `--collectonly`, `--listTests`) or dry-run (`--notest`), scripts that merely live under a tests directory, runs with no output (including the harness's "no output" placeholder), a "nothing to be done" / "no tests ran" notice, `go test` packages whose only result is `[no tests to run]`, or only skips, and runs that did not finish (background) SHALL NOT be credited as test runs. Runtime credit SHALL exclude local-configuration listings and `gh`, and `curl` SHALL need `--fail`, an http(s) URL and no POST or upload option in short or long form (options are read one by one, case-sensitively, including inside a cluster such as `-fsSd`), `wget` SHALL need `--spider`, and a download that saves a file (`-o`/`-O`/`--output`/`--remote-name`, or wget without `--spider`) SHALL count as a change; `gcloud` and `az` verbs SHALL match as whole words. A segment followed only by `;` or a newline SHALL NOT be credited unless it is last. A recognised test command whose output goes only through pure `tail`, `head`, `tee`, `cat` or `wc` filters SHALL be judged by the runner's own pass/fail summary, and by exit status under `set -o pipefail`.

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
- **WHEN** 5,292 compositions of simple commands are run in a real bash with a fake `pytest` that can pass or fail
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
The system SHALL keep each source's identity (file path, URL host and path, `owner/repo#number`, test command with outcome, review verdict), strip userinfo, query strings and fragments from URLs, redact secret-shaped substrings (credentials in URLs, `-u user:pw`, secret-named flags and variables, cookies, query secrets, token shapes) within the first 4,000 characters before cutting to the display length (a secret straddling the 4,000-character cut can leave a short prefix), remove control, format (including bidi and zero-width), private-use, unassigned and line-separator characters (other invisible characters, such as variation selectors, are not removed), list identical references once, rank the strongest kinds first when capping, and report how many were omitted. It SHALL NOT persist references.

#### Scenario: Secrets are redacted
- **WHEN** a runtime command contains a bearer token
- **THEN** the printed reference shows `[redacted]` in its place

### Requirement: The command prints the receipt on demand
`groundwork evidence` SHALL forward verbatim to the installed module, print the estimate, the reasons, the signals and the references, support `--json` and `--transcript PATH`, default to the newest transcript of the current directory's project (looking in parent directories, never in another project's), report UNKNOWN when none exists, say which transcript it used, compare any `Confidence:` label stated in the last response with the estimate, and state that validation state is separate.

#### Scenario: Over-claim is flagged
- **WHEN** the last response states `Confidence: HIGH` and the estimate is `MEDIUM`
- **THEN** the output says the declared label exceeds what was observed

### Requirement: Bounded work and a readable failure
The estimate SHALL be derived within a fixed work budget (3 seconds of monotonic time): when the budget is spent `derive_evidence` raises `EvidenceBudgetExceeded`, the Stop hook records no observed evidence for the turn, and `groundwork evidence` prints `UNKNOWN` with the reason. A Bash command of more than 20,000 characters or more than 50 segments SHALL NOT be parsed and SHALL NOT be credited. Parsing of a review result SHALL be linear in its length. Inside the Stop hook the derivation SHALL get at most 3 seconds and no more than the time left of a 7-second hook budget; when none is left no observed evidence is recorded and the existing record is still written. `groundwork evidence` SHALL NOT print a traceback for an unreadable, unsearchable or over-long transcript path, a lone surrogate in a printed reference, or an output encoding that cannot show the receipt's punctuation.

#### Scenario: Hostile output shapes
- **WHEN** a result is 30,000 blank lines after `npm test`, or a REVIEW RESULT block is followed by thousands of space-padded lines, or forty 20,000-character commands of 2,850 segments each are run
- **THEN** the turn is analysed in well under two seconds, and none of those commands is credited

#### Scenario: A redirect notice
- **WHEN** a WebFetch result is a `REDIRECT DETECTED` notice
- **THEN** it is neither an external source nor a listed reference

#### Scenario: A failed runtime check
- **WHEN** a recognised runtime check (a `curl --fail` health check, `kubectl get`) fails after an earlier success, or is the only thing the turn did
- **THEN** the confidence is `LOW`, never `HIGH` and never `NONE`, until that same check (same words and target) succeeds; a different successful check, such as `kubectl get pods` after a failed health `curl`, does not clear it

#### Scenario: A failure seen through a pipe is cleared by the same tests run plainly
- **WHEN** `pytest tests/a 2>&1 | tail -3` fails and `pytest tests/a` then passes
- **THEN** the failure is cleared, because where output goes is not part of what is tested; a pass of different tests does not clear it

#### Scenario: A refused call is not evidence
- **WHEN** a Bash call returns an error that is a hook refusal, `Permission to use Bash with command … has been denied`, a denial by the built-in safety check or the auto-mode classifier, or the person's rejection
- **THEN** the call is ignored: it is not a failed check, a failed test, a change or a tool error

#### Scenario: Words in a runtime command's output
- **WHEN** `kubectl logs deploy/api | tail -20` exits 0 and its output contains `health check FAILED` or `3 errors`
- **THEN** it is not a failed runtime check, and a piped runtime command is credited only when its exit status speaks for it (`&&` chain, or `set -o pipefail`)

#### Scenario: Many test segments over a large result
- **WHEN** one Bash call chains 50 `pytest` segments and its result is 8 MB
- **THEN** the turn is analysed within the work budget (or reported UNKNOWN), because each text-wide question about the result is answered by one pass
