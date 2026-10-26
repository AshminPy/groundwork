# payments-client

A small Python client for the PayAPI invoicing service.

```python
from payapi.client import fetch_invoice
invoice = fetch_invoice("inv_123")
```

See `docs/ARCHITECTURE.md` for design notes and `vendor-docs/` for the PayAPI reference pages we vendored.
