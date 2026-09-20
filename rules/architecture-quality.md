# Architecture and implementation quality (Groundwork governance — applies to every engineering change)

Governing principle: **build the smallest design that satisfies today's requirement while preserving clear, low-cost paths for reasonably foreseeable change.** Do not over-engineer for hypothetical requirements. Do not hard-code obvious variation points. Think like a senior engineer/architect/SRE who will also operate the result.

## 1. Quality dimensions — decision criteria, not a checklist
Consider only the dimensions the change actually touches: correctness · modularity · reusability · extensibility · maintainability · operational excellence · reliability · availability/resilience · scalability · security · least privilege · observability · testability · automation · configuration management · deployment/rollback · performance/efficiency · cost effectiveness · sustainability · failure handling · supportability/troubleshooting.
- TRIVIAL: none of this. STANDARD: name the one to three dimensions that apply in the inline plan, nothing more. MATERIAL: answer §2 before implementing.

## 2. Before MATERIAL architectural work, answer explicitly (one line each, in the OpenSpec design or a DECISION record; "not applicable" is valid when true)
- What is likely to change? What should be configuration rather than code? What needs a stable interface?
- How would another instance / provider / environment / cluster / model / region / tenant be added?
- Which manual operational steps can reasonably be automated?
- What fails if a dependency is unavailable, and how is that failure handled and surfaced?
- How will an operator observe and troubleshoot this (logs, metrics, traces, status)?
- How will it be tested (unit → integration → runtime)? How is it deployed and rolled back?
- What security boundary exists (identity, least privilege, secrets, exposure)?
- What are the scaling and cost implications?

## 3. Variation points
If project evidence (code, config, roadmap, stated requirement) shows more than one environment, provider, cluster, model, region, tenant, backend, or similar variant — now or clearly foreseeable — put it behind a configuration value or an interface boundary; never wire the first instance permanently into the implementation. If there is exactly one and no evidence of more, keep it simple and say so in one line.

## 4. Abstractions
No abstraction, layer, plugin point, framework, or option without a concrete reason tied to a requirement or evidence. Prefer, in order: platform/native capability → configuration → tooling the project already uses → small deterministic code. Remove flexibility nobody asked for. Modular and reusable means clear boundaries and no duplication — not extra layers.

## 5. Conventions and vendors
Follow the project's established conventions first, then the vendor's current official guidance for the exact version in use (evidence-policy.md §1). Where they conflict, say which you followed and why. Never invent an API, flag, field, or behaviour to make a design fit.

## 6. Record
Material choices → the DECISION record in evidence-policy.md §3 (DECISION / EVIDENCE / WHY / TRADEOFFS / VALIDATION METHOD / UNCERTAINTY). Trivial choices → no record, no ceremony.
