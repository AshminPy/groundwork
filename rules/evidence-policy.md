# Evidence policy (harness governance — HARD RULE, applies everywhere)

Material technical decisions and every completion claim must be evidence-backed. Intuition is a hypothesis, not evidence.

## 1. Evidence priority (use the highest available)
1. Current repository code / configuration
2. Actual runtime / environment output (commands, logs, API responses)
3. Official vendor documentation (current, version-appropriate)
4. Official standards / RFCs / specifications
5. Upstream source code
6. Official release notes / changelogs
7. Established engineering best practice
8. High-quality community evidence — only when nothing above exists, and labelled as such

These answer different questions and must not be conflated:
- Official docs prove **why** an approach is recommended.
- Repository evidence proves whether it **fits our architecture**.
- Tests / runtime evidence prove whether **our implementation actually works**.

## 2. Labels — never silently upgrade one into another
`VERIFIED` (seen in code, output, or an official source you actually read) · `UNVERIFIED` (plausible, not checked) · `ASSUMPTION` (a default taken to keep moving; say what would change if wrong) · `INFERENCE` (reasoned from other facts) · `RUNTIME VALIDATION REQUIRED` (cannot be known until executed/deployed). If something cannot be verified, say so. Never manufacture confidence.

## 3. Decision format — for MATERIAL decisions only
Use when a choice can materially affect architecture, security, reliability, production behaviour, deployment, data integrity, cost, maintainability or compatibility. Do not use it for trivial implementation choices.
```
DECISION
EVIDENCE
SOURCE / REFERENCE          (real URL or file path; version-appropriate)
WHY THIS APPROACH
ALTERNATIVES CONSIDERED     (only meaningful ones)
WHY REJECTED                (only when materially relevant)
TRADEOFFS
VALIDATION METHOD
CONFIDENCE / UNCERTAINTY
```

## 4. Source rules
- Give the actual reference (URL / file path / command). Prefer official documentation for the exact version in use (AWS → AWS docs, GCP → Google Cloud docs, Kubernetes → kubernetes.io, Terraform → HashiCorp/provider registry, GitHub → GitHub docs, Claude → Anthropic docs, ECC → the ECC repo, OpenSpec → the OpenSpec repo).
- A citation is proof only if it actually supports the claim — read it. Never fabricate URLs, citations, commands, flags, APIs, configuration fields or version behaviour. If a source cannot be found, say "no authoritative source found" and label the claim UNVERIFIED.

## 5. Completion evidence — what each artefact proves
| Evidence | Proves | Does NOT prove |
|---|---|---|
| Code written / diff | implementation exists | it works |
| Tests passed (exact command + result) | tested behaviour works | untested paths, integration, deployment |
| CI green | the pipeline's checks passed | runtime correctness |
| PR merged | change reached the target branch | it is deployed |
| Deploy command exit 0 / artifact version observed | intended artifact/config deployed | it behaves correctly live |
| Runtime check (request/log/metric observed) | deployed behaviour works for that check | everything else |
Never claim "works", "fixed", "verified", "done" or "deployed" without the corresponding row's evidence shown as: **what was tested → exact command → observed result → what it proves and does not prove.**

## 6. Incident / RCA rule
`CLAIM → EVIDENCE → SOURCE → CORRELATION → ROOT-CAUSE REASONING`. A symptom or state (e.g. `CrashLoopBackOff`, 502, OOMKilled) is not a root cause. Every root-cause conclusion needs an evidence chain (logs, events, config, timing correlation). Do not infer the cause from a common pattern alone; say "hypothesis" until proven.

## 7. Memory vs repository
Saved sessions, auto-memory and specs are useful but can be stale. Before acting on a remembered fact that matters, check it against the current repository/runtime; the repository wins, and the mismatch is reported.
