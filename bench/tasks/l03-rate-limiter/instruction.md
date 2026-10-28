Add client-side rate limiting to the API client:
- `apiclient/ratelimit.py`: a `TokenBucket(rate, capacity, clock=time.monotonic)` with `try_acquire(n=1) -> bool`
  (takes n tokens if available) and `wait_time(n=1) -> float` (seconds until n tokens will be available, 0 if they
  are now). The bucket starts full and refills continuously at `rate` tokens per second, never above `capacity`.
  `n` larger than `capacity` raises `ValueError`.
- `apiclient/config.py`: new settings `rate_per_second` (default 10) and `burst` (default 20), read from the
  environment variables `APICLIENT_RATE` and `APICLIENT_BURST` like the existing settings.
- `apiclient/client.py`: the `Client` builds its bucket from the settings, using the client's injected `clock`;
  `Client.request()` must take one token before each request; when none is available it sleeps for `wait_time()`
  using the injected `sleep` function, then retries.
The tests in tests/ are incomplete; your change will also be checked by other tests. Plan the change before you edit, and keep the existing public API working.
