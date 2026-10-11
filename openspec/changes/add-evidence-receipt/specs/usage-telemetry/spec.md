## ADDED Requirements

### Requirement: Evidence confidence in the per-turn record
The per-turn record SHALL carry, under `observed`, the evidence-confidence ceiling derived from the transcript (`NONE` | `LOW` | `MEDIUM` | `HIGH`), its signals as counts and booleans only, and whether the model's stated label exceeds the ceiling (`true`, `false`, or null when either is not a recognised label); and under `declared`, the label the model stated (`none` | `low` | `medium` | `high` | `unknown`). It SHALL NOT contain any path, URL, command, repository identity or review text. If the derivation is unavailable or raises, the record SHALL be written without the evidence fields.

#### Scenario: An over-claim is an observed fact
- **WHEN** a response states `Confidence: HIGH` after a turn whose transcript supports only `MEDIUM`
- **THEN** `observed.evidence_confidence` is `MEDIUM`, `declared.evidence_confidence` is `high`, and `observed.declared_confidence_exceeds_observed` is `true`

#### Scenario: Nothing from the turn's content reaches the file
- **WHEN** the turn read a private path and ran a test command containing a canary string
- **THEN** neither the path nor the command text appears anywhere in the record

#### Scenario: A broken evidence module does not break telemetry
- **WHEN** the evidence module raises on import
- **THEN** the hook still exits 0 silently and writes the record without the evidence fields
