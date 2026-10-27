## ADDED Requirements

### Requirement: Per-turn token totals
Each per-turn record in `events.jsonl` SHALL include a `tokens` object for the current turn (the same turn boundary the record already uses) with `main` and `subagents` parts, each holding `input`, `output`, `cache_read`, `cache_creation` and `requests`. Values SHALL be summed over distinct assistant `message.id`s, using the last transcript line for each id; `requests` SHALL be the number of distinct ids. `subagents` SHALL be summed the same way from the session's subagent transcript files changed since the turn started. When the transcript is missing, no `tokens` key SHALL be written; when the turn was longer than the hook's read cap, `tokens.truncated` SHALL be `true`. The new code SHALL read only `type`, `timestamp`, `message.id` and `message.usage`, never message text, and SHALL NOT compute a price.

#### Scenario: Repeated lines for one reply
- **WHEN** a turn's transcript has five lines for message id A (last one with input 100) and three lines for id B (last one with input 200)
- **THEN** the record has `tokens.main.requests: 2` and `tokens.main.input: 300`

#### Scenario: Subagent work
- **WHEN** a turn ran one subagent whose transcript holds two distinct replies with input 1000 each
- **THEN** the record has `tokens.subagents.requests: 2` and `tokens.subagents.input: 2000`, and `tokens.main` excludes them

#### Scenario: No transcript
- **WHEN** the Stop event's `transcript_path` does not exist
- **THEN** the record has no `tokens` key and no error is shown

#### Scenario: Privacy
- **WHEN** the transcript contains a secret in message text
- **THEN** the secret never appears in `events.jsonl`

### Requirement: Token report
The existing report generator (`scripts/groundwork_report.py`) SHALL show, for its selected period, the median and 90th percentile of input tokens per turn and per request, for the main thread and for subagents, counted only from records that carry `tokens`, and SHALL state that conversational turns without a record are not included.

#### Scenario: Before and after a change
- **WHEN** the report runs over a period that includes records with and without `tokens`
- **THEN** the token section uses only records with `tokens` and shows how many records it used
