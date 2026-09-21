# PLAN playbook

## Goal
Produce an executable, ordered plan whose steps another engineer could carry out, with real dependencies, real risks, and a clear definition of done.

## Workflow
1. State the goal and the current state it starts from (verify the current state from the repository, runtime or environment; do not plan from memory).
2. Break the work into phases that each leave the system in a working, verifiable state; order by dependency and by risk (prove the risky unknown early).
3. For each step name the action, the verification that proves it worked, and the rollback if it can fail in a way that matters.
4. Keep the plan to what the goal needs; cut steps that only exist to look thorough. Name explicitly what is out of scope.
5. Apply `architecture-quality.md` where a step introduces a variation point (environments, providers, regions) so the plan does not hard-wire the first instance.
6. For MATERIAL work in a repo that uses OpenSpec, the plan is the change's `tasks.md`; keep the two consistent.

## Evidence
- Current-state facts must come from inspection; every dependency must be real (a file, a service, an access right, a prior step), not assumed.

## Ask Before Acting When
- The target environment, the acceptable downtime, the rollback tolerance, or the scope boundary is unknown and would change the plan's shape. Otherwise assume the safest option, state it, and plan.

## Completion Criteria
- Every step has an owner action and a verification; dependencies and risks are the real ones; "done when" is observable.

## Output Format
Main response headings: **Goal** · **Plan** (numbered phases/steps, each with its verification) · **Dependencies / risks** (only when material) · **Done when**.
Then, per `output-contract.md`: `Technical details` and `Evidence & references` when they add something.
