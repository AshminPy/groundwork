We want the `checkout` deployment to run at no more than 60% CPU at peak. `metrics/cpu.csv` has a
day of hourly samples, and `docs/loadtest.md` has the load-test result. Write `capacity.json` in the repository root
with `"peak_rps"` (the highest rps in the samples) and `"pods_needed"` (the smallest whole number of pods that keeps
CPU at or below 60% at that peak, and never fewer than the minimum in `docs/loadtest.md`).
