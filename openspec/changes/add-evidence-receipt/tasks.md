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
- [x] 4.2 Mutation checks: 90 mutants of the safety clauses (`python3 tests/mutation/mutate_evidence.py [name …]`, which mutates a copy of the tree): earlier runs found survivors that were either missing tests (now added) or redundant clauses (removed), and the final set was re-run in full: 90 of 90 caught, no survivors (runner `tests/mutation/mutate_evidence.py`, mutates a copy); differential test against a real bash (5,292 compositions)
- [x] 4.3 Real run on a live transcript (104 MB, 0.12 s; synthetic 40 MB single turn 1.0 s)
- [x] 4.4 CLI dispatch + uninstall test
- [x] 4.5 Full suite, `openspec validate --all --strict` against the main baseline
- [x] 4.6 Independent reviews: round 1 (16 must-fix) and round 2 (15 must-fix) fixed
- [x] 4.6b Confirmation review, security (6 MUST FIX: quadratic regexes and rescans that took 8 to 32 s on crafted output, past the hook timeout; `groundwork evidence` tracebacks on a lone surrogate, an unreadable or over-long path and a non-UTF-8 terminal; the label staying MEDIUM after a heredoc write, an unparseable command, a non-review subagent, a local MCP writer or an unknown tool; a WebFetch redirect counted as a source; false documentation claims (an unrecognised command is LOW, empty or 'nothing to be done' runs were credited, 5,292 not about 1,000 compositions); multi-cookie headers and glued `-uuser:pw` not redacted); all fixed, pinned by tests and mutants. Not changed, documented as known gaps: the commit heredoc idiom, `terraform plan` and `kubectl apply --dry-run=none` as test runs, more secret shapes
- [x] 4.6c Confirmation review, correctness (5 MUST FIX, 2 overlapping the security review: every possible change counted, empty or 'nothing to be done' runs; and new: gcloud/az names that look like verbs (`list-api`), curl/wget options read case-sensitively and inside clusters (`-f` was read as `-F`; `-fsSd` was missed), spec text for unknown actions and `||`); all fixed. Also from its notes: a review block with an off layout that plainly reports findings caps the label, lone surrogates, the README tree, the executable bit, the turn-boundary change and the transcript lag documented
- [ ] 4.6d Fresh confirmation review of the 4.6b and 4.6c fixes
- [ ] 4.7 Owner check of labels on sessions they know (RUNTIME VALIDATION REQUIRED)
