---
description: Owner only — approve a Groundwork task's plan. Claude cannot run this.
argument-hint: <TASK-KEY> <approval-code>
disable-model-invocation: true
---
The owner typed: /gw-approve $ARGUMENTS

Groundwork's task gate checked this approval before this message reached you, and its note in your context says what it recorded. If the note says the approval was recorded, implement the approved plan within its scope and follow the steps in that note. If there is no such note, the gate is not installed or is disabled: tell the owner that, and do not treat this message as an approval.
