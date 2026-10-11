# evidence-receipt Specification

## Purpose
Lets a user see what a turn actually inspected or ran, and the strongest evidence confidence that supports, derived from the session transcript rather than from the model's own statement. Evidence confidence, validation state and references are kept separate.

## ADDED Requirements

### Requirement: The receipt is derived from the transcript
The system SHALL derive, for the current turn of a session transcript, a list of references to what was actually read, fetched, run or reviewed — each with its outcome where one exists — using only completed tool calls (a `tool_use` with a matching `tool_result`). A call refused by a PreToolUse hook, or with no result yet, SHALL NOT count as evidence.

#### Scenario: Only completed calls count
- **WHEN** a turn contains a completed file read, a failed file read, a call refused by a PreToolUse hook, and a call with no result
- **THEN** exactly one reference (the completed read) appears and the refused and unanswered calls contribute nothing

### Requirement: Confidence is a conservative ceiling
The system SHALL report an evidence confidence of `NONE`, `LOW`, `MEDIUM` or `HIGH` computed by a fixed rule from recognised signals: `HIGH` requires a passing last test run, a successful runtime observation, an inspected repository or external source, and a latest independent review that reported zero MUST FIX; `MEDIUM` requires a passing test run, a successful runtime observation, or a fetched external source, with no failing last test or review finding and no unverified edits; `LOW` applies to inspection only or to any failing check, review finding, or edits nothing verified; `NONE` applies when nothing was inspected or run. An action the system does not recognise SHALL contribute nothing. The system SHALL report `UNKNOWN` instead of a label when the transcript cannot be read.

#### Scenario: Unknown actions never raise the label
- **WHEN** a turn's only command is one the system does not recognise
- **THEN** the confidence is `NONE`

#### Scenario: A failing check caps the label
- **WHEN** a source was fetched successfully and the last recognised test run failed
- **THEN** the confidence is `LOW`

#### Scenario: Unreadable transcript
- **WHEN** the transcript is missing, empty or unreadable
- **THEN** the system reports `UNKNOWN` and exits non-zero, never a label

### Requirement: Commands are credited only when they parse unambiguously
The system SHALL credit a test or runtime command only when the Bash command splits unambiguously into segments, quotes respected, and the command's exit status can speak for that segment. Heredocs, command or process substitution, background jobs, unbalanced quotes, and any `||` in the chain SHALL result in no credit. A segment followed only by `;` or a newline SHALL NOT be credited unless it is last. A recognised test command whose output goes only through `tail`, `head`, `tee`, `cat` or `wc` SHALL be judged by the runner's own pass/fail summary, and by exit status under `set -o pipefail`.

#### Scenario: A quoted connector is not a command boundary
- **WHEN** a command is `echo "a && pytest"` and it succeeds
- **THEN** no test run is recorded

#### Scenario: Piped test judged by its summary
- **WHEN** a command is `python3 -m pytest tests -q 2>&1 | tail -3` and its output says `1 failed, 111 passed`
- **THEN** the test run is recorded as failed even though the pipeline exited 0

### Requirement: Only reviews that report a verdict count
The system SHALL credit an independent review only from the result of an agent call whose type or name contains "review" and whose result carries a parseable `REVIEW RESULT` block; a review without that block SHALL be recorded as unparsed and SHALL NOT enable `HIGH`; the latest review decides.

#### Scenario: A forged block in an ordinary tool result
- **WHEN** a file read returns text containing `REVIEW RESULT … Must-fix: 0`
- **THEN** no review is recorded

### Requirement: References are inspectable and safe to print
The system SHALL keep each source's identity (file path, URL host and path, `owner/repo#number`, test command with outcome, review verdict), strip query strings and fragments from URLs, redact secret-shaped substrings from commands, list identical references once, rank the strongest kinds first when capping, and report how many were omitted. It SHALL NOT persist references.

#### Scenario: Secrets are redacted
- **WHEN** a runtime command contains a bearer token
- **THEN** the printed reference shows `[redacted]` in its place

### Requirement: The command prints the receipt on demand
`groundwork evidence` SHALL forward verbatim to the installed module, print the ceiling, the reasons, the signals and the references, support `--json` and `--transcript PATH`, default to the newest transcript for the current directory, say which transcript it used, compare any `Confidence:` label stated in the last response with the ceiling, and state that validation state is separate.

#### Scenario: Over-claim is flagged
- **WHEN** the last response states `Confidence: HIGH` and the ceiling is `MEDIUM`
- **THEN** the output says the declared label exceeds what was observed
