Cart requests failed this morning. Using only the files in `logs/` (including `logs/ntp.log`,
which gives each host's clock offset from true time during the incident), write `incident.json` in the repository
root with exactly these keys, all times in true UTC as `YYYY-MM-DDTHH:MM:SSZ`:
- `"first_error_utc"`: the true time of the first user-facing error (a 5xx on a web host);
- `"first_error_host"`: which host logged it;
- `"user_impact_start_utc"`: the same as `first_error_utc`;
- `"recovered_utc"`: the true time of the first successful (200) request after the errors, on any web host;
- `"root_cause_host"`: the host where the failure started;
- `"root_cause"`: one of `"replication lag"`, `"migration lock"`, `"network partition"`.
Also write `timeline.csv` in the repository root: a CSV with the header `utc,host,level,message` and one row per line
of the web and db logs (not the ntp log), with `utc` in true UTC, sorted by `utc` and then by `host`; `message` is
the rest of the line after the level, unchanged.
A host whose clock is ahead logged timestamps later than true time. Round corrected times to the nearest second.
