# teach-learn-capability Specification

## Purpose
Lets Groundwork turn a session's own verified work into learning material ("teach me what we just fixed") by reusing the existing EXPLAIN playbook and the evidence a task already established — including, when available, the rejected hypotheses and decisions recorded by `investigation-continuity`. Introduces no second knowledge store and no new task-routing category.

## ADDED Requirements

### Requirement: Teaching requests route to the existing EXPLAIN category
A request to teach, explain, or walk through completed or in-progress work SHALL route to the existing EXPLAIN category and playbook, unchanged, with the addition of a "teach from verified work" content branch.

#### Scenario: Teach-from-work request
- **WHEN** the request is "teach me what we just fixed"
- **THEN** it routes to EXPLAIN as any other explanatory request would

### Requirement: Content never exceeds the session's own established evidence
Explanations produced under this capability SHALL be limited to what the session's own evidence (completion facts, evidence chain, rejected hypotheses and decisions where `investigation-continuity` recorded them) actually established. Facts SHALL NOT be invented, reinterpreted, or embellished to make a more complete-sounding lesson.

#### Scenario: Complete evidence available
- **WHEN** the current or recent session established a clear root cause with a verified evidence chain
- **THEN** the explanation states the architecture, cause, diagnosis path, evidence used, and remediation exactly as established, including any rejected hypotheses and why they were rejected

#### Scenario: Teaching about unavailable prior work
- **WHEN** the work being taught about happened in a session whose evidence trail is not available (e.g. only a commit or ticket reference remains)
- **THEN** the response states plainly what is being reconstructed from available artifacts versus what would require the original session's evidence to state with confidence

### Requirement: No second knowledge store
This capability SHALL consume evidence already produced by existing Groundwork mechanisms (completion facts, `investigation-continuity`'s recorded state where present, transcript evidence) and SHALL NOT introduce a new persistent knowledge base, learning-history file, or database.

#### Scenario: Implementation footprint check
- **WHEN** this capability's implementation diff is reviewed
- **THEN** it touches only `playbooks/explain.md` and introduces no new storage mechanism

### Requirement: Optional quiz is clearly optional and evidence-bounded
When a short quiz is offered, its questions SHALL be drawn from the same bounded evidence as the explanation itself, SHALL be clearly optional, and SHALL NOT be presented as a completion or certification requirement.

#### Scenario: Quiz offered
- **WHEN** a teaching response includes an optional quiz
- **THEN** the quiz questions relate directly to the concepts covered in the explanation and are marked as optional
