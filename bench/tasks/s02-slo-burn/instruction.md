The service has a 99.9% availability SLO (an error budget of 0.1% of requests over 30 days).
`metrics/requests.csv` holds per-minute request and error counts for a 4-hour window. Write `slo.json` in the
repository root with:
- `"requests"` and `"errors"`: the totals over the window;
- `"error_rate"`: errors / requests, as a fraction rounded to 6 decimals;
- `"burn_rate"`: the error rate divided by the error budget (0.001), rounded to 2 decimals;
- `"budget_consumed_pct"`: the share of the whole 30-day error budget this 4-hour window used, as a percentage
  rounded to 2 decimals, assuming the 30-day request volume is this window's volume × 180.
