Add safe retries to the payments client (`payclient/`). The tests in tests/ are incomplete; your
change will also be checked by other tests. Plan the change before you edit, and keep the existing public API.
- `payclient/config.py`: new settings `max_attempts` (total attempts including the first, default 3) and
  `max_backoff` (seconds, default 10.0).
- `payclient/retry.py`: the retry policy. Retry only on HTTP 429, 502, 503, 504, or a `ConnectionError` from the
  transport. Wait before retry n (n = 1, 2, ...) for the response's `Retry-After` header if present, either as
  seconds (`"2"`) or as an HTTP date (`"Wed, 21 Oct 2026 07:28:00 GMT"`, relative to the client's injected `clock()`,
  which returns Unix seconds); otherwise `0.5 * 2 ** (n - 1)` seconds. Never wait more than `max_backoff`, never a
  negative time. Wait with the client's injected `sleep`.
- `Client.request` retries GET, PUT and DELETE, and POST only when the request has an `Idempotency-Key` header.
  When attempts run out, raise `PaymentError` with the last status (for a `ConnectionError`, re-raise it).
  Other 4xx/5xx statuses raise `PaymentError` at once.
- `create_charge` sends an `Idempotency-Key` made with the client's injected `new_id()`: one key per call of
  `create_charge`, the same key on every retry of that call.
