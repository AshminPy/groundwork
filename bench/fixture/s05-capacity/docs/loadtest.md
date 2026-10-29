# checkout load test (2026-09-01)

One pod saturates (100% CPU) at 420 requests per second. CPU scales linearly with rps up to that
point. For availability we never run fewer than 3 pods.
