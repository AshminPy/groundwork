# DESIGN playbook

## Goal
Recommend one design that satisfies today's requirement with the smallest sound approach while preserving low-cost paths for foreseeable change, with the tradeoffs stated honestly.

## Workflow
1. Pin the requirement: what must be true when this is done, and the constraints that are evidence-backed (existing stack, conventions, scale, budget, security boundary).
2. Inspect what already exists before proposing anything new; reuse the project's platform, patterns and tooling first.
3. Apply `architecture-quality.md`: consider only the quality dimensions this design touches; for MATERIAL work answer its §2 questions (what changes, what is configuration, what needs a stable interface, how a second instance/provider/environment is added, failure handling, observability, security, testing, deployment/rollback, scale and cost).
4. Compare the two or three genuinely different options; discard the rest without ceremony. Prefer native/platform capability → configuration → existing tooling → small code.
5. Choose. Record the material choice as a DECISION record (`evidence-policy.md` §3) with real references. Say what you would deliberately not build.
6. This is a MATERIAL change in most cases: the design belongs in the OpenSpec `design.md` when the repo uses OpenSpec.

## Evidence
- Repository/config facts for "fits our architecture"; official docs for "why this approach"; label UNVERIFIED anything neither supports.

## Ask Before Acting When
- Two materially different valid architectures remain and no repository evidence, official doc, or stated constraint picks one; or the business/product intent itself is underspecified. Ask one question naming the fork. Do not ask to confirm a design the evidence already supports.

## Completion Criteria
- One recommendation, its material tradeoffs, its foreseeable variation points handled by configuration or an interface, and a named validation method.

## Output Format
```
Recommendation: <one design, one sentence>
Why:
- <key reasons only, each tied to evidence>
Design: <the shape: components, boundaries, what is configuration, how the next instance is added>
Tradeoffs:
- <material tradeoffs only>
Risks:
- <meaningful risks only, with how each is observed or mitigated>
Next: <the one action that moves this forward>
```
