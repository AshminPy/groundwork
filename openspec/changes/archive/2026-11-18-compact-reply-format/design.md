# Design: compact reply format

## Decisions

DECISION            One-line metadata, keyed segments split on " · "; the four-line block stays accepted.
EVIDENCE            `hooks/groundwork_telemetry.py` `parse_metadata` + `build_record` read only playbook, execution,
                    agents, evidence, validation, profile, environment; agent count/roles are reconciled against
                    observed Agent calls, so the declared Agents field is not load-bearing.
WHY                 Removing the block loses declared telemetry; a one-line form keeps it at a fraction of the space.
TRADEOFFS           Two accepted formats in the parser (small, tested).
VALIDATION METHOD   Unit tests for both forms in tests/test_telemetry.py and tests/test_reply_check.py.
UNCERTAINTY         None material.

DECISION            Reply check requires `Evidence & references` only when Edit/Write/MultiEdit/NotebookEdit ran.
EVIDENCE            rules/output-contract.md Layer 3 already says "omit the section when none does"; the hook's
                    unconditional check contradicted it.
WHY                 A file-changing turn always has a concrete thing to point at; a deterministic boundary is
                    testable, unlike "depends on sources".
TRADEOFFS           A read-only turn that makes a sourced claim relies on the rule, not the hook, to cite it.
VALIDATION METHOD   tests/test_reply_check.py cases for read-only, Bash-only and Edit turns.
UNCERTAINTY         Whether models still cite sources on read-only turns without the hook: observe in telemetry/use.

## Verification

```bash
python3 -m pytest tests -q
openspec validate compact-reply-format --strict
```
