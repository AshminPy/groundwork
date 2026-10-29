# Benchmark report: calibration-1 (calibration)

Model sonnet/medium; grader `2c03bc912992`, cases `8190e271e4e0`; code `bd14eab6effe`.

## Outcomes and cost per arm

| Arm | Runs | Completed | Incorrect claims | Probe pass | Errors/timeouts | Denials | Median wall s | Median tokens (out + uncached in) | Median cache read |
|---|---|---|---|---|---|---|---|---|---|
| V | 3 | 3/3 | 0 | - | 0 | 0 | 11 | 10,559 | 56,601 |
| E | 3 | 3/3 | 0 | - | 0 | 3 | 18 | 30,520 | 107,839 |
| G | 3 | 2/3 | 0 | - | 0 | 5 | 24 | 51,580 | 166,202 |

Tokens are output + uncached input + cache creation per run; cache reads are shown separately and not gated. Cost fields from Claude Code are list-price estimates and are not used.

## Calibration estimate for the full baseline

- **V:** mean 13 s per run × 76 planned runs ≈ 0.3 h; median 10,559 tokens and 56,601 cache-read tokens per run.
- **E:** mean 20 s per run × 76 planned runs ≈ 0.4 h; median 30,520 tokens and 107,839 cache-read tokens per run.
- **G:** mean 24 s per run × 76 planned runs ≈ 0.5 h; median 51,580 tokens and 166,202 cache-read tokens per run.
- **All arms, sequential:** about 1.2 h of run time.
- **G − E on the 3 calibration cases:** spread (SD) +58 pts; the minimum detectable difference at 14 cases would be about +46 pts. Three cases × one run is far too few to estimate this well; treat it as an order of magnitude.
- **G − V on the 3 calibration cases:** spread (SD) +58 pts; the minimum detectable difference at 14 cases would be about +46 pts. Three cases × one run is far too few to estimate this well; treat it as an order of magnitude.

## Per run

| Case | Arm | Rep | Completed | Claim | Wall s | Tokens | Error |
|---|---|---|---|---|---|---|---|
| c01-slugify-unicode | E | 1 | True | True | 18 | 35,249 |  |
| c01-slugify-unicode | G | 1 | True | True | 17 | 54,114 |  |
| c01-slugify-unicode | V | 1 | True | True | 10 | 9,554 |  |
| l03-rate-limiter | E | 1 | True | True | 23 | 30,520 |  |
| l03-rate-limiter | G | 1 | True | True | 31 | 51,580 |  |
| l03-rate-limiter | V | 1 | True | True | 17 | 12,429 |  |
| s01-incident-timeline | E | 1 | True | True | 17 | 28,240 |  |
| s01-incident-timeline | G | 1 | False | False | 24 | 49,662 |  |
| s01-incident-timeline | V | 1 | True | True | 11 | 10,559 |  |
