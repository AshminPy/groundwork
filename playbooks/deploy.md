# DEPLOY playbook

## Goal
Change a running system (cloud, Kubernetes, Docker, local) safely, prove it is healthy afterwards, and know how to roll it back.

## Workflow
1. Identify the target precisely: environment, project/account, cluster, namespace, service, version. Never guess a target.
2. Inspect the current state of the target and the deployment mechanism the project already uses (CI/CD, Terraform, Helm, kubectl, scripts). Use that mechanism; do not improvise a parallel one.
3. Classify: any production, IAM, data or paid-resource change is MATERIAL (`engineering-workflow.md` §1) and, being irreversible or production-facing, requires explicit authorization (§4) — ask before applying. Non-production, reversible changes proceed.
4. Preview before applying wherever the tooling allows (`terraform plan`, dry-run, diff). Read the preview; a replace or destroy of a stateful resource is a stop-and-confirm.
5. Apply. Watch the rollout to completion.
6. Validate health on the real path: service health, a real request, pod/rollout status, logs, metrics or traces — not just an exit code 0.
7. Have the rollback ready before applying and state it; execute it if validation fails.
8. Respect the guards: no direct push to protected branches, no force-push, no `--dangerously-skip-permissions`, no weakening of security controls to make a deploy pass.

## Evidence
- The preview output, the apply/rollout result, and the post-deploy runtime observation, each as real output. "Deploy command exit 0" proves the artifact shipped, not that it works (`evidence-policy.md` §6).

## Ask Before Acting When
- The target cannot be determined unambiguously; the change touches production, IAM, data, or paid resources; the preview shows destruction or replacement; credentials are missing. Otherwise proceed.

## Completion Criteria
- Target confirmed, change applied through the project's mechanism, runtime health observed, rollback known. Anything unobserved is PARTIAL, not DEPLOYED.

## Output Format
Main response headings: **Status** (deployed / partial / failed / blocked) · **What was deployed** (target, version) · **Validation** (the runtime health check in plain words) · **Issues / rollback** (only when relevant).
Technical details carries the preview/apply output, the health-check command → result, the rollback command, and the completion block for MATERIAL deploys.
Then, per `output-contract.md`: `Technical details` and `Evidence & references` when they add something.
