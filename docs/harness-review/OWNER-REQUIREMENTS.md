# Owner requirements (condensed, 2026-11-09)

Source: the owner's written answers in the harness-review conversation. Numbered so every keep/remove decision can
cite them. Goal: Claude Code that works like a highly competent senior CloudOps/SRE engineer. Everything else is
optional.

## Frustrations

| ID | Frustration | Expectation |
|---|---|---|
| F1 | No consistent, structured way of completing tasks; unclear problem, root cause, chosen fix, change, validation, remaining work; tasks feel endless | A consistent, transparent workflow with a clear outcome and completion criteria |
| F2 | Claude makes important decisions without involving the owner | Act as a senior advisor: explain findings and design decisions first, recommend with evidence, ask before decisions that change architecture, scope, security, cost or the agreed approach; then execute autonomously within the approved scope |
| F3 | Assumptions and inaccurate conclusions (example: a CloudAMQP version recommended without catching compatibility/security concerns) | Inspect real repos, configs, logs and runtime state; check vendor docs, versions, compatibility, security advisories and known limits before recommending; separate VERIFIED / ASSUMPTION / UNVERIFIED; challenge the owner when evidence says so |

## Requirements

| ID | Requirement |
|---|---|
| R1 | Works the same in the macOS desktop app (primary, managed from iPhone) and the CLI; no dependence on a terminal UI; replies concise and readable on mobile; no custom interface without a demonstrated need |
| R2 | Recognize the task type automatically; light process for questions and small low-risk changes; heavy process only for significant or high-risk work |
| R3 | Inspect and follow existing infrastructure patterns, naming, dependencies, security controls and deployment workflows (Terraform, GitOps, Flux, Spacelift, Helm, Kustomize, GKE, AWS, GCP …) instead of inventing new approaches |
| R4 | Native Claude Code features first; works with Claude Max (personal) and Enterprise (work) subscriptions; no extra paid model APIs or external services; respect Enterprise security; company code, credentials and data stay in approved tools and accounts; simple setup, update, diagnostics and rollback |
| R5 | Workflow: Understand → Investigate → Plan/Recommend → Approve when necessary → Implement → Validate → Report. After approval, continue autonomously within scope; stop and ask if a finding changes architecture, security, cost or the approved plan |
| R6 | Explicit authorization for production deployments, IAM changes, destructive operations, paid resource creation, PR merges and other high-impact actions. No repeated approvals for read-only investigation or approved local implementation. Deterministic controls around workflow, permissions, validation and completion |
| R7 | Completion states are distinct: Implemented, Tested, Reviewed, PR ready, Merged, Deployed, Live validated, Blocked/awaiting approval. Infra/deployment DONE = deployed to the authorized target and verified. Research/docs DONE = deliverable meets acceptance criteria with evidence. Never claim complete without verification |
| R8 | No endless loops: fix material problems, validate, stop when acceptance criteria are met |
| R9 | Factual audit before any keep/remove decision: installed, configured, executed, used, unused, duplicated, valuable, costly. A simple way to see which important capabilities a task used, without heavy metadata in every reply |
| R10 | One engineer first; portable and maintainable; no multi-user platform |
| R11 | Priority: correctness and safety → evidence and transparency → task completion → speed and efficiency. No duplicate agent work, excessive per-turn rules, repeated minor reviews, unnecessary approvals, expensive context, unmeasured ceremony, or re-investigating settled findings |
| R12 | Measure against plain Claude Code on representative real tasks: correctness, completion, serious errors, unnecessary interruptions, review iterations, time, tokens. Simplify or remove what shows no meaningful value |
| R13 | Integrations (AWS, GCP, GitHub, Spacelift, Jira/COR, Kubernetes/GKE, Elastic, Prometheus, Grafana, Cloudflare …) easy to discover, add, update, disable, remove and troubleshoot; MCP where useful, CLI/SDK/API when simpler; least privilege, read-only by default; show available/configured/connected/working; credentials never in logs, prompts or repos; native integration management first |
| R14 | Teach, not just execute: for important work explain what was wrong and why, how it was found, why the fix fits, what changed, how it was proved. Short replies; detailed evidence stored and retrievable later for explanation or documentation |
| R15 | Preserve objective, confirmed findings, decisions, rejected hypotheses, progress, blockers and next steps across sessions and compaction; minimal memory; current evidence beats saved notes; never reintroduce a rejected solution without new evidence |
| R16 | Before adding any hook, agent, skill, script, dashboard or rule, check whether Claude Code, ECC, OpenSpec or an existing component solves it; configuration and composition over custom frameworks; custom code only to enforce an important requirement existing tools cannot |
| R17 | Every capability must justify its maintenance and execution cost with evidence |
