## 1. Telemetry
- [x] 1.1 Hook: concise-block headline, ` / ` separator, status-language outcome classifier, schema 2 observed/declared, profile from env
- [x] 1.2 Tests: classifier cases (complete / partial / blocked / failed / missing-ambiguous → unknown), schema, profile, privacy, tail read, fail-open

## 2. Output
- [x] 2.1 output-contract: state word in Status, one status per response, four-line metadata block
- [x] 2.2 engineering-workflow §3 "Completion facts"; user rules (behavior/troubleshooting + toolkit mirror) aligned

## 3. Verify
- [x] 3.1 Regression: hooks/playbooks/pytest green; baseline diff limited to engineering-workflow.md
- [x] 3.2 Machine: `GROUNDWORK_PROFILE=work` in settings env; fresh session records `observed.profile: work` and `declared.outcome: complete`; response shows one status, no STATUS block
- [x] 3.3 Docs (README, ARCHITECTURE, CHANGELOG, VALIDATION), review, PR
