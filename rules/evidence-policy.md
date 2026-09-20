# Evidence policy (Groundwork governance — HARD RULE, applies everywhere)

Material technical decisions and every completion claim must be evidence-backed. Intuition is a hypothesis, not evidence.

## 1. Evidence priority (use the highest available)
1. Current repository code / configuration
2. Actual runtime / environment output (commands, logs, API responses, metrics, traces)
3. Official vendor documentation (current, version-appropriate)
4. Official standards / RFCs / specifications
5. Upstream source code / implementation
6. Official release notes / changelogs
7. Established engineering best practice
8. High-quality community evidence — only when nothing above exists, and labelled as such

These answer different questions and must not be conflated:
- Official docs prove **why** an approach is recommended.
- Repository evidence proves whether it **fits our architecture**.
- Tests / runtime evidence prove whether **our implementation actually works**.

## 2. Labels — never silently upgrade one into another
`VERIFIED` (seen in code, output, or an official source you actually read) · `UNVERIFIED` (plausible, not checked) · `ASSUMPTION` (a default taken to keep moving; say what would change if wrong) · `INFERENCE` (reasoned from other facts) · `RUNTIME VALIDATION REQUIRED` (cannot be known until executed/deployed). If something cannot be verified, say so. Never manufacture confidence. Never invent APIs, flags, capabilities, configuration, behaviour, or documentation.

## 3. DECISION record — for MATERIAL decisions only
Use when a choice can materially affect architecture, security, reliability, production behaviour, deployment, data integrity, cost, maintainability or compatibility. Do not use it for trivial implementation choices.
```
DECISION            what was chosen (one line)
EVIDENCE            the facts and their sources — real file paths, command output, or official URLs for the exact version in use
WHY                 why this approach; the meaningful alternatives and why they lost (only when materially relevant)
TRADEOFFS           what gets worse or is deferred
VALIDATION METHOD   how this will be proven (test, runtime check, live observation)
UNCERTAINTY         what is still assumed, inferred, or runtime-validation-required
```

## 4. Source rules
- Give the actual reference (URL / file path / command). Prefer official documentation for the exact version in use (AWS → AWS docs, GCP → Google Cloud docs, Kubernetes → kubernetes.io, Terraform → HashiCorp/provider registry, GitHub → GitHub docs, Claude Code → code.claude.com docs, ECC → the ECC repo, OpenSpec → the OpenSpec repo).
- A citation is proof only if it actually supports the claim — read it. Never fabricate URLs, citations, commands, flags, APIs, configuration fields or version behaviour. If a source cannot be found, say "no authoritative source found" and label the claim UNVERIFIED.

## 5. Validation ladder — derived from the project, progressively stronger
- Derive verification commands from the project's own evidence: README, Makefile, package manifests (`pyproject.toml`, `package.json`, `go.mod`, …), CI workflows, test layout. Do not run generic commands (`pytest`, `npm test`, `terraform validate`, …) unless project evidence shows they apply; if nothing is documented, infer the narrowest applicable check from the files present, label it INFERENCE, and say what remains unverified.
- Apply the rungs that are relevant, in order, and stop only when the change's real risk is covered:
  1. static / config validation (lint, type check, `terraform validate`, schema checks)
  2. unit tests
  3. integration tests
  4. build / package validation
  5. infrastructure validation (`terraform plan`, manifest dry-run, policy checks)
  6. controlled runtime test (local run, container, ephemeral environment)
  7. real non-production / live environment validation
- When runtime behaviour matters — an API, a deployed service, an MCP call, Kubernetes/GKE resources, cloud resources, logs, metrics, traces — test the real path when it is safe and available: the actual request, the deployed service's health, the real MCP call, the real `kubectl` read, the observed log/metric/trace. **Mocks and unit tests never prove runtime success.**
- If real validation cannot be performed (no environment, no credentials, no authorization), say exactly what remains unverified, label it RUNTIME VALIDATION REQUIRED, and never report COMPLETE.

## 6. Completion evidence — what each artefact proves
| Evidence | Proves | Does NOT prove |
|---|---|---|
| Code written / diff | implementation exists | it works |
| Tests passed (exact command + result) | tested behaviour works | untested paths, integration, deployment, runtime |
| Independent review done (reviewer + findings) | a fresh context found no MUST FIX left | that tests or runtime pass |
| CI green | the pipeline's checks passed | runtime correctness |
| PR merged | change reached the target branch | it is deployed |
| Deploy command exit 0 / artifact version observed | intended artifact/config deployed | it behaves correctly live |
| Runtime check (request/log/metric/trace observed) | deployed behaviour works for that check | everything else |
Never claim "works", "fixed", "verified", "done" or "deployed" without the corresponding row's evidence shown as: **what was tested → exact command → observed result → what it proves and does not prove.**

## 7. Incident / RCA rule
`CLAIM → EVIDENCE → SOURCE → CORRELATION → ROOT-CAUSE REASONING`. A symptom or state (e.g. `CrashLoopBackOff`, 502, OOMKilled) is not a root cause. Every root-cause conclusion needs an evidence chain (logs, events, config, timing correlation). Do not infer the cause from a common pattern alone; say "hypothesis" until proven.

## 8. Memory vs repository
Saved sessions, auto-memory, snapshots and specs are useful but can be stale. Before acting on a remembered fact that matters, check it against the current repository/runtime; the repository wins, and the mismatch is reported.
