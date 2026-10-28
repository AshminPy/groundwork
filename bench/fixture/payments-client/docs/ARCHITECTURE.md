# Architecture notes (written 2023-02)

- Every request is attempted exactly once. Retries are disabled, so callers must retry themselves.
- The default request timeout is 30 seconds.
- Invoices are listed with offset pagination.
