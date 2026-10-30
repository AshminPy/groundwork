# Spec Delta

## Purpose

Defines how Groundwork uses OpenSpec, ECC, TDD and the EGM review method, so each tool is used where it is strongest, without duplication or conflict.

## ADDED Requirements

### Requirement: Every ECC component has a recorded role
Each ECC agent, skill, command and hook in use SHALL be listed in an inventory with one role: reused as-is, wrapped by a Groundwork agent, or disabled, with a reason for each. A Groundwork agent SHALL NOT duplicate an ECC component marked reused.

#### Scenario: New ECC version
- **WHEN** a new ECC version adds a hook
- **THEN** the release check fails until the inventory records its role

### Requirement: No integrated hook may prompt
No hook from ECC or any other integrated tool that stays enabled with Groundwork SHALL be able to return an ask decision. A hook that can SHALL be disabled or wrapped.

#### Scenario: ECC gate hook
- **WHEN** the inventory finds an ECC hook that can return ask
- **THEN** it is marked disabled or wrapped, and a replay test shows no prompt

### Requirement: OpenSpec is the plan format
T3 and T4 plans SHALL be OpenSpec changes that pass `openspec validate --strict`. The OpenSpec CLI version SHALL be pinned and checked by `gw doctor`.

#### Scenario: Wrong CLI version
- **WHEN** the installed OpenSpec CLI doesn't match the pinned version
- **THEN** `gw doctor` reports both versions and the fix

### Requirement: TDD is red before green
On T2 and higher, qa's tests SHALL be shown to fail before any builder starts, and to pass before a task is done. Both results SHALL be saved as evidence.

#### Scenario: Test passes before the change
- **WHEN** a new qa test already passes before the builder starts
- **THEN** qa must revise the test, and the builder doesn't start

### Requirement: EGM reviews run in a fresh context
egm and final-reviewer SHALL start with only the packet and the files it points to, never the conversation history. Each SHALL apply the shared review rubric.

#### Scenario: Reviewer context
- **WHEN** egm starts
- **THEN** its context holds the packet and the rubric, and no earlier conversation turns
