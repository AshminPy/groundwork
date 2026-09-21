## Why

After 1.3.2, normal responses still rendered the Code / Tests / Reviewed / Merged / Deployed / Overall checklist (engineering-workflow §3 and the implement playbook still described it as the report form), and the Harness metadata block could state an execution mode, agent count and roles that disagreed with each other and with the Agent calls actually made.

## What Changes

- §3, output-contract, the two implement/deploy playbook lines and the private behaviour rules: completion facts in prose under Validation / Technical details; the aligned STATUS layout only on an explicit release/deployment-checklist request.
- output-contract: Execution and Agents must agree and come from the Agent calls actually launched.
- Hook: declared agent count / mode / roles reconciled against observed Agent calls (authoritative); regression tests.

## Non-goals

Schema 2, observed/declared separation, profile handling, outcome parsing, privacy filtering, fail-open, routing, security/evidence rules — unchanged.
