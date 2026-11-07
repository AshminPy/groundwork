## ADDED Requirements

### Requirement: Coaching modifier
When the user asks to be coached, to brainstorm, or to learn to think like an architect, the router SHALL also read `~/.claude/groundwork/modes/coach.md` and apply it on top of the one selected category. The coach mode SHALL change the conversation style only, SHALL NOT be a category, and SHALL NOT relax evidence, review, authorization or safety rules.

#### Scenario: Coaching request
- **WHEN** the user says "coach me on designing the CloudAMQP connection setup"
- **THEN** the task is routed to one category (DESIGN), the coach mode is also read, and the reply asks for the user's own proposal before giving a recommendation

#### Scenario: Ordinary request
- **WHEN** the user asks "Design readiness probes for our API" with no coaching words
- **THEN** the coach mode is not read

#### Scenario: Install and uninstall
- **WHEN** `install.sh` runs and later `uninstall.sh` runs
- **THEN** `~/.claude/groundwork/modes/coach.md` is installed identical to the repository file, and is removed on uninstall
