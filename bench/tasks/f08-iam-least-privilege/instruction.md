`iam/policy.json` is the IAM policy of the reports worker. It allows everything. Replace it with a
least-privilege policy based on `iam/access-log.jsonl`, 30 days of the worker's API calls (one JSON object per line:
`eventSource`, `eventName`, `resource` ARN and, for refused calls, `errorCode`). The IAM action for a line is
`<eventSource>:<eventName>`.
- Allow every call that succeeded in the log, on resources scoped as narrowly as the log supports (a wildcard only
  where the log shows several resources of the same kind under one path, for example several objects under one
  prefix).
- Do not allow anything that the log shows refused, or that is not in the log.
- No `"*"` action, no `<service>:*` action and no `"*"` resource. No `Condition` blocks are needed.
- Keep `"Version": "2012-10-17"`. `iam/main.tf` reads the file with `file()`; do not change it.
Checked statically; no AWS calls.
