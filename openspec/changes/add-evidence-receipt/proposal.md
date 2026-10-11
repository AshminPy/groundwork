## Why

Groundwork asks every substantive response to say what supports its conclusion (`Evidence & references`) and how verified it is (`Validation` in the Harness metadata block). Both are what the model *states*. Nothing derives them from what actually happened in the turn, so a confident-sounding response can name a source it never opened, or imply stronger evidence than it gathered. The two documented future candidates (docs/FUTURE-SCOPE.md §14.1 evidence references and §14.2 evidence confidence, recorded on PR #31) ask for exactly this to be made inspectable, and for confidence to be a deterministic label rather than the model's feeling.

## What Changes

- New `hooks/groundwork_evidence.py`: derives, from the session transcript, an **evidence receipt** for a turn (references to what was actually read, fetched, run and reviewed, each with its outcome) and an **evidence-confidence ceiling** (`NONE` | `LOW` | `MEDIUM` | `HIGH`, or `UNKNOWN` when the transcript cannot be read). The label is built only from signals the module recognises, so it can be too low and never too high.
- New `groundwork evidence` command (a pass-through, like `integrations` / `routines`): prints the receipt for the last turn on demand. Nothing is persisted.
- The Stop-hook telemetry record gains the ceiling and its signals (labels, counts and booleans only — no path, URL or command), the model's stated `Confidence:` label under `declared`, and whether the stated label exceeds the ceiling.
- Rule text: `evidence-policy.md` §2 and `output-contract.md` state that evidence confidence, validation state and references are three separate things, that a stated `Confidence:` must not exceed what the receipt shows, and that references name only sources actually inspected. No new lines in `output-contract.md` (it is at its enforced line cap).

Not in this change: a statusLine field, a dashboard panel, blocking a response whose stated label exceeds the ceiling, crediting background-agent hand-back messages as reviews.

## Capabilities

### New Capabilities
- `evidence-receipt`: derives and displays what a turn actually inspected or ran, and a deterministic evidence-confidence ceiling.

### Modified Capabilities
- `usage-telemetry`: the per-turn record carries the observed ceiling, the stated label and their comparison.

## Impact

`hooks/groundwork_evidence.py` (new; installed by the existing `hooks/*.py` copy), `hooks/groundwork_telemetry.py` (additive, fail-open import), `scripts/groundwork_cli.py` (one pass-through), `uninstall.sh`, `rules/evidence-policy.md`, `rules/output-contract.md`, README / ARCHITECTURE / CHANGELOG, tests. No new dependency, no network, no new persisted file.
