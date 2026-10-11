## 1. Derivation
- [x] 1.1 `hooks/groundwork_evidence.py`: transcript → signals, references, ceiling, reasons; `telemetry_summary`; `declared_exceeds`
- [x] 1.2 Quote-aware command splitter that rejects ambiguous commands; exit-status attribution; pipe-through-filter handling by the runner's own summary; `set -o pipefail`
- [x] 1.3 Reference redaction, URL query/fragment stripping, de-duplication, priority-ranked cap

## 2. Integration
- [x] 2.1 `hooks/groundwork_telemetry.py`: fail-open import; `observed.evidence_confidence`, `observed.evidence_signals`, `observed.declared_confidence_exceeds_observed`, `declared.evidence_confidence`
- [x] 2.2 `scripts/groundwork_cli.py`: `groundwork evidence` pass-through to the installed hook-directory module
- [x] 2.3 `uninstall.sh` removes the module and its bytecode

## 3. Rules and docs
- [x] 3.1 `rules/evidence-policy.md` §2: confidence / validation / references are separate; ceiling rule; never upgrades UNKNOWN or UNVERIFIED
- [x] 3.2 `rules/output-contract.md`: `Confidence:` field and references-from-the-receipt rule, within the existing line cap
- [ ] 3.3 README, ARCHITECTURE, CHANGELOG

## 4. Verification
- [x] 4.1 Unit tests on synthetic transcripts (label rule, attribution, ambiguity, pipes, references, privacy, CLI, Stop-hook integration incl. fail-open)
- [x] 4.2 Mutation checks of the safety clauses (each fails the tests); two equivalent/defence-in-depth mutants recorded
- [x] 4.3 Real run on a live transcript (83 MB, 0.15 s)
- [x] 4.4 CLI dispatch + uninstall test
- [ ] 4.5 Full suite, `openspec validate --all --strict` against the main baseline
- [ ] 4.6 Independent fresh-context review; fix MUST FIX; confirmation review
- [ ] 4.7 Owner check of labels on sessions they know (RUNTIME VALIDATION REQUIRED)
