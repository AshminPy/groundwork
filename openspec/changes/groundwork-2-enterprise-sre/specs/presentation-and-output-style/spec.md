# presentation-and-output-style Specification

## Purpose
Establishes the invariant that communication style (concise/technical/executive/incident/architecture/presentation framing, native Claude Code output styles) never changes factual meaning, and that presentation output is generated from the same authoritative evidence as any other Groundwork response — never fabricated to improve a slide. Presentation output routes through the existing DOCUMENT category/playbook; the truth/style separation is an addition to `output-contract.md`. Does not introduce a rendering engine, a design-system enforcement mechanism, or a new task-routing category. Native Claude Code output styles (verified, `code.claude.com/docs/en/output-styles`) own the "how" of communication; Groundwork's output contract continues to own the "what is true," per the platform's own documented guidance that output styles are unenforced instructions and anything that "has to happen without fail" belongs in a hook or rule Groundwork already controls.

## ADDED Requirements

### Requirement: Output contract governs truth regardless of style
Groundwork's evidence, validation, and completion-status rules (`output-contract.md`, `evidence-policy.md`) SHALL remain in force regardless of which output style (native Claude Code style, or none) is active in a session. A Groundwork-authored output style SHALL NOT restate, override, or weaken these rules.

#### Scenario: Non-default output style active
- **WHEN** a session has a non-Default output style selected
- **THEN** completion status, evidence labels, and validation statements in Groundwork-governed responses are unchanged in substance from what they would be under the Default style

### Requirement: Output style invariance
The same underlying evidence package, rendered under different output styles (e.g. technical vs. executive vs. presentation), SHALL yield equivalent factual claims and the same completion status — only tone, format, and level of detail SHALL differ.

#### Scenario: Same task, different styles
- **WHEN** a completed task's result is rendered once under a technical style and once under an executive/presentation style
- **THEN** every factual claim and the overall completion status are the same across both renderings; only presentation differs

### Requirement: Presentation content is sourced from authoritative evidence only
A presentation (slide deck, architecture review, demo, management summary) SHALL be generated only from the repository, configuration, runtime evidence, or verified findings the task actually established — matching `document.md`'s existing "gather the source of truth before writing" rule — and SHALL NOT include invented numbers, fabricated deployment/validation state, or architecture components that were not verified.

#### Scenario: Presentation requested after a completed task
- **WHEN** a presentation is generated summarizing a completed task
- **THEN** every metric, status, and architecture claim in it traces to that task's own recorded evidence, with nothing added for effect

#### Scenario: Evidence is incomplete
- **WHEN** some aspect of the work being presented was not verified (e.g. no runtime validation was performed)
- **THEN** the presentation states this plainly rather than presenting it as verified or omitting it to look more complete

### Requirement: Presentation output defaults to a portable format
Presentation output SHALL default to Markdown/Mermaid (or an equivalent plain-text, git-diffable format) unless a document-generation capability (e.g. an installed `document-skills`-equivalent plugin) is available and the user wants a bundled format (`.pptx`/`.docx`); Groundwork SHALL NOT assume such a plugin is installed and SHALL NOT degrade output quality or fail when it is absent.

#### Scenario: No document-generation plugin installed
- **WHEN** a presentation is requested and no pptx/docx-generation plugin is available
- **THEN** Groundwork produces Markdown/Mermaid output and states that a bundled-format plugin was not detected, rather than failing or silently producing a lower-quality substitute

### Requirement: No rendering engine or design-system enforcement mechanism is built
This capability SHALL NOT include a custom slide-rendering engine, image/diagram generator, or any hook/script enforcing visual design-system compliance. Visual consistency, where wanted, is achieved through an optional, separately-tracked template reference, not through new Groundwork machinery.

#### Scenario: Implementation footprint check
- **WHEN** this capability's implementation diff is reviewed
- **THEN** it touches only `output-contract.md` and `document.md`, and introduces no new script, hook, or rendering code
