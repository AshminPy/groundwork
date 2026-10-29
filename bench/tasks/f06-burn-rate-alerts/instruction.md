The checkout service has a 99.9% availability SLO, so its error budget is 0.001 of requests.
`metrics/requests.csv` has one row per minute (`minute,requests,errors`, where `minute` is the start of that minute).
We use the multi-window, multi-burn-rate alerts from the Google SRE workbook:
- the burn rate over a window of W minutes ending at minute m is (errors in minutes m-W+1 to m) / (requests in the
  same minutes) / 0.001;
- **page** at minute m when the 60-minute burn rate and the 5-minute burn rate are both above 14.4;
- **ticket** at minute m when the 360-minute burn rate and the 30-minute burn rate are both above 6;
- a window is evaluated only when all of its minutes are in the data (no partial windows).
Write `alerts.json` in the repository root: `{"page_first": ..., "ticket_first": ...}`, each the `minute` value of the
first minute at which that alert fires, or `null` if it never fires. Also write `firing.json`:
`{"page": [[first, last], ...], "ticket": [[first, last], ...]}`, every run of consecutive minutes during which that
alert's condition holds, as the `minute` values of the run's first and last minute, in time order (`[]` if never).
