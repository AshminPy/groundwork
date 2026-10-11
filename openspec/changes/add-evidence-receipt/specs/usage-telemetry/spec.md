## ADDED Requirements

### Requirement: Evidence confidence in the per-turn record
The per-turn record SHALL carry, under `observed`, the evidence-confidence estimate derived from the transcript (`NONE` | `LOW` | `MEDIUM` | `HIGH`), its signals as counts and booleans only, and whether the model's stated label exceeds the estimate (`true`, `false`, or null when either is not a recognised label); and under `declared`, the label the model stated (`none` | `low` | `medium` | `high` | `unknown`). It SHALL NOT contain any path, URL, command, repository identity or review text. If the derivation is unavailable or raises, or the transcript is unreadable (nothing to derive from), the record SHALL be written without the evidence fields and without the comparison; a decorated stated label (`High.`, `**HIGH**`, `MEDIUM/HIGH`) SHALL still be read as the label it states.

#### Scenario: An over-claim is an observed fact
- **WHEN** a response states `Confidence: HIGH` after a turn whose transcript supports only `MEDIUM`
- **THEN** `observed.evidence_confidence` is `MEDIUM`, `declared.evidence_confidence` is `high`, and `observed.declared_confidence_exceeds_observed` is `true`

#### Scenario: Nothing from the turn's content reaches the file
- **WHEN** the turn read a private path and ran a test command containing a canary string
- **THEN** neither the path nor the command text appears anywhere in the record

#### Scenario: A broken evidence module does not break telemetry
- **WHEN** the evidence module raises on import
- **THEN** the hook still exits 0 silently and writes the record without the evidence fields

#### Scenario: A context compaction falls inside a turn
- **WHEN** a context-compaction summary entry (`isCompactSummary`) appears between a human prompt and the end of the turn
- **THEN** the turn still starts at the human prompt, so edits and failures from before the compaction count toward the estimate and the `observed` counts

#### Scenario: The summariser request of a compaction
- **WHEN** a compaction inserts its summariser request as a user entry (`sdk`-originated, opening "Below is a conversation log from a Claude Code coding session", or followed within 200 entries, bookkeeping entries included, by the boundary) before the boundary and the summary
- **THEN** it does not start a turn, while a `claude -p` prompt (also `sdk`) and a typed prompt still do

#### Scenario: A long run of blanks in the model's answer
- **WHEN** the model's final message starts with 20,000 spaces or tabs, or `Overall:` is followed by thousands of blank lines
- **THEN** the Stop hook still finishes well inside its timeout and writes the record, because the status regexes (`OVERALL`, `STATUS_HEAD`, `LEAD_HEAD`, `NOTHING_LEFT`) bound their blank runs; and a transcript read that outlasts the hook deadline yields a record built from the entries read so far (a lower bound) rather than a lost one

#### Scenario: The Stop of a compaction's summariser turn
- **WHEN** the Stop hook fires at the end of the turn in which Claude Code summarises the context (the last main-thread assistant message descends, by `parentUuid`, from the summariser request)
- **THEN** no record is written, because the real turn has not ended; a Stop whose last assistant message does not descend from the request records the whole turn: after a compaction boundary, after a compaction that was aborted and never wrote one, before the summary reply lands, and for a Claude Code that writes no uuids
