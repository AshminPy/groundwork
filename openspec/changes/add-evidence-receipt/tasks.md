## 1. Derivation
- [x] 1.1 `hooks/groundwork_evidence.py`: transcript → signals, references, estimate, reasons; `telemetry_summary`; `declared_exceeds`
- [x] 1.2 Quote-aware command splitter that rejects ambiguous commands; exit-status attribution; pipe-through-filter handling by the runner's own summary; `set -o pipefail`
- [x] 1.3 Reference redaction, URL query/fragment stripping, de-duplication, priority-ranked cap

## 2. Integration
- [x] 2.1 `hooks/groundwork_telemetry.py`: fail-open import; `observed.evidence_confidence`, `observed.evidence_signals`, `observed.declared_confidence_exceeds_observed`, `declared.evidence_confidence`
- [x] 2.2 `scripts/groundwork_cli.py`: `groundwork evidence` pass-through to the installed hook-directory module
- [x] 2.3 `uninstall.sh` removes the module and its bytecode

## 3. Rules and docs
- [x] 3.1 `rules/evidence-policy.md` §2: confidence / validation / references are separate; estimate rule; never upgrades UNKNOWN or UNVERIFIED
- [x] 3.2 `rules/output-contract.md`: `Confidence:` field and references-from-the-receipt rule, within the existing line cap
- [x] 3.3 README, ARCHITECTURE, CHANGELOG

## 4. Verification
- [x] 4.1 Unit tests on synthetic transcripts (label rule, attribution, ambiguity, pipes, references, privacy, CLI, Stop-hook integration incl. fail-open)
- [x] 4.2 Mutation checks: 55 mutants of the safety clauses (`python3 tests/mutation/mutate_evidence.py`, which mutates a copy of the tree). The previous run caught 53 of 56; the three survivors (`${…}` expansion, a risky environment prefix, a `pipefail` position rule) have since been pinned by tests or, for the last, the redundant clause was removed. A complete re-run of the final set is in progress runner `tests/mutation/mutate_evidence.py` (mutates a copy); differential test against a real bash (5,292 compositions)
- [x] 4.3 Real run on a live transcript (104 MB, 0.12 s; synthetic 40 MB single turn 1.0 s)
- [x] 4.4 CLI dispatch + uninstall test
- [x] 4.5 Full suite, `openspec validate --all --strict` against the main baseline
- [x] 4.6 Independent reviews: round 1 (16 must-fix) and round 2 (15 must-fix) fixed
- [ ] 4.6b Fresh confirmation review of the latest fixes
- [ ] 4.7 Owner check of labels on sessions they know (RUNTIME VALIDATION REQUIRED)
