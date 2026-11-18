## 1. Implementation

- [x] 1.1 Telemetry: parse the one-line metadata form; add `has_metadata()`; keep the block form working
- [x] 1.2 Reply check: use `has_metadata()`; require Evidence only on file-changing turns; update reminder text
- [x] 1.3 Output contract: one-line metadata section; no-repeat rule for Technical details and the host recap box
- [x] 1.4 README and CHANGELOG describe the new form

## 2. Validation

- [x] 2.1 Tests for both metadata forms and the new evidence boundary; full suite green
- [x] 2.2 `openspec validate compact-reply-format --strict` passes
- [x] 2.3 Independent review with zero MUST FIX
