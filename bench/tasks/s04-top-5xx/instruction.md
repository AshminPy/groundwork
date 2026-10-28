From `logs/access.log` (nginx combined format), find the three request paths with the most 5xx
responses. Write `top_errors.json` in the repository root: a JSON list of three objects `{"path": ..., "count": ...}`,
highest count first (ties broken by path, alphabetically). Count only status codes 500-599; ignore query strings if
any.
