# quiet-interaction Specification

## Purpose
Reduces low-value mid-turn narration in Claude Code sessions running Groundwork, so a normal engineering question reads closer to question → quiet evidence gathering → answer, without hiding anything safety-relevant or reducing evidence-gathering.

## ADDED Requirements

### Requirement: Mid-turn narration is discouraged for routine read-only work
Groundwork's output contract SHALL instruct Claude not to narrate routine read-only investigation (reads, searches, checks) as it happens. This instruction SHALL NOT reduce the evidence-gathering, verification, or testing Claude actually performs — only the narration of performing it.

#### Scenario: A simple read-only question produces no step-by-step narration
- **WHEN** a user asks a normal engineering question answerable by read-only investigation
- **THEN** the final response is not preceded by narration such as "I'll read...", "Now I'll check...", "Next I'll..." for each routine step

### Requirement: Safety-relevant and materially useful updates remain visible
The output contract's quiet-narration instruction SHALL NOT suppress: a request for user input or approval, a permission/approval gate, a blocker, a failure, conflicting evidence, a security concern, a destructive or mutating action, unexpected repository state that materially changes the task, or genuinely long-running work where progress information is useful.

#### Scenario: A blocker during investigation is still surfaced
- **WHEN** Claude encounters a blocker, a failure, a security concern, or conflicting evidence during otherwise-quiet investigation
- **THEN** that information is surfaced to the user, not suppressed by the quiet-narration instruction

### Requirement: The built-in Concise output style is additively configured
Groundwork's installer SHALL set `outputStyle` to `"Concise"` in `settings.json` only when that key is entirely absent. An existing user-configured `outputStyle` (any value, including `"Concise"` itself already set by the user) SHALL NOT be overwritten or removed by install, upgrade, or reconfiguration.

#### Scenario: Fresh install with no existing outputStyle preference
- **WHEN** a fresh Groundwork installation runs against a `settings.json` with no `outputStyle` key
- **THEN** `outputStyle` is set to `"Concise"`

#### Scenario: Existing explicit user preference is preserved
- **WHEN** `settings.json` already has an `outputStyle` key set to any value (including one different from `"Concise"`)
- **THEN** installing or upgrading Groundwork does not change that key

#### Scenario: Uninstall removes only what Groundwork itself set
- **WHEN** uninstalling Groundwork and the current `outputStyle` value exactly matches what Groundwork's installer would have set
- **THEN** the key is removed
- **WHEN** the current `outputStyle` value does not match what Groundwork would have set (the user changed it after install, or set it themselves before uninstall runs)
- **THEN** the key is left untouched
