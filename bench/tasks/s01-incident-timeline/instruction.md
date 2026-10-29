Checkout failed for part of the afternoon of 2026-04-11. Using only the logs in `logs/`, write
`incident.json` in the repository root with exactly these keys:
- `"impact_start"`: the UTC timestamp (as written in the logs) of the first user-facing error;
- `"impact_end"`: the UTC timestamp of the first successful checkout after the errors;
- `"impact_minutes"`: the whole minutes between them, rounded down;
- `"origin_service"`: the service where the failure started (`api`, `payments` or `db`);
- `"trigger"`: the event that triggered it, as one of `"deploy"`, `"traffic spike"`, `"database outage"`;
- `"mitigation"`: what ended it, as one of `"rollback"`, `"restart"`, `"scale up"`.
